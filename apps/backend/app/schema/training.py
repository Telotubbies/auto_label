"""Column upgrades for the model registry and the job queue."""

TRAINED_MODELS = {
    "family": "VARCHAR(32) DEFAULT 'ultralytics'", "variant": "VARCHAR(64) DEFAULT ''",
    "license": "VARCHAR(64) DEFAULT 'AGPL-3.0'", "runtime_refs": "JSON"}
JOBS = {"executor": "VARCHAR(8) DEFAULT ''"}
