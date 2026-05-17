from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan

class ContinuitySupervisorAgent:
    """
    Enforces continuity constraints, detects identity drift and environment inconsistencies.
    """
    
    def __init__(self):
        self.name = "ContinuitySupervisorAgent"

    def review(self, scene_intent: SceneIntent, shot_plan: ShotPlan) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        # 1. Identity Consistency
        # Check if characters from scene intent are present in shot plan
        intent_chars = set(scene_intent.character_directions.keys())
        planned_chars = set()
        for shot in shot_plan.shots:
            planned_chars.update(shot.performance.keys())
        
        missing_chars = intent_chars - planned_chars
        if missing_chars:
            score -= 0.3
            issues.append(f"Characters {missing_chars} are in intent but missing from shot plan.")
            recommendations.append("Ensure all key characters are visually represented in the shot sequence.")

        # 2. Emotional Carry-over
        # Check if emotional intensity jumps too drastically between shots
        prev_intensity = None
        for shot in shot_plan.shots:
            for char_id, perf in shot.performance.items():
                if prev_intensity is not None and abs(perf.intensity - prev_intensity) > 0.5:
                    score -= 0.2
                    issues.append(f"Shot {shot.shot_id}: Emotional jump for {char_id} is too jarring.")
                    recommendations.append(f"Smooth emotional transition for {char_id} between shots.")
                prev_intensity = perf.intensity

        # 3. Environment Coherence
        if not scene_intent.environment_direction.location:
            score -= 0.1
            issues.append("Missing location context in scene intent.")
            recommendations.append("Define specific location to ensure environmental continuity.")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
