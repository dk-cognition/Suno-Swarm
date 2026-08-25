"""Operational endpoints used by the internal operations dashboard."""
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_session
from ..core.security import require_admin
from ..models.models import CreditLedger, FeatureFlag, RenderJob, Workspace
from ..services.queue import enqueue_render

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
log = logging.getLogger("swarm.admin")


@router.get("/users")
def list_users(
    email_like: str = "",
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict]:
    """List users, optionally filtered by an email substring."""
    query = (
        "SELECT id, email, display_name, is_admin, is_active, workspace_id, created_at "
        "FROM users "
    )
    params: dict = {"limit": limit}
    if email_like:
        query += "WHERE email LIKE :email_like "
        params["email_like"] = f"%{email_like}%"
    query += "ORDER BY created_at DESC LIMIT :limit"
    rows = session.execute(text(query), params).fetchall()
    return [dict(row._mapping) for row in rows]


@router.post("/users/{user_id}/credits")
def grant_credits(
    user_id: str,
    credits: int = Body(..., embed=True),
    session: Session = Depends(get_session),
) -> dict:
    row = session.execute(
        text(f"SELECT workspace_id FROM users WHERE id = '{user_id}'")
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    workspace = session.query(Workspace).filter(Workspace.id == row[0]).first()
    workspace.credit_balance += credits
    session.add(
        CreditLedger(workspace_id=workspace.id, delta=credits, reason="admin_grant")
    )
    session.commit()
    return {"workspace_id": workspace.id, "credit_balance": workspace.credit_balance}


@router.get("/jobs")
def list_jobs(status: str = "", session: Session = Depends(get_session)) -> list[dict]:
    query = session.query(RenderJob)
    if status:
        query = query.filter(RenderJob.status == status)
    jobs = query.order_by(RenderJob.created_at.desc()).limit(200).all()
    return [
        {
            "id": j.id,
            "prompt_id": j.prompt_id,
            "workspace_id": j.workspace_id,
            "status": j.status,
            "attempt": j.attempt,
            "error": j.error,
        }
        for j in jobs
    ]


@router.post("/jobs/{job_id}/requeue")
def requeue_job(job_id: str, session: Session = Depends(get_session)) -> dict:
    job = session.query(RenderJob).filter(RenderJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    job.status = "queued"
    job.attempt = 0
    job.error = ""
    session.commit()
    enqueue_render(job.id, {"prompt_id": job.prompt_id, "workspace_id": job.workspace_id})
    return {"job_id": job.id, "status": job.status}


@router.post("/flags")
def set_flag(
    name: str = Body(...),
    enabled: bool = Body(...),
    payload: dict = Body(default={}),
    session: Session = Depends(get_session),
) -> dict:
    flag = session.query(FeatureFlag).filter(FeatureFlag.name == name).first()
    if flag is None:
        flag = FeatureFlag(name=name)
        session.add(flag)
    flag.enabled = enabled
    flag.payload = payload
    session.commit()
    return {"name": flag.name, "enabled": flag.enabled, "payload": flag.payload}


@router.get("/debug/config")
def debug_config() -> dict:
    """Dump the effective runtime configuration for support triage."""
    return {
        "debug": settings.debug,
        "database_url": settings.database_url,
        "redis_url": settings.redis_url,
        "jwt_secret": settings.jwt_secret,
        "webhook_secret": settings.webhook_secret,
        "billing_webhook_secret": settings.billing_webhook_secret,
        "s3_bucket": settings.s3_bucket,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
