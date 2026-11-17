"""Install plans: the exact argv, bytes and disk-after for a selection of engines (T-1006).

A plan is a pure function of one host's last inventory and the catalogue: it writes nothing, and
its ``plan_id`` is a digest of the host, the steps and the inventory, so a plan that no longer
describes the host is refused instead of executed. No request string reaches an argv — the id is
looked up in the catalogue, the version must equal the pin, and the runtime must be one the engine
offers. A path is relative to the worker's engines directory: the only form that is true on a
remote host and still cannot leave that directory, because the worker's guard resolves it there.
"""
import hashlib
import json

from . import inference_catalog, inference_compat


class InvalidSelection(ValueError):
    """An engine, runtime or version the catalogue does not offer."""


def _commands(engine: dict, runtime: str) -> list[list[str]]:
    """The fixed install argv for one pinned engine; every string comes from the catalogue."""
    target = f"{engine['id']}-{engine['version']}"
    if runtime == "docker":
        return [["docker", "pull", engine["container"]]]
    if runtime == "uv":
        return [["uv", "venv", target],
                ["uv", "pip", "install", "--python", f"{target}/bin/python", engine["package"]]]
    return [["python", "-m", "venv", target],
            [f"{target}/bin/python", "-m", "pip", "install", "--no-input", engine["package"]]]


def installed_version(engine: dict, installed: dict) -> str:
    """The version the host says it has, used only when it is pin-shaped; else the catalogue pin."""
    version = str(installed.get("version") or "")
    return version if inference_catalog.VERSION.match(version) else engine["version"]


def uninstall_commands(engine: dict, runtime: str, version: str) -> list[list[str]]:
    """Remove the container by digest, or the venv directory the host says it has."""
    if runtime == "docker":
        return [["docker", "rmi", engine["container"]]]
    return [["rm", "-rf", f"{engine['id']}-{version}"]]


def _stamp(inventory: dict | None) -> dict:
    """What the plan depends on, with free disk in whole GB so ordinary drift is not a stale plan."""
    inv = inventory or {}
    free = (inv.get("disk") or {}).get("models_free_gb")
    gpus = sorted(([g.get("name"), g.get("vram_mb"), g.get("driver"), g.get("cuda")]
                   for g in inv.get("gpus") or [] if isinstance(g, dict)), key=json.dumps)
    engines = sorted(([e.get("id"), e.get("version"), e.get("runtime")]
                      for e in inv.get("engines") or [] if isinstance(e, dict)), key=json.dumps)
    return {"os": inv.get("os"), "arch": inv.get("arch"), "cuda": inv.get("cuda"),
            "gpus": gpus, "engines": engines,
            "disk_free_gb": None if free is None else round(float(free))}


def _plan_id(host: str, steps: list[dict], inventory: dict | None) -> str:
    body = json.dumps({"host": host, "steps": steps, "inventory": _stamp(inventory)},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def build(host: dict, engines: list[dict], inventory: dict | None) -> dict:
    """One step per engine, plus bytes, disk after, warnings and the blocked rows.

    ``host`` is the host row: its id identifies the plan and its ``online`` flag decides whether an
    install may be planned at all. Unknown ids, versions and runtimes raise ``InvalidSelection``.
    """
    free = ((inventory or {}).get("disk") or {}).get("models_free_gb")
    steps, blocked, warnings = [], [], []
    for choice in engines:
        try:
            engine = inference_catalog.engine(str(choice.get("id") or ""))
        except KeyError:
            raise InvalidSelection(f"{choice.get('id')!r} is not in the engine catalogue") from None
        runtime = str(choice.get("runtime") or "")
        if runtime not in engine["runtimes"]:
            raise InvalidSelection(f"{engine['name']} does not offer the {runtime} runtime")
        if str(choice.get("version") or "") != engine["version"]:
            raise InvalidSelection(f"{engine['name']} is pinned to {engine['version']}")

        verdict = inference_compat.evaluate(inventory, engine, runtime, free_gb=free)
        step = {"id": engine["id"], "version": engine["version"], "runtime": runtime,
                "argv": [], "disk_mb": 0}
        if verdict["installed"]:
            step.update(status="installed", installed_version=engine["version"])
        elif not host.get("online", True):
            reason = inference_compat.OFFLINE
            step.update(status="blocked", reason=reason)
            blocked.append({"id": engine["id"], "reason": reason})
        elif verdict["status"] == "blocked":
            reason = " ".join(verdict["reasons"])
            step.update(status="blocked", reason=reason)
            blocked.append({"id": engine["id"], "reason": reason})
        else:
            step.update(status="install", argv=_commands(engine, runtime), disk_mb=engine["disk_mb"])
            warnings.extend(verdict["warnings"])
        steps.append(step)

    total = sum(step["disk_mb"] for step in steps if step["status"] == "install")
    free_gb = None if free is None else float(free)
    return {"plan_id": _plan_id(host["id"], steps, inventory), "host": host["id"], "steps": steps,
            "total_disk_mb": total, "disk_free_gb": free_gb,
            "disk_after_gb": None if free_gb is None else round(free_gb - total / 1024, 1),
            "warnings": warnings, "blocked": blocked,
            "noop": not any(step["status"] == "install" for step in steps)}
