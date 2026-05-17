from typing import List
from core.cinematic_state.models import CinematicStateGraph
from core.scene_intent.schema import SceneIntent
from core.shot_planner.schema import ShotPlan
from core.render_orchestrator.schema import RenderExecutionPlan
from .schema import RenderOutputs, QualityValidationReport, ValidationIssue
from .continuity_validator import ContinuityValidator
from .emotional_coherence_analyzer import EmotionalCoherenceAnalyzer
from .cinematic_language_validator import CinematicLanguageValidator
from .performance_consistency_checker import PerformanceConsistencyChecker
from .pacing_analyzer import PacingAnalyzer
from .scoring_engine import ScoringEngine
from .fallback_recommender import FallbackRecommender

class QualityIntelligenceService:
    def __init__(self):
        self.continuity_validator = ContinuityValidator()
        self.emotional_analyzer = EmotionalCoherenceAnalyzer()
        self.cinematic_validator = CinematicLanguageValidator()
        self.performance_checker = PerformanceConsistencyChecker()
        self.pacing_analyzer = PacingAnalyzer()
        self.scoring_engine = ScoringEngine()
        self.fallback_recommender = FallbackRecommender()

    def validate_render_output(
        self,
        state_graph: CinematicStateGraph,
        scene_intent: SceneIntent,
        shot_plan: ShotPlan,
        render_execution_plan: RenderExecutionPlan,
        render_outputs: RenderOutputs
    ) -> QualityValidationReport:
        """
        Main entry point for Phase 5: Continuity + Quality Intelligence.
        Validates the cinematic coherence of rendered outputs.
        """
        
        all_issues: List[ValidationIssue] = []
        
        # 1. Validate Continuity
        all_issues.extend(self.continuity_validator.validate(
            state_graph, scene_intent, shot_plan, render_execution_plan, render_outputs
        ))
        
        # 2. Analyze Emotional Coherence
        all_issues.extend(self.emotional_analyzer.analyze(shot_plan, render_outputs))
        
        # 3. Validate Cinematic Language
        all_issues.extend(self.cinematic_validator.validate(shot_plan, render_outputs))
        
        # 4. Check Performance Consistency
        all_issues.extend(self.performance_checker.check(shot_plan, render_outputs))
        
        # 5. Analyze Pacing
        all_issues.extend(self.pacing_analyzer.analyze(shot_plan, render_outputs))
        
        # 6. Compute Quality Scores
        scores = self.scoring_engine.compute_scores(all_issues)
        
        # 7. Generate Recommendations & Strategy
        regeneration_required, fallback_recommended, recommendations = self.fallback_recommender.determine_strategy(
            scores, all_issues
        )
        
        # 8. Return Final Report
        return QualityValidationReport(
            story_id=state_graph.story_id,
            scene_id=scene_intent.scene_id,
            overall_score=scores.overall_score,
            continuity_score=scores.continuity_score,
            emotional_coherence_score=scores.emotional_coherence_score,
            character_consistency_score=scores.character_consistency_score,
            environment_consistency_score=scores.environment_consistency_score,
            cinematic_language_score=scores.cinematic_language_score,
            pacing_score=scores.pacing_score,
            issues=all_issues,
            recommendations=recommendations,
            regeneration_required=regeneration_required,
            fallback_recommended=fallback_recommended
        )

# Singleton instance for easy access
service = QualityIntelligenceService()

def validate_render_output(
    state_graph: CinematicStateGraph,
    scene_intent: SceneIntent,
    shot_plan: ShotPlan,
    render_execution_plan: RenderExecutionPlan,
    render_outputs: RenderOutputs
) -> QualityValidationReport:
    return service.validate_render_output(
        state_graph, scene_intent, shot_plan, render_execution_plan, render_outputs
    )
