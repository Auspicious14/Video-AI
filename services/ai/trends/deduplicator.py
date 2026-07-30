"""
services/ai/trends/deduplicator.py — Topic Deduplicator and Enricher

Responsibility:
Unifies clusters of raw candidate signals into singular high-quality TopicOpportunities.
Queries the AI client to enrich the topics with scripts/hooks/audiences and fallback
safely on LLM failure.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import List

from services.ai.client import generate_json
from services.ai.prompts import load_prompt
from services.ai.trends.schemas import (
    TrendCandidate,
    TopicOpportunity,
    ContentAngleSuggestion,
    VisualAssessment,
    ScoreBreakdown
)

logger = logging.getLogger(__name__)


def _make_slug(title: str) -> str:
    """Creates a URL-safe slug."""
    s = title.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[-\s]+", "-", s)


def _generate_deterministic_id(title: str) -> str:
    """Generates a stable unique hash identifier based on title."""
    h = hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()
    return h[:16]


def _choose_best_title(candidates: List[TrendCandidate]) -> str:
    """
    Selects the most descriptive title from a list of candidates.
    Prefers titles with balanced length (not too short, not extremely long sentence).
    """
    if not candidates:
        return ""
    # Sort candidates by length of title, filter out simple headers, pick middle-longest
    sorted_cand = sorted(candidates, key=lambda c: len(c.title))
    return sorted_cand[-1].title


def _build_local_fallback(
    title: str,
    niche: str,
    candidates: List[TrendCandidate]
) -> TopicOpportunity:
    """Builds a robust, default TopicOpportunity Locally if LLM fails."""
    summary = "Trending topic surfaced by search signals: " + " / ".join(c.title for c in candidates[:3])
    
    # Extract unique tags
    tags = set()
    for c in candidates:
        tags.update(c.tags)
        
    return TopicOpportunity(
        id=_generate_deterministic_id(title),
        title=title,
        slug=_make_slug(title),
        niche=niche,
        summary=summary,
        why_it_matters=f"This topic is trending across {len(candidates)} search nodes.",
        target_audience="General audience interested in " + niche,
        suggested_hook=f"Here is why everyone is talking about {title} today.",
        recommended_duration=30,
        recommended_platform="tiktok",
        visual_assessment=VisualAssessment(
            overall_score=0.8,
            available_types=["stock_video", "ai_image"],
            notes="Default fallback visual layout."
        ),
        content_angles=[
            ContentAngleSuggestion(
                angle="General overview",
                hook=f"Let's break down the news about {title}.",
                description="Core explanation.",
                strength=0.8
            )
        ],
        sources=list(set(c.source for c in candidates)),
        source_urls=list(set(c.source_url for c in candidates if c.source_url)),
        cluster_size=len(candidates)
    )


async def deduplicate_and_enrich(
    candidates: List[TrendCandidate],
    niche: str
) -> TopicOpportunity:
    """
    Processes a list/cluster of raw candidates. Picks the best title, 
    combines source info, and queries LLM to yield a rich TopicOpportunity.
    """
    if not candidates:
        raise ValueError("Cannot deduplicate empty candidate cluster.")

    best_title = _choose_best_title(candidates)
    logger.info("[Enricher] Selected best title: %r", best_title)

    # Compile context from candidates
    context_lines = []
    for idx, c in enumerate(candidates, 1):
        context_lines.append(
            f"Signal {idx} (Source: {c.source.value}):\n"
            f"- Title: {c.title}\n"
            f"- Summary: {c.summary}\n"
            f"- Engagement score/Metric: {c.engagement}\n"
        )
    context_dump = "\n".join(context_lines)

    try:
        system = load_prompt("base")
        prompt = load_prompt(
            "trend_enricher",
            niche=niche,
            title=best_title,
            context=context_dump
        )

        raw = await generate_json(
            prompt=prompt,
            system=system,
            temperature=0.4,
            max_tokens=1800  # Phase 2A: Enriched trend data (~1400 tokens typical)
        )

        # Merge raw facts retrieved from LLM with actual candidate provenance
        final_title = raw.get("title") or best_title
        opp_id = _generate_deterministic_id(final_title)
        slug = _make_slug(final_title)
        sources = list(set(c.source for c in candidates))
        source_urls = list(set(c.source_url for c in candidates if c.source_url))
        
        # Populate assessment
        raw_vis = raw.get("visual_assessment", {})
        visual_eval = VisualAssessment(
            overall_score=raw_vis.get("overall_score", 0.7),
            available_types=raw_vis.get("available_types", ["stock_video", "ai_image"]),
            notes=raw_vis.get("notes", "")
        )

        angles = []
        for a in raw.get("content_angles", []):
            angles.append(
                ContentAngleSuggestion(
                    angle=a.get("angle", "Alternative Perspective"),
                    hook=a.get("hook", ""),
                    description=a.get("description", ""),
                    strength=a.get("strength", 0.8)
                )
            )

        opp = TopicOpportunity(
            id=opp_id,
            title=final_title,
            slug=slug,
            niche=niche,
            summary=raw.get("summary", ""),
            why_it_matters=raw.get("why_it_matters", ""),
            target_audience=raw.get("target_audience", ""),
            suggested_hook=raw.get("suggested_hook", ""),
            recommended_duration=raw.get("recommended_duration", 30),
            recommended_platform=raw.get("recommended_platform", "tiktok"),
            visual_assessment=visual_eval,
            content_angles=angles,
            sources=sources,
            source_urls=source_urls,
            cluster_size=len(candidates),
            related_topics=raw.get("related_topics", [])
        )
        return opp

    except Exception as exc:
        logger.error("[Enricher] Enrichment failed for %r: %s. Using default fallback.", best_title, exc)
        return _build_local_fallback(best_title, niche, candidates)
