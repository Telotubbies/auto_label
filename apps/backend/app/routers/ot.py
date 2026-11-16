"""PLC / OT outputs: configure reject-signal endpoints and test them (admin, flagged)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ..deps import Ctx, audit, project_ctx
from ..models import OtDelivery, OtOutput
from ..services import ot
from ..services.flags import require_flag

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/ot-outputs", tags=["ot"],
                   dependencies=[Depends(require_flag("task_40"))])


class OutputIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: str
    endpoint: dict
    event_filter: dict = Field(default_factory=dict)
    latency_budget_ms: int = ot.DEFAULT_LATENCY_BUDGET_MS
    pulse_ms: int = ot.DEFAULT_PULSE_MS
    enabled: bool = True


class OutputPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    protocol: str | None = None
    endpoint: dict | None = None
    event_filter: dict | None = None
    latency_budget_ms: int | None = None
    pulse_ms: int | None = None
    enabled: bool | None = None


def _out(row: OtOutput) -> dict:
    return {"id": row.id, "workspace_id": row.workspace_id, "project_id": row.project_id,
            "name": row.name, "protocol": row.protocol, "endpoint": row.endpoint or {},
            "event_filter": row.event_filter or {}, "latency_budget_ms": row.latency_budget_ms,
            "pulse_ms": row.pulse_ms, "enabled": bool(row.enabled), "last_status": row.last_status,
            "last_latency_ms": row.last_latency_ms, "last_error": row.last_error,
            "created": row.created, "updated": row.updated}


def _delivery_out(row: OtDelivery) -> dict:
    return {"id": row.id, "output_id": row.output_id, "stream_id": row.stream_id,
            "rule_kind": row.rule_kind, "event": row.event or {}, "status": row.status,
            "latency_ms": row.latency_ms, "detail": row.detail, "created": row.created}


def _get(c: Ctx, output_id: str) -> OtOutput:
    row = c.db.get(OtOutput, output_id)
    if row is None or row.project_id != c.project.id or row.workspace_id != c.ws.id:
        raise HTTPException(404, "OT output not found")
    return row


def _config(protocol: str, endpoint: dict, event_filter: dict | None, name: str,
            latency_budget_ms: int, pulse_ms: int) -> dict:
    """Validate every user-supplied field in one place; ValueError becomes a 400."""
    try:
        clean = ot.validate_endpoint(protocol, endpoint)
        ot.check_target(protocol, clean)            # no egress outside LD_OT_ALLOW_CIDR
        return {"protocol": protocol,
                "endpoint": clean,
                "event_filter": ot.validate_event_filter(event_filter),
                **dict(zip(("name", "latency_budget_ms", "pulse_ms"),
                           ot.check_limits(name, latency_budget_ms, pulse_ms), strict=True))}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
def list_outputs(c: Ctx = Depends(project_ctx)):
    c.perm("project.read")
    rows = c.db.scalars(select(OtOutput).where(OtOutput.project_id == c.project.id,
                                               OtOutput.workspace_id == c.ws.id)
                        .order_by(OtOutput.created.desc())).all()
    return [_out(row) for row in rows]


@router.post("")
def create_output(body: OutputIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.settings")
    cfg = _config(body.protocol, body.endpoint, body.event_filter, body.name,
                  body.latency_budget_ms, body.pulse_ms)
    row = OtOutput(workspace_id=c.ws.id, project_id=c.project.id, enabled=body.enabled, **cfg)
    c.db.add(row)
    audit(c.db, c.ws.id, c.uid, "ot.create", row.name, protocol=row.protocol, enabled=row.enabled)
    c.db.commit()
    return _out(row)


@router.get("/{output_id}")
def get_output(output_id: str, c: Ctx = Depends(project_ctx)):
    c.perm("project.read")
    return _out(_get(c, output_id))


@router.patch("/{output_id}")
def update_output(output_id: str, body: OutputPatch, c: Ctx = Depends(project_ctx)):
    c.perm("project.settings")
    row = _get(c, output_id)
    cfg = _config(body.protocol or row.protocol,
                  body.endpoint if body.endpoint is not None else row.endpoint,
                  body.event_filter if body.event_filter is not None else row.event_filter,
                  body.name if body.name is not None else row.name,
                  body.latency_budget_ms if body.latency_budget_ms is not None else row.latency_budget_ms,
                  body.pulse_ms if body.pulse_ms is not None else row.pulse_ms)
    for key, value in cfg.items():
        setattr(row, key, value)
    if body.enabled is not None:
        row.enabled = body.enabled
    audit(c.db, c.ws.id, c.uid, "ot.update", row.name, protocol=row.protocol, enabled=row.enabled)
    c.db.commit()
    return _out(row)


@router.delete("/{output_id}")
def delete_output(output_id: str, c: Ctx = Depends(project_ctx)):
    c.perm("project.settings")
    row = _get(c, output_id)
    c.db.execute(delete(OtDelivery).where(OtDelivery.output_id == row.id))
    audit(c.db, c.ws.id, c.uid, "ot.delete", row.name, protocol=row.protocol)
    c.db.delete(row)
    c.db.commit()
    return {"ok": True}


@router.post("/{output_id}/test")
def test_output(output_id: str, c: Ctx = Depends(project_ctx)):
    """Send one synthetic pulse through the real driver; a dead line is a report, not a 5xx."""
    c.perm("project.settings")
    row = _get(c, output_id)
    if not row.enabled:
        raise HTTPException(400, "enable the output before sending a test signal")
    sent_at = ot._now()
    with ot.output_lock(row.id):
        result = ot.deliver(row.protocol, row.endpoint, budget_ms=row.latency_budget_ms,
                            pulse_ms=row.pulse_ms, event_ts=sent_at)
    delivery = ot.record_delivery(c.db, row, {"kind": "test", "summary": "manual test"}, result)
    audit(c.db, c.ws.id, c.uid, "ot.test", row.name, protocol=row.protocol, status=result.status,
          latency_ms=result.latency_ms)
    c.db.commit()
    return _delivery_out(delivery)


@router.get("/{output_id}/deliveries")
def list_deliveries(output_id: str, limit: int = Query(50, ge=1, le=200), c: Ctx = Depends(project_ctx)):
    c.perm("project.read")
    row = _get(c, output_id)
    rows = c.db.scalars(select(OtDelivery).where(OtDelivery.output_id == row.id,
                                                 OtDelivery.workspace_id == c.ws.id)
                        .order_by(OtDelivery.created.desc()).limit(limit)).all()
    return [_delivery_out(item) for item in rows]
