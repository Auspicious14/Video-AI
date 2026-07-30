"""Stage 1: topic intelligence specialist."""

from __future__ import annotations

from services.ai.schemas import TopicIntelligenceResult
from services.ai.studio.agent_utils import generate_structured_artifact


async def run_topic_intelligence_agent(
    *,
    topic: str,
    target_platform: str = "youtube",
    audience_profile: str = "",
    monetization_goal: str = "long-term YouTube revenue",
) -> TopicIntelligenceResult:
    """Transform a raw topic into a structured content brief."""
    return await generate_structured_artifact(
        prompt_name="studio_topic_intelligence",
        model=TopicIntelligenceResult,
        variables={
            "topic": topic,
            "target_platform": target_platform,
            "audience_profile": audience_profile or "General curious YouTube audience",
            "monetization_goal": monetization_goal,
        },
        temperature=0.35,
        max_tokens=400  # Phase 2A: Compact metadata (~300 tokens typical),
    )
