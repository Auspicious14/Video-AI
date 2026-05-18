from typing import List, Any
from core.observability_engine.schema import BottleneckReport, Severity, PipelinePhase, PerformanceMetrics

class BottleneckDetector:
    """
    Detects and classifies system bottlenecks across all phases.
    """
    
    def detect_bottlenecks(
        self,
        performance_metrics: PerformanceMetrics,
        render_jobs: List[Any],
        events: List[Any]
    ) -> List[BottleneckReport]:
        bottlenecks = []
        
        # 1. Check for GPU Overload
        if performance_metrics.gpu_utilization_avg > 0.95:
            bottlenecks.append(BottleneckReport(
                type="GPU_SATURATION",
                severity=Severity.HIGH,
                description="Average GPU utilization is near 100%, causing potential scheduling delays.",
                affected_phases=[PipelinePhase.RENDER],
                root_cause_guess="Too many concurrent high-resolution render jobs.",
                recommended_fix="Reduce max_concurrent_jobs or optimize render strategy."
            ))
            
        # 2. Check for FFmpeg Bottlenecks
        ffmpeg_jobs = [j for j in render_jobs if getattr(j, 'tool', '') == 'ffmpeg']
        slow_ffmpeg = [j for j in ffmpeg_jobs if getattr(j, 'duration', 0) > 300] # > 5 mins
        if slow_ffmpeg:
            bottlenecks.append(BottleneckReport(
                type="FFMPEG_PERFORMANCE",
                severity=Severity.MEDIUM,
                description=f"Detected {len(slow_ffmpeg)} slow FFmpeg assembly jobs.",
                affected_phases=[PipelinePhase.RENDER],
                root_cause_guess="Complex codec settings or large file I/O overhead.",
                recommended_fix="Use faster preset or optimize intermediate asset resolution."
            ))
            
        # 3. Check for Pipeline Latency Spikes
        # (This would analyze events to find long gaps between phases)
        
        # 4. Check for High Failure Rate
        if performance_metrics.job_failure_rate > 0.1:
            bottlenecks.append(BottleneckReport(
                type="PIPELINE_INSTABILITY",
                severity=Severity.CRITICAL,
                description=f"Job failure rate is {performance_metrics.job_failure_rate * 100:.1f}%.",
                affected_phases=[PipelinePhase.RENDER, PipelinePhase.SCHEDULER],
                root_cause_guess="Resource exhaustion or unstable AI model endpoints.",
                recommended_fix="Implement more robust retry logic and resource circuit breakers."
            ))

        return bottlenecks
