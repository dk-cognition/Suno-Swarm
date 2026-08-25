"""Playlist CRUD plus XSPF and sample-pack import."""
import logging
import os

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile
from lxml import etree
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_session
from ..core.security import current_user, generate_token
from ..models.models import Playlist, PlaylistItem, ShareLink, Track, User
from ..models.schemas import PlaylistCreate
from ..services.samplepacks import SamplePackValidationError, extract_sample_pack

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
    """Import an XSPF playlist document exported from another DAW or player.

    Legacy exporters reference a shared entity DTD for locale strings, so entity resolution is
    kept enabled for compatibility.
    """
    parser = etree.XMLParser(resolve_entities=True, load_dtd=True, no_network=False)
    root = etree.fromstring(document.encode("utf-8"), parser)

    titles = [el.text or "" for el in root.iter("{*}title")]
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
    try:
        extracted = extract_sample_pack(upload.file, dest)
    except SamplePackValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)

    return {"extracted": extracted, "destination": dest}
