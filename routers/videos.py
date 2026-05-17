"""
routers/videos.py  —  Video generation endpoints
"""

import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from typing import Optional

from models import (
    TikTokRequest,
    StillToMotionRequest,
    HybridVideoRequest,
    MotionDesignRequest,
    AIVideoRequest,
    JobStatus,
    AvatarVideoRequest,
    
)
from services.pipeline import run_tiktok_pipeline
from services.pipeline_still import run_still_to_motion_pipeline
from services.pipeline_hybrid import run_hybrid_pipeline
from services.pipeline_motion_design import run_motion_design_pipeline
from services.pipeline_ai_video import run_ai_video_pipeline
from services.pipeline_avatar import run_avatar_pipeline
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


# ─── 1. Hybrid Pipeline (primary product) ─────────────────────────────────────

@router.post("/hybrid", summary="Full hybrid pipeline — AI assets + deterministic composition")
async def generate_hybrid(req: HybridVideoRequest, background_tasks: BackgroundTasks):
    """
    Primary video generation endpoint.

    Pipeline:
      Layer B: Gemini script → gTTS audio → FLUX.1-schnell images
      Layer A: FFmpeg deterministic composition (Ken Burns, transitions, overlays)
      Layer C: Optional HuggingFace AI video clips (if use_ai_motion=true)

    Returns a job_id immediately. Poll /generate/jobs/{job_id} for status + progress.

    Request body:
      topic: str          — the video subject (LLM writes script)
      tone: str           — educational | urgent | inspiring | conversational
      duration: int       — 15 | 30 | 60
      use_ai_motion: bool — set true to attempt AI video clips per scene (slower)
      subtitles: bool     — burn word-by-word subtitle cards into video
    """
    _gate(req.user_email)
    job_id = _new_job("hybrid")
    background_tasks.add_task(run_hybrid_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued", "type": "hybrid"}


# ─── 2. TikTok Clips (legacy / backward-compatible) ──────────────────────────

@router.post("/tiktok", summary="Prompt → TikTok-style video clip")
async def generate_tiktok(req: TikTokRequest, background_tasks: BackgroundTasks):
    """
    Original TikTok pipeline (backward-compatible).
    Gemini script → gTTS audio → FLUX.1-schnell images → FFmpeg render.
    For new integrations, prefer /generate/hybrid.
    """
    _gate(req.user_email)
    job_id = _new_job("tiktok")
    background_tasks.add_task(run_tiktok_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued", "type": "tiktok"}


# ─── 3. Still Image → Motion ──────────────────────────────────────────────────

@router.post("/still-to-motion", summary="Upload image → animated Ken Burns video")
async def generate_still_to_motion(
    background_tasks: BackgroundTasks,
    user_email: str = Form(...),
    hook: str = Form(...),
    cta: str = Form(...),
    narration: str = Form(...),
    effect: Optional[str] = Form(None),
    image: UploadFile = File(...),
):
    """
    Animates a single uploaded image:
    Ken Burns effect + TTS voiceover + text overlays → MP4.

    effect options: zoom_in | zoom_out | pan_right | pan_left | tilt_up | tilt_down | static
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(400, f"Expected an image file, got: {image.content_type}")

    req = StillToMotionRequest(
        user_email=user_email,
        hook=hook,
        cta=cta,
        narration=narration,
        effect=effect,
    )

    _gate(req.user_email)
    job_id = _new_job("still_to_motion")

    suffix     = Path(image.filename).suffix or ".jpg"
    image_path = OUTPUT_DIR / f"{job_id}_upload{suffix}"
    with image_path.open("wb") as f:
        shutil.copyfileobj(image.file, f)

    background_tasks.add_task(run_still_to_motion_pipeline, job_id, req, image_path)
    return {"job_id": job_id, "status": "queued", "type": "still_to_motion"}


# ─── 4. AI Video (Layer C primary) ────────────────────────────────────────────

@router.post("/ai-video", summary="True AI video generation (CogVideoX-5B → Wan2.1 → Ken Burns fallback)")
async def generate_ai_video(req: AIVideoRequest, background_tasks: BackgroundTasks):
    """
    Attempts to generate true AI video using:
      1. CogVideoX-5B (HuggingFace — best free quality)
      2. Wan2.1-T2V-14B (HuggingFace — faster)
      3. Deterministic Ken Burns fallback (Layer A — always succeeds)

    Note: HuggingFace free tier has queue delays (30–120s per clip).
    The pipeline always completes, even if AI models are unavailable.
    """
    _gate(req.user_email)
    job_id = _new_job("ai_video")
    background_tasks.add_task(run_ai_video_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued", "type": "ai_video"}


# ─── 5. Motion Design (Remotion) ──────────────────────────────────────────────

"""
REPLACE the existing motion-design route in routers/videos.py with this.

Also add to the top-level imports in videos.py:
  from services.pipeline_motion_design import run_motion_design_pipeline

The route now handles two flows:
  POST /generate/motion-design         — JSON body (topic → motion design)
  POST /generate/motion-design/flyer   — multipart (flyer image → motion design)
"""

# ─── 5a. Motion Design — from topic (JSON) ────────────────────────────────────

@router.post("/motion-design", summary="Topic → Remotion motion design video")
async def generate_motion_design(req: MotionDesignRequest, background_tasks: BackgroundTasks):
    """
    Generates a motion design video from a text topic.

    Gemini writes a structured design brief (colors, layout, copy, style),
    then Remotion renders it into a polished animated MP4.

    Styles:
      minimal       — quote cards, elegant announcements, flyer conversions
      bold          — brand intros, product launches, big statements
      glassmorphism — stats / data reveals (counts up live numbers)
      neon          — listicles, tip lists, how-to content

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

    Gemini reads the flyer (headline, colors, copy, visual style) and maps
    it into the best-fit Remotion template. The output is a fully animated
    version of the flyer, ready to post as a Reel, TikTok, or YouTube Short.

    style: auto | minimal | bold | glassmorphism | neon
      (auto = Gemini decides based on the flyer's visual language)
    """
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if flyer.content_type not in allowed_types:
        raise HTTPException(400, f"Expected JPEG/PNG/WebP, got: {flyer.content_type}")

    # Save flyer temporarily
    job_id      = _new_job("motion_design_flyer")
    suffix      = Path(flyer.filename).suffix or ".jpg"
    flyer_path  = OUTPUT_DIR / f"{job_id}_flyer{suffix}"

    with flyer_path.open("wb") as f:
        shutil.copyfileobj(flyer.file, f)

    if flyer_path.stat().st_size < 3000:
        flyer_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded flyer is too small or corrupt.")

    _gate(user_email)

    req = MotionDesignRequest(
        user_email=user_email,
        topic=f"Motion design from uploaded flyer",  # placeholder; Gemini reads the image
        style=style if style != "auto" else "minimal",  # brief generator will override
        duration=duration,
        brand_name=brand_name,
        brand_color=brand_color,
        aspect_ratio=aspect_ratio,
    )

    background_tasks.add_task(run_motion_design_pipeline, job_id, req, flyer_path)
    return {
        "job_id":      job_id,
        "status":      "queued",
        "type":        "motion_design_flyer",
        "flyer_saved": flyer_path.name,
    }

# ─── Job status ───────────────────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatus,
    summary="Poll job status + progress",
)
def get_job(job_id: str):
    """
    Returns the current status of a video generation job.

    Status values:
      queued → generating_script → generating_audio → generating_images
      → generating_ai_motion (if use_ai_motion=true) → rendering → done | failed

    progress: 0–100 integer percentage.
    status_detail: human-readable description of the current step.
    """
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatus(job_id=job_id, **job)


import shutil
from fastapi import File, UploadFile, Form


# ── GET /generate/avatar/styles ───────────────────────────────────────────────
@router.get("/avatar/styles")
def avatar_styles():
    """Returns available avatar styles for the frontend selector."""
    from services.avatar import get_available_styles
    return {"styles": get_available_styles()}


# ── POST /generate/avatar (FREE — AI-generated face) ─────────────────────────
@router.post("/avatar")
async def generate_avatar(
    req: AvatarVideoRequest,
    background_tasks: BackgroundTasks,
):
    """
    FREE tier: AI-generated face avatar.
    Send JSON body exactly like /generate/tiktok.
    face_image_path should be null / omitted.
    """
    # ── DEV MODE credit gate ──────────────────────────────────────────────────
    if DEV_MODE:
        if store.get_credits(req.user_email) == 0:
            store.set_credits(req.user_email, DEV_FREE_CREDITS)
    # ── PRODUCTION ────────────────────────────────────────────────────────────
    # if store.get_credits(req.user_email) < 1:
    #     raise HTTPException(402, "Insufficient credits. Please top up.")
    # ─────────────────────────────────────────────────────────────────────────

    store.deduct_credit(req.user_email)

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, video_type="avatar_free")

    background_tasks.add_task(
        run_avatar_pipeline,
        job_id,
        req,
        None,           # face_image_path = None → AI-generated face
    )
    return {"job_id": job_id, "status": "queued", "tier": "free"}


# ── POST /generate/avatar/premium (PREMIUM — user uploads own photo) ──────────
@router.post("/avatar/premium")
async def generate_avatar_premium(
    background_tasks: BackgroundTasks,
    # Form fields (multipart/form-data)
    user_email: str         = Form(...),
    topic: str              = Form(...),
    tone: str               = Form("educational"),
    duration: int           = Form(30),
    brand_name: Optional[str] = Form(None),
    avatar_style: str       = Form("friend"),   # style hint even with own photo
    # File upload
    face_image: UploadFile  = File(...),
):
    """
    PREMIUM tier: user uploads their own face photo.
    Costs 2 credits (charged as 2 deductions).
    """
    PREMIUM_CREDIT_COST = 2

    # ── DEV MODE credit gate ──────────────────────────────────────────────────
    if DEV_MODE:
        if store.get_credits(user_email) == 0:
            store.set_credits(user_email, DEV_FREE_CREDITS)
    # ── PRODUCTION ────────────────────────────────────────────────────────────
    # if store.get_credits(user_email) < PREMIUM_CREDIT_COST:
    #     raise HTTPException(402, f"Premium avatar requires {PREMIUM_CREDIT_COST} credits.")
    # ─────────────────────────────────────────────────────────────────────────

    # Validate file type
    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if face_image.content_type not in allowed:
        raise HTTPException(400, "Please upload a JPEG, PNG, or WebP image.")

    # Save uploaded image
    from config import OUTPUT_DIR
    job_id    = str(uuid.uuid4())
    face_path = OUTPUT_DIR / f"{job_id}_upload{Path(face_image.filename).suffix}"

    with face_path.open("wb") as f:
        shutil.copyfileobj(face_image.file, f)

    if face_path.stat().st_size < 5000:
        face_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded file is too small or corrupt.")

    # Deduct premium credits
    for _ in range(PREMIUM_CREDIT_COST):
        store.deduct_credit(user_email)

    store.create_job(job_id)
    store.update_job(job_id, video_type="avatar_premium")

    req = AvatarVideoRequest(
        user_email=user_email,
        topic=topic,
        tone=tone,
        duration=duration,
        brand_name=brand_name,
        avatar_style=avatar_style,
        face_image_path=str(face_path),
    )

    background_tasks.add_task(
        run_avatar_pipeline,
        job_id,
        req,
        face_path,      # face_image_path set → premium flow
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "tier": "premium",
        "credits_charged": PREMIUM_CREDIT_COST,
    }