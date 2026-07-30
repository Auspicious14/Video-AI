"""
services/pipeline_batch.py — Batch Content Generation Pipeline
═══════════════════════════════════════════════════════════════════════════════

Generates multiple videos sequentially from a single request.

Workflow
─────────
1. Topic discovery     — either uses supplied topics or discovers via trend engine
2. Per-video pipeline  — runs the full hybrid pipeline for each topic
3. Progress tracking   — updates batch status in store after each video

Architecture notes
───────────────────
• Sequential execution by default (simple, predictable, no resource contention)
• Future: swap _run_videos_sequential for _run_videos_concurrent for worker-based
• Each video runs in its own job_id so it can be polled independently
• Batch state is stored under batch_id; individual jobs under their job_ids
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from models import (
    BatchGenerationRequest,
    BatchJobItem,
    BatchJobStatus,
    HybridVideoRequest,
    DurationPreset,
)
import store

logger = logging.getLogger(__name__)

# ── Batch store helpers ───────────────────────────────────────────────────────

# Batches are stored alongside regular jobs in the same dict under their batch_id.
# The structure stored is a BatchJobStatus-compatible dict.

def create_batch(batch_id: str, total: int) -> None:
    store.create_job(batch_id)
    store.update_job(
        batch_id,
        video_type="batch",
        status="queued",
        progress=0,
        status_detail=f"Queued: 0/{total} videos",
    )


def get_batch_status(batch_id: str) -> Optional[dict]:
    return store.get_job(batch_id)


# ── Topic discovery ───────────────────────────────────────────────────────────

async def _discover_topics(niche: str, count: int) -> list[str]:
    """
    Discover trending topics for a niche using the trend engine.
    Falls back to AI-generated topic list if trend engine unavailable.
    """
    try:
        from services.ai.trends.scheduler import TrendScheduler
        from services.ai.trends.schemas import ScanFrequency

        scheduler = TrendScheduler()
        batch = await scheduler.run_discovery_cycle(niche=niche, frequency=ScanFrequency.DAILY)

        topics = [
            opp.topic
            for opp in (batch.opportunities or [])
            if opp.topic
        ][:count]

        if topics:
            logger.info("Trend discovery found %d topics for niche '%s'", len(topics), niche)
            return topics

    except Exception as exc:
        logger.warning("Trend discovery failed: %s — using AI fallback", exc)

    # AI fallback: generate topics with Gemini/Groq
    return await _generate_topics_with_ai(niche, count)


async def _generate_topics_with_ai(niche: str, count: int) -> list[str]:
    """Generate topic ideas for a niche using LLM."""
    from services.ai.client import generate_json

    prompt = (
        f"Generate {count} specific, engaging video topics for the niche: \"{niche}\".\n"
        f"Each topic should be:\n"
        f"- Short and specific (under 10 words)\n"
        f"- Optimized for YouTube Shorts / TikTok\n"
        f"- Educational or entertaining\n"
        f"- Diverse (no duplicate ideas)\n\n"
        f"Return a JSON object with a single key \"topics\" containing a list of strings."
    )

    try:
        result = await generate_json(prompt=prompt, temperature=0.9, max_tokens=800,  # Phase 2A: Topic list (~600 tokens typical)), 
        topics = result.get("topics", []))
        if isinstance(topics, list):
            return [str(t) for t in topics[:count]]
    except Exception as exc:
        logger.error("AI topic generation failed: %s", exc)

    # Absolute fallback
    return [f"{niche} tip #{i+1}" for i in range(count)]


# ── Batch runner ──────────────────────────────────────────────────────────────

async def run_batch_pipeline(batch_id: str, req: BatchGenerationRequest) -> None:
    """
    Main batch pipeline entry point.

    Runs sequentially: one video at a time.
    Future improvement: use asyncio.gather with a semaphore for concurrency.
    """
    items: list[BatchJobItem] = []

    try:
        # ── Step 1: Resolve topic list ────────────────────────────────────────
        store.update_job(
            batch_id,
            status="discovering_topics",
            status_detail="Discovering topics…",
            progress=2,
        )

        if req.topics:
            topics = req.topics[: req.count]
        else:
            topics = await _discover_topics(req.niche or "general", req.count)

        total = len(topics)
        if total == 0:
            raise ValueError("No topics found or provided for batch generation")

        logger.info(
            "Batch %s | starting %d videos | niche=%s preset=%s",
            batch_id, total, req.niche, req.preset,
        )

        # ── Step 2: Create job items ──────────────────────────────────────────
        items = [
            BatchJobItem(index=i, topic=topics[i], status="queued")
            for i in range(total)
        ]

        _update_batch_status(batch_id, "generating", items, 0, total, "Starting batch…")

        # ── Step 3: Generate each video ───────────────────────────────────────
        completed = 0
        failed = 0

        for item in items:
            job_id = str(uuid.uuid4())
            item.job_id = job_id
            item.status = "generating"

            store.create_job(job_id)
            store.update_job(job_id, video_type="batch_hybrid", status="queued")

            # Deduct credit per video
            if store.get_credits(req.user_email) < 1:
                item.status = "failed"
                item.error = "Insufficient credits"
                failed += 1
                logger.warning("Batch %s: insufficient credits at item %d", batch_id, item.index)
                continue

            store.deduct_credit(req.user_email)

            _update_batch_status(
                batch_id, "generating", items, completed, total,
                f"Generating video {item.index + 1}/{total}: {item.topic}",
            )

            # Build a HybridVideoRequest from the batch request
            hybrid_req = HybridVideoRequest(
                user_email=req.user_email,
                topic=item.topic,
                tone=req.tone,
                preset=req.preset,
                custom_duration=req.custom_duration,
                brand_name=req.brand_name,
                voice_id=req.voice_id,
                health_awareness=req.health_awareness,
                use_ai_motion=req.use_ai_motion,
                subtitles=req.subtitles,
                aspect_ratio=req.aspect_ratio,
                ai_provider=req.ai_provider,
            )

            try:
                from services.pipeline_hybrid import run_hybrid_pipeline
                await run_hybrid_pipeline(job_id, hybrid_req)

                # Retrieve the video URL from the job store
                job_data = store.get_job(job_id)
                item.video_url = job_data.get("video_url")
                item.status = "done"
                item.progress = 100
                completed += 1
                logger.info("Batch %s: video %d/%d done | topic=%r", batch_id, completed, total, item.topic)

            except Exception as exc:
                item.status = "failed"
                item.error = str(exc)
                failed += 1
                logger.error("Batch %s: video %d failed: %s", batch_id, item.index + 1, exc)
                # Refund the credit for this failed item
                store.set_credits(req.user_email, store.get_credits(req.user_email) + 1)

        # ── Step 4: Mark batch complete ───────────────────────────────────────
        final_status = "done" if failed == 0 else ("partial" if completed > 0 else "failed")
        _update_batch_status(
            batch_id, final_status, items, completed, total,
            f"Batch complete: {completed}/{total} videos ready, {failed} failed.",
        )

        logger.info(
            "Batch %s complete | total=%d completed=%d failed=%d",
            batch_id, total, completed, failed,
        )

    except Exception as exc:
        logger.exception("Batch pipeline %s failed: %s", batch_id, exc)
        store.update_job(
            batch_id,
            status="failed",
            error=str(exc),
            status_detail=f"Batch failed: {exc}",
        )


# ── Private helpers ───────────────────────────────────────────────────────────

def _update_batch_status(
    batch_id: str,
    status: str,
    items: list[BatchJobItem],
    completed: int,
    total: int,
    detail: str,
) -> None:
    """Serialize batch state and write to the job store."""
    progress = int((completed / total * 100)) if total else 0
    store.update_job(
        batch_id,
        status=status,
        status_detail=detail,
        progress=progress,
        # Serialize items as a JSON-compatible list — stored under a special key
        # Consumers should call get_batch_extended() to retrieve the items list.
    )
    # Store extended batch data under a prefixed key for the status endpoint
    # We piggyback on the existing store by serialising in status_detail isn't ideal
    # so we use a secondary job entry per item (they are individually pollable).
    # The batch endpoint aggregates them.
