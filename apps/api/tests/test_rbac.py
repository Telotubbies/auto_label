"""Two-level RBAC: permission matrix, project roles, custom roles, audit filters."""
import os
import secrets
import tempfile
import time

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-rbac-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import rbac
from app.db import SessionLocal
from app.main import app
from app.models import (
    PROJECT_ROLES,
    WORKSPACE_ROLES,
    Audit,
    CustomRole,
    Image,
    Member,
    Project,
    ProjectMember,
    User,
    Workspace,
)

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
TAG = secrets.token_hex(3)

WS_PERMS = {
    "owner": {"workspace.read", "workspace.update", "workspace.delete", "workspace.members", "workspace.billing",
              "workspace.keys", "workspace.audit", "workspace.trash", "workspace.connectors",
              "workspace.project.create", "workspace.project.delete"},
    "admin": {"workspace.read", "workspace.update", "workspace.members", "workspace.keys", "workspace.audit",
              "workspace.trash", "workspace.connectors", "workspace.project.create", "workspace.project.delete"},
    "billing": {"workspace.read", "workspace.billing"},
    "member": {"workspace.read"},
}
PROJ_PERMS = {
    "manager": {"project.read", "project.annotate", "project.review", "project.upload", "project.export",
                "project.settings", "project.classes", "project.train", "project.models", "project.infer",
                "project.streams", "project.privacy", "project.roles"},
    "reviewer": {"project.read", "project.annotate", "project.review", "project.upload", "project.export",
                 "project.classes", "project.models", "project.infer"},
    "labeler": {"project.read", "project.annotate", "project.classes", "project.infer"},
    "viewer": {"project.read"},
}


def login(email="demo@labeldesk.dev", pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module", autouse=True)
def db_ready():
    with TestClient(app):
        yield


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    with SessionLocal() as db:
        uids = db.scalars(select(User.id).where(User.email.like("%@rbac.test"))).all()
        for row in db.scalars(select(ProjectMember).where(ProjectMember.user_id.in_(uids))).all():
            db.delete(row)
        for row in db.scalars(select(Member).where(Member.user_id.in_(uids))).all():
            db.delete(row)
        demo = db.scalars(select(User.id).where(User.email.in_(
            ("labeler@labeldesk.dev", "reviewer@labeldesk.dev")))).all()
        for row in db.scalars(select(ProjectMember).where(ProjectMember.user_id.in_(demo))).all():
            db.delete(row)
        for row in db.scalars(select(CustomRole).where(CustomRole.name.like(f"rbac-{TAG}-%"))).all():
            db.delete(row)
        for row in db.scalars(select(Image).where(Image.name.like(f"rbac-{TAG}-%"))).all():
            db.delete(row)
        db.commit()


@pytest.fixture(scope="module")
def admin():
    return login()


def ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def project_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Project.id).where(Project.workspace_id == ws_id(), Project.slug == PR))


def user_id(email: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def new_image(assignee: str | None = None) -> str:
    with SessionLocal() as db:
        img = Image(project_id=project_id(), name=f"rbac-{TAG}-{secrets.token_hex(3)}.jpg",
                    sha256=secrets.token_hex(16), width=64, height=64, path="", thumb="", size=1,
                    assignee_id=assignee)
        db.add(img)
        db.commit()
        return img.id


# --- permission matrix (pure, no DB) -------------------------------------------------

@pytest.mark.parametrize("role", WORKSPACE_ROLES)
def test_workspace_permission_matrix(role):
    assert rbac.permissions_for(role) == WS_PERMS[role]


@pytest.mark.parametrize("role", PROJECT_ROLES)
def test_project_permission_matrix(role):
    assert rbac.permissions_for("member", role) == WS_PERMS["member"] | PROJ_PERMS[role]


@pytest.mark.parametrize("raw,level,project", [
    ("annotator", "member", "labeler"), ("reviewer", "member", "reviewer"),
    ("admin", "admin", "manager"), ("billing", "billing", "viewer"), ("member", "member", "labeler"),
])
def test_legacy_and_new_role_mapping(raw, level, project):
    assert rbac.legacy_workspace_role(raw) == level
    ws = rbac.workspace_role(raw, False)
    assert ws == level
    assert rbac.base_project_role(raw, ws) == project


def test_owner_wins_over_legacy_admin_row():
    assert rbac.workspace_role("admin", True) == "owner"
    assert rbac.base_project_role("admin", "owner") == "manager"


def test_billing_gets_billing_but_not_annotate():
    perms = rbac.permissions_for("billing", "viewer")
    assert "workspace.billing" in perms
    assert "project.annotate" not in perms
    assert rbac.has("workspace.billing", "billing")
    assert not rbac.has("project.annotate", "billing", "viewer")


def test_labeler_and_viewer_limits():
    labeler = rbac.permissions_for("member", "labeler")
    assert "project.annotate" in labeler and "project.review" not in labeler and "project.train" not in labeler
    assert rbac.permissions_for("member", "viewer") == WS_PERMS["member"] | {"project.read"}


def test_project_permissions_need_a_project():
    assert not rbac.has("project.read", "member")
    assert rbac.has("workspace.read", "member")


def test_custom_permissions_are_grant_only():
    assert rbac.has("project.export", "member", "viewer", project_custom=("project.export",))
    assert not rbac.has("project.review", "member", "viewer", project_custom=("project.export",))
    assert rbac.has("workspace.audit", "member", None, ws_custom=("workspace.audit",))


def test_validate_permissions_rejects_unknown_and_mismatched():
    rbac.validate_permissions("project", ["project.export", "project.read"])
    with pytest.raises(ValueError):
        rbac.validate_permissions("project", ["workspace.read"])
    with pytest.raises(ValueError):
        rbac.validate_permissions("workspace", ["project.export"])
    with pytest.raises(ValueError):
        rbac.validate_permissions("workspace", ["nope.read"])
    with pytest.raises(ValueError):
        rbac.validate_permissions("tenant", [])


def test_matrix_lists_every_permission():
    m = rbac.matrix()
    assert set(m) == {"workspace", "project"}
    assert set(m["workspace"]) == set(rbac.WORKSPACE_PERMISSIONS)
    assert set(m["project"]) == set(rbac.PROJECT_PERMISSIONS)
    assert rbac.all_permissions("project") == set(rbac.PROJECT_PERMISSIONS)


# --- legacy behaviour stays intact ---------------------------------------------------

def test_demo_admin_can_invite_and_list_members(admin):
    wid = ws_id()
    with SessionLocal() as db:
        ws = db.get(Workspace, wid)
        old_plan = ws.plan
        ws.plan = "pro"                      # free seats are already taken by the demo users
        db.commit()
    try:
        r = admin.post(f"/api/ws/{WS}/invites", json={"email": f"invite-{TAG}@rbac.test", "role": "annotator"})
        assert r.status_code == 200, r.text
        admin.delete(f"/api/ws/{WS}/invites/{r.json()['token']}")
    finally:
        with SessionLocal() as db:
            db.get(Workspace, wid).plan = old_plan
            db.commit()
    members = admin.get(f"/api/ws/{WS}/members").json()["members"]
    assert any(m["email"] == "labeler@labeldesk.dev" and "custom_role_id" in m for m in members)


def test_annotator_cannot_create_versions_but_can_read_project():
    lab = login("labeler@labeldesk.dev")
    assert lab.post(f"{BASE}/versions", json={"name": "x"}).status_code == 403
    assert lab.get(BASE).status_code == 200


def test_reviewer_can_review_and_annotator_cannot_see_unassigned():
    img = new_image()
    reviewer = login("reviewer@labeldesk.dev")
    assert reviewer.post(f"/api/images/{img}/review", json={"approved": True}).status_code == 200
    lab = login("labeler@labeldesk.dev")
    listed = lab.get(f"{BASE}/images", params={"q": f"rbac-{TAG}"}).json()["items"]
    assert [i for i in listed if i["id"] == img] == []
    assert lab.get(f"/api/images/{img}").status_code == 403


# --- project roles -------------------------------------------------------------------

def test_project_viewer_cannot_annotate_but_keeps_read(admin):
    lab_id = user_id("labeler@labeldesk.dev")
    img = new_image(assignee=lab_id)
    r = admin.patch(f"{BASE}/members/{lab_id}", json={"role": "viewer"})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.action == "project.member.role",
                                            Audit.target == "labeler@labeldesk.dev").order_by(Audit.created.desc()))
        assert row is not None and row.meta["role"] == "viewer"
    lab = login("labeler@labeldesk.dev")
    assert lab.put(f"/api/images/{img}/annotations", json={"annotations": []}).status_code == 403
    assert lab.post(f"{BASE}/board/move",
                    json={"from_status": "unassigned", "to_status": "annotating"}).status_code == 403
    assert lab.patch(BASE, json={"name": "nope"}).status_code == 403
    assert lab.get(f"{BASE}/images").status_code == 200
    assert admin.delete(f"{BASE}/members/{lab_id}").status_code == 200


def test_custom_role_grants_export_only(admin):
    lab_id = user_id("labeler@labeldesk.dev")
    name = f"rbac-{TAG}-exporter"
    role = admin.post(f"/api/ws/{WS}/roles", json={"name": name, "level": "project",
                                                   "permissions": ["project.export"]}).json()
    assert admin.patch(f"{BASE}/members/{lab_id}",
                       json={"role": "viewer", "custom_role_id": role["id"]}).status_code == 200
    lab = login("labeler@labeldesk.dev")
    perms = lab.get(f"{BASE}/permissions").json()
    assert "project.export" in perms["permissions"] and perms["project_role"] == "viewer"
    assert rbac.has("project.export", "member", "viewer", project_custom=tuple(role["permissions"]))
    assert lab.post(f"/api/images/{new_image()}/review", json={"approved": True}).status_code == 403
    assert admin.delete(f"/api/ws/{WS}/roles/{role['id']}").status_code == 200
    with SessionLocal() as db:
        assert db.get(ProjectMember, (project_id(), lab_id)).custom_role_id is None
    assert "project.export" not in lab.get(f"{BASE}/permissions").json()["permissions"]
    admin.delete(f"{BASE}/members/{lab_id}")


def test_workspace_admin_cannot_be_locked_out_of_a_project(admin):
    uid = user_id("demo@labeldesk.dev")
    assert admin.patch(f"{BASE}/members/{uid}", json={"role": "viewer"}).status_code == 200
    perms = admin.get(f"{BASE}/permissions").json()
    assert perms["project_role"] == "manager"          # ownership outranks a stale project row
    assert admin.delete(f"{BASE}/members/{uid}").status_code == 200


def test_workspace_custom_role_grants_billing_read(admin):
    lab_id = user_id("labeler@labeldesk.dev")
    name = f"rbac-{TAG}-billing-reader"
    role = admin.post(f"/api/ws/{WS}/roles", json={"name": name, "level": "workspace",
                                                   "permissions": ["workspace.billing"]}).json()
    assert admin.patch(f"/api/ws/{WS}/members/{lab_id}/custom-role",
                       json={"custom_role_id": role["id"]}).status_code == 200
    lab = login("labeler@labeldesk.dev")
    perms = lab.get(f"/api/ws/{WS}/permissions").json()["permissions"]
    assert "workspace.billing" in perms and "workspace.members" not in perms
    assert admin.patch(f"/api/ws/{WS}/members/{lab_id}/custom-role",
                       json={"custom_role_id": None}).status_code == 200
    assert "workspace.billing" not in lab.get(f"/api/ws/{WS}/permissions").json()["permissions"]
    assert admin.delete(f"/api/ws/{WS}/roles/{role['id']}").status_code == 200


def test_duplicate_role_name_is_conflict(admin):
    body = {"name": f"rbac-{TAG}-dup", "level": "workspace", "permissions": ["workspace.read"]}
    first = admin.post(f"/api/ws/{WS}/roles", json=body)
    assert first.status_code == 200, first.text
    assert admin.post(f"/api/ws/{WS}/roles", json=body).status_code == 409
    admin.delete(f"/api/ws/{WS}/roles/{first.json()['id']}")


def test_billing_member_cannot_invite():
    email = f"billing-{TAG}@rbac.test"
    c = TestClient(app)
    assert c.post("/api/auth/signup", json={"name": "Bill Ing", "email": email,
                                            "password": "longpassword1"}).status_code == 200
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        db.add(Member(workspace_id=ws_id(), user_id=uid, role="billing"))
        db.commit()
    bill = login(email, "longpassword1")
    assert bill.post(f"/api/ws/{WS}/invites", json={"email": f"x-{TAG}@rbac.test"}).status_code == 403
    assert bill.get(f"/api/ws/{WS}/keys").status_code == 403
    assert bill.get(f"{BASE}/images").status_code == 200       # billing keeps workspace.read


def test_only_project_manager_can_patch_project_members(admin):
    lab_id, rev_id = user_id("labeler@labeldesk.dev"), user_id("reviewer@labeldesk.dev")
    lab = login("labeler@labeldesk.dev")
    assert lab.patch(f"{BASE}/members/{rev_id}", json={"role": "viewer"}).status_code == 403
    assert admin.patch(f"{BASE}/members/{lab_id}", json={"role": "manager"}).status_code == 200
    assert lab.patch(f"{BASE}/members/{rev_id}", json={"role": "viewer"}).status_code == 200
    assert lab.patch(f"{BASE}/members/does-not-exist", json={"role": "viewer"}).status_code == 404
    assert lab.patch(f"{BASE}/members/{rev_id}", json={"role": "nope"}).status_code == 400
    admin.delete(f"{BASE}/members/{rev_id}")
    admin.delete(f"{BASE}/members/{lab_id}")


def test_non_member_cannot_read_project_roles():
    email = f"outsider-{TAG}@rbac.test"
    c = TestClient(app)
    assert c.post("/api/auth/signup", json={"name": "Out Sider", "email": email,
                                            "password": "longpassword1"}).status_code == 200
    out = login(email, "longpassword1")
    assert out.get(f"{BASE}/roles").status_code == 403
    assert out.get(f"{BASE}/permissions").status_code == 403


def test_workspace_roles_endpoint_and_permission_shape(admin):
    perms = admin.get(f"{BASE}/permissions").json()
    assert perms["workspace_role"] == "owner" and perms["project_role"] == "manager"
    assert perms["roles"] == list(PROJECT_ROLES) and perms["workspace_roles"] == list(WORKSPACE_ROLES)
    assert "workspace.project.delete" in perms["permissions"]
    assert perms["matrix"]["project"]["project.roles"] == ["manager"]
    assert admin.get(f"/api/ws/{WS}/permissions").json()["project_role"] is None
    scoped = admin.get(f"/api/ws/{WS}/permissions", params={"project": PR}).json()
    assert scoped["project_role"] == "manager"
    assert admin.get(f"/api/ws/{WS}/roles").status_code == 200
    assert admin.post(f"/api/ws/{WS}/roles", json={"name": f"rbac-{TAG}-bad", "level": "project",
                                                   "permissions": ["workspace.read"]}).status_code == 400


# --- classes -------------------------------------------------------------------------

def test_project_classes_follow_the_matrix(admin):
    """I4: add/edit/delete use project.classes — viewer 403, labeler 200."""
    lab_id = user_id("labeler@labeldesk.dev")
    assert admin.patch(f"{BASE}/members/{lab_id}", json={"role": "viewer"}).status_code == 200
    lab = login("labeler@labeldesk.dev")
    name = f"rbac-{TAG}-class"
    r = lab.post(f"{BASE}/classes", json={"name": name})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "requires project.classes"
    existing = admin.get(f"{BASE}/classes").json()[0]
    assert lab.patch(f"{BASE}/classes/{existing['id']}", json={"name": f"{name}-x"}).status_code == 403
    assert lab.delete(f"{BASE}/classes/{existing['id']}").status_code == 403

    assert admin.patch(f"{BASE}/members/{lab_id}", json={"role": "labeler"}).status_code == 200
    created = lab.post(f"{BASE}/classes", json={"name": name})
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert lab.patch(f"{BASE}/classes/{cid}", json={"name": f"{name}-renamed"}).status_code == 200
    assert lab.delete(f"{BASE}/classes/{cid}").status_code == 200
    assert admin.delete(f"{BASE}/members/{lab_id}").status_code == 200


# --- leaving and removal -------------------------------------------------------------

def test_removal_and_leaving_revoke_project_roles():
    """I5: removal (and self-leave) deletes ProjectMember rows, so a re-invite cannot inherit them."""
    email = f"returning-{TAG}@rbac.test"
    c = TestClient(app)
    assert c.post("/api/auth/signup", json={"name": "Returning User", "email": email,
                                            "password": "longpassword1"}).status_code == 200
    uid = user_id(email)
    with SessionLocal() as db:
        db.add(Member(workspace_id=ws_id(), user_id=uid, role="member"))
        db.add(ProjectMember(project_id=project_id(), user_id=uid, role="manager"))
        db.commit()
    user = login(email, "longpassword1")
    assert user.get(f"/api/ws/{WS}/permissions", params={"project": PR}).json()["project_role"] == "manager"

    admin = login()
    assert admin.delete(f"/api/ws/{WS}/members/{uid}").status_code == 200
    with SessionLocal() as db:
        assert db.get(ProjectMember, (project_id(), uid)) is None
        row = db.scalar(select(Audit).where(Audit.action == "member.remove", Audit.target == email)
                        .order_by(Audit.created.desc()))
        assert row is not None and row.meta["projects"] == 1

    # Re-invited as a plain annotator: the stale manager role must not come back.
    with SessionLocal() as db:
        db.add(Member(workspace_id=ws_id(), user_id=uid, role="annotator"))
        db.commit()
    assert login(email, "longpassword1").get(
        f"/api/ws/{WS}/permissions", params={"project": PR}).json()["project_role"] == "labeler"

    # Leaving on your own takes the same cleanup path.
    with SessionLocal() as db:
        db.add(ProjectMember(project_id=project_id(), user_id=uid, role="manager"))
        db.commit()
    assert login(email, "longpassword1").delete(f"/api/ws/{WS}/members/{uid}").status_code == 200
    with SessionLocal() as db:
        assert db.get(ProjectMember, (project_id(), uid)) is None
        row = db.get(Member, (ws_id(), uid))
        if row:
            db.delete(row)
        db.commit()


# --- audit filters -------------------------------------------------------------------

def test_audit_filters_and_pagination(admin):
    marker = f"audit-{TAG}"
    ids = []
    with SessionLocal() as db:
        for i in range(3):
            row = Audit(workspace_id=ws_id(), user_id=user_id("demo@labeldesk.dev"), action=f"member.{marker}",
                        target=f"{marker}-{i}", meta={"probe": marker})
            db.add(row)
            db.flush()
            ids.append(row.id)
        nullrow = Audit(workspace_id=ws_id(), user_id=None, action=f"member.{marker}", target=f"{marker}-api", meta={})
        db.add(nullrow)
        db.flush()
        ids.append(nullrow.id)
        db.commit()
    since = time.time() - 60
    rows = admin.get(f"/api/ws/{WS}/audit", params={
        "action": "member", "user": "demo", "since": since, "q": marker}).json()
    assert {r["id"] for r in rows} == set(ids[:3])
    assert {r["id"] for r in admin.get(f"/api/ws/{WS}/audit", params={"user": "api"}).json()} >= {ids[3]}
    page = admin.get(f"/api/ws/{WS}/audit", params={"action": "member", "q": marker, "limit": 2, "offset": 1}).json()
    assert len(page) == 2
    allrows = admin.get(f"/api/ws/{WS}/audit", params={"action": "member", "q": marker}).json()
    assert [r["id"] for r in page] == [r["id"] for r in allrows][1:3]
    with SessionLocal() as db:
        for rid in ids:
            db.delete(db.get(Audit, rid))
        db.commit()
