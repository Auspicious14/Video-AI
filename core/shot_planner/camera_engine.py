from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import CameraBlock, FramingBlock
from typing import Dict

class CameraEngine:
    """
    Maps SceneIntent camera_direction into shot-level camera behavior.
    Ensures camera behavior reflects emotional state.
    """
    
    def generate_camera_block(self, scene_intent: SceneIntent, shot_type: str, shot_index: int) -> CameraBlock:
        emotion = scene_intent.emotional_target.dominant_emotion.lower()
        intensity = scene_intent.emotional_target.intensity
        
        movement = "static"
        cam_intensity = intensity
        lens_style = "cinematic_standard"
        
        # Rule-based camera movement selection
        if "anxiety" in emotion or "fear" in emotion:
            movement = "handheld"
            cam_intensity = max(0.5, intensity)
        elif "tension" in emotion or "suspense" in emotion:
            movement = "slow_push_in"
            cam_intensity = intensity
        elif "grief" in emotion or "sadness" in emotion:
            movement = "static"
            lens_style = "shallow_depth" if shot_type == "close_up" else "cinematic_standard"
        elif "reflection" in emotion or "calm" in emotion:
            movement = "drift" if shot_type == "wide" else "static"
            cam_intensity = 0.3
            lens_style = "deep_focus" if shot_type == "wide" else "cinematic_standard"
        else:
            # Default fallback based on SceneIntent movement if provided
            movement = self._map_intent_movement(scene_intent.camera_direction.movement)
            
        return CameraBlock(
            movement=movement,
            intensity=cam_intensity,
            lens_style=lens_style
        )

    def generate_framing_block(self, scene_intent: SceneIntent, shot_type: str) -> FramingBlock:
        # Default subject is the first character in directions
        subject = list(scene_intent.character_directions.keys())[0] if scene_intent.character_directions else "unknown"
        
        composition = "center"
        if shot_type == "wide":
            composition = "rule_of_thirds"
        elif shot_type == "close_up":
            composition = "center"
        elif scene_intent.tension_delta > 0.6:
            composition = "off_center"
            
        return FramingBlock(
            subject=subject,
            composition=composition
        )

    def _map_intent_movement(self, intent_movement: str) -> str:
        mapping = {
            "pan": "pan",
            "tilt": "tilt",
            "push": "slow_push_in",
            "handheld": "handheld",
            "static": "static",
            "drift": "drift"
        }
        return mapping.get(intent_movement.lower(), "static")
