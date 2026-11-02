"""Public capability reporting for the landing page (I14).

The reference deployment disables SAM and provisions no vLLM, so the public config must not
report the SAM/VLM add-on as available. Both halves are required: a loaded SAM is not a VLM.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import capabilities

CONFIG_PATH = "/api/config"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_reference_deployment_reports_the_addons_as_unavailable(client):
    assert capabilities.sam_configured() is False
    assert capabilities.vlm_configured() is False
    assert capabilities.addons_available() is False

    cfg = client.get(CONFIG_PATH).json()
    assert cfg["sam"]["enabled"] is False
    assert cfg["vlm"]["configured"] is False
    assert cfg["addons"]["available"] is False


def test_public_config_needs_both_sam_and_vlm(client, monkeypatch):
    monkeypatch.setattr(capabilities, "sam_configured", lambda: True)
    monkeypatch.setattr(capabilities, "vlm_configured", lambda: False)
    assert client.get(CONFIG_PATH).json()["addons"]["available"] is False

    monkeypatch.setattr(capabilities, "vlm_configured", lambda: True)
    assert client.get(CONFIG_PATH).json()["addons"]["available"] is True
