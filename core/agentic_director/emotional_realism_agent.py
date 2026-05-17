from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan

class EmotionalRealismAgent:
    """
    CRITICAL AGENT.
    Evaluates emotional authenticity, reduces melodrama, and ensures restrained human realism.
    """
    
    def __init__(self):
        self.name = "EmotionalRealismAgent"

    def review(self, scene_intent: SceneIntent, shot_plan: ShotPlan) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        # 1. Evaluate emotional intensity for melodrama
        if scene_intent.emotional_target.intensity > 0.8:
            score -= 0.2
            issues.append("Emotional intensity is dangerously high, risking melodrama.")
            recommendations.append("Reduce emotional intensity to allow for more subtle performance.")

        # 2. Check for "artificial intensity" in shot planning
        for shot in shot_plan.shots:
            if shot.camera.movement == "handheld" and shot.camera.intensity > 0.7:
                score -= 0.1
                issues.append(f"Shot {shot.shot_id} has hyperactive handheld movement.")
                recommendations.append(f"Lower handheld intensity for shot {shot.shot_id} to ground the realism.")
            
            # 3. Evaluate performance for subtle human realism
            for char_id, perf in shot.performance.items():
                if perf.intensity > 0.85:
                    score -= 0.15
                    issues.append(f"Character {char_id} performance in shot {shot.shot_id} is too loud.")
                    recommendations.append(f"Introduce restrained micro-actions for {char_id} in shot {shot.shot_id}.")

        # 4. Ensure "breathing room" (silence/stillness)
        total_duration = sum(shot.duration_sec for shot in shot_plan.shots)
        if total_duration < 3.0: # Very short scene
            score -= 0.1
            issues.append("Scene pacing is too fast for emotional resonance.")
            recommendations.append("Extend shot durations to allow emotional beats to breathe.")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
