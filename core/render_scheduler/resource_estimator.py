from typing import List
from core.render_scheduler.schema import RenderJobNode, ResourceRequirements

class ResourceEstimator:
    """
    Estimates GPU, CPU, and Memory requirements for rendering jobs.
    Deterministic based on job type and payload parameters.
    """
    
    def estimate_job_resources(self, job: RenderJobNode) -> ResourceRequirements:
        """
        Calculates estimated resources for a specific job node.
        """
        if job.stage == "image_generation":
            return ResourceRequirements(
                estimated_gpu_time=5.0,
                estimated_cpu_time=1.0,
                estimated_memory_mb=4000.0
            )
        elif job.stage == "ai_motion":
            return ResourceRequirements(
                estimated_gpu_time=15.0,
                estimated_cpu_time=2.0,
                estimated_memory_mb=8000.0
            )
        elif job.stage == "audio_generation":
            return ResourceRequirements(
                estimated_gpu_time=2.0,
                estimated_cpu_time=0.5,
                estimated_memory_mb=1000.0
            )
        elif job.stage == "lipsync_processing":
            return ResourceRequirements(
                estimated_gpu_time=10.0,
                estimated_cpu_time=1.0,
                estimated_memory_mb=2000.0
            )
        elif job.stage == "ffmpeg_composition":
            # Composition depends on duration
            duration = job.payload.get("duration_sec", 1.0)
            return ResourceRequirements(
                estimated_gpu_time=0.0,
                estimated_cpu_time=0.5 * duration,
                estimated_memory_mb=512.0
            )
        elif job.stage == "post_processing":
            return ResourceRequirements(
                estimated_gpu_time=1.0,
                estimated_cpu_time=1.0,
                estimated_memory_mb=1000.0
            )
        
        return ResourceRequirements()

    def estimate_total_requirements(self, jobs: List[RenderJobNode]) -> ResourceRequirements:
        """
        Aggregates total resource requirements for a set of jobs.
        """
        total = ResourceRequirements()
        for job in jobs:
            est = self.estimate_job_resources(job)
            total.estimated_gpu_time += est.estimated_gpu_time
            total.estimated_cpu_time += est.estimated_cpu_time
            total.estimated_memory_mb = max(total.estimated_memory_mb, est.estimated_memory_mb)
            
        return total
