"""Platform-operator identity. `LD_SUPERADMINS` is read per call so tests and ops can change it."""
import os


def emails() -> set[str]:
    raw = os.environ.get("LD_SUPERADMINS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_superadmin(user) -> bool:
    return bool(user and (getattr(user, "email", "") or "").lower() in emails())
