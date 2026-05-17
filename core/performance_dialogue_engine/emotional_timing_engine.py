from typing import List
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import Shot
from .schema import PerformanceBeat

class EmotionalTimingEngine:
    """
    Responsible for emotional pacing over time, pause timing, hesitation timing,
    and emotional transition timing.
    """
    
    def generate_performance_timeline(
        self, 
        shot: Shot, 
        scene_intent: SceneIntent
    ) -> List[PerformanceBeat]:
        """
        Generates a timeline of emotional performance beats for a specific shot.
        """
        timeline = []
        duration_ms = int(shot.duration_sec * 1000)
        
        # We generate beats at intervals (e.g., every 500ms) or based on scene beats
        interval_ms = 500
        
        for ts in range(0, duration_ms, interval_ms):
            # Calculate emotional state and intensity at this timestamp
            # This logic interpolates between the shot's performance targets
            # and the overall scene intent emotional targets.
            
            # For simplicity, we'll pick the primary character's performance in this shot
            # In a multi-character shot, we'd generate timelines for each.
            for char_id, perf in shot.performance.items():
                beat = PerformanceBeat(
                    timestamp_ms=ts,
                    emotional_state=perf.emotion,
                    intensity=self._calculate_dynamic_intensity(ts, duration_ms, perf.intensity),
                    body_language=self._map_body_language(perf.emotion, ts),
                    eye_contact_behavior=self._map_eye_behavior(perf.emotion, ts)
                )
                timeline.append(beat)
                
        return timeline

    def _calculate_dynamic_intensity(self, ts: int, total_ms: int, base_intensity: float) -> float:
        # Subtle oscillation of intensity to simulate human micro-shifts
        # This prevents "frozen" emotional states
        import math
        oscillation = 0.05 * math.sin(ts / 1000.0 * math.pi)
        return max(0.0, min(1.0, base_intensity + oscillation))

    def _map_body_language(self, emotion: str, ts: int) -> str:
        # Map emotion to restrained body language
        mapping = {
            "sadness": "slight_slouch",
            "anxiety": "tense_shoulders",
            "anger": "rigid_posture",
            "joy": "open_posture",
            "neutral": "relaxed"
        }
        return mapping.get(emotion.lower(), "relaxed")

    def _map_eye_behavior(self, emotion: str, ts: int) -> str:
        # Human eye behavior is never static
        if "anxiety" in emotion.lower():
            return "frequent_darting" if (ts // 500) % 2 == 0 else "avoidant"
        if "sadness" in emotion.lower():
            return "downward_gaze"
        if "anger" in emotion.lower():
            return "intense_fixed"
        return "natural_scanning"
