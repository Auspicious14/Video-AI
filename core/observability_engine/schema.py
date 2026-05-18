from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PipelinePhase(str, Enum):
    STATE = "state"
    INTENT = "intent"
    SHOTS = "shots"
    RENDER = "render"
    SCHEDULER = "scheduler"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    MEMORY = "memory"
    DIRECTOR = "director"

class PipelineEvent(BaseModel):
    event_id: str
    phase: PipelinePhase
    timestamp: int
    actor: str
    action: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PerformanceMetrics(BaseModel):
    total_render_time_sec: float
    gpu_utilization_avg: float
    cpu_utilization_avg: float
    memory_peak: float
    job_failure_rate: float

class CinematicQualityMetrics(BaseModel):
    emotional_realism_score: float
    continuity_score: float
    pacing_score: float
    character_consistency_score: float
    visual_coherence_score: float

class BottleneckReport(BaseModel):
    type: str
    severity: Severity
    description: str
    affected_phases: List[PipelinePhase]
    root_cause_guess: str
    recommended_fix: str

class OptimizationSuggestion(BaseModel):
    id: str
    title: str
    description: str
    target_phase: PipelinePhase
    expected_impact: str
    causal_evidence: str

class AutoTuningRecommendation(BaseModel):
    parameter_name: str
    old_value: Any
    new_value: Any
    reasoning: str

class CinematicExecutionTrace(BaseModel):
    story_id: str
    full_pipeline_trace: List[PipelineEvent]
    performance_metrics: PerformanceMetrics
    cinematic_quality_metrics: CinematicQualityMetrics
    bottlenecks: List[BottleneckReport]
    optimization_suggestions: List[str]
    system_health_score: float = Field(ge=0.0, le=1.0)
    auto_tuning_recommendations: List[AutoTuningRecommendation]
