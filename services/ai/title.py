"""
services/ai/title.py — Title Agent

Generates multiple title candidates from a ResearchResult,
then selects the strongest one.

Usage
-----
    from services.ai.title import run_title_agent

    titles = await run_title_agent(
        research=research,
        topic="...",
        tone="educational",
        platform="youtube",
    )
    print(titles.best_title)
"""

from __future__ import annotations

import json
import logging

from services.ai.client import generate_json
from services.ai.exceptions import ValidationError
from services.ai.prompts import load_prompt
from services.ai.research import research_hooks_summary, research_to_summary
from services.ai.schemas import ResearchResult, TitleResult

logger = logging.getLogger(__name__)


async def run_title_agent(
    research:  ResearchResult,
    topic:     str,
    tone:      str  = "educational",
    platform:  str  = "youtube",
) -> TitleResult:
    """
    Generate video title suggestions grounded in pre-computed research.

    Parameters
    ----------
    research:   Pre-computed ResearchResult (mandatory).
    topic:      Video subject.
    tone:       Desired tone.
    platform:   "youtube" | "tiktok" | "youtube_shorts"

    Returns
    -------
    Validated TitleResult.
    """
    logger.info("Title Agent starting | topic=%r platform=%s", topic, platform)

    # Use the rich hook summary (includes strength scores) for better title generation
    hook_angles  = research_hooks_summary(research)
    research_summary = research_to_summary(research)

    system = load_prompt("base")
    prompt = load_prompt(
        "title",
        topic=topic,
        tone=tone,
        platform=platform,
        research_summary=research_summary,
        hook_angles=hook_angles,
    )

    raw: dict = await generate_json(
        prompt=prompt,
        system=system,
        temperature=0.7,
        max_tokens=200  # Phase 2A: Compact title list (~150 tokens typical),
    )

    try:
        result = TitleResult.model_validate(raw)
        logger.info("Title Agent done | candidates=%d best=%r", len(result.titles), result.best_title)
        return result
    except Exception as exc:
        raise ValidationError(
            f"TitleResult validation failed: {exc}",
            raw=json.dumps(raw)[:300],
        ) from exc
