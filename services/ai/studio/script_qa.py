"""Stage 5: script quality assurance specialist."""

from __future__ import annotations

import logging

from services.ai.exceptions import ValidationError
from services.ai.schemas import (
    DocumentaryScriptResult,
    QualityIssue,
    ResearchResult,
    ScriptQAResult,
    StoryArchitectureResult,
    ScriptQAGeneration
)
from services.ai.studio.agent_utils import generate_structured_artifact
from services.ai.studio.context import research_brief_context, script_context, story_context

logger = logging.getLogger(__name__)


async def run_script_qa_agent(
    *,
    script: DocumentaryScriptResult,
    research: ResearchResult,
    story: StoryArchitectureResult,
    target_duration: int | None = None,
) -> ScriptQAResult:
    from services.ai.studio.duration import estimate_duration_seconds, word_count_range

    narration_word_count = len(script.narration.split())
    estimated_seconds = estimate_duration_seconds(script.narration)

    if target_duration:
        min_words, max_words = word_count_range(target_duration)
    else:
        min_words, max_words = word_count_range(script.estimated_duration_seconds)
        target_duration = script.estimated_duration_seconds

    try:
        generated = await generate_structured_artifact(
            prompt_name="studio_script_qa",
            model=ScriptQAGeneration,
            variables={
                "research_context": research_brief_context(research, rich=False),
                "story_context": story_context(story),
                "script_context": script_context(script),
                "word_count": narration_word_count,
                "expected_min_words": min_words,
                "expected_max_words": max_words,
                "estimated_seconds": estimated_seconds,
            },
            temperature=0.24,
            max_tokens=900,
            attempts=2,
        )

        # Copy the correctly-generated script forward. Only swap in a QA
        # rewrite if one was explicitly given AND it isn't suspiciously
        # shorter than the original — never let QA silently shrink a
        # script that was already correct. section_metadata comes along
        # for free since it's a deep copy, no separate carry-forward needed.
        revised = script.model_copy(deep=True)
        if generated.revised_narration and len(generated.revised_narration.split()) >= narration_word_count * 0.9:
            revised.narration = generated.revised_narration

        return ScriptQAResult(
            approved=generated.approved,
            score=generated.score,
            revised_script=revised,
            issues=generated.issues,
            strengths=generated.strengths,
        )
    except ValidationError as exc:
        logger.warning(
            "Script QA AI output failed; using fallback approval gate | topic=%s error=%s",
            research.topic, exc,
        )
        return _fallback_script_qa(script, target_duration)

def _fallback_script_qa(script: DocumentaryScriptResult, target_duration: int | None = None) -> ScriptQAResult:
    """Preserve the script and continue with a manual-review warning."""
    word_count = len(script.narration.split())
    issues: list[QualityIssue] = [
        QualityIssue(
            severity="medium",
            stage="script_qa",
            issue="Automated script QA returned invalid structured output.",
            recommendation="Review the script manually before publishing.",
        )
    ]
    
    # Check duration if target provided
    if target_duration:
        from services.ai.studio.duration import word_count_range
        min_words, max_words = word_count_range(target_duration)
        if word_count < min_words * 0.85:
            issues.append(
                QualityIssue(
                    severity="high",
                    stage="script_qa",
                    issue=f"Script is significantly short: {word_count} words (expected {min_words}-{max_words} for {target_duration}s)",
                    recommendation="Expand the story beats with research details before rendering.",
                )
            )
    elif word_count < 120:
        issues.append(
            QualityIssue(
                severity="high",
                stage="script_qa",
                issue="Script appears short for long-form YouTube narration.",
                recommendation="Expand the story beats before rendering.",
            )
        )

    score = 72.0 if word_count >= 120 else 55.0
    return ScriptQAResult(
        approved=word_count >= 120,
        score=score,
        revised_script=script,
        issues=issues,
        strengths=["Script preserved from writing stage for downstream production."],
    )
