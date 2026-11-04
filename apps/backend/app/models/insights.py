"""Insights dashboards, metering, audit and the labeling-quality records."""
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import new_id, now


class Dashboard(Base):
    """Saved Insights Studio dashboard; widget specs are JSON in display order."""
    __tablename__ = "dashboards"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    widgets: Mapped[list] = mapped_column(JSON, default=list)
    share_token: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(Text, default="")   # webhook URLs reach 1024 chars
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(Float, default=now, index=True)


class Worker(Base):
    """Heartbeat row per worker process (embedded or standalone), for the admin console."""
    __tablename__ = "workers"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)       # host:pid
    host: Mapped[str] = mapped_column(String(120), default="")
    kinds: Mapped[list] = mapped_column(JSON, default=list)
    current_job: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started: Mapped[float] = mapped_column(Float, default=now)
    last_seen: Mapped[float] = mapped_column(Float, default=now, index=True)


class UsageEvent(Base):
    """One metered quantity. Rows stay after a project is deleted: usage history is billing data."""
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_ws_metric_created", "workspace_id", "metric", "created"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metric: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(Float, default=now, index=True)


class ConsensusJob(Base):
    """One image set sent to K labelers; the merge writes the agreed labels back."""
    __tablename__ = "consensus_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="collecting")   # collecting | ready | merged
    k: Mapped[int] = mapped_column(Integer)
    iou_threshold: Mapped[float] = mapped_column(Float, default=0.5)
    image_ids: Mapped[list] = mapped_column(JSON, default=list)
    agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    # per-image {agreement, no_consensus} cache: detail/queue reads must not re-run the pairwise pass
    image_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)


class ConsensusAssignment(Base):
    """A labeler's private draft for one image of a job; the Image row is only written on merge."""
    __tablename__ = "consensus_assignments"
    __table_args__ = (UniqueConstraint("job_id", "image_id", "user_id"),
                      Index("ix_consensus_assignments_project_image", "project_id", "image_id"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("consensus_jobs.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(32), index=True)
    project_id: Mapped[str] = mapped_column(String(32))
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    annotations: Mapped[list] = mapped_column(JSON, default=list)
    submitted: Mapped[float | None] = mapped_column(Float, nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class Honeypot(Base):
    """An image with known-good ground truth; a labeler's save is scored against it once."""
    __tablename__ = "honeypots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(32), index=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), unique=True)
    annotations: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class HoneypotAttempt(Base):
    __tablename__ = "honeypot_attempts"
    __table_args__ = (UniqueConstraint("honeypot_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    honeypot_id: Mapped[str] = mapped_column(ForeignKey("honeypots.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created: Mapped[float] = mapped_column(Float, default=now)


class LabelEvent(Base):
    """One annotation save — throughput, AI-acceptance and consensus-pending live here."""
    __tablename__ = "label_events"
    __table_args__ = (Index("ix_label_events_project_user_created", "project_id", "user_id", "created"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(String(32), index=True)
    project_id: Mapped[str] = mapped_column(String(32))
    image_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(32))
    annotations: Mapped[int] = mapped_column(Integer, default=0)
    ai_seen: Mapped[int] = mapped_column(Integer, default=0)
    ai_kept: Mapped[int] = mapped_column(Integer, default=0)
    # distinct AI annotation ids this save exposed to the labeler; acceptance is derived from these
    # plus the image's final annotations, never from the per-save counters above
    ai_ids: Mapped[list] = mapped_column(JSON, default=list)
    created: Mapped[float] = mapped_column(Float, default=now)
