"""The read tools: look at a project's data the way the Dataset and Models screens do.

Each tool is one `api.call` plus the shaping an agent needs and the route does not: a page cap
below the route's own maximum, and a sort allow-list so a typo never reaches the ranking.
"""
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .api import Api
from .server import TOOL_SCOPES, _enabled

# The Dataset screen accepts more sort values than an agent should be able to ask for.
SORTS = ("newest", "oldest", "name", "most", "least", "review")
MAX_PAGE = 200
READ_ONLY = ToolAnnotations(read_only_hint=True)

NAMES = ("get_project", "list_images", "get_image", "list_versions", "list_models", "get_model",
         "get_job", "list_deployments")


def register(server: MCPServer, api: Api) -> None:
    """Declare the eight read tools; `build_server` calls this once, both transports share them."""

    @server.tool(annotations=READ_ONLY)
    def get_project(project: str) -> dict:
        """One project by slug: its classes with ids and counts, image and model counts, status counts."""
        _enabled(api)
        return api.call("get_project", "get_project", path_params={"project": project})

    @server.tool(annotations=READ_ONLY)
    def list_images(project: str, q: str = "", split: str = "", status: str = "", class_id: str = "",
                    tag: str = "", batch_id: str = "", annotated: str = "", sort: str = "newest",
                    offset: int = 0, limit: int = 50) -> dict:
        """One page of a project's images plus `total`; a page is capped at 200.

        `sort=review` means lowest-confidence AI work first — the label-quality loop.
        """
        _enabled(api)
        return api.call("list_images", "list_images", path_params={"project": project}, params={
            "q": q, "split": split, "status": status, "class_id": class_id, "tag": tag,
            "batch_id": batch_id, "annotated": annotated, "sort": sort if sort in SORTS else "newest",
            "offset": offset, "limit": min(max(limit, 1), MAX_PAGE)})

    @server.tool(annotations=READ_ONLY)
    def get_image(image_id: str) -> dict:
        """One image with its annotations: classId, shape, source and confidence for every label."""
        _enabled(api)
        return api.call("get_image", "get_image", path_params={"image_id": image_id})

    @server.tool(annotations=READ_ONLY)
    def list_versions(project: str) -> list:
        """A project's frozen versions, newest first."""
        _enabled(api)
        return api.call("list_versions", "list_versions", path_params={"project": project})

    @server.tool(annotations=READ_ONLY)
    def list_models() -> list:
        """Every trained model in this workspace, newest first."""
        _enabled(api)
        return api.call("list_models", "list_models")

    @server.tool(annotations=READ_ONLY)
    def get_model(model_id: str) -> dict:
        """One trained model: variant, status, metrics and the version it was trained on."""
        _enabled(api)
        return api.call("get_model", "get_model", path_params={"model_id": model_id})

    @server.tool(annotations=READ_ONLY)
    def get_job(job_id: str) -> dict:
        """One job's status, progress, error and result; poll this rather than waiting on a call."""
        _enabled(api)
        return api.call("get_job", "get_job", path_params={"job_id": job_id})

    @server.tool(annotations=READ_ONLY)
    def list_deployments() -> dict:
        """Every project's deployment aliases and the ready models each alias can point at."""
        _enabled(api)
        return api.call("list_deployments", "list_deployments")

    TOOL_SCOPES.update(dict.fromkeys(NAMES, "read"))
