"""The meta surface: three resources and two prompts, read before an agent touches a label.

Markdown, not JSON, is the point: a resource is what the model reads to understand the project.
Every value comes through `Api.call`, so a secret or a storage path is scrubbed before it renders.
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import INVALID_REQUEST, MCPError

from .api import Api
from .server import _enabled

MARKDOWN = "text/markdown"
MAX_CLASSES = 50  # the class table is the only part that can grow; a 200-class table is a wall of text


def _call(api: Api, operation: str, uri: str, **kw):
    """One API call as one rendering; a refusal or a 404 names the URI the caller asked for."""
    try:
        _enabled(api)
        return api.call(operation, operation, **kw)
    except ToolError as exc:
        raise MCPError(INVALID_REQUEST, f"{exc} — {uri}", data={"uri": uri}) from exc


def _classes(rows: list[dict]) -> list[str]:
    """The class table with ids, so an agent can copy one into `write_annotations`."""
    if not rows:
        return ["No classes yet."]
    shown = sorted(rows, key=lambda row: -(row.get("count") or 0))[:MAX_CLASSES] if len(rows) > MAX_CLASSES else rows
    table = ["| id | name | colour | images |", "| --- | --- | --- | --- |"]
    table += [f"| `{row.get('id')}` | {row.get('name')} | {row.get('color') or '—'} | {row.get('count') or 0} |"
              for row in shown]
    if len(rows) > MAX_CLASSES:
        table += ["", f"(+{len(rows) - MAX_CLASSES} more)"]
    return table


def _workspace(api: Api) -> str:
    uri = "labeldesk://workspace"
    me = _call(api, "whoami", uri)
    projects = _call(api, "list_projects", uri) or []
    plan = str(me.get("plan") or "free")
    scopes = ", ".join(me.get("scopes") or []) or "no scopes"
    return "\n".join([
        f"# {me.get('name') or me.get('workspace')}",
        "",
        f"- Workspace: `{me.get('workspace')}`",
        f"- Plan: {plan[:1].upper()}{plan[1:]}",
        f"- Projects: {len(projects)}",
        f"- This key's scopes: {scopes}",
        "",
    ])


def _project(api: Api, project: str, uri: str) -> dict:
    return _call(api, "get_project", uri, path_params={"project": project})


def _summary(project: dict) -> str:
    statuses = ", ".join(f"{status} {count}" for status, count in sorted((project.get("statusCounts") or {}).items()))
    return "\n".join([
        f"# {project.get('name')} (`{project.get('slug')}`)",
        "",
        f"- Type: {project.get('type')}",
        f"- Images: {project.get('images') or 0}",
        f"- Models: {project.get('models') or 0}",
        f"- Status: {statuses or 'no images yet'}",
        "",
        "## Classes",
        "",
        *_classes(project.get("classes") or []),
        "",
    ])


def _review(api: Api, project: str, threshold: float, limit: int) -> str:
    """The low-confidence AI labels, in the order the review ranking already puts them."""
    uri = f"labeldesk://projects/{project}"
    names = {row.get("id"): row.get("name") for row in _project(api, project, uri).get("classes") or []}
    page = _call(api, "list_images", uri, path_params={"project": project},
                 params={"sort": "review", "limit": max(1, min(limit, 200))})
    found = []
    for row in page.get("items") or []:
        image = _call(api, "get_image", uri, path_params={"image_id": row.get("id")})
        for ann in image.get("annotations") or []:
            conf = ann.get("confidence")
            if isinstance(conf, (int, float)) and conf < threshold:
                found.append(f"- {row.get('name')} — {names.get(ann.get('classId'), 'unassigned class')} ({conf:.2f})")
    if not found:
        return f"No AI label below {threshold} in the first {limit} review candidates of `{project}` — nothing to review."
    return "\n".join([
        f"Review these AI labels in `{project}`, lowest confidence first (below {threshold}):",
        "",
        *found,
        "",
        "Next step: open each image in the LabelDesk editor, correct the class or the box, then approve it. "
        f"This list stops at {limit} images — call the prompt again with a larger limit for more.",
    ])


def _audit(api: Api, project: str, batch_id: str) -> str:
    """What a batch still needs, and the confirm the operator must give before a credit is spent."""
    uri = f"labeldesk://projects/{project}"
    page = _call(api, "list_images", uri, path_params={"project": project},
                 params={"annotated": "no", "batch_id": batch_id, "limit": 1})
    classes = ", ".join(row.get("name") or "" for row in _project(api, project, uri).get("classes") or [])
    count = page.get("total") or 0
    return "\n".join([
        f"Batch `{batch_id}` in `{project}` has {count} image(s) with no annotation.",
        "",
        f"1. Open `{project}` and filter the Dataset by batch `{batch_id}`.",
        f"2. Check the classes a model would predict: {classes or 'no classes yet'}.",
        "3. Predict one image with `predict_image` — it costs 0.001 credits and writes nothing.",
        f"4. Tell the operator that auto-label would touch {count} image(s) and which classes it writes, "
        "then ask for a decision in words.",
        "5. Run `run_auto_label` only after the operator confirms the cost.",
    ])


def register(server: MCPServer, api: Api) -> None:
    """Declare the three resources and the two prompts; `build_server` calls this once."""

    @server.resource("labeldesk://workspace", name="workspace", mime_type=MARKDOWN,
                     description="The workspace this key belongs to: its plan, project count and the key's scopes.")
    def workspace() -> str:
        return _workspace(api)

    @server.resource("labeldesk://projects/{project}", name="project", mime_type=MARKDOWN,
                     description="One project's summary: type, image and model counts, status counts, class ids.")
    def project_resource(project: str) -> str:
        return _summary(_project(api, project, f"labeldesk://projects/{project}"))

    @server.resource("labeldesk://projects/{project}/classes", name="classes", mime_type=MARKDOWN,
                     description="The project's class table only: id, name, colour and image count.")
    def classes_resource(project: str) -> str:
        found = _project(api, project, f"labeldesk://projects/{project}/classes").get("classes") or []
        return "\n".join(_classes(found))

    @server.prompt(name="review_low_confidence_labels",
                   description="The AI labels below a confidence threshold in one project, lowest first, "
                               "with a next step. `threshold` defaults to 0.4 and `limit` to 20 images.")
    def review_low_confidence_labels(project: str, threshold: float = 0.4, limit: int = 20) -> str:
        return _review(api, project, threshold, limit)

    @server.prompt(name="audit_unannotated_batch",
                   description="What a batch still has unannotated and the five steps to fill it, "
                               "ending with the operator's confirmation before any credit is spent.")
    def audit_unannotated_batch(project: str, batch_id: str) -> str:
        return _audit(api, project, batch_id)
