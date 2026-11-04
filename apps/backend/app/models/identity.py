"""Identity, workspace, membership and workspace-level integrations."""
import secrets

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .common import new_id, now


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
    # Per-workspace quota overrides; NULL/absent keys fall back to the plan allowance.
    quotas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)


class WorkspaceFlag(Base):
    """Per-workspace feature-flag override. No row (or enabled=False) means the flag is off."""
    __tablename__ = "workspace_flags"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated: Mapped[float] = mapped_column(Float, default=now)


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
    secret: Mapped[str] = mapped_column(Text)          # enc:v1:… is longer than the old 64-char column
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
