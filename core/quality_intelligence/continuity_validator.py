from typing import List, Dict, Any
from core.cinematic_state.models import CinematicStateGraph
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan
from core.render_orchestrator.schema import RenderExecutionPlan
from .schema import RenderOutputs, ValidationIssue

class ContinuityValidator:
    def validate(
        self,
        state_graph: CinematicStateGraph,
        scene_intent: SceneIntent,
        shot_plan: ShotPlan,
        render_execution_plan: RenderExecutionPlan,
        render_outputs: RenderOutputs
    ) -> List[ValidationIssue]:
        issues = []
        
        # 1. Validate Character Presence Consistency
        issues.extend(self._check_character_presence(shot_plan, render_outputs))
        
        # 2. Validate Emotional Progression (Discontinuities)
        issues.extend(self._check_emotional_discontinuity(shot_plan, render_outputs))
        
        # 3. Validate Environment Consistency
        issues.extend(self._check_environment_consistency(scene_intent, render_outputs))
        
        # 4. Validate Camera Language Consistency
        issues.extend(self._check_camera_consistency(shot_plan, render_outputs))
        
        return issues

    def _check_character_presence(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        shot_map = {s.shot_id: s for s in shot_plan.shots}
        
        for shot_output in render_outputs.shot_outputs:
            shot = shot_map.get(shot_output.shot_id)
            if not shot:
                continue
            
            # Check if characters planned for the shot are actually present in output metadata
            planned_chars = set(shot.performance.keys())
            detected_chars = set(shot_output.metadata.get("detected_characters", []))
            
            missing_chars = planned_chars - detected_chars
            if missing_chars:
                issues.append(ValidationIssue(
                    type="character_drift",
                    severity="high",
                    description=f"Missing characters {missing_chars} in shot {shot.shot_id}",
                    affected_shot_ids=[shot.shot_id],
                    recommended_fix="Regenerate shot with explicit character prompts."
                ))
        
        return issues

    def _check_emotional_discontinuity(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        shot_outputs = render_outputs.shot_outputs
        
        for i in range(1, len(shot_outputs)):
            prev_output = shot_outputs[i-1]
            curr_output = shot_outputs[i]
            
            prev_emotions = prev_output.metadata.get("detected_emotions", {})
            curr_emotions = curr_output.metadata.get("detected_emotions", {})
            
            for char_id, curr_emotion in curr_emotions.items():
                if char_id in prev_emotions:
                    prev_emotion = prev_emotions[char_id]
                    # Check for abrupt emotional jumps (e.g., Grief -> Joy)
                    if self._is_emotionally_inconsistent(prev_emotion, curr_emotion):
                        issues.append(ValidationIssue(
                            type="emotional_discontinuity",
                            severity="medium",
                            description=f"Abrupt emotional shift for {char_id} from {prev_emotion} to {curr_emotion}",
                            affected_shot_ids=[prev_output.shot_id, curr_output.shot_id],
                            recommended_fix="Apply emotional smoothing or regenerate with transition performance."
                        ))
        
        return issues

    def _is_emotionally_inconsistent(self, prev: str, curr: str) -> bool:
        # Define incompatible emotional pairs
        incompatible = {
            ("grief", "joy"), ("joy", "grief"),
            ("anger", "fear"), ("fear", "anger"),
            ("boredom", "excitement"), ("excitement", "boredom")
        }
        return (prev.lower(), curr.lower()) in incompatible

    def _check_environment_consistency(self, scene_intent: SceneIntent, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        target_location = scene_intent.environment_direction.location
        target_time = scene_intent.environment_direction.time_of_day
        
        for shot_output in render_outputs.shot_outputs:
            detected_location = shot_output.metadata.get("detected_location")
            detected_time = shot_output.metadata.get("detected_time_of_day")
            
            if detected_location and detected_location != target_location:
                issues.append(ValidationIssue(
                    type="environment_reset",
                    severity="critical",
                    description=f"Environment mismatch in shot {shot_output.shot_id}: expected {target_location}, got {detected_location}",
                    affected_shot_ids=[shot_output.shot_id],
                    recommended_fix="Regenerate with corrected environment seed/prompt."
                ))
            
            if detected_time and detected_time != target_time:
                issues.append(ValidationIssue(
                    type="wardrobe_inconsistency", # Often related to lighting/time changes
                    severity="medium",
                    description=f"Lighting inconsistency in shot {shot_output.shot_id}: expected {target_time}, got {detected_time}",
                    affected_shot_ids=[shot_output.shot_id],
                    recommended_fix="Adjust lighting parameters or regenerate."
                ))
        
        return issues

    def _check_camera_consistency(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        shot_map = {s.shot_id: s for s in shot_plan.shots}
        
        for shot_output in render_outputs.shot_outputs:
            shot = shot_map.get(shot_output.shot_id)
            if not shot:
                continue
            
            planned_movement = shot.camera.movement
            detected_movement = shot_output.metadata.get("detected_camera_movement")
            
            if detected_movement and detected_movement != planned_movement:
                issues.append(ValidationIssue(
                    type="camera_language_inconsistency",
                    severity="medium",
                    description=f"Camera movement mismatch in shot {shot.shot_id}: expected {planned_movement}, got {detected_movement}",
                    affected_shot_ids=[shot.shot_id],
                    recommended_fix="Verify motion parameters in render pipeline."
                ))
        
        return issues
