"""
services/ai/research.py — Research Intelligence Agent v2

Responsibility
--------------
Transform a bare topic into a comprehensive, structured ResearchResult.

This is the CENTRAL KNOWLEDGE ENGINE of the VideoAI platform.
Every downstream content agent (Script, Title, Thumbnail, SEO, Blog, LinkedIn,
Newsletter) consumes the same ResearchResult instead of performing its own research.

Research is performed ONCE. All agents reuse it.

What this agent produces
------------------------
  - Executive summary
  - Key facts (8+)
  - Timeline
  - Surprising facts
  - Common misconceptions
  - Emotional angles (with example hooks)
  - Hook opportunities (10+, scored by engagement potential)
  - Visual opportunities (8+, with type taxonomy for the rendering pipeline)
  - Search keywords
  - Related topics (with content angles)
  - Reliable sources (typed by authority level)
  - Risk flags (medical, legal, misinformation, etc.)
  - Content angles per platform (TikTok, YouTube, Blog, LinkedIn, Twitter, Newsletter)
  - Audience insights (pain points, questions, emotional triggers, cultural context)

What this agent does NOT do
---------------------------
  - Write scripts
  - Write titles
  - Generate thumbnails
  - Perform any downstream creative work

Architecture
------------
  run_research()             — Primary async entry point
  research_to_summary()      — Compact text block for script/title/SEO prompts
  research_to_context()      — Rich context block for long-form agents
  research_hooks_summary()   — Top hooks only (for title + thumbnail agents)
  research_risks_summary()   — Risk flags formatted for agent awareness

Usage
-----
    from services.ai.research import run_research, research_to_summary

    research = await run_research(
        topic="Postpartum depression in Nigeria",
        tone="empathetic",
        duration=30,
        platform="tiktok",
        audience_profile="Young Nigerian mothers, 18–35",
    )

    # Pass to downstream agents
    summary = research_to_summary(research)
    print(research.best_hooks)          # top 5 hooks by strength
    print(research.has_risks)           # True if risk flags exist
"""

from __future__ import annotations
from services.ai.studio.agent_utils import generate_structured_artifact

import json
import logging
from typing import Optional
from services.ai.exceptions import ValidationError
from services.ai.schemas import (
    AudienceInsights,
    ContentAngles,
    EmotionalAngle,
    HookOpportunity,
    RelatedTopic,
    ReliableSource,
    ResearchResult,
    RiskFlag,
    VisualOpportunity,
    ResearchVisualContext,
    ResearchCoreFacts, ResearchEngagement,
)
from services.ai.studio.cache import get_or_create_artifact


logger = logging.getLogger(__name__)


# ── Platform constants ─────────────────────────────────────────────────────────

PLATFORM_TIKTOK    = "tiktok"
PLATFORM_YT_SHORT  = "youtube_shorts"
PLATFORM_YT_LONG   = "youtube_long"
PLATFORM_INSTAGRAM = "instagram"
PLATFORM_BLOG      = "blog"
PLATFORM_LINKEDIN  = "linkedin"

_VALID_PLATFORMS = {
    PLATFORM_TIKTOK, PLATFORM_YT_SHORT, PLATFORM_YT_LONG,
    PLATFORM_INSTAGRAM, PLATFORM_BLOG, PLATFORM_LINKEDIN,
}


# ── Public API ─────────────────────────────────────────────────────────────────

async def run_research(
    topic:            str,
    tone:             str  = "educational",
    duration:         int  = 30,
    platform:         str  = PLATFORM_TIKTOK,
    niche_context:    str  = "",
    audience_profile: str  = "",
) -> ResearchResult:
    if platform not in _VALID_PLATFORMS:
        logger.warning("Unknown platform %r — defaulting to 'tiktok'", platform)
        platform = PLATFORM_TIKTOK

    logger.info(
        "Research Agent starting | topic=%r platform=%s tone=%s duration=%ds",
        topic, platform, tone, duration,
    )

    shared_vars = {
        "topic": topic,
        "tone": tone,
        "platform": platform,
        "duration": duration,
        "niche_context": niche_context or "No specific niche context.",
        "audience_profile": audience_profile,
    }

    async def _module(stage: str, prompt_name: str, model: type, max_tokens: int):
        return await get_or_create_artifact(
            stage=f"research_{stage}",
            payload={"stage": stage, **shared_vars},
            model=model,
            factory=lambda: generate_structured_artifact(
                prompt_name=prompt_name,
                model=model,
                temperature=0.45,
                max_tokens=max_tokens,
                variables=shared_vars,
            ),
        )

    core = await _module(
        "core_facts", "research_core_facts", ResearchCoreFacts,
        _tokens_for_duration(duration, "core"),
    )
    engagement = await _module(
        "engagement", "research_engagement", ResearchEngagement,
        _tokens_for_duration(duration, "engagement"),
    )
    visual_context = await _module(
        "visual_context", "research_visual_context", ResearchVisualContext,
        _tokens_for_duration(duration, "visual"),
    )

    merged = {
        **core.model_dump(mode="json"),
        **engagement.model_dump(mode="json"),
        **visual_context.model_dump(mode="json"),
    }

    return _validate_and_repair(merged, topic=topic, platform=platform, tone=tone)

# ── Summary formatters (for downstream agents) ────────────────────────────────

def research_to_summary(research: ResearchResult) -> str:
    """
    Format a ResearchResult into a focused text block for script/title/SEO prompts.

    Optimised for token efficiency — includes the highest-signal fields only.
    """
    hooks = research.best_hooks[:5]
    hook_lines = [f"  - {h}" for h in hooks]

    visual_lines = []
    for v in research.visual_opportunities[:5]:
        if isinstance(v, VisualOpportunity):
            visual_lines.append(f"  - [{v.visual_type}] {v.concept}")
        else:
            visual_lines.append(f"  - {v}")

    emotional_lines = []
    for e in research.emotional_angles[:4]:
        if isinstance(e, EmotionalAngle):
            emotional_lines.append(f"  - {e.angle}: {e.description}")
        else:
            emotional_lines.append(f"  - {e}")

    lines = [
        f"EXECUTIVE SUMMARY: {research.executive_summary}",
        "",
        "KEY FACTS:",
        *[f"  - {f}" for f in research.key_facts[:7]],
        "",
        "SURPRISING FACTS:",
        *[f"  - {f}" for f in research.surprising_facts[:4]],
        "",
        "EMOTIONAL ANGLES:",
        *emotional_lines,
        "",
        "VISUAL OPPORTUNITIES:",
        *visual_lines,
        "",
        "TOP HOOKS:",
        *hook_lines,
        "",
        "KEY STATS:",
        *[f"  - {s}" for s in research.interesting_stats[:4]],
    ]

    # Append risk warning if any flags exist
    if research.has_risks:
        lines += [
            "",
            "⚠️  RISK FLAGS (handle carefully):",
            *[f"  - [{rf.risk_type}] {rf.description}" for rf in research.risk_flags],
        ]

    return "\n".join(lines)


# def research_to_context(research: ResearchResult) -> str:
#     """
#     Format a ResearchResult into a rich context block for long-form agents
#     (YouTube long-form, blog, LinkedIn, newsletters).

#     More detailed than research_to_summary — includes platform angles,
#     audience insights, and misconceptions.
#     """
#     lines = [
#         f"TOPIC: {research.topic}",
#         f"PLATFORM: {research.platform}",
#         f"TONE: {research.tone}",
#         "",
#         f"EXECUTIVE SUMMARY:",
#         f"  {research.executive_summary}",
#         "",
#         "KEY FACTS:",
#         *[f"  {i+1}. {f}" for i, f in enumerate(research.key_facts)],
#         "",
#     ]

#     if research.timeline:
#         lines += [
#             "TIMELINE:",
#             *[f"  - {t}" for t in research.timeline],
#             "",
#         ]

#     lines += [
#         "SURPRISING FACTS:",
#         *[f"  - {f}" for f in research.surprising_facts],
#         "",
#         "MISCONCEPTIONS:",
#         *[f"  - {m}" for m in research.misconceptions],
#         "",
#         "INTERESTING STATS:",
#         *[f"  - {s}" for s in research.interesting_stats],
#         "",
#     ]

#     if research.emotional_angles:
#         lines.append("EMOTIONAL ANGLES:")
#         for ea in research.emotional_angles:
#             if isinstance(ea, EmotionalAngle):
#                 lines.append(f"  [{ea.angle}] {ea.description}")
#                 if ea.example_hook:
#                     lines.append(f"    Example: \"{ea.example_hook}\"")
#             else:
#                 lines.append(f"  - {ea}")
#         lines.append("")

#     lines += [
#         "ALL HOOKS (sorted by strength):",
#         *[f"  [{h.strength:.1f}] {h.hook}" for h in sorted(research.hook_opportunities, key=lambda x: x.strength, reverse=True)],
#         "",
#         "PLATFORM ANGLES:",
#         f"  TikTok/Reels:   {research.content_angles.tiktok_short}",
#         f"  YouTube Short:  {research.content_angles.youtube_short}",
#         f"  YouTube Long:   {research.content_angles.youtube_long}",
#         f"  Blog:           {research.content_angles.blog}",
#         f"  LinkedIn:       {research.content_angles.linkedin}",
#         f"  Twitter Thread: {research.content_angles.twitter_thread}",
#         f"  Newsletter:     {research.content_angles.newsletter}",
#         "",
#         "AUDIENCE INSIGHTS:",
#         f"  Cultural context: {research.audience_insights.cultural_context}",
#         "  Pain points:",
#         *[f"    - {p}" for p in research.audience_insights.primary_pain_points],
#         "  Common questions:",
#         *[f"    - {q}" for q in research.audience_insights.common_questions],
#     ]

#     if research.reliable_sources:
#         lines += [
#             "",
#             "RELIABLE SOURCES:",
#             *[f"  [{rs.type}] {rs.name} — {rs.relevance}" for rs in research.reliable_sources],
#         ]

#     if research.has_risks:
#         lines += [
#             "",
#             "⚠️  RISK FLAGS:",
#             *[f"  [{rf.risk_type}] {rf.description} | Mitigation: {rf.mitigation}" for rf in research.risk_flags],
#         ]

#     if research.content_warnings:
#         lines += [
#             "",
#             "CONTENT WARNINGS:",
#             *[f"  - {w}" for w in research.content_warnings],
#         ]

#     return "\n".join(lines)

def research_to_context(research: ResearchResult) -> str:
    """
    Rich context for documentary writers.

    Deliberately split into:
        1. Engagement
        2. Core Facts
        3. Visual Context

    This mirrors how documentary writers naturally think.
    """

    lines: list[str] = []

    # ------------------------------------------------------------------
    # ENGAGEMENT
    # ------------------------------------------------------------------

    lines += [
        "# ENGAGEMENT",
        "",
        f"TOPIC: {research.topic}",
        f"PLATFORM: {research.platform}",
        f"TONE: {research.tone}",
        "",
        "EXECUTIVE SUMMARY:",
        research.executive_summary,
        "",
    ]

    if research.emotional_angles:
        lines.append("EMOTIONAL ANGLES:")
        for angle in research.emotional_angles:
            lines.append(f"- {angle.angle}: {angle.description}")
            if angle.example_hook:
                lines.append(f"  Example: {angle.example_hook}")
        lines.append("")

    if research.hook_opportunities:
        lines.append("BEST HOOKS:")
        for hook in sorted(
            research.hook_opportunities,
            key=lambda h: h.strength,
            reverse=True,
        )[:8]:
            lines.append(f"- ({hook.strength:.1f}) {hook.hook}")
        lines.append("")

    # ------------------------------------------------------------------
    # CORE FACTS
    # ------------------------------------------------------------------

    lines += [
        "# CORE FACTS",
        "",
        "KEY FACTS:",
        *[f"- {x}" for x in research.key_facts],
        "",
    ]

    if research.timeline:
        lines += [
            "TIMELINE:",
            *[f"- {x}" for x in research.timeline],
            "",
        ]

    if research.interesting_stats:
        lines += [
            "IMPORTANT NUMBERS:",
            *[f"- {x}" for x in research.interesting_stats],
            "",
        ]

    if research.surprising_facts:
        lines += [
            "SURPRISING FACTS:",
            *[f"- {x}" for x in research.surprising_facts],
            "",
        ]

    if research.misconceptions:
        lines += [
            "COMMON MISCONCEPTIONS:",
            *[f"- {x}" for x in research.misconceptions],
            "",
        ]

    if research.reliable_sources:
        lines += [
            "RELIABLE SOURCES:",
            *[
                f"- [{s.type}] {s.name}: {s.relevance}"
                for s in research.reliable_sources
            ],
            "",
        ]

    # ------------------------------------------------------------------
    # VISUAL CONTEXT
    # ------------------------------------------------------------------

    lines += [
        "# VISUAL CONTEXT",
        "",
    ]

    if research.visual_opportunities:
        lines.append("VISUAL OPPORTUNITIES:")

        for visual in research.visual_opportunities:
            lines.append(
                f"- [{visual.visual_type}] {visual.concept}"
            )

            if visual.description:
                lines.append(
                    f"  Description: {visual.description}"
                )

            if visual.scene_moment:
                lines.append(
                    f"  Best used: {visual.scene_moment}"
                )

        lines.append("")

    if research.has_risks:
        lines += [
            "FACTUAL CAUTIONS:",
            *[
                f"- {r.description} | {r.mitigation}"
                for r in research.risk_flags
            ],
            "",
        ]

    return "\n".join(lines)

def research_hooks_summary(research: ResearchResult) -> str:
    """
    Return a compact hooks block for Title Agent and Thumbnail Agent prompts.

    Includes both structured hooks (with scores) and plain suggested angles.
    """
    parts: list[str] = []

    if research.hook_opportunities:
        top = sorted(research.hook_opportunities, key=lambda h: h.strength, reverse=True)[:8]
        parts.append("TOP HOOKS (by engagement score):")
        for h in top:
            parts.append(f"  [{h.angle} | {h.strength:.1f}] {h.hook}")

    if research.suggested_hook_angles:
        parts.append("\nADDITIONAL HOOK ANGLES:")
        parts.extend(f"  - {a}" for a in research.suggested_hook_angles[:5])

    return "\n".join(parts)


def research_risks_summary(research: ResearchResult) -> str:
    """
    Return a formatted risk summary for agents that must be risk-aware.
    Returns empty string if no risks exist.
    """
    if not research.has_risks:
        return ""

    lines = ["⚠️  CONTENT RISK FLAGS — Handle carefully:"]
    for rf in research.risk_flags:
        lines.append(f"  [{rf.risk_type.upper()}] {rf.description}")
        if rf.mitigation:
            lines.append(f"    ↳ Mitigation: {rf.mitigation}")

    if research.content_warnings:
        lines.append("\nCONTENT WARNINGS:")
        lines.extend(f"  - {w}" for w in research.content_warnings)

    return "\n".join(lines)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _tokens_for_duration(duration: int, module: str) -> int:
    """
    Scale max_tokens with target duration AND module size — each module is
    far smaller than the old monolithic call, so budgets are correspondingly
    smaller. Capped well under Mistral free-tier's 4096 output limit even at
    the largest duration tier.
    """
    base = {"core": 1200, "engagement": 1600, "visual": 1600}[module]
    if duration <= 60:
        scale = 1.0
    elif duration <= 300:
        scale = 1.3
    else:
        scale = 1.6
    return min(3800, round(base * scale))

def _validate_and_repair(raw: dict, *, topic: str, platform: str, tone: str) -> ResearchResult:
    """
    Validate raw dict against ResearchResult schema.

    Repair strategy
    ---------------
    Rather than failing immediately on partial output from the AI, we apply
    targeted repairs so that downstream agents always receive a usable object:

    1.  Ensure 'topic', 'platform', 'tone' are always set.
    2.  Coerce legacy string lists into structured sub-models where possible.
    3.  Back-fill 'suggested_hook_angles' from hook_opportunities if empty.
    4.  Log warnings for every repair performed so issues are visible in logs.

    Only if Pydantic validation still fails after repairs do we raise.
    """
    # 1. Anchor identity fields
    raw.setdefault("topic",    topic)
    raw.setdefault("platform", platform)
    raw.setdefault("tone",     tone)

    # 2. Coerce emotional_angles: list[str] → list[dict]
    raw_angles = raw.get("emotional_angles", [])
    if raw_angles and isinstance(raw_angles[0], str):
        logger.warning("Repairing emotional_angles: coercing list[str] → list[dict]")
        raw["emotional_angles"] = [
            {"angle": "curiosity", "description": s, "example_hook": ""}
            for s in raw_angles
        ]

    # 3. Coerce visual_opportunities: list[str] → list[dict]
    raw_visuals = raw.get("visual_opportunities", [])
    if raw_visuals and isinstance(raw_visuals[0], str):
        logger.warning("Repairing visual_opportunities: coercing list[str] → list[dict]")
        raw["visual_opportunities"] = [
            {"concept": s, "visual_type": "ai_image", "description": s, "scene_moment": ""}
            for s in raw_visuals
        ]

    # 4. Coerce related_topics: list[str] → list[dict]
    raw_related = raw.get("related_topics", [])
    if raw_related and isinstance(raw_related[0], str):
        logger.warning("Repairing related_topics: coercing list[str] → list[dict]")
        raw["related_topics"] = [
            {"topic": s, "relevance": "", "content_angle": ""}
            for s in raw_related
        ]

    # 5. Coerce reliable_sources: list[str] → list[dict]
    raw_sources = raw.get("reliable_sources", [])
    if raw_sources and isinstance(raw_sources[0], str):
        logger.warning("Repairing reliable_sources: coercing list[str] → list[dict]")
        raw["reliable_sources"] = [
            {"name": s, "type": "news", "relevance": ""}
            for s in raw_sources
        ]

    # 6. Coerce risk_flags: list[str] → list[dict]
    raw_risks = raw.get("risk_flags", [])
    if raw_risks and isinstance(raw_risks[0], str):
        logger.warning("Repairing risk_flags: coercing list[str] → list[dict]")
        raw["risk_flags"] = [
            {"risk_type": "sensitive_content", "description": s, "mitigation": ""}
            for s in raw_risks
        ]

    # 7. Back-fill suggested_hook_angles from hook_opportunities
    if not raw.get("suggested_hook_angles") and raw.get("hook_opportunities"):
        hooks = raw["hook_opportunities"]
        raw["suggested_hook_angles"] = [
            h["hook"] if isinstance(h, dict) else str(h)
            for h in hooks[:8]
        ]
        logger.debug("Back-filled suggested_hook_angles from hook_opportunities")

    # 8. Ensure content_angles is a dict (not missing)
    if not raw.get("content_angles"):
        raw["content_angles"] = {}

    # 9. Ensure audience_insights is a dict (not missing)
    if not raw.get("audience_insights"):
        raw["audience_insights"] = {}

    # 10. Validate
    try:
        result = ResearchResult.model_validate(raw)
        logger.info(
            "Research validated | key_facts=%d hooks=%d visuals=%d risks=%d",
            len(result.key_facts),
            len(result.hook_opportunities),
            len(result.visual_opportunities),
            len(result.risk_flags),
        )
        return result

    except Exception as exc:
        logger.error(
            "ResearchResult validation failed after repair attempts: %s | raw keys: %s",
            exc,
            list(raw.keys()),
        )
        raise ValidationError(
            f"ResearchResult validation failed: {exc}",
            raw=json.dumps(raw)[:600],
        ) from exc
