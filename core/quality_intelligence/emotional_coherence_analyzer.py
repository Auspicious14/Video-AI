from typing import List, Dict, Any
from core.shot_planner.schema import ShotPlan
from .schema import RenderOutputs, ValidationIssue

class EmotionalCoherenceAnalyzer:
    def analyze(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        
        # 1. Validate Emotional Progression (Gradual Shifts)
        issues.extend(self._validate_emotional_progression(render_outputs))
        
        # 2. Validate Silence vs Dialogue Balance
        issues.extend(self._validate_dialogue_balance(shot_plan, render_outputs))
        
        # 3. Validate Emotional Pacing
        issues.extend(self._validate_emotional_pacing(render_outputs))
        
        return issues

    def _validate_emotional_progression(self, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        outputs = render_outputs.shot_outputs
        
        for i in range(1, len(outputs)):
            prev_meta = outputs[i-1].metadata
            curr_meta = outputs[i].metadata
            
            prev_intensity = prev_meta.get("emotional_intensity", 0.5)
            curr_intensity = curr_meta.get("emotional_intensity", 0.5)
            
            # Rule: Emotional intensity jumps > 0.4 are considered non-gradual
            if abs(curr_intensity - prev_intensity) > 0.4:
                issues.append(ValidationIssue(
                    type="emotional_discontinuity",
                    severity="medium",
                    description=f"Non-gradual emotional intensity jump ({prev_intensity} -> {curr_intensity}) between shots.",
                    affected_shot_ids=[outputs[i-1].shot_id, outputs[i].shot_id],
                    recommended_fix="Add a buffer shot or adjust intensity parameters for smoother progression."
                ))
        
        return issues

    def _validate_dialogue_balance(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        # Check if dialogue-heavy scenes have enough "breathing room" (silence)
        total_duration = sum(s.duration_sec for s in shot_plan.shots)
        dialogue_duration = sum(s.duration_sec for s in shot_plan.shots if s.dialogue_sync)
        
        if total_duration > 0 and (dialogue_duration / total_duration) > 0.8:
            issues.append(ValidationIssue(
                type="pacing_problem",
                severity="low",
                description="Scene is dialogue-heavy with minimal breathing room.",
                affected_shot_ids=[s.shot_id for s in shot_plan.shots if s.dialogue_sync],
                recommended_fix="Insert a reaction shot or environment shot to allow emotional resonance."
            ))
            
        return issues

    def _validate_emotional_pacing(self, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        # Check for "robotic" emotional consistency (intensity staying exactly the same for too long)
        intensities = [o.metadata.get("emotional_intensity", 0.0) for o in render_outputs.shot_outputs]
        
        if len(intensities) >= 3:
            for i in range(len(intensities) - 2):
                if intensities[i] == intensities[i+1] == intensities[i+2] and intensities[i] != 0:
                    issues.append(ValidationIssue(
                        type="robotic_pacing",
                        severity="low",
                        description="Static emotional intensity detected across 3+ shots, feels unnatural.",
                        affected_shot_ids=[render_outputs.shot_outputs[j].shot_id for j in range(i, i+3)],
                        recommended_fix="Vary emotional micro-expressions to add human nuance."
                    ))
        
        return issues
