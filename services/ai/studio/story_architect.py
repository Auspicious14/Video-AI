"""Stage 3: story architecture specialist."""

from __future__ import annotations

import logging

from services.ai.exceptions import ValidationError
from services.ai.schemas import ResearchResult, StoryArchitectureResult, TopicIntelligenceResult
from services.ai.studio.agent_utils import generate_structured_artifact
from services.ai.studio.context import research_brief_context, topic_brief_context

logger = logging.getLogger(__name__)


async def run_story_architect_agent(
    *,
    brief: TopicIntelligenceResult,
    research: ResearchResult,
    target_duration: int | None = None,
) -> StoryArchitectureResult:
    """Build the documentary story before narration is written."""
    # Use target_duration if provided, otherwise fall back to brief recommendation
    duration = target_duration or brief.recommended_video_length_seconds
    
    try:
        return await generate_structured_artifact(
            prompt_name="studio_story_architect",
            model=StoryArchitectureResult,
            variables={
                "topic_brief": topic_brief_context(brief),
                "research_context": research_brief_context(research, rich=False),
                "target_duration": duration,
            },
            temperature=0.42,
            max_tokens=1400,  # Phase 2A: Realistic limit for story structure (~1000 tokens typical),
            attempts=2,
        )
    except ValidationError as exc:
        logger.warning(
            "Story Architect AI output failed; using deterministic fallback | topic=%s error=%s",
            brief.topic,
            exc,
        )
        return _fallback_story_architecture(brief, research)


def _fallback_story_architecture(
    brief: TopicIntelligenceResult,
    research: ResearchResult,
) -> StoryArchitectureResult:
    """Build a concise story arc from validated research when AI JSON fails."""
    hooks = research.best_hooks
    opening_hook = hooks[0] if hooks else f"What really explains {brief.topic}?"
    facts = research.key_facts[:5] or [research.executive_summary]
    timeline = research.timeline[:4]

    turning_points: list[str] = []
    if timeline:
        turning_points.extend(timeline)
    turning_points.extend(facts[: max(0, 5 - len(turning_points))])

    central_conflict = (
        f"The audience wants a clear answer to {brief.topic}, but the real story depends on "
        "context, tradeoffs, and evidence that are easy to oversimplify."
    )
    climax_fact = research.surprising_facts[0] if research.surprising_facts else facts[-1]

    return StoryArchitectureResult(
        opening_hook=opening_hook,
        central_conflict=central_conflict,
        key_turning_points=turning_points[:6],
        climax=f"Reveal the decisive insight: {climax_fact}",
        conclusion=(
            f"Resolve the comparison by returning to the viewer's original intent: "
            f"what {brief.topic} means for the audience and what to watch next."
        ),
        emotional_progression=[
            "Curiosity in the opening question",
            "Grounded clarity as the facts are established",
            "Tension as tradeoffs and limits appear",
            "Resolution with a practical, evidence-based takeaway",
        ],
        pacing=[
            "Open with a compact hook, then quickly define the stakes",
            "Group facts into story turns instead of listing them one by one",
            "Slow down at the climax so the central insight lands",
            "End with a concise conclusion and no exaggerated hype",
        ],
        act_structure=[
            "Act 1: Set up the question and viewer expectation",
            "Act 2: Follow the evidence through the main turning points",
            "Act 3: Resolve the central conflict with a nuanced answer",
        ],
    )
