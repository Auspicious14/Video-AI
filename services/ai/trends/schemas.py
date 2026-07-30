"""
services/ai/trends/schemas.py — Data contracts for the Trend Discovery Engine
═══════════════════════════════════════════════════════════════════════════════

All models use extra="allow" to safely accept future fields from LLM responses
without breaking existing consumers.

Hierarchy
---------
TrendCandidate   →  raw signal from a provider (Google Trends, Reddit, etc.)
TopicOpportunity →  fully enriched+scored topic ready for pipeline consumption
DiscoveryBatch   →  a complete discovery run (metadata + list of opportunities)
DashboardView    →  presentation-layer grouping for the frontend
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EXTRA_ALLOW = ConfigDict(extra="allow")


# ────────────────────────────────────────────────────────────────────────────────
#  Enums
# ────────────────────────────────────────────────────────────────────────────────

class TrendSource(str, Enum):
    """Supported trend signal providers."""
    GOOGLE_TRENDS  = "google_trends"
    YOUTUBE        = "youtube_trending"
    REDDIT         = "reddit"
    HACKER_NEWS    = "hacker_news"
    PRODUCT_HUNT   = "product_hunt"
    TWITTER_X      = "twitter_x"
    GITHUB         = "github_trending"
    RSS            = "rss_feed"
    AI_NEWSLETTER  = "ai_newsletter"
    TECH_BLOG      = "tech_blog"
    MANUAL         = "manual"
    LLM_GENERATED  = "llm_generated"


class ScanFrequency(str, Enum):
    """Scan cadences supported by the scheduler."""
    HOURLY  = "hourly"
    DAILY   = "daily"
    WEEKLY  = "weekly"


class OpportunityTier(str, Enum):
    """Quality tier assigned after scoring."""
    PLATINUM = "platinum"     # 90-100
    GOLD     = "gold"         # 75-89
    SILVER   = "silver"       # 60-74
    BRONZE   = "bronze"       # 40-59
    LOW      = "low"          # 0-39


# ────────────────────────────────────────────────────────────────────────────────
#  Raw signal from a provider
# ────────────────────────────────────────────────────────────────────────────────

class TrendCandidate(BaseModel):
    """
    A raw trend signal collected from a single provider.
    This is the INPUT to the scoring/clustering pipeline.
    """
    model_config = _EXTRA_ALLOW

    title:        str          = Field(..., description="Short title of the trending topic.")
    summary:      str          = Field(default="", description="Brief summary or snippet.")
    source:       TrendSource  = Field(..., description="Provider that surfaced this signal.")
    source_url:   str          = Field(default="", description="Link to the original source.")
    niche:        str          = Field(default="general", description="Content niche (e.g. ai_tools, tech, business).")
    discovered_at: datetime    = Field(default_factory=datetime.utcnow)
    raw_score:    float        = Field(default=0.0, ge=0.0, le=100.0, description="Provider-specific popularity metric (normalized 0-100).")
    engagement:   int          = Field(default=0, description="Upvotes/likes/comments if available.")
    region:       str          = Field(default="global", description="Geographic region (global, us, ng, etc.).")
    language:     str          = Field(default="en")
    tags:         list[str]    = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────────
#  Content angle suggestion
# ────────────────────────────────────────────────────────────────────────────────

class ContentAngleSuggestion(BaseModel):
    """One possible content angle for a topic."""
    model_config = _EXTRA_ALLOW

    angle:       str   = Field(..., description="Name of the angle (e.g. 'Beginner explanation').")
    hook:        str   = Field(default="", description="Suggested opening hook for this angle.")
    description: str   = Field(default="", description="Why this angle works.")
    strength:    float = Field(default=0.7, ge=0.0, le=1.0, description="Estimated engagement strength.")


# ────────────────────────────────────────────────────────────────────────────────
#  Scoring breakdown
# ────────────────────────────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    """Transparent sub-scores for auditing the final opportunity score."""
    model_config = _EXTRA_ALLOW

    novelty:              float = Field(default=0.0, ge=0.0, le=10.0)
    search_interest:      float = Field(default=0.0, ge=0.0, le=10.0)
    audience_curiosity:   float = Field(default=0.0, ge=0.0, le=10.0)
    educational_value:    float = Field(default=0.0, ge=0.0, le=10.0)
    emotional_impact:     float = Field(default=0.0, ge=0.0, le=10.0)
    evergreen_potential:  float = Field(default=0.0, ge=0.0, le=10.0)
    competition:          float = Field(default=0.0, ge=0.0, le=10.0, description="Lower competition = higher score.")
    recency:              float = Field(default=0.0, ge=0.0, le=10.0)
    storytelling:         float = Field(default=0.0, ge=0.0, le=10.0)
    thumbnail_potential:  float = Field(default=0.0, ge=0.0, le=10.0)
    hook_potential:       float = Field(default=0.0, ge=0.0, le=10.0)
    visual_potential:     float = Field(default=0.0, ge=0.0, le=10.0)

    @property
    def weighted_total(self) -> float:
        """Weighted sum → 0-100 final score."""
        weights = {
            "novelty": 1.0,
            "search_interest": 1.2,
            "audience_curiosity": 1.1,
            "educational_value": 0.9,
            "emotional_impact": 1.0,
            "evergreen_potential": 0.7,
            "competition": 0.8,
            "recency": 1.0,
            "storytelling": 0.9,
            "thumbnail_potential": 0.6,
            "hook_potential": 1.0,
            "visual_potential": 0.8,
        }
        raw = sum(
            getattr(self, k) * w for k, w in weights.items()
        )
        max_possible = sum(10.0 * w for w in weights.values())
        return round((raw / max_possible) * 100, 1) if max_possible else 0.0


# ────────────────────────────────────────────────────────────────────────────────
#  Visual opportunity assessment
# ────────────────────────────────────────────────────────────────────────────────

class VisualAssessment(BaseModel):
    """Assessment of the visual potential for a topic."""
    model_config = _EXTRA_ALLOW

    overall_score:    float    = Field(default=0.7, ge=0.0, le=1.0)
    available_types:  list[str] = Field(
        default_factory=list,
        description="Visual types available: screenshot, logo, stock_video, chart, map, product_image, historical_photo, website, ai_image"
    )
    notes:            str      = Field(default="")


# ────────────────────────────────────────────────────────────────────────────────
#  Fully enriched + scored topic opportunity
# ────────────────────────────────────────────────────────────────────────────────

class TopicOpportunity(BaseModel):
    """
    A fully scored topic opportunity ready for VideoAI pipeline consumption.
    This is the OUTPUT of the Trend Discovery Engine.
    """
    model_config = _EXTRA_ALLOW

    # Identity
    id:                  str            = Field(default="", description="Unique hash ID for deduplication.")
    title:               str            = Field(..., description="Final clean topic title.")
    slug:                str            = Field(default="", description="URL-friendly slug.")
    niche:               str            = Field(default="general")

    # Scoring
    score:               float          = Field(default=0.0, ge=0.0, le=100.0, description="Final composite score 0-100.")
    tier:                OpportunityTier = Field(default=OpportunityTier.BRONZE)
    score_breakdown:     ScoreBreakdown  = Field(default_factory=ScoreBreakdown)

    # Context
    summary:             str            = Field(default="", description="2-3 sentence summary of the topic.")
    why_it_matters:      str            = Field(default="", description="Why this topic is relevant right now.")
    target_audience:     str            = Field(default="", description="Best-fit audience segment.")

    # Content strategy
    suggested_hook:      str            = Field(default="", description="Best opening hook.")
    content_angles:      list[ContentAngleSuggestion] = Field(default_factory=list)
    recommended_duration: int           = Field(default=30, description="Recommended video duration in seconds.")
    recommended_platform: str           = Field(default="tiktok", description="Best platform: tiktok | youtube_shorts | youtube_long")

    # Visual assessment
    visual_assessment:   VisualAssessment = Field(default_factory=VisualAssessment)

    # Provenance
    sources:             list[TrendSource] = Field(default_factory=list, description="Providers that surfaced this topic.")
    source_urls:         list[str]       = Field(default_factory=list)
    related_topics:      list[str]       = Field(default_factory=list)
    discovered_at:       datetime        = Field(default_factory=datetime.utcnow)
    cluster_size:        int             = Field(default=1, description="How many raw signals were merged into this opportunity.")

    # State management
    status:              str            = Field(default="new", description="new | queued | in_progress | published | skipped")

    @field_validator("tier", mode="before")
    @classmethod
    def coerce_tier(cls, v: Any) -> str:
        if isinstance(v, str):
            try:
                return OpportunityTier(v.lower())
            except ValueError:
                return OpportunityTier.BRONZE
        return v

    def to_pipeline_input(self) -> dict:
        """Convert to the dict expected by run_research / run_script_agent."""
        return {
            "topic": self.title,
            "tone": "educational",
            "duration": self.recommended_duration,
            "platform": self.recommended_platform,
            "niche_context": self.summary,
        }


# ────────────────────────────────────────────────────────────────────────────────
#  Discovery batch — one full scan run
# ────────────────────────────────────────────────────────────────────────────────

class DiscoveryBatch(BaseModel):
    """
    Output of a complete discovery run. Contains metadata and all scored opportunities.
    """
    model_config = _EXTRA_ALLOW

    batch_id:         str                  = Field(default="")
    niche:            str                  = Field(default="general")
    frequency:        ScanFrequency        = Field(default=ScanFrequency.DAILY)
    started_at:       datetime             = Field(default_factory=datetime.utcnow)
    completed_at:     Optional[datetime]   = None
    candidates_found: int                  = Field(default=0)
    opportunities:    list[TopicOpportunity] = Field(default_factory=list)
    errors:           list[str]            = Field(default_factory=list)

    @property
    def top_opportunities(self) -> list[TopicOpportunity]:
        """Return opportunities sorted by score descending."""
        return sorted(self.opportunities, key=lambda o: o.score, reverse=True)


# ────────────────────────────────────────────────────────────────────────────────
#  Dashboard view — presentation-layer grouping
# ────────────────────────────────────────────────────────────────────────────────

class DashboardView(BaseModel):
    """
    Pre-grouped data for the frontend dashboard.
    """
    model_config = _EXTRA_ALLOW

    top_today:           list[TopicOpportunity] = Field(default_factory=list)
    trending_this_week:  list[TopicOpportunity] = Field(default_factory=list)
    evergreen:           list[TopicOpportunity] = Field(default_factory=list)
    recently_covered:    list[str]              = Field(default_factory=list, description="Topic titles already published.")
