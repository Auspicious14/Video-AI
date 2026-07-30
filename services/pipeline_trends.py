"""
services/pipeline_trends.py — Trend-Augmented VideoAI Pipeline

Responsibility:
Implements the v2 youtube trend discovery pipeline:
Niche -> Trend Discovery -> Topic Ranking -> Opportunity Scoring -> Research -> Script -> Media -> Render
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import store
from models import HybridVideoRequest
from services.ai.trends.scheduler import TrendScheduler
from services.ai.trends.schemas import ScanFrequency, TopicOpportunity
from services.pipeline_hybrid import run_hybrid_pipeline

logger = logging.getLogger(__name__)


async def run_trend_pipeline(
    job_id: str,
    niche: str,
    req: HybridVideoRequest
) -> TopicOpportunity:
    """
    Executes the trend-discovery augmented pipeline.
    
    1. Triggers Trend Discovery & Opportunity Scoring for the Niche.
    2. Selects the #1 Highest-Ranked Opportunity.
    3. Feeds that opportunity into the standard Research & Scripting pipeline.
    4. Acquires visual assets using the Media Engine.
    5. Renders the final video.
    """
    logger.info("Starting Trend-Augmented Pipeline for Job %s (Niche: %r)", job_id, niche)
    
    # ── 1. Trend Discovery & Scoring ──────────────────────────────────────────
    store.update_job(job_id, status="trend_discovery", progress=1)
    
    scheduler = TrendScheduler()
    
    # Check if we should trigger a new scan (e.g. if backlog has no items for the niche)
    dashboard = scheduler.get_dashboard_view(niche)
    need_scan = len(dashboard.top_today) == 0 and len(dashboard.evergreen) == 0
    
    if need_scan:
        logger.info("[Pipeline] No cached opportunities found for niche %r. Running discovery cycle...", niche)
        store.update_job(job_id, status_detail="Scanning trends for potential opportunities...")
        await scheduler.run_discovery_cycle(niche=niche, frequency=ScanFrequency.DAILY)
        dashboard = scheduler.get_dashboard_view(niche)

    # ── 2. Topic Ranking & Selection ──────────────────────────────────────────
    # Pick the absolute best opportunity (preferring Today, then Evergreen, then Trending)
    opportunities = dashboard.top_today + dashboard.evergreen + dashboard.trending_this_week
    
    if not opportunities:
        logger.warning("[Pipeline] No opportunities discovered for niche %r. Using general fallback.", niche)
        # Construct fallback opportunity
        fallback_title = f"The Future of {niche.replace('_', ' ').title()}"
        opp = TopicOpportunity(
            title=fallback_title,
            niche=niche,
            summary=f"Analysis of current developments in {niche}.",
            score=60.0,
            suggested_hook=f"Do you know where {niche} is headed next?",
        )
    else:
        # Pick the highest-scored opportunity
        opp = sorted(opportunities, key=lambda o: o.score, reverse=True)[0]
    
    logger.info("[Pipeline] Selected Topic Opportunity: %r (Score: %.1f)", opp.title, opp.score)
    store.update_job(
        job_id,
        status_detail=f"Discovered high-value trend: '{opp.title}' (Score: {opp.score})"
    )

    # Mark opportunity as in-progress/published so scheduler doesn't recommend it again
    opp.status = "published"
    scheduler.backlog[opp.id] = opp
    scheduler._save_db()

    # ── 3. Feed to Downstream Pipeline ────────────────────────────────────────
    # Bind discovered details to the request parameters
    req.topic = opp.title
    req.duration = opp.recommended_duration
    if hasattr(req, "platform"):
        setattr(req, "platform", opp.recommended_platform)
    
    logger.info("[Pipeline] Handoff to Hybrid Pipeline on: %r", req.topic)
    
    # Trigger Downstream: Research -> Script -> Media -> Render
    await run_hybrid_pipeline(job_id, req)
    
    return opp
