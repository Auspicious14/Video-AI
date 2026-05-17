from typing import List
from core.shot_planner.schema import ShotPlan, Shot
from .schema import (
    RenderExecutionPlan, 
    RenderShot, 
    AssetRequirements, 
    AudioPlan
)
from .strategy_selector import select_render_strategy
from .prompt_context_builder import build_generation_plan
from .ffmpeg_adapter import build_ffmpeg_plan
from .motion_orchestrator import build_motion_plan
from .continuity_guard import build_continuity_constraints, validate_continuity

def generate_render_execution_plan(shot_plan: ShotPlan) -> RenderExecutionPlan:
    """
    Transforms a ShotPlan into a deterministic RenderExecutionPlan.
    This is the "execution director" of the platform.
    """
    
    render_shots: List[RenderShot] = []
    
    for i, shot in enumerate(shot_plan.shots):
        # 1. Select rendering strategy
        strategy = select_render_strategy(shot)
        
        # 2. Determine asset requirements
        asset_reqs = AssetRequirements(
            requires_image_generation=True, # Always need a base image
            requires_video_generation=strategy in ["ai_motion", "hybrid"],
            requires_voice=shot.dialogue_sync is not None,
            requires_lipsync=shot.dialogue_sync is not None and strategy != "deterministic"
        )
        
        # 3. Build generation context
        gen_plan = build_generation_plan(shot)
        
        # 4. Build FFmpeg execution instructions
        ffmpeg_plan = build_ffmpeg_plan(shot)
        
        # 5. Configure AI motion plan
        motion_plan = build_motion_plan(shot, strategy)
        
        # 6. Configure audio + lip sync plans
        audio_plan = AudioPlan(
            tts_provider="elevenlabs", # System default
            emotional_tone=next(iter(shot.performance.values())).emotion if shot.performance else "neutral",
            pacing=shot.dialogue_sync.delivery_style if shot.dialogue_sync else "steady"
        )
        
        # 7. Apply continuity constraints
        continuity = build_continuity_constraints(shot)
        
        # 8. Assemble RenderShot
        render_shot = RenderShot(
            shot_id=shot.shot_id,
            render_strategy=strategy,
            asset_requirements=asset_reqs,
            generation_plan=gen_plan,
            ffmpeg_plan=ffmpeg_plan,
            ai_motion_plan=motion_plan,
            audio_plan=audio_plan,
            continuity_constraints=continuity,
            execution_order=i
        )
        
        render_shots.append(render_shot)
        
    # 9. Validate overall continuity
    validate_continuity(render_shots)
    
    # 10. Return the final execution plan
    return RenderExecutionPlan(
        story_id=shot_plan.story_id,
        scene_id=shot_plan.scene_id,
        shots=render_shots
    )
