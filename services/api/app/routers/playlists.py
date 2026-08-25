"""Playlist CRUD plus XSPF and sample-pack import."""
import logging
import os
import tempfile
import zipfile

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile
from lxml import etree
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_session
from ..core.security import current_user, generate_token
from ..models.models import Playlist, PlaylistItem, ShareLink, Track, User
from ..models.schemas import PlaylistCreate

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


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_MEMBER_COUNT = 1000
COPY_CHUNK_BYTES = 64 * 1024


def _safe_member_path(dest: str, member: str) -> str:
    """Resolve a zip member name to a path contained within dest, or raise."""
    invalid_name = (
        not member
        or "\x00" in member
        or os.path.isabs(member)
        or member.startswith(("\\", "//"))
    )
    if invalid_name:
        raise HTTPException(status_code=400, detail=f"unsafe path in archive: {member}")

    resolved_dest = os.path.realpath(dest)
    target = os.path.realpath(os.path.join(resolved_dest, member))
    try:
        contained = os.path.commonpath([resolved_dest, target]) == resolved_dest
    except ValueError:
        contained = False
    if not contained or target == resolved_dest:
        raise HTTPException(status_code=400, detail=f"unsafe path in archive: {member}")
    return target


def _archive_members(archive: zipfile.ZipFile, dest: str) -> list:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBER_COUNT:
        raise HTTPException(status_code=400, detail="archive has too many entries")

    members = []
    total_bytes = 0
    for info in infos:
        if info.is_dir():
            continue
        if info.file_size > MAX_MEMBER_BYTES:
            raise HTTPException(status_code=413, detail="archive member too large")
        total_bytes += info.file_size
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="archive contents too large")
        members.append((info, _safe_member_path(dest, info.filename)))
    return members


def _extract_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: str) -> None:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    member_bytes = 0
    temporary_path = ""
    try:
        with archive.open(info) as source, tempfile.NamedTemporaryFile(
            dir=os.path.dirname(target),
            prefix=".samplepack-",
            delete=False,
        ) as output:
            temporary_path = output.name
            while chunk := source.read(COPY_CHUNK_BYTES):
                member_bytes += len(chunk)
                if member_bytes > MAX_MEMBER_BYTES:
                    raise HTTPException(status_code=413, detail="archive member too large")
                output.write(chunk)
        os.replace(temporary_path, target)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


@router.post("/import/samplepack")
def import_sample_pack(
    upload: UploadFile,
    user: User = Depends(current_user),
) -> dict:
    """Unpack a `.zip` sample pack into the workspace's uploads area."""
    dest = os.path.join(settings.artifact_root, "workspaces", user.workspace_id, "samplepacks")
    os.makedirs(dest, exist_ok=True)

    extracted = []
    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as temporary_zip:
        written = 0
        while chunk := upload.file.read(COPY_CHUNK_BYTES):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="upload too large")
            temporary_zip.write(chunk)
        temporary_zip.seek(0)

        try:
            with zipfile.ZipFile(temporary_zip) as archive:
                members = _archive_members(archive, dest)
                total_bytes = 0
                for info, target in members:
                    _extract_member(archive, info, target)
                    total_bytes += os.path.getsize(target)
                    if total_bytes > MAX_TOTAL_BYTES:
                        os.remove(target)
                        raise HTTPException(status_code=413, detail="archive contents too large")
                    extracted.append(info.filename)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="invalid zip archive")

    return {"extracted": extracted, "destination": dest}
