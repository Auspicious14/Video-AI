"""
services/pipeline_ai_video.py  —  True AI Video Generation
═══════════════════════════════════════════════════════════════════════════════

UPDATED: Uses HuggingFace InferenceClient with Inference Providers (fal-ai →
replicate fallback). The old /models/ endpoint returned 410 Gone for all
video models — they've been migrated to the provider system.

Fallback chain:
  1. Wan2.2-TI2V-5B via fal-ai   (fastest)
  2. Wan2.2-TI2V-5B via replicate (fallback provider)
  3. Ken Burns (Layer A)          — always works, no external deps
"""

import asyncio
import base64
import io
import time
from pathlib import Path
from typing import Optional

from models import AIVideoRequest
from services.renderer import render_video, FPS
from services.audio import generate_audio, get_audio_duration
from services.images import get_image_client
from config import HF_API_KEY, OUTPUT_DIR
import store


# ─── Model + provider config ──────────────────────────────────────────────────

# The Wan2.1 models are GONE from the legacy HF Inference API (410).
# Wan2.2-TI2V-5B is the current model, available via Inference Providers.
WAN_MODEL = "Wan-AI/Wan2.2-TI2V-5B"

# Provider fallback order — fal-ai is fastest, replicate is the backup.
# Both support text_to_video with the above model.
PROVIDERS = ["fal-ai", "replicate"]

GENERATION_TIMEOUT = 180.0  # seconds per clip attempt


async def run_ai_video_pipeline(job_id: str, req: AIVideoRequest) -> None:
    """
    Layered AI video pipeline:
      1. Generate multi-scene plan from prompt
      2. Generate gTTS voiceover
      3. Generate FLUX still images per scene (always works)
      4. Attempt AI video clips via InferenceClient (Layer C)
      5. Compose final video — AI clips used where available, Ken Burns elsewhere
    """
    try:
        store.update_job(job_id, status="planning_scenes", progress=5)
        scenes = _plan_scenes(req)
        scene_count = len(scenes)

        store.update_job(job_id, status="generating_audio", progress=10)
        narration = req.narration or _build_narration(req.prompt, req.duration)
        audio_path = await generate_audio(narration, job_id)
        actual_duration = get_audio_duration(audio_path)

        # Distribute audio duration evenly across scenes
        per_scene = round(actual_duration / scene_count, 3)
        for scene in scenes:
            scene["duration"] = per_scene

        store.update_job(job_id, status="generating_images", progress=20)
        client = get_image_client()
        image_paths = await client.generate_images(scenes, job_id)
        store.update_job(job_id, progress=40)

        store.update_job(job_id, status="generating_video_clips", progress=45)
        ai_clips = await _generate_scene_clips_with_fallback(
            scenes, image_paths, job_id
        )
        store.update_job(job_id, progress=75)

        store.update_job(job_id, status="rendering", progress=80)
        script_meta = {
            "hook": req.hook or req.prompt[:60],
            "cta":  req.cta or "Watch the full video →",
        }
        video_path = await render_video(
            audio_path=audio_path,
            image_paths=image_paths,
            script=script_meta,
            job_id=job_id,
            actual_duration=actual_duration,
            ai_clip_paths=ai_clips,
            aspect_ratio=req.aspect_ratio,
        )

        store.update_job(
            job_id,
            status="done",
            progress=100,
            video_url=f"/outputs/{video_path.name}",
        )

    except Exception as e:
        store.update_job(job_id, status="failed", error=str(e), progress=0)
        store.refund_credit(req.user_email)
        print(f"[ai_video_pipeline] Job {job_id} failed: {e}")


# ─── Scene planning ───────────────────────────────────────────────────────────

def _plan_scenes(req: AIVideoRequest) -> list:
    base     = req.prompt
    duration = req.duration
    n_scenes = max(2, duration // 5)

    shot_types = [
        f"Extreme close-up, {base}, cinematic lighting",
        f"Wide establishing shot, {base}, dramatic atmosphere",
        f"Medium shot, {base}, dynamic motion",
        f"Over-the-shoulder shot, {base}, emotional depth",
        f"Low angle looking up, {base}, epic scale",
        f"Aerial bird-eye view, {base}, sweeping panorama",
    ]

    return [
        {
            "description": shot_types[i % len(shot_types)],
            "duration": round(duration / n_scenes, 3),
        }
        for i in range(n_scenes)
    ]


def _build_narration(prompt: str, duration: int) -> str:
    return f"{prompt}. Experience the moment."


# ─── AI clip generation with provider fallback ────────────────────────────────

async def _generate_scene_clips_with_fallback(
    scenes: list,
    image_paths: list,
    job_id: str,
) -> list:
    tasks = [
        _get_clip_for_scene(
            scene=scenes[i],
            image_path=image_paths[i][0] if i < len(image_paths) else None,
            job_id=job_id,
            scene_index=i,
        )
        for i in range(len(scenes))
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    clips = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"[ai_video] Scene {i} exception: {r} — using Ken Burns")
            clips.append(None)
        else:
            clips.append(r)

    n_ok = sum(1 for c in clips if c is not None)
    print(f"[ai_video] AI clips: {n_ok}/{len(scenes)} succeeded")
    return clips


async def _get_clip_for_scene(
    scene: dict,
    image_path: Optional[Path],
    job_id: str,
    scene_index: int,
) -> Optional[Path]:
    """
    Tries each provider in PROVIDERS order until one succeeds.
    Returns None → Ken Burns handles this scene.
    """
    if not HF_API_KEY:
        print("[ai_video] HF_API_KEY not set — skipping AI clips")
        return None

    out_path = OUTPUT_DIR / f"{job_id}_aiclip_{scene_index:02d}.mp4"

    for provider in PROVIDERS:
        result = await asyncio.wait_for(
            _call_inference_provider(
                provider=provider,
                prompt=scene["description"],
                image_path=image_path,
                out_path=out_path,
                scene_index=scene_index,
            ),
            timeout=GENERATION_TIMEOUT,
        )
        if result and result.exists() and result.stat().st_size > 10_000:
            return result

    print(f"[ai_video] Scene {scene_index}: all providers failed — Ken Burns fallback")
    return None


async def _call_inference_provider(
    provider: str,
    prompt: str,
    image_path: Optional[Path],
    out_path: Path,
    scene_index: int,
) -> Optional[Path]:
    """
    Uses huggingface_hub InferenceClient to call Wan2.2 via the given provider.
    Runs the blocking SDK call in a thread pool to stay async-safe.
    """
    def _sync_generate() -> Optional[bytes]:
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(provider=provider, api_key=HF_API_KEY)

            if image_path and image_path.exists():
                # Image-to-video: pass image bytes as input
                image_bytes = image_path.read_bytes()
                video = client.image_to_video(
                    image=image_bytes,
                    model=WAN_MODEL,
                )
            else:
                # Text-to-video
                video = client.text_to_video(
                    prompt,
                    model=WAN_MODEL,
                )

            # SDK returns bytes or a file-like object depending on version
            if isinstance(video, bytes):
                return video
            elif hasattr(video, "read"):
                return video.read()
            else:
                # Some versions return a path string or other object
                print(f"[ai_video] Unexpected return type from SDK: {type(video)}")
                return None

        except Exception as e:
            print(f"[ai_video] Scene {scene_index} via {provider}: {e}")
            return None

    loop = asyncio.get_event_loop()
    video_bytes = await loop.run_in_executor(None, _sync_generate)

    if video_bytes and len(video_bytes) > 10_000:
        out_path.write_bytes(video_bytes)
        print(f"[ai_video] ✓ Scene {scene_index} via {provider} ({len(video_bytes)//1024}KB)")
        return out_path

    return None
