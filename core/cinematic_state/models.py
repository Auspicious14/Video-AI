from typing import List, Dict, Literal, Optional
from pydantic import BaseModel, Field

class CharacterState(BaseModel):
    name: str
    current_emotion: str
    emotion_intensity: float = Field(ge=0.0, le=1.0)

class NarrativeState(BaseModel):
    current_sequence: str
    current_scene_index: int
    tension: float = Field(ge=0.0, le=1.0)

class EnvironmentState(BaseModel):
    location: str
    time_of_day: str
    audio_atmosphere: str

class EmotionState(BaseModel):
    dominant_emotion: str
    intensity: float = Field(ge=0.0, le=1.0)

class ContinuityMemory(BaseModel):
    locked_facts: List[str] = Field(default_factory=list)
    last_scene_summary: str

class SequenceStatus(BaseModel):
    id: str
    status: Literal["active", "completed", "upcoming"]

class RenderState(BaseModel):
    fps: int = 30
    aspect_ratio: str = "9:16"
    last_render_status: str

class CinematicStateGraph(BaseModel):
    story_id: str
    narrative_state: NarrativeState
    characters: Dict[str, CharacterState] = Field(default_factory=dict)
    environment: EnvironmentState
    emotion_state: EmotionState
    continuity_memory: ContinuityMemory
    sequence_state: List[SequenceStatus] = Field(default_factory=list)
    render_state: RenderState

# Update Input Schema
class EmotionShift(BaseModel):
    dominant_emotion: str
    intensity_delta: float

class CharacterUpdate(BaseModel):
    character_id: str
    emotion: str
    intensity: float

class SceneResult(BaseModel):
    scene_summary: str
    emotion_shift: EmotionShift
    character_updates: List[CharacterUpdate]
    new_facts: List[str]
