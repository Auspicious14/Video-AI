from typing import List, Tuple
from core.agentic_director.schema import AgentReview, RefinementAction

class ConsensusEngine:
    """
    Aggregates scores, critiques, and approvals.
    Determines whether render is approved or regeneration is required.
    """
    
    def evaluate_consensus(
        self, 
        reviews: List[AgentReview]
    ) -> Tuple[float, bool, bool, List[RefinementAction]]:
        if not reviews:
            return 0.0, False, True, []

        # 1. Calculate global quality score (weighted)
        # EmotionalRealismAgent is critical, so it has higher weight
        weights = {
            "EmotionalRealismAgent": 2.5,
            "NarrativeDirectorAgent": 1.5,
            "CinematographyAgent": 1.0,
            "PerformanceDirectorAgent": 1.5,
            "ContinuitySupervisorAgent": 2.0,
            "EditingRhythmAgent": 1.0,
            "RenderStrategyAgent": 0.5
        }
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for review in reviews:
            weight = weights.get(review.agent_name, 1.0)
            total_weighted_score += review.score * weight
            total_weight += weight
            
        global_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

        # 2. Determine approval and regeneration
        # Approved if global score > 0.85 and no critical issues (score < 0.5 in any critical agent)
        critical_failure = any(
            review.score < 0.5 for review in reviews 
            if review.agent_name in ["EmotionalRealismAgent", "ContinuitySupervisorAgent"]
        )
        
        approved = global_score >= 0.85 and not critical_failure
        regeneration_required = global_score < 0.6 or critical_failure

        # 3. Generate structured refinement actions based on recommendations
        # This is a simplified mapping for deterministic behavior
        refinement_actions = []
        for review in reviews:
            if review.score < 0.9:
                for rec in review.recommendations:
                    action = self._map_recommendation_to_action(review.agent_name, rec)
                    if action:
                        refinement_actions.append(action)

        return global_score, approved, regeneration_required, refinement_actions

    def _map_recommendation_to_action(self, agent_name: str, recommendation: str) -> RefinementAction:
        """
        Maps a natural language recommendation to a structured RefinementAction.
        In a real system, this would be more sophisticated or use a registry.
        """
        rec_lower = recommendation.lower()
        
        if "reduce emotional intensity" in rec_lower:
            return RefinementAction(
                action_type="shift_emotional_target",
                description=recommendation,
                parameters={"intensity_adj": -0.1}
            )
        
        if "lower handheld intensity" in rec_lower:
            return RefinementAction(
                action_type="adjust_camera",
                description=recommendation,
                parameters={"intensity": 0.4}
            )

        if "add micro-actions" in rec_lower or "introduce restrained micro-actions" in rec_lower:
            return RefinementAction(
                action_type="refine_performance",
                description=recommendation,
                parameters={"add_micro_actions": ["shallow breath", "eye dart"]}
            )

        if "extend shot durations" in rec_lower:
            return RefinementAction(
                action_type="modify_pacing",
                description=recommendation,
                parameters={"duration_adj": 1.5}
            )

        if "rule_of_thirds" in rec_lower:
            return RefinementAction(
                action_type="adjust_camera",
                description=recommendation,
                parameters={"composition": "rule_of_thirds"}
            )
            
        if "consider subtle 'drift' or 'handheld'" in rec_lower:
            return RefinementAction(
                action_type="adjust_camera",
                description=recommendation,
                parameters={"movement": "drift"}
            )
            
        if "align scene beat transitions" in rec_lower:
            return RefinementAction(
                action_type="shift_emotional_target",
                description=recommendation,
                parameters={"align_beats": True}
            )
            
        if "switch" in rec_lower and "deterministic" in rec_lower:
             return RefinementAction(
                action_type="optimize_render",
                description=recommendation,
                parameters={"render_strategy": "deterministic"}
            )

        return None
