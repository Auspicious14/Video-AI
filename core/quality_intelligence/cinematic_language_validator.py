from typing import List, Dict, Any
from core.shot_planner.schema import ShotPlan
from .schema import RenderOutputs, ValidationIssue

class CinematicLanguageValidator:
    def validate(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        
        # 1. Validate Shot Progression (e.g., Wide -> Medium -> Close-up)
        issues.extend(self._validate_shot_progression(shot_plan))
        
        # 2. Validate Framing Consistency
        issues.extend(self._validate_framing_consistency(shot_plan, render_outputs))
        
        # 3. Validate Transition Appropriateness
        issues.extend(self._validate_transitions(shot_plan))
        
        # 4. Detect Camera Style Breaks
        issues.extend(self._detect_style_breaks(shot_plan))
        
        return issues

    def _validate_shot_progression(self, shot_plan: ShotPlan) -> List[ValidationIssue]:
        issues = []
        shots = shot_plan.shots
        
        for i in range(1, len(shots)):
            prev_type = shots[i-1].shot_type
            curr_type = shots[i].shot_type
            
            # Example rule: Jumping from Wide directly to Close-up without a Medium can be jarring
            if prev_type == "wide" and curr_type == "close_up":
                issues.append(ValidationIssue(
                    type="cinematic_style_break",
                    severity="low",
                    description="Abrupt jump from Wide to Close-up without transitionary Medium shot.",
                    affected_shot_ids=[shots[i-1].shot_id, shots[i].shot_id],
                    recommended_fix="Consider adding a Medium shot between Wide and Close-up."
                ))
        
        return issues

    def _validate_framing_consistency(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        shot_map = {s.shot_id: s for s in shot_plan.shots}
        
        for output in render_outputs.shot_outputs:
            shot = shot_map.get(output.shot_id)
            if not shot:
                continue
            
            planned_composition = shot.framing.composition
            detected_composition = output.metadata.get("detected_composition")
            
            if detected_composition and detected_composition != planned_composition:
                issues.append(ValidationIssue(
                    type="framing_consistency",
                    severity="medium",
                    description=f"Framing mismatch in shot {shot.shot_id}: expected {planned_composition}, got {detected_composition}",
                    affected_shot_ids=[shot.shot_id],
                    recommended_fix="Regenerate with corrected framing parameters."
                ))
        
        return issues

    def _validate_transitions(self, shot_plan: ShotPlan) -> List[ValidationIssue]:
        issues = []
        for shot in shot_plan.shots:
            # Rule: Match cuts are high risk for continuity
            if shot.transition_to_next == "match_cut":
                issues.append(ValidationIssue(
                    type="transition_appropriateness",
                    severity="low",
                    description=f"Shot {shot.shot_id} uses match_cut which requires high precision continuity.",
                    affected_shot_ids=[shot.shot_id],
                    recommended_fix="Verify visual similarity between end of current and start of next shot."
                ))
        return issues

    def _detect_style_breaks(self, shot_plan: ShotPlan) -> List[ValidationIssue]:
        issues = []
        # Check for random style shifts (e.g. handheld in a static sequence)
        movements = [s.camera.movement for s in shot_plan.shots]
        if len(movements) >= 3:
            for i in range(1, len(movements) - 1):
                if movements[i] == "handheld" and movements[i-1] == "static" and movements[i+1] == "static":
                    issues.append(ValidationIssue(
                        type="cinematic_style_break",
                        severity="medium",
                        description=f"Random handheld movement in shot {shot_plan.shots[i].shot_id} breaks static sequence rhythm.",
                        affected_shot_ids=[shot_plan.shots[i].shot_id],
                        recommended_fix="Change camera movement to static or slow_push_in to match surrounding shots."
                    ))
        return issues
