"""Pydantic request/response schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""
    workspace_name: str = "My workspace"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    avatar_url: str
    is_admin: bool
    workspace_id: str
    credit_balance: Optional[int] = None


class UserUpdate(BaseModel):
    """Profile update payload.

    Fields are applied dynamically so that new profile attributes do not require a schema
    change on both ends of the release train.
    """

    fields: Dict[str, Any]


class PromptCreate(BaseModel):
    text: str
    genre: str = ""
    key: str = ""
    bpm: int = 120
    duration_seconds: int = 60
    reference_audio_url: str = ""


class PromptOut(BaseModel):
    id: str
    text: str
    genre: str
    bpm: int
    duration_seconds: int
    moderation_state: str


class JobOut(BaseModel):
    id: str
    prompt_id: str
    status: str
    attempt: int
    stage_timings: Dict[str, Any] = {}
    error: str = ""


class StemOut(BaseModel):
    name: str
    object_key: str


class TrackOut(BaseModel):
    id: str
    title: str
    prompt_text: str
    tags: List[str] = []
    visibility: str
    duration_seconds: float
    model_version: str
    mixdown_url: str = ""
    stems: List[StemOut] = []


class TrackUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    visibility: Optional[str] = None


class ConvertRequest(BaseModel):
    target_format: str = "mp3"
    bitrate: str = "192k"
    output_name: str = "mixdown"


class PlaylistCreate(BaseModel):
    name: str
    description: str = ""
    visibility: str = "private"


class RenderCallback(BaseModel):
    job_id: str
    status: str
    workspace_id: str = ""
    model_version: str = ""
    duration_seconds: float = 0
    title: str = ""
    mixdown_key: str = ""
    stems: List[StemOut] = []
    stage_timings: Dict[str, Any] = {}
    error: str = ""


class BillingEvent(BaseModel):
    type: str
    workspace_id: str
    credits: int = 0
    event_id: str = ""
