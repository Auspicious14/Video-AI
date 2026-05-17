from typing import List, Dict
from core.shot_planner.schema import ShotPlan, Shot
from core.scene_intent.schema import SceneIntent
from core.memory_engine.schema import CharacterIdentityProfile

from .schema import PerformanceSequencePlan
from .dialogue_director import DialogueDirector
from .emotional_timing_engine import EmotionalTimingEngine
from .facial_expression_mapper import FacialExpressionMapper
from .gesture_director import GestureDirector
from .lipsync_coordinator import LipSyncCoordinator
from .silence_engine import SilenceEngine
from .interruption_manager import InterruptionManager

class PerformanceDialogueService:
    """
    Main entry point for Phase 8: Multimodal Performance + Dialogue Engine.
    Orchestrates the generation of synchronized, emotionally grounded cinematic performances.
    """
    
    def __init__(self):
        self.dialogue_director = DialogueDirector()
        self.emotional_timing_engine = EmotionalTimingEngine()
        self.facial_expression_mapper = FacialExpressionMapper()
        self.gesture_director = GestureDirector()
        self.lipsync_coordinator = LipSyncCoordinator()
        self.silence_engine = SilenceEngine()
        self.interruption_manager = InterruptionManager()

    def generate_performance_sequence(
        self, 
        shot_plan: ShotPlan, 
        scene_intent: SceneIntent, 
        character_profiles: List[CharacterIdentityProfile]
    ) -> List[PerformanceSequencePlan]:
        """
        Generates a multimodal performance plan for each shot in the shot plan.
        Returns a list of PerformanceSequencePlan objects.
        """
        performance_plans = []
        
        # 1. Generate overall dialogue blocks for the scene first to ensure continuity
        all_dialogue_blocks = self.dialogue_director.generate_dialogue_blocks(
            scene_intent, character_profiles
        )
        
        # 2. Process each shot in the plan
        for shot in shot_plan.shots:
            plan = self._generate_shot_performance(
                shot, scene_intent, character_profiles, all_dialogue_blocks
            )
            performance_plans.append(plan)
            
        return performance_plans

    def _generate_shot_performance(
        self,
        shot: Shot,
        scene_intent: SceneIntent,
        character_profiles: List[CharacterIdentityProfile],
        all_dialogue_blocks: List[any]
    ) -> PerformanceSequencePlan:
        """
        Internal helper to generate performance for a single shot.
        """
        # Filter dialogue blocks that belong to this shot
        # In a real system, we'd use Shot.dialogue_sync to map these
        shot_dialogue = self._filter_dialogue_for_shot(shot, all_dialogue_blocks)
        
        # 3. Generate emotional timing (PerformanceBeat timeline)
        performance_timeline = self.emotional_timing_engine.generate_performance_timeline(
            shot, scene_intent
        )
        
        # 4. Generate facial expression timeline
        facial_timeline = self.facial_expression_mapper.generate_facial_timeline(
            performance_timeline
        )
        
        # 5. Generate gesture timeline
        gesture_timeline = self.gesture_director.generate_gesture_timeline(
            shot, performance_timeline
        )
        
        # 6. Generate silence windows
        silence_windows = self.silence_engine.generate_silence_windows(
            shot, shot_dialogue
        )
        
        # 7. Generate interruption points
        interruption_points = self.interruption_manager.detect_interruption_points(
            scene_intent, shot_dialogue
        )
        
        # 8. Generate lipsync metadata
        lipsync_timeline = self.lipsync_coordinator.generate_lipsync_timeline(
            shot_dialogue
        )
        
        # 9. Return the complete PerformanceSequencePlan
        return PerformanceSequencePlan(
            story_id=scene_intent.story_id,
            scene_id=scene_intent.scene_id,
            shot_id=shot.shot_id,
            dialogue_blocks=shot_dialogue,
            performance_timeline=performance_timeline,
            facial_expression_timeline=facial_timeline,
            gesture_timeline=gesture_timeline,
            silence_windows=silence_windows,
            interruption_points=interruption_points,
            lipsync_timeline=lipsync_timeline
        )

    def _filter_dialogue_for_shot(self, shot: Shot, all_blocks: List[any]) -> List[any]:
        # Logic to map which dialogue blocks happen in which shot.
        # This typically depends on the Shot.dialogue_sync metadata.
        if not shot.dialogue_sync:
            return []
            
        # For now, we return blocks that match the character speaking in this shot
        return [b for b in all_blocks if b.character_id == shot.dialogue_sync.spoken_by]
