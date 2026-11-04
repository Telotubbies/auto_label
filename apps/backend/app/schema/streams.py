"""Column upgrades for live streams and their rule events."""

STREAM_EVENTS = {
    "clean_path": "VARCHAR(1024) DEFAULT ''",
    "rule_index": "INTEGER", "rule_kind": "VARCHAR(16) DEFAULT ''",
    "rule_label": "VARCHAR(255) DEFAULT ''", "classes": "TEXT DEFAULT ''"}
