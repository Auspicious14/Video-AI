"""
routers/videos.py — Video generation endpoints
═══════════════════════════════════════════════════════════════════════════════

Endpoints
─────────
  POST /generate/hybrid            — Primary full pipeline (Adaptive Runtime)
  POST /generate/youtube-studio    — AI-first documentary production package
  POST /generate/tiktok            — Legacy backward-compatible TikTok pipeline
  POST /generate/ai-video          — Layer C primary (CogVideoX → Wan2.1 → Ken Burns)
  POST /generate/still-to-motion   — Upload image → animated Ken Burns video
  POST /generate/motion-design     — Remotion programmatic animation
  POST /generate/motion-design/flyer — Flyer image → Remotion animation
  POST /generate/avatar            — AI-generated face talking head (FREE)
  POST /generate/avatar/premium    — User-uploaded face talking head (PREMIUM)
  POST /generate/trends/scan       — Trigger trend discovery sweep
  POST /generate/trends/hybrid     — Trend-augmented hybrid video
  GET  /generate/trends/dashboard  — Trends dashboard view
  POST /generate/batch             — Batch multi-video generation ← NEW
  GET  /generate/batch/{batch_id}  — Batch status ← NEW
  GET  /generate/jobs/{job_id}     — Per-job status (progress, ETA, warnings)
  GET  /generate/presets           — Available duration presets ← NEW
  GET  /generate/voices            — Available voices ← NEW
"""

import uuid
import shutil
from pathlib import Path
from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from models import (
    TikTokRequest,
    StillToMotionRequest,
    HybridVideoRequest,
    YouTubeStudioRequest,
    MotionDesignRequest,
    AIVideoRequest,
    JobStatus,
    AvatarVideoRequest,
    TrendPipelineRequest,
    BatchGenerationRequest,
    BatchJobStatus,
    BatchJobItem,
    DURATION_PRESETS,
)
from services.pipeline import run_tiktok_pipeline
from services.pipeline_still import run_still_to_motion_pipeline
from services.pipeline_hybrid import run_hybrid_pipeline
from services.ai.studio import run_youtube_studio_production
from services.pipeline_motion_design import run_motion_design_pipeline
from services.pipeline_ai_video import run_ai_video_pipeline
from services.pipeline_avatar import run_avatar_pipeline
from services.pipeline_trends import run_trend_pipeline
from services.pipeline_batch import run_batch_pipeline, create_batch
from services.audio import VOICE_REGISTRY
from services.ai.trends.scheduler import TrendScheduler
from services.ai.trends.schemas import ScanFrequency
import store
from config import DEV_MODE, DEV_FREE_CREDITS, OUTPUT_DIR

router = APIRouter(prefix="/generate", tags=["videos"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _gate(email: str) -> None:
    """Check/assign credits. Raises 402 if insufficient (in production mode)."""
    if DEV_MODE:
        if store.get_credits(email) == 0:
            store.set_credits(email, DEV_FREE_CREDITS)
    else:
        if store.get_credits(email) < 1:
            raise HTTPException(402, "Insufficient credits. Please top up.")
    store.deduct_credit(email)


def _new_job(video_type: str) -> str:
    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, video_type=video_type)
    return job_id


# ─── Discovery endpoints ──────────────────────────────────────────────────────

@router.get("/presets", summary="Available duration presets for Adaptive Runtime Engine")
def get_presets():
    """Returns all available duration presets with their ranges."""
    return {
        "presets": {
            name: {"min_seconds": lo, "max_seconds": hi, "target_seconds": (lo + hi) // 2}
            for name, (lo, hi) in DURATION_PRESETS.items()
        },
        "default": "shorts",
    }


@router.get("/voices", summary="Available TTS voices")
def get_voices():
    """Returns all registered voice IDs with their provider."""
    return {
        "voices": [
            {"id": key, "internal_id": val, "provider": "kokoro"}
            for key, val in VOICE_REGISTRY.items()
        ],
        "default": "female_warm",
    }


# ─── 1. Hybrid Pipeline (primary product) ─────────────────────────────────────

@router.post("/hybrid", summary="Full hybrid pipeline — Adaptive Runtime Engine")
async def generate_hybrid(req: HybridVideoRequest, background_tasks: BackgroundTasks):
    """
    Primary video generation endpoint with Adaptive Runtime Engine.

    Duration is driven by preset or custom_duration — the pipeline automatically
    adapts to the actual narration length.

    Presets: shorts (20-40s) | short (40-90s) | medium (2-4min) | long (6-10min) | documentary (10-20min)

    Returns a job_id. Poll /generate/jobs/{job_id} for status.
    """
    _gate(req.user_email)
    job_id = _new_job("hybrid")
    background_tasks.add_task(run_hybrid_pipeline, job_id, req)
    return {
        "job_id": job_id,
        "status": "queued",
        "type": "hybrid",
        "target_duration": req.resolved_duration,
        "preset": req.preset,
    }


# ─── 1b. YouTube Studio Production Pipeline ──────────────────────────────────

@router.post("/youtube-studio", summary="Topic → documentary-grade YouTube production package")
async def generate_youtube_studio(req: YouTubeStudioRequest, background_tasks: BackgroundTasks):
    """
    AI-first faceless YouTube studio.

    The user supplies a topic. The pipeline produces editable, structured
    artifacts for all production stages: topic intelligence, research, story,
    script QA/revision, visual planning, real asset collection, image prompts,
    voice direction, audio QA, edit plan, thumbnails, titles, SEO, and final QA.
    """
    _gate(req.user_email)
    job_id = _new_job("youtube_studio")
    background_tasks.add_task(run_youtube_studio_production, job_id, req)
    return {
        "job_id": job_id,
        "status": "queued",
        "type": "youtube_studio",
        "target_duration": req.resolved_duration,
        "aspect_ratio": req.aspect_ratio,
    }


# ─── 2. TikTok Clips (legacy / backward-compatible) ──────────────────────────

@router.post("/tiktok", summary="Prompt → TikTok-style video (legacy)")
async def generate_tiktok(req: TikTokRequest, background_tasks: BackgroundTasks):
    """
    Original TikTok pipeline (backward-compatible).
    For new integrations, prefer /generate/hybrid with preset='shorts'.
    """
    _gate(req.user_email)
    job_id = _new_job("tiktok")
    background_tasks.add_task(run_tiktok_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued", "type": "tiktok"}


# ─── 3. Still Image → Motion ──────────────────────────────────────────────────

@router.post("/still-to-motion", summary="Upload image → animated Ken Burns video")
async def generate_still_to_motion(
    background_tasks: BackgroundTasks,
    user_email: str     = Form(...),
    hook: str           = Form(...),
    cta: str            = Form(...),
    narration: str      = Form(...),
    effect: Optional[str] = Form(None),
    image: UploadFile   = File(...),
):
    """
    Animates a single uploaded image:
    Ken Burns effect + TTS voiceover + text overlays → MP4.

    effect options: zoom_in | zoom_out | pan_right | pan_left | tilt_up | tilt_down | static
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(400, f"Expected an image file, got: {image.content_type}")

    req = StillToMotionRequest(
        user_email=user_email, hook=hook, cta=cta, narration=narration, effect=effect,
    )
    _gate(req.user_email)
    job_id = _new_job("still_to_motion")

    suffix = Path(image.filename).suffix or ".jpg"
    image_path = OUTPUT_DIR / f"{job_id}_upload{suffix}"
    with image_path.open("wb") as f:
        shutil.copyfileobj(image.file, f)

    background_tasks.add_task(run_still_to_motion_pipeline, job_id, req, image_path)
    return {"job_id": job_id, "status": "queued", "type": "still_to_motion"}


# ─── 4. AI Video (Layer C primary) ────────────────────────────────────────────

@router.post("/ai-video", summary="True AI video generation (CogVideoX-5B → Wan2.1 → Ken Burns fallback)")
async def generate_ai_video(req: AIVideoRequest, background_tasks: BackgroundTasks):
    """
    Attempts to generate AI video using CogVideoX-5B → Wan2.1 → Ken Burns fallback.
    Always completes even if AI models are unavailable (Ken Burns guaranteed).
    """
    _gate(req.user_email)
    job_id = _new_job("ai_video")
    background_tasks.add_task(run_ai_video_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued", "type": "ai_video"}


# ─── 5a. Motion Design — from topic (JSON) ────────────────────────────────────

@router.post("/motion-design", summary="Topic → Remotion motion design video")
async def generate_motion_design(req: MotionDesignRequest, background_tasks: BackgroundTasks):
    """
    Generates a motion design video from a text topic.

    Styles: minimal | bold | glassmorphism | neon
    Aspect ratios: 9:16 (TikTok/Reels) | 16:9 (YouTube) | 1:1 (Square)
    """
    _gate(req.user_email)
    job_id = _new_job("motion_design")
    background_tasks.add_task(run_motion_design_pipeline, job_id, req, None)
    return {"job_id": job_id, "status": "queued", "type": "motion_design"}


# ─── 5b. Motion Design — from flyer image (multipart) ─────────────────────────

@router.post("/motion-design/flyer", summary="Flyer image → Remotion motion design video")
async def generate_motion_design_from_flyer(
    background_tasks: BackgroundTasks,
    user_email: str          = Form(...),
    style: str               = Form("auto"),
    aspect_ratio: str        = Form("9:16"),
    duration: int            = Form(15),
    brand_name: Optional[str] = Form(None),
    brand_color: Optional[str] = Form(None),
    flyer: UploadFile        = File(...),
):
    """
    Animates a graphic design flyer into a motion design video.
    Gemini reads the flyer and maps it into the best-fit Remotion template.
    """
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if flyer.content_type not in allowed_types:
        raise HTTPException(400, f"Expected JPEG/PNG/WebP, got: {flyer.content_type}")

    job_id = _new_job("motion_design_flyer")
    suffix = Path(flyer.filename).suffix or ".jpg"
    flyer_path = OUTPUT_DIR / f"{job_id}_flyer{suffix}"

    with flyer_path.open("wb") as f:
        shutil.copyfileobj(flyer.file, f)

    if flyer_path.stat().st_size < 3000:
        flyer_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded flyer is too small or corrupt.")

    _gate(user_email)

    req = MotionDesignRequest(
        user_email=user_email,
        topic="Motion design from uploaded flyer",
        style=style if style != "auto" else "minimal",
        duration=duration,
        brand_name=brand_name,
        brand_color=brand_color,
        aspect_ratio=aspect_ratio,
    )

    background_tasks.add_task(run_motion_design_pipeline, job_id, req, flyer_path)
    return {
        "job_id": job_id,
        "status": "queued",
        "type": "motion_design_flyer",
        "flyer_saved": flyer_path.name,
    }


# ─── Avatar styles ────────────────────────────────────────────────────────────

@router.get("/avatar/styles", summary="Available avatar styles")
def avatar_styles():
    """Returns available avatar styles for the frontend selector."""
    from services.avatar import get_available_styles
    return {"styles": get_available_styles()}


# ─── 6. Avatar (FREE) ─────────────────────────────────────────────────────────

@router.post("/avatar", summary="AI-generated face talking head (FREE tier)")
async def generate_avatar(req: AvatarVideoRequest, background_tasks: BackgroundTasks):
    """
    FREE tier: AI-generated face avatar.
    Send JSON body. face_image_path should be null / omitted.
    """
    if DEV_MODE:
        if store.get_credits(req.user_email) == 0:
            store.set_credits(req.user_email, DEV_FREE_CREDITS)
    store.deduct_credit(req.user_email)

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, video_type="avatar_free")

    background_tasks.add_task(run_avatar_pipeline, job_id, req, None)
    return {"job_id": job_id, "status": "queued", "tier": "free"}


# ─── 7. Avatar (PREMIUM) ──────────────────────────────────────────────────────

@router.post("/avatar/premium", summary="User-uploaded face talking head (PREMIUM — 2 credits)")
async def generate_avatar_premium(
    background_tasks: BackgroundTasks,
    user_email: str          = Form(...),
    topic: str               = Form(...),
    tone: str                = Form("educational"),
    duration: int            = Form(30),
    brand_name: Optional[str] = Form(None),
    avatar_style: str        = Form("friend"),
    health_awareness: bool   = Form(False),
    face_image: UploadFile   = File(...),
):
    """
    PREMIUM tier: user uploads their own face photo.
    Costs 2 credits. Returns lip-synced talking-head video.
    """
    PREMIUM_CREDIT_COST = 2

    if DEV_MODE:
        if store.get_credits(user_email) == 0:
            store.set_credits(user_email, DEV_FREE_CREDITS)

    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if face_image.content_type not in allowed:
        raise HTTPException(400, "Please upload a JPEG, PNG, or WebP image.")

    job_id = str(uuid.uuid4())
    face_path = OUTPUT_DIR / f"{job_id}_upload{Path(face_image.filename).suffix}"

    with face_path.open("wb") as f:
        shutil.copyfileobj(face_image.file, f)

    if face_path.stat().st_size < 5000:
        face_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded file is too small or corrupt.")

    for _ in range(PREMIUM_CREDIT_COST):
        store.deduct_credit(user_email)

    store.create_job(job_id)
    store.update_job(job_id, video_type="avatar_premium")

    req = AvatarVideoRequest(
        user_email=user_email,
        topic=topic, tone=tone, duration=duration,
        brand_name=brand_name, avatar_style=avatar_style,
        health_awareness=health_awareness,
        face_image_path=str(face_path),
    )

    background_tasks.add_task(run_avatar_pipeline, job_id, req, face_path)
    return {
        "job_id": job_id,
        "status": "queued",
        "tier": "premium",
        "credits_charged": PREMIUM_CREDIT_COST,
    }


# ─── Trends ───────────────────────────────────────────────────────────────────

@router.get("/trends/dashboard", summary="Fetch YouTube trends dashboard view")
def get_trends_dashboard(niche: str = "general"):
    """Returns organised dashboard view: top_today, trending_this_week, evergreen, recently_covered."""
    scheduler = TrendScheduler()
    return scheduler.get_dashboard_view(niche=niche)


@router.post("/trends/scan", summary="Trigger real-time trend discovery sweep")
async def trigger_trend_scan(niche: str = "general", frequency: str = "daily"):
    """Triggers immediate trend discovery, clustering, LLM enrichment, and scoring."""
    scheduler = TrendScheduler()
    try:
        freq_enum = ScanFrequency(frequency)
    except ValueError:
        freq_enum = ScanFrequency.DAILY

    batch = await scheduler.run_discovery_cycle(niche=niche, frequency=freq_enum)
    return {
        "batch_id": batch.batch_id,
        "niche": batch.niche,
        "frequency": batch.frequency.value,
        "started_at": batch.started_at,
        "completed_at": batch.completed_at,
        "candidates_found": batch.candidates_found,
        "opportunities_generated": len(batch.opportunities),
        "errors": batch.errors,
    }


@router.post("/trends/hybrid", summary="Generate video based on high-interest trend niche")
async def generate_trend_hybrid(req: TrendPipelineRequest, background_tasks: BackgroundTasks):
    """Submits a trend-augmented hybrid video generation request."""
    _gate(req.user_email)
    job_id = _new_job("trend_hybrid")

    hybrid_req = HybridVideoRequest(
        user_email=req.user_email,
        tone=req.tone,
        preset=req.preset,
        use_ai_motion=req.use_ai_motion,
        subtitles=req.subtitles,
    )

    background_tasks.add_task(run_trend_pipeline, job_id, req.niche, hybrid_req)
    return {"job_id": job_id, "status": "queued", "type": "trend_hybrid"}


# ─── 8. Batch Generation ──────────────────────────────────────────────────────

@router.post("/batch", summary="Batch multi-video generation")
async def generate_batch(req: BatchGenerationRequest, background_tasks: BackgroundTasks):
    """
    Generate multiple videos in a single request.

    Supports:
    - Automatic topic discovery from a niche (using trend engine + AI fallback)
    - Explicit topic lists

    Each video runs as an independent job and can be polled individually.
    Poll the batch status at /generate/batch/{batch_id} for aggregate progress.

    Credits: 1 credit charged per successful video.
    """
    # Verify user has enough credits for at least 1 video
    if DEV_MODE:
        if store.get_credits(req.user_email) == 0:
            store.set_credits(req.user_email, DEV_FREE_CREDITS)
    elif store.get_credits(req.user_email) < 1:
        raise HTTPException(402, "Insufficient credits. Please top up.")

    batch_id = str(uuid.uuid4())
    topic_count = len(req.topics) if req.topics else req.count
    create_batch(batch_id, topic_count)

    background_tasks.add_task(run_batch_pipeline, batch_id, req)

    return {
        "batch_id": batch_id,
        "status": "queued",
        "type": "batch",
        "count": topic_count,
        "preset": req.preset,
        "niche": req.niche,
    }


@router.get("/batch/{batch_id}", summary="Get batch generation status")
def get_batch_status(batch_id: str):
    """
    Returns the current status of a batch generation job.

    status: queued | discovering_topics | generating | done | partial | failed
    progress: 0–100 (percentage of videos completed)
    """
    batch = store.get_job(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


# ─── Job status ───────────────────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatus,
    summary="Poll job status + progress",
)
def get_job(job_id: str):
    """
    Returns the current status of a video generation job.

    Status flow:
      queued → researching → generating_script → generating_audio →
      acquiring_media → generating_ai_motion? → rendering → done | failed

    progress: 0–100 integer percentage.
    status_detail: human-readable description of current step.
    estimated_remaining: seconds remaining (rough estimate).
    warnings: list of non-fatal issues encountered.
    """
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatus(job_id=job_id, **job)
