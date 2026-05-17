from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan

class PerformanceDirectorAgent:
    """
    Evaluates actor realism, refines gestures and speech delivery, improves emotional subtlety.
    """
    
    def __init__(self):
        self.name = "PerformanceDirectorAgent"

    def review(self, scene_intent: SceneIntent, shot_plan: ShotPlan) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        for shot in shot_plan.shots:
            for char_id, perf in shot.performance.items():
                # 1. Human realism check (micro-actions)
                if not perf.micro_actions:
                    score -= 0.15
                    issues.append(f"Shot {shot.shot_id}: Character {char_id} lacks humanizing micro-actions.")
                    recommendations.append(f"Add micro-actions like 'eye dart', 'shallow breath', or 'slight swallow' for {char_id}.")
                
                # 2. Emotional believability
                # If emotion is intense but no physical micro-actions support it
                if perf.intensity > 0.7 and len(perf.micro_actions) < 2:
                    score -= 0.1
                    issues.append(f"Shot {shot.shot_id}: {char_id}'s high-intensity emotion lacks supporting physical cues.")
                    recommendations.append(f"Add more micro-actions to support the high intensity of {char_id}.")

            # 3. Dialogue delivery check
            if shot.dialogue_sync:
                if shot.dialogue_sync.delivery_style == "steady" and scene_intent.emotional_target.intensity > 0.8:
                    score -= 0.1
                    issues.append(f"Shot {shot.shot_id}: 'Steady' delivery might feel robotic for high-intensity emotion.")
                    recommendations.append(f"Change delivery style to 'broken' or 'whispered' for shot {shot.shot_id}.")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
