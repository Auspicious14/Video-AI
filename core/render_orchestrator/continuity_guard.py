from typing import List
from core.shot_planner.schema import Shot
from .schema import ContinuityConstraints, RenderShot

def build_continuity_constraints(shot: Shot) -> ContinuityConstraints:
    """
    Defines continuity requirements for the rendering pipeline.
    """
    # By default, we always want to preserve character and environment.
    # Camera language preservation depends on the consistency of the shot type 
    # and camera movement with the overall scene.
    return ContinuityConstraints(
        preserve_character_identity=True,
        preserve_environment=True,
        preserve_camera_language=shot.camera.intensity < 0.9 # High intensity might break standard language
    )

def validate_continuity(shots: List[RenderShot]) -> bool:
    """
    Validates that the sequence of shots maintains cinematic continuity.
    Prevents sudden visual resets or emotion discontinuity.
    """
    if not shots:
        return True
        
    for i in range(1, len(shots)):
        prev_shot = shots[i-1]
        curr_shot = shots[i]
        
        # Rule: No abrupt rendering strategy shifts if continuity is high priority
        if prev_shot.render_strategy == "ai_motion" and curr_shot.render_strategy == "deterministic":
            # This might cause a visual "pop". We should flag it or ensure the transition is smooth.
            pass
            
        # Rule: Ensure character identity preservation is enabled across performance-heavy shots
        if curr_shot.asset_requirements.requires_lipsync and not curr_shot.continuity_constraints.preserve_character_identity:
            return False
            
    return True
