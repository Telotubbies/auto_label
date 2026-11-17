"""Engine compatibility: whether this host can run a pinned engine, said before the button exists.

The evaluator is pure — a sanitised host report (T-1001) and one catalogue row (T-1002) in, a
verdict out — so every rule is testable without HTTP. Rules run in the card's order and stop at the
first block, while every warning is collected. Versions compare numerically (``12.10 > 12.4``), and
no inventory key is read with ``[]``: a partial report answers "unknown", never a 500.
"""
from __future__ import annotations

import re

UNKNOWN_HARDWARE = "This host has not reported hardware yet."
OFFLINE = "This host is offline; its last report is shown, but installs are blocked."

_OS_LABELS = {"linux": "Linux", "macos": "macOS", "windows": "Windows"}


def _verdict(reasons: list[str], warnings: list[str], installed: bool = False) -> dict:
    status = "blocked" if reasons else ("warn" if warnings else "ok")
    return {"status": status, "reasons": reasons, "warnings": warnings, "installed": installed}


def _versions(text) -> tuple[int, ...] | None:
    """``"12.10"`` → ``(12, 10)``; text with no number is unreadable, not zero."""
    if text is None or isinstance(text, bool):
        return None
    if not isinstance(text, (str, int, float)):
        return None
    parts = re.findall(r"\d+", str(text))
    return tuple(int(part) for part in parts) if parts else None


def _gpu_field(host_inventory: dict, key: str) -> str | None:
    gpus = host_inventory.get("gpus")
    for gpu in gpus if isinstance(gpus, list) else []:
        if isinstance(gpu, dict) and gpu.get(key):
            return str(gpu[key])
    return None


def _os_requirement(supported: list[str]) -> str:
    labels = [_OS_LABELS.get(name, name) for name in supported]
    return f"{labels[0]} only" if len(labels) == 1 else " or ".join(labels)


def _installed(inventory: dict, engine: dict) -> bool:
    rows = inventory.get("engines")
    for row in rows if isinstance(rows, list) else []:
        if (isinstance(row, dict) and row.get("id") == engine.get("id")
                and str(row.get("version") or "") == str(engine.get("version") or "")):
            return True
    return False


def evaluate(host_inventory: dict | None, engine: dict, runtime: str | None, *,
             free_gb: float | None) -> dict:
    """One engine on one host: ``{status, reasons, warnings, installed}``."""
    if not isinstance(host_inventory, dict) or not host_inventory:
        return _verdict([UNKNOWN_HARDWARE], [])
    warnings: list[str] = []
    accelerators = [str(a).lower() for a in engine.get("accelerator") or []]

    gpus = host_inventory.get("gpus")
    if not (isinstance(gpus, list) and any(isinstance(gpu, dict) for gpu in gpus)):
        if "cpu" not in accelerators:
            need = "an NVIDIA GPU" if "nvidia" in accelerators else "a GPU"
            return _verdict([f"Needs {need}; this host reports CPU only."], warnings)

    supported = [str(o).lower() for o in engine.get("os") or []]
    reported_os = str(host_inventory.get("os") or "").lower()
    if supported and reported_os and reported_os not in supported:
        requirement = _os_requirement(supported)
        if reported_os == "windows":
            warnings.append(f"{requirement}; the host reports Windows and WSL was not detected.")
        else:
            return _verdict([f"{requirement}; the host reports {host_inventory.get('os')}."], warnings)

    pin_driver = engine.get("min_driver")
    if pin_driver:
        driver = _gpu_field(host_inventory, "driver")
        have, need = _versions(driver), _versions(pin_driver)
        if have is None:
            return _verdict(["The host has not reported its driver, so the driver requirement is unknown."],
                            warnings)
        if need and have < need:
            cuda = host_inventory.get("cuda")
            seen = f"{driver} and CUDA {cuda}" if cuda else driver
            return _verdict([f"Needs driver {pin_driver} or newer; the host reports {seen}."], warnings)
        if need and have[0] != need[0]:
            warnings.append(f"Untested driver {driver}; the pin is verified on {pin_driver}.")

    if engine.get("cuda_min") or engine.get("cuda_max"):
        cuda = host_inventory.get("cuda")
        have = _versions(cuda)
        if have is None:
            return _verdict(["The host has not reported its CUDA version, so the CUDA requirement is unknown."],
                            warnings)
        low, high = _versions(engine.get("cuda_min")), _versions(engine.get("cuda_max"))
        if low and have < low:
            return _verdict([f"Needs CUDA {engine['cuda_min']} or newer; the host reports {cuda}."], warnings)
        if high and have > high:
            wants = (f"{engine['cuda_min']}–{engine['cuda_max']}" if engine.get("cuda_min")
                     else f"up to {engine['cuda_max']}")
            return _verdict([f"Needs CUDA {wants}; the host reports {cuda}."], warnings)

    disk_mb = engine.get("disk_mb")
    if disk_mb:
        try:
            free = float(free_gb)
        except (TypeError, ValueError):
            free = None
        if free is None:
            return _verdict(["The host has not reported free disk, so the disk requirement is unknown."],
                            warnings)
        if free < float(disk_mb) * 1.2 / 1024:
            return _verdict([f"Needs {float(disk_mb) / 1024:.1f} GB free; the host has {free:.1f} GB."],
                            warnings)

    if runtime == "docker" and host_inventory.get("docker") is not True:
        if host_inventory.get("docker") is False:
            return _verdict(["Docker is not available on this host."], warnings)
        return _verdict(["The host has not reported whether Docker is available, so compatibility is unknown."],
                        warnings)

    if _installed(host_inventory, engine):
        return _verdict([], warnings, installed=True)
    return _verdict([], warnings)
