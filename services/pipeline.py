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
        # ── 1. Script & Research ──────────────────────────────────────────────
        store.update_job(job_id, status="researching", progress=5)
        from services.ai.research import run_research
        from services.ai.scripting import run_script_agent, _HEALTH_CONTEXT
        
        topic = req.topic
        tone = req.tone
        duration = req.duration
        brand_name = req.brand_name
        
        niche = _HEALTH_CONTEXT if req.health_awareness else ""
        research = await run_research(
            topic=topic,
            tone=tone,
            duration=duration,
            platform="tiktok",
            niche_context=niche,
        )
        
        store.update_job(job_id, status="generating_script", progress=10)
        script_res = await run_script_agent(
            topic=topic,
            tone=tone,
            duration=duration,
            brand_name=brand_name,
            health_awareness=req.health_awareness,
            research=research,
            platform="tiktok",
        )
        script = script_res.to_legacy_dict()
        
        store.update_job(
            job_id,
            caption=script.get("caption"),
            cta=script.get("cta"),
            progress=15,
        )

        # ── 2. Audio ──────────────────────────────────────────────────────────
        store.update_job(job_id, status="generating_audio", progress=20)
        audio_path = await generate_audio(script["narration"], job_id, req.voice_id)

        # ── 3. Measure actual audio duration — video matches this exactly
        actual_duration = get_audio_duration(audio_path)
        scene_count     = len(script["scenes"])
        per_scene       = round(actual_duration / scene_count, 3)
        for scene in script["scenes"]:
            scene["duration"] = per_scene
        for scene_res in script_res.scenes:
            scene_res.duration = per_scene
        store.update_job(job_id, progress=30)

        # ── 4. Media Acquisition (v2 Engine) ──────────────────────────────────
        store.update_job(job_id, status="acquiring_media", progress=35)
        from services.ai.media import acquire_media_assets
        image_paths, ai_clips = await acquire_media_assets(
            research=research,
            script=script_res,
            job_id=job_id,
            health_mode=req.health_awareness
        )
        store.update_job(job_id, progress=70)

        # ── 5. Render (deterministic, shake-free, 30fps)
        store.update_job(job_id, status="rendering", progress=75)
        video_path = await render_video(
            audio_path=audio_path,
            image_paths=image_paths,
            script=script,
            job_id=job_id,
            actual_duration=actual_duration,
            ai_clip_paths=ai_clips,
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