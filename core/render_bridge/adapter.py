"""
core/render_bridge/adapter.py
Adapts ShotPlan + RenderExecutionPlan into existing pipeline inputs.
"""
from core.shot_planner.schema import ShotPlan
from core.render_orchestrator.schema import RenderExecutionPlan
from typing import List, Dict, Any


def adapt_render_plan_to_pipeline(
    shot_plan: ShotPlan,
    render_execution_plan: RenderExecutionPlan,
    request: Any
) -> Dict[str, Any]:
    """
    Converts cinematic planning outputs into a format compatible with existing hybrid pipeline.
    """
    # Build scenes structure for existing pipeline
    scenes = []
    for i, shot in enumerate(shot_plan.shots):
        scene = {
            "description": f"{shot.shot_type} - {shot.camera.movement}",
            "duration": shot.duration_sec,
        }
        scenes.append(scene)

    # Build narration from shot dialogue intents
    narration_parts = []
    for shot in shot_plan.shots:
        if shot.dialogue_sync:
            narration_parts.append(shot.dialogue_sync.line)
    narration = " ".join(narration_parts) or request.topic

    return {
        "scenes": scenes,
        "narration": narration,
        "caption": request.topic,
        "cta": "",
    }

