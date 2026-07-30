"""
tests/test_trends.py — Unit Tests for the YouTube Intelligence & Trend Discovery Engine
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai.trends.schemas import (
    TrendCandidate,
    TopicOpportunity,
    ScoreBreakdown,
    ScanFrequency,
    OpportunityTier,
    TrendSource
)
from services.ai.trends.discovery import DiscoveryEngine, SimulationTrendsProvider
from services.ai.trends.clustering import cluster_candidates, calculate_jaccard_similarity
from services.ai.trends.deduplicator import deduplicate_and_enrich, _make_slug
from services.ai.trends.scorer import evaluate_and_score, calculate_recency_score
from services.ai.trends.ranking import rank_and_group_trends
from services.ai.trends.scheduler import TrendScheduler
from services.pipeline_trends import run_trend_pipeline
from models import HybridVideoRequest


class TestTrendDiscoveryEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.raw_signals = [
            TrendCandidate(
                title="OpenAI announces GPT-6 leaks online",
                summary="A massive leak reveals details of OpenAI's GPT-6 specs.",
                source=TrendSource.REDDIT,
                source_url="https://reddit.com/r/technology/123",
                niche="ai_tools",
                raw_score=90.0,
                engagement=4000
            ),
            TrendCandidate(
                title="OpenAI leaks GPT-6 online during test",
                summary="Reports suggest GPT-6 got leaked online.",
                source=TrendSource.HACKER_NEWS,
                source_url="https://news.ycombinator.com/item?id=456",
                niche="ai_tools",
                raw_score=95.0,
                engagement=6000
            ),
            TrendCandidate(
                title="Vite 7 release boosts server hot replacement",
                summary="Vite 7.0 release candidate is out with performance gains.",
                source=TrendSource.GITHUB,
                source_url="https://github.com/vitejs/vite",
                niche="tech",
                raw_score=75.0,
                engagement=2000
            )
        ]

    def test_jaccard_similarity_calculations(self) -> None:
        """Verify title token intersections compute correct coefficients."""
        s1 = "OpenAI releases GPT-6 with agentic features"
        s2 = "GPT-6 released by OpenAI today"
        s3 = "Apple releases new iPad Pro details"
        
        sim_gpt = calculate_jaccard_similarity(s1, s2)
        sim_apple = calculate_jaccard_similarity(s1, s3)
        
        # GPT-6 titles should have much higher similarity than Apple titles
        self.assertGreater(sim_gpt, sim_apple)
        self.assertGreater(sim_gpt, 0.2)

    def test_clustering_groups_matching_topics(self) -> None:
        """Verify clustering engine groups similar titles and separates others."""
        clusters = cluster_candidates(self.raw_signals, threshold=0.25)
        
        # Result should result in 2 clusters: GPT-6 cluster (2 items), Vite cluster (1 item)
        self.assertEqual(len(clusters), 2)
        # Verify sizes
        sizes = [len(c) for c in clusters]
        self.assertIn(2, sizes)
        self.assertIn(1, sizes)

    @patch("services.ai.trends.deduplicator.generate_json", new_callable=AsyncMock)
    async def test_deduplicator_enrichment(self, mock_generate_json: AsyncMock) -> None:
        """Verify deduplicator unifies clusters and enriches via mock LLMs."""
        mock_generate_json.return_value = {
            "title": "OpenAI Launches GPT-6",
            "summary": "GPT-6 is officially here with massive upgrades.",
            "why_it_matters": "Changes automation workflows.",
            "target_audience": "Developers & founders",
            "suggested_hook": "GPT-6 is finally here.",
            "recommended_duration": 30,
            "recommended_platform": "tiktok",
            "visual_assessment": {
                "overall_score": 0.9,
                "available_types": ["screenshot", "video"],
                "notes": "Good B-roll."
            },
            "content_angles": [],
            "related_topics": []
        }
        
        gpt_cluster = [self.raw_signals[0], self.raw_signals[1]]
        opp = await deduplicate_and_enrich(gpt_cluster, "ai_tools")
        
        self.assertEqual(opp.title, "OpenAI Launches GPT-6")
        self.assertEqual(opp.slug, _make_slug("OpenAI Launches GPT-6"))
        self.assertEqual(opp.cluster_size, 2)
        self.assertIn(TrendSource.REDDIT, opp.sources)
        self.assertIn(TrendSource.HACKER_NEWS, opp.sources)

    def test_scorer_computes_score_weights(self) -> None:
        """Verify the scoring breakdown computes weighted averages correctly."""
        gpt_cluster = [self.raw_signals[0], self.raw_signals[1]]
        opp = TopicOpportunity(
            title="OpenAI Launches GPT-6",
            niche="ai_tools",
            summary="Test summary",
            sources=[TrendSource.REDDIT],
            cluster_size=2
        )
        
        scored_opp = evaluate_and_score(opp, gpt_cluster)
        
        self.assertGreater(scored_opp.score, 0.0)
        self.assertLessEqual(scored_opp.score, 100.0)
        self.assertIsNotNone(scored_opp.tier)

    def test_ranking_and_dashboard_grouping(self) -> None:
        """Verify grouping maps opportunities into correct dashboard categories."""
        opp_today = TopicOpportunity(
            id="today_opt",
            title="Today Tech News",
            niche="tech",
            score=82.0,
            discovered_at=datetime.utcnow() - timedelta(hours=2)
        )
        opp_evergreen = TopicOpportunity(
            id="evergreen_opt",
            title="How to learn Rust",
            niche="tech",
            score=72.0,
            discovered_at=datetime.utcnow() - timedelta(days=2),
            score_breakdown=ScoreBreakdown(evergreen_potential=9.0)
        )
        opp_week = TopicOpportunity(
            id="week_opt",
            title="GitHub Actions Leak",
            niche="tech",
            score=65.0,
            discovered_at=datetime.utcnow() - timedelta(days=3)
        )
        
        dashboard = rank_and_group_trends([opp_today, opp_evergreen, opp_week])
        
        self.assertEqual(len(dashboard.top_today), 1)
        self.assertEqual(dashboard.top_today[0].title, "Today Tech News")
        
        self.assertEqual(len(dashboard.evergreen), 1)
        self.assertEqual(dashboard.evergreen[0].title, "How to learn Rust")
        
        self.assertEqual(len(dashboard.trending_this_week), 1)
        self.assertEqual(dashboard.trending_this_week[0].title, "GitHub Actions Leak")

    def test_scheduler_persists_trends(self) -> None:
        """Verify the TrendScheduler writes to and loads from the JSON database on disk."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "trends_db.json"
            
            scheduler = TrendScheduler(db_path=db_file)
            opp = TopicOpportunity(
                id="test_key",
                title="Space exploration trends",
                niche="space",
                score=80.0
            )
            
            scheduler.backlog["test_key"] = opp
            scheduler.scan_history.append({"batch_id": "batch_123"})
            scheduler._save_db()
            
            # Reload new scheduler instance using same file
            loader = TrendScheduler(db_path=db_file)
            self.assertIn("test_key", loader.backlog)
            self.assertEqual(loader.backlog["test_key"].title, "Space exploration trends")
            self.assertEqual(len(loader.scan_history), 1)

    @patch("services.pipeline_trends.run_hybrid_pipeline", new_callable=AsyncMock)
    @patch("services.ai.trends.scheduler.TrendScheduler.run_discovery_cycle", new_callable=AsyncMock)
    async def test_run_trend_pipeline_integration(
        self,
        mock_run_discovery: AsyncMock,
        mock_hybrid_pipeline: AsyncMock
    ) -> None:
        """Verify the main entry trend pipeline discovers top opportunity and runs hybrid flow."""
        req = HybridVideoRequest(
            user_email="test@video.ai",
            tone="educational",
            use_ai_motion=False,
            subtitles=True
        )
        
        opp = TopicOpportunity(
            id="trend_1",
            title="Discovered AI Agent News",
            niche="ai_tools",
            score=95.0,
            recommended_duration=30,
            recommended_platform="tiktok"
        )
        
        # Mock database setup
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "trends_db.json"
            with patch("services.pipeline_trends.TrendScheduler") as MockSchedulerClass:
                mock_sched_inst = MagicMock()
                mock_sched_inst.backlog = {}
                mock_sched_inst.get_dashboard_view.return_value = MagicMock(
                    top_today=[opp],
                    evergreen=[],
                    trending_this_week=[]
                )
                MockSchedulerClass.return_value = mock_sched_inst
                
                result_opp = await run_trend_pipeline(
                    job_id="job_trend_test",
                    niche="ai_tools",
                    req=req
                )
                
                # Check resulting opportunity
                self.assertEqual(result_opp.id, "trend_1")
                self.assertEqual(result_opp.title, "Discovered AI Agent News")
                
                # Verify request topic was overwritten
                self.assertEqual(req.topic, "Discovered AI Agent News")
                # Verify downstream pipeline was triggered
                mock_hybrid_pipeline.assert_called_once_with("job_trend_test", req)


if __name__ == "__main__":
    unittest.main()
