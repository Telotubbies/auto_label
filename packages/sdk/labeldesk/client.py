"""Hand-written client over the generated operation map. One dependency: httpx."""
from __future__ import annotations

import mimetypes
import os
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from ._generated import OPERATIONS

DEFAULT_URL = "http://localhost:8010"


class LabelDeskError(Exception):
    """An API or transport failure. `status` 0 means the request never got a response."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}" if status else str(detail))


def _detail(response: httpx.Response) -> str:
    """FastAPI puts the human message in `detail`; validation errors arrive as a list."""
    try:
        body = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(body, dict) and body.get("detail"):
        detail = body["detail"]
        if isinstance(detail, list):
            return "; ".join(str(d.get("msg", d)) if isinstance(d, dict) else str(d) for d in detail)
        return str(detail)
    return response.text or response.reason_phrase


def _content_type(path: str | os.PathLike) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _file_part(path: str | os.PathLike, handle) -> tuple[str, Any, str]:
    return (Path(path).name, handle, _content_type(path))


class LabelDesk:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 transport: httpx.BaseTransport | None = None, timeout: float = 60):
        self.api_key = api_key if api_key is not None else os.environ.get("LABELDESK_API_KEY")
        self.base_url = (base_url or os.environ.get("LABELDESK_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self._http = httpx.Client(transport=transport, timeout=timeout)

    # --- transport -------------------------------------------------------------------------

    def call(self, operation: str, path_params: dict | None = None, params: dict | None = None,
             json: Any = None, files: Any = None, data: dict | None = None) -> Any:
        spec = OPERATIONS.get(operation)
        if spec is None:
            raise LabelDeskError(0, f"unknown operation: {operation}")
        path_params = path_params or {}
        path = spec["path"]
        for name in spec["params"]:
            if name not in path_params:
                raise LabelDeskError(0, f"{operation} needs path parameter '{name}'")
            path = path.replace("{" + name + "}", quote(str(path_params[name]), safe=""))

        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = self._http.request(spec["method"].upper(), self.base_url + path, params=params, json=json,
                                          files=files, data=data, headers=headers)
        except httpx.HTTPError as exc:
            raise LabelDeskError(0, str(exc)) from exc
        if not response.is_success:
            raise LabelDeskError(response.status_code, _detail(response))
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    # --- developer API ---------------------------------------------------------------------

    def whoami(self) -> dict:
        return self.call("whoami")

    def projects(self) -> list:
        return self.call("list_projects")

    def images(self, project: str, offset: int = 0, limit: int = 100) -> dict:
        return self.call("list_images", {"project": project}, params={"offset": offset, "limit": limit})

    def upload(self, project: str, paths: str | os.PathLike | list, batch_name: str = "CLI Upload",
               split: str = "auto", tags: str = "") -> dict:
        paths = [paths] if isinstance(paths, (str, os.PathLike)) else list(paths)
        with ExitStack() as stack:
            files = [("files", _file_part(p, stack.enter_context(open(p, "rb")))) for p in paths]
            return self.call("upload_images", {"project": project}, files=files,
                             data={"batch_name": batch_name, "split": split, "tags": tags})

    def versions(self, project: str) -> list:
        return self.call("list_versions", {"project": project})

    def export(self, project: str, version_id: str, fmt: str = "coco") -> dict:
        return self.call("export_version", {"project": project, "vid": version_id}, json={"format": fmt})

    def train(self, project: str, version_id: str, variant: str = "yolo26n", epochs: int = 30,
              imgsz: int = 640, batch: int = 8) -> dict:
        return self.call("start_training", {"project": project},
                         json={"version_id": version_id, "variant": variant, "epochs": epochs,
                               "imgsz": imgsz, "batch": batch})

    def job(self, job_id: str, wait: bool = False, poll_s: float = 2.0) -> dict:
        job = self.call("get_job", {"job_id": job_id})
        while wait and job.get("status") not in ("done", "failed", "cancelled"):
            time.sleep(poll_s)
            job = self.call("get_job", {"job_id": job_id})
        if job.get("status") == "failed":
            raise LabelDeskError(0, job.get("error") or f"job {job_id} failed")
        return job

    def models(self) -> list:
        return self.call("list_models")

    def model(self, model_id: str) -> dict:
        return self.call("get_model", {"model_id": model_id})

    def predict(self, model_id: str, image_path: str | os.PathLike, confidence: float | None = None) -> dict:
        with ExitStack() as stack:
            handle = stack.enter_context(open(image_path, "rb"))
            # confidence/overlap are query params on the hosted route, not multipart fields
            params = {} if confidence is None else {"confidence": confidence}
            return self.call("predict", {"model_id": model_id}, params=params or None,
                             files={"file": _file_part(image_path, handle)})

    def download(self, url: str, dest: str | os.PathLike) -> Path:
        full = url if url.startswith(("http://", "https://")) else self.base_url + url
        dest = Path(dest)
        # only hand the key to our own API — never to a third-party absolute URL
        same_origin = not url.startswith(("http://", "https://")) or full.startswith(self.base_url + "/")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key and same_origin else {}
        try:
            with self._http.stream("GET", full, headers=headers) as response:
                if not response.is_success:
                    response.read()
                    raise LabelDeskError(response.status_code, _detail(response))
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as out:
                    for chunk in response.iter_bytes():
                        out.write(chunk)
        except httpx.HTTPError as exc:
            raise LabelDeskError(0, str(exc)) from exc
        return dest

    # --- lifecycle -------------------------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "LabelDesk":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
