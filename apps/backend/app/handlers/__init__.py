"""Worker job handlers, one module per feature.

``app.worker`` composes ``HANDLERS`` from ``MODULES`` below, so a new job kind adds a handler and
one ``HANDLERS`` entry to its own feature module instead of editing the runner.
"""
from . import insights, ops, streams, training, versioning

MODULES = (versioning, training, streams, insights, ops)
