"""The job queue, trained models, deployments and drift runs."""
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import new_id, now


class Job(Base):
    """Background work item. The worker claims rows with status='queued'.

    The queue is shared by version, export and train, so it lives with the model registry that
    consumes most of its kinds.
    """
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))     # version | export | export_engine | train | autolabel
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # Who claimed it: "local" (app.worker) or "remote" (pip GPU worker). The reaper must only
    # own remote claims; a local train/autolabel job has no progress heartbeat (I9).
    executor: Mapped[str] = mapped_column(String(8), default="")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    started: Mapped[float | None] = mapped_column(Float, nullable=True)
    finished: Mapped[float | None] = mapped_column(Float, nullable=True)


class TrainedModel(Base):
    __tablename__ = "trained_models"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id", ondelete="CASCADE"))
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    arch: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(String(16))           # detect | segment | classify
    status: Mapped[str] = mapped_column(String(16), default="training")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    history: Mapped[list] = mapped_column(JSON, default=list)
    classes: Mapped[list] = mapped_column(JSON, default=list)
    weights: Mapped[str] = mapped_column(String(1024), default="")
    family: Mapped[str] = mapped_column(String(32), default="ultralytics")
    variant: Mapped[str] = mapped_column(String(64), default="")
    license: Mapped[str] = mapped_column(String(64), default="AGPL-3.0")
    runtime_refs: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(Float, default=now)


class DeploymentAlias(Base):
    """One inference alias per project (`production`, `staging`) -> a ready trained model."""
    __tablename__ = "deployment_aliases"
    __table_args__ = (UniqueConstraint("project_id", "alias"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str | None] = mapped_column(ForeignKey("trained_models.id", ondelete="SET NULL"), nullable=True)
    previous_model_id: Mapped[str | None] = mapped_column(String(32), nullable=True)   # rollback target
    updated_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)


class DeploymentEvent(Base):
    """Append-only alias history: what moved where, who did it, and when."""
    __tablename__ = "deployment_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    from_model_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(16), default="deploy")   # deploy | rollback
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class DriftSample(Base):
    """A recent production input (hosted API or stream) kept for the two-sample drift test."""
    __tablename__ = "drift_samples"
    __table_args__ = (Index("ix_drift_samples_project_created", "project_id", "created"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="api")        # api | stream
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(512), default="")
    features: Mapped[list] = mapped_column(JSON, default=list)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[float] = mapped_column(Float, default=now)


class DriftRun(Base):
    """One embedding MMD run between the training distribution and recent production samples."""
    __tablename__ = "drift_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")   # running | done | insufficient | failed
    statistic: Mapped[float] = mapped_column(Float, default=0.0)
    p_value: Mapped[float] = mapped_column(Float, default=1.0)
    threshold: Mapped[float] = mapped_column(Float, default=0.05)
    n_reference: Mapped[int] = mapped_column(Integer, default=0)
    n_current: Mapped[int] = mapped_column(Integer, default=0)
    alert: Mapped[bool] = mapped_column(Boolean, default=False)
    feature_source: Mapped[str] = mapped_column(String(32), default="colour/layout map")
    samples_sent: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[float] = mapped_column(Float, default=now)
    finished: Mapped[float | None] = mapped_column(Float, nullable=True)
