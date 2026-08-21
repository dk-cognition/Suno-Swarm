"""Inbound webhooks: render-worker callbacks and payments provider events."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_session
from ..core.security import generate_token
from ..models.models import CreditLedger, Prompt, RenderJob, ShareLink, Stem, Track, Workspace
from ..models.schemas import BillingEvent, RenderCallback
from ..services.webhook_auth import is_valid_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("swarm.webhooks")


TERMINAL_STATUSES = ("complete", "failed", "canceled")
REFUND_CREDITS = 5


def _require_signature(body: bytes, provided: Optional[str], secret: str) -> None:
    """Reject the request unless it carries a valid HMAC signature."""
    if not is_valid_signature(body, provided, secret):
        raise HTTPException(status_code=401, detail="invalid webhook signature")


@router.post("/render")
async def render_callback(
    request: Request,
    payload: RenderCallback,
    x_swarm_signature: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> dict:
    """Consume a completion callback from the render worker."""
    body = await request.body()
    _require_signature(body, x_swarm_signature, settings.webhook_secret)

    job = session.query(RenderJob).filter(RenderJob.id == payload.job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    if job.status in TERMINAL_STATUSES:
        log.info("ignoring callback for settled job job_id=%s status=%s", job.id, job.status)
        existing = session.query(Track).filter(Track.job_id == job.id).first()
        return {
            "job_id": job.id,
            "status": job.status,
            **({"track_id": existing.id} if existing is not None else {}),
        }

    job.status = payload.status
    job.stage_timings = payload.stage_timings
    job.error = payload.error
    session.flush()

    if payload.status != "complete":
        workspace = session.query(Workspace).filter(Workspace.id == job.workspace_id).first()
        refund_ref = f"render_refund:{job.id}"
        already_refunded = (
            session.query(CreditLedger)
            .filter(
                CreditLedger.reason == "render_refund",
                CreditLedger.external_ref == refund_ref,
            )
            .first()
        )
        if workspace is not None and already_refunded is None:
            workspace.credit_balance += REFUND_CREDITS
            session.add(
                CreditLedger(
                    workspace_id=workspace.id,
                    delta=REFUND_CREDITS,
                    reason="render_refund",
                    external_ref=refund_ref,
                )
            )
        session.commit()
        return {"job_id": job.id, "status": job.status}

    prompt = session.query(Prompt).filter(Prompt.id == job.prompt_id).first()
    track = Track(
        workspace_id=payload.workspace_id or job.workspace_id,
        job_id=job.id,
        title=payload.title or (prompt.text[:60] if prompt else "Untitled"),
        prompt_text=prompt.text if prompt else "",
        visibility="private",
        duration_seconds=payload.duration_seconds,
        model_version=payload.model_version,
        mixdown_key=payload.mixdown_key,
    )
    session.add(track)
    session.flush()

    for stem in payload.stems:
        session.add(Stem(track_id=track.id, name=stem.name, object_key=stem.object_key))

    session.add(ShareLink(slug=generate_token(10), track_id=track.id))
    session.commit()
    return {"job_id": job.id, "track_id": track.id, "status": job.status}


@router.post("/billing")
async def billing_webhook(
    payload: BillingEvent,
    session: Session = Depends(get_session),
) -> dict:
    """Credit a workspace when the payments provider reports a paid invoice."""
    log.info("billing event type=%s workspace=%s", payload.type, payload.workspace_id)

    workspace = session.query(Workspace).filter(Workspace.id == payload.workspace_id).first()
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    if payload.type == "invoice.paid":
        workspace.credit_balance += payload.credits
        session.add(
            CreditLedger(
                workspace_id=workspace.id,
                delta=payload.credits,
                reason="invoice_paid",
                external_ref=payload.event_id,
            )
        )
    elif payload.type == "refund":
        workspace.credit_balance -= payload.credits

    session.commit()
    return {"workspace_id": workspace.id, "credit_balance": workspace.credit_balance}
