"""
services/pipeline_hybrid.py — Unified Hybrid Video Pipeline
═══════════════════════════════════════════════════════════════════════════════

This is the primary production pipeline. It unifies all three layers:

  Layer A (always):   Deterministic FFmpeg composition (renderer.py)
  Layer B (always):   AI asset generation — script, audio, images
  Layer C (optional): AI motion clips for enhanced scenes (ai_motion.py)

Adaptive Runtime Engine (Part 3)
──────────────────────────────────
Video duration is now driven by the actual narration length rather than a
strict fixed target. The pipeline:
  1. Determines the *target* duration from the user's preset / custom_duration.
  2. Generates the script aimed at that duration.
  3. Generates audio and measures actual narration length.
  4. Redistributes scene timing so total duration == actual narration length.
  5. Adjusts scene count proportionally if the actual narration significantly
     over- or under-shoots the target.

This allows a 30-second Short to scale seamlessly to a 10-minute documentary
without code changes — just changing the preset.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from models import HybridVideoRequest, scene_count_for_duration
from services.script import generate_script
from services.audio import generate_audio, get_audio_duration
from services.images import get_image_client
from services.renderer import render_video
from services.ai_motion import generate_ai_clips_parallel
import store

logger = logging.getLogger(__name__)


# ── Adaptive scene redistribution ─────────────────────────────────────────────

def _redistribute_scenes(
    script: dict,
    script_res,
    actual_duration: float,
    target_duration: int,
) -> tuple[list, float]:
    """
    Redistribute scene durations to match the actual narration length.

    Strategy
    ────────
    - Per-scene duration = actual_duration / scene_count
    - If actual >> target by >20%, warn but do NOT truncate
    - Scene count is unchanged (the script was already generated)
    - Returns (scenes, per_scene_duration)
    """
    scenes = script["scenes"]
    scene_count = len(scenes)

    if scene_count == 0:
        raise ValueError("Script has no scenes — cannot redistribute")

    ratio = actual_duration / max(target_duration, 1)
    if ratio > 1.25:
        logger.warning(
            "Narration exceeds target by %.0f%% (%.1fs vs %ds target) — adapting gracefully",
            (ratio - 1) * 100,
            actual_duration,
            target_duration,
        )
    elif ratio < 0.75:
        logger.info(
            "Narration shorter than target (%.1fs vs %ds target) — adapting gracefully",
            actual_duration,
            target_duration,
        )

    per_scene = round(actual_duration / scene_count, 3)
    for scene in scenes:
        scene["duration"] = per_scene
    for scene_res in script_res.scenes:
        scene_res.duration = per_scene

    logger.info(
        "Adaptive timing | actual=%.2fs target=%ds scenes=%d per_scene=%.2fs",
        actual_duration, target_duration, scene_count, per_scene,
    )
    return scenes, per_scene


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_hybrid_pipeline(job_id: str, req: HybridVideoRequest) -> None:
    """
    Full end-to-end hybrid pipeline:
      Stage 1: Research
      Stage 2: Script generation
      Stage 3: Audio generation  (ffprobe-safe with fallbacks)
      Stage 4: Adaptive timing redistribution
      Stage 5: Media acquisition (stock video / AI images)
      Stage 6: AI motion clips (optional, Layer C)
      Stage 7: Video rendering (FFmpeg, Layer A)

    Duration is driven by actual narration length (Adaptive Runtime Engine).
    """
    try:
        # ── Stage 1: Research ─────────────────────────────────────────────────
        store.update_job(
            job_id,
            status="researching",
            status_detail="Researching topic with AI…",
            progress=5,
        )
        from services.ai.research import run_research
        from services.ai.scripting import run_script_agent, _HEALTH_CONTEXT

        topic      = req.topic or req.prompt or "AI"
        tone       = req.tone
        target_dur = req.resolved_duration   # Adaptive Runtime — respects preset
        brand_name = req.brand_name
        platform   = getattr(req, "platform", "tiktok")

        store.update_job(job_id, status_detail=f"Researching '{topic}'…")

        niche = _HEALTH_CONTEXT if req.health_awareness else ""
        research = await run_research(
            topic=topic,
            tone=tone,
            duration=target_dur,
            platform=platform,
            niche_context=niche,
        )

        # ── Stage 2: Script ───────────────────────────────────────────────────
        store.update_job(
            job_id,
            status="generating_script",
            status_detail="Writing script…",
            progress=10,
        )

        # Use long-form template for longer durations
        template = "youtube_script" if target_dur > 90 else "tiktok_script"
        
        script_res = await run_script_agent(
            topic=topic,
            tone=tone,
            duration=target_dur,
            brand_name=brand_name,
            health_awareness=req.health_awareness,
            research=research,
            template=template,
            platform=platform,
        )
        script = script_res.to_legacy_dict()

        store.update_job(
            job_id,
            caption=script.get("caption"),
            cta=script.get("cta"),
            status_detail="Script ready — generating audio…",
            progress=15,
        )

        # ── Stage 3: Audio ────────────────────────────────────────────────────
        store.update_job(
            job_id,
            status="generating_audio",
            status_detail="Generating voiceover with Kokoro TTS…",
            progress=20,
        )

        audio_path = await generate_audio(
            narration=script["narration"],
            job_id=job_id,
            voice_id=req.voice_id,
        )
        actual_duration = get_audio_duration(audio_path)

        store.update_job(
            job_id,
            status_detail=f"Audio generated ({actual_duration:.1f}s) — planning scenes…",
            progress=27,
        )

        # ── Stage 4: Adaptive timing ──────────────────────────────────────────
        scenes, per_scene = _redistribute_scenes(
            script, script_res, actual_duration, target_dur
        )

        store.update_job(job_id, progress=30)

        # ── Stage 5: Media acquisition ────────────────────────────────────────
        store.update_job(
            job_id,
            status="acquiring_media",
            status_detail="Planning media for each scene…",
            progress=35,
        )
        from services.ai.media import acquire_media_assets

        image_paths, ai_clips = await acquire_media_assets(
            research=research,
            script=script_res,
            job_id=job_id,
            health_mode=req.health_awareness,
        )
        store.update_job(
            job_id,
            status_detail="Media assets ready — preparing render…",
            progress=55,
        )

        # ── Stage 6: AI motion clips (Layer C, optional) ──────────────────────
        if req.use_ai_motion:
            store.update_job(
                job_id,
                status="generating_ai_motion",
                status_detail="Generating AI motion clips (Wan2.1)…",
                progress=60,
            )

            def _progress(msg: str) -> None:
                store.update_job(job_id, status_detail=msg)

            motion_clips = await generate_ai_clips_parallel(
                scenes=scenes,
                job_id=job_id,
                image_paths=image_paths,
                progress_callback=_progress,
            )

            for idx in range(len(scenes)):
                if ai_clips[idx] is None and idx < len(motion_clips):
                    ai_clips[idx] = motion_clips[idx]

            store.update_job(job_id, progress=75)

        # ── Stage 7: Subtitle lines ───────────────────────────────────────────
        subtitle_lines = _build_subtitle_lines(
            script.get("narration", ""), actual_duration, scenes
        ) if req.subtitles else None

        # ── Stage 8: Render ───────────────────────────────────────────────────
        store.update_job(
            job_id,
            status="rendering",
            status_detail="Rendering video with FFmpeg…",
            progress=80,
        )
        video_path = await render_video(
            audio_path=audio_path,
            image_paths=image_paths,
            script=script,
            job_id=job_id,
            actual_duration=actual_duration,
            ai_clip_paths=ai_clips,
            subtitle_lines=subtitle_lines,
            aspect_ratio=req.aspect_ratio,
        )

        store.update_job(
            job_id,
            status="done",
            status_detail="Video ready!",
            progress=100,
            video_url=f"/outputs/{video_path.name}",
        )
        logger.info("Hybrid pipeline complete | job=%s duration=%.1fs", job_id, actual_duration)

    except Exception as exc:
        store.update_job(
            job_id,
            status="failed",
            error=str(exc),
            status_detail=f"Pipeline failed: {exc}",
            progress=0,
        )
        store.refund_credit(req.user_email)
        logger.exception("Hybrid pipeline failed | job=%s error=%s", job_id, exc)
        raise


# ── Subtitle builder ──────────────────────────────────────────────────────────

def _build_subtitle_lines(
    narration: str,
    total_duration: float,
    scenes: list,
) -> list:
    """
    Build [(text, start_t, end_t), ...] for subtitle overlay.

    Strategy: per-scene narration is split into 4-word cards, timed
    to the scene's window. Falls back to proportional word split if
    per-scene narration is not populated.
    """
    if not narration.strip():
        return []

    sub_lines: list = []
    t = 0.0
    n_scenes = max(1, len(scenes))
    words_all = narration.split()
    n_words = len(words_all)

    for i, scene in enumerate(scenes):
        dur = scene.get("duration", total_duration / n_scenes)
        scene_narration = scene.get("narration", "").strip()

        if scene_narration:
            scene_words = scene_narration.split()
        else:
            start_idx = round(i * n_words / n_scenes)
            end_idx   = round((i + 1) * n_words / n_scenes)
            scene_words = words_all[start_idx:end_idx]

        if not scene_words:
            t += dur
            continue

        card_size = 4
        n_cards   = max(1, (len(scene_words) + card_size - 1) // card_size)
        card_dur  = dur / n_cards

        for j in range(n_cards):
            card_words = scene_words[j * card_size: (j + 1) * card_size]
            if not card_words:
                continue
            start_t = t + j * card_dur
            end_t   = start_t + card_dur - 0.05
            sub_lines.append((" ".join(card_words), round(start_t, 3), round(end_t, 3)))

        t += dur

    return sub_lines


# ── Legacy script adapter (backward compat) ───────────────────────────────────

async def generate_script_for_hybrid(req: HybridVideoRequest) -> dict:
    """Adapts HybridVideoRequest → legacy generate_script interface."""
    from models import TikTokRequest
    tiktok_req = TikTokRequest(
        user_email=req.user_email,
        topic=req.topic or req.prompt,
        tone=req.tone,
        duration=req.resolved_duration,
        brand_name=req.brand_name,
        voice_id=req.voice_id,
        health_awareness=req.health_awareness,
    )
    from services.script import generate_script
    return await generate_script(tiktok_req, req.health_awareness)
