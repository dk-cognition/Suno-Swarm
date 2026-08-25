"""SQLAlchemy models for the Suno-Swarm domain."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    plan = Column(String, default="free")
    credit_balance = Column(Integer, default=50)
    created_at = Column(DateTime(timezone=True), default=_now)

    users = relationship("User", back_populates="workspace")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, default="")
    avatar_url = Column(String, default="")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    refresh_token = Column(String, default="")
    reset_token = Column(String, default="")
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    workspace = relationship("Workspace", back_populates="users")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    genre = Column(String, default="")
    key = Column(String, default="")
    bpm = Column(Integer, default=120)
    duration_seconds = Column(Integer, default=60)
    reference_audio_url = Column(String, default="")
    moderation_state = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), default=_now)


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(String, primary_key=True, default=_uuid)
    prompt_id = Column(String, ForeignKey("prompts.id"), nullable=False)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    status = Column(String, default="queued")
    attempt = Column(Integer, default=0)
    stage_timings = Column(JSON, default=dict)
    error = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class Track(Base):
    __tablename__ = "tracks"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    job_id = Column(String, ForeignKey("render_jobs.id"))
    title = Column(String, default="Untitled")
    prompt_text = Column(Text, default="")
    tags = Column(ARRAY(String), default=list)
    visibility = Column(String, default="private")
    duration_seconds = Column(Numeric(8, 2), default=0)
    model_version = Column(String, default="")
    mixdown_key = Column(String, default="")
    play_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    stems = relationship("Stem", back_populates="track")


class Stem(Base):
    __tablename__ = "stems"

    id = Column(String, primary_key=True, default=_uuid)
    track_id = Column(String, ForeignKey("tracks.id"), nullable=False)
    name = Column(String, nullable=False)
    object_key = Column(String, nullable=False)

    track = relationship("Track", back_populates="stems")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, default="New playlist")
    description = Column(Text, default="")
    visibility = Column(String, default="private")
    created_at = Column(DateTime(timezone=True), default=_now)

    items = relationship("PlaylistItem", back_populates="playlist")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id = Column(String, primary_key=True, default=_uuid)
    playlist_id = Column(String, ForeignKey("playlists.id"), nullable=False)
    track_id = Column(String, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, default=0)

    playlist = relationship("Playlist", back_populates="items")


class ShareLink(Base):
    __tablename__ = "share_links"

    slug = Column(String, primary_key=True)
    track_id = Column(String, ForeignKey("tracks.id"), nullable=True)
    playlist_id = Column(String, ForeignKey("playlists.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    external_ref = Column(String, default="")
    created_at = Column(DateTime(timezone=True), default=_now)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    name = Column(String, primary_key=True)
    enabled = Column(Boolean, default=False)
    payload = Column(JSON, default=dict)
