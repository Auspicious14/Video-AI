from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class EmotionalTarget(BaseModel):
    dominant_emotion: str
    intensity: float = Field(ge=0.0, le=1.0)

class CharacterDirection(BaseModel):
    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)
    behavior_notes: List[str] = Field(default_factory=list)

class SceneBeat(BaseModel):
    beat: str
    emotion_shift: str

class EnvironmentDirection(BaseModel):
    location: str
    time_of_day: str
    audio_atmosphere: str

class CameraDuration(BaseModel):
    min: int
    max: int

class CameraDirection(BaseModel):
    style: str
    shot_type: str
    movement: str
    duration_sec: CameraDuration

class DialogueIntent(BaseModel):
    character_id: str
    intent: str
    tone: str

class ContinuityUpdates(BaseModel):
    new_facts: List[str] = Field(default_factory=list)
    resolved_facts: List[str] = Field(default_factory=list)

class SceneIntent(BaseModel):
    story_id: str
    scene_id: str
    sequence_id: str
    
    narrative_purpose: str
    
    emotional_target: EmotionalTarget
    tension_delta: float
    
    character_directions: Dict[str, CharacterDirection]
    scene_beats: List[SceneBeat]
    
    environment_direction: EnvironmentDirection
    camera_direction: CameraDirection
    
    dialogue_intent: List[DialogueIntent]
    
    continuity_updates: ContinuityUpdates
