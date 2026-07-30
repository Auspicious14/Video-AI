"""
services/ai/scripting.py — Script Agent

Responsibility
--------------
Transform a ResearchResult (or a bare topic) into a validated ScriptResult.

The Script Agent NEVER performs research.
All facts come from the ResearchResult passed in.

Usage
-----
    from services.ai.scripting import run_script_agent
    from services.ai.research import run_research

    research = await run_research(topic="...", tone="...", duration=30)
    script   = await run_script_agent(research=research, req=req)

Direct usage (without pre-computed research) is also supported for
backward-compatibility with existing pipelines that pass a bare TikTokRequest.
In that case, lightweight inline research is generated automatically.

Supported prompt templates
--------------------------
    "tiktok_script"   — short-form (TikTok/Reels)
    "youtube_script"  — long-form (YouTube)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from services.ai.client import generate_json
from services.ai.exceptions import ValidationError
from services.ai.prompts import load_prompt
from services.ai.research import research_to_summary, research_risks_summary, run_research
from services.ai.schemas import ResearchResult, Scene, ScriptResult

logger = logging.getLogger(__name__)

# Supported template identifiers
TEMPLATE_TIKTOK   = "tiktok_script"
TEMPLATE_YOUTUBE  = "youtube_script"

_HEALTH_CONTEXT = """
HEALTH AWARENESS MODE — Additional rules:
- Use empathetic, non-alarming language
- Show diverse Nigerian/African people of different ages
- Avoid medical jargon — use everyday language
- Never show graphic medical imagery
- End with ONE clear, calm action step
- Image prompts must show real everyday settings, not clinical stock imagery
- Emotional tone: concerned but hopeful, never fearful
"""


# ── Public API ─────────────────────────────────────────────────────────────────

async def run_script_agent(
    topic:            str,
    tone:             str   = "educational",
    duration:         int   = 30,
    brand_name:       Optional[str] = None,
    health_awareness: bool  = False,
    research:         Optional[ResearchResult] = None,
    template:         str   = TEMPLATE_TIKTOK,
    platform:         str   = "tiktok",
    audience_profile: str   = "",
) -> ScriptResult:
    """
    Generate a validated script from research.

    Parameters
    ----------
    topic:            Subject of the video.
    tone:             Desired tone (educational | urgent | empathetic | inspiring | conversational).
    duration:         Target video duration in seconds.
    brand_name:       Optional brand/app name to weave into the narration.
    health_awareness: Enables health-awareness constraints in the prompt.
    research:         Pre-computed ResearchResult. If None, research is run first.
    template:         Prompt template name: "tiktok_script" or "youtube_script".
    platform:         Target platform — passed to Research Agent for platform-aware research.
    audience_profile: Optional audience description — passed to Research Agent.

    Returns
    -------
    Validated ScriptResult.

    Raises
    ------
    ProviderError:   All providers failed.
    ValidationError: Response failed schema validation.
    """
    logger.info(
        "Script Agent starting | topic=%r tone=%s duration=%ds template=%s platform=%s",
        topic, tone, duration, template, platform,
    )

    # ── Research phase ────────────────────────────────────────────────────────
    if research is None:
        niche = _HEALTH_CONTEXT if health_awareness else ""
        research = await run_research(
            topic=topic,
            tone=tone,
            duration=duration,
            platform=platform,
            niche_context=niche,
            audience_profile=audience_profile,
        )

    research_summary = research_to_summary(research)

    # Append risk context so the script writer is aware of sensitivities
    risk_context = research_risks_summary(research)
    if risk_context:
        research_summary = research_summary + "\n\n" + risk_context

    # ── Derived constants ─────────────────────────────────────────────────────
    if duration <= 60:
        seconds_per_scene = 5
    elif duration <= 180:
        seconds_per_scene = 7
    elif duration <= 600:
        seconds_per_scene = 10
    else:
        seconds_per_scene = 12

    scene_count = max(4, round(duration / seconds_per_scene))
    avg_scene_duration = round(duration / scene_count, 1)
    word_target      = int(duration * 2.1)
    brand_line       = f"Mention the brand/app name naturally: {brand_name}." if brand_name else ""
    health_context   = _HEALTH_CONTEXT if health_awareness else ""

    # ── Build prompt ──────────────────────────────────────────────────────────
    system = load_prompt("base")
    prompt = load_prompt(
        template,
        topic=topic,
        tone=tone,
        duration=duration,
        scene_count=scene_count,
        avg_scene_duration=avg_scene_duration,
        word_target=word_target,
        brand_line=brand_line,
        health_context=health_context,
        research_summary=research_summary,
    )

    # ── AI call ───────────────────────────────────────────────────────────────
    raw: dict = await generate_json(
        prompt=prompt,
        system=system,
        temperature=0.78,
        max_tokens=4096,
    )

    # ── Validate & return ─────────────────────────────────────────────────────
    return _validate_script(raw, scene_count, avg_scene_duration)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _validate_script(
    raw: dict,
    expected_scene_count: int,
    default_scene_duration: float,
) -> ScriptResult:
    """
    Validate the raw dict against ScriptResult + repair minor issues.

    Repairs
    -------
    - Missing 'duration' on individual scenes → filled with default.
    - Missing 'caption' or 'cta' → filled with safe string fallback.
    - Wrong scene count is tolerated with a warning (Pydantic min_length=1 still applies).
    - Invalid emotion values → coerced to 'informative' by Scene.coerce_emotion().
    """
    # Fill missing top-level fields
    raw.setdefault("caption", "Check out this video! #fyp")
    raw.setdefault("cta", "Like and subscribe for more!")

    # Fill missing scene durations before validation
    for scene in raw.get("scenes", []):
        scene.setdefault("duration", default_scene_duration)

    # Warn if count differs from the prompt instruction
    actual_count = len(raw.get("scenes", []))
    if actual_count != expected_scene_count:
        logger.warning(
            "Scene count mismatch: expected=%d got=%d — accepting output",
            expected_scene_count,
            actual_count,
        )

    try:
        result = ScriptResult.model_validate(raw)
        logger.info(
            "Script validated | scenes=%d narration_words=%d",
            len(result.scenes),
            len(result.narration.split()),
        )
        return result
    except Exception as exc:
        logger.error("ScriptResult validation failed: %s | raw keys: %s", exc, list(raw.keys()))
        raise ValidationError(
            f"ScriptResult validation failed: {exc}",
            raw=json.dumps(raw)[:500],
        ) from exc
