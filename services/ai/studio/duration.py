"""Duration and narration word-budget helpers for the studio pipeline."""

from __future__ import annotations

from services.ai.schemas import QualityIssue

DOCUMENTARY_WORDS_PER_MINUTE = 145
SCRIPT_DURATION_TOLERANCE = 0.05


def target_word_count(duration_seconds: int, words_per_minute: int = DOCUMENTARY_WORDS_PER_MINUTE) -> int:
    return max(1, round(duration_seconds * words_per_minute / 60))


def word_count(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def estimate_duration_seconds(text: str, words_per_minute: int = DOCUMENTARY_WORDS_PER_MINUTE) -> int:
    return max(1, round(word_count(text) * 60 / words_per_minute))


def word_count_range(duration_seconds: int, tolerance: float = SCRIPT_DURATION_TOLERANCE) -> tuple[int, int]:
    target = target_word_count(duration_seconds)
    return max(1, round(target * (1 - tolerance))), max(1, round(target * (1 + tolerance)))


def duration_issue(
    *,
    narration: str,
    target_duration: int,
    stage: str,
    tolerance: float = SCRIPT_DURATION_TOLERANCE,
) -> QualityIssue | None:
    estimated = estimate_duration_seconds(narration)
    lower = target_duration * (1 - tolerance)
    upper = target_duration * (1 + tolerance)
    if lower <= estimated <= upper:
        return None
    return QualityIssue(
        severity="high",
        stage=stage,
        issue=(
            f"Narration length estimates at {estimated}s for a {target_duration}s target "
            f"(allowed {round(lower)}-{round(upper)}s)."
        ),
        recommendation="Regenerate only the narration/script stage with the target word count enforced.",
    )
