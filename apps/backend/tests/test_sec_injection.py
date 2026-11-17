"""T-1305 — injection, stored XSS, path traversal and SSRF: one adversarial file, four payload tables.

`safefetch` and the stream guard have good unit tests. This file covers the *route* surface
instead: every place a user string reaches SQL, HTML, a file path or an outbound connection.
The payloads are data (module-level tuples below) so a reviewer can read the table. Each group is
a `parametrize` over its table with ids naming the payload.

Two fixtures make the groups non-vacuous:

* ``no_network`` raises on ``socket.connect`` for the whole test, so an SSRF that slips past
  validation fails loudly instead of reaching the internet; ``test_the_socket_guard_blocks_a_real_connection``
  proves the guard itself works.
* ``opened`` records every ``open``/``Path.open``, so a traversal test can assert that no path
  outside ``LD_DATA_DIR`` was ever opened, not merely that the response was a 404.

Some payloads are refused by a designed rule rather than stored (a class name with punctuation, a
URL scheme the route does not speak, a filename that is not an image). Those rows assert *that*
refusal: a 400 from a validation rule is the product working, not a hole this file should widen.

What is deliberately not covered here: no browser is involved, so "no XSS" means "the API
returns the characters it stored and no frontend sink takes a raw field" (the grep test below).
"""
import asyncio
import builtins
import io
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import text

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Connector, Image, Project, Stream, Version, Webhook, Workspace
from app.security import sign_path, sign_query
from conftest import login

PW = "longpassword1"
ALPHA_EMAIL = "alpha@sec-injection.test"
BRAVO_EMAIL = "bravo@sec-injection.test"
BRAVO = "Bravo"                      # every row in workspace B carries this word


def _jpeg() -> bytes:
    """Unique bytes per call: the ingest dedupes on content hash, so a shared sample is a duplicate."""
    buf = io.BytesIO()
    PImage.new("RGB", (8, 8), tuple(os.urandom(3))).save(buf, "JPEG")
    return buf.getvalue()


# --- the four tables ------------------------------------------------------------------------

# 1. SQL injection / query-language abuse. Every surface that takes free text reaches SQL
#    either as a bound parameter or through a whitelist; nothing here may carry a 500.
SQLI = (
    ("quote-or", "' OR 1=1--"),
    ("double-quote", '"'),
    ("percent", "%"),
    ("underscore", "_"),
    ("drop-table", "'; DROP TABLE images;--"),
    ("nul", "\x00"),
    ("5000-chars", "A" * 5000),
    ("combining", "e\u0301\u0301\u0301\u0327"),
)

# 2. Stored/reflected XSS. The API stores text; the frontend renders it as text.
XSS = (
    ("img-onerror", "<img src=x onerror=alert(1)>"),
    ("svg-onload", '"><svg/onload=alert(1)>'),
    ("javascript-url", "javascript:alert(1)"),
)

# 3. Path traversal, in every encoding a browser or a shell may send.
TRAVERSAL = (
    ("dotdot-unix", "../../etc/passwd"),
    ("dotdot-windows", "..\\..\\win.ini"),
    ("percent-encoded", "%2e%2e%2f"),
    ("four-dots", "....//"),
    ("absolute", "/etc/passwd"),
    ("drive", "C:\\Windows\\win.ini"),
    ("device-con", "CON"),
    ("device-nul", "NUL"),
    ("device-aux", "AUX"),
    ("4096-chars", "x" * 4096),
    ("nul-byte", "passwd\x00.jpg"),
)

# 4. SSRF. `routes` names the surfaces that speak this scheme and fetch this kind of URL:
#    upload/webhook/connector accept http(s) only, the stream route also accepts rtsp.
SSRF = (
    {"id": "metadata-ip", "url": "http://169.254.169.254/latest/meta-data/"},
    {"id": "loopback-api", "url": "http://127.0.0.1:8000/api/health"},
    {"id": "ipv6-loopback", "url": "http://[::1]/"},
    {"id": "unspecified", "url": "http://0.0.0.0/"},
    {"id": "decimal-loopback", "url": "http://2130706433/"},
    {"id": "metadata-name", "url": "http://metadata.google.internal/"},
    {"id": "file-scheme", "url": "file:///etc/passwd"},
    {"id": "gopher-scheme", "url": "gopher://127.0.0.1:70/_"},
    {"id": "mixed-dns", "url": "http://mixed.example.test/a.jpg",
     "note": "resolves to a public and a private address; every answer is checked"},
    {"id": "rtsp-private", "url": "rtsp://192.168.1.20:554/live", "routes": ("stream",),
     "note": "a LAN camera without LD_STREAM_ALLOW_CIDR is refused"},
    {"id": "redirect-private", "url": "http://redirect.example.test/r", "routes": (),
     "note": "answers 302 to http://10.0.0.5/; the dedicated test drives the hop"},
)

# The resolver answers the test needs. Literal addresses keep the real resolver; only names are
# synthetic, so the suite stays offline and deterministic.
DNS = {
    "metadata.google.internal": ["169.254.169.254"],
    "mixed.example.test": ["93.184.216.34", "10.0.0.5"],
    "redirect.example.test": ["93.184.216.34"],
    # the legacy numeric form of 127.0.0.1: Windows refuses to resolve it and Linux resolves it
    # to loopback; pinning the answer keeps the refusal (private address) the same on both
    "2130706433": ["127.0.0.1"],
}


# --- fixtures -------------------------------------------------------------------------------

def _answers(ips: list[str], port: int):
    out = []
    for ip in ips:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        out.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port)))
    return out


@pytest.fixture(scope="module")
def live():
    """Two tenants; A is exercised through the real routes, B is the row that must never leak."""
    with TestClient(app) as c:
        made = c.post("/api/auth/signup", json={"name": "Alpha Owner", "email": ALPHA_EMAIL,
                                                "password": PW, "workspace": "Payload Workspace"})
        assert made.status_code == 200, made.text
        other = c.post("/api/auth/signup", json={"name": "Bravo Owner", "email": BRAVO_EMAIL,
                                                 "password": PW, "workspace": "Bravo Injection Workspace"})
        assert other.status_code == 200, other.text
        headers = login(c, ALPHA_EMAIL, PW)
        ws = c.get("/api/me", headers=headers).json()["workspaces"][0]["slug"]

        made_project = c.post(f"/api/ws/{ws}/projects", headers=headers,
                              json={"name": "Payload Project", "classes": ["person"]})
        assert made_project.status_code == 200, made_project.text
        project = made_project.json()["slug"]

        uploaded = c.post(f"/api/ws/{ws}/projects/{project}/upload", headers=headers,
                          files={"files": ("anchor.jpg", _jpeg(), "image/jpeg")}, data={"split": "train"})
        assert uploaded.status_code == 200, uploaded.text
        image = uploaded.json()["images"][0]["id"]

        with SessionLocal() as db:
            bravo_ws = db.query(Workspace).filter(Workspace.slug == "bravo-injection-workspace").one()   # its own tenant: the IDOR suite owns bravo-workspace
            bravo_project = Project(workspace_id=bravo_ws.id, slug="bravo-injection-proj", name="Bravo Project",
                                    settings={})
            db.add(bravo_project)
            db.flush()
            db.add(Image(project_id=bravo_project.id, name="Bravo payload image.jpg", sha256="b" * 64,
                         width=8, height=8, path="bravo/payload.jpg", thumb="bravo/payload-thumb.jpg",
                         status="review", created=time.time()))
            alpha = db.query(Workspace).filter(Workspace.slug == ws).one()
            from app.services.flags import set_flag
            set_flag(db, alpha.id, "task_992", True)          # the MCP tool's own switch
            db.commit()

        probe = c.post(f"/api/ws/{ws}/keys", headers=headers,
                       json={"name": "payload key", "scopes": ["read", "upload"]})
        assert probe.status_code == 200, probe.text

        # One entered client for the whole module: a TestClient used outside `with` builds a new
        # portal (and a Windows event loop) per request, which is both slow and a loopback socket.
        c.headers.update(headers)
        yield {"session": c, "ws": ws, "project": project, "image": image,
               "key": probe.json()["key"], "base": f"/api/ws/{ws}/projects/{project}"}


@pytest.fixture()
def no_network(monkeypatch):
    """Any outbound connect is a failed test, not a fetch: the SSRF groups must never dial out."""
    attempted: list = []

    def refuse(_sock, address):
        attempted.append(address)
        raise AssertionError(f"outbound connection attempted during the test: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    return attempted


@pytest.fixture()
def opened(monkeypatch):
    """Every path this test opens, resolved. A traversal must never appear here outside DATA_DIR."""
    seen: list[Path] = []
    real_open, real_path_open = builtins.open, Path.open

    def record(file):
        try:
            seen.append(Path(os.fspath(file)).resolve())
        except (OSError, ValueError, TypeError):
            seen.append(Path("<unresolvable>"))

    def spy(file, *a, **kw):
        record(file)
        return real_open(file, *a, **kw)

    def spy_path(self, *a, **kw):
        record(self)
        return real_path_open(self, *a, **kw)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(Path, "open", spy_path)
    yield seen


def assert_nothing_outside_data_dir(seen: list[Path]) -> None:
    allowed = [DATA_DIR, Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
    outside = [p for p in seen if not any(p == a or a in p.parents for a in allowed)]
    assert outside == [], f"a path outside DATA_DIR was opened: {outside}"


@pytest.fixture()
def offline_dns(monkeypatch):
    """The real resolver for literals, a fixed answer for the synthetic names above."""
    real = socket.getaddrinfo

    def resolve(host, port, *a, **kw):
        if host in DNS:
            return _answers(DNS[host], port)
        return real(host, port, *a, **kw)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)


def _no_leak(response, label: str) -> None:
    """Every refusal is a user message: no stack trace, no SQL text, no foreign marker."""
    assert response.status_code != 500, (label, response.text[:500])
    assert "Traceback" not in response.text, label
    assert "sqlalchemy" not in response.text.lower(), label
    assert "OperationalError" not in response.text, label
    assert BRAVO not in response.text, label


# --- 1. SQL injection -----------------------------------------------------------------------

def _sqli_probes(client, ids, payload):
    base = ids["base"]
    return {
        "q": client.get(f"{base}/images", params={"q": payload}),
        "class": client.post(f"{base}/classes", json={"name": payload}),
        "tag": client.post(f"{base}/images/bulk",
                           json={"ids": [ids["image"]], "action": "add_tag", "value": payload}),
        "slug": client.get(f"/api/ws/{ids['ws']}/projects/{quote(payload, safe='')}"),
        "batch": client.get(f"{base}/images", params={"batch_id": payload}),
        "sort": client.get(f"{base}/images", params={"sort": payload}),
    }


@pytest.mark.parametrize("payload", [p for _, p in SQLI], ids=[name for name, _ in SQLI])
def test_sql_payloads_never_500_and_never_leak(live, payload):
    ids = {**live, "base": live["base"]}
    for surface, response in _sqli_probes(live["session"], ids, payload).items():
        label = f"{surface} {payload[:24]!r}"
        _no_leak(response, label)
        # A free-text surface answers 200 (or 404 for a slug that is not a project); a class name
        # with punctuation is refused by the naming rule at 400. Both are designed answers.
        assert response.status_code in (200, 400, 404, 422), (label, response.status_code, response.text[:300])
        if surface == "q" or surface == "sort" or surface == "batch":
            assert response.status_code == 200, (label, response.status_code)


def test_the_database_survived_every_payload(live):
    with SessionLocal() as db:
        assert db.execute(text("select count(*) from images")).scalar() >= 1
        assert db.execute(text("select count(*) from projects")).scalar() >= 1


def test_a_search_never_returns_the_other_workspace(live):
    for _, payload in SQLI:
        r = live["session"].get(f"{live['base']}/images", params={"q": payload})
        assert r.status_code == 200, (payload[:20], r.status_code)
        assert BRAVO not in r.text and "bravo" not in r.text


def test_a_tag_payload_is_stored_as_text_and_filters_exactly(live):
    payload = "' OR 1=1--"
    tag = live["session"].post(f"{live['base']}/images/bulk",
                               json={"ids": [live["image"]], "action": "add_tag", "value": payload})
    assert tag.status_code == 200, tag.text

    matched = live["session"].get(f"{live['base']}/images", params={"tag": payload})
    assert matched.status_code == 200, matched.text
    assert [i["id"] for i in matched.json()["items"]] == [live["image"]]
    with SessionLocal() as db:
        row = db.get(Image, live["image"])
        assert payload in row.tags


# --- 2. stored / reflected XSS ---------------------------------------------------------------

def assert_text_round_trip(stored: str, shown: str, label: str) -> None:
    """The API returns exactly what it stored: no HTML-entity encoding on the way out."""
    assert shown == stored, (label, stored, shown)
    assert "&lt;" not in shown and "&gt;" not in shown and "&amp;" not in shown, label


@pytest.mark.parametrize("payload", [p for _, p in XSS], ids=[name for name, _ in XSS])
def test_an_image_name_round_trips_without_encoding(live, payload):
    r = live["session"].post(f"{live['base']}/upload",
                             files={"files": (f"{payload}.jpg", _jpeg(), "image/jpeg")},
                             data={"split": "train"})
    assert r.status_code == 200, r.text
    shown = r.json()["images"][0]["name"]
    with SessionLocal() as db:
        stored = db.get(Image, r.json()["images"][0]["id"]).name
    assert_text_round_trip(stored, shown, "image name")
    assert "/" not in shown and "\\" not in shown


@pytest.mark.parametrize("payload", [p for _, p in XSS], ids=[name for name, _ in XSS])
def test_a_comment_round_trips_without_encoding(live, payload):
    made = live["session"].post(f"/api/images/{live['image']}/comments", json={"text": payload})
    assert made.status_code == 200, made.text
    assert_text_round_trip(payload, made.json()["text"], "comment")

    listed = live["session"].get(f"/api/images/{live['image']}/comments")
    assert payload in [c["text"] for c in listed.json()]


@pytest.mark.parametrize("payload", [p for _, p in XSS], ids=[name for name, _ in XSS])
def test_a_class_name_is_refused_or_round_trips(live, payload):
    made = live["session"].post(f"{live['base']}/classes", json={"name": payload})
    if made.status_code == 400:
        # the naming rule refuses markup before it is stored; nothing was encoded either
        assert "class names may contain" in made.text
        return
    assert made.status_code == 200, made.text
    assert_text_round_trip(made.json()["name"], made.json()["name"], "class name")
    listed = live["session"].get(f"{live['base']}/classes")
    assert payload in [c["name"] for c in listed.json()]


@pytest.mark.parametrize("payload", [p for _, p in XSS], ids=[name for name, _ in XSS])
def test_a_tag_round_trips_without_encoding(live, payload):
    live["session"].post(f"{live['base']}/images/bulk",
                         json={"ids": [live["image"]], "action": "add_tag", "value": payload})
    listed = live["session"].get(f"{live['base']}/images", params={"limit": 1000})
    row = next(i for i in listed.json()["items"] if i["id"] == live["image"])
    assert payload in row["tags"]
    with SessionLocal() as db:
        assert payload in db.get(Image, live["image"]).tags


@pytest.mark.parametrize("payload", [p for _, p in XSS], ids=[name for name, _ in XSS])
def test_a_project_name_round_trips_without_encoding(live, payload):
    # Rename the seeded project instead of creating one per payload: the Free plan caps projects,
    # and the field under test is the same name column either way.
    patched = live["session"].patch(f"{live['base']}", json={"name": payload})
    assert patched.status_code == 200, patched.text
    shown = live["session"].get(f"{live['base']}").json()["name"]
    with SessionLocal() as db:
        stored = db.query(Project).filter(Project.slug == live["project"]).one().name
    assert_text_round_trip(stored, shown, "project name")


def test_a_workspace_name_round_trips_without_encoding(live):
    payload = XSS[0][1]
    patched = live["session"].patch(f"/api/ws/{live['ws']}", json={"name": payload})
    assert patched.status_code == 200, patched.text
    shown = live["session"].get(f"/api/ws/{live['ws']}").json()["name"]
    assert_text_round_trip(payload, shown, "workspace name")


def test_no_frontend_sink_renders_an_api_field_as_html():
    """The repo-wide half: no `dangerouslySetInnerHTML` takes a field the API returns raw.

    This app has no sanitiser module, so the rule is strict: a raw HTML sink is a finding until a
    sanitiser exists and is imported at the sink. Scanning source text keeps the guard honest even
    when the sink count is zero today.
    """
    root = Path(__file__).resolve().parents[2] / "apps" / "frontend" / "src"
    sinks = []
    for path in root.rglob("*"):
        if path.suffix not in (".tsx", ".ts"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if "dangerouslySetInnerHTML" not in line or stripped.startswith(("*", "//", "/*")):
                continue
            sinks.append(f"{path.relative_to(root)}:{number}: {stripped}")
    assert sinks == [], ("a raw HTML sink needs a sanitiser and one does not exist; render text instead:",
                         sinks)


# --- 3. path traversal ----------------------------------------------------------------------

def _signed_file(rel: str) -> str:
    """A URL for `rel` whose signature is valid — the strongest form of a traversal attempt."""
    return f"/api/files/{quote(rel, safe='')}?{sign_query(rel)}"


@pytest.mark.parametrize("rel", [p for _, p in TRAVERSAL], ids=[name for name, _ in TRAVERSAL])
def test_a_signed_traversal_is_refused_without_opening_outside_data_dir(live, opened, rel):
    r = live["session"].get(_signed_file(rel))
    # 403 when the encoded form no longer matches the signed text, 404 when it resolves to nothing:
    # either way the link is dead, and the file route never opens the target.
    assert r.status_code in (400, 403, 404), (rel, r.status_code, r.text[:200])
    assert b"root:" not in r.content and b"[fonts]" not in r.content
    assert_nothing_outside_data_dir(opened)


def test_a_forged_signature_is_403_and_opens_nothing(live, opened):
    legal = "exports/payload-probe/coco.zip"
    target = DATA_DIR / legal
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    url = sign_path(legal)
    good = live["session"].get(url)
    assert good.status_code == 200, good.text

    path, query = url.split("?", 1)
    exp, sig = query.split("&")
    forged = f"{path}?{exp}&sig={'0' * len(sig.split('=')[1])}"
    refused = live["session"].get(forged)
    assert refused.status_code == 403, refused.text
    assert_nothing_outside_data_dir(opened)


def test_a_legal_download_keeps_a_basename_only(live):
    legal = "exports/payload-probe/coco.zip"
    target = DATA_DIR / legal
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    r = live["session"].get(sign_path(legal))
    assert r.status_code == 200, r.text
    disposition = r.headers.get("content-disposition", "")
    assert "coco.zip" in disposition and ".." not in disposition and "/" not in disposition.split("filename=")[-1]


def test_a_percent_encoded_traversal_is_refused(live):
    """The server decodes `%2e%2e%2f` into `../`; the signature is valid for the decoded path."""
    decoded = "../../../etc/passwd"
    encoded = "%2e%2e%2f" * 3 + "etc%2fpasswd"
    r = live["session"].get(f"/api/files/{encoded}?{sign_query(decoded)}")
    assert r.status_code in (400, 404), (r.status_code, r.text[:200])
    assert b"root:" not in r.content


@pytest.mark.parametrize("name", [p for _, p in TRAVERSAL], ids=[name for name, _ in TRAVERSAL])
def test_an_upload_filename_cannot_escape_data_dir(live, opened, name):
    r = live["session"].post(f"{live['base']}/upload",
                             files={"files": (name, _jpeg(), "image/jpeg")}, data={"split": "train"})
    # A name with no image suffix is not an image at all (400); a name that looks like one is
    # stored under a generated path with a sanitised display name.
    assert r.status_code in (200, 400), (name, r.status_code, r.text[:300])
    if r.status_code == 200:
        shown = r.json()["images"][0]["name"]
        assert "/" not in shown and "\\" not in shown, (name, shown)
        assert len(shown) <= 200
    assert_nothing_outside_data_dir(opened)


def test_version_name_is_text_not_a_path(live):
    payload = TRAVERSAL[0][1]
    made = live["session"].post(f"{live['base']}/versions", json={"name": payload, "settings": {}})
    assert made.status_code in (200, 402), made.text          # 402: the free plan's credit cap
    if made.status_code == 402:
        pytest.skip("workspace is out of version credits; the traversal claim needs no version row")
    assert made.json()["name"] == payload

    with SessionLocal() as db:
        version = db.get(Version, made.json()["id"])
    assert version is not None and version.name == payload


def test_nul_byte_is_rejected_not_truncated(live, opened):
    """A NUL in a name must not shorten it into `passwd`: neither at ingest nor on the file route."""
    r = live["session"].post(f"{live['base']}/upload",
                             files={"files": ("passwd\x00.jpg", _jpeg(), "image/jpeg")},
                             data={"split": "train"})
    assert r.status_code in (200, 400), (r.status_code, r.text[:200])
    if r.status_code == 200:
        shown = r.json()["images"][0]["name"]
        assert shown != "passwd" and "passwd_" in shown, shown

    signed = live["session"].get(_signed_file("passwd\x00.jpg"))
    assert signed.status_code in (400, 404), (signed.status_code, signed.text[:200])
    assert not (DATA_DIR / "passwd").exists()
    assert_nothing_outside_data_dir(opened)


@pytest.mark.skipif(os.name != "nt", reason="Windows device names only exist on Windows")
def test_windows_device_name_does_not_hang(live):
    started = time.monotonic()
    response = live["session"].get(_signed_file("CON"))
    elapsed = time.monotonic() - started
    assert response.status_code in (400, 404), (response.status_code, response.text[:200])
    assert elapsed < 2, f"the device name took {elapsed:.2f}s"


# --- 4. SSRF ----------------------------------------------------------------------------------

def _ssrf_request(client, ids, key, route: str, url: str):
    base = ids["base"]
    if route == "webhook":
        return client.post(f"/api/ws/{ids['ws']}/webhooks", json={"url": url, "events": ["job.done"]})
    if route == "connector":
        return client.post(f"/api/ws/{ids['ws']}/connectors",
                           json={"name": "ssrf probe", "kind": "s3",
                                 "config": {"bucket": "probe", "endpoint_url": url}})
    if route == "stream":
        return client.post(f"{base}/streams", json={"name": "ssrf probe", "source": url,
                                                    "model_ref": "ultralytics:yolo11n"})
    if route == "upload":
        # the route's contract reads `image` as a query parameter; a hostile caller uses exactly that
        return client.post(f"/api/v1/{ids['ws']}/{ids['project']}/upload",
                           headers={"x-api-key": key}, params={"image": url, "name": "probe.jpg"})
    raise AssertionError(route)


def _rows(ws_slug: str) -> tuple:
    with SessionLocal() as db:
        ws = db.query(Workspace).filter(Workspace.slug == ws_slug).one()
        return (db.query(Webhook).filter(Webhook.workspace_id == ws.id).count(),
                db.query(Connector).filter(Connector.workspace_id == ws.id).count(),
                db.query(Stream).filter(Stream.workspace_id == ws.id).count())


@pytest.mark.parametrize("row", SSRF, ids=[row["id"] for row in SSRF])
def test_a_url_payload_is_refused_on_every_route_that_takes_one(live, no_network, offline_dns, row):
    routes = row.get("routes", ("webhook", "connector", "stream", "upload"))
    if not routes:
        pytest.skip("a redirect needs a live fetch; see test_a_public_url_that_redirects_private_is_refused")
    before = _rows(live["ws"])
    for route in routes:
        response = _ssrf_request(live["session"], live, live["key"], route, row["url"])
        assert response.status_code in (400, 422), (row["id"], route, response.status_code, response.text[:300])
        assert response.json().get("detail"), (row["id"], route, response.text[:200])
        _no_leak(response, f"{row['id']}/{route}")
    assert no_network == [], f"{row['id']} attempted a connection: {no_network}"
    assert _rows(live["ws"]) == before, f"{row['id']} left a row behind"


def test_a_public_url_that_redirects_private_is_refused(live, no_network, offline_dns, monkeypatch):
    """The one fetch the guard cannot refuse before switching is a redirect: it must refuse the hop."""
    from app.services import safefetch
    hops: list[str] = []

    class Conn:
        sock = None

        def request(self, method, path, body=None, headers=None):
            hops.append(headers["Host"])

        def getresponse(self):
            return type("R", (), {"status": 302,
                                  "getheader": lambda _self, name: "http://10.0.0.5/" if name == "Location" else None})()

        def close(self):
            pass

    real = safefetch._pinned_connection
    monkeypatch.setattr(safefetch, "_pinned_connection",
                        lambda u, ip, port, timeout: Conn() if u.hostname == "redirect.example.test"
                        else real(u, ip, port, timeout))

    response = _ssrf_request(live["session"], live, live["key"], "upload", "http://redirect.example.test/r")
    assert response.status_code == 400, (response.status_code, response.text[:300])
    assert "private or reserved" in response.text
    assert len(hops) == 1, f"the private redirect hop was fetched: {hops}"
    assert no_network == []


def test_the_allowlists_are_empty_so_private_targets_are_refused():
    from app import config
    assert config.STREAM_ALLOW_CIDR == ()
    assert config.OT_ALLOW_CIDR == ()


def test_the_socket_guard_blocks_a_real_connection(no_network):
    with pytest.raises(AssertionError, match="outbound connection attempted"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.5)
    assert len(no_network) == 1


# --- the MCP tool: the same URL payload through the agent surface -----------------------------

# Created at import, before any socket guard: on Windows a new event loop opens a loopback self-pipe,
# which is bookkeeping for the loop, not egress. One loop for both MCP tests keeps `no_network` honest.
_MCP_LOOP = asyncio.new_event_loop()


def _mcp_call(live, tool: str, args: dict):
    """Run one MCP tool against the real API in-process, so no socket is involved either way."""
    root = Path(__file__).resolve().parents[3]
    for entry in (root / "apps" / "mcp", root / "packages" / "sdk"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    import httpx
    from labeldesk_mcp import server as mcp_server
    from labeldesk_mcp.api import Api
    from mcp.client import Client

    def bridge(request):
        forwarded = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
        answer = live["session"].request(request.method, request.url.raw_path.decode(),
                                         content=request.content, headers=forwarded)
        return httpx.Response(answer.status_code, content=answer.content,
                              headers={"content-type": answer.headers.get("content-type", "application/json")})

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(bridge))
    api.use(live["key"])

    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return await client.call_tool(tool, args)

    return _MCP_LOOP.run_until_complete(run())


def test_mcp_upload_image_url_cannot_fetch_a_private_url(live, no_network, offline_dns):
    """The agent surface is another caller of the same fetcher, so a private URL must not go out.

    Finding F-1 (named in the report, not fixed by this card): the tool answers 500 before any
    fetch because it sends the URL as multipart form data while the hosted route reads `image` as
    a query parameter. That is a functional defect owned by the MCP card — its own test pins the
    body — so the security claim is asserted instead: the tool errors, nothing is dialled, no row
    appears.
    """
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.slug == live["project"]).one()
        project_id = project.id
        before = db.query(Image).filter(Image.project_id == project_id).count()

    for row in (SSRF[0], SSRF[1], SSRF[7]):
        result = _mcp_call(live, "upload_image_url",
                           {"project": live["project"], "url": row["url"], "confirm": True})
        assert result.is_error is True, (row["id"], result.content)

    assert no_network == []
    with SessionLocal() as db:
        assert db.query(Image).filter(Image.project_id == project_id).count() == before


def test_mcp_project_slug_is_never_a_path(live, opened, no_network):
    result = _mcp_call(live, "upload_image_url",
                       {"project": "../../etc/passwd", "url": "https://images.example.test/a.jpg",
                        "confirm": True})
    assert result.is_error is True, result.content
    assert "HTTP 404" in result.content[0].text or "HTTP 422" in result.content[0].text
    assert_nothing_outside_data_dir(opened)
