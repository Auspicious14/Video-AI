from typing import List
from core.cinematic_state.models import CinematicStateGraph
from .schema import EmotionalTarget, SceneBeat

class ScenePlanner:
    def determine_narrative_purpose(self, state: CinematicStateGraph) -> str:
        tension = state.narrative_state.tension
        scene_index = state.narrative_state.current_scene_index
        
        # Deterministic logic based on tension and scene progress
        if tension < 0.3:
            return "World Building & Atmosphere"
        elif tension < 0.6:
            if scene_index % 2 == 0:
                return "Character Development"
            else:
                return "Rising Action & Investigation"
        elif tension < 0.8:
            return "Escalating Conflict"
        else:
            return "Climax & High Stakes Confrontation"

    def determine_emotional_target(self, state: CinematicStateGraph) -> EmotionalTarget:
        current_emotion = state.emotion_state.dominant_emotion
        current_intensity = state.emotion_state.intensity
        
        # Rule 1: Emotion must change or reinforce. 
        # Deterministic shift: slightly increase intensity if below 0.8, else shift to a related emotion
        if current_intensity < 0.8:
            new_intensity = round(min(1.0, current_intensity + 0.1), 2)
            new_emotion = current_emotion
        else:
            new_intensity = round(max(0.5, current_intensity - 0.2), 2)
            # Simple deterministic emotion shift for high intensity
            shifts = {
                "joy": "contentment",
                "anger": "cold resentment",
                "fear": "paranoia",
                "sadness": "reflection",
                "neutral": "curiosity"
            }
            new_emotion = shifts.get(current_emotion.lower(), "neutral")
        
        return EmotionalTarget(
            dominant_emotion=new_emotion,
            intensity=new_intensity
        )

    def determine_tension_delta(self, state: CinematicStateGraph) -> float:
        # Rule 2: Tension must NEVER remain identical.
        current_tension = state.narrative_state.tension
        
        # Simple deterministic progression
        if current_tension < 0.4:
            return 0.15 # Increase
        elif current_tension < 0.7:
            return 0.1  # Further increase
        elif current_tension < 0.9:
            return 0.05 # Slower increase towards climax
        else:
            return -0.2 # Release tension after climax

    def generate_scene_beats(self, state: CinematicStateGraph, purpose: str, target: EmotionalTarget) -> List[SceneBeat]:
        # Generate beats based on purpose
        beats = []
        if "World Building" in purpose:
            beats = [
                SceneBeat(beat="Establish environment details", emotion_shift="Curiosity"),
                SceneBeat(beat="Introduce atmospheric elements", emotion_shift="Immersion")
            ]
        elif "Conflict" in purpose or "Climax" in purpose:
            beats = [
                SceneBeat(beat="Direct confrontation starts", emotion_shift="Stress"),
                SceneBeat(beat="High stakes moment revealed", emotion_shift="Shock"),
                SceneBeat(beat="Immediate reaction to crisis", emotion_shift=target.dominant_emotion)
            ]
        elif "Character Development" in purpose:
            beats = [
                SceneBeat(beat="Internal reflection moment", emotion_shift="Contemplation"),
                SceneBeat(beat="Key character trait revealed", emotion_shift=target.dominant_emotion)
            ]
        else:
            beats = [
                SceneBeat(beat="Character interaction begins", emotion_shift="Neutral/Observational"),
                SceneBeat(beat="Emotional core of scene revealed", emotion_shift=target.dominant_emotion)
            ]
        return beats
