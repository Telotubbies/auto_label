"""Per-domain schema upgrades.

``STEPS`` is the order an existing database has always passed its ``ADD COLUMN`` statements in.
The blocks are independent and idempotent, so only the phase boundary in ``bootstrap._init_db``
matters: every column exists before the widen, encrypt and backfill phases run.
"""
from . import dataset, identity, streams, training
from .columns import ensure_columns

STEPS = (
    ("trained_models", training.TRAINED_MODELS),
    ("api_keys", identity.API_KEYS),
    ("connectors", identity.CONNECTORS),
    ("users", identity.USERS),
    ("workspaces", identity.WORKSPACES),
    ("projects", dataset.PROJECTS),
    ("members", identity.MEMBERS),
    ("project_members", identity.PROJECT_MEMBERS),
    ("classes", dataset.CLASSES),
    ("images", dataset.IMAGES),
    ("jobs", training.JOBS),
    ("label_events", dataset.LABEL_EVENTS),
    ("consensus_jobs", dataset.CONSENSUS_JOBS),
    ("refresh_tokens", identity.REFRESH_TOKENS),
    ("stream_events", streams.STREAM_EVENTS),
)

DOMAIN_MODULES = (identity, dataset, training, streams)


def apply(engine) -> None:
    for table, cols in STEPS:
        ensure_columns(engine, table, cols)
