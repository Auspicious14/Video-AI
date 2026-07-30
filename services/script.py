"""
services/script.py — Backward-compatibility shim

ALL script generation now goes through services/ai/scripting.py.

This module preserves the original function signature so existing
pipelines (pipeline.py, pipeline_hybrid.py, pipeline_avatar.py, etc.)
continue to work without modification during the transition period.

Migration path:
  Old: from services.script import generate_script
  New: from services.ai import run_script_agent

The shim will be removed in a future cleanup pass once all callers
have been updated to use the new agent interface directly.
"""

from __future__ import annotations

import logging

from models import TikTokRequest
from services.ai.scripting import run_script_agent

logger = logging.getLogger(__name__)


async def generate_script(req: TikTokRequest, health_awareness: bool = False) -> dict:
    """
    Backward-compatible wrapper around the new Script Agent.

    Accepts the original TikTokRequest and returns the legacy flat dict
    expected by existing pipeline code.

    The new Script Agent internally:
      1. Runs the Research Agent to gather topic insights.
      2. Builds a prompt from services/ai/prompts/tiktok_script.md.
      3. Calls the AI client (Groq → Gemini failover).
      4. Validates the response with Pydantic.
      5. Returns a validated ScriptResult.

    This shim converts that ScriptResult back to the dict format the
    existing pipelines expect (via ScriptResult.to_legacy_dict()).
    """
    logger.info(
        "generate_script (shim) | topic=%r tone=%s duration=%ds",
        req.topic, req.tone, req.duration,
    )

    result = await run_script_agent(
        topic=req.topic,
        tone=req.tone,
        duration=req.duration,
        brand_name=req.brand_name,
        health_awareness=health_awareness,
        research=None,          # Research Agent runs automatically
        template="tiktok_script",
    )

    return result.to_legacy_dict()