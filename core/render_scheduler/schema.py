from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class ResourceRequirements(BaseModel):
    estimated_gpu_time: float = 0.0
    estimated_cpu_time: float = 0.0
    estimated_memory_mb: float = 0.0

class RetryPolicy(BaseModel):
    max_retries: int = 3
    backoff_strategy: Literal["exponential", "fixed", "linear"] = "exponential"

class FallbackRoutes(BaseModel):
    deterministic_fallback_enabled: bool = True
    ai_fallback_enabled: bool = False

class DistributedMetadata(BaseModel):
    shard_count: int = 1
    worker_assignment_strategy: Literal["round_robin", "least_loaded", "gpu_affinity"] = "least_loaded"

class RenderJobNode(BaseModel):
    job_id: str
    stage: Literal[
        "image_generation",
        "ai_motion",
        "ffmpeg_composition",
        "audio_generation",
        "lipsync_processing",
        "post_processing"
    ]
    dependencies: List[str] = Field(default_factory=list)
    resource_type: Literal["cpu", "gpu", "hybrid"]
    estimated_duration_sec: int
    payload: Dict[str, Any] = Field(description="Structured execution input (shot, scene, or performance data)")
    status: Literal["queued", "running", "completed", "failed", "retrying"] = "queued"
    error_message: Optional[str] = None

class CinematicRenderJobPlan(BaseModel):
    story_id: str
    scene_id: str
    job_graph: List[RenderJobNode]
    execution_order: List[str] = Field(description="Dependency-sorted job execution list (job_ids)")
    resource_requirements: ResourceRequirements
    priority_score: float = Field(ge=0.0, le=1.0, default=0.5)
    retry_policy: RetryPolicy
    fallback_routes: FallbackRoutes
    distributed_metadata: DistributedMetadata
