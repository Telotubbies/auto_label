"""Single source of truth for the two-level permission model.

Workspace roles describe what someone may do to the workspace (billing, keys, members);
project roles describe what they may do inside one project. Legacy Member rows still carry
``admin``/``reviewer``/``annotator`` and are mapped here, never rewritten in the database.
Custom roles are grant-only permission bundles unioned on top of the base role.
"""
from .models import WORKSPACE_ROLES

Level = str

WORKSPACE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "workspace.read": ("owner", "admin", "billing", "member"),
    "workspace.update": ("owner", "admin"),
    "workspace.delete": ("owner",),
    "workspace.members": ("owner", "admin"),
    "workspace.billing": ("owner", "billing"),
    "workspace.keys": ("owner", "admin"),
    "workspace.audit": ("owner", "admin"),
    "workspace.trash": ("owner", "admin"),
    "workspace.connectors": ("owner", "admin"),
    "workspace.project.create": ("owner", "admin"),
    "workspace.project.delete": ("owner", "admin"),
}

PROJECT_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "project.read": ("manager", "reviewer", "labeler", "viewer"),
    "project.annotate": ("manager", "reviewer", "labeler"),
    "project.review": ("manager", "reviewer"),
    "project.upload": ("manager", "reviewer"),
    "project.export": ("manager", "reviewer"),
    "project.settings": ("manager",),
    "project.classes": ("manager", "reviewer", "labeler"),
    "project.train": ("manager",),
    "project.models": ("manager", "reviewer"),
    "project.infer": ("manager", "reviewer", "labeler"),
    "project.streams": ("manager",),
    "project.privacy": ("manager",),
    "project.roles": ("manager",),
}

_LEVELS = {"workspace": WORKSPACE_PERMISSIONS, "project": PROJECT_PERMISSIONS}
# Owner/admin-only rights that must never travel in a delegated bundle (I18).
CUSTOM_DENIED = frozenset({"workspace.members", "workspace.delete"})


def _table(level: Level) -> dict[str, tuple[str, ...]]:
    try:
        return _LEVELS[level]
    except KeyError:
        raise ValueError(f"level must be one of {tuple(_LEVELS)}") from None


def all_permissions(level: Level) -> set[str]:
    """Every permission name defined for a level (``workspace`` or ``project``)."""
    return set(_table(level))


def matrix() -> dict[str, dict[str, list[str]]]:
    """The permission -> roles table, JSON-ready, for the UI and API documentation."""
    return {level: {perm: list(roles) for perm, roles in table.items()} for level, table in _LEVELS.items()}


def legacy_workspace_role(raw: str) -> str:
    """Map a legacy Member.role value onto the four-role model (annotator/reviewer -> member)."""
    if raw in ("annotator", "reviewer"):
        return "member"
    return raw if raw in WORKSPACE_ROLES else "member"


def workspace_role(raw: str, is_owner: bool) -> str:
    """Resolve the effective workspace role; ownership outranks whatever the Member row says."""
    return "owner" if is_owner else legacy_workspace_role(raw)


def base_project_role(raw: str, ws_role: str) -> str:
    """The project role inherited from the workspace role when no ProjectMember row exists."""
    if ws_role in ("owner", "admin"):
        return "manager"
    if raw == "reviewer":
        return "reviewer"
    if raw == "annotator":
        return "labeler"
    if ws_role == "billing":
        return "viewer"
    return "labeler"


def permissions_for(ws_role: str, project_role: str | None = None, ws_custom: tuple[str, ...] = (),
                    project_custom: tuple[str, ...] = ()) -> set[str]:
    """Union of the base workspace/project permissions and any granted custom bundles.

    A missing ``project_role`` means "outside a project", so project permissions are not
    granted. Custom entries are filtered to their level: a stale bundle can never leak a
    permission from the other level.
    """
    out = {perm for perm, roles in WORKSPACE_PERMISSIONS.items() if ws_role in roles}
    if project_role:
        out |= {perm for perm, roles in PROJECT_PERMISSIONS.items() if project_role in roles}
    out |= {p for p in ws_custom if p in WORKSPACE_PERMISSIONS}
    out |= {p for p in project_custom if p in PROJECT_PERMISSIONS}
    return out


def has(perm: str, ws_role: str, project_role: str | None = None, ws_custom: tuple[str, ...] = (),
        project_custom: tuple[str, ...] = ()) -> bool:
    """True when the resolved role/custom bundle grants ``perm``."""
    return perm in permissions_for(ws_role, project_role, ws_custom, project_custom)


def validate_permissions(level: Level, perms: list[str]) -> list[str]:
    """Validate and de-duplicate a custom-role bundle; unknown or cross-level names raise ValueError."""
    table = _table(level)
    seen: list[str] = []
    for perm in perms:
        if not isinstance(perm, str) or perm not in table:
            raise ValueError(f"unknown {level} permission: {perm}")
        if perm in CUSTOM_DENIED:
            raise ValueError(f"{perm} cannot be granted by a custom role")
        if perm not in seen:
            seen.append(perm)
    return seen
