from typing import List, Dict, Any
from core.shot_planner.schema import ShotPlan
from .schema import RenderOutputs, ValidationIssue

class PerformanceConsistencyChecker:
    def check(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        
        # 1. Validate Speech Delivery Consistency
        issues.extend(self._validate_speech_consistency(shot_plan, render_outputs))
        
        # 2. Validate Emotional Carry-over
        issues.extend(self._validate_emotional_carry_over(render_outputs))
        
        # 3. Validate Micro-action Continuity
        issues.extend(self._validate_micro_action_continuity(shot_plan, render_outputs))
        
        return issues

    def _validate_speech_consistency(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        shot_map = {s.shot_id: s for s in shot_plan.shots}
        
        for output in render_outputs.shot_outputs:
            shot = shot_map.get(output.shot_id)
            if not (shot and shot.dialogue_sync):
                continue
            
            planned_delivery = shot.dialogue_sync.delivery_style
            detected_delivery = output.metadata.get("detected_delivery_style")
            
            if detected_delivery and detected_delivery != planned_delivery:
                issues.append(ValidationIssue(
                    type="performance_consistency",
                    severity="high",
                    description=f"Speech delivery mismatch in shot {shot.shot_id}: expected {planned_delivery}, got {detected_delivery}",
                    affected_shot_ids=[shot.shot_id],
                    recommended_fix="Regenerate audio with correct delivery style parameters."
                ))
        
        return issues

    def _validate_emotional_carry_over(self, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        outputs = render_outputs.shot_outputs
        
        for i in range(1, len(outputs)):
            prev_emotions = outputs[i-1].metadata.get("detected_emotions", {})
            curr_emotions = outputs[i].metadata.get("detected_emotions", {})
            
            for char_id, curr_emotion in curr_emotions.items():
                if char_id in prev_emotions:
                    prev_emotion = prev_emotions[char_id]
                    # Check for "emotional residue" - character should not instantly lose high intensity tension
                    prev_intensity = outputs[i-1].metadata.get("emotional_intensity", 0.0)
                    curr_intensity = outputs[i].metadata.get("emotional_intensity", 0.0)
                    
                    if prev_intensity > 0.8 and curr_intensity < 0.3:
                        issues.append(ValidationIssue(
                            type="emotional_discontinuity",
                            severity="medium",
                            description=f"Character {char_id} dropped from high intensity ({prev_intensity}) to low intensity ({curr_intensity}) too quickly.",
                            affected_shot_ids=[outputs[i-1].shot_id, outputs[i].shot_id],
                            recommended_fix="Increase emotional residue/intensity in the following shot."
                        ))
        
        return issues

    def _validate_micro_action_continuity(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        # Check if micro-actions planned are detected in output
        shot_map = {s.shot_id: s for s in shot_plan.shots}
        
        for output in render_outputs.shot_outputs:
            shot = shot_map.get(output.shot_id)
            if not shot:
                continue
            
            for char_id, perf in shot.performance.items():
                planned_actions = set(perf.micro_actions)
                detected_actions = set(output.metadata.get("detected_micro_actions", []))
                
                missing_actions = planned_actions - detected_actions
                if missing_actions:
                    # Severity is low because micro-actions are subtle
                    issues.append(ValidationIssue(
                        type="performance_consistency",
                        severity="low",
                        description=f"Character {char_id} missing planned micro-actions: {missing_actions} in shot {shot.shot_id}",
                        affected_shot_ids=[shot.shot_id],
                        recommended_fix="Refine motion prompt to include specific micro-actions."
                    ))
        
        return issues
