from core.shot_planner.schema import Shot
from .schema import AIMotionPlan

def build_motion_plan(shot: Shot, render_strategy: str) -> AIMotionPlan:
    """
    Coordinates AI motion system selection and fallback strategies.
    """
    enabled = render_strategy in ["ai_motion", "hybrid"]
    
    # Model selection based on duration and complexity
    # Based on services/pipeline_hybrid.py logic:
    # Short clips (<=4s) -> Wan2.1
    # Others -> CogVideoX or SVD
    model = "deterministic_fallback"
    if enabled:
        if shot.duration_sec <= 4.0:
            model = "Wan2.1"
        else:
            model = "CogVideoX"
            
    # Fallback ladder: AI Video -> Image+KenBurns
    fallback_strategy = "ken_burns_deterministic"
    
    return AIMotionPlan(
        enabled=enabled,
        model=model,
        timeout_sec=180, # Default from services/pipeline_ai_video.py
        fallback_strategy=fallback_strategy
    )
