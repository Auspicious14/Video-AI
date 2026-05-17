from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan
from core.render_orchestrator.schema import RenderExecutionPlan

class RenderStrategyAgent:
    """
    Optimizes rendering choices, decides deterministic vs generative rendering, 
    optimizes GPU/resource usage.
    """
    
    def __init__(self):
        self.name = "RenderStrategyAgent"

    def review(
        self, 
        scene_intent: SceneIntent, 
        shot_plan: ShotPlan, 
        render_execution_plan: RenderExecutionPlan
    ) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        # 1. Evaluate AI Motion usage
        ai_motion_count = sum(1 for shot in render_execution_plan.shots if shot.render_strategy == "ai_motion")
        if ai_motion_count > len(render_execution_plan.shots) * 0.8:
            # Over-reliance on AI motion can be expensive and sometimes less stable than deterministic
            score -= 0.1
            issues.append("High reliance on AI motion; potentially inefficient resource usage.")
            recommendations.append("Consider 'deterministic' or 'hybrid' strategies for simpler shots to save resources.")

        # 2. Check for missing asset requirements
        for shot in render_execution_plan.shots:
            if shot.asset_requirements.requires_voice and not shot.audio_plan.tts_provider:
                score -= 0.2
                issues.append(f"Shot {shot.shot_id} requires voice but no TTS provider is specified.")
                recommendations.append(f"Specify a TTS provider for shot {shot.shot_id}.")

        # 3. Deterministic rendering preservation
        # If a shot is a static close-up, AI motion might be overkill
        for shot_p, shot_r in zip(shot_plan.shots, render_execution_plan.shots):
            if shot_p.camera.movement == "static" and shot_r.render_strategy == "ai_motion":
                score -= 0.05
                issues.append(f"Shot {shot_r.shot_id}: AI motion might be unnecessary for a static camera.")
                recommendations.append(f"Switch shot {shot_r.shot_id} to 'deterministic' or 'hybrid' to preserve realism and reduce cost.")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
