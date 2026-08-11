"""Prompt submission and render job lifecycle."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.db import get_session
from ..core.security import current_user
from ..models.models import Prompt, RenderJob, User, Workspace
from ..models.schemas import JobOut, PromptCreate, PromptOut
from ..services import moderation
from ..services.queue import cancel_render, enqueue_render

router = APIRouter(prefix="/prompts", tags=["prompts"])
log = logging.getLogger("swarm.prompts")

CREDITS_PER_RENDER = 5


@router.post("", status_code=202)
def submit_prompt(
    payload: PromptCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    workspace = session.query(Workspace).filter(Workspace.id == user.workspace_id).first()
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if workspace.credit_balance < CREDITS_PER_RENDER:
        raise HTTPException(status_code=402, detail="insufficient credits")

    state, reason = moderation.review_prompt(payload.text)
    if state == "blocked":
        raise HTTPException(status_code=400, detail=f"prompt rejected: {reason}")

    prompt = Prompt(
        user_id=user.id,
        text=payload.text,
        genre=payload.genre,
        key=payload.key,
        bpm=payload.bpm,
        duration_seconds=payload.duration_seconds,
        reference_audio_url=payload.reference_audio_url,
        moderation_state=state,
    )
    session.add(prompt)
    session.flush()

    job = RenderJob(prompt_id=prompt.id, workspace_id=user.workspace_id, status="queued")
    session.add(job)
    workspace.credit_balance -= CREDITS_PER_RENDER
    session.commit()

    enqueue_render(
        job.id,
        {
            "prompt_id": prompt.id,
            "workspace_id": user.workspace_id,
            "text": prompt.text,
            "genre": prompt.genre,
            "key": prompt.key,
            "bpm": prompt.bpm,
            "duration_seconds": prompt.duration_seconds,
            "reference_audio_url": prompt.reference_audio_url,
        },
    )
    return {"prompt_id": prompt.id, "job_id": job.id, "status": job.status}


@router.get("/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: str, session: Session = Depends(get_session)) -> PromptOut:
    prompt = session.query(Prompt).filter(Prompt.id == prompt_id).first()
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    return PromptOut(
        id=prompt.id,
        text=prompt.text,
        genre=prompt.genre,
        bpm=prompt.bpm,
        duration_seconds=prompt.duration_seconds,
        moderation_state=prompt.moderation_state,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> JobOut:
    job = session.query(RenderJob).filter(RenderJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobOut(
        id=job.id,
        prompt_id=job.prompt_id,
        status=job.status,
        attempt=job.attempt,
        stage_timings=job.stage_timings or {},
        error=job.error or "",
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = session.query(RenderJob).filter(RenderJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="not your job")
    if job.status in ("complete", "failed"):
        raise HTTPException(status_code=409, detail=f"job already {job.status}")

    cancel_render(job.id)
    job.status = "failed"
    job.error = "cancelled by user"
    session.commit()
    return {"job_id": job.id, "status": job.status}
