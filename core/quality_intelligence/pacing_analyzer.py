from typing import List, Dict, Any
from core.shot_planner.schema import ShotPlan
from .schema import RenderOutputs, ValidationIssue

class PacingAnalyzer:
    def analyze(self, shot_plan: ShotPlan, render_outputs: RenderOutputs) -> List[ValidationIssue]:
        issues = []
        
        # 1. Analyze Shot Duration Rhythm
        issues.extend(self._analyze_rhythm(shot_plan))
        
        # 2. Analyze Scene Tempo
        issues.extend(self._analyze_tempo(shot_plan))
        
        # 3. Detect Hyperactive Editing
        issues.extend(self._detect_hyperactive_editing(shot_plan))
        
        return issues

    def _analyze_rhythm(self, shot_plan: ShotPlan) -> List[ValidationIssue]:
        issues = []
        durations = [s.duration_sec for s in shot_plan.shots]
        
        if len(durations) >= 3:
            # Check for robotic rhythm (exact same duration for every shot)
            if all(d == durations[0] for d in durations):
                issues.append(ValidationIssue(
                    type="pacing_problem",
                    severity="low",
                    description="Robotic pacing detected: all shots have identical duration.",
                    affected_shot_ids=[s.shot_id for s in shot_plan.shots],
                    recommended_fix="Vary shot durations to create a more natural cinematic rhythm."
                ))
        
        return issues

    def _analyze_tempo(self, shot_plan: ShotPlan) -> List[ValidationIssue]:
        issues = []
        # Check for emotionally rushed scenes (high intensity dialogue with very short shots)
        for shot in shot_plan.shots:
            if shot.dialogue_sync and shot.duration_sec < 2.0:
                issues.append(ValidationIssue(
                    type="pacing_problem",
                    severity="medium",
                    description=f"Shot {shot.shot_id} is emotionally rushed: dialogue in < 2s shot.",
                    affected_shot_ids=[shot.shot_id],
                    recommended_fix="Extend shot duration to allow dialogue to breathe."
                ))
        return issues

    def _detect_hyperactive_editing(self, shot_plan: ShotPlan) -> List[ValidationIssue]:
        issues = []
        # Check for too many cuts in a short period
        total_duration = sum(s.duration_sec for s in shot_plan.shots)
        num_shots = len(shot_plan.shots)
        
        if total_duration > 0 and (num_shots / total_duration) > 0.8: # More than 0.8 cuts per second
            issues.append(ValidationIssue(
                type="pacing_problem",
                severity="medium",
                description="Hyperactive editing detected: excessive cuts for the scene duration.",
                affected_shot_ids=[s.shot_id for s in shot_plan.shots],
                recommended_fix="Consolidate shots or increase durations to reduce cut frequency."
            ))
            
        return issues
