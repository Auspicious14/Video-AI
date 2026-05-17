from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AgentReview(BaseModel):
    agent_name: str
    score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class RefinementAction(BaseModel):
    action_type: str  # e.g., "adjust_camera", "refine_performance", "modify_pacing"
    description: str
    target_shot_ids: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)

class AgenticReviewReport(BaseModel):
    story_id: str
    scene_id: str
    
    agent_reviews: List[AgentReview] = Field(default_factory=list)
    global_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    refinement_actions: List[RefinementAction] = Field(default_factory=list)
    
    regeneration_required: bool = False
    approved_for_render: bool = False
