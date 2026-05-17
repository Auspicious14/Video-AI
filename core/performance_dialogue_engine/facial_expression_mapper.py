from typing import List
from core.shot_planner.schema import Shot
from .schema import FacialExpressionBeat, PerformanceBeat

class FacialExpressionMapper:
    """
    Maps emotional states into facial transitions, micro-expressions, 
    eye behavior, and expression timing.
    """
    
    def generate_facial_timeline(
        self, 
        performance_timeline: List[PerformanceBeat]
    ) -> List[FacialExpressionBeat]:
        """
        Translates a performance timeline into specific facial expression beats.
        """
        facial_timeline = []
        
        for p_beat in performance_timeline:
            # Map the general emotional state to specific facial micro-expressions
            expression = self._map_to_micro_expression(p_beat.emotional_state, p_beat.intensity)
            
            f_beat = FacialExpressionBeat(
                timestamp_ms=p_beat.timestamp_ms,
                expression=expression,
                intensity=p_beat.intensity * 0.9, # Subtle reduction for realism
                transition_speed="slow" if p_beat.intensity < 0.5 else "natural"
            )
            facial_timeline.append(f_beat)
            
        return facial_timeline

    def _map_to_micro_expression(self, emotion: str, intensity: float) -> str:
        # Realism-focused micro-expressions
        if "sadness" in emotion.lower():
            return "slight_brow_knit" if intensity < 0.5 else "lip_tremor"
        if "anger" in emotion.lower():
            return "jaw_clench" if intensity < 0.7 else "flared_nostrils"
        if "anxiety" in emotion.lower():
            return "frequent_blink"
        if "joy" in emotion.lower():
            return "eye_crinkle"
        
        return "neutral_gaze"
