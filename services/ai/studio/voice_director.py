"""Stage 9 and 10: voice direction and audio QA."""

from __future__ import annotations

from pathlib import Path

from services.ai.schemas import AudioQAResult, QualityIssue, ScriptQAResult, VoiceDirectionResult
from services.ai.studio.agent_utils import generate_structured_artifact
from services.ai.studio.context import VoiceDirectionContext, script_context
from services.ai.studio.duration import SCRIPT_DURATION_TOLERANCE


async def run_voice_direction_agent(
    *,
    context: VoiceDirectionContext,
) -> VoiceDirectionResult:
    """
    Define narration performance, pacing, pronunciation, and emotion.
    
    Optimized: Receives only narration (1,000 tokens) instead of full script artifact (4,000 tokens).
    Token reduction: 75%
    """
    return await generate_structured_artifact(
        prompt_name="studio_voice_direction",
        model=VoiceDirectionResult,
        variables={
            "requested_voice_id": context.voice_id,
            "narration": context.narration,
        },
        temperature=0.35,
        max_tokens=1200  # Phase 2A: Realistic limit for voice notes (~800 tokens typical),
    )


def run_audio_qa(
    *,
    audio_path: Path,
    duration_seconds: float,
    expected_duration_seconds: int,
) -> AudioQAResult:
    """Perform deterministic audio checks after TTS generation."""
    issues: list[QualityIssue] = []
    
    # Check audio file exists and has content
    if not audio_path.exists() or audio_path.stat().st_size < 5000:
        issues.append(
            QualityIssue(
                severity="critical",
                stage="audio_qa",
                issue="Generated audio file is missing or too small.",
                recommendation="Regenerate narration audio with another provider.",
            )
        )

    # Check duration measurement
    if duration_seconds <= 0:
        issues.append(
            QualityIssue(
                severity="critical",
                stage="audio_qa",
                issue="Could not measure narration duration.",
                recommendation="Inspect ffprobe/soundfile output and regenerate the audio file.",
            )
        )
    else:
        # Check duration alignment using the same tolerance as script validation
        lower_bound = expected_duration_seconds * (1 - SCRIPT_DURATION_TOLERANCE)
        upper_bound = expected_duration_seconds * (1 + SCRIPT_DURATION_TOLERANCE)
        
        if duration_seconds < lower_bound:
            severity = "high" if duration_seconds < lower_bound * 0.9 else "medium"
            issues.append(
                QualityIssue(
                    severity=severity,
                    stage="audio_qa",
                    issue=f"Audio is too short: {duration_seconds:.1f}s (expected {expected_duration_seconds}s, range {lower_bound:.1f}-{upper_bound:.1f}s)",
                    recommendation="Script narration may need expansion, or TTS speed may be too fast.",
                )
            )
        elif duration_seconds > upper_bound:
            severity = "high" if duration_seconds > upper_bound * 1.1 else "medium"
            issues.append(
                QualityIssue(
                    severity=severity,
                    stage="audio_qa",
                    issue=f"Audio is too long: {duration_seconds:.1f}s (expected {expected_duration_seconds}s, range {lower_bound:.1f}-{upper_bound:.1f}s)",
                    recommendation="Script narration may need trimming, or TTS speed may be too slow.",
                )
            )

    score = max(0.0, 100.0 - (35.0 * len([i for i in issues if i.severity == "critical"])) - (12.0 * len(issues)))
    return AudioQAResult(
        approved=not any(i.severity == "critical" for i in issues),
        score=score,
        duration_seconds=duration_seconds,
        issues=issues,
        regenerate_ranges=[],
    )
