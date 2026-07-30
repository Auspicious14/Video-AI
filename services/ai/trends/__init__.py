"""
services/ai/trends — YouTube Intelligence & Trend Discovery Engine exports
"""

from __future__ import annotations

from services.ai.trends.schemas import (
    TrendSource,
    ScanFrequency,
    OpportunityTier,
    TrendCandidate,
    TopicOpportunity,
    DiscoveryBatch,
    DashboardView
)
from services.ai.trends.discovery import (
    TrendDiscoveryProvider,
    DiscoveryEngine
)
from services.ai.trends.clustering import cluster_candidates
from services.ai.trends.deduplicator import deduplicate_and_enrich
from services.ai.trends.scorer import evaluate_and_score
from services.ai.trends.ranking import rank_and_group_trends
from services.ai.trends.scheduler import TrendScheduler

__all__ = [
    "TrendSource",
    "ScanFrequency",
    "OpportunityTier",
    "TrendCandidate",
    "TopicOpportunity",
    "DiscoveryBatch",
    "DashboardView",
    "TrendDiscoveryProvider",
    "DiscoveryEngine",
    "cluster_candidates",
    "deduplicate_and_enrich",
    "evaluate_and_score",
    "rank_and_group_trends",
    "TrendScheduler",
]
