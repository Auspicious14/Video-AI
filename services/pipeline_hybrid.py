"""
services/pipeline_hybrid.py  —  Unified Hybrid Video Pipeline
═══════════════════════════════════════════════════════════════════════════════

This is the primary production pipeline.  It unifies all three layers:

  Layer A (always):   Deterministic FFmpeg composition (renderer.py)
  Layer B (always):   AI asset generation — script, audio, images
  Layer C (optional): AI motion clips for enhanced scenes (ai_motion.py)

Illusion-Based Scene System
─────────────────────────────
Rather than generating a single long AI video (which current models do poorly),
we break the content into short shots and choose the best strategy per shot:

  • Short clips (≤4s) → text-to-video (Wan2.1)
  • Medium clips (4-8s) → image-to-video (SVD)
  • All clips → deterministic Ken Burns as guaranteed fallback

The output feels like a high-quality AI video even though it is a controlled
composition of AI-generated assets.

Fallback Ladder:
  1. AI video clip (Wan2.1 / SVD) — Layer C
  2. AI image + Ken Burns effect  — Layer A (always available)

Usage:
  from services.pipeline_hybrid import run_hybrid_pipeline
  await run_hybrid_pipeline(job_id, req)
"""

import asyncio
from pathlib import Path
from models import HybridVideoRequest
from services.script import generate_script
from services.audio import generate_audio, get_audio_duration
from services.images import get_image_client
from services.renderer import render_video
from services.ai_motion import generate_ai_clips_parallel
import store


async def run_hybrid_pipeline(job_id: str, req: HybridVideoRequest) -> None:
    """
    Full end-to-end hybrid pipeline:
      1. Script generation (Gemini)
      2. Audio generation (Kokoro TTS / gTTS )
      3. Image generation (Fal.ai / FLUX.1-schnell via HF)
      4. AI motion clips (Wan2.1 / SVD) — concurrent, non-blocking
      5. Deterministic video composition (FFmpeg)
    """
    try:
        # ── 1. Script ─────────────────────────────────────────────────────────
        store.update_job(job_id, status="generating_script", progress=5)
        script = await generate_script(req, req.health_awareness)
        store.update_job(
            job_id,
            caption=script.get("caption"),
            cta=script.get("cta"),
            progress=15,
        )

        # ── 2. Audio ──────────────────────────────────────────────────────────
        store.update_job(job_id, status="generating_audio", progress=20)
        audio_path = await generate_audio(
            script["narration"], job_id, req.voice_id
        )
        actual_duration = get_audio_duration(audio_path)

        # Distribute time evenly across scenes
        scenes      = script["scenes"]
        scene_count = len(scenes)
        per_scene   = round(actual_duration / scene_count, 3)
        for scene in scenes:
            scene["duration"] = per_scene

        store.update_job(job_id, progress=30)

        # ── 3. Images (Layer B) ────────────────────────────────────────────────
        store.update_job(job_id, status="generating_images", progress=35)
        client      = get_image_client()
        image_paths = await client.generate_images(scenes, job_id)
        store.update_job(job_id, progress=55)

        # ── 4. AI Motion Clips (Layer C) — concurrent ─────────────────────────
        ai_clips = None
        if req.use_ai_motion:
            store.update_job(
                job_id, status="generating_ai_motion", progress=60
            )

            def _progress(msg: str):
                store.update_job(job_id, status_detail=msg)

            ai_clips = await generate_ai_clips_parallel(
                scenes=scenes,
                job_id=job_id,
                image_paths=image_paths,
                progress_callback=_progress,
            )
            store.update_job(job_id, progress=75)

        # ── 5. Build subtitle lines from narration ────────────────────────────
        subtitle_lines = _build_subtitle_lines(
            script.get("narration", ""), actual_duration, scenes
        ) if req.subtitles else None

        # ── 6. Render (Layer A composition) ──────────────────────────────────
        store.update_job(job_id, status="rendering", progress=80)
        video_path = await render_video(
            audio_path=audio_path,
            image_paths=image_paths,
            script=script,
            job_id=job_id,
            actual_duration=actual_duration,
            ai_clip_paths=ai_clips,
            subtitle_lines=subtitle_lines,
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
        print(f"[hybrid_pipeline] Job {job_id} failed: {e}")
        raise


# ─── Script adapter for hybrid requests ──────────────────────────────────────

async def generate_script_for_hybrid(req: HybridVideoRequest) -> dict:
    """Adapts HybridVideoRequest → TikTokRequest-compatible for generate_script."""
    from models import TikTokRequest
    tiktok_req = TikTokRequest(
        user_email=req.user_email,
        topic=req.topic or req.prompt,
        tone=req.tone,
        duration=req.duration,
        brand_name=req.brand_name,
        voice_id=req.voice_id,
        health_awareness=req.health_awareness,
    )
    from services.script import generate_script
    return await generate_script(tiktok_req, req.health_awareness)


# ─── Subtitle builder ─────────────────────────────────────────────────────────

def _build_subtitle_lines(
    narration: str,
    total_duration: float,
    scenes: list,
) -> list:
    """
    Builds [(text, start_t, end_t), ...] for subtitle overlay.

    Strategy: split narration into per-scene chunks, timing each chunk
    to the scene's time window.  Each chunk is further split into
    2-4 word cards to keep subtitles readable.
    """
    if not narration.strip():
        return []

    words      = narration.split()
    n_words    = len(words)
    n_scenes   = len(scenes)
    sub_lines  = []
    t          = 0.0

    for i, scene in enumerate(scenes):
        dur = scene.get("duration", total_duration / n_scenes)
        # Proportional word count for this scene
        n_scene_words = max(1, round(n_words * (dur / total_duration)))
        start_idx = round(i * n_words / n_scenes)
        end_idx   = min(n_words, start_idx + n_scene_words)

        scene_words = words[start_idx:end_idx]
        if not scene_words:
            t += dur
            continue

        # Split scene words into 4-word cards
        card_size    = 4
        n_cards      = max(1, len(scene_words) // card_size + (1 if len(scene_words) % card_size else 0))
        card_dur     = dur / n_cards

        for j in range(n_cards):
            card_words = scene_words[j * card_size: (j + 1) * card_size]
            if not card_words:
                continue
            text      = " ".join(card_words)
            start_t   = t + j * card_dur
            end_t     = start_t + card_dur - 0.1   # tiny gap between cards
            sub_lines.append((text, round(start_t, 3), round(end_t, 3)))

        t += dur

    return sub_lines
