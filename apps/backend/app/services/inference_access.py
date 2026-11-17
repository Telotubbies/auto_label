"""Which workspace owns the inference hub in this deployment.

One deployment serves one hub: ``LD_INFERENCE_WORKSPACE`` (a workspace id or slug) pins it, and
every hub route 404s for another workspace. Unset means the deployment serves every workspace,
which is the single-tenant case.
"""
import os

from sqlalchemy import select

from ..models import Workspace


def scope() -> str:
    """The configured workspace id or slug; empty when the deployment is not pinned."""
    return os.environ.get("LD_INFERENCE_WORKSPACE", "").strip()


def workspace_allowed(db, ws_id: str) -> bool:
    """False when the hub belongs to another workspace, so its routes must 404."""
    pinned = scope()
    if not pinned or pinned == ws_id:
        return True
    return db.scalar(select(Workspace.id).where(Workspace.slug == pinned)) == ws_id
