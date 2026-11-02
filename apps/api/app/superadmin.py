"""Platform-operator identity. `LD_SUPERADMINS` is read per call so tests and ops can change it.

Privilege never comes from an unverified address: signup is open by default, so an operator
pre-listing `ops@company.com` must not hand the console to whoever registers that address first.
A persisted `platform_admin` flag (set out of band) is honoured for the same verified account.
"""
import os


def emails() -> set[str]:
    raw = os.environ.get("LD_SUPERADMINS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_superadmin(user) -> bool:
    if not user or not getattr(user, "email_verified", None):
        return False
    if getattr(user, "platform_admin", False):
        return True
    return (getattr(user, "email", "") or "").lower() in emails()
