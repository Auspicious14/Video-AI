---
description: How to run, test, and extend the YouTube Intelligence & Trend Discovery Engine
---

# YouTube Intelligence & Trend Discovery Engine (v2)

This guide documents the architecture, data structures, scheduling loops, and extension guidelines for the YouTube Intelligence Engine implemented in the VideoAI platform.

## Pipeline Architecture

The engine shifts the VideoAI pipeline from a manual, creator-driven entry point to an automated, trend-aware recommendation workflow:

```text
Niche (e.g. AI Tools, Tech, Business)
  ↓
Trend Discovery (Hacker News, Reddit, GitHub, RSS Tech Blogs, Google Trends)
  ↓
Topic Clustering (Single-linkage Jaccard token-overlap grouping)
  ↓
Topic Deduplication (Binds matching clusters into Topic Opportunities)
  ↓
Opportunity Scoring & Ranking (Weighted evaluation across 12 dimensions)
  ↓
Pipeline Handoff (Overwrites request variables and runs standard v2 Flow)
  ↓
Research → Script → Media Acquisition → Render
```

---

## Directory Matrix

The module structure resides within `services/ai/trends/`:

- `schemas.py`: Pydantic contracts setting criteria for raw signals, content angles, sub-scores, opportunities, and dashboard aggregates.
- `discovery.py`: Pluggable source scanner managing live public APIs (Reddit hot list JSONs, Hacker News Algolia query nodes, TechCrunch XML RSS nodes, GitHub Star ranking queries) and zero-config simulated fallbacks.
- `clustering.py`: Token-overlap engine defining cluster groups without external heavyweight vector extensions.
- `deduplicator.py`: Combines clusters, resolves target titles, and calls the LLM (`trend_enricher.md`) to build initial hooks and outlines.
- `scorer.py`: Computes 12 sub-scores (0–10) including novelty, search interest, ever green potential, thumbnail suitability, recency, storytelling depth, and visual availability. Uses weights to compute a final `0-100` opportunity score.
- `ranking.py`: Groups scored topics into Top Today, Weekly Trends, and Evergreen buckets, filtering already covered topics to prevent fatigue.
- `scheduler.py`: Handles persistent JSON archiving on disk (`outputs/trends_db.json`) and checks frequency timestamps.
- `__init__.py`: Clean exports wrapper.

---

## Opportunities Schema Contract

Every opportunity exposes a detailed set of strategic content properties before video generation:

- `title`: Consolidated title (e.g. `"OpenAI releases GPT-6 with agentic thinking"`).
- `score`: Weighted opportunity popularity rank (0-100).
- `status`: State tracking (`new`, `in_progress`, `published`, `skipped`).
- `score_breakdown`: Key points ranking for novelty, competition, search interest, etc.
- `summary`: Context summary to guide the Research Agent.
- `why_it_matters`: Strategic audience interest reasons.
- `suggested_hook`: Compelling hook built by the enricher.
- `content_angles`: Enriched suggestion list with targeted hooks.
- `recommended_duration`: Optimal runtime in seconds.
- `recommended_platform`: Best fit platform (Tiktok, YouTube Shorts, YouTube Long).
- `visual_assessment`: Dict listing asset types (`screenshot`, `logo`, `stock_video`) and notes.

---

## Integration Entry Point

To trigger a trend-discovery augmented pipeline, invoke `run_trend_pipeline`:

```python
from models import HybridVideoRequest
from services.pipeline_trends import run_trend_pipeline

# Setup request config
req = HybridVideoRequest(
    user_email="creator@videoai.ng",
    tone="inspiring",
    use_ai_motion=True
)

# Run trend-aware generation on the 'ai_tools' niche
opportunity = await run_trend_pipeline(
    job_id="job_trending_01",
    niche="ai_tools",
    req=req
)

print(f"Discovered and generated video for: {opportunity.title} (Score: {opportunity.score})")
```

---

## Running Unit Tests

To run the unit tests for the Trend Engine and the Media Acquisition Engine, invoke:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
python -m unittest tests/test_trends.py -v
python -m unittest tests/test_media_acquisition.py -v
```
