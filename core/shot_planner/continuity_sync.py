from typing import List
from core.shot_planner.schema import Shot

class ContinuitySync:
    """
    Ensures continuity across shots.
    Rules:
    - character emotion must not reset between shots
    - environment must remain stable unless explicitly changed
    - emotional intensity must evolve gradually
    """
    
    def sync_shots(self, shots: List[Shot]) -> List[Shot]:
        if not shots:
            return shots
            
        for i in range(1, len(shots)):
            prev_shot = shots[i-1]
            curr_shot = shots[i]
            
            # 1. Emotional Continuity: Ensure intensity doesn't jump too much
            for char_id, perf in curr_shot.performance.items():
                if char_id in prev_shot.performance:
                    prev_perf = prev_shot.performance[char_id]
                    
                    # Smooth out intensity jumps > 0.3
                    intensity_diff = perf.intensity - prev_perf.intensity
                    if abs(intensity_diff) > 0.3:
                        perf.intensity = prev_perf.intensity + (0.3 if intensity_diff > 0 else -0.3)
                        
            # 2. Environment Stability: Ensure motion elements don't conflict
            # (In this simple version, we just ensure the list is consistent or evolving)
            if not curr_shot.environment_motion and prev_shot.environment_motion:
                curr_shot.environment_motion = prev_shot.environment_motion.copy()
                
            # 3. Framing Consistency
            # If the subject is the same, composition shouldn't jump drastically 
            # unless it's a different shot type
            if (curr_shot.framing.subject == prev_shot.framing.subject and 
                curr_shot.shot_type == prev_shot.shot_type):
                # Keep same composition for same subject/type unless intentional shift
                pass 
                
        return shots
