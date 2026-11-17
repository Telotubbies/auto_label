"""T-999: the deployment is the feature — one profile, one Caddy route, one honest document.

Structural assertions on files that would otherwise drift silently: the compose service that is off
unless asked for, the route that must stay ahead of the SPA, the pin the MCP app imports, and the two
documents an operator and their security reviewer read.
"""
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "deploy" / "docker-compose.yml"
CADDY = REPO / "deploy" / "Caddyfile"
REQUIREMENTS = REPO / "apps" / "backend" / "requirements.txt"
README = REPO / "apps" / "mcp" / "README.md"
DOCS = REPO / "docs" / "MCP.md"

TOOLS = ("whoami", "list_projects", "get_project", "list_images", "get_image", "list_versions",
         "get_job", "list_models", "get_model", "list_deployments", "upload_image_url",
         "write_annotations", "run_auto_label", "create_version", "start_training", "predict_image")
EXCLUDED = ("delete_", "deploy_", "revoke_")


def test_the_mcp_service_is_behind_a_profile():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    assert "mcp" in services, "the compose stack has no mcp service"
    mcp = services["mcp"]
    assert mcp["profiles"] == ["mcp"], "MCP must be off unless the operator asks for it"
    assert mcp["build"] == {"context": "..", "dockerfile": "apps/mcp/Dockerfile"}
    assert mcp["environment"]["LABELDESK_URL"] == "http://api:8000"
    assert "api" in mcp["depends_on"]
    joined = " ".join(str(key) for key in mcp["environment"])
    for forbidden in ("LD_SECRET", "DATABASE_URL", "LABELDESK_API_KEY"):
        assert forbidden not in joined, f"the mcp service must not hold {forbidden}"


def test_caddy_routes_mcp_before_the_spa():
    text = CADDY.read_text(encoding="utf-8")
    site = re.search(r"^\{\$LD_DOMAIN\} \{(?P<body>.*?)^\}", text, re.MULTILINE | re.DOTALL)
    assert site, "the Caddyfile has no {$LD_DOMAIN} site block"
    body = site.group("body")
    assert "route /mcp*" in body, "the site never routes /mcp"
    assert body.index("route /mcp*") < body.index("reverse_proxy web:80"), (
        "the MCP route must be written before the SPA fallback")


def test_the_requirements_file_still_pins_the_mcp_sdk():
    pinned = [line.strip() for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()]
    assert "mcp>=2.3,<3" in pinned, "the suite imports the MCP server, so the pin is a test dependency"


def test_docs_name_every_tool():
    text = README.read_text(encoding="utf-8")
    missing = [name for name in TOOLS if f"`{name}`" not in text]
    assert not missing, f"apps/mcp/README.md never names {missing}"
    for name in EXCLUDED:
        assert name not in text, f"README offers a deliberately excluded surface: {name}"


def test_docs_carry_no_secret_or_live_key():
    for path in (README, DOCS):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bld_[A-Za-z0-9_]{4,}", text), f"{path.name} carries a key-shaped literal"
        assert "Bearer ey" not in text, f"{path.name} carries a JWT-shaped literal"
