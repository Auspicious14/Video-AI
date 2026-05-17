from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class ValidationIssue(BaseModel):
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    affected_shot_ids: List[str]
    recommended_fix: str

class QualityScores(BaseModel):
    overall_score: float = Field(ge=0.0, le=1.0)
    continuity_score: float = Field(ge=0.0, le=1.0)
    emotional_coherence_score: float = Field(ge=0.0, le=1.0)
    character_consistency_score: float = Field(ge=0.0, le=1.0)
    environment_consistency_score: float = Field(ge=0.0, le=1.0)
    cinematic_language_score: float = Field(ge=0.0, le=1.0)
    pacing_score: float = Field(ge=0.0, le=1.0)

class QualityValidationReport(BaseModel):
    story_id: str
    scene_id: str
    
    overall_score: float
    
    continuity_score: float
    emotional_coherence_score: float
    character_consistency_score: float
    environment_consistency_score: float
    cinematic_language_score: float
    pacing_score: float
    
    issues: List[ValidationIssue]
    recommendations: List[str]
    
    regeneration_required: bool
    fallback_recommended: bool

class RenderShotOutput(BaseModel):
    shot_id: str
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RenderOutputs(BaseModel):
    story_id: str
    scene_id: str
    shot_outputs: List[RenderShotOutput]
    final_video_path: Optional[str] = None
