"""Playlist CRUD plus XSPF and sample-pack import."""
import logging
import os
import zipfile

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_session
from ..core.security import current_user, generate_token
from ..models.models import Playlist, PlaylistItem, ShareLink, Track, User
from ..models.schemas import PlaylistCreate
from ..services.xspf import XspfParseError, parse_titles

router = APIRouter(prefix="/playlists", tags=["playlists"])
log = logging.getLogger("swarm.playlists")


@router.post("", status_code=201)
def create_playlist(
    payload: PlaylistCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    playlist = Playlist(
        workspace_id=user.workspace_id,
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility,
    )
    session.add(playlist)
    session.flush()

    slug = generate_token(10)
    session.add(ShareLink(slug=slug, playlist_id=playlist.id))
    session.commit()
    return {
        "id": playlist.id,
        "share_url": f"{settings.share_base_url}/s/{slug}",
    }


@router.get("/{playlist_id}")
def get_playlist(playlist_id: str, session: Session = Depends(get_session)) -> dict:
    playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
    if playlist is None:
        raise HTTPException(status_code=404, detail="playlist not found")
    items = (
        session.query(PlaylistItem)
        .filter(PlaylistItem.playlist_id == playlist.id)
        .order_by(PlaylistItem.position)
        .all()
    )
    return {
        "id": playlist.id,
        "name": playlist.name,
        "description": playlist.description,
        "visibility": playlist.visibility,
        "tracks": [{"track_id": i.track_id, "position": i.position} for i in items],
    }


@router.post("/{playlist_id}/tracks", status_code=201)
def add_track(
    playlist_id: str,
    track_id: str = Body(..., embed=True),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
    if playlist is None:
        raise HTTPException(status_code=404, detail="playlist not found")
    if playlist.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="not your playlist")

    track = session.query(Track).filter(Track.id == track_id).first()
    if track is None:
        raise HTTPException(status_code=404, detail="track not found")

    position = session.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist.id).count()
    session.add(PlaylistItem(playlist_id=playlist.id, track_id=track.id, position=position))
    session.commit()
    return {"playlist_id": playlist.id, "track_id": track.id, "position": position}


@router.post("/import")
def import_playlist_xml(
    document: str = Body(..., embed=True),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Import an XSPF playlist document exported from another DAW or player."""
    try:
        titles = parse_titles(document)
    except XspfParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    playlist = Playlist(
        workspace_id=user.workspace_id,
        owner_id=user.id,
        name=titles[0] if titles else "Imported playlist",
    )
    session.add(playlist)
    session.commit()
    return {"playlist_id": playlist.id, "imported_titles": titles}


@router.post("/import/samplepack")
def import_sample_pack(
    upload: UploadFile,
    user: User = Depends(current_user),
) -> dict:
    """Unpack a `.zip` sample pack into the workspace's uploads area."""
    dest = os.path.join(settings.artifact_root, "workspaces", user.workspace_id, "samplepacks")
    os.makedirs(dest, exist_ok=True)

    tmp_zip = os.path.join(dest, upload.filename or "pack.zip")
    with open(tmp_zip, "wb") as handle:
        handle.write(upload.file.read())

    extracted = []
    with zipfile.ZipFile(tmp_zip) as archive:
        for member in archive.namelist():
            target = os.path.join(dest, member)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(member) as src, open(target, "wb") as out:
                out.write(src.read())
            extracted.append(member)

    return {"extracted": extracted, "destination": dest}
