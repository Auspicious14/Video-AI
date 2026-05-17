from typing import List, Dict, Any, Optional
from core.render_scheduler.schema import RenderJobNode, FallbackRoutes

class FallbackRouter:
    """
    Defines fallback execution paths for failed rendering jobs.
    Ensures cinematic continuity by providing safe alternatives.
    """
    
    def get_fallback_job(
        self, 
        failed_job: RenderJobNode, 
        routes: FallbackRoutes
    ) -> Optional[RenderJobNode]:
        """
        Returns a new job node that acts as a fallback for the failed one.
        Returns None if no fallback is possible or allowed.
        """
        if not routes.deterministic_fallback_enabled:
            return None
            
        if failed_job.stage == "ai_motion":
            # Fallback to deterministic FFmpeg pan/zoom
            return self._create_ffmpeg_motion_fallback(failed_job)
            
        elif failed_job.stage == "image_generation":
            # Fallback to cached asset or generic placeholder
            return self._create_asset_fallback(failed_job)
            
        elif failed_job.stage == "lipsync_processing":
            # Fallback to static performance (audio only)
            return self._create_static_performance_fallback(failed_job)
            
        return None

    def _create_ffmpeg_motion_fallback(self, failed_job: RenderJobNode) -> RenderJobNode:
        return RenderJobNode(
            job_id=f"{failed_job.job_id}_fallback_ffmpeg",
            stage="ffmpeg_composition",
            dependencies=failed_job.dependencies,
            resource_type="cpu",
            estimated_duration_sec=2,
            payload={
                **failed_job.payload,
                "fallback_mode": True,
                "composition_type": "deterministic_motion"
            }
        )

    def _create_asset_fallback(self, failed_job: RenderJobNode) -> RenderJobNode:
        return RenderJobNode(
            job_id=f"{failed_job.job_id}_fallback_asset",
            stage="ffmpeg_composition", # Use ffmpeg to just copy/placeholder
            dependencies=[],
            resource_type="cpu",
            estimated_duration_sec=1,
            payload={
                "shot_id": failed_job.payload.get("shot_id"),
                "use_placeholder": True,
                "reason": "image_gen_failed"
            }
        )

    def _create_static_performance_fallback(self, failed_job: RenderJobNode) -> RenderJobNode:
        return RenderJobNode(
            job_id=f"{failed_job.job_id}_fallback_static",
            stage="ffmpeg_composition",
            dependencies=failed_job.dependencies,
            resource_type="cpu",
            estimated_duration_sec=1,
            payload={
                **failed_job.payload,
                "skip_lipsync": True
            }
        )
