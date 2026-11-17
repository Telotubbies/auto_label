"""The read tools: look at a project's data the way the Dataset and Models screens do.

Each tool is one `api.call` plus the shaping an agent needs and the route does not: a page cap
below the route's own maximum, and a sort allow-list so a typo never reaches the ranking.
"""
from typing import Any, TypedDict

from mcp.server.mcpserver import MCPServer
from pydantic import ConfigDict

from .api import Api
from .server import READ, TOOL_SCOPES, _enabled, summarised

# The Dataset screen accepts more sort values than an agent should be able to ask for.
SORTS = ("newest", "oldest", "name", "most", "least", "review")
MAX_PAGE = 200

NAMES = ("get_project", "list_images", "get_image", "list_versions", "list_models", "get_model",
         "get_job", "list_deployments")


class Page(TypedDict, total=False):
    """A page of images: the total the filter matched and the rows on this page."""

    __pydantic_config__ = ConfigDict(extra="allow")  # a new route field reaches the agent, never dropped
    total: int
    items: list[dict[str, Any]]


def register(server: MCPServer, api: Api) -> None:
    """Declare the eight read tools; `build_server` calls this once, both transports share them."""

    @server.tool(annotations=READ)
    def get_project(project: str) -> dict[str, Any]:
        """One project by slug: classes with ids and counts, image and model counts, status counts.

        Use it to learn a project's class ids before writing labels; do not use it to list images —
        call list_images with a filter.
        """
        _enabled(api)
        found = api.call("get_project", "get_project", path_params={"project": project})
        return summarised(found, f"{found.get('name')} ({found.get('slug')}): {found.get('images') or 0} images, "
                                 f"{found.get('models') or 0} models.")

    @server.tool(annotations=READ)
    def list_images(project: str, q: str = "", split: str = "", status: str = "", class_id: str = "",
                    tag: str = "", batch_id: str = "", annotated: str = "", sort: str = "newest",
                    offset: int = 0, limit: int = 50) -> Page:
        """One page of a project's images plus `total`; a page is capped at 200.

        Use it to find the images a job should touch; do not use it to read one image's labels — call
        get_image. `sort=review` means lowest-confidence AI work first, the label-quality loop.
        """
        _enabled(api)
        page = api.call("list_images", "list_images", path_params={"project": project}, params={
            "q": q, "split": split, "status": status, "class_id": class_id, "tag": tag,
            "batch_id": batch_id, "annotated": annotated, "sort": sort if sort in SORTS else "newest",
            "offset": offset, "limit": min(max(limit, 1), MAX_PAGE)})
        return summarised(page, f"{page.get('total') or 0} images in {project}, "
                                f"{len(page.get('items') or [])} on this page.")

    @server.tool(annotations=READ)
    def get_image(image_id: str) -> dict[str, Any]:
        """One image with its annotations: classId, shape, source and confidence for every label.

        Use it to judge label quality before you replace a set; do not use it to read many images —
        page list_images and read the ones you need.
        """
        _enabled(api)
        image = api.call("get_image", "get_image", path_params={"image_id": image_id})
        return summarised(image, f"{image.get('name')}: {len(image.get('annotations') or [])} annotations.")

    @server.tool(annotations=READ)
    def list_versions(project: str) -> list[dict]:
        """A project's frozen versions, newest first.

        Use it to pick a version to train on; do not use it to read a model's metrics — call get_model.
        """
        _enabled(api)
        return api.call("list_versions", "list_versions", path_params={"project": project})

    @server.tool(annotations=READ)
    def list_models() -> list[dict]:
        """Every trained model in this workspace, newest first.

        Use it to find a model id or a production candidate; do not use it to read one model's metrics —
        call get_model.
        """
        _enabled(api)
        return api.call("list_models", "list_models")

    @server.tool(annotations=READ)
    def get_model(model_id: str) -> dict[str, Any]:
        """One trained model: variant, status, metrics and the version it was trained on.

        Use it before predicting or deploying; do not use it to list the workspace's models — call
        list_models.
        """
        _enabled(api)
        model = api.call("get_model", "get_model", path_params={"model_id": model_id})
        return summarised(model, f"{model.get('name')} is {model.get('status')}.")

    @server.tool(annotations=READ)
    def get_job(job_id: str) -> dict[str, Any]:
        """One job's status, progress, error and result.

        Use it to poll work this session queued; do not use it to wait on a call — every job tool returns
        at once, so poll again after a pause.
        """
        _enabled(api)
        job = api.call("get_job", "get_job", path_params={"job_id": job_id})
        return summarised(job, f"Job {job.get('id')} is {job.get('status')} at {job.get('progress') or 0}%.")

    @server.tool(annotations=READ)
    def list_deployments() -> dict[str, Any]:
        """Every project's deployment aliases and the ready models each alias can point at.

        Use it to see what is serving before you deploy; do not use it to change an alias — that is a
        person's action in the Deploy screen.
        """
        _enabled(api)
        found = api.call("list_deployments", "list_deployments")
        return summarised(found, f"{len(found.get('projects') or [])} projects carry deployment aliases.")

    TOOL_SCOPES.update(dict.fromkeys(NAMES, "read"))
