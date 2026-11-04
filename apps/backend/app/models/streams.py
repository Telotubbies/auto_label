"""Live camera / video feeds and the rule events they fire."""
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import new_id, now


class Stream(Base):
    """A live camera / video feed processed by the StreamManager (one grabber + one processor thread)."""
    __tablename__ = "streams"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(Text)                # rtsp://… or file:videos/<name>
    model_ref: Mapped[str] = mapped_column(String(255))
    sample_fps: Mapped[float] = mapped_column(Float, default=5.0)
    zones: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="stopped")
    last_error: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[float] = mapped_column(Float, default=now)


class StreamEvent(Base):
    """One rule firing, with a JPEG snapshot and the predictions that triggered it."""
    __tablename__ = "stream_events"
    __table_args__ = (Index("ix_stream_events_stream_ts", "stream_id", "ts"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    stream_id: Mapped[str] = mapped_column(ForeignKey("streams.id", ondelete="CASCADE"), index=True)
    ts: Mapped[float] = mapped_column(Float, default=now)
    rule: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    snapshot_path: Mapped[str] = mapped_column(String(1024), default="")     # annotated, relative to DATA_DIR
    clean_path: Mapped[str] = mapped_column(String(1024), default="")        # no overlays: the dataset copy
    predictions: Mapped[list] = mapped_column(JSON, default=list)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    # denormalised from `rule` / `predictions` so the timeline filters and pages in SQL
    rule_index: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    rule_kind: Mapped[str] = mapped_column(String(16), default="")
    rule_label: Mapped[str] = mapped_column(String(255), default="")
    classes: Mapped[str] = mapped_column(Text, default="")                   # "|person|helmet|"
