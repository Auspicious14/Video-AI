"""
services/ai/prompts.py — Prompt loader and template renderer.

Prompt files live in services/ai/prompts/*.md
Variables are interpolated using Python str.format_map().

Usage
-----
    from services.ai.prompts import load_prompt

    system = load_prompt("base")
    user   = load_prompt("tiktok_script", topic="AI in Africa", duration=30)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any

from services.ai.exceptions import PromptError

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ── Internal helpers ──────────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def _read_template(name: str) -> str:
    """
    Load a prompt template from disk.

    Caches the raw file content so repeated calls within the same process
    do not hit the filesystem.

    Raises PromptError if the file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise PromptError(
            f"Prompt template not found: '{name}' (looked for {path})"
        )
    return path.read_text(encoding="utf-8")


def _safe_format(template: str, variables: dict[str, Any]) -> str:
    """
    Render a prompt template using str.format_map().

    Missing keys raise PromptError with a clear message listing which
    variables are required.

    Literal braces can be escaped as {{ and }}.
    """
    # Discover which keys the template uses
    formatter = Formatter()
    required_keys = {
        field_name
        for _, field_name, _, _ in formatter.parse(template)
        if field_name is not None
    }

    missing = required_keys - variables.keys()
    if missing:
        raise PromptError(
            f"Prompt template is missing variables: {sorted(missing)}"
        )

    try:
        return template.format_map(variables)
    except KeyError as exc:
        raise PromptError(f"Unexpected missing key in template: {exc}") from exc
    except Exception as exc:
        raise PromptError(f"Template rendering failed: {exc}") from exc


# ── Public API ─────────────────────────────────────────────────────────────────

def load_prompt(name: str, **variables: Any) -> str:
    """
    Load and render a prompt template.

    Parameters
    ----------
    name:       File stem inside services/ai/prompts/ (without .md).
    **variables: Key-value pairs for template interpolation.

    Returns
    -------
    Rendered prompt string, ready to send to the AI client.

    Raises
    ------
    PromptError: File not found, or missing variables.
    """
    template = _read_template(name)

    if not variables:
        return template

    rendered = _safe_format(template, variables)
    logger.debug("Loaded prompt '%s' with %d variables", name, len(variables))
    return rendered


def reload_prompts() -> None:
    """
    Clear the template cache so updated .md files are picked up
    without restarting the process. Useful in development.
    """
    _read_template.cache_clear()
    logger.info("Prompt cache cleared")
