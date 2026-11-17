"""T-1302: one scrapeable surface for request rate, errors and latency (MONITORING-PLAN §4.2).

Four HTTP series — `requests_total`, `request_duration_seconds`, `exceptions_total`, `inflight` —
plus `build_info` and the readiness-fed `db_up`. Labels are bounded by construction: `route` is the
matched template or `<unmatched>`, never a raw path, and no label carries a workspace, a user, an
email or a file name. The surface is closed unless `LD_METRICS_TOKEN` is set: 404 when the
deployment publishes nothing, 401 for a wrong token, and the body never says which.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.main import app
from app.routers import health
from conftest import login

TOKEN = "t1302-metrics-token"
WS = "labeldesk-demo"
# Every label a scrape may carry. `python_gc_*`/`process_*` are not in the contract, so neither are
# their label sets; a family outside the allowlist below fails the shape test.
ALLOWED_LABELS = {"method", "route", "status_class", "le", "type", "version"}
ALLOWED_SERIES = {
    "labeldesk_http_requests_total", "labeldesk_http_requests_created",
    "labeldesk_http_request_duration_seconds_bucket", "labeldesk_http_request_duration_seconds_count",
    "labeldesk_http_request_duration_seconds_sum", "labeldesk_http_request_duration_seconds_created",
    "labeldesk_http_exceptions_total", "labeldesk_http_exceptions_created",
    "labeldesk_http_inflight", "labeldesk_build_info", "labeldesk_db_up",
}
BUCKETS = {"0.005", "0.01", "0.025", "0.05", "0.1", "0.15", "0.25", "0.5", "1.0", "2.5", "5.0",
           "10.0", "+Inf"}


@pytest.fixture(scope="module")
def c():
    """A bare client: metrics need no lifespan, and the session fixture already created the schema."""
    return TestClient(app)


@pytest.fixture
def token(monkeypatch):
    """The deployment sets the scrape token; without it the route answers 404."""
    monkeypatch.setattr(config, "METRICS_TOKEN", TOKEN)
    return TOKEN


def _scrape(c: TestClient) -> str:
    r = c.get("/api/metrics", headers={"Authorization": f"Bearer {config.METRICS_TOKEN}"})
    assert r.status_code == 200, r.text
    return r.text


def _samples(text: str):
    """(series, labels, value) for every sample line of the exposition; comments are skipped."""
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        head, _, raw = line.rpartition(" ")
        name, _, block = head.partition("{")
        labels = {}
        for part in block.rstrip("}").split(",") if block else ():
            key, _, value = part.partition("=")
            labels[key] = value.strip('"')
        yield name, labels, float(raw)


def _value(text: str, series: str, **match: str) -> float:
    return sum(value for name, labels, value in _samples(text)
               if name == series and all(labels.get(k) == v for k, v in match.items()))


def _label_sets(text: str, series: str) -> set[frozenset]:
    return {frozenset(labels.items()) for name, labels, _ in _samples(text) if name == series}


def test_route_label_is_the_template_not_the_path(c, token):
    c.get("/api/ws/acme/projects/img-1/images")          # matched, then 401/404: the label is what counts
    routes = {labels["route"] for name, labels, _ in _samples(_scrape(c))
              if name == "labeldesk_http_requests_total"}
    assert "/api/ws/{ws}/projects/{project}/images" in routes
    assert not any("acme" in route or "img-1" in route for route in routes), (
        "a raw path would create one series per id")


def test_unknown_path_becomes_unmatched(c, token):
    before = _label_sets(_scrape(c), "labeldesk_http_requests_total")
    c.request("PUT", "/api/nope/9")
    added = _label_sets(_scrape(c), "labeldesk_http_requests_total") - before
    unmatched = [dict(s) for s in added if dict(s).get("route") == "<unmatched>"]
    assert len(unmatched) == 1, f"one <unmatched> series, not {added}"
    after_one = _label_sets(_scrape(c), "labeldesk_http_requests_total")
    for i in range(10):
        c.get(f"/api/nope/{i}")
    after_ten = _label_sets(_scrape(c), "labeldesk_http_requests_total")
    for i in range(10, 20):
        c.get(f"/api/nope/{i}")
    assert _label_sets(_scrape(c), "labeldesk_http_requests_total") == after_ten, (
        "ten more unknown paths must not create ten series")
    assert after_ten - after_one <= {
        frozenset({("method", "GET"), ("route", "<unmatched>"), ("status_class", "4xx")})}
    assert not any("nope" in dict(s).get("route", "") for s in after_ten)


def test_counts_and_status_classes(c, token):
    before = _scrape(c)
    for _ in range(3):
        assert c.get("/api/health").status_code == 200
    assert c.get("/api/nope/t1302").status_code == 404
    assert c.get(f"/api/ws/{WS}/projects").status_code == 401
    after = _scrape(c)

    def delta(**match):
        return (_value(after, "labeldesk_http_requests_total", **match)
                - _value(before, "labeldesk_http_requests_total", **match))

    assert delta(route="/api/health", status_class="2xx") == 3
    assert delta(route="<unmatched>", status_class="4xx") == 1
    # 401 keeps its 4xx class: an unauthenticated scanner is the signal, not a success
    assert delta(route="/api/ws/{ws}/projects", status_class="4xx") == 1


def test_duration_histogram_has_all_buckets(c, token):
    c.get("/api/health")
    text = _scrape(c)
    seen = {labels["le"] for name, labels, _ in _samples(text)
            if name == "labeldesk_http_request_duration_seconds_bucket"
            and labels["route"] == "/api/health"}
    assert seen == BUCKETS, "5 ms – 10 s: p50/p95/p99 stay derivable at every load level"
    assert _value(text, "labeldesk_http_request_duration_seconds_count", route="/api/health") >= 1
    assert _value(text, "labeldesk_http_request_duration_seconds_sum", route="/api/health") > 0


def test_exception_increments_the_exception_counter_and_a_5xx(c, token):
    async def boom():
        raise ZeroDivisionError("t1302")

    app.add_api_route("/api/_t1302_boom", boom)
    try:
        before = _scrape(c)
        r = c.get("/api/_t1302_boom")
        assert r.status_code == 500
        after = _scrape(c)
    finally:
        app.router.routes[:] = [r for r in app.router.routes
                                if getattr(r, "path", None) != "/api/_t1302_boom"]
    assert (_value(after, "labeldesk_http_exceptions_total", route="/api/_t1302_boom",
                   type="ZeroDivisionError")
            - _value(before, "labeldesk_http_exceptions_total", route="/api/_t1302_boom",
                     type="ZeroDivisionError")) == 1
    assert (_value(after, "labeldesk_http_requests_total", route="/api/_t1302_boom",
                   status_class="5xx")
            - _value(before, "labeldesk_http_requests_total", route="/api/_t1302_boom",
                     status_class="5xx")) == 1, "the exception path is a 5xx, not a gap"


def test_metrics_route_is_404_without_a_token(c, monkeypatch):
    monkeypatch.setattr(config, "METRICS_TOKEN", "")
    for headers in ({}, {"Authorization": "Bearer anything"}):
        r = c.get("/api/metrics", headers=headers)
        assert r.status_code == 404, "an unset token means this deployment publishes no metrics"
        assert r.json() == {"detail": "Not Found"}, "the body must not explain the deployment"


def test_metrics_route_is_200_with_the_token(c, token):
    r = c.get("/api/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# HELP labeldesk_http_requests_total" in r.text
    assert 'labeldesk_build_info{version="' in r.text


@pytest.mark.parametrize("headers", [{"Authorization": "Bearer wrong"}, {}])
def test_metrics_route_is_401_with_a_wrong_token(c, token, headers):
    r = c.get("/api/metrics", headers=headers)
    assert r.status_code == 401
    assert r.json() == {"detail": "Unauthorized"}, "the body must not explain the token"


def test_scrape_shape(c, token):
    auth = login(c)
    me = c.get("/api/me", headers=auth).json()
    workspace = me["workspaces"][0]
    filename = "t1302-scrape-shape.png"
    c.get(f"/api/ws/{workspace['slug']}/projects/shape-check/images")
    c.get(f"/api/images/{filename}")
    text = _scrape(c)

    assert {name for name, _, _ in _samples(text)} <= ALLOWED_SERIES, "no collector leaked in"
    for _, labels, _ in _samples(text):
        assert set(labels) <= ALLOWED_LABELS, labels
    lowered = text.lower()
    for secret in (workspace["id"], me["id"], me["email"], filename, "shape-check"):
        assert secret.lower() not in lowered, f"the exposition carries {secret!r}"
    assert _value(text, "labeldesk_http_inflight") == 1.0, "only the scrape itself is in flight"


def test_db_up_reflects_the_readyz_check(c, token, monkeypatch):
    assert _value(_scrape(c), "labeldesk_db_up") == 1.0
    dead = create_engine("postgresql+psycopg2://labeldesk:x@127.0.0.1:1/labeldesk",
                         connect_args={"connect_timeout": 1})
    monkeypatch.setattr(health, "SessionLocal", sessionmaker(bind=dead))
    try:
        assert _value(_scrape(c), "labeldesk_db_up") == 0.0, "the gauge is the readiness check's answer"
    finally:
        dead.dispose()


def test_the_scrape_route_is_measured_without_recursing(c, token):
    _scrape(c)
    series = {"route": "/api/metrics", "status_class": "2xx"}
    before = _value(_scrape(c), "labeldesk_http_requests_total", **series)
    assert before >= 1, "the scrape is measured, not excluded"
    assert _value(_scrape(c), "labeldesk_http_requests_total", **series) == before + 1
