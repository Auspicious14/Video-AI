"""
services/ai_motion.py  —  Layer C: AI Motion Enhancement (selective)
═══════════════════════════════════════════════════════════════════════════════

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
import httpx
import json
import time
from pathlib import Path
from typing import Optional
from config import HF_API_KEY, OUTPUT_DIR

# ─── Constants ────────────────────────────────────────────────────────────────
HF_API_BASE          = "https://api-inference.huggingface.co/models"
# WAN2_MODEL           = "Wan-AI/Wan2.1-T2V-14B"
SVD_MODEL            = "stabilityai/stable-video-diffusion-img2vid-xt"

MAX_RETRIES          = 3
RETRY_BACKOFF_BASE   = 4.0    # seconds (doubles on each retry)
GENERATION_TIMEOUT   = 120.0  # seconds — after this, skip and use Layer A
POLL_INTERVAL        = 5.0    # seconds between async polling attempts

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
        print(f"[ai_motion] ⏱ Timeout for scene {scene_index} — Layer A will handle it")
    except Exception as e:
        print(f"[ai_motion] ✗ Scene {scene_index} AI generation failed: {e}")

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
            client = InferenceClient(provider="fal-ai", api_key=HF_API_KEY)
            video = client.text_to_video(enhanced_prompt, model="Wan-AI/Wan2.2-TI2V-5B")
            return video if isinstance(video, bytes) else (video.read() if hasattr(video, "read") else None)
        except Exception as e:
            print(f"[ai_motion] text_to_video failed: {e}")
            return None

    if progress_callback:
        await _safe_callback(progress_callback, "🎬 Generating AI clip via Wan2.2…")

    loop = asyncio.get_event_loop()
    video_bytes = await loop.run_in_executor(None, _sync)

    if video_bytes and len(video_bytes) > 10_000:
        output_path.write_bytes(video_bytes)
        return output_path
    return None



# ─── Text-to-Video (Wan2.1) THIS IS 410 ERROR: GONE ───────────────────────────────────────────────────

# async def _try_text_to_video(
#     prompt: str,
#     duration: float,
#     output_path: Path,
#     width: int,
#     height: int,
#     progress_callback=None,
# ) -> Optional[Path]:
#     """
#     Submits a text-to-video job to Wan2.1 via HF Inference API.
#     HF API can be synchronous (bytes in response) or async (202 + polling).
#     Handles both patterns transparently.
#     """
#     enhanced_prompt = (
#         f"cinematic {width}x{height} vertical video, 9:16 aspect ratio, "
#         f"smooth camera motion, professional cinematography, "
#         f"{prompt}"
#     )

#     headers = {
#         "Authorization": f"Bearer {HF_API_KEY}",
#         "Content-Type": "application/json",
#         "X-Wait-For-Model": "true",
#     }
#     payload = {
#         "inputs": enhanced_prompt,
#         "parameters": {
#             "num_frames": max(16, int(duration * 8)),
#             "width": width,
#             "height": height,
#         }
#     }

#     if progress_callback:
#         await _safe_callback(progress_callback, f"🎬 Generating AI clip via Wan2.1…")

#     return await _hf_inference_with_retry(
#         model=WAN2_MODEL,
#         headers=headers,
#         payload=payload,
#         output_path=output_path,
#         content_type_check="video",
#     )


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
    Submits an image-to-video job to Stable Video Diffusion via HF.
    Encodes the image as base64 and sends as multipart.
    """
    import base64
    image_b64 = base64.b64encode(image_path.read_bytes()).decode()

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
        "X-Wait-For-Model": "true",
    }
    payload = {
        "inputs": f"data:image/jpeg;base64,{image_b64}",
        "parameters": {
            "num_frames": max(16, int(duration * 6)),
            "motion_bucket_id": 127,   # controls motion intensity (0-255)
            "noise_aug_strength": 0.02,
        }
    }

    if progress_callback:
        await _safe_callback(progress_callback, f"🖼️ Animating image via SVD…")

    return await _hf_inference_with_retry(
        model=SVD_MODEL,
        headers=headers,
        payload=payload,
        output_path=output_path,
        content_type_check="video",
    )


# ─── HF Inference call with retry ────────────────────────────────────────────

async def _hf_inference_with_retry(
    model: str,
    headers: dict,
    payload: dict,
    output_path: Path,
    content_type_check: str = "video",
) -> Optional[Path]:
    """
    Calls HF Inference API with exponential backoff on 429/503.
    Handles both synchronous (200 + body) and async (202 + polling) responses.
    """
    url     = f"{HF_API_BASE}/{model}"
    backoff = RETRY_BACKOFF_BASE

    async with httpx.AsyncClient(timeout=GENERATION_TIMEOUT) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if content_type_check in content_type or len(resp.content) > 50_000:
                        output_path.write_bytes(resp.content)
                        return output_path
                    # Might be JSON with a URL
                    try:
                        data = resp.json()
                        if isinstance(data, dict) and "url" in data:
                            return await _download_url(client, data["url"], output_path)
                    except Exception:
                        pass
                    print(f"[ai_motion] Unexpected 200 content-type: {content_type}")
                    return None

                elif resp.status_code == 202:
                    # Async job — poll for completion
                    data = resp.json()
                    job_url = data.get("job_id") or resp.headers.get("location")
                    if job_url:
                        return await _poll_hf_job(client, job_url, headers, output_path)
                    return None

                elif resp.status_code in (429, 503):
                    print(f"[ai_motion] HF rate-limited ({resp.status_code}), retry in {backoff:.0f}s…")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)

                elif resp.status_code == 404:
                    print(f"[ai_motion] Model {model} not found or unavailable")
                    return None

                elif resp.status_code == 401:
                    print("[ai_motion] Invalid HF_API_KEY — check .env")
                    return None

                else:
                    print(f"[ai_motion] Unexpected status {resp.status_code}: {resp.text[:200]}")
                    return None

            except httpx.TimeoutException:
                print(f"[ai_motion] Request timeout (attempt {attempt + 1})")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)

    return None


async def _poll_hf_job(
    client: httpx.AsyncClient,
    job_url: str,
    headers: dict,
    output_path: Path,
) -> Optional[Path]:
    """Polls an async HF job until completion or timeout."""
    deadline = time.monotonic() + GENERATION_TIMEOUT
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            resp = await client.get(job_url, headers=headers)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "video" in content_type or len(resp.content) > 50_000:
                    output_path.write_bytes(resp.content)
                    return output_path
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    url = data.get("output") or data.get("url")
                    if url:
                        return await _download_url(client, url, output_path)
                elif status in ("failed", "error"):
                    print(f"[ai_motion] HF job failed: {data}")
                    return None
        except Exception as e:
            print(f"[ai_motion] Poll error: {e}")

    print("[ai_motion] Polling timed out")
    return None


async def _download_url(
    client: httpx.AsyncClient,
    url: str,
    output_path: Path,
) -> Optional[Path]:
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            output_path.write_bytes(resp.content)
            return output_path
    except Exception as e:
        print(f"[ai_motion] Download failed: {e}")
    return None


# ─── Clip cache ───────────────────────────────────────────────────────────────

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


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _safe_callback(callback, message: str) -> None:
    try:
        if asyncio.iscoroutinefunction(callback):
            await callback(message)
        else:
            callback(message)
    except Exception:
        pass
