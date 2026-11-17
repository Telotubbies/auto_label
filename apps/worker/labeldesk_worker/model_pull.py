"""T-1011: one resumable, verified model download on a worker host.

The API sends catalogue data and a relative target; nothing from a request becomes a path or a URL.
This module re-checks that boundary, refuses a download that would eat the disk's last 20%, lets
``huggingface_hub`` resume each file from its own ``.incomplete`` state, verifies every LFS file
against the hub's sha256 and only then moves ``<target>.partial`` into place. A checksum mismatch
or a full disk deletes the partial tree, so a half-downloaded model is never visible as installed.
"""
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from . import hf

GIB = 1024 ** 3
DISK_MARGIN = 0.8
CHECK_EVERY_PCT = 5.0
POST_EVERY_PCT = 1.0
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

disk_usage = shutil.disk_usage          # the one seam a test uses to move the free-space needle


class GuardError(RuntimeError):
    """A payload whose repo, revision, target or file path is not catalogue data."""


class DownloadFailed(RuntimeError):
    """A download the worker refused or aborted; the message is the job's error."""


def _gb(size) -> str:
    return f"{float(size) / GIB:.1f} GB"


def _size(size) -> str:
    """Human bytes for a file line; the disk sentence keeps GB so its shortfall is comparable."""
    if size >= GIB:
        return _gb(size)
    if size >= 1024 ** 2:
        return f"{size / 1024 ** 2:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _clean(value):
    """Redact token-shaped strings anywhere in a progress payload before it is posted."""
    if isinstance(value, str):
        return hf.redact(value)
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    return value


def _post(srv, job: dict, path: str, **kw) -> dict:
    return srv.post(f"/api/worker/jobs/{job['id']}/{path}", **kw) or {}


def _progress(srv, job: dict, percent: float, phase: str, log: list[str] | None = None) -> dict:
    return _post(srv, job, "progress", json=_clean({
        "progress": round(min(100.0, max(0.0, percent)), 1), "phase": phase,
        "log": list(log or [])}))


def _fail(srv, job: dict, message: str) -> None:
    _post(srv, job, "fail", json={"error": hf.redact(message)})


def _complete(srv, job: dict, result: dict) -> None:
    _post(srv, job, "complete", data={"result": json.dumps(_clean(result))})


def _safe_target(target) -> PurePosixPath:
    """``<id>/<variant>``: two plain segments and nothing a path could climb out of."""
    if not isinstance(target, str) or "\\" in target or target.startswith("/"):
        raise GuardError("target is not a relative catalogue path")
    parts = PurePosixPath(target).parts
    if len(parts) != 2 or not all(SEGMENT.fullmatch(part) for part in parts):
        raise GuardError("target must be <model>/<variant> from the catalogue")
    return PurePosixPath(*parts)


def _safe_file(path) -> str:
    """A relative POSIX path that stays under the partial directory."""
    if not isinstance(path, str) or not path or "\\" in path or path.startswith("/"):
        raise GuardError(f"{path!r} is not a relative file path")
    parts = PurePosixPath(path).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise GuardError(f"{path!r} leaves the target directory")
    if ":" in parts[0]:
        raise GuardError(f"{path!r} is an absolute path")
    return PurePosixPath(*parts).as_posix()


def guard(payload: dict) -> SimpleNamespace:
    """Validate the whole payload before the first hub call; raise ``GuardError`` on any doubt."""
    action = payload.get("action")
    if action not in ("download", "remove"):
        raise GuardError("action must be download or remove")
    repo = payload.get("repo")
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise GuardError("repo must be owner/name")
    revision = payload.get("revision")
    if not isinstance(revision, str) or not COMMIT.fullmatch(revision):
        raise GuardError("revision must be a pinned commit")
    target = _safe_target(payload.get("target"))
    files = payload.get("files") or []
    if not isinstance(files, list):
        raise GuardError("files must be a list")
    clean = []
    for item in files:
        if not isinstance(item, dict):
            raise GuardError("a file entry must be an object")
        size = item.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise GuardError("every file needs a positive byte size")
        clean.append({"path": _safe_file(item.get("path")), "bytes": size,
                      "sha256": item.get("sha256")})
    total = payload.get("total_bytes")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise GuardError("total_bytes must be a non-negative integer")
    if action == "download":
        if not clean:
            raise GuardError("a download needs at least one file")
        if total != sum(item["bytes"] for item in clean):
            raise GuardError("total_bytes does not add up to the file sizes")
    return SimpleNamespace(action=action, repo=repo, revision=revision, target=target.as_posix(),
                           files=clean, total=total)


def _check_disk(models_dir: Path, total: int, phase: str) -> None:
    """The 20% floor, checked before the first byte, every 5% and after every file."""
    free = disk_usage(models_dir).free
    if free * DISK_MARGIN >= total:
        return
    short = (total - free * DISK_MARGIN) / GIB
    raise DownloadFailed(
        f"disk_full: {phase} needs {_gb(total)}, {_gb(free)} free; the download keeps 20% of the "
        f"disk free, short by {short:.1f} GB.")


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _download(srv, job: dict, spec, models_dir: Path, token: str | None) -> None:
    target = models_dir / spec.target
    partial = target.with_name(target.name + ".partial")
    _check_disk(models_dir, spec.total, "download")
    meta = hf.metadata(spec.repo, spec.revision, token)
    partial.mkdir(parents=True, exist_ok=True)
    done = 0
    last_check = -CHECK_EVERY_PCT
    last_post = -POST_EVERY_PCT

    for index, file in enumerate(spec.files, 1):
        phase = f"downloading {file['path']} ({index}/{len(spec.files)})"
        _progress(srv, job, done / spec.total * 100 if spec.total else 0, phase,
                  [f"{file['path']} — {_size(file['bytes'])}"])
        first = True

        def on_bytes(written, base=done, size=file["bytes"], phase=phase):
            nonlocal last_check, last_post, first
            if first:                       # the hub's bar starts at what the .incomplete file has
                first = False
                if written:
                    _progress(srv, job, base / spec.total * 100 if spec.total else 0, phase,
                              [f"resuming at {_size(min(int(written), size))}"])
            have = base + min(int(written), size)
            percent = have / spec.total * 100 if spec.total else 100
            if percent - last_check >= CHECK_EVERY_PCT:
                last_check = percent
                _check_disk(models_dir, spec.total, phase)
            if percent - last_post >= POST_EVERY_PCT or percent >= 100:
                last_post = percent
                _progress(srv, job, percent, phase)

        hf.download(spec.repo, spec.revision, file["path"], partial, token, on_bytes)
        _check_disk(models_dir, spec.total, f"after {file['path']}")
        done += file["bytes"]

    _progress(srv, job, 100, "verifying")
    records = []
    lfs = 0
    for file in spec.files:
        path = partial / file["path"]
        live = meta.get(file["path"])
        if live is None:
            raise DownloadFailed(f"checksum_failed: {file['path']} is not in the repository "
                                 f"at this revision")
        if live["bytes"] != file["bytes"]:
            _progress(srv, job, 100, "verifying",
                      [f"{file['path']} is {live['bytes']} bytes; the catalogue said "
                       f"{file['bytes']}, the hub metadata wins"])
        actual = path.stat().st_size
        if actual != live["bytes"]:
            raise DownloadFailed(f"checksum_failed: {file['path']} is {actual} bytes, expected "
                                 f"{live['bytes']}")
        if live["lfs_oid"]:
            lfs += 1
            if hf.sha256(path) != live["lfs_oid"]:
                raise DownloadFailed(f"checksum_failed: {file['path']} does not match the "
                                     f"hub sha256")
            records.append({"path": file["path"], "bytes": actual, "verified": "sha256"})
        else:
            records.append({"path": file["path"], "bytes": actual, "verified": "size"})
    plain = len(records) - lfs
    if plain:
        _progress(srv, job, 100, "verifying",
                  [f"{plain} non-LFS files were size-checked only; the hub publishes no sha256 "
                   f"for them"])

    os.replace(partial, target)
    free = disk_usage(models_dir).free
    _complete(srv, job, {"target": spec.target, "bytes": spec.total, "files": records,
                         "disk_free_gb": round(free / GIB, 1)})


def run_model_pull(srv, job: dict, args) -> None:
    """Claimed ``model_pull`` job: validate, then download-and-verify or remove the target."""
    payload = job.get("payload") or {}
    spec = guard(payload)                    # before any hub call, progress post or write
    models_dir = Path(args.models_dir).expanduser().resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    target = models_dir / spec.target

    if spec.action == "remove":
        _progress(srv, job, 0, f"removing {spec.target}")
        if not target.is_dir():
            _fail(srv, job, f"not_installed: {spec.target} is not on this host")
            return
        freed = _tree_bytes(target)
        shutil.rmtree(target)
        free = disk_usage(models_dir).free
        _complete(srv, job, {"target": spec.target, "freed_bytes": freed,
                             "disk_free_gb": round(free / GIB, 1)})
        return

    try:
        _download(srv, job, spec, models_dir, hf.token())
    except DownloadFailed as exc:
        shutil.rmtree(target.with_name(target.name + ".partial"), ignore_errors=True)
        _fail(srv, job, str(exc))
