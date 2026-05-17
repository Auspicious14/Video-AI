from typing import List, Dict, Any
from core.agentic_director.schema import AgentReview
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan

class NarrativeDirectorAgent:
    """
    Evaluates narrative progression, detects weak scene purpose, 
    and ensures emotional escalation and thematic coherence.
    """
    
    def __init__(self):
        self.name = "NarrativeDirectorAgent"

    def review(self, scene_intent: SceneIntent, shot_plan: ShotPlan) -> AgentReview:
        issues = []
        recommendations = []
        score = 1.0
        
        # 1. Evaluate narrative purpose
        if not scene_intent.narrative_purpose or len(scene_intent.narrative_purpose) < 10:
            score -= 0.3
            issues.append("Weak or missing narrative purpose.")
            recommendations.append("Define a clearer narrative goal for this scene.")

        # 2. Check for emotional escalation
        if scene_intent.tension_delta <= 0:
            score -= 0.2
            issues.append("Lack of emotional escalation; scene feels static.")
            recommendations.append("Increase tension delta or shift emotional target to create narrative movement.")

        # 3. Thematic coherence check (simplified deterministic logic)
        # If the scene beats don't align with the emotional target
        beat_emotions = [beat.emotion_shift for beat in scene_intent.scene_beats]
        if scene_intent.emotional_target.dominant_emotion not in " ".join(beat_emotions).lower():
            score -= 0.15
            issues.append("Scene beats do not strongly support the dominant emotional target.")
            recommendations.append("Align scene beat transitions with the target emotion.")

        return AgentReview(
            agent_name=self.name,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations
        )
