"""
routers/cinematic.py — Cinematic generation endpoints
"""
import uuid

from fastapi import APIRouter, HTTPException, BackgroundTasks

from models import CinematicGenerateRequest, CinematicJobStatus
from pipelines.pipeline_cinematic import run_cinematic_pipeline
import store
from config import DEV_MODE, DEV_FREE_CREDITS


router = APIRouter(prefix="/api/cinematic", tags=["cinematic"])


def _gate(email: str) -> None:
    """Check/assign credits. Raises 402 if insufficient (in production mode)."""
    if DEV_MODE:
        if store.get_credits(email) == 0:
            store.set_credits(email, DEV_FREE_CREDITS)
    else:
        if store.get_credits(email) < 1:
            raise HTTPException(402, "Insufficient credits. Please top up.")
    store.deduct_credit(email)


@router.post("/generate", summary="Cinematic video generation pipeline")
async def generate_cinematic(req: CinematicGenerateRequest, background_tasks: BackgroundTasks):
    """
    Creates a cinematic video generation job.

    Pipeline:
      CinematicStateGraph → SceneIntent → ShotPlan → RenderExecutionPlan → Existing Rendering → Final Video

    Returns a job_id immediately. Poll /api/cinematic/status/{job_id} for progress.
    """
    _gate(req.user_email)
    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, video_type="cinematic")
    background_tasks.add_task(run_cinematic_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}", response_model=CinematicJobStatus, summary="Get cinematic job status")
def get_cinematic_status(job_id: str):
    """
    Returns the status of a cinematic generation job, including progress, current phase, and logs.
    """
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return CinematicJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        current_phase=job.get("current_phase"),
        logs=job.get("logs", []),
        video_url=job.get("video_url"),
    )

