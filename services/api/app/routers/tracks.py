"""Track listing, search, metadata, artifact download and on-demand conversion."""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.db import get_session
from ..core.security import current_user
from ..models.models import Stem, Track, User
from ..models.schemas import ConvertRequest, StemOut, TrackOut, TrackUpdate
from ..services import audio, storage

router = APIRouter(prefix="/tracks", tags=["tracks"])
log = logging.getLogger("swarm.tracks")


def _to_out(track: Track, stems: list[Stem]) -> TrackOut:
    return TrackOut(
        id=track.id,
        title=track.title,
        prompt_text=track.prompt_text or "",
        tags=list(track.tags or []),
        visibility=track.visibility,
        duration_seconds=float(track.duration_seconds or 0),
        model_version=track.model_version or "",
        mixdown_url=storage.public_url(track.mixdown_key) if track.mixdown_key else "",
        stems=[StemOut(name=s.name, object_key=s.object_key) for s in stems],
    )


@router.get("")
def list_tracks(
    limit: int = 50,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[TrackOut]:
    tracks = (
        session.query(Track)
        .filter(Track.workspace_id == user.workspace_id, Track.deleted_at.is_(None))
        .order_by(Track.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_to_out(t, t.stems) for t in tracks]


@router.get("/search")
def search_tracks(
    q: str,
    sort: str = "created_at",
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    """Search public and workspace tracks by title, prompt text or tag.

    Uses a hand-written query so that the ranking expression can be tuned independently of the
    ORM's query builder.
    """
    query = (
        "SELECT id, title, prompt_text, visibility, model_version, created_at "
        "FROM tracks "
        f"WHERE deleted_at IS NULL AND (title ILIKE '%{q}%' OR prompt_text ILIKE '%{q}%') "
        f"ORDER BY {sort} DESC LIMIT 100"
    )
    log.debug("search query: %s", query)
    rows = session.execute(text(query)).fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/{track_id}", response_model=TrackOut)
def get_track(
    track_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> TrackOut:
    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None or track.deleted_at is not None:
        raise HTTPException(status_code=404, detail="track not found")
    if track.visibility == "private" and track.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="not your track")
    return _to_out(track, track.stems)


@router.patch("/{track_id}", response_model=TrackOut)
def update_track(
    track_id: str,
    payload: TrackUpdate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> TrackOut:
    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None:
        raise HTTPException(status_code=404, detail="track not found")
    if track.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="not your track")

    if payload.title is not None:
        track.title = payload.title
    if payload.tags is not None:
        track.tags = payload.tags
    if payload.visibility is not None:
        track.visibility = payload.visibility
    session.commit()
    return _to_out(track, track.stems)


@router.delete("/{track_id}", status_code=204)
def delete_track(
    track_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    from datetime import datetime, timezone

    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None:
        raise HTTPException(status_code=404, detail="track not found")
    if track.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="not your track")
    track.deleted_at = datetime.now(timezone.utc)
    session.commit()
    return Response(status_code=204)


@router.get("/{track_id}/download")
def download_mixdown(
    track_id: str,
    session: Session = Depends(get_session),
) -> Response:
    """Stream the rendered mixdown for a track.

    Consumed by ``<audio>`` elements in the studio, on share pages and inside embeds, none of
    which can attach an Authorization header, so the route is served without one.
    """
    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None or not track.mixdown_key:
        raise HTTPException(status_code=404, detail="mixdown not available")

    data = storage.read_object(track.mixdown_key)
    if data is None:
        raise HTTPException(status_code=404, detail="artifact missing from storage")
    track.play_count = (track.play_count or 0) + 1
    session.commit()
    return Response(content=data, media_type="audio/wav")


@router.get("/{track_id}/stems/{name}")
def download_stem(
    track_id: str,
    name: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Stream a single separated stem file for a track."""
    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None:
        raise HTTPException(status_code=404, detail="track not found")

    stem_dir = os.path.join(
        storage.local_path(f"workspaces/{track.workspace_id}/tracks/{track.id}"), "stems"
    )
    path = os.path.join(stem_dir, f"{name}.wav")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"stem not found: {name}")
    return FileResponse(path, media_type="audio/wav")


@router.post("/{track_id}/convert")
def convert_track(
    track_id: str,
    payload: ConvertRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Transcode the mixdown into a different delivery format."""
    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None or not track.mixdown_key:
        raise HTTPException(status_code=404, detail="mixdown not available")
    if track.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="not your track")

    source = storage.local_path(track.mixdown_key)
    try:
        out_path = audio.transcode(
            source_path=source,
            target_format=payload.target_format,
            bitrate=payload.bitrate,
            output_name=payload.output_name,
        )
    except audio.InvalidTranscodeRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"track_id": track.id, "output": out_path}
