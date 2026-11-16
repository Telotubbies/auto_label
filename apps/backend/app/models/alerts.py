"""Alert channels for stream events, and the delivery history behind the settings panel."""

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from .common import new_id, now

ALERT_KINDS = ("line", "slack", "email")


class AlertChannel(Base):
    """Where stream events go (LINE Messaging API, Slack incoming webhook or email).

    `config` holds provider credentials encrypted by `services.secretbox`; API responses
    expose only a masked preview. `settings` holds throttle seconds and quiet hours.
    """

    __tablename__ = "alert_channels"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # line | slack | email
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent: Mapped[float | None] = mapped_column(Float, nullable=True)  # throttle state, only on success
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)


class AlertDelivery(Base):
    """One attempted alert, including throttled/quiet-hour skips, for the history panel."""

    __tablename__ = "alert_deliveries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("alert_channels.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(32), index=True)
    event: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_path: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # ok | failed | skipped
    reason: Mapped[str] = mapped_column(String(120), default="")
    last_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)
