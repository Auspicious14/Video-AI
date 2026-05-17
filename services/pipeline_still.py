"""
services/pipeline_still.py

Pipeline for: Still Image → Motion
- Accepts an uploaded image file path
- Generates TTS audio from narration text
- Animates the still image with a deterministic Ken Burns effect
- Composites text overlays + audio → final MP4
"""

from pathlib import Path
from models import StillToMotionRequest
from services.audio import generate_audio, get_audio_duration
from services.renderer import render_still_to_motion, EFFECT_MAP
import store


async def run_still_to_motion_pipeline(
    job_id: str,
    req: StillToMotionRequest,
    image_path: Path,       # path to the uploaded image (already saved)
) -> None:
    try:
        # 1. Generate audio from narration
        store.update_job(job_id, status="generating_audio", progress=10)
        audio_path = await generate_audio(req.narration, job_id, voice_id=None)

        # 2. Measure actual audio duration
        actual_duration = get_audio_duration(audio_path)
        store.update_job(job_id, progress=40)

        # 3. Render: deterministic effect (or safe default)
        store.update_job(job_id, status="rendering", progress=50)
        effect_fn = EFFECT_MAP.get(req.effect) if req.effect else None

        video_path = await render_still_to_motion(
            image_path=image_path,
            audio_path=audio_path,
            hook_text=req.hook,
            cta_text=req.cta,
            actual_duration=actual_duration,
            job_id=job_id,
            effect_fn=effect_fn,
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
        raise
