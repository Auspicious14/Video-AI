from typing import Optional, Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
#  Video type models
#  Each video product maps to one Request model + one pipeline function.
#
#  ┌──────────────────────────────┬──────────────────────────────────────────┐
#  │ Type                         │ Status   │ Description                    │
#  ├──────────────────────────────┼──────────────────────────────────────────┤
#  │ tiktok          (live)       │ ✅ Live  │ Prompt → script → images → MP4 │
#  │ still_to_motion (live)       │ ✅ Live  │ Image upload → Ken Burns → MP4 │
#  │ hybrid          (live)       │ ✅ Live  │ Full hybrid pipeline (primary)  │
#  │ ai_video        (live)       │ ✅ Live  │ Multi-layer AI video (Layer C)  │
#  │ motion_design   (planned)    │ 📅 Soon  │ Remotion programmatic anim.     │
#  └──────────────────────────────┴──────────────────────────────────────────┘
# ─────────────────────────────────────────────────────────────────────────────


# ── 1. TikTok Clips (backward compatible) ────────────────────────────────────
class TikTokRequest(BaseModel):
    user_email: str
    topic: str
    tone: str = "educational"       # educational | urgent | inspiring | conversational
    duration: int = 30              # 15 | 30 | 60
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"


# ── 2. Still Image → Motion ───────────────────────────────────────────────────
class StillToMotionRequest(BaseModel):
    user_email: str
    hook: str                       # short text overlay at top
    cta: str                        # call-to-action text at bottom
    narration: str                  # voiceover script (will be TTS'd)
    effect: Optional[Literal[
        "zoom_in", "zoom_out",
        "pan_right", "pan_left",
        "tilt_up", "tilt_down",
        "static",
    ]] = None                       # None = default (zoom_in) — deterministic


# ── 3. Hybrid Video (primary product) ────────────────────────────────────────
class HybridVideoRequest(BaseModel):
    """
    Unified input for the full Hybrid Video Pipeline.

    Accepts either a topic (LLM writes the script) or directly a prompt.
    Layers A + B always run.  Layer C (AI motion) is optional and selective.
    """
    user_email: str
    topic: Optional[str] = None         # LLM will write script from this
    prompt: Optional[str] = None        # alias for topic; used if topic is empty
    tone: str = "educational"
    duration: int = 30                  # 15 | 30 | 60
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # Layer C controls
    use_ai_motion: bool = False         # set True to attempt AI video clips
    ai_motion_timeout: float = 90.0    # seconds per scene before giving up

    # Output controls
    subtitles: bool = True              # burn in word-by-word subtitle cards
    aspect_ratio: str = "9:16"         # 9:16 (TikTok) | 16:9 | 1:1

    @property
    def resolved_topic(self) -> str:
        return self.topic or self.prompt or "Untitled"


# ── 4. AI Video (Layer C primary) ────────────────────────────────────────────
class AIVideoRequest(BaseModel):
    """
    True AI video generation pipeline.
    Uses CogVideoX-5B → Wan2.1 → Ken Burns fallback per scene.
    """
    user_email: str
    prompt: str                     # natural language video description
    aspect_ratio: str = "9:16"
    duration: int = 15              # 5–60 seconds
    style: Optional[str] = None     # cinematic | documentary | animation

    # Optional overrides
    hook: Optional[str] = None      # text displayed at top for first 3s
    cta: Optional[str] = None       # call-to-action at bottom for last 5s
    narration: Optional[str] = None # if None, auto-generated from prompt
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"


"""
PATCH for models.py — replace the existing MotionDesignRequest class with this.
Adds aspect_ratio field so the pipeline and router can control output dimensions.
"""

# ── 5. Motion Design (Remotion) ───────────────────────────────────────────────
class MotionDesignRequest(BaseModel):
    user_email: str
    topic: str
    style: str = "minimal"          # minimal | bold | glassmorphism | neon | auto
    duration: int = 15              # 10–30 seconds
    brand_name: Optional[str] = None
    brand_color: Optional[str] = None    # hex e.g. "#FF6B35"
    aspect_ratio: str = "9:16"          # 9:16 | 16:9 | 1:1

# ── Shared ────────────────────────────────────────────────────────────────────
class PaystackInitRequest(BaseModel):
    email: str
    plan: str                       # starter | pro | business


class JobStatus(BaseModel):
    job_id: str
    status: str                     # queued | generating_script | generating_audio
                                    # generating_images | generating_ai_motion
                                    # rendering | done | failed
    video_type: Optional[str] = None
    video_url: Optional[str] = None
    caption: Optional[str] = None
    cta: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[int] = None  # 0–100 percentage
    status_detail: Optional[str] = None  # human-readable step description

"""
ADD THIS TO services/models.py
═══════════════════════════════════════════════════════════════════════════════
Paste after the AIVideoRequest class.
"""

from typing import Literal  # already imported in your models.py


# ── 6. Avatar Video ───────────────────────────────────────────────────────────
class AvatarVideoRequest(BaseModel):
    """
    Talking head avatar video.

    FREE tier    — face_image_path is None, avatar_style picks AI-generated face
    PREMIUM tier — face_image_path is set (user uploaded their own photo)
    """
    user_email: str
    topic: str
    tone: str = "educational"
    duration: int = 30
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    # FREE: choose an AI-generated face style
    avatar_style: Literal["doctor", "presenter", "friend"] = "doctor"

    # PREMIUM: path to uploaded image (set by the router after saving the upload)
    # Frontend sends multipart/form-data; router saves the file and sets this.
    face_image_path: Optional[str] = None      # absolute path string on server