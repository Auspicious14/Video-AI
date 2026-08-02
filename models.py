"""
models.py — VideoAI Request/Response Models
═══════════════════════════════════════════════════════════════════════════════

Video product map:
  hybrid        ✅ Primary — full pipeline (research + script + audio + images + render)
  tiktok        ✅ Legacy  — backward-compatible original pipeline
  ai_video      ✅ Live    — Layer C primary (CogVideoX / Wan2.1)
  still_motion  ✅ Live    — single image → Ken Burns animation
  motion_design ✅ Live    — Remotion programmatic animation
  avatar        ✅ Live    — talking-head avatar (SadTalker)
  trend_hybrid  ✅ Live    — trend-augmented hybrid pipeline
  batch         ✅ New     — multi-video batch generation

Duration presets (Adaptive Runtime Engine — Part 3)
────────────────────────────────────────────────────
  shorts    20–40 s   — YouTube Shorts / TikTok / Instagram Reels
  short     40–90 s   — Punchy how-to / explainer
  medium    2–4 min   — In-depth explainer / tutorial
  long      6–10 min  — YouTube long-form
  documentary 10–20 min — Deep-dive / documentary
"""

from typing import Optional, Literal, List
from pydantic import BaseModel, Field, model_validator


# ── Duration presets ──────────────────────────────────────────────────────────

DURATION_PRESETS: dict[str, tuple[int, int]] = {
    "shorts":       (20,  40),
    "short":        (40,  90),
    "medium":       (120, 240),
    "long":         (360, 600),
    "documentary":  (600, 1200),
}

DurationPreset = Literal["shorts", "short", "medium", "long", "documentary"]


def resolve_duration(
    preset: Optional[DurationPreset] = None,
    custom_duration: Optional[int] = None,
    default: int = 30,
) -> int:
    """
    Resolve a duration preset or custom duration to a target integer (seconds).

    Preset → midpoint of the allowed range.
    Custom duration overrides preset.
    Neither → default.
    """
    if custom_duration and custom_duration > 0:
        return custom_duration
    if preset and preset in DURATION_PRESETS:
        lo, hi = DURATION_PRESETS[preset]
        return (lo + hi) // 2
    return default


def scene_count_for_duration(duration_seconds: int) -> int:
    """
    Return a sensible scene count for a given duration.

    Rule: ~1 scene per 5 seconds for short-form, ~1 per 8 seconds for long-form.
    """
    if duration_seconds <= 60:
        return max(3, duration_seconds // 5)
    elif duration_seconds <= 300:
        return max(6, duration_seconds // 6)
    else:
        return max(10, duration_seconds // 8)


# ── 1. TikTok Clips (backward compatible) ─────────────────────────────────────

class TikTokRequest(BaseModel):
    user_email: str
    topic: str
    tone: str = "educational"
    duration: int = 30
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    health_awareness: bool = False


# ── 2. Still Image → Motion ───────────────────────────────────────────────────

class StillToMotionRequest(BaseModel):
    user_email: str
    hook: str
    cta: str
    narration: str
    effect: Optional[Literal[
        "zoom_in", "zoom_out",
        "pan_right", "pan_left",
        "tilt_up", "tilt_down",
        "static",
    ]] = None


# ── 3. Hybrid Video (primary product) ─────────────────────────────────────────

class HybridVideoRequest(BaseModel):
    """
    Unified input for the full Hybrid Video Pipeline.

    Duration resolution order:
      1. custom_duration (explicit override)
      2. preset (Shorts / Short / Medium / Long / Documentary)
      3. duration (legacy field — kept for backward compatibility)
      4. 30 seconds (default)
    """

    user_email: str
    topic: Optional[str] = None
    prompt: Optional[str] = None           # alias for topic
    tone: str = "educational"
    duration: int = 30                     # legacy — prefer preset
    preset: Optional[DurationPreset] = None
    custom_duration: Optional[int] = None  # explicit override
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    health_awareness: bool = False
    ai_provider: Optional[str] = None     # 'groq' | 'gemini' | None (auto)

    # Layer C controls
    use_ai_motion: bool = False
    ai_motion_timeout: float = 90.0

    # Output controls
    subtitles: bool = True
    aspect_ratio: str = "9:16"

    @property
    def resolved_topic(self) -> str:
        return self.topic or self.prompt or "Untitled"

    @property
    def resolved_duration(self) -> int:
        """Returns the effective target duration in seconds."""
        return resolve_duration(self.preset, self.custom_duration, self.duration)


# ── 3b. YouTube Studio Documentary Production ────────────────────────────────

class YouTubeStudioRequest(BaseModel):
    """
    AI-first faceless YouTube production request.

    A topic is enough. The studio pipeline produces editable artifacts for
    topic intelligence, research, story, script, visual planning, assets,
    voice direction, packaging, SEO, and final QA.
    """

    user_email: str
    topic: str
    tone: str = "documentary"
    duration: int = 720
    preset: Optional[DurationPreset] = None
    custom_duration: Optional[int] = None
    audience_profile: str = ""
    monetization_goal: str = "long-term YouTube revenue"
    voice_id: str = "female_warm"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    generate_audio: bool = True
    generate_images: bool = False
    render_video: bool = False

    @property
    def resolved_duration(self) -> int:
        return resolve_duration(self.preset, self.custom_duration, self.duration)


# ── 4. AI Video (Layer C primary) ─────────────────────────────────────────────

class AIVideoRequest(BaseModel):
    """True AI video generation pipeline (CogVideoX-5B → Wan2.1 → Ken Burns fallback)."""

    user_email: str
    prompt: str
    aspect_ratio: str = "9:16"
    duration: int = 15
    preset: Optional[DurationPreset] = None
    custom_duration: Optional[int] = None
    style: Optional[str] = None

    hook: Optional[str] = None
    cta: Optional[str] = None
    narration: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    @property
    def resolved_duration(self) -> int:
        return resolve_duration(self.preset, self.custom_duration, self.duration)


# ── 5. Motion Design (Remotion) ───────────────────────────────────────────────

class MotionDesignRequest(BaseModel):
    user_email: str
    topic: str
    style: str = "minimal"
    duration: int = 15
    preset: Optional[DurationPreset] = None
    custom_duration: Optional[int] = None
    brand_name: Optional[str] = None
    brand_color: Optional[str] = None
    aspect_ratio: str = "9:16"

    @property
    def resolved_duration(self) -> int:
        return resolve_duration(self.preset, self.custom_duration, self.duration)


# ── 6. Avatar Video ───────────────────────────────────────────────────────────

class AvatarVideoRequest(BaseModel):
    """
    Talking-head avatar video.

    FREE tier    — face_image_path is None, avatar_style picks AI-generated face.
    PREMIUM tier — face_image_path is set (user uploaded their own photo).
    """

    user_email: str
    topic: str
    tone: str = "educational"
    duration: int = 30
    preset: Optional[DurationPreset] = None
    custom_duration: Optional[int] = None
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    health_awareness: bool = False
    avatar_style: Literal["doctor", "presenter", "friend"] = "doctor"
    face_image_path: Optional[str] = None

    @property
    def resolved_duration(self) -> int:
        return resolve_duration(self.preset, self.custom_duration, self.duration)


# ── 7. Trend Pipeline ─────────────────────────────────────────────────────────

class TrendPipelineRequest(BaseModel):
    user_email: str
    niche: str = "general"
    tone: str = "educational"
    use_ai_motion: bool = False
    subtitles: bool = True
    preset: Optional[DurationPreset] = "shorts"


# ── 8. Batch Content Generation ───────────────────────────────────────────────

class BatchVideoItem(BaseModel):
    """A single item in a batch generation request."""
    topic: str
    tone: str = "educational"
    preset: Optional[DurationPreset] = "shorts"
    custom_duration: Optional[int] = None
    brand_name: Optional[str] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"


class BatchGenerationRequest(BaseModel):
    """
    Batch video generation request.

    Generates multiple videos in sequence, tracking progress per video.
    Supports topic discovery (niche mode) or explicit topic lists.
    """

    user_email: str
    niche: Optional[str] = None              # auto-discover topics from this niche
    topics: Optional[List[str]] = None      # explicit topic list (overrides niche discovery)
    count: int = Field(default=5, ge=1, le=50, description="Number of videos to generate")
    tone: str = "educational"
    preset: DurationPreset = "shorts"
    custom_duration: Optional[int] = None
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    brand_name: Optional[str] = None
    use_ai_motion: bool = False
    subtitles: bool = True
    health_awareness: bool = False
    aspect_ratio: str = "9:16"
    ai_provider: Optional[str] = None

    @model_validator(mode="after")
    def validate_topics_or_niche(self) -> "BatchGenerationRequest":
        if not self.niche and not self.topics:
            raise ValueError("Either 'niche' (for auto-discovery) or 'topics' (explicit list) is required")
        if self.topics and len(self.topics) > 50:
            raise ValueError("Maximum 50 explicit topics per batch")
        return self

    @property
    def resolved_duration(self) -> int:
        return resolve_duration(self.preset, self.custom_duration, 30)


class BatchJobItem(BaseModel):
    """Status of a single video within a batch."""
    index: int
    topic: str
    job_id: Optional[str] = None
    status: str = "queued"
    video_url: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0


class BatchJobStatus(BaseModel):
    """Status of the entire batch."""
    batch_id: str
    status: str = "queued"
    total: int
    completed: int = 0
    failed: int = 0
    progress: int = 0
    items: List[BatchJobItem] = Field(default_factory=list)
    error: Optional[str] = None


# ── Shared ─────────────────────────────────────────────────────────────────────

class PaystackInitRequest(BaseModel):
    email: str
    plan: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    video_type: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    cta: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[int] = None
    status_detail: Optional[str] = None
    estimated_remaining: Optional[int] = None   # seconds remaining (Part 4 frontend)
    warnings: Optional[List[str]] = None        # non-fatal issues
    artifacts: Optional[dict] = None
    package_url: Optional[str] = None
    audio_url: Optional[str] = None
    quality_score: Optional[float] = None
    title: Optional[str] = None
