"""
services/ai/trends/scorer.py — Opportunity Scoring Engine

Responsibility:
Evaluates a TopicOpportunity using quantitative signal metrics (Reddit points, 
GitHub stars, HN points, cluster density, age) and qualitative elements (angles, 
visual types) to compute sub-scores for the 12 key dimensions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from services.ai.trends.schemas import (
    TrendCandidate,
    TopicOpportunity,
    ScoreBreakdown,
    OpportunityTier
)

logger = logging.getLogger(__name__)


def calculate_recency_score(candidates: List[TrendCandidate]) -> float:
    """Estimates recency score based on elapsed discovery time."""
    if not candidates:
        return 5.0
    now = datetime.utcnow()
    # Find newest candidate
    newest = max(c.discovered_at for c in candidates)
    diff = now - newest
    
    # Under 6 hours = 10/10, scales down over 72 hours
    if diff.total_seconds() < 6 * 3600:
        return 10.0
    elif diff.total_seconds() < 24 * 3600:
        return 8.0
    elif diff.total_seconds() < 48 * 3600:
        return 6.0
    elif diff.total_seconds() < 72 * 3600:
        return 4.0
    else:
        return 2.0


def calculate_organic_interest_score(candidates: List[TrendCandidate]) -> float:
    """Calculates search interest / organic popularity based on raw candidate metrics."""
    if not candidates:
        return 5.0
    # Average of normalized raw candidate scores
    avg_raw = sum(c.raw_score for c in candidates) / len(candidates)
    # Density boost for multiple sources reporting the same thing
    density_bonus = min(2.0, (len(candidates) - 1) * 0.5)
    return min(10.0, (avg_raw / 10.0) + density_bonus)


def evaluate_and_score(
    opportunity: TopicOpportunity,
    candidates: List[TrendCandidate]
) -> TopicOpportunity:
    """
    Evaluates and scores a TopicOpportunity.
    Populates score_breakdown, calculates the final weighted score, and sets the quality tier.
    """
    logger.info("[Scorer] Scoring topic opportunity: %r", opportunity.title)

    # 1. Recency
    recency = calculate_recency_score(candidates)

    # 2. Search Interest / Signal density
    search_interest = calculate_organic_interest_score(candidates)

    # 3. Novelty
    # AI/Leaks are highly novel. We scan for news terms
    novelty = 6.0
    title_lower = opportunity.title.lower()
    if any(k in title_lower for k in ("leak", "gpt-6", "released", "announced", "launch", "breakthrough", "introducing")):
        novelty = 9.0
    elif any(k in title_lower for k in ("guide", "tutorial", "how to", "best practice")):
        novelty = 5.0  # Evergreen but less novel

    # 4. Audience Curiosity
    audience_curiosity = min(10.0, search_interest * 1.1)

    # 5. Educational Value
    educational_value = 8.5 if opportunity.niche in ("ai_tools", "tech", "business") else 7.0
    if "how to" in title_lower or "guide" in title_lower or "explain" in title_lower:
        educational_value = 9.5

    # 6. Emotional Impact
    # Leaks, replacements, job loss, or huge updates have higher impact
    emotional_impact = 6.0
    if any(k in title_lower for k in ("replace", "kill", "threaten", "leak", "secrets", "warning", "shock")):
        emotional_impact = 9.0

    # 7. Evergreen Potential
    # Direct news items have low evergreen score, tutorial tutorials have high
    evergreen_potential = 7.0
    if any(k in title_lower for k in ("leak", "today", "yesterday", "announced", "latest")):
        evergreen_potential = 3.0
    elif any(k in title_lower for k in ("guide", "architecture", "concepts", "fundamentals", "history")):
        evergreen_potential = 9.0

    # 8. Competition
    # High-density reporting might mean higher competition (deduct slightly from score)
    competition = max(1.0, min(10.0, float(len(candidates)) * 1.5))

    # 9. Storytelling Potential
    storytelling = 7.0
    if len(opportunity.content_angles) >= 2:
        storytelling = min(10.0, 6.0 + len(opportunity.content_angles))

    # 10. Thumbnail Potential
    thumbnail_potential = 7.5
    if len(opportunity.visual_assessment.available_types) >= 3:
        thumbnail_potential = 9.0

    # 11. Hook Potential
    hook_potential = 8.0
    if opportunity.suggested_hook:
        hook_potential = 9.0

    # 12. Visual Potential
    visual_potential = min(10.0, float(len(opportunity.visual_assessment.available_types)) * 2.0)

    # Combine into Breakdown Pydantic model
    breakdown = ScoreBreakdown(
        novelty=novelty,
        search_interest=search_interest,
        audience_curiosity=audience_curiosity,
        educational_value=educational_value,
        emotional_impact=emotional_impact,
        evergreen_potential=evergreen_potential,
        competition=competition,
        recency=recency,
        storytelling=storytelling,
        thumbnail_potential=thumbnail_potential,
        hook_potential=hook_potential,
        visual_potential=visual_potential
    )

    final_score = breakdown.weighted_total
    
    # Assign tier
    if final_score >= 90.0:
        tier = OpportunityTier.PLATINUM
    elif final_score >= 75.0:
        tier = OpportunityTier.GOLD
    elif final_score >= 60.0:
        tier = OpportunityTier.SILVER
    elif final_score >= 40.0:
        tier = OpportunityTier.BRONZE
    else:
        tier = OpportunityTier.LOW

    opportunity.score_breakdown = breakdown
    opportunity.score = final_score
    opportunity.tier = tier

    logger.info(
        "[Scorer] Complete: score=%.1f | tier=%s | cluster=%d",
        final_score, tier.value, opportunity.cluster_size
    )

    return opportunity
