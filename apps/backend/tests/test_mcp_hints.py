"""T-1100: every tool says whether it reads, writes or deletes, and records come back typed.

One in-memory layer, because this card changes only what a host is told and what a host can parse:
the annotations, the output schemas, the strict `confirm` and the dry run that writes nothing.
"""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (REPO_ROOT / "apps" / "mcp", REPO_ROOT / "packages" / "sdk"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import httpx
import jsonschema
from mcp.client import Client

from labeldesk_mcp import server as mcp_server
from labeldesk_mcp.api import Api

KEY = "ld_hints_s3cret_key_do_not_leak"
ALL_SCOPES = ("read", "upload", "write", "train", "infer")
# The tools that overwrite or remove what a person already made. A new one joins this set and the card.
DESTRUCTIVE = {"write_annotations"}
LISTS = ("list_projects", "list_images", "list_versions", "list_models", "list_deployments")
LIST_ARGS = {"list_projects": {}, "list_images": {"project": "parcels"}, "list_versions": {"project": "parcels"},
             "list_models": {}, "list_deployments": {}}
RECORDS = {"whoami": {}, "get_project": {"project": "parcels"}, "get_image": {"image_id": "img_1"},
           "get_model": {"model_id": "mdl_1"}, "get_job": {"job_id": "job_1"}, "list_deployments": {}}
WRITE_ARGS = {"upload_image_url": {"project": "parcels", "url": "https://images.example.test/a.jpg"},
              "write_annotations": {"image_id": "img_1", "annotations": []},
              "run_auto_label": {"project": "parcels", "model_id": "mdl_1"},
              "create_version": {"project": "parcels"}, "start_training": {"project": "parcels",
                                                                          "version_id": "ver_1"},
              "predict_image": {"model_id": "mdl_1", "image_id": "img_1"}}
BOX = {"id": "ann-1", "classId": "cls_1", "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}


def shape(request):
    """One plausible record per route, so every tool has something to shape."""
    path = request.url.path
    if path == "/api/v1/projects":
        return [{"id": "prj_1", "slug": "parcels", "name": "Parcels", "type": "object-detection",
                 "images": 2, "classes": ["box"]}]
    if path.endswith("/images"):
        return {"total": 2, "items": [{"id": "img_1", "name": "a.jpg"}]}
    if path.endswith("/versions"):
        return [{"id": "ver_1", "number": 1, "name": "parcels v1", "status": "ready"}]
    if path == "/api/v1/models":
        return [{"id": "mdl_1", "name": "parcels-ready", "status": "ready"}]
    if path == "/api/v1/deployments":
        return {"projects": [{"project": "parcels", "aliases": []}]}
    if path.startswith("/api/v1/images/"):
        return {"id": "img_1", "name": "a.jpg", "annotations": [BOX]}
    if path.startswith("/api/v1/models/"):
        return {"id": "mdl_1", "name": "parcels-ready", "status": "ready"}
    if path.startswith("/api/v1/jobs/"):
        return {"id": "job_1", "kind": "export", "status": "done", "progress": 100}
    return {"id": "prj_1", "slug": "parcels", "name": "Parcels", "type": "object-detection", "images": 2,
            "models": 1, "statusCounts": {"review": 1}, "classes": []}


def api_with(handler=None):
    """An Api over a MockTransport whose `/whoami` carries every scope and the switch turned on."""
    seen = []

    def transport(request):
        seen.append(request)
        if request.url.path == "/api/v1/whoami":
            return httpx.Response(200, json={"workspace": "demo", "name": "Demo", "plan": "free",
                                             "scopes": list(ALL_SCOPES), "mcp": True})
        return httpx.Response(200, json=(handler or shape)(request))

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))
    api.use(KEY)
    return api, seen


def tools(api):
    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return {tool.name: tool for tool in (await client.list_tools()).tools}

    return asyncio.run(run())


def call(api, name, args=None):
    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return await client.call_tool(name, args or {})

    return asyncio.run(run())


def mutating(seen):
    return [request for request in seen if request.method in ("POST", "PUT", "PATCH", "DELETE")]


def test_every_registered_tool_declares_annotations():
    """A tool added without annotations fails here, and the message names it."""
    api, _ = api_with()

    listed = tools(api)

    assert set(listed) == set(mcp_server.TOOL_SCOPES)
    for name, tool in listed.items():
        assert tool.annotations is not None, f"{name} has no annotations"


def test_read_tools_are_read_only_closed_and_idempotent():
    api, _ = api_with()

    listed = tools(api)

    for name, tool in listed.items():
        wire = tool.model_dump(by_alias=True)["annotations"]
        read_only = name.startswith(("list_", "get_")) or name == "whoami"
        assert wire["readOnlyHint"] is read_only, name
        assert wire["openWorldHint"] is False, name
        if read_only:
            assert wire["idempotentHint"] is True, name
        else:
            assert isinstance(wire["idempotentHint"], bool), name


def test_the_destructive_set_is_pinned_and_asks_first():
    api, _ = api_with()

    listed = tools(api)

    destructive = {name for name, tool in listed.items() if tool.annotations.destructive_hint is True}
    assert destructive == DESTRUCTIVE
    for name in destructive:
        props = listed[name].model_dump(by_alias=True)["inputSchema"]["properties"]
        assert props["confirm"]["type"] == "boolean", name


def test_a_destructive_tool_without_confirm_changes_nothing():
    api, seen = api_with()
    api.me()                       # the scope filter's own whoami, cached for this request
    seen.clear()

    result = call(api, "write_annotations", {"image_id": "img_1", "annotations": [BOX]})

    assert result.is_error is False
    assert json.loads(result.content[0].text)["dryRun"] is True
    assert mutating(seen) == []
    # the one read a dry run needs: how many annotations the replace would discard
    assert [request.url.path for request in seen] == ["/api/v1/images/img_1"]


def test_confirm_must_be_the_boolean_true():
    api, seen = api_with()

    result = call(api, "write_annotations", {"image_id": "img_1", "annotations": [BOX], "confirm": "true"})

    assert result.is_error is True
    assert "confirm" in " ".join(block.text for block in result.content)
    assert mutating(seen) == []


def test_list_tools_publish_a_schema_and_return_structured_content():
    api, _ = api_with()

    listed = tools(api)

    for name in LISTS:
        schema = listed[name].output_schema
        assert schema, f"{name} declares no outputSchema"
        result = call(api, name, LIST_ARGS[name])
        assert result.is_error is False, name
        assert result.structured_content is not None, f"{name} returns no structuredContent"
        jsonschema.validate(result.structured_content, schema)


def test_a_page_is_a_total_and_its_items():
    api, _ = api_with()

    result = call(api, "list_images", {"project": "parcels"})

    assert result.structured_content == {"total": 2, "items": [{"id": "img_1", "name": "a.jpg"}]}


def test_a_record_result_ends_with_a_one_line_summary():
    api, _ = api_with()

    for name, args in RECORDS.items():
        result = call(api, name, args)
        assert result.is_error is False, name
        summary = result.content[-1].text
        assert "\n" not in summary and summary.strip(), name
