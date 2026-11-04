"""Shared schema pieces: id generators and the enum-like tuples the routers validate against."""
import secrets
import time

# Legacy workspace roles stay valid on Member rows (mapped by app/rbac.py); new workspaces use the
# four-role model. Project roles live on ProjectMember and never replace the workspace role.
ROLES = ("admin", "reviewer", "annotator")
WORKSPACE_ROLES = ("owner", "admin", "billing", "member")
PROJECT_ROLES = ("manager", "reviewer", "labeler", "viewer")
PROJECT_TYPES = ("object-detection", "instance-segmentation", "classification", "keypoint-detection")
SPLITS = ("train", "valid", "test")
STATUSES = ("unassigned", "annotating", "review", "done")
API_SCOPES = ("read", "upload", "train", "infer")
CONNECTOR_KINDS = ("s3", "gcs", "azure")
WEBHOOK_EVENTS = ("job.done", "model.ready", "stream.event")
DATA_REGIONS = ("th", "sg", "us")
DEPLOY_ALIASES = ("production", "staging")
# Metering keys. GPU time, stream time and AI calls are monthly allowances; storage is current bytes.
METRICS = ("gpu_seconds", "stream_hours", "ai_calls", "storage_bytes")


def new_id() -> str:
    return secrets.token_hex(8)


def now() -> float:
    return time.time()
