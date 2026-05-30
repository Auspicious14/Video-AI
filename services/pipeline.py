"""
services/pipeline.py  —  Original TikTok pipeline (backward-compatible)

For new integrations, prefer services/pipeline_hybrid.py which adds:
  • Layer C AI motion clips
  • Subtitle cards
  • Full progress tracking
"""

from models import TikTokRequest
from services.script import generate_script
from services.audio import generate_audio, get_audio_duration
from services.images import get_image_client
from services.renderer import render_video
import store


async def run_tiktok_pipeline(job_id: str, req: TikTokRequest) -> None:
    try:
        # 1. Generate script
        store.update_job(job_id, status="generating_script", progress=5)
        script = await generate_script(req, req.health_awareness)
        store.update_job(
            job_id,
            caption=script.get("caption"),
            cta=script.get("cta"),
            progress=15,
        )

        # 2. Generate audio
        store.update_job(job_id, status="generating_audio", progress=20)
        audio_path = await generate_audio(script["narration"], job_id, req.voice_id)

        # 3. Measure actual audio duration — video matches this exactly
        actual_duration = get_audio_duration(audio_path)
        scene_count     = len(script["scenes"])
        per_scene       = round(actual_duration / scene_count, 3)
        for scene in script["scenes"]:
            scene["duration"] = per_scene
        store.update_job(job_id, progress=30)

        # 4. Generate images
        store.update_job(job_id, status="generating_images", progress=35)
        client      = get_image_client()
        image_paths = await client.generate_images(script["scenes"], job_id)
        store.update_job(job_id, progress=70)

        # 5. Render (deterministic, shake-free, 30fps)
        store.update_job(job_id, status="rendering", progress=75)
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
        raise