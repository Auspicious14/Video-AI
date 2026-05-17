from typing import Literal
from core.shot_planner.schema import Shot

RenderStrategy = Literal["deterministic", "ai_motion", "hybrid"]

def select_render_strategy(shot: Shot) -> RenderStrategy:
    """
    Decides the rendering strategy for a given shot based on cinematic intent.
    
    Decision Factors:
    - emotional intensity
    - shot duration
    - camera movement complexity
    - performance complexity
    """
    
    # 1. Check for high-intensity action or dynamic camera movement
    is_dynamic_camera = shot.camera.movement in ["handheld", "pan", "tilt"] and shot.camera.intensity > 0.7
    
    # Check if any character has high performance intensity
    has_high_intensity_performance = any(p.intensity > 0.8 for p in shot.performance.values())
    
    # 2. AI Motion for high complexity/action
    if is_dynamic_camera or (has_high_intensity_performance and shot.shot_type in ["medium", "wide"]):
        return "ai_motion"
    
    # 3. Hybrid for subtle performances in close-up or medium shots
    if has_high_intensity_performance or shot.dialogue_sync:
        return "hybrid"
    
    # 4. Deterministic for static/low-intensity shots
    # Static emotional close-ups are deterministic by default as per requirements
    if shot.camera.movement == "static" or shot.camera.intensity < 0.4:
        return "deterministic"
    
    # Default to deterministic (safety first)
    return "deterministic"
