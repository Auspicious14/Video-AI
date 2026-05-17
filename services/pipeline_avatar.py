"""
services/pipeline_avatar.py  —  Talking Avatar Video Pipeline
═══════════════════════════════════════════════════════════════════════════════

Produces a talking head video where an AI avatar (or user's own face)
speaks the generated script directly to camera.

Pipeline:
  1. Script generation       (Gemini — same as hybrid pipeline)
  2. Audio generation        (gTTS / ElevenLabs)
  3. Face resolution         (FREE: FLUX portrait / PREMIUM: user upload)
  4. Avatar animation        (SadTalker → LatentSync → fallback)
  5. Scene B-roll images     (FLUX — shown during non-avatar moments)
  6. Composition             (renderer.py — avatar clip + B-roll + overlays)

Free vs Premium:
  FREE    — face_image_path is None   → AI-generated face portrait
  PREMIUM — face_image_path is set    → user's uploaded photo

Fallback:
  If both SadTalker and LatentSync fail, the pipeline falls back to
  run_hybrid_pipeline so the user always gets a video.

Output structure (30s example):
  0s  ───────────── 3s  : Hook text overlay on avatar
  0s  ── avatar clip ──► actual_duration : talking head speaks narration
  last 5s              : CTA text overlay
  B-roll images        : cut in during avatar pauses (optional, future)
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

from models import AvatarVideoRequest, TikTokRequest
from services.script import generate_script
from services.audio import generate_audio, get_audio_duration
from services.avatar import generate_avatar_video, is_premium_request
from services.renderer import render_avatar_video
from services.images import get_image_client
import store


async def run_avatar_pipeline(
    job_id: str,
    req: AvatarVideoRequest,
    face_image_path: Optional[Path] = None,   # None = free, Path = premium
) -> None:
    """
    Full avatar video pipeline.

    Wires together script → audio → face → animation → composition.
    Always produces a video — falls back to hybrid if animation fails.
    """
    try:
        # ── 1. Script ─────────────────────────────────────────────────────────
        store.update_job(job_id, status="generating_script", progress=5)
        script = await _generate_avatar_script(req)
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
        store.update_job(job_id, progress=30)

        # ── 3. Avatar animation ───────────────────────────────────────────────
        store.update_job(
            job_id,
            status="animating_avatar",
            progress=35,
            status_detail=(
                "Animating your face…" if face_image_path
                else f"Generating {req.avatar_style} avatar…"
            ),
        )

        avatar_clip = await generate_avatar_video(
            audio_path=audio_path,
            job_id=job_id,
            face_image_path=face_image_path,
            avatar_style=req.avatar_style,
        )
        store.update_job(job_id, progress=70)

        # ── 4. B-roll images (shown alongside / as fallback) ──────────────────
        store.update_job(job_id, status="generating_images", progress=72)
        scene_count = max(2, req.duration // 10)
        per_scene   = round(actual_duration / scene_count, 3)
        scenes      = [
            {
                "description": scene_desc,
                "duration": per_scene,
            }
            for scene_desc in _build_broll_descriptions(script, scene_count)
        ]

        client      = get_image_client()
        image_paths = await client.generate_images(scenes, job_id)
        store.update_job(job_id, progress=80)

        # ── 5. Compose final video ─────────────────────────────────────────────
        store.update_job(job_id, status="rendering", progress=82)

        if avatar_clip and avatar_clip.exists():
            # Happy path: avatar animation succeeded
            video_path = await render_avatar_video(
                avatar_clip=avatar_clip,
                audio_path=audio_path,
                image_paths=image_paths,
                script=script,
                job_id=job_id,
                actual_duration=actual_duration,
            )
        else:
            # Fallback: no avatar clip — use hybrid motion pipeline
            print(f"[avatar_pipeline] Avatar failed for job {job_id} — using hybrid fallback")
            store.update_job(
                job_id,
                status_detail="Avatar generation failed — using motion video instead",
            )
            from services.renderer import render_video
            video_path = await render_video(
                audio_path=audio_path,
                image_paths=image_paths,
                script=script,
                job_id=job_id,
                actual_duration=actual_duration,
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
        print(f"[avatar_pipeline] Job {job_id} failed: {e}")
        raise


# ─── Script adapter ───────────────────────────────────────────────────────────

async def _generate_avatar_script(req: AvatarVideoRequest) -> dict:
    """
    Generates a script optimised for talking head delivery.
    Injects avatar-specific instructions into the prompt via TikTokRequest.
    """
    tiktok_req = TikTokRequest(
        user_email=req.user_email,
        topic=_build_avatar_topic(req),
        tone=req.tone,
        duration=req.duration,
        brand_name=req.brand_name,
        voice_id=req.voice_id,
    )
    return await generate_script(tiktok_req)


def _build_avatar_topic(req: AvatarVideoRequest) -> str:
    """
    Enriches the topic with avatar delivery context so Gemini
    writes narration that sounds natural when spoken directly to camera.
    """
    style_context = {
        "doctor": (
            "You are a Nigerian doctor speaking directly and warmly to a patient. "
            "Use clear medical language. Be reassuring and authoritative."
        ),
        "presenter": (
            "You are a professional news presenter. "
            "Speak with authority and clarity. Structure like a news report."
        ),
        "friend": (
            "You are a young Nigerian content creator talking to your followers. "
            "Be casual, relatable, use TikTok-native language."
        ),
    }

    context = style_context.get(req.avatar_style, style_context["friend"])
    return f"{context}\n\nTopic: {req.topic}"


# ─── B-roll scene descriptions ────────────────────────────────────────────────

def _build_broll_descriptions(script: dict, count: int) -> list[str]:
    """
    Extracts scene descriptions from the script for B-roll images.
    Falls back to generic supporting visuals if scenes aren't available.
    """
    scenes = script.get("scenes", [])
    descriptions = [s.get("description", "") for s in scenes if s.get("description")]

    # Pad or trim to exact count
    while len(descriptions) < count:
        descriptions.append(descriptions[0] if descriptions else "cinematic abstract background")
    return descriptions[:count]


# ─── Render adapter in renderer.py ───────────────────────────────────────────
# NOTE: render_avatar_video needs to be added to renderer.py.
# It is a thin wrapper that:
#   1. Normalises the avatar clip to W×H @ FPS
#   2. Adds hook + CTA text overlays (same as render_video)
#   3. Muxes audio (avatar clip may already have audio; we replace it with
#      the clean TTS track)
#   4. Optionally composites B-roll images as picture-in-picture
#      (future enhancement — for now it's avatar full-screen)