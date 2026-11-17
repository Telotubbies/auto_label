"""The write and spend tools: they change data or spend credits, so one gate asks first.

Every tool answers a dry run (`preview`) unless the call passes `confirm: true`: what it would change,
how many images, how many credits. Costs are the server's published ones — kept in step with
`apps/backend/app/config.py` `CREDIT_COST` — and the API still charges, meters and validates exactly
as it does for a person using the app.
"""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .api import Api
from .server import TOOL_SCOPES, _enabled

# The published per-action costs, in credits. `apps/backend/app/config.py` owns them; a change there
# changes this line in the same PR.
CREDITS = {"train": 3.0, "version": 0.5, "autolabel_image": 0.01, "infer": 0.001}
NEXT = "call again with confirm: true"

WRITE = ToolAnnotations(read_only_hint=False)
DESTRUCTIVE = ToolAnnotations(read_only_hint=False, destructive_hint=True)

SCOPES = {"upload_image_url": "upload", "write_annotations": "write", "run_auto_label": "write",
          "create_version": "write", "start_training": "train", "predict_image": "infer"}


def preview(tool: str, confirm: bool, would: dict) -> dict | None:
    """The one gate: a dry run as a normal result, or None once the caller confirmed."""
    if confirm:
        return None
    return {"dryRun": True, "tool": tool, **would, "next": NEXT}


def _image_count(api: Api, project: str, **params) -> int:
    """How many images a project action would touch, from the route's own count."""
    page = api.call("list_images", "list_images", path_params={"project": project},
                    params={**params, "limit": 1})
    return int(page["total"])


def register(server: MCPServer, api: Api) -> None:
    """Declare the six write/spend tools; `build_server` calls this once, both transports share them."""

    @server.tool(annotations=WRITE)
    def upload_image_url(project: str, url: str, batch: str = "MCP upload", split: str = "auto",
                         tags: str = "", confirm: bool = False) -> dict:
        """Add one image by public URL, deduped on its content hash. The API fetches it (public addresses only, 20 MB, 10 s); this server never downloads anything. No credits per the server's published costs."""
        _enabled(api)
        dry = preview("upload_image_url", confirm, {"project": project, "url": url, "estimatedCredits": 0})
        if dry:
            return dry
        name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "upload.jpg"
        return api.call("upload_images_v1", "upload_images_v1",
                        path_params={"ws_slug": api.me()["workspace"], "project": project},
                        data={"image": url, "name": name, "batch": batch, "split": split, "tag": tags})

    @server.tool(annotations=DESTRUCTIVE)
    def write_annotations(image_id: str, annotations: list[dict], confirm: bool = False) -> dict:
        """Replace one image's whole annotation set (not a merge). Classes must belong to the image's own project. No credits per the server's published costs."""
        _enabled(api)
        current = api.call("get_image", "get_image", path_params={"image_id": image_id})
        dry = preview("write_annotations", confirm, {"wouldReplace": len(current["annotations"]),
                                                     "wouldSave": len(annotations), "estimatedCredits": 0})
        if dry:
            return dry
        return api.call("write_annotations", "write_annotations", path_params={"image_id": image_id},
                        json={"annotations": annotations})

    @server.tool(annotations=WRITE)
    def run_auto_label(project: str, model_id: str = "", model_ref: str = "", prompt: str = "",
                       class_ids: list[str] | None = None, image_ids: list[str] | None = None,
                       batch_id: str = "", confidence: float | None = None, only_unannotated: bool = True,
                       send_to_review: bool = True, confirm: bool = False) -> dict:
        """Queue an auto-label job over a project's images and return its job id; poll get_job, this never waits. Costs the server's published per-image rate; pass model_id or model_ref."""
        _enabled(api)
        if image_ids:
            target = len(image_ids)
        else:
            target = _image_count(api, project, annotated="no" if only_unannotated else "", batch_id=batch_id)
        dry = preview("run_auto_label", confirm, {"estimatedImages": target,
                                                  "estimatedCredits": round(target * CREDITS["autolabel_image"], 4)})
        if dry:
            return dry
        return api.call("run_auto_label", "run_auto_label", path_params={"project": project}, json={
            "method": "model", "model_id": model_id, "model_ref": model_ref, "prompt": prompt,
            "class_ids": class_ids or [], "image_ids": image_ids or [], "batch_id": batch_id,
            "confidence": confidence, "only_unannotated": only_unannotated, "send_to_review": send_to_review})

    @server.tool(annotations=WRITE)
    def create_version(project: str, name: str = "", settings: dict | None = None,
                       confirm: bool = False) -> dict:
        """Freeze the project's current data into a numbered version, ready to train on. Costs the server's published version rate."""
        _enabled(api)
        if not confirm:
            return preview("create_version", False, {"estimatedImages": _image_count(api, project),
                                                     "estimatedCredits": CREDITS["version"]})
        return api.call("create_version", "create_version", path_params={"project": project},
                        json={"name": name, "settings": settings or {}})

    @server.tool(annotations=WRITE)
    def start_training(project: str, version_id: str, variant: str = "yolo26n", epochs: int = 30,
                       imgsz: int = 640, batch: int = 8, name: str = "", confirm: bool = False) -> dict:
        """Queue a training run on a frozen version and return its job id; poll get_job, this never waits. Costs the server's published training rate."""
        _enabled(api)
        dry = preview("start_training", confirm, {"versionId": version_id,
                                                  "estimatedCredits": CREDITS["train"]})
        if dry:
            return dry
        return api.call("start_training", "start_training", path_params={"project": project},
                        json={"version_id": version_id, "name": name, "variant": variant, "epochs": epochs,
                              "imgsz": imgsz, "batch": batch})

    @server.tool(annotations=WRITE)
    def predict_image(model_id: str, image_id: str = "", image_url: str = "", confidence: float | None = None,
                      confirm: bool = False) -> dict:
        """Run one ready model over one image you already hold, or one public URL; give exactly one source. Costs the server's published inference rate."""
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
        return api.call("predict", "predict", path_params={"model_id": model_id},
                        params={k: v for k, v in params.items() if v not in (None, "")})

    TOOL_SCOPES.update(SCOPES)
