from core.shot_planner.schema import Shot
from .schema import FFmpegPlan

def build_ffmpeg_plan(shot: Shot) -> FFmpegPlan:
    """
    Maps ShotPlan instructions to existing FFmpeg infrastructure presets.
    """
    
    # Map camera movement to existing MOTION_EFFECTS in services/renderer.py
    # Options: zoom_in, zoom_out, pan_right, pan_left, tilt_up, tilt_down, static
    movement_map = {
        "static": "static",
        "slow_push_in": "zoom_in",
        "handheld": "zoom_in", # Best deterministic fallback for "breathing" camera
        "pan": "pan_right",
        "tilt": "tilt_up",
        "drift": "zoom_out"
    }
    
    motion_preset = movement_map.get(shot.camera.movement, "static")
    
    # Map transition to existing TRANSITIONS in services/renderer.py
    # Options: cut, fade, dissolve, match_cut
    transition_map = {
        "cut": "cut", # Note: renderer handles 'cut' by just appending
        "fade": "fade",
        "dissolve": "dissolve",
        "match_cut": "cut"
    }
    
    transition_type = transition_map.get(shot.transition_to_next, "cut")
    
    return FFmpegPlan(
        composition_type="hybrid_composition", # Standard for this system
        motion_preset=motion_preset,
        transition_type=transition_type
    )
