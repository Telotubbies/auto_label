"""ORM schema. Annotations live as JSON on the image row (one write per save,
trivially snapshotted into versions); everything else is relational."""
import secrets
import time

from sqlalchemy import (JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return secrets.token_hex(8)


def now() -> float:
    return time.time()


# Legacy workspace roles stay valid on Member rows (mapped by app/rbac.py); new workspaces use the
# four-role model. Project roles live on ProjectMember and never replace the workspace role.
ROLES = ("admin", "reviewer", "annotator")
WORKSPACE_ROLES = ("owner", "admin", "billing", "member")
PROJECT_ROLES = ("manager", "reviewer", "labeler", "viewer")
PROJECT_TYPES = ("object-detection", "instance-segmentation", "classification", "keypoint-detection")
SPLITS = ("train", "valid", "test")
STATUSES = ("unassigned", "annotating", "review", "done")
API_SCOPES = ("read", "upload", "train", "infer")
CONNECTOR_KINDS = ("s3", "gcs", "azure")
WEBHOOK_EVENTS = ("job.done", "model.ready", "stream.event")
DATA_REGIONS = ("th", "sg", "us")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    pw_hash: Mapped[str] = mapped_column(String(255), default="")
    email_verified: Mapped[float | None] = mapped_column(Float, nullable=True)   # timestamp of verification
    # Persisted platform-operator flag; out-of-band grant, still requires a verified address.
    platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Fernet-encrypted TOTP seed (ciphertext, not base32); nullable until enrolment starts.
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_codes: Mapped[list] = mapped_column(JSON, default=list)             # sha256 of each one-time code
    totp_last_step: Mapped[int] = mapped_column(Integer, default=0)              # replay guard for TOTP codes
    created: Mapped[float] = mapped_column(Float, default=now)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    plan: Mapped[str] = mapped_column(String(32), default="free")
    credits_used: Mapped[float] = mapped_column(Float, default=0.0)
    credits_period: Mapped[str] = mapped_column(String(7), default="")   # YYYY-MM the counter belongs to
    require_mfa: Mapped[bool] = mapped_column(Boolean, default=False)    # members must enrol TOTP to enter
    data_region: Mapped[str] = mapped_column(String(16), default="th")   # PDPA residency declaration
    created: Mapped[float] = mapped_column(Float, default=now)


class Member(Base):
    __tablename__ = "members"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="annotator")
    custom_role_id: Mapped[str | None] = mapped_column(String(32), nullable=True)   # grant-only permission bundle
    created: Mapped[float] = mapped_column(Float, default=now)
    user: Mapped[User] = relationship(lazy="joined")


class ProjectMember(Base):
    """Two-level RBAC: a workspace member may hold a different project role per project."""
    __tablename__ = "project_members"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="labeler")
    custom_role_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    user: Mapped[User] = relationship(lazy="joined")


class CustomRole(Base):
    """Named permission bundle (grant-only, unioned with the base role)."""
    __tablename__ = "custom_roles"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(16), default="project")   # workspace | project
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    created: Mapped[float] = mapped_column(Float, default=now)


class Invite(Base):
    __tablename__ = "invites"
    token: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: secrets.token_urlsafe(24))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="annotator")
    invited_by: Mapped[str] = mapped_column(String(32))
    created: Mapped[float] = mapped_column(Float, default=now)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)


class RefreshToken(Base):
    """One row per signed-in device. The column is the sha256 of the token, never the token itself."""
    __tablename__ = "refresh_tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires: Mapped[float] = mapped_column(Float)
    created: Mapped[float] = mapped_column(Float, default=now)
    last_seen: Mapped[float] = mapped_column(Float, default=now)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")


class EmailToken(Base):
    """Single-use tokens for password reset and email verification (only the hash is stored)."""
    __tablename__ = "email_tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))                  # reset | verify
    expires: Mapped[float] = mapped_column(Float)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[float] = mapped_column(Float, default=now)


class LoginEvent(Base):
    """Login history shown on the account security page."""
    __tablename__ = "login_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(16), default="password")   # password | mfa | oidc
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created: Mapped[float] = mapped_column(Float, default=now, index=True)


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created: Mapped[float] = mapped_column(Float, default=now)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    slug: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(32), default="object-detection")
    multilabel: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    license: Mapped[str] = mapped_column(String(64), default="CC BY 4.0")
    annotation_group: Mapped[str] = mapped_column(String(120), default="objects")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)   # active learning, review mode …
    # PDPA: per-project retention in days (NULL/0 = keep) and face anonymisation before frames reach datasets.
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_blur: Mapped[bool] = mapped_column(Boolean, default=True)
    biometrics: Mapped[bool] = mapped_column(Boolean, default=False)      # face recognition — opt-in only
    legal_basis: Mapped[str] = mapped_column(Text, default="")            # documented PDPA s.26 basis
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)
    deleted_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class LabelClass(Base):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(16), default="#8b5cf6")
    created: Mapped[float] = mapped_column(Float, default=now)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="upload")   # upload | import | api | active-learning
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (Index("ix_images_project_status", "project_id", "status"),
                      Index("ix_images_project_sha", "project_id", "sha256"),
                      Index("ix_images_project_created", "project_id", "deleted_at", "created"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(1024))       # relative to DATA_DIR
    thumb: Mapped[str] = mapped_column(String(1024))
    size: Mapped[int] = mapped_column(Integer, default=0)
    split: Mapped[str] = mapped_column(String(8), default="train")
    status: Mapped[str] = mapped_column(String(16), default="unassigned")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review: Mapped[str | None] = mapped_column(String(16), nullable=True)   # approved | rejected
    tags: Mapped[list] = mapped_column(JSON, default=list)
    annotations: Mapped[list] = mapped_column(JSON, default=list)
    n_annotations: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)
    deleted_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class ImageClass(Base):
    """Denormalised (image, class) -> count index of Image.annotations, kept in sync by
    set_annotations(). Lets class counts and class filters run in SQL instead of
    scanning every annotation JSON blob."""
    __tablename__ = "image_classes"
    __table_args__ = (Index("ix_image_classes_project_class", "project_id", "class_id"),)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), primary_key=True)
    class_id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    project_id: Mapped[str] = mapped_column(String(32))
    n: Mapped[int] = mapped_column(Integer, default=1)


def set_annotations(db, img: "Image", anns: list[dict]):
    """The only way annotations should be written — keeps n_annotations and image_classes in sync."""
    from collections import Counter
    from sqlalchemy import delete
    img.annotations = anns
    img.n_annotations = len(anns)
    img.updated = now()
    if img.id is None:
        img.id = new_id()
    db.execute(delete(ImageClass).where(ImageClass.image_id == img.id))
    for cid, n in Counter(a.get("classId") for a in anns if a.get("classId")).items():
        db.add(ImageClass(image_id=img.id, class_id=cid, project_id=img.project_id, n=n))


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    created: Mapped[float] = mapped_column(Float, default=now)
    user: Mapped[User] = relationship(lazy="joined")


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255), default="")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)   # preprocessing / augmentation / split
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)      # counts per split / class
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class Job(Base):
    """Background work item. The worker claims rows with status='queued'."""
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))     # version | export | export_engine | train | autolabel
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
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


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # empty/NULL = all scopes: keys issued before scopes existed keep full access
    scopes: Mapped[list] = mapped_column(JSON, nullable=True)
    publishable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    last_used: Mapped[float | None] = mapped_column(Float, nullable=True)


class Connector(Base):
    """Read-only object-storage link. Credentials stay in `config` and never leave the API."""
    __tablename__ = "connectors"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))                     # s3 | gcs | azure
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON, default=dict)          # bucket/container + credentials
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    last_sync: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_status: Mapped[str] = mapped_column(String(16), default="")


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    secret: Mapped[str] = mapped_column(String(64))
    events: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class WebhookDelivery(Base):
    """One webhook call, retried with backoff until MAX_ATTEMPTS."""
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    webhook_id: Mapped[str] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(32), index=True)
    event: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)   # pending | ok | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt: Mapped[float] = mapped_column(Float, default=now)
    last_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)
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
    target: Mapped[str] = mapped_column(String(255), default="")
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
