"""
services/ai_motion.py  —  Layer C: AI Motion Enhancement (selective)

Role in hybrid pipeline:
  This layer is OPTIONAL and ADDITIVE.  The deterministic Layer A
  (renderer.py) always works.  AI motion clips from this layer are used
  only if they arrive before the render timeout.

Fallback chain:
  1. Wan2.1-T2V-14B  (HuggingFace)  — best free text-to-video, ~30s latency
  2. StatistdiffVideoExtended        — image-to-motion via HF
  3. Skipped → Layer A handles the scene (still image + Ken Burns)

Design principles:
  • NEVER block the pipeline.  AI generation runs concurrently.
  • ALWAYS return a result (even None = Layer A takes over).
  • Retry transient HF errors (429, 503) up to MAX_RETRIES.
  • Cache generated clips by (prompt_hash + duration) to avoid re-generation.
"""

import asyncio
import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Optional
from config import HF_API_KEY, OUTPUT_DIR

# ─── Constants ────────────────────────────────────────────────────────────────
HF_API_BASE          = "https://api-inference.huggingface.co/models"
# WAN2_MODEL           = "Wan-AI/Wan2.1-T2V-14B"
SVD_MODEL            = "stabilityai/stable-video-diffusion-img2vid-xt"

MAX_RETRIES          = 3
RETRY_BACKOFF_BASE   = 4.0   # seconds (doubles on each retry)
GENERATION_TIMEOUT   = 120.0  # seconds — after this, skip and use Layer A
POLL_INTERVAL        = 5.0   # seconds between async polling attempts

# Clip cache directory
CLIP_CACHE_DIR = OUTPUT_DIR / "clip_cache"
CLIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─── Public interface ─────────────────────────────────────────────────────────

async def generate_ai_clip(
    prompt: str,
    duration: float,
    job_id: str,
    scene_index: int,
    image_path: Optional[Path] = None,
    width: int = 576,
    height: int = 1024,
    progress_callback=None,
) -> Optional[Path]:
    """
    Attempts to generate an AI video clip for a scene.

    Returns:
      Path to a downloaded .mp4 clip if successful.
      None if generation fails or times out (Layer A takes over).

    Args:
      prompt:          Scene description (from LLM script).
      duration:        Desired clip length in seconds.
      job_id:          For naming cached output files.
      scene_index:     Used for cache key and file naming.
      image_path:      If provided, tries image-to-video instead of text-to-video.
      progress_callback: Optional async callable(message: str).
    """
    if not HF_API_KEY:
        print(f"[ai_motion] HF_API_KEY not set — skipping AI clip (scene {scene_index})")
        return None

    # Check cache first
    cache_key  = _make_cache_key(prompt, duration, width, height)
    cached     = _check_cache(cache_key)
    if cached:
        print(f"[ai_motion] ✓ Cache hit for scene {scene_index}")
        return cached

    clip_path  = OUTPUT_DIR / f"{job_id}_aiclip_{scene_index:02d}.mp4"

    # Short clips (≤4s): prefer text-to-video
    # Longer clips: prefer image-to-video (more stable)
    try:
        if image_path and image_path.exists() and duration > 4.0:
            result = await _try_image_to_video(
                image_path, prompt, duration, clip_path,
                width, height, progress_callback
            )
        else:
            result = await _try_text_to_video(
                prompt, duration, clip_path,
                width, height, progress_callback
            )

        if result and result.exists() and result.stat().st_size > 10_000:
            _save_to_cache(cache_key, result)
            return result

    except asyncio.TimeoutError:
        print(f"[ai_motion] ⏱️ Timeout for scene {scene_index} — Layer A will handle it")
    except Exception as e:
        print(f"[ai_motion] ✗ Scene {scene_index} AI generation failed: {e}")
        print(traceback.format_exc())

    return None


async def generate_ai_clips_parallel(
    scenes: list,
    job_id: str,
    image_paths: list,
    progress_callback=None,
) -> list:
    """
    Generates AI clips for all scenes concurrently.
    Returns a list of Optional[Path] — None means Layer A handles that scene.
    """
    tasks = []
    for i, scene in enumerate(scenes):
        img = image_paths[i][0] if i < len(image_paths) else None
        tasks.append(
            asyncio.wait_for(
                generate_ai_clip(
                    prompt=scene.get("description", ""),
                    duration=scene.get("duration", 5.0),
                    job_id=job_id,
                    scene_index=i,
                    image_path=img,
                    progress_callback=progress_callback,
                ),
                timeout=GENERATION_TIMEOUT,
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    ai_clips = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            print(f"[ai_motion] Scene {i} exception: {res} — using Layer A")
            ai_clips.append(None)
        else:
            ai_clips.append(res)

    n_ok = sum(1 for r in ai_clips if r is not None)
    print(f"[ai_motion] {n_ok}/{len(scenes)} AI clips generated successfully")
    return ai_clips




async def _try_text_to_video(
    prompt: str,
    duration: float,
    output_path: Path,
    width: int,
    height: int,
    progress_callback=None,
) -> Optional[Path]:
    enhanced_prompt = (
        f"cinematic {width}x{height} vertical video, 9:16 aspect ratio, "
        f"smooth camera motion, professional cinematography, "
        f"{prompt}"
    )

    def _sync():
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(api_key=HF_API_KEY)
            video = client.text_to_video(enhanced_prompt, model="Wan-AI/Wan2.2-TI2V-5B")
            return video if isinstance(video, bytes) else (video.read() if hasattr(video, "read") else None)
        except Exception as e:
            print(f"[ai_motion] text-to-video failed: {e}")
            print(traceback.format_exc())
            return None

    if progress_callback:
        await _safe_callback(progress_callback, "🎬 Generating AI clip via Wan2.2…")

    loop = asyncio.get_event_loop()
    video_bytes = await loop.run_in_executor(None, _sync)

    if video_bytes and len(video_bytes) > 10_000:
        output_path.write_bytes(video_bytes)
        return output_path
    return None


# ─── Image-to-Video (SVD) ────────────────────────────────────────────────────

async def _try_image_to_video(
    image_path: Path,
    prompt: str,
    duration: float,
    output_path: Path,
    width: int,
    height: int,
    progress_callback=None,
) -> Optional[Path]:
    """
    Submits an image-to-video job to Stable Video Diffusion via HF InferenceClient.
    """
    from huggingface_hub import AsyncInferenceClient
    from PIL import Image

    if progress_callback:
        await _safe_callback(progress_callback, f"🖼️ Animating image via SVD…")

    try:
        image = Image.open(image_path)
        
        # Use AsyncInferenceClient for async operations
        client = AsyncInferenceClient(api_key=HF_API_KEY)
        
        # Generate video using image-to-video
        video_bytes = await client.image_to_video(
            image=image,
            model=SVD_MODEL,
            num_frames=max(16, int(duration * 6)),
            motion_bucket_id=127,   # controls motion intensity (0-255)
            noise_aug_strength=0.02,
        )
        
        # Save the video
        output_path.write_bytes(video_bytes)
        return output_path
    except Exception as e:
        print(f"[ai_motion] image-to-video failed: {e}")
        print(traceback.format_exc())
        return None


# ─── HF Inference call with retry (kept for compatibility) ────────────────────

async def _hf_inference_with_retry(
    model: str,
    headers: dict,
    payload: dict,
    output_path: Path,
    content_type_check: str = "video",
) -> Optional[Path]:
    """
    Kept for compatibility, but not used anymore — use AsyncInferenceClient instead.
    """
    return None


async def _poll_hf_job(
    client,
    job_url: str,
    headers: dict,
    output_path: Path,
) -> Optional[Path]:
    """Kept for compatibility."""
    return None


async def _download_url(
    client,
    url: str,
    output_path: Path,
) -> Optional[Path]:
    """Kept for compatibility."""
    return None


# ─── Clip cache ────────────────────────────────────────────────────────────────

def _make_cache_key(prompt: str, duration: float, width: int, height: int) -> str:
    raw = f"{prompt}|{duration:.1f}|{width}x{height}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _check_cache(key: str) -> Optional[Path]:
    path = CLIP_CACHE_DIR / f"{key}.mp4"
    if path.exists() and path.stat().st_size > 10_000:
        return path
    return None


def _save_to_cache(key: str, clip_path: Path) -> None:
    try:
        dst = CLIP_CACHE_DIR / f"{key}.mp4"
        if not dst.exists():
            dst.write_bytes(clip_path.read_bytes())
    except Exception as e:
        print(f"[ai_motion] Cache write failed: {e}")


# ─── Helpers ───────────────────────────────────────────────────────────────────

async def _safe_callback(callback, message: str) -> None:
    try:
        if asyncio.iscoroutinefunction(callback):
            await callback(message)
        else:
            callback(message)
    except Exception:
        pass