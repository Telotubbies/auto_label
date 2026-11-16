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
    tiling: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)   # task_30: per-frame slices
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
    # Why no snapshot was stored (quota, save failure). Empty means the frames were written, so an
    # event with an empty snapshot and an empty reason is a pre-fix row, not a silent loss.
    snapshot_error: Mapped[str] = mapped_column(String(120), default="")
    predictions: Mapped[list] = mapped_column(JSON, default=list)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    # denormalised from `rule` / `predictions` so the timeline filters and pages in SQL
    rule_index: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    rule_kind: Mapped[str] = mapped_column(String(16), default="")
    rule_label: Mapped[str] = mapped_column(String(255), default="")
    classes: Mapped[str] = mapped_column(Text, default="")                   # "|person|helmet|"


class OtOutput(Base):
    """One PLC/OT endpoint that receives a binary reject signal from stream events.

    ``endpoint`` is protocol-specific (host/port/topic/node, never a credential);
    ``event_filter`` limits which rule firings may actuate this output.
    """
    __tablename__ = "ot_outputs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    protocol: Mapped[str] = mapped_column(String(16))                 # modbus | opcua | mqtt | gpio
    endpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    event_filter: Mapped[dict] = mapped_column(JSON, default=dict)    # {"kinds": [...], "classes": [...]}
    latency_budget_ms: Mapped[int] = mapped_column(Integer, default=250)
    pulse_ms: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str] = mapped_column(String(16), default="never")   # never | ok | late | failed
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)


class OtDelivery(Base):
    """One attempted reject pulse, with the latency that decided it."""
    __tablename__ = "ot_deliveries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    output_id: Mapped[str] = mapped_column(ForeignKey("ot_outputs.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(32), index=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    stream_id: Mapped[str] = mapped_column(String(32), default="")
    rule_kind: Mapped[str] = mapped_column(String(16), default="")
    event: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="ok")     # ok | late | failed
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[float] = mapped_column(Float, default=now, index=True)
