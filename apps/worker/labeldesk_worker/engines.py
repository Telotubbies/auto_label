"""T-1008: run one reviewed engine plan on this worker host, and nowhere else.

The API never installs anything; a claimed ``engine_apply`` job runs here, one process group at a
time, with an argv the guard re-checks before exec. Progress carries the phase and a line-by-line
log tail, a cancel stops the group and removes what was being built, and a plan that no longer
matches this host's own inventory is refused instead of run. Uninstall is the same handler with
``action: "uninstall"`` and the removal argv.
"""
import hashlib
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import ollama
from .inventory import collect

ALLOWED_EXECUTABLES = {"uv", "python", "python3", "docker", "rm", "ollama"}
WRITES_OUTSIDE = {"--target", "--prefix", "-t"}       # options that plant files wherever they point
SHELL_META = (";", "|", "&", "$(", "`", ">", "<", "\n", "\r")
DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
OLLAMA_TAG = re.compile(r"^[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*$")
TIMEOUT_S = 30 * 60          # one engine, cold pip or an image pull included
CANCEL_GRACE_S = 10
HEARTBEAT_S = 5.0            # a silent command still reports, so the reaper sees it alive
MAX_LOG = 200
MAX_LINE = 500
PHASES = {"uninstall": "removing", "pull": "pulling"}
_CANCELLED = -1


class GuardError(RuntimeError):
    """An argv the guard will not execute."""


class PlanChanged(RuntimeError):
    """The plan was built for another inventory than the one this host reports."""


class InstallsDisabled(RuntimeError):
    """This worker was never told to accept engine installs."""


class EngineFailed(RuntimeError):
    """One engine's command failed; the message keeps the exit code and the last output line."""


def _stamp(inventory: dict | None) -> dict:
    """The plan-relevant facts of a report; the API hashes the same projection (inference_plan)."""
    inv = inventory or {}
    free = (inv.get("disk") or {}).get("models_free_gb")
    gpus = sorted(([gpu.get("name"), gpu.get("vram_mb"), gpu.get("driver"), gpu.get("cuda")]
                   for gpu in inv.get("gpus") or [] if isinstance(gpu, dict)), key=json.dumps)
    engines = sorted(([row.get("id"), row.get("version"), row.get("runtime")]
                      for row in inv.get("engines") or [] if isinstance(row, dict)), key=json.dumps)
    return {"os": inv.get("os"), "arch": inv.get("arch"), "cuda": inv.get("cuda"),
            "gpus": gpus, "engines": engines,
            "disk_free_gb": None if free is None else round(float(free))}


def plan_id(host: str, steps: list[dict], inventory: dict | None) -> str:
    """The API's plan digest, recomputed from this host's *own* inventory."""
    body = json.dumps({"host": host, "steps": steps, "inventory": _stamp(inventory)},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _pathlike(value: str) -> bool:
    return (value.startswith(("/", "./", "../", "~")) or DRIVE_PATH.match(value) is not None
            or "\\" in value or "/" in value)


def guard(argv: list[str], engines_dir: Path) -> None:
    """Refuse an argv whose executable or path arguments could leave ``engines_dir``.

    shortcut: an allowlisted interpreter still runs whatever it is handed, so the argv must come from
    the catalogue's plan; upgrade to an argv allowlist if a plan can ever carry anything else.
    """
    if not argv or Path(argv[0]).name.lower() not in ALLOWED_EXECUTABLES:
        raise GuardError(f"{argv[0] if argv else ''!r} is not an allowed executable")
    if Path(argv[0]).name.lower() == "ollama" and (
            len(argv) != 3 or argv[1] != "pull" or not OLLAMA_TAG.fullmatch(argv[2])):
        raise GuardError("only `ollama pull <name:tag>` may run on this worker")
    root = Path(engines_dir).resolve()
    for arg in argv:
        if not isinstance(arg, str) or not arg:
            raise GuardError("an empty argument is not allowed")
        if any(token in arg for token in SHELL_META):
            raise GuardError(f"{arg!r} contains a shell metacharacter")
        if arg in WRITES_OUTSIDE:
            raise GuardError(f"{arg} writes outside the engines directory")
        if ".." in Path(arg).parts:
            raise GuardError(f"{arg!r} leaves the engines directory")
        if _pathlike(arg) and root not in (root / arg).resolve().parents:
            raise GuardError(f"{arg!r} is outside the engines directory")


def minimal_env() -> dict:
    """PATH, HOME, LANG and a temp dir: HF_TOKEN and every other secret stays out of an install."""
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
    temp = (os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "TMPDIR": temp, "TEMP": temp, "TMP": temp,
           "LANG": os.environ.get("LANG", "C.UTF-8")}
    if os.name == "nt" and os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


def _group_kwargs() -> dict:
    """Own process group, so a cancel reaches pip and not just its parent."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _stop(proc: subprocess.Popen) -> None:
    """Stop the whole group; a pip child that outlives its parent would keep writing."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=CANCEL_GRACE_S)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=CANCEL_GRACE_S)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=CANCEL_GRACE_S)
    except OSError:                     # the process ended between the poll and the signal
        pass


def _pump(proc: subprocess.Popen, lines: "queue.Queue[str | None]") -> None:
    """Feed complete output lines to the queue and mark the end with None."""
    try:
        for line in proc.stdout:
            lines.put(line.rstrip("\r\n"))
    finally:
        lines.put(None)


def _resolved(argv: list[str]) -> list[str]:
    """A bare executable is found on PATH; a path form is resolved inside the engines directory."""
    exe = argv[0]
    if "/" in exe or "\\" in exe:
        return list(argv)
    return [shutil.which(exe) or exe, *argv[1:]]


def _post(srv, job: dict, path: str, **kw) -> dict:
    return srv.post(f"/api/worker/jobs/{job['id']}/{path}", **kw) or {}


def _stream(srv, job: dict, argv: list[str], cwd: Path, phase: str, percent: float,
            ) -> tuple[int, list[str]]:
    """Run one argv, posting every line; returns (exit code or _CANCELLED, tail)."""
    proc = subprocess.Popen([str(part) for part in argv], shell=False, cwd=str(cwd),
                            env=minimal_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **_group_kwargs())
    lines: "queue.Queue[str | None]" = queue.Queue()
    threading.Thread(target=_pump, args=(proc, lines), daemon=True).start()
    tail: list[str] = []
    deadline = time.monotonic() + TIMEOUT_S
    while True:
        try:
            line = lines.get(timeout=HEARTBEAT_S)
        except queue.Empty:
            line = ""
        if line is None:                                   # stdout closed: the command is done
            proc.wait()
            return proc.returncode, tail
        if line:
            tail = (tail + [line[-MAX_LINE:]])[-MAX_LOG:]
        answer = _post(srv, job, "progress", json={"progress": round(percent, 1), "phase": phase,
                                                   "log": [line[-MAX_LINE:]] if line else []})
        if answer.get("cancel"):
            _stop(proc)
            return _CANCELLED, tail
        if time.monotonic() > deadline:
            _stop(proc)
            raise EngineFailed(f"{phase} took longer than {TIMEOUT_S // 60} minutes")


def run_engine_apply(srv, job: dict, args) -> None:
    """Run the claimed plan: refuse, guard, verify, then one engine at a time."""
    if os.environ.get("LD_ALLOW_ENGINE_INSTALL") != "1":
        raise InstallsDisabled("installs_disabled: this worker does not accept engine installs "
                               "(set LD_ALLOW_ENGINE_INSTALL=1 on it)")
    payload = job.get("payload") or {}
    action = str(payload.get("action") or "install")
    engines = [engine for engine in payload.get("engines") or [] if isinstance(engine, dict)]
    root = Path(args.engines_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    if action == "pull":                                # a stopped server fails before any exec
        try:
            ollama.version()
        except ollama.OllamaUnreachable as exc:
            _post(srv, job, "progress", json={"progress": 0, "phase": "ollama_unreachable",
                                              "log": [str(exc)]})
            _post(srv, job, "fail", json={"error": str(exc)})
            return

    for engine in engines:                                 # every path is judged before the first exec
        for argv in engine.get("argv") or []:
            guard(argv, root)
    if action == "install" and payload.get("plan_id"):
        if plan_id(str(payload.get("host") or ""), engines, collect(args.models_dir)) != payload["plan_id"]:
            _post(srv, job, "progress", json={
                "progress": 0, "phase": "stale_plan",
                "log": ["stale_plan: this host changed since the plan was reviewed"]})
            raise PlanChanged("stale_plan: this install plan no longer matches the host; "
                              "review the install plan again")

    done: list[dict] = []
    try:
        for index, engine in enumerate(engines):
            target = f"{engine.get('id')}-{engine.get('version')}"
            phase = f"{PHASES.get(action, 'installing')} {engine.get('id')}"
            percent = index / max(1, len(engines)) * 100
            for argv in engine.get("argv") or []:
                code, tail = _stream(srv, job, _resolved(argv), root, phase, percent)
                if code == _CANCELLED:
                    shutil.rmtree(root / target, ignore_errors=True)
                    _post(srv, job, "complete",
                          data={"result": json.dumps({"cancelled": True, "engines": done})})
                    return
                if code:
                    raise EngineFailed(f"{phase} failed with exit code {code}: "
                                       f"{tail[-1] if tail else 'no output'}")
            if action == "pull":
                # The host's inventory is the one-model record; a pulled tag is a model it holds.
                marker = Path(args.models_dir).expanduser().resolve() / str(engine.get("id"))
                marker.mkdir(parents=True, exist_ok=True)
                (marker / "tag.txt").write_text(str(engine.get("tag") or ""))
                done.append({"id": engine.get("id"), "version": engine.get("version"),
                             "runtime": "ollama", "path": marker.name})
            elif action != "uninstall":
                path = target
                if engine.get("runtime") == "docker":
                    path = str(((engine.get("argv") or [[]])[0] or [""])[-1])
                done.append({"id": engine.get("id"), "version": engine.get("version"),
                             "runtime": engine.get("runtime"), "path": path})
            _post(srv, job, "progress",
                  json={"progress": round((index + 1) / max(1, len(engines)) * 100, 1),
                        "phase": phase, "log": []})
    except EngineFailed as exc:
        _post(srv, job, "fail", json={"error": str(exc), "result": {"engines": done}})
        return
    _post(srv, job, "complete", data={"result": json.dumps({"engines": done})})
