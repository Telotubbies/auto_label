"""The write and spend tools: they change data or spend credits, so one gate asks first.

Every tool answers a dry run (`preview`) unless the call passes `confirm: true`: what it would change,
how many images, how many credits. Costs are the server's published ones — kept in step with
`apps/backend/app/config.py` `CREDIT_COST` — and the API still charges, meters and validates exactly
as it does for a person using the app.
"""
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from pydantic import Field

from .api import Api
from .server import DESTRUCTIVE, IDEMPOTENT_WRITE, TOOL_SCOPES, WRITE, _enabled, summarised

# The published per-action costs, in credits. `apps/backend/app/config.py` owns them; a change there
# changes this line in the same PR.
CREDITS = {"train": 3.0, "version": 0.5, "autolabel_image": 0.01, "infer": 0.001}
NEXT = "call again with confirm: true"

# A string "true" is a host bug, not a confirmation: only the boolean `true` opens the gate.
Confirm = Annotated[bool, Field(strict=True)]

SCOPES = {"upload_image_url": "upload", "write_annotations": "write", "run_auto_label": "write",
          "create_version": "write", "start_training": "train", "predict_image": "infer"}


def preview(tool: str, confirm: bool, would: dict) -> CallToolResult | None:
    """The one gate: a dry run as a normal result, or None once the caller confirmed."""
    if confirm:
        return None
    body = {"dryRun": True, "tool": tool, **would, "next": NEXT}
    return summarised(body, f"Dry run: {tool} changed nothing. {NEXT}.")


def _image_count(api: Api, project: str, **params) -> int:
    """How many images a project action would touch, from the route's own count."""
    page = api.call("list_images", "list_images", path_params={"project": project},
                    params={**params, "limit": 1})
    return int(page["total"])


def register(server: MCPServer, api: Api) -> None:
    """Declare the six write/spend tools; `build_server` calls this once, both transports share them."""

    @server.tool(annotations=IDEMPOTENT_WRITE)
    def upload_image_url(project: str, url: str, batch: str = "MCP upload", split: str = "auto",
                         tags: str = "", confirm: Confirm = False) -> dict[str, Any]:
        """Add one image by public URL, deduped on its content hash; no credits.

        Use it to bring in a few images you already host; do not use it for a bulk import — a person
        drops a folder in the Dataset screen. The API fetches the URL (public addresses only, 20 MB,
        10 s); this server never downloads anything.
        """
        _enabled(api)
        dry = preview("upload_image_url", confirm, {"project": project, "url": url, "estimatedCredits": 0})
        if dry:
            return dry
        name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "upload.jpg"
        saved = api.call("upload_images_v1", "upload_images_v1",
                         path_params={"ws_slug": api.me()["workspace"], "project": project},
                         data={"image": url, "name": name, "batch": batch, "split": split, "tag": tags})
        return summarised(saved, f"Uploaded {saved.get('uploaded') or 0} image(s) to {project}, "
                                 f"{len(saved.get('duplicates') or [])} duplicate(s).")

    @server.tool(annotations=DESTRUCTIVE)
    def write_annotations(image_id: str, annotations: list[dict], confirm: Confirm = False) -> dict[str, Any]:
        """Replace one image's whole annotation set — not a merge — with classes from its own project.

        Use it to correct or add labels a person will review; do not use it to add one box to a set you
        have not read — call get_image first, because everything you leave out is discarded.
        """
        _enabled(api)
        current = api.call("get_image", "get_image", path_params={"image_id": image_id})
        dry = preview("write_annotations", confirm, {"wouldReplace": len(current["annotations"]),
                                                     "wouldSave": len(annotations), "estimatedCredits": 0})
        if dry:
            return dry
        saved = api.call("write_annotations", "write_annotations", path_params={"image_id": image_id},
                         json={"annotations": annotations})
        return summarised(saved, f"Replaced the annotations on {image_id} with "
                                 f"{saved.get('saved') or 0}.")

    @server.tool(annotations=WRITE)
    def run_auto_label(project: str, model_id: str = "", model_ref: str = "", prompt: str = "",
                       class_ids: list[str] | None = None, image_ids: list[str] | None = None,
                       batch_id: str = "", confidence: float | None = None, only_unannotated: bool = True,
                       send_to_review: bool = True, confirm: Confirm = False) -> dict[str, Any]:
        """Queue an auto-label job over a project's images and return its job id; it never waits.

        Use it when a person has agreed to the cost of labelling a batch; do not use it to test a model —
        predict_image on one image costs less. Poll get_job for progress.
        """
        _enabled(api)
        if image_ids:
            target = len(image_ids)
        else:
            target = _image_count(api, project, annotated="no" if only_unannotated else "", batch_id=batch_id)
        dry = preview("run_auto_label", confirm, {"estimatedImages": target,
                                                  "estimatedCredits": round(target * CREDITS["autolabel_image"], 4)})
        if dry:
            return dry
        queued = api.call("run_auto_label", "run_auto_label", path_params={"project": project}, json={
            "method": "model", "model_id": model_id, "model_ref": model_ref, "prompt": prompt,
            "class_ids": class_ids or [], "image_ids": image_ids or [], "batch_id": batch_id,
            "confidence": confidence, "only_unannotated": only_unannotated, "send_to_review": send_to_review})
        return summarised(queued, f"Queued auto-label over {target} image(s) in {project}; poll get_job.")

    @server.tool(annotations=WRITE)
    def create_version(project: str, name: str = "", settings: dict | None = None,
                       confirm: Confirm = False) -> dict[str, Any]:
        """Freeze the project's current data into a numbered version, ready to train on.

        Use it when the data is worth training on; do not use it as a snapshot to browse — it costs credits
        and freezes a split. A person's version wizard offers the same step with a preview.
        """
        _enabled(api)
        if not confirm:
            return preview("create_version", False, {"estimatedImages": _image_count(api, project),
                                                     "estimatedCredits": CREDITS["version"]})
        made = api.call("create_version", "create_version", path_params={"project": project},
                        json={"name": name, "settings": settings or {}})
        return summarised(made, f"Froze version {made.get('number')} of {project}.")

    @server.tool(annotations=WRITE)
    def start_training(project: str, version_id: str, variant: str = "yolo26n", epochs: int = 30,
                       imgsz: int = 640, batch: int = 8, name: str = "", confirm: Confirm = False) -> dict[str, Any]:
        """Queue a training run on a frozen version and return its job id; it never waits.

        Use it when a version is ready and the credits are agreed; do not use it to compare architectures
        cheaply — each run costs the published rate. Poll get_job for progress.
        """
        _enabled(api)
        dry = preview("start_training", confirm, {"versionId": version_id,
                                                  "estimatedCredits": CREDITS["train"]})
        if dry:
            return dry
        queued = api.call("start_training", "start_training", path_params={"project": project},
                          json={"version_id": version_id, "name": name, "variant": variant, "epochs": epochs,
                                "imgsz": imgsz, "batch": batch})
        return summarised(queued, f"Queued training on version {version_id}; poll get_job.")

    @server.tool(annotations=WRITE)
    def predict_image(model_id: str, image_id: str = "", image_url: str = "", confidence: float | None = None,
                      confirm: Confirm = False) -> dict[str, Any]:
        """Run one ready model over one image you already hold, or one public URL; give exactly one source.

        Use it to check a model on a single frame; do not use it to label a dataset — run_auto_label writes
        labels, this one returns predictions and writes nothing.
        """
        if image_id and image_url:
            raise ToolError("pass image_id or image_url, not both")
        if not (image_id or image_url):
            raise ToolError("pass image_id or image_url")
        _enabled(api)
        dry = preview("predict_image", confirm, {"source": "image_id" if image_id else "image_url",
                                                 "estimatedCredits": CREDITS["infer"]})
        if dry:
            return dry
        params = {"image_id": image_id, "image": image_url, "confidence": confidence}
        found = api.call("predict", "predict", path_params={"model_id": model_id},
                         params={k: v for k, v in params.items() if v not in (None, "")})
        return summarised(found, f"{len(found.get('predictions') or [])} prediction(s) from {model_id}.")

    TOOL_SCOPES.update(SCOPES)
