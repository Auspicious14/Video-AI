from typing import List
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import Shot, FramingBlock, CameraBlock, PerformanceBlock
import uuid

class ShotDecomposer:
    """
    Responsible for breaking SceneIntent into a sequence of shots.
    Ensures emotional progression (setup -> escalation -> resolution).
    """
    
    def decompose(self, scene_intent: SceneIntent) -> List[dict]:
        # Determine number of shots (2-5)
        # For simplicity, we can use the number of scene beats or a default based on tension
        num_shots = max(2, min(5, len(scene_intent.scene_beats)))
        if num_shots < 3 and scene_intent.tension_delta > 0.5:
            num_shots = 3
            
        shots_data = []
        
        # Determine duration per shot
        total_duration = (scene_intent.camera_direction.duration_sec.min + 
                          scene_intent.camera_direction.duration_sec.max) / 2
        duration_per_shot = total_duration / num_shots
        
        for i in range(num_shots):
            shot_id = f"shot_{i+1}_{uuid.uuid4().hex[:6]}"
            
            # Map emotional beat to shot
            beat_index = int((i / num_shots) * len(scene_intent.scene_beats))
            current_beat = scene_intent.scene_beats[beat_index]
            
            # Assign shot type based on progression and emotion
            shot_type = self._determine_shot_type(i, num_shots, scene_intent)
            
            # Determine transition
            transition = "cut"
            if i == num_shots - 1:
                transition = "fade" # Last shot transitions out
            elif scene_intent.tension_delta < 0.2:
                transition = "dissolve"
            
            shots_data.append({
                "shot_id": shot_id,
                "shot_type": shot_type,
                "duration_sec": duration_per_shot,
                "beat": current_beat,
                "transition_to_next": transition
            })
            
        return shots_data

    def _determine_shot_type(self, index: int, total: int, scene_intent: SceneIntent) -> str:
        # Rule 1: Setup usually wide or medium
        if index == 0:
            return "wide" if scene_intent.tension_delta < 0.7 else "medium"
            
        # Rule 2: Escalation / Peak usually close-up or OTS
        if index == total - 2 or (total > 2 and index == 1):
            if scene_intent.emotional_target.intensity > 0.7:
                return "close_up"
            return "over_the_shoulder"
            
        # Rule 3: Resolution / Transition
        if index == total - 1:
            return "medium"
            
        return "medium"
