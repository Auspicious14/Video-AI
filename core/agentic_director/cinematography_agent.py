from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan

class CinematographyAgent:
    """
    Evaluates camera language, shot composition, and visual storytelling coherence.
    """
    
    def __init__(self):
        self.name = "CinematographyAgent"

    def review(self, scene_intent: SceneIntent, shot_plan: ShotPlan) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        # 1. Match camera movement to emotion
        dominant_emotion = scene_intent.emotional_target.dominant_emotion.lower()
        
        for shot in shot_plan.shots:
            # Anxiety/Tension usually maps to handheld or drift
            if "anxiety" in dominant_emotion or "tension" in dominant_emotion:
                if shot.camera.movement not in ["handheld", "drift"]:
                    score -= 0.1
                    issues.append(f"Shot {shot.shot_id}: Static camera might feel too clinical for {dominant_emotion}.")
                    recommendations.append(f"Consider subtle 'drift' or 'handheld' for shot {shot.shot_id}.")
            
            # 2. Composition check
            if shot.shot_type == "close_up" and shot.framing.composition == "center":
                # Center composition in close-ups can feel too "YouTube-y" unless intentional
                score -= 0.05
                issues.append(f"Shot {shot.shot_id}: Center-framed close-up might lack cinematic depth.")
                recommendations.append(f"Try 'rule_of_thirds' for a more cinematic close-up in shot {shot.shot_id}.")

        # 3. Visual variety check
        shot_types = [shot.shot_type for shot in shot_plan.shots]
        if len(set(shot_types)) == 1 and len(shot_types) > 2:
            score -= 0.2
            issues.append("Lack of visual variety; repetitive shot types.")
            recommendations.append("Vary shot types (e.g., insert a medium shot between close-ups).")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
