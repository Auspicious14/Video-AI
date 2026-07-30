"""
services/ai/thumbnail.py — Thumbnail Agent

Generates thumbnail concepts and image prompts from a ResearchResult.

Usage
-----
    from services.ai.thumbnail import run_thumbnail_agent

    thumbnails = await run_thumbnail_agent(
        research=research,
        topic="...",
        tone="educational",
        hook="She thought it was normal pregnancy stress.",
    )
    print(thumbnails.best.image_prompt)
"""

from __future__ import annotations

import json
import logging

from services.ai.client import generate_json
from services.ai.exceptions import ValidationError
from services.ai.prompts import load_prompt
from services.ai.research import research_to_summary
from services.ai.schemas import ResearchResult, ThumbnailResult

logger = logging.getLogger(__name__)


async def run_thumbnail_agent(
    research: ResearchResult,
    topic:    str,
    tone:     str = "educational",
    hook:     str = "",
) -> ThumbnailResult:
    """
    Generate thumbnail concepts grounded in pre-computed research.

    Parameters
    ----------
    research:  Pre-computed ResearchResult (mandatory).
    topic:     Video subject.
    tone:      Desired tone.
    hook:      The video hook line — used to align thumbnail messaging.

    Returns
    -------
    Validated ThumbnailResult.
    """
    logger.info("Thumbnail Agent starting | topic=%r", topic)

    research_summary = research_to_summary(research)

    system = load_prompt("base")
    prompt = load_prompt(
        "thumbnail",
        topic=topic,
        tone=tone,
        hook=hook or topic,
        research_summary=research_summary,
    )

    raw: dict = await generate_json(
        prompt=prompt,
        system=system,
        temperature=0.75,
        max_tokens=300  # Phase 2A: Brief thumbnail concepts (~200 tokens typical),
    )

    try:
        result = ThumbnailResult.model_validate(raw)
        logger.info("Thumbnail Agent done | suggestions=%d", len(result.suggestions))
        return result
    except Exception as exc:
        raise ValidationError(
            f"ThumbnailResult validation failed: {exc}",
            raw=json.dumps(raw)[:300],
        ) from exc
