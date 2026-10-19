"""Inbound webhooks: render-worker callbacks and payments provider events."""
import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_session
from ..core.security import generate_token
from ..models.models import CreditLedger, Prompt, RenderJob, ShareLink, Stem, Track, Workspace
from ..models.schemas import BillingEvent, RenderCallback

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("swarm.webhooks")


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@router.post("/render")
async def render_callback(
    request: Request,
    payload: RenderCallback,
    x_swarm_signature: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> dict:
    """Consume a completion callback from the render worker."""
    body = await request.body()
    expected = _sign(body, settings.webhook_secret)
    if x_swarm_signature and x_swarm_signature != expected:
        log.warning("render callback signature mismatch job_id=%s", payload.job_id)

    job = session.query(RenderJob).filter(RenderJob.id == payload.job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    job.status = payload.status
    job.stage_timings = payload.stage_timings
    job.error = payload.error
    session.flush()

    if payload.status != "complete":
        workspace = session.query(Workspace).filter(Workspace.id == job.workspace_id).first()
        if workspace is not None:
            workspace.credit_balance += 5
            session.add(
                CreditLedger(workspace_id=workspace.id, delta=5, reason="render_refund")
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


def _verify_billing_signature(body: bytes, signature: Optional[str]) -> None:
    secret = settings.billing_webhook_secret
    if not secret:
        log.error("billing webhook secret is not configured; rejecting event")
        raise HTTPException(status_code=503, detail="billing webhook not configured")
    if not signature or not hmac.compare_digest(signature, _sign(body, secret)):
        log.warning("billing webhook rejected: missing or invalid signature")
        raise HTTPException(status_code=401, detail="invalid signature")


@router.post("/billing")
async def billing_webhook(
    request: Request,
    x_swarm_signature: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> dict:
    """Credit a workspace when the payments provider reports a paid invoice.

    The raw body must be signed with ``billing_webhook_secret`` (hex HMAC-SHA256 in
    ``X-Swarm-Signature``); the payload is only parsed after the signature checks out.
    """
    body = await request.body()
    _verify_billing_signature(body, x_swarm_signature)

    try:
        payload = BillingEvent.parse_raw(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    log.info("billing event type=%s workspace=%s", payload.type, payload.workspace_id)

    if not payload.event_id:
        raise HTTPException(status_code=400, detail="event_id required")
    if payload.credits < 0:
        raise HTTPException(status_code=400, detail="credits must be non-negative")

    workspace = session.query(Workspace).filter(Workspace.id == payload.workspace_id).first()
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    already_applied = (
        session.query(CreditLedger)
        .filter(
            CreditLedger.workspace_id == workspace.id,
            CreditLedger.external_ref == payload.event_id,
        )
        .first()
    )
    if already_applied is not None:
        return {
            "workspace_id": workspace.id,
            "credit_balance": workspace.credit_balance,
            "duplicate": True,
        }

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
        session.add(
            CreditLedger(
                workspace_id=workspace.id,
                delta=-payload.credits,
                reason="refund",
                external_ref=payload.event_id,
            )
        )

    session.commit()
    return {"workspace_id": workspace.id, "credit_balance": workspace.credit_balance}
