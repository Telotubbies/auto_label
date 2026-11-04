"""Denormalised event columns so the timeline endpoint filters and pages in SQL.

The rule snapshot stays the source of truth for display; these fields exist only
for WHERE clauses, and the manager writes both in the same transaction.
"""
from __future__ import annotations

CLASS_SEP = "|"


def class_key(classes: set[str]) -> str:
    """`|person|helmet|`: a delimited token list that both SQLite and Postgres can LIKE."""
    tokens = sorted({str(c).replace(CLASS_SEP, " ").strip() for c in classes if c})
    return CLASS_SEP + CLASS_SEP.join(tokens) + CLASS_SEP if tokens else ""


def filter_fields(rule: dict, predictions: list[dict]) -> dict:
    """Values for `StreamEvent.rule_index / rule_kind / rule_label / classes`."""
    classes = {p.get("class") for p in predictions if isinstance(p, dict) and p.get("class")}
    if rule.get("class"):
        classes.add(rule["class"])
    index = rule.get("index")
    return {
        "rule_index": index if isinstance(index, int) and not isinstance(index, bool) else None,
        "rule_kind": str(rule.get("kind") or "")[:16],
        "rule_label": str(rule.get("label") or rule.get("kind") or "")[:255],
        "classes": class_key(classes),
    }
