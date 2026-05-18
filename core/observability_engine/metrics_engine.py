from typing import List, Any
from core.observability_engine.schema import PerformanceMetrics

class MetricsEngine:
    """
    Computes performance metrics across the pipeline.
    Must be deterministic and reproducible.
    """
    
    def compute_performance_metrics(
        self,
        render_jobs: List[Any],
        performance_outputs: List[Any]
    ) -> PerformanceMetrics:
        
        total_render_time = self._calculate_total_render_time(render_jobs)
        gpu_util = self._calculate_avg_gpu_utilization(render_jobs)
        cpu_util = self._calculate_avg_cpu_utilization(render_jobs)
        memory_peak = self._calculate_peak_memory(render_jobs)
        failure_rate = self._calculate_failure_rate(render_jobs)
        
        return PerformanceMetrics(
            total_render_time_sec=total_render_time,
            gpu_utilization_avg=gpu_util,
            cpu_utilization_avg=cpu_util,
            memory_peak=memory_peak,
            job_failure_rate=failure_rate
        )

    def _calculate_total_render_time(self, render_jobs: List[Any]) -> float:
        if not render_jobs:
            return 0.0
        
        start_times = [getattr(j, 'started_at', None) for j in render_jobs if getattr(j, 'started_at', None)]
        end_times = [getattr(j, 'finished_at', None) for j in render_jobs if getattr(j, 'finished_at', None)]
        
        if not start_times or not end_times:
            return 0.0
            
        return float(max(end_times) - min(start_times))

    def _calculate_avg_gpu_utilization(self, render_jobs: List[Any]) -> float:
        utils = [getattr(j, 'gpu_util', 0.0) for j in render_jobs if hasattr(j, 'gpu_util')]
        return sum(utils) / len(utils) if utils else 0.0

    def _calculate_avg_cpu_utilization(self, render_jobs: List[Any]) -> float:
        utils = [getattr(j, 'cpu_util', 0.0) for j in render_jobs if hasattr(j, 'cpu_util')]
        return sum(utils) / len(utils) if utils else 0.0

    def _calculate_peak_memory(self, render_jobs: List[Any]) -> float:
        memories = [getattr(j, 'peak_memory_mb', 0.0) for j in render_jobs if hasattr(j, 'peak_memory_mb')]
        return max(memories) if memories else 0.0

    def _calculate_failure_rate(self, render_jobs: List[Any]) -> float:
        if not render_jobs:
            return 0.0
        failed = [j for j in render_jobs if getattr(j, 'status', '') == 'failed']
        return len(failed) / len(render_jobs)
