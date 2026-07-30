"""Stage 11: editing plan specialist."""

from __future__ import annotations

from services.ai.schemas import EditingPlanResult, ScriptQAResult, VisualPlanResult
from services.ai.studio.agent_utils import generate_structured_artifact
from services.ai.studio.context import script_context, visual_plan_context


async def run_editing_plan_agent(
    *,
    script_qa: ScriptQAResult,
    visual_plan: VisualPlanResult,
    aspect_ratio: str = "16:9",
) -> EditingPlanResult:
    """Create a synchronization and motion plan for the editor/renderer."""
    return await generate_structured_artifact(
        prompt_name="studio_editing_plan",
        model=EditingPlanResult,
        variables={
            "aspect_ratio": aspect_ratio,
            "script_context": script_context(script_qa),
            "visual_plan_context": visual_plan_context(visual_plan),
        },
        temperature=0.38,
        max_tokens=2800,
    )
