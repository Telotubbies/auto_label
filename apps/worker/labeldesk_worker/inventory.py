"""What this worker's machine has, reported to the hub on every claim.

The report carries OS/arch, Python, GPUs, CUDA, free disk, whether ``HF_TOKEN`` is present, the
engine-install switch, installed engines and downloaded models. Every probe is guarded: a failure
becomes an empty value plus a line in ``reasons``, never an exception that would stop the worker.
Only engine/model ids and byte sizes leave the machine — no path, no token.
"""
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

MAX_GPUS = 8
MAX_ENGINES = 8
MAX_MODELS = 200
TEXT = 120                     # the API truncates every string to the same length
_PROBE_TIMEOUT_S = 10


def _smi(*args: str) -> str:
    """`nvidia-smi` stdout, or "" when the driver, the binary or the call is unavailable."""
    try:
        out = subprocess.run(["nvidia-smi", *args], capture_output=True, text=True,
                             timeout=_PROBE_TIMEOUT_S, check=True)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout


def _cuda() -> str | None:
    """The CUDA version from the `nvidia-smi` header, else what torch was built against."""
    found = re.search(r"CUDA Version:\s*([\d.]+)", _smi())
    if found:
        return found.group(1)
    try:
        import torch
    except Exception:                       # not installed, or a half-installed wheel
        return None
    return getattr(torch.version, "cuda", None)


def _gpus(cuda: str | None) -> list[dict]:
    gpus = []
    for line in _smi("--query-gpu=name,memory.total,driver_version", "--format=csv,noheader").splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        mib = re.match(r"(\d+)", parts[1])
        gpus.append({"name": parts[0][:TEXT], "vram_mb": int(mib.group(1)) if mib else None,
                     "driver": parts[2][:TEXT], "cuda": cuda})
        if len(gpus) >= MAX_GPUS:
            break
    return gpus


def _torch_gpus(cuda: str | None) -> list[dict]:
    """Fallback when `nvidia-smi` is absent but torch sees the cards."""
    try:
        import torch
    except Exception:
        return []
    if not torch.cuda.is_available():
        return []
    return [{"name": torch.cuda.get_device_name(i)[:TEXT],
             "vram_mb": int(torch.cuda.get_device_properties(i).total_memory // (1024 * 1024)),
             "driver": None, "cuda": cuda} for i in range(min(torch.cuda.device_count(), MAX_GPUS))]


def _disk(models_dir: Path) -> dict | None:
    """Free space where models land; falls back to the volume root when the directory is new."""
    for path in (models_dir, Path(models_dir.anchor or "/")):
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        gib = 1024 ** 3
        return {"models_free_gb": round(usage.free / gib, 1), "models_total_gb": round(usage.total / gib, 1)}
    return None


def _size(path: Path) -> int | None:
    """Bytes; for a directory only its own files are summed (shortcut: nested files are not counted)."""
    try:
        if path.is_file():
            return path.stat().st_size
        return sum(f.stat().st_size for f in path.iterdir() if f.is_file())
    except OSError:
        return None


def _entries(root: Path, cap: int) -> list[Path]:
    try:
        return [p for p in sorted(root.iterdir()) if not p.name.startswith(".")][:cap]
    except OSError:
        return []


def _engines(models_dir: Path) -> list[dict]:
    """Installed engines live beside the models dir: `<models_dir>/../engines/<id>-<version>`."""
    out = []
    for path in _entries(models_dir.parent / "engines", MAX_ENGINES):
        engine, _, version = path.name.rpartition("-")
        ok = False
        try:
            ok = path.is_dir() and any(path.iterdir())
        except OSError:
            pass
        out.append({"id": (engine or path.name)[:TEXT], "version": version[:TEXT] or None, "ok": ok})
    return out


def _models(models_dir: Path) -> list[dict]:
    return [{"id": p.name[:TEXT], "bytes": _size(p)} for p in _entries(models_dir, MAX_MODELS)]


def collect(models_dir: str | Path | None = None) -> dict:
    """One report; a failed probe is an empty value plus its reason, never an exception."""
    root = Path(models_dir or os.environ.get("LD_MODELS_DIR") or "~/.labeldesk/models").expanduser()
    report: dict = {"python": platform.python_version(), "hf_token": bool(os.environ.get("HF_TOKEN")),
                    "allow_install": os.environ.get("LD_ALLOW_ENGINE_INSTALL") == "1", "reasons": {}}
    reasons = report["reasons"]
    for key, probe in (("os", platform.system), ("arch", platform.machine),
                       ("cuda", _cuda), ("disk", lambda: _disk(root)),
                       ("engines", lambda: _engines(root)), ("models", lambda: _models(root))):
        try:
            report[key] = probe()
        except Exception as e:                  # a probe must never cost the worker its claim
            report[key] = None
            reasons[key] = f"{type(e).__name__}: {e}"[:TEXT]
    try:
        gpus = _gpus(report.get("cuda")) or _torch_gpus(report.get("cuda"))
        report["gpus"] = gpus
        if not gpus:
            reasons["gpus"] = "nvidia-smi and torch report no GPU"
    except Exception as e:
        report["gpus"] = []
        reasons["gpus"] = f"{type(e).__name__}: {e}"[:TEXT]
    if report.get("cuda") is None:
        reasons["cuda"] = "no CUDA version in nvidia-smi and no torch CUDA build"
    if report.get("disk") is None:
        reasons["disk"] = "disk usage is unavailable"
    return report
