"""Public capability state for the landing page (I14).

A capability is "available" only when the operator provisioned both halves of the SAM/VLM
add-on: SAM is not disabled and a VLM endpoint was explicitly configured. The reference
deployment disables SAM and sets no ``LD_VLM_URL``, so the landing copy must fall back to
"requires operator setup" rather than promising a first-run workflow that cannot run.

Runtime ``sam.loaded`` is deliberately not part of availability: it is only true after the
model has actually loaded, so a correctly provisioned deployment would read as unavailable
until its first segmentation.
"""
import os

from ..config import SAM_ENABLED


def sam_configured() -> bool:
    return SAM_ENABLED != "0"


def vlm_configured() -> bool:
    """Only an explicit ``LD_VLM_URL`` counts; the localhost default is not a provisioned vLLM."""
    return bool(os.environ.get("LD_VLM_URL", "").strip())


def addons_available() -> bool:
    return sam_configured() and vlm_configured()
