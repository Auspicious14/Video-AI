"""
services/ai/seo.py — SEO Agent

Generates full SEO metadata (title, description, tags, hashtags) from
a ResearchResult and the generated script narration.

Usage
-----
    from services.ai.seo import run_seo_agent

    seo = await run_seo_agent(
        research=research,
        topic="...",
        tone="educational",
        narration_excerpt=script.narration[:200],
    )
    print(seo.title, seo.tags)
"""

from __future__ import annotations

import json
import logging

from services.ai.client import generate_json
from services.ai.exceptions import ValidationError
from services.ai.prompts import load_prompt
from services.ai.research import research_to_summary
from services.ai.schemas import ResearchResult, SEOResult

logger = logging.getLogger(__name__)


async def run_seo_agent(
    research:          ResearchResult | None = None,
    topic:             str = "",
    tone:              str = "educational",
    narration_excerpt: str = "",
    keywords:          list[str] | None = None,
    key_facts:         list[str] | None = None,
) -> SEOResult:
    """
    Generate SEO metadata grounded in research or minimal context.

    Supports two modes:
    1. Legacy: Pass full ResearchResult (deprecated)
    2. Optimized: Pass keywords + key_facts directly (70% token reduction)

    Parameters
    ----------
    research:          Pre-computed ResearchResult (optional, for backwards compatibility).
    topic:             Video subject.
    tone:              Desired tone.
    narration_excerpt: First 700 characters of the script narration for context.
    keywords:          Optional list of keywords (replaces research.search_keywords).
    key_facts:         Optional list of key facts (replaces research.key_facts).

    Returns
    -------
    Validated SEOResult.
    """
    logger.info("SEO Agent starting | topic=%r", topic)

    # Build research summary from either full research or minimal context
    if research:
        # Legacy mode: use full research
        research_summary = research_to_summary(research)
    else:
        # Optimized mode: build minimal summary from context
        if not keywords or not key_facts:
            raise ValueError("SEO agent requires either research OR (keywords + key_facts)")
        
        research_summary = "\n".join([
            f"TOPIC: {topic}",
            "",
            "KEY FACTS:",
            *[f"  - {fact}" for fact in key_facts[:5]],
            "",
            "KEYWORDS:",
            *[f"  - {kw}" for kw in keywords[:10]],
        ])

    system = load_prompt("base")
    prompt = load_prompt(
        "seo",
        topic=topic,
        tone=tone,
        narration_excerpt=narration_excerpt or topic,
        research_summary=research_summary,
    )

    raw: dict = await generate_json(
        prompt=prompt,
        system=system,
        temperature=0.4,
        max_tokens=900  # Phase 2A: Compact SEO metadata (~210 tokens typical),
    )

    try:
        result = SEOResult.model_validate(raw)
        logger.info(
            "SEO Agent done | tags=%d hashtags=%d",
            len(result.tags),
            len(result.hashtags),
        )
        return result
    except Exception as exc:
        raise ValidationError(
            f"SEOResult validation failed: {exc}",
            raw=json.dumps(raw)[:300],
        ) from exc
