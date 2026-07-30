"""
services/motion_brief.py — Motion Brief Generator (refactored)

Generates a structured DesignBrief JSON from:
  - A text topic/prompt (sourceType: "prompt")
  - A flyer image uploaded by the user (sourceType: "flyer")

The brief is the single contract between Python and Remotion.

Refactored to use the new AI layer:
  - generate_json() in client.py handles Groq → Gemini failover.
  - The prompt lives in services/ai/prompts/motion_brief.md.
  - DesignBrief schema validates the output.

Flyer image generation still uses the Gemini SDK directly because
the OpenAI-compatible endpoint does not support inline image inputs.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from services.ai.client import generate_json
from services.ai.exceptions import ValidationError
from services.ai.prompts import load_prompt
from services.ai.schemas import DesignBrief

logger = logging.getLogger(__name__)


# ── Remotion Mapping ───────────────────────────────────────────────────────────

STYLE_TO_COMPOSITION = {
    "minimal":       "MinimalVideo",
    "bold":          "BoldVideo",
    "glassmorphism": "GlassmorphismVideo",
    "neon":          "NeonVideo",
}


def brief_to_composition_id(brief: dict) -> str:
    return STYLE_TO_COMPOSITION.get(brief.get("style", "minimal"), "MinimalVideo")


# ── Public API ─────────────────────────────────────────────────────────────────

async def generate_brief_from_topic(
    topic:       str,
    style:       str,
    aspect_ratio: str,
    duration:    int,
    brand_name:  Optional[str],
    brand_color: Optional[str],
) -> dict:
    """
    Generate a DesignBrief from a text topic.
    Uses the new AI client (Groq → Gemini failover).
    """
    logger.info("Generating motion brief from topic | topic=%r style=%s", topic, style)

    system = load_prompt("base")
    prompt = load_prompt(
        "motion_brief",
        topic=topic,
        style=style,
        aspect_ratio=aspect_ratio,
        brand_name=brand_name or "none",
        brand_color=brand_color or "auto",
        duration=duration,
    )

    raw = await generate_json(
        prompt=prompt,
        system=system,
        temperature=0.7,
        max_tokens=1000  # Phase 2A: Design brief (~700 tokens typical),
    )

    return _validate_brief(raw)


async def generate_brief_from_flyer(
    flyer_image_path: Path,
    style:            str,
    aspect_ratio:     str,
    duration:         int,
) -> dict:
    """
    Generate a DesignBrief by reading a flyer image.

    Gemini SDK is used here because it supports inline image data.
    This is the only place in the new architecture that calls a
    provider SDK directly — justified because vision input is not
    supported by the OpenAI-compatible Groq endpoint.
    """
    logger.info("Generating motion brief from flyer | path=%s", flyer_image_path.name)

    from config import GEMINI_API_KEY
    from google import genai
    from google.genai import types as genai_types

    image_data = base64.b64encode(flyer_image_path.read_bytes()).decode()
    mime       = _guess_mime(flyer_image_path)

    system_text = load_prompt("base")

    flyer_prompt = f"""
The user uploaded a flyer to animate.

Style requested: {style}
Aspect ratio: {aspect_ratio}
Duration: {duration} seconds

1. Extract text, brand, colors, numbers from the flyer
2. Summarize in flyerDescription field
3. Map everything into a DesignBrief JSON
4. Set sourceType to "flyer"
5. Choose the best style for this content

{system_text}

Generate the DesignBrief JSON.
""".strip()

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    response = await gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            flyer_prompt,
            genai_types.Part.from_bytes(
                data=base64.b64decode(image_data),
                mime_type=mime,
            ),
        ],
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.6,
            max_output_tokens=1500,
        ),
    )

    text = getattr(response, "text", None)
    if not text:
        raise ValidationError("Gemini returned empty content for flyer brief")

    import json
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON from Gemini flyer brief: {exc}", raw=text[:300]) from exc

    brief = _validate_brief(raw)
    brief["sourceType"] = "flyer"
    return brief


# ── Internal helpers ───────────────────────────────────────────────────────────

def _validate_brief(raw: dict) -> dict:
    """
    Validate and coerce the raw dict using the DesignBrief Pydantic model,
    then return a plain dict for compatibility with existing pipeline code.
    """
    try:
        brief = DesignBrief.model_validate(raw)
        return brief.model_dump(exclude_none=False)
    except Exception as exc:
        import json as _json
        raise ValidationError(
            f"DesignBrief validation failed: {exc}",
            raw=_json.dumps(raw)[:300],
        ) from exc


def _guess_mime(path: Path) -> str:
    return {
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/jpeg")
