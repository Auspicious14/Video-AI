from typing import List, Any
from core.observability_engine.schema import AutoTuningRecommendation, PerformanceMetrics, CinematicQualityMetrics

class AutoTuner:
    """
    Adjusts system parameters dynamically based on deterministic rules.
    """
    
    def generate_tuning_recommendations(
        self,
        performance_metrics: PerformanceMetrics,
        quality_metrics: CinematicQualityMetrics
    ) -> List[AutoTuningRecommendation]:
        recommendations = []
        
        # 1. Tune Concurrency based on GPU load
        if performance_metrics.gpu_utilization_avg > 0.9:
            recommendations.append(AutoTuningRecommendation(
                parameter_name="max_concurrent_render_jobs",
                old_value="auto",
                new_value=2,
                reasoning="GPU utilization is critically high. Throttling concurrency to preserve stability."
            ))
        elif performance_metrics.gpu_utilization_avg < 0.4:
             recommendations.append(AutoTuningRecommendation(
                parameter_name="max_concurrent_render_jobs",
                old_value="auto",
                new_value=8,
                reasoning="GPU utilization is low. Increasing throughput."
            ))

        # 2. Tune Director Refinement depth based on Quality
        if quality_metrics.emotional_realism_score < 0.75:
            recommendations.append(AutoTuningRecommendation(
                parameter_name="director_refinement_iterations",
                old_value=2,
                new_value=4,
                reasoning="Emotional realism score is below threshold. Increasing agentic critique depth."
            ))

        # 3. Tune Scheduler Fallback policy
        if performance_metrics.job_failure_rate > 0.05:
            recommendations.append(AutoTuningRecommendation(
                parameter_name="scheduler_fallback_policy",
                old_value="aggressive",
                new_value="conservative",
                reasoning="High failure rate detected. Switching to conservative render strategies."
            ))

        return recommendations
