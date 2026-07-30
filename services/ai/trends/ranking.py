"""
services/ai/trends/ranking.py — Topic Ranking and Dashboard Formatting

Responsibility:
Sorts scored opportunities and organizes them into categorizations suitable
for the frontend dashboard (Top Today, Trending This Week, Evergreen, and Recently Covered)
while filtering duplicates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from services.ai.trends.schemas import TopicOpportunity, DashboardView

logger = logging.getLogger(__name__)


def rank_and_group_trends(
    opportunities: List[TopicOpportunity],
    published_titles: List[str] = None
) -> DashboardView:
    """
    Ranks similar opportunities by score, removes duplicates, and organizes them
    into Top Today, Trending This Week, Evergreen, and Recently Covered buckets.
    """
    if published_titles is None:
        published_titles = []

    published_set = {t.strip().lower() for t in published_titles}
    
    # 1. Filter out already covered topics
    fresh_opportunities: List[TopicOpportunity] = []
    recently_tracked: List[str] = [t for t in published_titles]
    
    for opp in opportunities:
        normal = opp.title.strip().lower()
        if normal in published_set or opp.status == "published":
            if opp.title not in recently_tracked:
                recently_tracked.append(opp.title)
        else:
            fresh_opportunities.append(opp)

    # Sort all fresh opportunities by score descending
    sorted_opps = sorted(fresh_opportunities, key=lambda o: o.score, reverse=True)

    now = datetime.utcnow()
    one_day_ago = now - timedelta(hours=24)
    one_week_ago = now - timedelta(days=7)

    top_today: List[TopicOpportunity] = []
    trending_this_week: List[TopicOpportunity] = []
    evergreen: List[TopicOpportunity] = []

    # Keep track of IDs we placed to avoid placing a topic in multiple categories
    placed_ids = set()

    # Category 1: Top Today (Discovered in last 24h, high score, prioritized)
    for opp in sorted_opps:
        # Check discovery time
        dis_time = opp.discovered_at.replace(tzinfo=None)
        if dis_time >= one_day_ago and opp.score >= 50.0:
            top_today.append(opp)
            placed_ids.add(opp.id)

    # Category 2: Evergreen (Evergreen potential score >= 7.5, not in top_today)
    for opp in sorted_opps:
        if opp.id in placed_ids:
            continue
        # Check evergreen potential
        sub_score = getattr(opp.score_breakdown, "evergreen_potential", 0.0)
        if sub_score >= 7.5:
            evergreen.append(opp)
            placed_ids.add(opp.id)

    # Category 3: Trending This Week (Discovered in last 7 days, not in top_today or evergreen)
    for opp in sorted_opps:
        if opp.id in placed_ids:
            continue
        dis_time = opp.discovered_at.replace(tzinfo=None)
        if dis_time >= one_week_ago:
            trending_this_week.append(opp)
            placed_ids.add(opp.id)

    # Cap categories to reasonable numbers (e.g., top 10 each)
    view = DashboardView(
        top_today=top_today[:10],
        trending_this_week=trending_this_week[:10],
        evergreen=evergreen[:10],
        recently_covered=recently_tracked[:10]
    )

    logger.info(
        "[Ranking] Grouped dashboard view: Today=%d | Week=%d | Evergreen=%d | Covered=%d",
        len(view.top_today), len(view.trending_this_week), len(view.evergreen), len(view.recently_covered)
    )

    return view
