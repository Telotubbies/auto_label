"""T-1304 — the cross-workspace IDOR and auth-bypass matrix.

Two tenants, one row of every resource kind in each. Workspace A's principal (a real session,
and an API key where the product accepts one) asks for workspace B's id: the answer must be
404, the body must not carry B's name or id, and B's rows must not change. The control row asks
for A's own id and must succeed, so a route that 404s everything cannot pass.

The exact refusal is part of the contract: a 403 that says "no access" is an existence oracle
just as a 200 is a leak. Two rows cannot answer 404, and say why in the table: an audit export
takes filters rather than an id, so its probe is a filter on B's marker and asserts an empty
export; a deployment alias names its model in a body, so the foreign id is a validation error,
and the test proves the same 400 answers a nonexistent id (no oracle).

The auth-bypass half is the other side: every malformed credential, a publishable key on a write
route, a refresh token replayed after rotation, and a signed URL re-pointed at a foreign path.

Nothing here mocks the surface under test. The session is a real login, the key is a real key,
the rows are real rows in the seeded SQLite database.
"""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app import routers as router_pkg
from app.config import DATA_DIR, SECRET
from app.db import SessionLocal
from app.main import app
from app.metrics import router as metrics_router
from app.models import (ApiKey, AlertChannel, Audit, Connector, DeploymentAlias, EventSearchFrame,
                        Image, Job, LabelClass, Member, Project, ProjectMember, Stream, TrainedModel,
                        User, Version, Video, Webhook, Workflow, Workspace)
from app.security import issue_access, new_api_key, sign_path
from conftest import login

PW = "longpassword1"
BRAVO = "Bravo"          # every row in workspace B carries this word, so one assertion covers all

# --- the resource table -------------------------------------------------------------------
#
# One dict per kind. `url`/`own` are request templates; `{placeholders}` come from `ids`.
# `key` is the same idea over an API-key-authenticated route, where one exists: a key is a
# developer-API credential, not a session, so a session route answers 401 before the route runs.
# A reviewer adds a kind by adding one dict.

FOREIGN = [
    {"kind": "project", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{b_project_slug}",
     "own": "/api/ws/{a_ws}/projects/{a_project_slug}",
     "key": "/api/v1/projects/{b_project_slug}"},
    {"kind": "image", "method": "GET",
     "url": "/api/images/{b_image}", "own": "/api/images/{a_image}",
     "key": "/api/v1/images/{b_image}"},
    {"kind": "annotation", "method": "PUT",
     "url": "/api/images/{b_image}/annotations", "own": "/api/images/{a_image}/annotations",
     "json": {"annotations": []}, "key": "/api/v1/images/{b_image}/annotations"},
    {"kind": "version", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{a_project}/versions/{b_version}",
     "own": "/api/ws/{a_ws}/projects/{a_project}/versions/{a_version}",
     "key": "/api/v1/projects/{a_project}/versions/{b_version}/export",
     "key_method": "POST", "key_json": {"format": "coco"}},
    {"kind": "model", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{a_project}/models/{b_model}",
     "own": "/api/ws/{a_ws}/projects/{a_project}/models/{a_model}",
     "key": "/api/v1/models/{b_model}"},
    {"kind": "job", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{a_project}/jobs/{b_job}",
     "own": "/api/ws/{a_ws}/projects/{a_project}/jobs/{a_job}",
     "key": "/api/v1/jobs/{b_job}"},
    {"kind": "stream", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{a_project}/streams/{b_stream}",
     "own": "/api/ws/{a_ws}/projects/{a_project}/streams/{a_stream}"},
    {"kind": "connector", "method": "GET",
     "url": "/api/ws/{a_ws}/connectors/{b_connector}/objects",
     "own": "/api/ws/{a_ws}/connectors/{a_connector_spare}", "own_method": "DELETE"},
    {"kind": "webhook", "method": "GET",
     "url": "/api/ws/{a_ws}/webhooks/{b_webhook}/deliveries",
     "own": "/api/ws/{a_ws}/webhooks/{a_webhook}/deliveries"},
    {"kind": "alert_channel", "method": "GET",
     "url": "/api/ws/{a_ws}/alerts/{b_alert}/deliveries",
     "own": "/api/ws/{a_ws}/alerts/{a_alert}/deliveries"},
    {"kind": "workflow", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{a_project}/workflows/{b_workflow}",
     "own": "/api/ws/{a_ws}/projects/{a_project}/workflows/{a_workflow}"},
    {"kind": "api_key", "method": "DELETE",
     "url": "/api/ws/{a_ws}/keys/{b_key}", "own": "/api/ws/{a_ws}/keys/{a_key_spare}"},
    {"kind": "audit_export", "method": "GET",
     "url": "/api/ws/{a_ws}/audit/export?format=json&q={b_audit_marker}",
     "own": "/api/ws/{a_ws}/audit/export?format=json&q={a_audit_marker}",
     "foreign_status": 200},
    {"kind": "deployment_alias", "method": "PUT",
     "url": "/api/ws/{a_ws}/projects/{a_project}/deployments/production",
     "own": "/api/ws/{a_ws}/projects/{a_project}/deployments/production",
     "json": {"model_id": "{b_model}"}, "own_json": {"model_id": "{a_model}"},
     # the alias names a model in a body, so a foreign id is a validation error, not a path lookup;
     # the same 400 for a nonexistent model id proves the answer is not an existence oracle
     "foreign_status": 400, "no_oracle": True},
    {"kind": "video", "method": "GET",
     "url": "/api/ws/{a_ws}/projects/{a_project}/videos/{b_video}",
     "own": "/api/ws/{a_ws}/projects/{a_project}/videos/{a_video}"},
    {"kind": "event_search_frame", "method": "POST",
     "url": "/api/ws/{a_ws}/projects/{a_project}/event-search/frames/{b_frame}/confirm",
     "own": "/api/ws/{a_ws}/projects/{a_project}/event-search/frames/{a_frame}/confirm",
     "json": {"confirmed": True}},
]
BY_KIND = {row["kind"]: row for row in FOREIGN}
KINDS = tuple(BY_KIND)
# T-1304's matrix found a real leak on 2026-11-18: `deps.image_ctx` answers 403 "no access to this
# image" for an id in a workspace the caller is not in, which confirms the id exists. The card's
# contract is 404, but `test_security.py::test_cross_workspace_isolation` and
# `test_parity_guard_area3.py::test_foreign_workspace_image_id_stays_out_of_reach` deliberately pin
# the 403, and neither file belongs to this card. Until the PM rules, the row is a strict xfail:
# green while the product is wrong, red the moment someone fixes it and forgets to drop the mark.
PRODUCT_403: set[str] = set()   # fixed in deps.image_ctx: a foreign image is 404


def fill(value, ids):
    """Format a string template, and every string inside a JSON payload, from `ids`."""
    if isinstance(value, str):
        return value.format(**ids)
    if isinstance(value, dict):
        return {key: fill(item, ids) for key, item in value.items()}
    return value


def call(client, row, which="url", ids=None):
    method = row.get(f"{which}_method", row["method"])
    if which == "own":
        payload = row.get("own_json", row.get("json"))
    elif which == "key":
        payload = row.get("key_json", row.get("json"))
    else:
        payload = row.get("json")
    return client.request(method, fill(row[which], ids), json=fill(payload, ids) if payload else None)


# --- fixtures ------------------------------------------------------------------------------

def _new_user(db, name: str, role: str, ws: Workspace) -> User:
    user = User(email=f"{name.lower().replace(' ', '-')}@sec-idor.test", name=name,
                pw_hash="", email_verified=time.time())
    db.add(user)
    db.flush()
    db.add(Member(workspace_id=ws.id, user_id=user.id, role=role))
    db.flush()
    return user


def tenant_b() -> dict:
    """What a foreign write could change in workspace B, read straight from the database."""
    with SessionLocal() as db:
        ws = db.query(Workspace).filter(Workspace.slug == "bravo-workspace").one()
        projects = db.query(Project).filter(Project.workspace_id == ws.id).all()
        pids = [p.id for p in projects]
        image = db.query(Image).filter(Image.project_id.in_(pids)).one()
        return {
            "projects": len(projects),
            "images": db.query(Image).filter(Image.project_id.in_(pids)).count(),
            "image_status": image.status, "image_name": image.name,
            "annotations": len(image.annotations or []),
            "versions": db.query(Version).filter(Version.project_id.in_(pids)).count(),
            "models": db.query(TrainedModel).filter(TrainedModel.workspace_id == ws.id).count(),
            "jobs": db.query(Job).filter(Job.workspace_id == ws.id).count(),
            "streams": db.query(Stream).filter(Stream.workspace_id == ws.id).count(),
            "aliases": db.query(DeploymentAlias).filter(DeploymentAlias.project_id.in_(pids)).count(),
            "keys": db.query(ApiKey).filter(ApiKey.workspace_id == ws.id).count(),
        }


@pytest.fixture(scope="module")
def live():
    """Two tenants with one row of every kind, A's session, A's key and A's publishable key."""
    with TestClient(app) as c:
        made = c.post("/api/auth/signup", json={"name": "Alpha Owner", "email": "alpha@sec-idor.test",
                                                "password": PW, "workspace": "Alpha Workspace"})
        assert made.status_code == 200, made.text
        other = c.post("/api/auth/signup", json={"name": "Bravo Owner", "email": "bravo@sec-idor.test",
                                                 "password": PW, "workspace": "Bravo Workspace"})
        assert other.status_code == 200, other.text
        headers = login(c, "alpha@sec-idor.test", PW)
        a_ws_slug = c.get("/api/me", headers=headers).json()["workspaces"][0]["slug"]

        with SessionLocal() as db:
            a_ws = db.query(Workspace).filter(Workspace.slug == a_ws_slug).one()
            b_ws = db.query(Workspace).filter(Workspace.slug == "bravo-workspace").one()
            owner_a = db.get(User, a_ws.owner_id)
            member = _new_user(db, "Alpha Member", "annotator", a_ws)
            labeler = _new_user(db, "Alpha Labeler", "annotator", a_ws)

            a_proj = Project(workspace_id=a_ws.id, slug="alpha-proj", name="Alpha Project", settings={})
            b_proj = Project(workspace_id=b_ws.id, slug="bravo-proj", name="Bravo Project", settings={})
            db.add_all([a_proj, b_proj]); db.flush()
            db.add(ProjectMember(project_id=a_proj.id, user_id=labeler.id, role="labeler"))

            a_class = LabelClass(project_id=a_proj.id, name="alpha-class", color="#ef4444")
            b_class = LabelClass(project_id=b_proj.id, name="Bravo-class", color="#3b82f6")
            db.add_all([a_class, b_class]); db.flush()

            a_image = Image(project_id=a_proj.id, name="alpha-image.jpg", sha256="a" * 64, width=8, height=8,
                            path="projects/alpha/images/alpha-image.jpg", thumb="projects/alpha/alpha.jpg",
                            status="done", created=time.time())
            b_image = Image(project_id=b_proj.id, name="Bravo-image.jpg", sha256="b" * 64, width=8, height=8,
                            path="projects/bravo/images/bravo-image.jpg", thumb="projects/bravo/bravo.jpg",
                            status="review", created=time.time(),
                            annotations=[{"id": "b-ann", "classId": "bc", "shape": {"kind": "bbox", "x": 0, "y": 0,
                                                                                   "w": 1, "h": 1}}],
                            n_annotations=1)
            db.add_all([a_image, b_image]); db.flush()

            a_version = Version(project_id=a_proj.id, number=1, name="Alpha v1", status="ready")
            b_version = Version(project_id=b_proj.id, number=1, name="Bravo v1", status="ready")
            db.add_all([a_version, b_version]); db.flush()

            a_model = TrainedModel(workspace_id=a_ws.id, project_id=a_proj.id, version_id=a_version.id,
                                   name="Alpha model", arch="yolo26n", task="detect", status="ready")
            b_model = TrainedModel(workspace_id=b_ws.id, project_id=b_proj.id, version_id=b_version.id,
                                   name="Bravo model", arch="yolo26n", task="detect", status="ready")
            db.add_all([a_model, b_model]); db.flush()

            a_job = Job(workspace_id=a_ws.id, project_id=a_proj.id, kind="export", status="done")
            b_job = Job(workspace_id=b_ws.id, project_id=b_proj.id, kind="export", status="done")
            db.add_all([a_job, b_job])

            a_stream = Stream(workspace_id=a_ws.id, project_id=a_proj.id, name="Alpha stream",
                              source="file:videos/alpha.mp4", model_ref="ultralytics:yolo26n")
            b_stream = Stream(workspace_id=b_ws.id, project_id=b_proj.id, name="Bravo stream",
                              source="file:videos/bravo.mp4", model_ref="ultralytics:yolo26n")
            db.add_all([a_stream, b_stream])

            a_conn = Connector(workspace_id=a_ws.id, kind="s3", name="Alpha connector", config={"bucket": "a"})
            a_conn_spare = Connector(workspace_id=a_ws.id, kind="s3", name="Alpha spare", config={"bucket": "a2"})
            b_conn = Connector(workspace_id=b_ws.id, kind="s3", name="Bravo connector", config={"bucket": "b"})
            db.add_all([a_conn, a_conn_spare, b_conn])

            a_hook = Webhook(workspace_id=a_ws.id, url="https://alpha.example/hook", secret="whsec_alpha",
                             events=["job.done"])
            b_hook = Webhook(workspace_id=b_ws.id, url="https://bravo.example/hook", secret="whsec_bravo",
                             events=["job.done"])
            db.add_all([a_hook, b_hook])

            a_alert = AlertChannel(workspace_id=a_ws.id, kind="email", name="Alpha alerts", config={})
            b_alert = AlertChannel(workspace_id=b_ws.id, kind="email", name="Bravo alerts", config={})
            db.add_all([a_alert, b_alert])

            a_wf = Workflow(workspace_id=a_ws.id, project_id=a_proj.id, name="Alpha workflow", blocks=[])
            b_wf = Workflow(workspace_id=b_ws.id, project_id=b_proj.id, name="Bravo workflow", blocks=[])
            db.add_all([a_wf, b_wf])

            a_video = Video(project_id=a_proj.id, workspace_id=a_ws.id, name="Alpha video",
                            path="videos/alpha.mp4", status="ready")
            b_video = Video(project_id=b_proj.id, workspace_id=b_ws.id, name="Bravo video",
                            path="videos/bravo.mp4", status="ready")
            db.add_all([a_video, b_video]); db.flush()

            a_frame = EventSearchFrame(workspace_id=a_ws.id, project_id=a_proj.id, source="footage",
                                       source_id=a_image.id, path=a_image.path, label="Alpha frame")
            b_frame = EventSearchFrame(workspace_id=b_ws.id, project_id=b_proj.id, source="footage",
                                       source_id=b_image.id, path=b_image.path, label="Bravo frame")
            db.add_all([a_frame, b_frame])

            a_alias = DeploymentAlias(project_id=a_proj.id, alias="production", model_id=a_model.id)
            b_alias = DeploymentAlias(project_id=b_proj.id, alias="production", model_id=b_model.id)
            db.add_all([a_alias, b_alias])

            _, b_key_prefix, b_key_hash = new_api_key()
            b_key = ApiKey(workspace_id=b_ws.id, name="Bravo key", prefix=b_key_prefix, hash=b_key_hash,
                           scopes=["read"])
            db.add(b_key)

            a_audit = Audit(workspace_id=a_ws.id, user_id=owner_a.id, action="sec.test",
                            target="alpha-audit-marker")
            b_audit = Audit(workspace_id=b_ws.id, user_id=b_ws.owner_id, action="sec.test",
                            target="bravo-audit-marker")
            db.add_all([a_audit, b_audit])

            # the surfaces whose routes sit behind a flag, enabled for A and left off for B
            from app.services.flags import set_flag
            for key in ("task_10b", "task_22", "task_31", "task_33", "task_38"):
                set_flag(db, a_ws.id, key, True)

            db.commit()

            ids = {
                "a_ws": a_ws.slug, "b_ws": b_ws.slug, "a_project": a_proj.slug,
                "a_project_slug": a_proj.slug, "b_project_slug": b_proj.slug,
                "a_image": a_image.id, "b_image": b_image.id, "a_version": a_version.id,
                "b_version": b_version.id, "a_model": a_model.id, "b_model": b_model.id,
                "a_job": a_job.id, "b_job": b_job.id, "a_stream": a_stream.id, "b_stream": b_stream.id,
                "a_connector": a_conn.id, "a_connector_spare": a_conn_spare.id, "b_connector": b_conn.id,
                "a_webhook": a_hook.id, "b_webhook": b_hook.id, "a_alert": a_alert.id, "b_alert": b_alert.id,
                "a_workflow": a_wf.id, "b_workflow": b_wf.id, "b_key": b_key.id,
                "a_audit_marker": "alpha-audit-marker", "b_audit_marker": "bravo-audit-marker",
                "a_video": a_video.id, "b_video": b_video.id, "a_frame": a_frame.id, "b_frame": b_frame.id,
            }
            member_id, labeler_id = member.id, labeler.id

        key = c.post(f"/api/ws/{a_ws_slug}/keys", headers=headers, json={"name": "matrix key",
                                                                        "scopes": ["read", "upload", "write", "train", "infer"]})
        assert key.status_code == 200, key.text
        pub = c.post(f"/api/ws/{a_ws_slug}/keys", headers=headers, json={"name": "Alpha publishable",
                                                                        "publishable": True})
        assert pub.status_code == 200, pub.text
        spare = c.post(f"/api/ws/{a_ws_slug}/keys", headers=headers, json={"name": "Alpha spare", "scopes": ["read"]})
        assert spare.status_code == 200, spare.text
        ids["a_key_spare"] = spare.json()["id"]

        ids["a_user"] = owner_a.id
        ids["member"] = member_id
        ids["labeler"] = labeler_id

        session = TestClient(app)
        session.headers.update(headers)
        api_key = TestClient(app)
        api_key.headers.update({"x-api-key": key.json()["key"]})
        publishable = TestClient(app)
        publishable.headers.update({"x-api-key": pub.json()["key"]})

        yield {"session": session, "key": api_key, "pub": publishable,
               "ids": ids, "owner_email": "alpha@sec-idor.test", "b_baseline": tenant_b()}


# --- the matrix ------------------------------------------------------------------------------

def _matrix_param(row):
    if row["kind"] in PRODUCT_403:
        return pytest.param(row, id=row["kind"], marks=pytest.mark.xfail(
            strict=True,
            reason="image_ctx answers 403 'no access' for a foreign image (existence oracle); "
                   "the 404 fix needs the two guard tests that pin 403, which this card does not own"))
    return pytest.param(row, id=row["kind"])


@pytest.mark.parametrize("row", [_matrix_param(row) for row in FOREIGN])
def test_foreign_id_is_404_for_every_resource_kind(live, row):
    r = call(live["session"], row, "url", live["ids"])

    assert r.status_code == row.get("foreign_status", 404), (row["kind"], r.status_code, r.text[:300])
    assert BRAVO not in r.text, row["kind"]
    for foreign_id in (value for key, value in live["ids"].items() if key.startswith("b_")):
        assert foreign_id not in r.text, (row["kind"], foreign_id)
    for leaked in ("Traceback", "sqlalchemy", "no access to this"):
        assert leaked not in r.text, (row["kind"], leaked)
    if row["kind"] == "audit_export":
        assert r.json() == [], "a filter on another tenant's marker must export nothing"
    if row.get("no_oracle"):
        bogus = call(live["session"], row, "url", {**live["ids"], "b_model": "model-not-in-any-workspace"})
        assert (bogus.status_code, bogus.text) == (r.status_code, r.text), \
            "a foreign id and a nonexistent id must be indistinguishable"
    assert tenant_b() == live["b_baseline"], f"{row['kind']} changed workspace B"


@pytest.mark.parametrize("row", FOREIGN, ids=[row["kind"] for row in FOREIGN])
def test_foreign_id_is_404_for_an_api_key(live, row):
    if row.get("key"):
        # a key is a developer-API credential: only /api/v1 accepts it, and there the row is 404
        r = call(live["key"], row, "key", live["ids"])
        assert r.status_code == 404, (row["kind"], r.status_code, r.text[:300])
        assert BRAVO not in r.text, row["kind"]
    else:
        # no developer-API route exists for this kind yet: the session route must refuse the key
        # (401) before it can reach another tenant's row, and the body carries no tenant data
        r = call(live["key"], row, "url", live["ids"])
        assert r.status_code == 401, (row["kind"], r.status_code, r.text[:300])
        assert BRAVO not in r.text, row["kind"]

    if row["kind"] == "api_key":
        # a revoked key is a dead credential, never a fallback to another identity
        made = live["session"].post(f"/api/ws/{live['ids']['a_ws']}/keys",
                                    json={"name": "revoked mid-suite", "scopes": ["read"]})
        assert made.status_code == 200, made.text
        alive = TestClient(app).get("/api/v1/whoami", headers={"x-api-key": made.json()["key"]})
        assert alive.status_code == 200, alive.text
        gone = live["session"].delete(f"/api/ws/{live['ids']['a_ws']}/keys/{made.json()['id']}")
        assert gone.status_code == 200, gone.text
        dead = TestClient(app).get("/api/v1/whoami", headers={"x-api-key": made.json()["key"]})
        assert dead.status_code == 401, dead.text
    assert tenant_b() == live["b_baseline"], f"{row['kind']} changed workspace B"


@pytest.mark.parametrize("row", FOREIGN, ids=[row["kind"] for row in FOREIGN])
def test_own_id_is_200_for_every_resource_kind(live, row):
    r = call(live["session"], row, "own", live["ids"])

    assert r.status_code == 200, (row["kind"], r.status_code, r.text[:300])
    if row["kind"] == "audit_export":
        assert [x["target"] for x in r.json()] == ["alpha-audit-marker"]


def test_no_foreign_row_appears_in_a_list(live):
    """B's rows must not surface in A's lists, search and exports, and A's own rows must."""
    s, ids = live["session"], live["ids"]
    a_ws, a_proj = ids["a_ws"], ids["a_project"]

    listed = {
        "projects": s.get(f"/api/ws/{a_ws}/projects"),
        "models": s.get(f"/api/ws/{a_ws}/models"),
        "jobs": s.get(f"/api/ws/{a_ws}/jobs"),
        "deployments": s.get(f"/api/ws/{a_ws}/deployments"),
        "keys": s.get(f"/api/ws/{a_ws}/keys"),
        "audit": s.get(f"/api/ws/{a_ws}/audit", params={"q": "audit-marker"}),
        "search": s.get(f"/api/ws/{a_ws}/projects/{a_proj}/images", params={"q": "image"}),
        "export": s.get(f"/api/ws/{a_ws}/audit/export", params={"format": "json", "q": "audit-marker"}),
        "v1 projects": live["key"].get("/api/v1/projects"),
        "v1 models": live["key"].get("/api/v1/models"),
        "v1 deployments": live["key"].get("/api/v1/deployments"),
    }
    for name, r in listed.items():
        assert r.status_code == 200, (name, r.status_code, r.text[:300])
        assert BRAVO not in r.text, name
        assert ids["b_image"] not in r.text and ids["b_key"] not in r.text, name

    # the control: an empty-everything route cannot pass either
    assert "Alpha Project" in listed["projects"].text
    assert "Alpha model" in listed["models"].text
    assert "Alpha" in listed["audit"].text
    assert "alpha-image.jpg" in listed["search"].text
    assert "alpha-audit-marker" in listed["export"].text
    assert "Alpha Project" in listed["v1 projects"].text

    # and the same export filtered on B's marker is empty, not a 200 carrying a foreign row
    empty = s.get(f"/api/ws/{a_ws}/audit/export", params={"format": "json", "q": ids["b_audit_marker"]})
    assert empty.status_code == 200 and empty.json() == []


def test_a_foreign_file_url_is_403(live):
    """A's signature cannot be re-pointed at B's path; the signature covers the whole path."""
    s = live["session"]

    alpha_rel = "ws/alpha-workspace/projects/alpha-proj/images/alpha.jpg"
    bravo_rel = "ws/bravo-workspace/projects/bravo-proj/images/bravo.jpg"
    for rel in (alpha_rel, bravo_rel):
        path = DATA_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xd8\xff\xd9")

    own = s.get(sign_path(alpha_rel))
    assert own.status_code == 200, own.text
    assert own.content == b"\xff\xd8\xff\xd9"

    # keep A's exp/sig, swap the path for B's: the classic signed-URL IDOR attempt
    query = sign_path(alpha_rel).split("?", 1)[1]
    swapped = s.get(f"/api/files/{bravo_rel}?{query}")
    assert swapped.status_code == 403, swapped.text
    assert b"\xff\xd8" not in swapped.content

    # and a tampered signature is refused rather than trusted. A signature minted for B's path is
    # the capability itself, so possession of one is the recognised residual risk, not this test.
    exp, sig = query.split("&viewer=")[0].split("&")
    forged = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    assert s.get(f"/api/files/{bravo_rel}?{exp}&{forged}").status_code == 403


def test_refresh_replay_after_rotation_is_401(live):
    c = TestClient(app)
    first = c.post("/api/auth/login", json={"email": live["owner_email"], "password": PW})
    assert first.status_code == 200, first.text
    old = first.json()["refresh_token"]

    rotated = c.post("/api/auth/refresh", json={"refresh_token": old})
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != old

    replay = c.post("/api/auth/refresh", json={"refresh_token": old})
    assert replay.status_code == 401
    assert BRAVO not in replay.text and "sub" not in replay.text


def test_publishable_key_cannot_reach_a_write_route(live):
    """Every write in the table refuses the browser-safe key, and so does every non-infer v1 read."""
    pub, ids = live["pub"], live["ids"]
    for row in FOREIGN:
        method = row.get("own_method", row["method"])
        if method == "GET":
            continue
        r = call(pub, row, "own", ids)
        assert not r.is_success, (row["kind"], r.status_code, r.text[:200])
        assert r.status_code in (401, 403), (row["kind"], r.status_code, r.text[:200])
        assert BRAVO not in r.text, row["kind"]

    for url in ("/api/v1/projects", "/api/v1/whoami", "/api/v1/models"):
        r = pub.get(url)
        assert r.status_code == 403, (url, r.status_code, r.text)
        assert "infer" in r.text or "scope" in r.text, url


def test_expired_and_tampered_tokens_are_401(live):
    owner = live["ids"]["a_user"]
    now = int(time.time())
    expired = jwt.encode({"sub": owner, "iat": now - 3600, "exp": now - 60, "scope": "access"},
                         SECRET, algorithm="HS256")
    valid = issue_access(owner)
    head, payload, sig = valid.rsplit(".", 2)
    flipped = "A" if sig[0] != "A" else "B"
    tampered = f"{head}.{payload}.{flipped}{sig[1:]}"

    for label, token in {
        "no header": None,
        "garbage": "Bearer garbage",
        "expired": f"Bearer {expired}",
        "tampered": f"Bearer {tampered}",
    }.items():
        headers = {} if token is None else {"Authorization": token}
        r = TestClient(app).get("/api/me", headers=headers)
        assert r.status_code == 401, (label, r.status_code, r.text)
        assert live["owner_email"] not in r.text, label
        assert owner not in r.text, label
        assert "eyJ" not in r.text, label


def test_a_deleted_users_token_is_401(live):
    with SessionLocal() as db:
        user = User(email="deleted@sec-idor.test", name="Deleted", pw_hash="", email_verified=time.time())
        db.add(user); db.commit()
        uid = user.id
        token = issue_access(uid)
        db.delete(user); db.commit()

    r = TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert uid not in r.text and "deleted@sec-idor.test" not in r.text


# --- the gate guard --------------------------------------------------------------------------

# A router is either exercised by a kind row above, or named here with the reason it has no
# workspace row at all. A new router file must add one or the other; that is the point.
COVERED = {
    "projects": ("project",),
    "images": ("image", "annotation"),
    "videos": ("video",),
    "versions": ("version",),
    "training": ("model",),
    "devapi": ("project", "image", "annotation", "version", "model", "job"),
    "devapi_actions": ("version",),
    "connectors": ("connector",),
    "webhooks": ("webhook",),
    "alerts": ("alert_channel",),
    "workflows": ("workflow",),
    "deployments": ("deployment_alias",),
    "streams": ("stream",),
    "event_search": ("event_search_frame",),
    "workspaces": ("api_key",),
    "audit": ("audit_export",),
}
OMITTED = {
    "auth": "the auth-bypass tests in this file: refresh replay, expired/tampered tokens, deleted user",
    "health": "/api/health, /api/healthz, /api/readyz have no workspace resource",
    "metrics": "/api/metrics is process metrics, token-gated and 404 when unset",
    "admin": "platform-operator console, superadmin only; no tenant row is addressed by id",
    "anomaly": "project resource outside this card's kind list (T-1310 owns its audit coverage)",
    "batch_inference": "job rows are covered by the job kind",
    "dashboards": "project resource outside this card's kind list",
    "devmail": "dev-only inbox, not mounted in production",
    "flags": "workspace settings, not a tenant row",
    "inference": "inference-hub surface, gated by task_inference",
    "insights": "read-only analytics over A's own project; no id-addressed row",
    "insights_lineage": "read-only analytics over A's own project",
    "insights_models": "read-only analytics over A's own model",
    "compute": "read-only dashboard scoped to the caller's own workspace via ws_ctx; no id-addressed row",
    "labeling": "project workflow, outside this card's kind list",
    "ocr": "project resource outside this card's kind list",
    "ops": "operator websocket, token-gated",
    "ot": "project resource outside this card's kind list",
    "playground": "inference-only surface; no persisted tenant row",
    "privacy": "workspace/project settings, not an id-addressed row",
    "public": "anonymous read-only dataset page; no tenant caller, its 404-on-private is in tests/test_public_dataset.py",
    "publishing": "project settings, gated by task_a1_publish; its foreign-slug 404 is in tests/test_publishing.py",
    "rbac": "roles are workspace settings; the key kind proves key tenancy",
    "registry": "read-only catalogue of A's own models",
    "remote": "remote-GPU worker, worker-token only",
    "semantic": "search over A's own project; the list test asserts no foreign row",
}
# Routes declared on the app itself rather than a router. `/api/files` is the signed-URL row;
# the rest carry no tenant data. A new one must be classified here.
APP_ROUTES = {"/api/health", "/api/files/{rel:path}", "/openapi.json", "/docs",
              "/docs/oauth2-redirect", "/redoc", "/{path:path}"}


def _attached_routers():
    """Every APIRouter the app mounts, following FastAPI's lazy `_IncludedRouter` wrapper."""
    found = {}
    for route in app.routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            found[id(original)] = original
    return found


def _router_names():
    attached = _attached_routers()
    names = {}
    for module_name, module in vars(router_pkg).items():
        if module_name.startswith("__") or not hasattr(module, "__dict__"):
            continue
        for value in vars(module).values():
            if id(value) in attached:
                names[id(value)] = module_name
    if id(metrics_router) in attached:
        names[id(metrics_router)] = "metrics"
    return names


def test_matrix_covers_every_router():
    """A new router file (or a second router beside an old one) must add a row or a reason."""
    names = _router_names()
    unknown = sorted(set(names.values()) - set(COVERED) - set(OMITTED))
    assert not unknown, f"add a FOREIGN row or an OMITTED reason for: {unknown}"

    covered_kinds = {kind for kinds in COVERED.values() for kind in kinds}
    assert set(KINDS) <= covered_kinds, sorted(set(KINDS) - covered_kinds)
    assert not set(COVERED) & set(OMITTED), "a router is either covered or omitted, not both"

    # every mounted router was identified: a route whose owner is unknown would be untested
    assert len(names) == len(_attached_routers()), (names, len(_attached_routers()))

    # and a route declared on the app itself is classified rather than silently untested
    direct = {route.path for route in app.routes
              if getattr(route, "methods", None) and getattr(route, "original_router", None) is None}
    assert direct <= APP_ROUTES, sorted(direct - APP_ROUTES)
