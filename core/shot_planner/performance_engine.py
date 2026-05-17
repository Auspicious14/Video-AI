from typing import List, Dict, Optional
from core.scene_intent.schema import SceneIntent, CharacterDirection
from core.shot_planner.schema import PerformanceBlock, DialogueSyncBlock

class PerformanceEngine:
    """
    Transforms character emotional state into physical behavior.
    Generates micro-actions, body language, and speech delivery patterns.
    """
    
    # Emotional mapping to physical behaviors (micro-actions)
    EMOTION_MAP = {
        "suppressed_grief": {
            "micro_actions": ["delayed speech", "tight jaw", "low eye contact", "restricted movement"],
            "delivery": "whispered",
            "body_language": "rigid posture"
        },
        "anxiety": {
            "micro_actions": ["fidgeting fingers", "rapid blinking", "darting eyes", "shallow breaths"],
            "delivery": "broken",
            "body_language": "hunched shoulders"
        },
        "anger": {
            "micro_actions": ["flared nostrils", "clenched fists", "intense stare", "heavy breathing"],
            "delivery": "steady",
            "body_language": "leaning forward"
        },
        "joy": {
            "micro_actions": ["relaxed smile", "bright eyes", "open gestures", "light movement"],
            "delivery": "steady",
            "body_language": "open stance"
        },
        "reflection": {
            "micro_actions": ["slow gaze shift", "slight tilt of head", "stillness", "soft expression"],
            "delivery": "slow",
            "body_language": "relaxed but thoughtful"
        }
    }

    def generate_performance(self, character_id: str, direction: CharacterDirection) -> PerformanceBlock:
        emotion = direction.emotion.lower().replace(" ", "_")
        intensity = direction.intensity
        
        # Find best match in EMOTION_MAP or fallback
        config = self.EMOTION_MAP.get(emotion, self._get_fallback_config(emotion))
        
        micro_actions = config["micro_actions"].copy()
        # Add behavior notes from intent
        micro_actions.extend(direction.behavior_notes)
        
        # Adjust micro-actions based on intensity
        if intensity < 0.3:
            micro_actions = micro_actions[:2] # Less actions for low intensity
        elif intensity > 0.8:
            micro_actions.append("exaggerated expressions")
            
        return PerformanceBlock(
            emotion=direction.emotion,
            intensity=intensity,
            micro_actions=micro_actions
        )

    def generate_dialogue_sync(self, scene_intent: SceneIntent, character_id: str) -> Optional[DialogueSyncBlock]:
        # Find if this character has dialogue in this scene
        for dial in scene_intent.dialogue_intent:
            if dial.character_id == character_id:
                emotion = scene_intent.character_directions.get(character_id).emotion.lower().replace(" ", "_")
                config = self.EMOTION_MAP.get(emotion, {"delivery": "steady"})
                
                return DialogueSyncBlock(
                    spoken_by=character_id,
                    line_intent=dial.intent,
                    delivery_style=config.get("delivery", "steady")
                )
        return None

    def _get_fallback_config(self, emotion: str) -> dict:
        return {
            "micro_actions": [f"showing {emotion}", "standard idle movement"],
            "delivery": "steady",
            "body_language": "neutral"
        }
