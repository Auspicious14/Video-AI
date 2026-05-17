from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan, Shot
from core.shot_planner.shot_decomposer import ShotDecomposer
from core.shot_planner.camera_engine import CameraEngine
from core.shot_planner.performance_engine import PerformanceEngine
from core.shot_planner.continuity_sync import ContinuitySync
from typing import List

class ShotPlannerService:
    """
    Main entry point for Phase 3: Shot Planner + Performance Engine.
    Orchestrates the full shot generation pipeline.
    """
    
    def __init__(self):
        self.decomposer = ShotDecomposer()
        self.camera_engine = CameraEngine()
        self.performance_engine = PerformanceEngine()
        self.continuity_sync = ContinuitySync()

    def generate_shot_plan(self, scene_intent: SceneIntent) -> ShotPlan:
        # 1-5. Decompose scene into shots
        shot_data_list = self.decomposer.decompose(scene_intent)
        
        shots: List[Shot] = []
        
        for i, data in enumerate(shot_data_list):
            shot_type = data["shot_type"]
            
            # 6. Map camera behavior per shot
            camera_block = self.camera_engine.generate_camera_block(scene_intent, shot_type, i)
            framing_block = self.camera_engine.generate_framing_block(scene_intent, shot_type)
            
            # 7. Generate performance instructions per character
            performance_map = {}
            dialogue_sync = None
            
            for char_id, direction in scene_intent.character_directions.items():
                performance_map[char_id] = self.performance_engine.generate_performance(char_id, direction)
                
                # 8. Attach dialogue timing and delivery style (if applicable)
                # For simplicity, we attach dialogue to the first shot or shots with dialogue intent
                if not dialogue_sync:
                    dialogue_sync = self.performance_engine.generate_dialogue_sync(scene_intent, char_id)
            
            # Environment motion from SceneIntent
            env_motion = [scene_intent.environment_direction.audio_atmosphere]
            
            shot = Shot(
                shot_id=data["shot_id"],
                shot_type=shot_type,
                duration_sec=data["duration_sec"],
                camera=camera_block,
                framing=framing_block,
                performance=performance_map,
                dialogue_sync=dialogue_sync if i == 0 else None, # Attach to first shot for now
                environment_motion=env_motion,
                transition_to_next=data["transition_to_next"]
            )
            shots.append(shot)
            
        # 9. Ensure continuity consistency across shots
        shots = self.continuity_sync.sync_shots(shots)
        
        # 10. Output ShotPlan
        return ShotPlan(
            story_id=scene_intent.story_id,
            scene_id=scene_intent.scene_id,
            shots=shots
        )

# Convenience function for external use
def generate_shot_plan(scene_intent: SceneIntent) -> ShotPlan:
    service = ShotPlannerService()
    return service.generate_shot_plan(scene_intent)
