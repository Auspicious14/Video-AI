"""
pipelines/pipeline_cinematic.py
Orchestrates the cinematic generation pipeline:
INPUT → CinematicStateGraph → SceneIntent → ShotPlan → RenderExecutionPlan → Existing Rendering → Final Video
"""
import asyncio
import uuid
from pathlib import Path

from models import CinematicGenerateRequest
from core.cinematic_state.service import CinematicStateService
from core.scene_intent.service import generate_scene_intent
from core.shot_planner.service import generate_shot_plan
from core.render_orchestrator.service import generate_render_execution_plan
from core.render_bridge.adapter import adapt_render_plan_to_pipeline

from services.script import generate_script
from services.audio import generate_audio, get_audio_duration
from services.images import get_image_client
from services.renderer import render_video

import store
from config import DEV_MODE, DEV_FREE_CREDITS, OUTPUT_DIR


async def run_cinematic_pipeline(job_id: str, req: CinematicGenerateRequest) -> None:
    """
    Runs the full cinematic generation pipeline.
    """
    try:
        # Create story_id from job_id
        story_id = job_id

        # Step 1: Initialize CinematicStateGraph
        store.update_job(
            job_id,
            status="running",
            progress=10,
            current_phase="cinematic_state",
            logs=["Initializing CinematicStateGraph"],
        )
        state = CinematicStateService.create_state(story_id)
        store.update_job(job_id, progress=20, logs=["CinematicStateGraph initialized"])

        # Step 2: Generate SceneIntent
        store.update_job(
            job_id,
            progress=30,
            current_phase="scene_intent",
            logs=["Generating SceneIntent sequence"],
        )
        scene_intent = generate_scene_intent(state)
        store.update_job(job_id, progress=40, logs=["SceneIntent generated"])

        # Step 3: Generate ShotPlans
        store.update_job(
            job_id,
            progress=50,
            current_phase="shot_planning",
            logs=["Generating ShotPlans for scenes"],
        )
        shot_plan = generate_shot_plan(scene_intent)
        store.update_job(job_id, progress=60, logs=["ShotPlans generated"])

        # Step 4: Generate RenderExecutionPlan
        store.update_job(
            job_id,
            progress=70,
            current_phase="render_execution_plan",
            logs=["Generating RenderExecutionPlan"],
        )
        render_plan = generate_render_execution_plan(shot_plan)
        store.update_job(job_id, progress=75, logs=["RenderExecutionPlan generated"])

        # Step 5: Convert RenderExecutionPlan into existing rendering inputs
        store.update_job(
            job_id,
            progress=80,
            current_phase="mapping_to_renderer",
            logs=["Mapping render instructions"],
        )
        # For MVP: Let's use existing hybrid pipeline logic
        from models import TikTokRequest
        tiktok_req = TikTokRequest(
            user_email=req.user_email,
            topic=req.topic,
            tone=req.tone,
            duration=req.duration_sec,
        )
        script = await generate_script(tiktok_req)
        store.update_job(job_id, progress=82, logs=["Script generated"])

        # Step 6: Render using existing infrastructure
        store.update_job(job_id, progress=84, status="generating_audio", logs=["Generating audio"])
        audio_path = await generate_audio(script["narration"], job_id, "21m00Tcm4TlvDq8ikWAM")
        actual_duration = get_audio_duration(audio_path)
        scenes = script["scenes"]
        scene_count = len(scenes)
        per_scene = round(actual_duration / scene_count, 3)
        for scene in scenes:
            scene["duration"] = per_scene
        store.update_job(job_id, progress=86, logs=["Audio generated"])

        store.update_job(job_id, progress=88, status="generating_images", logs=["Generating images"])
        client = get_image_client()
        image_paths = await client.generate_images(scenes, job_id)
        store.update_job(job_id, progress=92, logs=["Images generated"])

        store.update_job(job_id, progress=94, status="rendering", logs=["Rendering final video"])
        video_path = await render_video(
            audio_path=audio_path,
            image_paths=image_paths,
            script=script,
            job_id=job_id,
            actual_duration=actual_duration,
        )
        store.update_job(job_id, progress=98, logs=["Final video rendered"])

        # Finalize job
        store.update_job(
            job_id,
            status="done",
            progress=100,
            current_phase="completed",
            logs=["Job completed successfully"],
            video_url=f"/outputs/{video_path.name}",
        )

    except Exception as e:
        store.update_job(
            job_id,
            status="failed",
            error=str(e),
            progress=0,
            logs=[f"Job failed: {str(e)}"],
        )
        store.refund_credit(req.user_email)
        print(f"[cinematic_pipeline] Job {job_id} failed: {e}")
        raise
