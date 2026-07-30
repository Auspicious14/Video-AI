"""
services/ai/trends/scheduler.py — Periodic Scan Coordinator and Backlog Storage

Responsibility:
Loads/saves discovery backlogs to disk. Orchestrates the full trend discovery loop:
Fetch Candidates -> Cluster -> Deduplicate & Enrich -> Score -> Merge Backlog.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import OUTPUT_DIR
from services.ai.trends.schemas import (
    DiscoveryBatch,
    TopicOpportunity,
    ScanFrequency,
    DashboardView
)
from services.ai.trends.discovery import DiscoveryEngine
from services.ai.trends.clustering import cluster_candidates
from services.ai.trends.deduplicator import deduplicate_and_enrich
from services.ai.trends.scorer import evaluate_and_score
from services.ai.trends.ranking import rank_and_group_trends

logger = logging.getLogger(__name__)

DB_PATH = OUTPUT_DIR / "trends_db.json"


class TrendScheduler:
    """
    Orchestrates periodic trend scanning and maintains a persistent database backlog on disk.
    """
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.backlog: Dict[str, TopicOpportunity] = {}
        self.scan_history: List[Dict] = []
        self._load_db()

    def _load_db(self) -> None:
        """Loads repository state from JSON file."""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r") as f:
                    data = json.load(f)
                    
                # Parse backlog
                raw_backlog = data.get("backlog", {})
                for k, v in raw_backlog.items():
                    try:
                        self.backlog[k] = TopicOpportunity.model_validate(v)
                    except Exception as e:
                        logger.warning("[Scheduler] Failed parsing opportunity %s: %s", k, e)
                        
                # Parse history
                self.scan_history = data.get("scan_history", [])
            except Exception as e:
                logger.error("[Scheduler] Failed to load trends database: %s", e)

    def _save_db(self) -> None:
        """Saves current state to JSON file."""
        try:
            data = {
                "backlog": {k: v.model_dump(mode="json") for k, v in self.backlog.items()},
                "scan_history": self.scan_history
            }
            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("[Scheduler] Persisted trends database to %s", self.db_path)
        except Exception as e:
            logger.error("[Scheduler] Failed writing trends database: %s", e)

    async def run_discovery_cycle(
        self,
        niche: str = "general",
        frequency: ScanFrequency = ScanFrequency.DAILY,
        limit_per_source: int = 10
    ) -> DiscoveryBatch:
        """
        Executes a complete trend discovery lifecycle.
        Returns a DiscoveryBatch report and updates the database backlog.
        """
        logger.info(
            "[Scheduler] Initiating trend discovery: niche=%r, frequency=%s", 
            niche, frequency.value
        )
        
        batch = DiscoveryBatch(
            batch_id=f"batch_{int(datetime.utcnow().timestamp())}",
            niche=niche,
            frequency=frequency,
            started_at=datetime.utcnow()
        )

        try:
            # 1. Fetch
            engine = DiscoveryEngine()
            candidates = await engine.collect_all_candidates(niche, limit_per_source=limit_per_source)
            batch.candidates_found = len(candidates)

            # 2. Cluster
            clusters = cluster_candidates(candidates)

            # 3. Deduplicate, Enrich, and Score each cluster
            for cluster in clusters:
                try:
                    # Deduplicate into a single opportunity + enrich using LLM
                    opp = await deduplicate_and_enrich(cluster, niche)
                    
                    # Compute sub-scores & final scoring breakdown
                    opp = evaluate_and_score(opp, cluster)
                    
                    # Merge with existing backlog (avoid duplicates)
                    # If this topic already exists in history, preserve status but update metrics
                    existing = self.backlog.get(opp.id)
                    if existing:
                        opp.status = existing.status
                        opp.discovered_at = existing.discovered_at
                    
                    self.backlog[opp.id] = opp
                    batch.opportunities.append(opp)
                except Exception as ex:
                    logger.error("[Scheduler] Error processing cluster: %s", ex)
                    batch.errors.append(str(ex))

            batch.completed_at = datetime.utcnow()
            
            # Record cycle execution in logs/history
            self.scan_history.append({
                "batch_id": batch.batch_id,
                "niche": niche,
                "frequency": frequency.value,
                "timestamp": datetime.utcnow().isoformat(),
                "candidates_found": batch.candidates_found,
                "opportunities_generated": len(batch.opportunities)
            })
            
            self._save_db()

        except Exception as e:
            logger.error("[Scheduler] Global crop cycle failure: %s", e)
            batch.errors.append(f"Global scheduler error: {e}")
            batch.completed_at = datetime.utcnow()

        return batch

    def get_dashboard_view(self, niche: str = "general") -> DashboardView:
        """
        Returns the ranked and grouped trends matching a given niche.
        """
        niche_opps = [o for o in self.backlog.values() if o.niche == niche]
        
        # Pull recently covered/published titles
        published = [o.title for o in self.backlog.values() if o.status == "published"]
        
        return rank_and_group_trends(niche_opps, published_titles=published)

    def trigger_periodic_scan(
        self,
        frequency: ScanFrequency,
        niche: str = "general"
    ) -> bool:
        """
        Analyzes scan history to check if the periodic threshold (hourly, daily, weekly) 
        has elapsed. Returns True if a new scan must be triggered.
        """
        history_run = [h for h in self.scan_history if h.get("frequency") == frequency.value and h.get("niche") == niche]
        if not history_run:
            return True  # Never run before

        # Find the latest timestamp
        latest_str = max(h.get("timestamp") for h in history_run)
        latest_time = datetime.fromisoformat(latest_str)
        elapsed = datetime.utcnow() - latest_time

        if frequency == ScanFrequency.HOURLY:
            return elapsed.total_seconds() >= 3600
        elif frequency == ScanFrequency.DAILY:
            return elapsed.total_seconds() >= 24 * 3600
        elif frequency == ScanFrequency.WEEKLY:
            return elapsed.total_seconds() >= 7 * 24 * 3600

        return False
