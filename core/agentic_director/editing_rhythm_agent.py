from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan

class EditingRhythmAgent:
    """
    Evaluates pacing, cut rhythm, and scene breathing room.
    """
    
    def __init__(self):
        self.name = "EditingRhythmAgent"

    def review(self, scene_intent: SceneIntent, shot_plan: ShotPlan) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        # 1. Evaluate cut frequency
        durations = [shot.duration_sec for shot in shot_plan.shots]
        if not durations:
            return AgentReview(agent_name=self.name, score=0.0, issues=["No shots found in plan."])

        avg_duration = sum(durations) / len(durations)
        
        # Too fast (TikTok style)
        if avg_duration < 1.5:
            score -= 0.3
            issues.append("Pacing is too fast; cuts are hyperactive.")
            recommendations.append("Extend shot durations to allow emotional beats to settle.")
        
        # 2. Scene "Breathing Room"
        # Check for very long static shots that might feel stagnant
        for shot in shot_plan.shots:
            if shot.duration_sec > 8.0 and shot.camera.movement == "static":
                score -= 0.1
                issues.append(f"Shot {shot.shot_id} is too long for a static frame.")
                recommendations.append(f"Add a subtle 'slow_push_in' or 'drift' to shot {shot.shot_id} to maintain visual interest.")

        # 3. Cut rhythm consistency
        # If there's a mix of extremely short and extremely long shots without clear narrative reason
        if max(durations) - min(durations) > 6.0:
            score -= 0.1
            issues.append("Jarring rhythm; inconsistent shot durations.")
            recommendations.append("Normalize shot durations unless the rhythm change is narratively justified.")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
