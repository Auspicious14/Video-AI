from typing import List, Optional, Any
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan
from core.render_orchestrator.schema import RenderExecutionPlan
from core.agentic_director.schema import AgenticReviewReport, AgentReview
from core.agentic_director.narrative_director import NarrativeDirectorAgent
from core.agentic_director.cinematography_agent import CinematographyAgent
from core.agentic_director.performance_director import PerformanceDirectorAgent
from core.agentic_director.continuity_supervisor import ContinuitySupervisorAgent
from core.agentic_director.emotional_realism_agent import EmotionalRealismAgent
from core.agentic_director.editing_rhythm_agent import EditingRhythmAgent
from core.agentic_director.render_strategy_agent import RenderStrategyAgent
from core.agentic_director.refinement_engine import RefinementEngine
from core.agentic_director.consensus_engine import ConsensusEngine

class AgenticDirectorService:
    """
    Main orchestration layer for the Phase 7 Agentic Director System.
    Coordinates all agents, aggregates critiques, and applies refinement logic.
    """
    
    def __init__(self):
        self.narrative_agent = NarrativeDirectorAgent()
        self.cinematography_agent = CinematographyAgent()
        self.performance_agent = PerformanceDirectorAgent()
        self.continuity_agent = ContinuitySupervisorAgent()
        self.emotional_agent = EmotionalRealismAgent()
        self.editing_agent = EditingRhythmAgent()
        self.render_agent = RenderStrategyAgent()
        
        self.refinement_engine = RefinementEngine()
        self.consensus_engine = ConsensusEngine()

    def run_agentic_review_pipeline(
        self,
        state_graph: Any, # CinematicStateGraph
        scene_intent: SceneIntent,
        shot_plan: ShotPlan,
        render_execution_plan: RenderExecutionPlan,
        max_iterations: int = 2
    ) -> AgenticReviewReport:
        
        current_intent = scene_intent
        current_shot_plan = shot_plan
        current_render_plan = render_execution_plan
        
        all_reviews: List[AgentReview] = []
        iteration = 0
        
        while iteration < max_iterations:
            # 1. Run all agents in parallel (simulated here)
            reviews = [
                self.narrative_agent.review(current_intent, current_shot_plan),
                self.cinematography_agent.review(current_intent, current_shot_plan),
                self.performance_agent.review(current_intent, current_shot_plan),
                self.continuity_agent.review(current_intent, current_shot_plan),
                self.emotional_agent.review(current_intent, current_shot_plan),
                self.editing_agent.review(current_intent, current_shot_plan),
                self.render_agent.review(current_intent, current_shot_plan, current_render_plan)
            ]
            
            all_reviews = reviews # Keep the latest reviews
            
            # 2. Evaluate consensus
            score, approved, regen, actions = self.consensus_engine.evaluate_consensus(reviews)
            
            # 3. If approved or no more actions, we are done
            if approved or not actions or iteration >= max_iterations - 1:
                return AgenticReviewReport(
                    story_id=scene_intent.story_id,
                    scene_id=scene_intent.scene_id,
                    agent_reviews=all_reviews,
                    global_quality_score=score,
                    refinement_actions=actions,
                    regeneration_required=regen,
                    approved_for_render=approved
                )
            
            # 4. Apply refinements for the next iteration
            current_intent, current_shot_plan, current_render_plan = self.refinement_engine.apply_refinements(
                current_intent, current_shot_plan, current_render_plan, actions
            )
            
            iteration += 1

        # Fallback return (should not hit this due to logic above)
        return AgenticReviewReport(
            story_id=scene_intent.story_id,
            scene_id=scene_intent.scene_id,
            agent_reviews=all_reviews,
            global_quality_score=0.0,
            approved_for_render=False
        )

# Global entry point
def run_agentic_review_pipeline(
    state_graph: Any,
    scene_intent: SceneIntent,
    shot_plan: ShotPlan,
    render_execution_plan: RenderExecutionPlan
) -> AgenticReviewReport:
    service = AgenticDirectorService()
    return service.run_agentic_review_pipeline(
        state_graph, scene_intent, shot_plan, render_execution_plan
    )
