"""Read-only cloud storage connectors (S3 / GCS / Azure Blob).

Admin owns the credentials; reviewers can list objects and start an import job. There is
deliberately no endpoint that writes, moves or deletes objects in the remote bucket.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import Ctx, audit, project_ctx, ws_ctx
from ..models import SPLITS, Connector, Job
from ..services import connectors, secretbox
from .projects import job_out

router = APIRouter(prefix="/api/ws/{ws}", tags=["connectors"])


def connector_out(conn: Connector) -> dict:
    return {"id": conn.id, "name": conn.name, "kind": conn.kind, "config": connectors.public_config(conn),
            "created": conn.created, "last_sync": conn.last_sync, "last_status": conn.last_status}


def _connector(db, ws_id: str, cid: str) -> Connector:
    conn = db.get(Connector, cid)
    if not conn or conn.workspace_id != ws_id:
        raise HTTPException(404, "connector not found")
    return conn


# --- connectors ----------------------------------------------------------------------

@router.get("/connectors")
def list_connectors(c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    rows = c.db.scalars(select(Connector).where(Connector.workspace_id == c.ws.id)
                        .order_by(Connector.created.desc())).all()
    return [connector_out(r) for r in rows]


class ConnectorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str
    config: dict = Field(default_factory=dict)


@router.post("/connectors")
def create_connector(body: ConnectorIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    try:
        connectors.validate(body.kind, body.config)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    conn = Connector(workspace_id=c.ws.id, name=body.name.strip(), kind=body.kind,
                     config=secretbox.encrypt_config(body.config, connectors.SECRET_FIELDS), created_by=c.uid)
    c.db.add(conn)
    audit(c.db, c.ws.id, c.uid, "connector.create", conn.name, kind=conn.kind)
    c.db.commit()
    return connector_out(conn)


@router.delete("/connectors/{cid}")
def delete_connector(cid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    conn = _connector(c.db, c.ws.id, cid)
    audit(c.db, c.ws.id, c.uid, "connector.delete", conn.name, kind=conn.kind)
    c.db.delete(conn)
    c.db.commit()
    return {"ok": True}


@router.get("/connectors/{cid}/objects")
def list_objects(cid: str, prefix: str = "", limit: int = 100, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    conn = _connector(c.db, c.ws.id, cid)
    return {"objects": connectors.list_objects(conn, prefix=prefix, limit=limit)}


# --- import job ----------------------------------------------------------------------

class SyncIn(BaseModel):
    prefix: str = ""
    split: str = "auto"
    batch_name: str = ""
    limit: int = 200


@router.post("/projects/{project}/connectors/{cid}/sync")
def sync_connector(cid: str, body: SyncIn, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    conn = _connector(c.db, c.ws.id, cid)
    if body.split not in (*SPLITS, "auto"):
        raise HTTPException(400, f"split must be one of {(*SPLITS, 'auto')}")
    job = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="connector_sync", created_by=c.uid,
              params={"connector_id": conn.id, "project_id": c.project.id, "prefix": body.prefix,
                      "split": body.split, "batch_name": body.batch_name,
                      "limit": max(1, min(body.limit, connectors.MAX_SYNC_LIMIT))})
    c.db.add(job)
    audit(c.db, c.ws.id, c.uid, "connector.sync", conn.name, project=c.project.slug, prefix=body.prefix)
    c.db.commit()
    return job_out(job)
