"""Workspace RBAC: project roles, custom roles, permission matrix (replaces the legacy single role)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .. import rbac
from ..deps import Ctx, apply_project_role, audit, project_ctx, ws_ctx
from ..models import PROJECT_ROLES, WORKSPACE_ROLES, CustomRole, Member, Project, ProjectMember

router = APIRouter(prefix="/api/ws/{ws}", tags=["rbac"])


def _permission_payload(c: Ctx) -> dict:
    perms = rbac.permissions_for(c.ws_role, c.project_role, c.ws_custom, c.project_custom)
    return {
        "workspace_role": c.ws_role,
        "project_role": c.project_role,
        "permissions": sorted(perms),
        "matrix": rbac.matrix(),
        "roles": list(PROJECT_ROLES),
        "workspace_roles": list(WORKSPACE_ROLES),
    }


def _role_out(r: CustomRole) -> dict:
    return {"id": r.id, "name": r.name, "level": r.level, "permissions": list(r.permissions or []),
            "created": r.created}


@router.get("/permissions")
def permissions(project: str | None = None, c: Ctx = Depends(ws_ctx)):
    """Effective permissions of the caller, optionally resolved inside one project."""
    if project:
        p = c.db.scalar(select(Project).where(Project.workspace_id == c.ws.id, Project.slug == project,
                                              Project.deleted_at.is_(None)))
        if not p:
            raise HTTPException(404, "project not found")
        apply_project_role(c, p)
    return _permission_payload(c)


@router.get("/projects/{project}/permissions")
def project_permissions(c: Ctx = Depends(project_ctx)):
    return _permission_payload(c)


@router.get("/roles")
def list_roles(c: Ctx = Depends(ws_ctx)):
    """Custom roles are readable by any member; only workspace admins may change them."""
    rows = c.db.scalars(select(CustomRole).where(CustomRole.workspace_id == c.ws.id)
                        .order_by(CustomRole.created)).all()
    return [_role_out(r) for r in rows]


class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    level: str
    permissions: list[str] = Field(default_factory=list)


class RolePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    permissions: list[str] | None = None


def _clean_name(name: str) -> str:
    name = name.strip()
    if not 2 <= len(name) <= 80:
        raise HTTPException(400, "name must be 2..80 characters")
    return name


def _validated(level: str, perms: list[str]) -> list[str]:
    if level not in ("workspace", "project"):
        raise HTTPException(400, "level must be workspace or project")
    try:
        return rbac.validate_permissions(level, perms)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


def _role_or_404(c: Ctx, rid: str) -> CustomRole:
    role = c.db.get(CustomRole, rid)
    if not role or role.workspace_id != c.ws.id:
        raise HTTPException(404, "role not found")
    return role


@router.post("/roles")
def create_role(body: RoleIn, c: Ctx = Depends(ws_ctx)):
    c.perm("workspace.members")
    role = CustomRole(workspace_id=c.ws.id, name=_clean_name(body.name), level=body.level,
                      permissions=_validated(body.level, body.permissions))
    c.db.add(role)
    audit(c.db, c.ws.id, c.user.id, "rbac.role.create", role.name, level=role.level)
    try:
        c.db.commit()
    except IntegrityError:
        c.db.rollback()
        raise HTTPException(409, "a role with this name already exists") from None
    return _role_out(role)


@router.patch("/roles/{rid}")
def update_role(rid: str, body: RolePatch, c: Ctx = Depends(ws_ctx)):
    c.perm("workspace.members")
    role = _role_or_404(c, rid)
    if body.name is not None:
        role.name = _clean_name(body.name)
    if body.permissions is not None:
        role.permissions = _validated(role.level, body.permissions)
    audit(c.db, c.ws.id, c.user.id, "rbac.role.update", role.name, level=role.level)
    try:
        c.db.commit()
    except IntegrityError:
        c.db.rollback()
        raise HTTPException(409, "a role with this name already exists") from None
    return _role_out(role)


@router.delete("/roles/{rid}")
def delete_role(rid: str, c: Ctx = Depends(ws_ctx)):
    c.perm("workspace.members")
    role = _role_or_404(c, rid)
    # Assignments must not dangle: clear every bundle at both levels before removing the role.
    c.db.execute(update(Member).where(Member.workspace_id == c.ws.id, Member.custom_role_id == rid)
                 .values(custom_role_id=None))
    pids = select(Project.id).where(Project.workspace_id == c.ws.id)
    c.db.execute(update(ProjectMember).where(ProjectMember.project_id.in_(pids), ProjectMember.custom_role_id == rid)
                 .values(custom_role_id=None))
    audit(c.db, c.ws.id, c.user.id, "rbac.role.delete", role.name, level=role.level)
    c.db.delete(role)
    c.db.commit()
    return {"ok": True}


def _project_permissions(c: Ctx, m: Member) -> tuple[str, list[str]]:
    """(effective project role, effective permissions) for one workspace member."""
    ws_role = rbac.workspace_role(m.role, m.user_id == c.ws.owner_id)
    row = c.db.get(ProjectMember, (c.project.id, m.user_id))
    base = rbac.base_project_role(m.role, ws_role)
    ws_custom = _custom(c, m.custom_role_id, "workspace")
    project_custom = _custom(c, row.custom_role_id, "project") if row else ()
    project_role = "manager" if ws_role in ("owner", "admin") else (row.role if row else base)
    perms = rbac.permissions_for(ws_role, project_role, ws_custom, project_custom)
    return project_role, sorted(perms)


def _custom(c: Ctx, rid: str | None, level: str) -> tuple[str, ...]:
    if not rid:
        return ()
    role = c.db.get(CustomRole, rid)
    return tuple(role.permissions or []) if role and role.level == level else ()


@router.get("/projects/{project}/roles")
def project_roles(c: Ctx = Depends(project_ctx)):
    """Every workspace member with their effective project role (inherited when unassigned)."""
    c.perm("project.roles")
    rows = c.db.scalars(select(Member).where(Member.workspace_id == c.ws.id).order_by(Member.created)).all()
    members = []
    for m in rows:
        row = c.db.get(ProjectMember, (c.project.id, m.user_id))
        role, perms = _project_permissions(c, m)
        members.append({"id": m.user_id, "name": m.user.name, "email": m.user.email, "role": role,
                        "custom_role_id": row.custom_role_id if row else None,
                        "effective": perms, "inherited": row is None})
    return {"members": members, "roles": list(PROJECT_ROLES)}


class ProjectMemberIn(BaseModel):
    role: str
    custom_role_id: str | None = None


class WorkspaceCustomRoleIn(BaseModel):
    custom_role_id: str | None = None


@router.patch("/members/{uid}/custom-role")
def set_workspace_custom_role(uid: str, body: WorkspaceCustomRoleIn, c: Ctx = Depends(ws_ctx)):
    """Grant a workspace-level custom bundle on top of a member's base role (grant-only)."""
    c.perm("workspace.members")
    m = c.db.get(Member, (c.ws.id, uid))
    if not m:
        raise HTTPException(404, "member not found")
    if body.custom_role_id is not None:
        role = c.db.get(CustomRole, body.custom_role_id)
        if not role or role.workspace_id != c.ws.id or role.level != "workspace":
            raise HTTPException(400, "custom_role_id must be a workspace role of this workspace")
    m.custom_role_id = body.custom_role_id
    audit(c.db, c.ws.id, c.user.id, "member.custom_role", m.user.email,
          custom_role_id=body.custom_role_id)
    c.db.commit()
    return {"id": uid, "custom_role_id": m.custom_role_id}


@router.patch("/projects/{project}/members/{uid}")
def set_project_role(uid: str, body: ProjectMemberIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.roles")
    target = c.db.get(Member, (c.ws.id, uid))
    if not target:
        raise HTTPException(404, "member not found")
    if body.role not in PROJECT_ROLES:
        raise HTTPException(400, f"role must be one of {PROJECT_ROLES}")
    supplied = "custom_role_id" in body.model_fields_set
    if supplied and body.custom_role_id is not None:
        role = c.db.get(CustomRole, body.custom_role_id)
        if not role or role.workspace_id != c.ws.id or role.level != "project":
            raise HTTPException(400, "custom_role_id must be a project role of this workspace")
    row = c.db.get(ProjectMember, (c.project.id, uid))
    if row:
        row.role = body.role
        if supplied:
            row.custom_role_id = body.custom_role_id
    else:
        row = ProjectMember(project_id=c.project.id, user_id=uid, role=body.role,
                            custom_role_id=body.custom_role_id if supplied else None)
        c.db.add(row)
    audit(c.db, c.ws.id, c.user.id, "project.member.role", target.user.email, role=body.role)
    c.db.commit()
    return {"id": uid, "role": row.role, "custom_role_id": row.custom_role_id}


@router.delete("/projects/{project}/members/{uid}")
def remove_project_role(uid: str, c: Ctx = Depends(project_ctx)):
    c.perm("project.roles")
    row = c.db.get(ProjectMember, (c.project.id, uid))
    if not row:
        raise HTTPException(404, "project member not found")
    email = row.user.email if row.user else uid
    audit(c.db, c.ws.id, c.user.id, "project.member.remove", email)
    c.db.delete(row)
    c.db.commit()
    return {"ok": True}
