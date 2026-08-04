"""
services/ai/schemas.py — Pydantic models for all AI response objects.

These are the canonical data contracts between the AI layer and the rest of
the application.  Every AI agent validates its output against one of these
models before returning it to business logic.

Parsing convention
------------------
    result = MyModel.model_validate_json(raw_json_string)

or from a dict:

    result = MyModel.model_validate(parsed_dict)

Schema versioning
-----------------
All models use model_config = ConfigDict(extra="allow") so that new fields
added by the AI layer never crash existing consumers.  Consumers only read
fields they know about — unknown fields are silently accepted.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.ai.media.visual_intent import VisualIntent
from services.ai.media.asset_types import AssetKind

# ── Shared config ─────────────────────────────────────────────────────────────

_EXTRA_ALLOW = ConfigDict(extra="allow")   # forward-compatible: new fields never break consumers


# ────────────────────────────────────────────────────────────────────────────────
#  Script-layer primitives
# ────────────────────────────────────────────────────────────────────────────────

EmotionType = Literal["urgent", "hopeful", "informative", "empathetic", "inspiring"]
_VALID_EMOTIONS: set[str] = {"urgent", "hopeful", "informative", "empathetic", "inspiring"}

def _coerce_str_or_join(v: Any, sep: str = " ") -> str:
    """Shared coercion for fields where a model sometimes reasonably
    returns a list of phrases instead of one string (a beat's on-screen
    description changing over its duration, motion changing mid-shot, a
    thumbnail's multiple text elements). Joins rather than rejects a
    well-formed-but-wrong-shape answer."""
    if isinstance(v, list):
        return sep.join(str(item) for item in v if item)
    return v if isinstance(v, str) else str(v)

class Scene(BaseModel):
    """A single scene within a video script."""

    model_config = _EXTRA_ALLOW

    description:  str   = Field(..., description="Cinematic scene description for the director.")
    image_prompt: str   = Field(..., description="Self-contained AI image generation prompt.")
    emotion:      EmotionType = Field(default="informative")
    duration:     float = Field(default=5.0, ge=1.0, le=120.0)
    narration:    str   = Field(default="", description="Spoken narration for this scene only.")

    @field_validator("emotion", mode="before")
    @classmethod
    def coerce_emotion(cls, v: Any) -> str:
        """Coerce unknown emotion values to 'informative' rather than crashing."""
        if isinstance(v, str) and v.lower() in _VALID_EMOTIONS:
            return v.lower()
        return "informative"


class ScriptResult(BaseModel):
    """
    Full script produced by the Script Agent.

    This is the primary output consumed by audio, image, and render pipelines.
    """

    model_config = _EXTRA_ALLOW

    hook:      str        = Field(..., description="Short emotionally strong opening line.")
    narration: str        = Field(..., description="Full spoken narration — no stage directions.")
    scenes:    list[Scene] = Field(..., min_length=1)
    caption:   str        = Field(..., description="Social media caption with hashtags.")
    cta:       str        = Field(..., description="Short calm call-to-action.")

    @model_validator(mode="after")
    def check_scene_count(self) -> "ScriptResult":
        if not self.scenes:
            raise ValueError("ScriptResult must contain at least one scene.")
        return self

    def to_legacy_dict(self) -> dict:
        """
        Converts this model back to the flat dict shape expected by the
        existing renderer, audio, and image pipelines.

        This shim preserves backward compatibility during the transition period.
        """
        return {
            "hook":      self.hook,
            "narration": self.narration,
            "scenes":    [s.model_dump() for s in self.scenes],
            "caption":   self.caption,
            "cta":       self.cta,
        }


# ────────────────────────────────────────────────────────────────────────────────
#  Research layer — full expanded schema (v2)
# ────────────────────────────────────────────────────────────────────────────────

class RiskType(str, Enum):
    MEDICAL_ADVICE    = "medical_advice"
    LEGAL_CONCERN     = "legal_concern"
    FINANCIAL_ADVICE  = "financial_advice"
    OUTDATED_INFO     = "outdated_info"
    DISPUTED_CLAIM    = "disputed_claim"
    MISINFORMATION    = "misinformation"
    SENSITIVE_CONTENT = "sensitive_content"


class VisualType(str, Enum):
    STOCK_VIDEO = "stock_video"
    HISTORICAL_FOOTAGE = "historical_footage"
    DOCUMENTARY_FOOTAGE = "documentary_footage"
    NEWS_FOOTAGE = "news_footage"
    OFFICIAL_COMPANY_VIDEO = "official_company_video"
    PRODUCT_FOOTAGE = "product_footage"
    DRONE_FOOTAGE = "drone_footage"
    B_ROLL = "b_roll"
    STOCK_IMAGE = "stock_image"
    HISTORICAL_PHOTO = "historical_photo"
    COMPANY_PRESS_IMAGE = "company_press_image"
    OFFICIAL_PRODUCT_IMAGE = "official_product_image"
    SCREENSHOT = "screenshot"
    WEBSITE_CAPTURE = "website_capture"
    UI_RECORDING = "ui_recording"
    SCREEN_RECORDING = "screen_recording"
    MAP = "map"
    TIMELINE_ANIMATION = "timeline_animation"
    MOTION_GRAPHIC = "motion_graphic"
    CHART = "chart"
    INFOGRAPHIC = "infographic"
    LOGO = "logo"
    AI_IMAGE = "ai_image"
    AI_VIDEO = "ai_video"

    # Backward-compatible aliases retained for previously cached artifacts.
    STOCK_FOOTAGE = "stock_footage"
    TIMELINE = "timeline"
    ANIMATION = "animation"
    PRODUCT_UI = "product_ui"


class SourceType(str, Enum):
    GOVERNMENT = "government"
    NGO        = "ngo"
    ACADEMIC   = "academic"
    NEWS       = "news"
    INDUSTRY   = "industry"


class HookAngle(str, Enum):
    CURIOSITY    = "curiosity"
    SUSPENSE     = "suspense"
    INSPIRATION  = "inspiration"
    CONTROVERSY  = "controversy"
    HOPE         = "hope"
    CAUTION      = "caution"
    DISCOVERY    = "discovery"


# ── Sub-models ────────────────────────────────────────────────────────────────

class EmotionalAngle(BaseModel):
    """A storytelling emotional angle with an example hook."""

    model_config = _EXTRA_ALLOW

    angle:       str = Field(..., description="Emotion type, e.g. 'curiosity', 'suspense'.")
    description: str = Field(..., description="Why this angle works for the topic and audience.")
    example_hook: str = Field(default="", description="Short example of how to open with this angle.")


class HookOpportunity(BaseModel):
    """A single hook idea — curiosity-driven, never clickbait."""

    model_config = _EXTRA_ALLOW

    hook:     str   = Field(..., description="The opening line or question.")
    angle:    str   = Field(default="curiosity", description="Emotional angle driving this hook.")
    strength: float = Field(default=7.0, ge=0.0, le=10.0, description="Estimated engagement score 0–10.")

    @field_validator("angle", mode="before")
    @classmethod
    def coerce_angle(cls, v: Any) -> str:
        valid = {a.value for a in HookAngle}
        if isinstance(v, str) and v.lower() in valid:
            return v.lower()
        return "curiosity"


class VisualOpportunity(BaseModel):
    """A visual opportunity with sourcing guidance for the rendering pipeline."""

    model_config = _EXTRA_ALLOW

    concept:      str = Field(..., description="What the visual should show.")
    visual_type:  str = Field(default="ai_image", description="Type: ai_image | stock_footage | screenshot | chart | map | timeline | animation | product_ui | historical_photo | logo")
    description:  str = Field(default="", description="Detailed description for generation or sourcing.")
    scene_moment: str = Field(default="", description="Which point in the story this visual fits.")

    @field_validator("visual_type", mode="before")
    @classmethod
    def coerce_visual_type(cls, v: Any) -> str:
        valid = {vt.value for vt in VisualType}
        if isinstance(v, str) and v.lower() in valid:
            return v.lower()
        return "ai_image"


class RelatedTopic(BaseModel):
    """A related topic suitable for a future video."""

    model_config = _EXTRA_ALLOW

    topic:          str = Field(..., description="The related topic.")
    relevance:      str = Field(default="", description="Why it connects to the current topic.")
    content_angle:  str = Field(default="", description="Suggested format or angle.")


class ReliableSource(BaseModel):
    """A credible reference for the research topic."""

    model_config = _EXTRA_ALLOW

    name:      str = Field(..., description="Source name, e.g. 'WHO', 'NBS Nigeria'.")
    type:      str = Field(default="news", description="government | ngo | academic | news | industry")
    relevance: str = Field(default="", description="What this source covers for this topic.")

    @field_validator("type", mode="before")
    @classmethod
    def coerce_source_type(cls, v: Any) -> str:
        valid = {st.value for st in SourceType}
        if isinstance(v, str) and v.lower() in valid:
            return v.lower()
        return "news"


class RiskFlag(BaseModel):
    """A content risk identified for this topic."""

    model_config = _EXTRA_ALLOW

    risk_type:   str = Field(..., description="medical_advice | legal_concern | financial_advice | outdated_info | disputed_claim | misinformation | sensitive_content")
    description: str = Field(..., description="What the risk is.")
    mitigation:  str = Field(default="", description="How to handle it responsibly.")

    @field_validator("risk_type", mode="before")
    @classmethod
    def coerce_risk_type(cls, v: Any) -> str:
        valid = {rt.value for rt in RiskType}
        if isinstance(v, str) and v.lower() in valid:
            return v.lower()
        return "sensitive_content"


class ContentAngles(BaseModel):
    """Platform-specific content angle suggestions."""

    model_config = _EXTRA_ALLOW

    tiktok_short:   str = Field(default="", description="Best angle for TikTok / Reel (15–60s).")
    youtube_short:  str = Field(default="", description="Best angle for YouTube Short.")
    youtube_long:   str = Field(default="", description="Best angle for a 5–15 min YouTube video.")
    blog:           str = Field(default="", description="Best angle for a blog article.")
    linkedin:       str = Field(default="", description="Best angle for a LinkedIn post.")
    twitter_thread: str = Field(default="", description="Best angle for an X/Twitter thread.")
    newsletter:     str = Field(default="", description="Best angle for a newsletter section.")


class AudienceInsights(BaseModel):
    """Audience intelligence for the specific topic × platform combination."""

    model_config = _EXTRA_ALLOW

    primary_pain_points: list[str] = Field(default_factory=list)
    common_questions:    list[str] = Field(default_factory=list)
    emotional_triggers:  list[str] = Field(default_factory=list)
    cultural_context:    str       = Field(default="", description="Cultural nuances relevant to the intended audience.")

class ResearchCoreFacts(BaseModel):
    """Module 1: the factual foundation. Merged into ResearchResult."""
    model_config = _EXTRA_ALLOW

    executive_summary: str = Field(..., description="3-5 sentence overview — factual, no hype.")
    key_facts:         list[str] = Field(default_factory=list)
    timeline:          list[str] = Field(default_factory=list)
    surprising_facts:  list[str] = Field(default_factory=list)
    misconceptions:    list[str] = Field(default_factory=list)
    interesting_stats: list[str] = Field(default_factory=list)
    content_warnings:  list[str] = Field(default_factory=list)


class ResearchEngagement(BaseModel):
    """Module 2: hooks and storytelling framing. Merged into ResearchResult."""
    model_config = _EXTRA_ALLOW

    emotional_angles:      list[EmotionalAngle]  = Field(default_factory=list)
    hook_opportunities:    list[HookOpportunity] = Field(default_factory=list)
    suggested_hook_angles: list[str]             = Field(default_factory=list)
    content_angles:        ContentAngles         = Field(default_factory=ContentAngles)


class ResearchVisualContext(BaseModel):
    """Module 3: visual sourcing, sources, risk, audience. Merged into ResearchResult."""
    model_config = _EXTRA_ALLOW

    visual_opportunities: list[VisualOpportunity] = Field(default_factory=list)
    search_keywords:      list[str]               = Field(default_factory=list)
    related_topics:       list[RelatedTopic]       = Field(default_factory=list)
    reliable_sources:     list[ReliableSource]     = Field(default_factory=list)
    risk_flags:           list[RiskFlag]           = Field(default_factory=list)
    audience_insights:    AudienceInsights         = Field(default_factory=AudienceInsights)
    
# ── Core ResearchResult model ─────────────────────────────────────────────────

class ResearchResult(BaseModel):
    """
    Structured research package produced by the Research Intelligence Agent.

    This is the SINGLE SOURCE OF TRUTH consumed by every downstream agent:
      - Script Agent (TikTok, YouTube Shorts, YouTube Long-form)
      - Title Agent
      - Thumbnail Agent
      - SEO Agent
      - Blog Agent
      - LinkedIn Agent
      - Newsletter Agent

    Versioning
    ----------
    model_config = extra="allow" means new fields added by the AI layer
    are silently accepted. Existing consumers keep working without changes.

    Usage
    -----
        from services.ai.schemas import ResearchResult

        result = ResearchResult.model_validate(raw_dict)
        result = ResearchResult.model_validate_json(raw_json_string)
    """

    model_config = _EXTRA_ALLOW

    # ── Identity ──────────────────────────────────────────────────────────────
    topic:    str = Field(..., description="The original research topic.")
    platform: str = Field(default="tiktok", description="Target platform.")
    tone:     str = Field(default="educational", description="Target tone.")

    # ── Core knowledge ────────────────────────────────────────────────────────
    executive_summary:    str        = Field(..., description="3–5 sentence overview — factual, no hype.")
    key_facts:            list[str]  = Field(default_factory=list, description="Most important verified facts (8+ items).")
    timeline:             list[str]  = Field(default_factory=list, description="Chronological events, prefixed with year.")
    surprising_facts:     list[str]  = Field(default_factory=list, description="Little-known, counterintuitive facts.")
    misconceptions:       list[str]  = Field(default_factory=list, description="Myths and corrections.")
    interesting_stats:    list[str]  = Field(default_factory=list, description="Stats with source attribution.")

    # ── Storytelling intelligence ─────────────────────────────────────────────
    emotional_angles:       list[EmotionalAngle]    = Field(default_factory=list, description="5+ emotional storytelling approaches.")
    hook_opportunities:     list[HookOpportunity]   = Field(default_factory=list, description="10+ curiosity-driven hook ideas.")
    suggested_hook_angles:  list[str]               = Field(default_factory=list, description="Simple hook phrases (backward-compat shortcut).")

    # ── Visual intelligence ───────────────────────────────────────────────────
    visual_opportunities: list[VisualOpportunity] = Field(default_factory=list, description="8+ visual concepts with sourcing guidance.")

    # ── Distribution intelligence ─────────────────────────────────────────────
    search_keywords:  list[str]          = Field(default_factory=list, description="SEO / asset-search keywords.")
    related_topics:   list[RelatedTopic] = Field(default_factory=list, description="5+ future video ideas.")
    content_angles:   ContentAngles      = Field(default_factory=ContentAngles)

    # ── Credibility ───────────────────────────────────────────────────────────
    reliable_sources: list[ReliableSource] = Field(default_factory=list, description="3+ credible references.")

    # ── Risk ──────────────────────────────────────────────────────────────────
    risk_flags:       list[RiskFlag]  = Field(default_factory=list, description="Content risk flags.")
    content_warnings: list[str]       = Field(default_factory=list, description="Advisor notes for the publisher.")

    # ── Audience ──────────────────────────────────────────────────────────────
    audience_insights: AudienceInsights = Field(default_factory=AudienceInsights)

    # ── Legacy aliases (backward-compat with v1 ResearchResult) ───────────────
    # Agents that used these fields on the old schema still work:
    #   research.keywords         → search_keywords
    #   research.visual_opportunities → list[str] in v1, list[VisualOpportunity] in v2

    @property
    def keywords(self) -> list[str]:
        """Backward-compat alias for search_keywords."""
        return self.search_keywords

    @property
    def has_risks(self) -> bool:
        """Quick check: does this research contain any risk flags?"""
        return len(self.risk_flags) > 0

    @property
    def best_hooks(self) -> list[str]:
        """
        Return the top 5 hooks by strength score.
        Falls back to suggested_hook_angles if hook_opportunities is empty.
        """
        if self.hook_opportunities:
            top = sorted(self.hook_opportunities, key=lambda h: h.strength, reverse=True)
            return [h.hook for h in top[:5]]
        return self.suggested_hook_angles[:5]


# ────────────────────────────────────────────────────────────────────────────────
#  Title Agent schemas
# ────────────────────────────────────────────────────────────────────────────────

class TitleSuggestion(BaseModel):
    """A single video title candidate."""

    model_config = _EXTRA_ALLOW

    title:      str   = Field(..., description="The candidate title.")
    hook_score: float = Field(default=0.0, ge=0.0, le=10.0, description="Estimated hook strength 0–10.")
    rationale:  str   = Field(default="", description="Why this title works.")


class TitleResult(BaseModel):
    """Output of the Title Agent."""

    model_config = _EXTRA_ALLOW

    titles:     list[TitleSuggestion] = Field(..., min_length=1)
    best_title: str = Field(..., description="The top recommended title.")


# ────────────────────────────────────────────────────────────────────────────────
#  Thumbnail Agent schemas
# ────────────────────────────────────────────────────────────────────────────────

class ThumbnailSuggestion(BaseModel):
    """A single thumbnail concept."""

    model_config = _EXTRA_ALLOW

    concept:       str       = Field(..., description="Visual concept description.")
    image_prompt:  str       = Field(..., description="AI image generation prompt for this thumbnail.")
    text_overlay:  str       = Field(default="", description="Bold text to overlay on the thumbnail.")
    color_palette: list[str] = Field(default_factory=list, description="Hex color suggestions.")


class ThumbnailResult(BaseModel):
    """Output of the Thumbnail Agent."""

    model_config = _EXTRA_ALLOW

    suggestions: list[ThumbnailSuggestion] = Field(..., min_length=1)
    best:        ThumbnailSuggestion


# ────────────────────────────────────────────────────────────────────────────────
#  SEO Agent schemas
# ────────────────────────────────────────────────────────────────────────────────

class SEOResult(BaseModel):
    """Output of the SEO Agent."""

    model_config = _EXTRA_ALLOW

    title:              str          = Field(..., description="SEO-optimised video title.")
    description:        str          = Field(..., description="Full video description with keywords.")
    tags:               list[str]    = Field(..., description="YouTube/TikTok tags.")
    hashtags:           list[str]    = Field(..., description="Social media hashtags.")
    primary_keyword:    str          = Field(..., description="The central keyword to rank for.")
    secondary_keywords: list[str]    = Field(default_factory=list)
    chapters:           Optional[list[str]] = Field(default=None, description="YouTube chapter timestamps.")


# ────────────────────────────────────────────────────────────────────────────────
#  YouTube Studio production schemas
# ────────────────────────────────────────────────────────────────────────────────

class QualityIssue(BaseModel):
    """Actionable issue found by a validation or QA stage."""

    model_config = _EXTRA_ALLOW

    severity: Literal["low", "medium", "high", "critical"] = "medium"
    stage: str = Field(..., description="Pipeline stage where the issue was found.")
    issue: str = Field(..., description="Clear description of the problem.")
    recommendation: str = Field(default="", description="Specific fix or mitigation.")

    @field_validator("severity", mode="before")
    @classmethod
    def coerce_severity(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "medium"
        value = v.strip().lower()
        mapping = {
            "minor": "low",
            "warning": "medium",
            "moderate": "medium",
            "major": "high",
            "severe": "critical",
            "blocker": "critical",
            "fatal": "critical",
        }
        return mapping.get(value, value if value in {"low", "medium", "high", "critical"} else "medium")


class TopicIntelligenceResult(BaseModel):
    """Stage 1: structured content brief from a raw topic."""

    model_config = _EXTRA_ALLOW

    topic: str
    target_audience: str
    search_intent: str
    viewer_expectations: list[str] = Field(default_factory=list)
    educational_depth: Literal["introductory", "intermediate", "advanced"] = "intermediate"
    emotional_angle: str
    monetization_suitability: str
    recommended_video_length_seconds: int = Field(default=600, ge=60, le=2400)
    recommended_storytelling_style: str
    production_notes: list[str] = Field(default_factory=list)


class StoryArchitectureResult(BaseModel):
    """Stage 3: story shape before narration is written."""

    model_config = _EXTRA_ALLOW
    opening_hook: str
    central_question: str
    central_conflict: str
    acts: list[StoryAct]
    key_turning_points: list[str] = Field(default_factory=list)
    climax: str
    conclusion: str
    emotional_progression: list[str] = Field(default_factory=list)
    pacing_notes: list[str] = Field(default_factory=list)


class StoryAct(BaseModel):
    title: str
    purpose: str
    story_goal: str
    key_points: list[str]


class NarrationSectionMeta(BaseModel):
    """
    Phase 2A: Metadata for a single narration section (future section-based generation).
    
    This schema prepares for future section-based narration where each section
    is generated independently with specific token budgets and constraints.
    
    Example sections:
    - Hook: 30-50 words, high-impact opening
    - Introduction: 80-120 words, context setting
    - Chapter 1: 200-300 words, first main point
    - Chapter 2: 200-300 words, second main point
    - Conclusion: 100-150 words, synthesis
    - CTA: 30-50 words, call to action
    """
    
    model_config = _EXTRA_ALLOW
    
    section_type: Literal["hook", "introduction", "chapter", "conclusion", "cta"] = Field(..., description="Type of section.")
    title: str = Field(..., description="Section title (e.g., 'Hook', 'Chapter 1: The Discovery').")
    target_word_count: int = Field(..., ge=1, description="Target word count for this section.")
    actual_word_count: int = Field(default=0, ge=0, description="Actual word count after generation.")
    start_time_seconds: float = Field(default=0.0, ge=0.0, description="Approximate start time in video.")
    duration_seconds: float = Field(..., ge=5.0, description="Target duration for this section.")
    key_points: list[str] = Field(default_factory=list, description="Key points to cover in this section.")
    emotional_tone: str = Field(default="informative", description="Emotional tone for this section.")
    
    @property
    def token_budget(self) -> int:
        """Calculate token budget for this section (~1.35 tokens per word)."""
        return max(50, min(1500, round(self.target_word_count * 1.35)))


class DocumentaryNarration(BaseModel):
    """
    Stage 4a: Long-form narration only (no metadata, no JSON structure).
    
    This is generated FIRST by a specialized narration writer agent that outputs
    plain markdown prose, NOT JSON. The narration is the spoken script for the video.
    
    Token optimization: By separating narration from metadata, we avoid passing
    2,500+ token narration to downstream agents that only need metadata.
    
    Phase 2A Extension: Prepared for future section-based generation.
    Currently generates monolithic narration, but schema supports sectioned format
    for future migration to Hook/Intro/Chapters/Conclusion/CTA architecture.
    """

    model_config = _EXTRA_ALLOW

    title: str = Field(..., description="Working title for this narration.")
    narration: str = Field(..., description="Full spoken narration (700-1500 words for long-form video).")
    estimated_duration_seconds: int = Field(default=600, ge=30, description="Calculated from word count.")
    
    # Phase 2A: Section-based generation interface (optional, for future use)
    # When section_mode=True, narration will contain section markers
    # Format: "## Hook\n{content}\n\n## Introduction\n{content}\n\n## Chapter 1: Title\n..."
    section_mode: bool = Field(default=False, description="Whether narration uses section-based format.")
    section_metadata: Optional[list[NarrationSectionMeta]] = Field(default=None, description="Section generation metadata when narration was built section-by-section.")

    @property
    def word_count(self) -> int:
        """Return actual word count of narration."""
        return len(self.narration.split())
    
    @property
    def sections_parsed(self) -> dict[str, str]:
        """
        Parse section-based narration into structured sections.
        
        Phase 2A: Future support for section-based generation.
        Returns: {"Hook": "...", "Introduction": "...", "Chapter 1": "...", etc.}
        """
        if not self.section_mode:
            return {"Full Narration": self.narration}
        
        sections = {}
        current_section = "Preamble"
        current_content = []
        
        for line in self.narration.split("\n"):
            if line.strip().startswith("## "):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line.strip()[3:].strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()
        
        return sections


class DocumentaryMetadata(BaseModel):
    """
    Stage 4b: Structured metadata extracted from narration.
    
    This is generated SECOND by a lightweight metadata extraction agent that
    reads the narration and extracts structured information WITHOUT including
    the narration itself.
    
    Token optimization: Downstream agents receive only this metadata (~200-400 tokens)
    instead of the full script artifact (~2,500 tokens).
    
    Phase 2A Extension: Enhanced for future section-based generation support.
    """

    model_config = _EXTRA_ALLOW

    hook: str = Field(..., description="Opening hook extracted from narration.")
    sections: list[str] = Field(default_factory=list, description="Major section boundaries (3-7 sections).")
    key_entities: list[str] = Field(default_factory=list, description="People, companies, places mentioned.")
    key_facts: list[str] = Field(default_factory=list, description="Core facts presented (5-8 items).")
    chapters: list[str] = Field(default_factory=list, description="YouTube chapter markers with timestamps.")
    source_notes: list[str] = Field(default_factory=list, description="Credible references cited.")
    estimated_duration_seconds: int = Field(default=600, ge=30)
    
    # Phase 2A: Section metadata for future section-based generation
    # When populated, provides structured section information
    section_metadata: Optional[list[NarrationSectionMeta]] = Field(default=None, description="Detailed section metadata for section-based generation.")

    @field_validator("sections", "key_entities", "key_facts", "chapters", "source_notes", mode="before")
    @classmethod
    def coerce_string_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            parts = [part.strip() for part in v.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return [str(v)]


class NarrationSectionResult(BaseModel):
    """Checkpointed output for one generated narration section."""

    model_config = _EXTRA_ALLOW

    section: NarrationSectionMeta
    narration: str
    summary: str = Field(default="", description="Continuity summary passed to later sections.")
    actual_word_count: int = Field(default=0, ge=0)
    estimated_duration_seconds: int = Field(default=1, ge=1)
    provider: str = "unknown"
    model: str = "unknown"
    prompt_tokens: int = 0
    output_tokens: int = 0
    thoughts_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = "unknown"
    latency_ms: int = 0
    retry_count: int = 0


class DocumentaryScriptResult(BaseModel):
    """
    Stage 4: LEGACY combined artifact (narration + metadata).
    
    This model is DEPRECATED for internal use but maintained for backwards compatibility.
    New code should use DocumentaryNarration and DocumentaryMetadata separately.
    
    Migration adapter: This can be constructed from separated artifacts via from_separated().
    """

    model_config = _EXTRA_ALLOW

    hook: str
    narration: str
    sections: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int = Field(default=600, ge=30)
    source_notes: list[str] = Field(default_factory=list)
    # Propagated from DocumentaryNarration when built via run_section_based_narration_writer.
    # None when constructed from a legacy combined generation (old script_writer path).
    section_metadata: Optional[list[NarrationSectionMeta]] = Field(
        default=None,
        description="Per-section timing/word-count metadata produced by the sectioned narration writer.",
    )

    @field_validator("sections", "source_notes", mode="before")
    @classmethod
    def coerce_string_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            parts = [part.strip() for part in v.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return [str(v)]

    @classmethod
    def from_separated(cls, narration: DocumentaryNarration, metadata: DocumentaryMetadata) -> "DocumentaryScriptResult":
        """
        Construct legacy DocumentaryScriptResult from separated artifacts.
        
        Use this adapter to maintain backwards compatibility with existing code
        while internally using the separated architecture.
        """
        return cls(
            hook=metadata.hook,
            narration=narration.narration,
            sections=metadata.sections,
            estimated_duration_seconds=narration.estimated_duration_seconds,
            source_notes=metadata.source_notes,
            section_metadata=narration.section_metadata or metadata.section_metadata,
        )

    def to_separated(self) -> tuple[DocumentaryNarration, DocumentaryMetadata]:
        """
        Split legacy DocumentaryScriptResult into separated artifacts.
        
        Use this when migrating existing artifacts to the new architecture.
        """
        narration = DocumentaryNarration(
            title=self.hook[:80],  # Use hook as title
            narration=self.narration,
            estimated_duration_seconds=self.estimated_duration_seconds,
            section_metadata=self.section_metadata,
        )
        metadata = DocumentaryMetadata(
            hook=self.hook,
            sections=self.sections,
            key_entities=[],  # Cannot extract from legacy artifact
            key_facts=[],     # Cannot extract from legacy artifact
            chapters=[],      # Cannot extract from legacy artifact
            source_notes=self.source_notes,
            estimated_duration_seconds=self.estimated_duration_seconds,
            section_metadata=self.section_metadata,
        )
        return narration, metadata

class ScriptQAResult(BaseModel):
    """Stage 5: script review and optional revision."""

    model_config = _EXTRA_ALLOW

    approved: bool = False
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    revised_script: DocumentaryScriptResult
    issues: list[QualityIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)

    @field_validator("strengths", mode="before")
    @classmethod
    def coerce_strengths(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            parts = [part.strip() for part in v.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return [str(v)]


class VisualAssetSpec(BaseModel):
    """One asset within a visual beat. A narration beat may use several assets."""

    model_config = _EXTRA_ALLOW

    asset_index: int = 0
    visual_type: VisualType = VisualType.STOCK_VIDEO
    on_screen: str
    reason: str = ""
    sourcing_priority: Literal["real_asset_first", "ai_only", "generated_graphic"] = "real_asset_first"
    search_queries: list[str] = Field(default_factory=list)
    preferred_sources: list[str] = Field(default_factory=list)
    generation_prompt: str = ""
    motion_direction: str = "slow cinematic push-in"

    @field_validator("visual_type", mode="before")
    @classmethod
    def coerce_visual_type(cls, v: Any) -> str:
        return _coerce_visual_type_value(v)

    @field_validator("sourcing_priority", mode="before")
    @classmethod
    def coerce_sourcing_priority(cls, v: Any) -> str:
        return _coerce_sourcing_priority_value(v)

    @field_validator("search_queries", "preferred_sources", mode="before")
    @classmethod
    def coerce_string_lists(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            parts = [part.strip() for part in v.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return [str(v)]


def _coerce_visual_type_value(v: Any) -> str:
    if isinstance(v, VisualType):
        return v.value
    if not isinstance(v, str):
        return VisualType.AI_IMAGE.value
    normalized = v.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "stock": "stock_video",
        "stock_footage": "stock_video",
        "footage": "stock_video",
        "video": "stock_video",
        "broll": "b_roll",
        "b_roll": "b_roll",
        "historical_video": "historical_footage",
        "documentary_video": "documentary_footage",
        "news_video": "news_footage",
        "official_video": "official_company_video",
        "company_video": "official_company_video",
        "product": "product_footage",
        "product_video": "product_footage",
        "drone": "drone_footage",
        "aerial": "drone_footage",
        "photo": "historical_photo",
        "image": "stock_image",
        "generated_image": "ai_image",
        "ai": "ai_image",
        "ai_generated_image": "ai_image",
        "product_ui": "screenshot",
        "website": "website_capture",
        "webpage": "website_capture",
        "screen_capture": "screenshot",
        "timeline": "timeline_animation",
        "animation": "motion_graphic",
        "graphic": "motion_graphic",
        "diagram": "infographic",
    }
    normalized = aliases.get(normalized, normalized)
    valid = {item.value for item in VisualType}
    return normalized if normalized in valid else VisualType.AI_IMAGE.value


def _coerce_sourcing_priority_value(v: Any) -> str:
    if not isinstance(v, str):
        return "real_asset_first"
    normalized = v.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "real": "real_asset_first",
        "real_first": "real_asset_first",
        "real_asset": "real_asset_first",
        "authentic": "real_asset_first",
        "ai": "ai_only",
        "ai_generation": "ai_only",
        "graphic": "generated_graphic",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"real_asset_first", "ai_only", "generated_graphic"} else "real_asset_first"


class VisualTimelineItem(BaseModel):
    """A single planned visual beat aligned to narration."""

    model_config = _EXTRA_ALLOW

    index: int
    start_seconds: float = Field(default=0.0, ge=0.0)
    end_seconds: float = Field(default=5.0, ge=0.0)
    narration_reference: str
    on_screen: str
    asset_type: VisualType = VisualType.AI_IMAGE
    sourcing_priority: Literal["real_asset_first", "ai_only", "generated_graphic"] = "real_asset_first"
    search_queries: list[str] = Field(default_factory=list)
    generation_prompt: str = ""
    motion_direction: str = "slow cinematic push-in"
    reason: str = ""
    assets: list[VisualAssetSpec] = Field(default_factory=list)

    @field_validator("motion_direction", mode="before")
    @classmethod
    def coerce_motion_direction(cls, v: Any) -> str:
        """Models sometimes describe motion changing partway through a
        longer beat as a list of directional phrases instead of one string
        — join them into a single description rather than reject a
        reasonable answer in the wrong shape."""
        if isinstance(v, list):
            return " then ".join(str(item) for item in v if item)
        return v if isinstance(v, str) else str(v)

    @field_validator("on_screen", mode="before")
    @classmethod
    def coerce_on_screen(cls, v: Any) -> str:
        return _coerce_str_or_join(v)

    @model_validator(mode="before")
    @classmethod
    def repair_alias_fields(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw

        data = dict(raw)
        prompt = (
            data.get("generation_prompt")
            or data.get("image_prompt")
            or data.get("prompt")
            or data.get("visual_prompt")
            or data.get("description")
            or data.get("scene")
            or data.get("visual")
            or data.get("on_screen")
            or ""
        )
        if not data.get("on_screen"):
            data["on_screen"] = str(
                data.get("screen")
                or data.get("visual_description")
                or data.get("description")
                or prompt
                or "Generated documentary visual"
            )
        if not data.get("narration_reference"):
            data["narration_reference"] = str(
                data.get("narration")
                or data.get("voiceover")
                or data.get("script_reference")
                or data.get("beat")
                or data["on_screen"]
            )
        if prompt and not data.get("generation_prompt"):
            data["generation_prompt"] = str(prompt)

        time_value = data.get("time") or data.get("timestamp")
        if time_value and not data.get("start_seconds"):
            start, end = _parse_time_range(time_value)
            data["start_seconds"] = start
            if not data.get("end_seconds"):
                data["end_seconds"] = end
        if data.get("duration") and not data.get("end_seconds"):
            try:
                data["end_seconds"] = float(data.get("start_seconds", 0.0)) + float(data["duration"])
            except (TypeError, ValueError):
                pass

        return data

    @field_validator("asset_type", mode="before")
    @classmethod
    def coerce_asset_type(cls, v: Any) -> str:
        return _coerce_visual_type_value(v)

    @field_validator("sourcing_priority", mode="before")
    @classmethod
    def coerce_sourcing_priority(cls, v: Any) -> str:
        return _coerce_sourcing_priority_value(v)

    @field_validator("search_queries", mode="before")
    @classmethod
    def coerce_search_queries(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            parts = [part.strip() for part in v.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return [str(v)]

    @model_validator(mode="after")
    def ensure_valid_timing(self) -> "VisualTimelineItem":
        if self.end_seconds <= self.start_seconds:
            self.end_seconds = self.start_seconds + 5.0
        if not self.assets:
            self.assets = [
                VisualAssetSpec(
                    asset_index=0,
                    visual_type=self.asset_type,
                    on_screen=self.on_screen,
                    reason=self.reason,
                    sourcing_priority=self.sourcing_priority,
                    search_queries=self.search_queries,
                    generation_prompt=self.generation_prompt,
                    motion_direction=self.motion_direction,
                )
            ]
        return self


def _parse_time_range(value: Any) -> tuple[float, float]:
    text = str(value).lower().replace("seconds", "").replace("second", "").replace("s", "").strip()
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if not numbers:
        return 0.0, 5.0
    start = float(numbers[0])
    end = float(numbers[1]) if len(numbers) > 1 else start + 5.0
    if end <= start:
        end = start + 5.0
    return start, end


class VisualPlanResult(BaseModel):
    """Stage 6: complete visual timeline before assets are collected."""

    model_config = _EXTRA_ALLOW

    visual_style: str
    consistency_rules: list[str] = Field(default_factory=list)
    timeline: list[VisualTimelineItem] = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def repair_timeline_indices(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        timeline = data.get("timeline")
        if isinstance(timeline, list):
            repaired = []
            cursor = 0.0
            for idx, item in enumerate(timeline):
                if not isinstance(item, dict):
                    repaired.append(item)
                    continue
                item_data = dict(item)
                item_data.setdefault("index", idx)
                item_data.setdefault("start_seconds", cursor)
                item_data.setdefault("end_seconds", float(item_data.get("start_seconds", cursor)) + 5.0)
                cursor = max(cursor, float(item_data.get("end_seconds", cursor + 5.0)))
                assets = item_data.get("assets")
                if isinstance(assets, list):
                    item_data["assets"] = [
                        {**asset, "asset_index": asset.get("asset_index", asset_idx)}
                        if isinstance(asset, dict)
                        else asset
                        for asset_idx, asset in enumerate(assets)
                    ]
                repaired.append(item_data)
            data["timeline"] = repaired
        return data


class AssetCandidate(BaseModel):
    """A real or generated asset candidate for a visual beat."""

    model_config = _EXTRA_ALLOW

    visual_index: int
    asset_index: int = 0
    source: str
    asset_type: str
    url: str = ""
    local_path: str = ""
    license: str = "unknown"
    credit: str = ""
    suitability_score: float = Field(default=0.0, ge=0.0, le=10.0)
    notes: str = ""


class AssetCollectionResult(BaseModel):
    """Stage 7: selected real assets and explicit AI fallback needs."""

    model_config = _EXTRA_ALLOW

    selected_assets: list[AssetCandidate] = Field(default_factory=list)
    ai_required_indices: list[int] = Field(default_factory=list)
    issues: list[QualityIssue] = Field(default_factory=list)


class ImageGenerationPlanResult(BaseModel):
    """Stage 8: prompts for only the visuals that need AI generation."""

    model_config = _EXTRA_ALLOW

    style_reference: str
    prompts: list[VisualTimelineItem] = Field(default_factory=list)
    negative_prompt: str = "distorted faces, unreadable text, extra fingers, artifacts, watermark, logo errors"

    @model_validator(mode="before")
    @classmethod
    def repair_prompt_indices(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        prompts = data.get("prompts")
        if isinstance(prompts, list):
            data["prompts"] = [
                {**item, "index": item.get("index", idx)}
                if isinstance(item, dict)
                else item
                for idx, item in enumerate(prompts)
            ]
        return data


class VoiceDirectionResult(BaseModel):
    """Stage 9: narration performance guidance and provider settings."""

    model_config = _EXTRA_ALLOW

    voice_profile: str
    pacing_notes: list[str] = Field(default_factory=list)
    pronunciation_notes: list[str] = Field(default_factory=list)
    emotion_map: list[str] = Field(default_factory=list)
    preferred_voice_id: str = "female_warm"


class AudioQAResult(BaseModel):
    """Stage 10: technical and performance checks for generated narration."""

    model_config = _EXTRA_ALLOW

    approved: bool = False
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    duration_seconds: float = 0.0
    issues: list[QualityIssue] = Field(default_factory=list)
    regenerate_ranges: list[str] = Field(default_factory=list)


class EditingPlanResult(BaseModel):
    """Stage 11: deterministic edit plan consumed by renderers/editors."""

    model_config = _EXTRA_ALLOW

    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    fps: int = 30
    music_direction: str = ""
    caption_style: str = ""
    timeline: list[VisualTimelineItem] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def repair_timeline_indices(cls, raw: Any) -> Any:
        return VisualPlanResult.repair_timeline_indices(raw)

class EditingPlanGeneration(BaseModel):
    """What the editing agent actually needs to invent — never the timeline,
    which already exists correctly from visual planning and would otherwise
    be regenerated at real token cost for no reason."""
    model_config = _EXTRA_ALLOW
    fps: int = 30
    music_direction: str = ""
    caption_style: str = ""
    transitions: list[str] = Field(default_factory=list)

class ScoredThumbnailConcept(BaseModel):
    """Stage 12: thumbnail concept with production scoring."""
    model_config = _EXTRA_ALLOW
    concept: str
    image_prompt: str
    text_overlay: str = ""
    curiosity: float = Field(default=0.0, ge=0.0, le=10.0)
    clarity: float = Field(default=0.0, ge=0.0, le=10.0)
    readability: float = Field(default=0.0, ge=0.0, le=10.0)
    mobile_visibility: float = Field(default=0.0, ge=0.0, le=10.0)
    emotional_impact: float = Field(default=0.0, ge=0.0, le=10.0)

    @field_validator("text_overlay", mode="before")
    @classmethod
    def coerce_text_overlay(cls, v: Any) -> str:
        """Models sometimes describe a thumbnail's multiple text elements
        (date, role, milestone) as a list of short phrases instead of one
        string — join them into the single line this field expects rather
        than reject a reasonable answer in the wrong shape."""
        if isinstance(v, list):
            return " | ".join(str(item) for item in v if item)
        return v if isinstance(v, str) else str(v)


class ThumbnailStrategyResult(BaseModel):
    """Stage 12: scored thumbnail options."""

    model_config = _EXTRA_ALLOW

    concepts: list[ScoredThumbnailConcept] = Field(..., min_length=1)
    best_index: int = 0

    @model_validator(mode="after")
    def clamp_best_index(self) -> "ThumbnailStrategyResult":
        if self.best_index < 0 or self.best_index >= len(self.concepts):
            self.best_index = 0
        return self


class ScoredTitleCandidate(BaseModel):
    """Stage 13: title option with transparent scoring."""

    model_config = _EXTRA_ALLOW

    title: str
    curiosity: float = Field(default=0.0, ge=0.0, le=10.0)
    seo: float = Field(default=0.0, ge=0.0, le=10.0)
    ctr_potential: float = Field(default=0.0, ge=0.0, le=10.0)
    clarity: float = Field(default=0.0, ge=0.0, le=10.0)
    rationale: str = ""


class TitleStrategyResult(BaseModel):
    """Stage 13: scored title options."""

    model_config = _EXTRA_ALLOW

    candidates: list[ScoredTitleCandidate] = Field(..., min_length=1)
    best_index: int = 0

    @model_validator(mode="after")
    def clamp_best_index(self) -> "TitleStrategyResult":
        if self.best_index < 0 or self.best_index >= len(self.candidates):
            self.best_index = 0
        return self


class FinalQAResult(BaseModel):
    """Stage 15: final release gate across factual, creative, and technical quality."""

    model_config = _EXTRA_ALLOW

    approved: bool = False
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    factual_consistency: float = Field(default=0.0, ge=0.0, le=100.0)
    script_quality: float = Field(default=0.0, ge=0.0, le=100.0)
    narration_quality: float = Field(default=0.0, ge=0.0, le=100.0)
    image_quality: float = Field(default=0.0, ge=0.0, le=100.0)
    timing_pacing: float = Field(default=0.0, ge=0.0, le=100.0)
    subtitle_accuracy: float = Field(default=0.0, ge=0.0, le=100.0)
    thumbnail_quality: float = Field(default=0.0, ge=0.0, le=100.0)
    title_quality: float = Field(default=0.0, ge=0.0, le=100.0)
    issues: list[QualityIssue] = Field(default_factory=list)


class YouTubeProductionPackage(BaseModel):
    """Serializable bundle of every editable production-stage artifact."""

    model_config = _EXTRA_ALLOW

    topic_intelligence: TopicIntelligenceResult
    research: ResearchResult
    story: StoryArchitectureResult
    script_qa: ScriptQAResult
    visual_plan: VisualPlanResult
    asset_collection: AssetCollectionResult
    image_generation_plan: ImageGenerationPlanResult
    voice_direction: VoiceDirectionResult
    audio_qa: Optional[AudioQAResult] = None
    editing_plan: EditingPlanResult
    thumbnails: ThumbnailStrategyResult
    titles: TitleStrategyResult
    seo: SEOResult
    final_qa: Optional[FinalQAResult] = None


# ────────────────────────────────────────────────────────────────────────────────
#  Motion Design schemas (Remotion)
# ────────────────────────────────────────────────────────────────────────────────

class StatItem(BaseModel):

    model_config = _EXTRA_ALLOW

    label:        str
    value:        str
    suffix:       Optional[str] = None
    prefix:       Optional[str] = None
    numericValue: float = 0.0


class ListItem(BaseModel):

    model_config = _EXTRA_ALLOW

    index:    int
    headline: str
    body:     Optional[str] = None
    emoji:    Optional[str] = None


class DesignBrief(BaseModel):
    """Structured brief consumed by the Remotion motion design templates."""

    model_config = _EXTRA_ALLOW

    style:            Literal["minimal", "bold", "glassmorphism", "neon"] = "minimal"
    aspectRatio:      Literal["9:16", "16:9", "1:1"] = "9:16"
    durationSeconds:  float = 15.0
    brandName:        Optional[str] = None
    brandColor:       str = "#6C63FF"
    accentColor:      str = "#FF6584"
    bgColor:          str = "#0A0A0A"
    textColor:        str = "#FFFFFF"
    title:            str
    subtitle:         Optional[str] = None
    bodyText:         Optional[str] = None
    tagline:          Optional[str] = None
    cta:              Optional[str] = None
    stats:            Optional[list[StatItem]] = None
    listItems:        Optional[list[ListItem]] = None
    animationSpeed:   Literal["slow", "normal", "fast"] = "normal"
    fontPairing:      Literal["syne_dmsans", "inter", "playfair_inter"] = "syne_dmsans"
    sourceType:       Literal["prompt", "flyer"] = "prompt"
    flyerDescription: Optional[str] = None

    @field_validator("style", mode="before")
    @classmethod
    def coerce_style(cls, v: Any) -> str:
        if isinstance(v, str) and v in {"minimal", "bold", "glassmorphism", "neon"}:
            return v
        return "minimal"

    @field_validator("aspectRatio", mode="before")
    @classmethod
    def coerce_aspect(cls, v: Any) -> str:
        if isinstance(v, str) and v in {"9:16", "16:9", "1:1"}:
            return v
        return "9:16"


# ────────────────────────────────────────────────────────────────────────────────
#  Intelligent Media Acquisition Engine schemas
# ────────────────────────────────────────────────────────────────────────────────


class VisualSearchPlan(BaseModel):
    model_config = _EXTRA_ALLOW

    primary_query: str
    alternate_queries: list[str] = Field(default_factory=list)
    preferred_sources: list[str] = Field(default_factory=list)
    avoid_terms: list[str] = Field(default_factory=list)
    required_entities: list[str] = Field(default_factory=list)
    required_objects: list[str] = Field(default_factory=list)
    visual_style: str = "photographic"
    requires_people: bool = False
    requires_logos: bool = False
    requires_buildings: bool = False
    requires_product: bool = False


class MediaPlan(BaseModel):
    model_config = _EXTRA_ALLOW

    scene: int

    visual_intent: VisualIntent

    reasoning: str

    confidence: float = 0.8

    fallback_asset_kind: AssetKind = AssetKind.STOCK_IMAGE


class MediaPlanResult(BaseModel):
    """
    Full video script media plan containing a MediaPlan for each scene.
    """
    model_config = _EXTRA_ALLOW

    plans: list[MediaPlan] = Field(..., min_length=1)
