from typing import List
from core.shot_planner.schema import Shot
from .schema import GestureBeat, PerformanceBeat

class GestureDirector:
    """
    Responsible for body-language behavior, gesture timing, gesture restraint, 
    and movement realism.
    """
    
    def generate_gesture_timeline(
        self, 
        shot: Shot, 
        performance_timeline: List[PerformanceBeat]
    ) -> List[GestureBeat]:
        """
        Generates a timeline of gestures based on the performance and shot type.
        """
        gesture_timeline = []
        
        # Gestures are less frequent than facial expressions for realism
        # We only trigger them at significant emotional shifts or specific intervals
        last_intensity = 0.0
        
        for p_beat in performance_timeline:
            # Trigger gesture if intensity shift is significant or at random natural intervals
            if abs(p_beat.intensity - last_intensity) > 0.3:
                gesture_type = self._select_gesture(p_beat.emotional_state, p_beat.intensity)
                
                if gesture_type != "none":
                    g_beat = GestureBeat(
                        timestamp_ms=p_beat.timestamp_ms,
                        gesture_type=gesture_type,
                        intensity=p_beat.intensity,
                        duration_ms=self._calculate_duration(gesture_type)
                    )
                    gesture_timeline.append(g_beat)
                
                last_intensity = p_beat.intensity
                
        return gesture_timeline

    def _select_gesture(self, emotion: str, intensity: float) -> str:
        # Restrained gesture selection
        if intensity < 0.4:
            return "none" # Most human movement is subtle/still
            
        if "anxiety" in emotion.lower():
            return "hand_wring" if intensity > 0.7 else "finger_tap"
        if "anger" in emotion.lower():
            return "sharp_head_turn" if intensity > 0.8 else "hand_clench"
        if "sadness" in emotion.lower():
            return "slow_head_bow"
        
        return "slight_posture_shift"

    def _calculate_duration(self, gesture_type: str) -> int:
        durations = {
            "hand_wring": 2000,
            "finger_tap": 1500,
            "sharp_head_turn": 600,
            "hand_clench": 1200,
            "slow_head_bow": 2500,
            "slight_posture_shift": 1800
        }
        return durations.get(gesture_type, 1000)
