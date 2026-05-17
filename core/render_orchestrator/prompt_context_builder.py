from core.shot_planner.schema import Shot
from .schema import GenerationPlan

def build_generation_plan(shot: Shot) -> GenerationPlan:
    """
    Derives structured context from ShotPlan for downstream generation systems.
    Does NOT generate raw prompts, but provides the context needed to build them.
    """
    
    # Image context focuses on framing, lens, and environment
    image_context = (
        f"Type: {shot.shot_type}, "
        f"Framing: {shot.framing.composition} subject {shot.framing.subject}, "
        f"Lens: {shot.camera.lens_style}, "
        f"Environment: {', '.join(shot.environment_motion)}"
    )
    
    # Motion context focuses on camera movement and performance intensity
    performance_summary = "; ".join([
        f"{char}: {p.emotion} (intensity {p.intensity:.2f})" 
        for char, p in shot.performance.items()
    ])
    motion_context = (
        f"Camera: {shot.camera.movement} at intensity {shot.camera.intensity:.2f}, "
        f"Performance: {performance_summary}"
    )
    
    # Voice direction derived from dialogue sync if available
    voice_direction = "N/A"
    if shot.dialogue_sync:
        voice_direction = (
            f"Speaker: {shot.dialogue_sync.spoken_by}, "
            f"Style: {shot.dialogue_sync.delivery_style}, "
            f"Intent: {shot.dialogue_sync.line_intent}"
        )
        
    return GenerationPlan(
        image_prompt_context=image_context,
        motion_prompt_context=motion_context,
        voice_direction=voice_direction
    )
