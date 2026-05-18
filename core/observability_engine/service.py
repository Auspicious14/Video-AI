from typing import List, Any
from core.observability_engine.schema import CinematicExecutionTrace
from core.observability_engine.trace_collector import TraceCollector
from core.observability_engine.metrics_engine import MetricsEngine
from core.observability_engine.cinematic_quality_monitor import CinematicQualityMonitor
from core.observability_engine.bottleneck_detector import BottleneckDetector
from core.observability_engine.optimization_engine import OptimizationEngine
from core.observability_engine.auto_tuner import AutoTuner

class ObservabilityService:
    """
    Main entry point for Phase 10: Cinematic Observability + Self-Optimizing Engine.
    """
    
    def __init__(self):
        self.collector = TraceCollector()
        self.metrics_engine = MetricsEngine()
        self.quality_monitor = CinematicQualityMonitor()
        self.bottleneck_detector = BottleneckDetector()
        self.optimization_engine = OptimizationEngine()
        self.auto_tuner = AutoTuner()

    def generate_execution_trace(
        self,
        story_id: str,
        state_graph: Any,
        scene_intents: List[Any],
        shot_plans: List[Any],
        render_jobs: List[Any],
        performance_outputs: List[Any]
    ) -> CinematicExecutionTrace:
        """
        Generates a full cinematic execution trace with metrics and optimization insights.
        """
        # 1. Collect and normalize events
        events = self.collector.collect_events(
            story_id, state_graph, scene_intents, shot_plans, render_jobs, performance_outputs
        )
        
        # 2. Compute performance metrics
        perf_metrics = self.metrics_engine.compute_performance_metrics(
            render_jobs, performance_outputs
        )
        
        # 3. Evaluate cinematic quality
        quality_metrics = self.quality_monitor.evaluate_quality(
            scene_intents, shot_plans, performance_outputs, render_jobs
        )
        
        # 4. Detect bottlenecks
        bottlenecks = self.bottleneck_detector.detect_bottlenecks(
            perf_metrics, render_jobs, events
        )
        
        # 5. Generate optimization suggestions
        suggestions = self.optimization_engine.generate_suggestions(
            bottlenecks, quality_metrics
        )
        
        # 6. Compute system health score
        health_score = self.optimization_engine.calculate_health_score(
            bottlenecks, quality_metrics
        )
        
        # 7. Generate auto-tuning recommendations
        tuning_recs = self.auto_tuner.generate_tuning_recommendations(
            perf_metrics, quality_metrics
        )
        
        # 8. Assemble final trace
        return CinematicExecutionTrace(
            story_id=story_id,
            full_pipeline_trace=events,
            performance_metrics=perf_metrics,
            cinematic_quality_metrics=quality_metrics,
            bottlenecks=bottlenecks,
            optimization_suggestions=suggestions,
            system_health_score=health_score,
            auto_tuning_recommendations=tuning_recs
        )
