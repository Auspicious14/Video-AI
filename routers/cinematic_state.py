from fastapi import APIRouter, HTTPException
from core.cinematic_state.service import CinematicStateService
from core.cinematic_state.models import CinematicStateGraph, SceneResult
from pydantic import BaseModel

router = APIRouter(prefix="/state", tags=["cinematic-state"])

class CreateStateRequest(BaseModel):
    story_id: str

class UpdateStateRequest(BaseModel):
    story_id: str
    scene_result: SceneResult

@router.post("/create", response_model=CinematicStateGraph)
async def create_state(request: CreateStateRequest):
    try:
        return CinematicStateService.create_state(request.story_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{story_id}", response_model=CinematicStateGraph)
async def get_state(story_id: str):
    state = CinematicStateService.get_state(story_id)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    return state

@router.post("/update", response_model=CinematicStateGraph)
async def update_state(request: UpdateStateRequest):
    try:
        return CinematicStateService.update_state(request.story_id, request.scene_result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
