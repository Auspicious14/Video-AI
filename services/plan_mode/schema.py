"""Pydantic schema + pure helpers for a hand-written production plan.

Deliberately dependency-light (pydantic only): validating a plan and printing a
dry-run summary must work with no network, no ffmpeg, no API keys.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WORDS_PER_MINUTE = 150  # same pace generate_video.py assumes (2.5 words/sec)
MIN_RECOMMENDED_SCENE_SECONDS = 2.0


class VisualKind(str, Enum):
    WIKIMEDIA = "wikimedia"          # Wikimedia Commons image search, no API key
    PEXELS_IMAGE = "pexels_image"    # needs PEXELS_API_KEY
    PEXELS_VIDEO = "pexels_video"    # needs PEXELS_API_KEY
    URL = "url"                      # direct http(s) URL or local file (image or video)
    TEXT_CARD = "text_card"          # generated title card, fully offline


_QUERY_KINDS = {VisualKind.WIKIMEDIA, VisualKind.PEXELS_IMAGE, VisualKind.PEXELS_VIDEO}


class _Strict(BaseModel):
    # Reject unknown keys so typos ("scene" vs "scenes") fail loudly.
    model_config = ConfigDict(extra="forbid")


class Scene(_Strict):
    kind: VisualKind
    query: str | None = Field(None, description="Search text for wikimedia / pexels_* kinds")
    url: str | None = Field(None, description="http(s) URL or local path for kind=url")
    text: str | None = Field(None, description="Text shown for kind=text_card (also the fallback card text)")
    caption: str | None = Field(None, description="Free-form note. Not rendered; kept in the credits sidecar")
    duration_weight: float = Field(1.0, gt=0, le=100, description="Relative share of the section's narration time")

    @field_validator("query", "url", "text", "caption")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _required_fields_for_kind(self) -> "Scene":
        if self.kind in _QUERY_KINDS and not self.query:
            raise ValueError(f"kind '{self.kind.value}' requires 'query'")
        if self.kind is VisualKind.URL and not self.url:
            raise ValueError("kind 'url' requires 'url'")
        if self.kind is VisualKind.TEXT_CARD and not self.text:
            raise ValueError("kind 'text_card' requires 'text'")
        return self

    @property
    def fallback_text(self) -> str:
        """Text for the text-card used when asset retrieval fails."""
        return self.text or self.caption or self.query or ""


class Section(_Strict):
    title: str = Field(..., min_length=1)
    narration: str = Field(..., description="Spoken text for this section")
    scenes: list[Scene] = Field(..., min_length=1)

    @field_validator("narration")
    @classmethod
    def _narration_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("narration must not be empty")
        return v

    @property
    def word_count(self) -> int:
        return len(self.narration.split())


class ProductionPlan(_Strict):
    title: str = Field(..., min_length=1)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    voice: str | None = Field(None, description="Kokoro voice id (e.g. 'am_adam') or a VOICE_REGISTRY key")
    music: str | None = Field(None, description="Background music: local path or http(s) URL (mixed at -18 dB)")
    hook: str = Field("", description="Optional text overlaid for the first 3 seconds")
    cta: str = Field("", description="Optional text overlaid for the last 5 seconds")
    subtitles: bool = True
    sections: list[Section] = Field(..., min_length=1)

    @property
    def word_count(self) -> int:
        return sum(s.word_count for s in self.sections)

    @property
    def scene_count(self) -> int:
        return sum(len(s.scenes) for s in self.sections)

    @property
    def estimated_duration_seconds(self) -> float:
        return estimate_duration(self.word_count)

    @property
    def narration(self) -> str:
        return "\n\n".join(s.narration for s in self.sections)


def estimate_duration(word_count: int, wpm: int = WORDS_PER_MINUTE) -> float:
    return word_count / wpm * 60.0


def split_durations(total: float, weights: list[float]) -> list[float]:
    """Split ``total`` seconds across scenes proportionally to ``weights``.

    The parts always sum to exactly ``total`` (the last part absorbs rounding).
    """
    if not weights:
        return []
    if any(w <= 0 for w in weights):
        raise ValueError("weights must be positive")
    weight_sum = sum(weights)
    parts = [round(total * w / weight_sum, 3) for w in weights]
    parts[-1] = round(total - sum(parts[:-1]), 3)
    return parts


def load_plan(path: str | Path) -> ProductionPlan:
    """Read and validate a plan file. Raises pydantic.ValidationError / ValueError."""
    raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    return ProductionPlan.model_validate(data)


def format_summary(plan: ProductionPlan) -> str:
    """Human-readable dry-run report (no network)."""
    lines = [
        f"Title:      {plan.title}",
        f"Aspect:     {plan.aspect_ratio}",
        f"Voice:      {plan.voice or '(default)'}",
        f"Music:      {plan.music or '(none)'}",
        f"Sections:   {len(plan.sections)}",
        f"Scenes:     {plan.scene_count}",
        f"Words:      {plan.word_count}",
        f"Est. time:  {plan.estimated_duration_seconds:.0f}s at {WORDS_PER_MINUTE} wpm",
        "",
    ]
    for i, sec in enumerate(plan.sections, 1):
        sec_secs = estimate_duration(sec.word_count)
        lines.append(f"[{i}] {sec.title}  ({sec.word_count} words, ~{sec_secs:.0f}s)")
        parts = split_durations(sec_secs, [sc.duration_weight for sc in sec.scenes])
        for j, (sc, secs) in enumerate(zip(sec.scenes, parts), 1):
            detail = sc.query or sc.url or sc.text or ""
            flag = "  <-- short" if secs < MIN_RECOMMENDED_SCENE_SECONDS else ""
            lines.append(f"     {j}. {sc.kind.value:<13} ~{secs:4.1f}s  {detail[:60]}{flag}")
    kinds = {sc.kind for s in plan.sections for sc in s.scenes}
    env = []
    if kinds & {VisualKind.PEXELS_IMAGE, VisualKind.PEXELS_VIDEO}:
        env.append("PEXELS_API_KEY")
    lines += ["", "Env needed: " + (", ".join(env) if env else "none")]
    return "\n".join(lines)
