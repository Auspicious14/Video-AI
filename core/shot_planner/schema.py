from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

class CameraBlock(BaseModel):
    movement: Literal["static", "slow_push_in", "handheld", "pan", "tilt", "drift"]
    intensity: float = Field(ge=0.0, le=1.0)
    lens_style: Literal["shallow_depth", "deep_focus", "cinematic_standard"]

class PerformanceBlock(BaseModel):
    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)
    micro_actions: List[str]

class DialogueSyncBlock(BaseModel):
    spoken_by: str
    line_intent: str
    delivery_style: Literal["slow", "broken", "steady", "whispered"]

class FramingBlock(BaseModel):
    subject: str
    composition: Literal["center", "rule_of_thirds", "off_center"]

class Shot(BaseModel):
    shot_id: str
    shot_type: Literal["close_up", "medium", "wide", "over_the_shoulder", "insert"]
    duration_sec: float
    
    camera: CameraBlock
    framing: FramingBlock
    
    performance: Dict[str, PerformanceBlock] = Field(
        description="character_id -> PerformanceBlock"
    )
    
    dialogue_sync: Optional[DialogueSyncBlock] = None
    
    environment_motion: List[str] = Field(default_factory=list)
    
    transition_to_next: Literal["cut", "fade", "dissolve", "match_cut"]

class ShotPlan(BaseModel):
    story_id: str
    scene_id: str
    shots: List[Shot]
