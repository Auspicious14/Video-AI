from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class DialogueBlock(BaseModel):
    character_id: str
    line: str
    emotional_subtext: str
    delivery_style: str
    pacing_style: str
    pause_before_ms: int
    pause_after_ms: int

class PerformanceBeat(BaseModel):
    timestamp_ms: int
    emotional_state: str
    intensity: float = Field(ge=0.0, le=1.0)
    body_language: str
    eye_contact_behavior: str

class FacialExpressionBeat(BaseModel):
    timestamp_ms: int
    expression: str
    intensity: float = Field(ge=0.0, le=1.0)
    transition_speed: str

class GestureBeat(BaseModel):
    timestamp_ms: int
    gesture_type: str
    intensity: float = Field(ge=0.0, le=1.0)
    duration_ms: int

class SilenceWindow(BaseModel):
    timestamp_ms: int
    duration_ms: int
    emotional_quality: str

class InterruptionPoint(BaseModel):
    timestamp_ms: int
    interrupted_character_id: str
    interrupting_character_id: str
    intensity: float

class LipSyncBeat(BaseModel):
    timestamp_ms: int
    phoneme: str
    duration_ms: int

class PerformanceSequencePlan(BaseModel):
    story_id: str
    scene_id: str
    shot_id: str
    
    dialogue_blocks: List[DialogueBlock] = Field(default_factory=list)
    performance_timeline: List[PerformanceBeat] = Field(default_factory=list)
    facial_expression_timeline: List[FacialExpressionBeat] = Field(default_factory=list)
    gesture_timeline: List[GestureBeat] = Field(default_factory=list)
    silence_windows: List[SilenceWindow] = Field(default_factory=list)
    interruption_points: List[InterruptionPoint] = Field(default_factory=list)
    lipsync_timeline: List[LipSyncBeat] = Field(default_factory=list, description="phoneme-aligned speech timing metadata")
