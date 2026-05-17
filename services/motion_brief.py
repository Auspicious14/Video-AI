"""
services/motion_brief.py

Generates a structured DesignBrief JSON from:
  - A text topic/prompt (sourceType: "prompt")
  - A flyer image uploaded by the user (sourceType: "flyer")

The brief is the single contract between Python and Remotion.
Gemini writes everything the templates need: colors, text, stats, list items.
"""

import json
import base64
import re
from pathlib import Path
from typing import Optional, Any

from google import genai
from config import GEMINI_API_KEY


# ── Client Setup ──────────────────────────────────────────────────────────────

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"


# ── Prompt templates ───────────────────────────────────────────────────────────

_BRIEF_SYSTEM = """
You are a motion design director for VideoAI.ng, a Nigerian video SaaS.
Your job is to generate a structured DesignBrief JSON for a Remotion video template.

Return ONLY valid JSON. No markdown, no backticks, no explanation. Pure JSON object.

The JSON must exactly match this TypeScript type:

interface StatItem {
  label: string;
  value: string;
  suffix?: string;
  prefix?: string;
  numericValue: number;
}

interface ListItem {
  index: number;
  headline: string;
  body?: string;
  emoji?: string;
}

interface DesignBrief {
  style: "minimal" | "bold" | "glassmorphism" | "neon";
  aspectRatio: "9:16" | "16:9" | "1:1";
  durationSeconds: number;
  brandName?: string;
  brandColor: string;
  accentColor: string;
  bgColor: string;
  textColor: string;
  title: string;
  subtitle?: string;
  bodyText?: string;
  tagline?: string;
  cta?: string;
  stats?: StatItem[];
  listItems?: ListItem[];
  animationSpeed: "slow" | "normal" | "fast";
  fontPairing: "syne_dmsans" | "inter" | "playfair_inter";
  sourceType: "prompt" | "flyer";
  flyerDescription?: string;
}

Rules:
- brandColor and accentColor must be contrasting, vivid hex codes
- bgColor must be very dark (near black) for "neon" and "glassmorphism" styles
- bgColor can be white or light for "minimal"
- textColor must contrast well against bgColor
- For "glassmorphism": always include 2–4 stats items with realistic numericValue
- For "neon": always include 3–5 listItems
- For "bold": always include tagline
- For "minimal": always include bodyText
- title should be punchy (max 7 words)
- durationSeconds: 10–25 depending on complexity
- fontPairing: use "syne_dmsans" for Nigerian brands
- animationSpeed: fast for TikTok, normal for brand, slow for luxury
"""

_PROMPT_USER_TEMPLATE = """
Topic: {topic}
Style requested: {style}
Aspect ratio: {aspect_ratio}
Brand name: {brand_name}
Brand color hint: {brand_color}
Duration: {duration} seconds

Generate a DesignBrief JSON.
"""

_FLYER_USER_TEMPLATE = """
The user uploaded a flyer to animate.

Style requested: {style}
Aspect ratio: {aspect_ratio}
Duration: {duration} seconds

1. Extract text, brand, colors, numbers
2. Summarize in flyerDescription
3. Map everything into DesignBrief JSON
4. Choose best style

Generate the DesignBrief JSON.
"""


# ── Core Gemini Wrapper (IMPORTANT) ────────────────────────────────────────────

async def _generate_with_gemini(contents: list[Any], temperature: float) -> str:
    """
    Unified Gemini call wrapper (safer + reusable).
    """
    response = await client.models.generate_content_async(
        model=MODEL_NAME,
        contents=contents,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": 1500,
        },
    )

    return _extract_text(response)


def _extract_text(response: Any) -> str:
    """
    Safely extract text from Gemini response.
    """
    if hasattr(response, "text") and response.text:
        return response.text

    try:
        return response.candidates[0].content.parts[0].text
    except Exception:
        raise ValueError("Failed to extract text from Gemini response")


# ── Public API ─────────────────────────────────────────────────────────────────

async def generate_brief_from_topic(
    topic: str,
    style: str,
    aspect_ratio: str,
    duration: int,
    brand_name: Optional[str],
    brand_color: Optional[str],
) -> dict:
    prompt = _PROMPT_USER_TEMPLATE.format(
        topic=topic,
        style=style,
        aspect_ratio=aspect_ratio,
        brand_name=brand_name or "none",
        brand_color=brand_color or "auto",
        duration=duration,
    )

    raw_text = await _generate_with_gemini(
        [_BRIEF_SYSTEM, prompt],
        temperature=0.7,
    )

    return _parse_brief(raw_text)


async def generate_brief_from_flyer(
    flyer_image_path: Path,
    style: str,
    aspect_ratio: str,
    duration: int,
) -> dict:
    image_data = base64.b64encode(flyer_image_path.read_bytes()).decode()
    mime = _guess_mime(flyer_image_path)

    prompt = _FLYER_USER_TEMPLATE.format(
        style=style,
        aspect_ratio=aspect_ratio,
        duration=duration,
    )

    raw_text = await _generate_with_gemini(
        [
            _BRIEF_SYSTEM,
            {
                "inline_data": {
                    "mime_type": mime,
                    "data": image_data,
                }
            },
            prompt,
        ],
        temperature=0.6,
    )

    brief = _parse_brief(raw_text)
    brief["sourceType"] = "flyer"
    return brief


# ── Parsing + Validation ───────────────────────────────────────────────────────

def _parse_brief(raw_text: str) -> dict:
    text = raw_text.strip()

    # Remove markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        brief = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from Gemini:\n{text[:500]}") from e

    _validate_brief(brief)
    return brief


def _validate_brief(brief: dict) -> None:
    required = ["style", "aspectRatio", "brandColor", "bgColor", "textColor", "title"]

    for key in required:
        if key not in brief:
            raise ValueError(f"Missing required field: {key}")

    if brief.get("style") not in {"minimal", "bold", "glassmorphism", "neon"}:
        brief["style"] = "minimal"

    if brief.get("aspectRatio") not in {"9:16", "16:9", "1:1"}:
        brief["aspectRatio"] = "9:16"

    brief.setdefault("durationSeconds", 15)
    brief.setdefault("animationSpeed", "normal")
    brief.setdefault("fontPairing", "syne_dmsans")
    brief.setdefault("sourceType", "prompt")


def _guess_mime(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/jpeg")


# ── Remotion Mapping ───────────────────────────────────────────────────────────

STYLE_TO_COMPOSITION = {
    "minimal": "MinimalVideo",
    "bold": "BoldVideo",
    "glassmorphism": "GlassmorphismVideo",
    "neon": "NeonVideo",
}


def brief_to_composition_id(brief: dict) -> str:
    return STYLE_TO_COMPOSITION.get(brief.get("style", "minimal"), "MinimalVideo")
