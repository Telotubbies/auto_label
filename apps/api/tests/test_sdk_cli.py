"""The Python SDK/CLI is generated from this API's OpenAPI schema — keep the two in lockstep."""
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-sdk-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import httpx
import pytest
from PIL import Image as PImage

API_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(APP_ROOT / "sdk") not in sys.path:
    sys.path.insert(0, str(APP_ROOT / "sdk"))

from app.main import app                                            # noqa: E402

GEN_SDK = REPO_ROOT / "tools" / "gen_sdk.py"

# the public developer surface, and the scope each operation needs
EXPECTED_SCOPES = {
    "whoami": "read",
    "list_projects": "read",
    "list_images": "read",
    "upload_images": "upload",
    "upload_images_v1": "upload",
    "list_versions": "read",
    "export_version": "read",
    "start_training": "train",
    "get_job": "read",
    "list_models": "read",
    "get_model": "read",
    "predict": "infer",
}


def load_gen_sdk():
    spec = importlib.util.spec_from_file_location("gen_sdk_under_test", GEN_SDK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jpeg(color=(200, 50, 50)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (32, 24), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture()
def image(tmp_path):
    p = tmp_path / "tiny.jpg"
    p.write_bytes(jpeg())
    return p


# --- generation drift -------------------------------------------------------------------------

def test_generated_operations_match_openapi():
    from labeldesk import _generated

    got = load_gen_sdk().operations(app.openapi())
    assert got == _generated.OPERATIONS, "run `python tools/gen_sdk.py` — the committed SDK is stale"
    assert set(got) == set(EXPECTED_SCOPES)
    assert len(got) == 12
    for op, spec in got.items():
        assert spec["scopes"] == [EXPECTED_SCOPES[op]], op
        assert spec["path"].startswith("/api/v1"), op


def test_generated_operations_extract_path_params_and_methods():
    got = load_gen_sdk().operations(app.openapi())
    assert got["predict"] == {"method": "post", "path": "/api/v1/models/{model_id}/predict",
                              "scopes": ["infer"], "params": ["model_id"]}
    assert got["upload_images_v1"]["params"] == ["ws_slug", "project"]
    assert got["export_version"]["params"] == ["project", "vid"]
    assert got["whoami"]["params"] == []
    assert list(got) == sorted(got)


# --- client -----------------------------------------------------------------------------------

def test_whoami_sends_bearer_and_hits_v1(monkeypatch):
    from labeldesk import LabelDesk

    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("authorization")
        seen["accept"] = req.headers.get("accept")
        seen["path"] = req.url.path
        return httpx.Response(200, json={"workspace": "demo"})

    ld = LabelDesk(api_key="ld_key", base_url="http://api.test", transport=httpx.MockTransport(handler))
    assert ld.whoami() == {"workspace": "demo"}
    assert seen == {"auth": "Bearer ld_key", "accept": "application/json", "path": "/api/v1/whoami"}


def test_predict_posts_multipart_file(image):
    from labeldesk import LabelDesk

    reqs = []

    def handler(req: httpx.Request) -> httpx.Response:
        reqs.append(req)
        return httpx.Response(200, json={"predictions": []})

    ld = LabelDesk(api_key="k", base_url="http://api.test", transport=httpx.MockTransport(handler))
    assert ld.predict("m1", image, confidence=0.25) == {"predictions": []}

    req = reqs[0]
    assert req.method == "POST"
    assert req.url.path == "/api/v1/models/m1/predict"
    assert req.headers["content-type"].startswith("multipart/form-data")
    assert b'name="file"' in req.content
    # the hosted route reads confidence from the query string, not the form
    assert req.url.params["confidence"] == "0.25"
    assert b'name="confidence"' not in req.content


def test_error_maps_403_detail():
    from labeldesk import LabelDesk, LabelDeskError

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "api_key lacks the 'train' scope"})

    ld = LabelDesk(api_key="k", base_url="http://api.test", transport=httpx.MockTransport(handler))
    with pytest.raises(LabelDeskError) as ei:
        ld.train("ppe-detection", "v1")
    assert ei.value.status == 403
    assert ei.value.detail == "api_key lacks the 'train' scope"


def test_path_params_come_from_generated_spec():
    from labeldesk import LabelDesk, LabelDeskError

    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["query"] = dict(req.url.params)
        return httpx.Response(200, json={"total": 0, "items": []})

    ld = LabelDesk(api_key="k", base_url="http://api.test", transport=httpx.MockTransport(handler))
    assert ld.images("ppe-detection", limit=5) == {"total": 0, "items": []}
    assert seen["path"] == "/api/v1/projects/ppe-detection/images"
    assert seen["query"]["limit"] == "5"

    with pytest.raises(LabelDeskError):
        ld.call("list_images")


# --- CLI --------------------------------------------------------------------------------------

class FakeClient:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeClient.calls.append(("init", kwargs))

    def whoami(self):
        FakeClient.calls.append(("whoami",))
        return {"workspace": "demo"}

    def upload(self, project, paths, batch_name="CLI Upload", split="auto", tags=""):
        FakeClient.calls.append(("upload", project, [str(p) for p in paths], batch_name, split, tags))
        return {"uploaded": 1}

    def predict(self, model_id, image_path, confidence=None):
        FakeClient.calls.append(("predict", model_id, str(image_path), confidence))
        return {"predictions": []}

    def close(self):
        FakeClient.calls.append(("close",))


@pytest.fixture()
def fake_cli(monkeypatch):
    from labeldesk import cli

    FakeClient.calls = []
    monkeypatch.setattr(cli, "LabelDesk", FakeClient)
    return cli


def test_cli_whoami(fake_cli, capsys):
    assert fake_cli.main(["whoami"]) == 0
    assert ("whoami",) in FakeClient.calls
    assert "demo" in capsys.readouterr().out


def test_cli_upload_passes_files(fake_cli, image):
    assert fake_cli.main(["upload", "ppe-detection", str(image)]) == 0
    uploads = [c for c in FakeClient.calls if c[0] == "upload"]
    assert uploads == [("upload", "ppe-detection", [str(image)], "CLI Upload", "auto", "")]


def test_cli_predict_passes_model_and_image(fake_cli, image):
    assert fake_cli.main(["predict", "m1", str(image), "--confidence", "0.4"]) == 0
    assert ("predict", "m1", str(image), 0.4) in FakeClient.calls


def test_cli_error_is_readable(fake_cli, monkeypatch, capsys):
    from labeldesk import LabelDeskError

    def boom(self):
        raise LabelDeskError(401, "invalid api_key")

    monkeypatch.setattr(FakeClient, "whoami", boom)
    assert fake_cli.main(["whoami"]) == 1
    err = capsys.readouterr().err
    assert "error: invalid api_key" in err
