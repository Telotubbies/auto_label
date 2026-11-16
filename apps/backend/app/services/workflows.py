"""No-code workflow definitions: canonical block configs, versioned saves, restore.

A workflow is an ordered list of blocks. This module owns the *definition* half (validation and
versioning); execution lives in ``services/workflow_runner.py``.
"""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import ADAPTERS, parse_ref
from ..models import Project, TrainedModel, Workflow, WorkflowVersion, now

MAX_BLOCKS = 12
BLOCK_TYPES = ("model", "filter", "crop", "ocr", "rule", "sink")
RULE_KINDS = ("count", "zone")
SINK_KINDS = ("response", "annotations")
RULE_OPS = (">=", ">", "<=", "<", "==")
DEFAULT_OCR_PROMPT = "Read all text in the image and return it verbatim."


def _fail(index: int, message: str) -> None:
    raise ValueError(f"block {index + 1}: {message}")


def _number(value: Any, index: int, name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(index, f"{name} must be a number")
    if not lo <= value <= hi:
        _fail(index, f"{name} must be between {lo} and {hi}")
    return float(value)


def _names(value: Any, index: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        _fail(index, "classes must be a list of class names")
    return [v.strip() for v in value]


def _model_ref(value: Any, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(index, "model_ref is required")
    ref = value.strip()
    try:
        parse_ref(ref)
    except ValueError as e:
        _fail(index, str(e))
    return ref


def _points(value: Any, index: int) -> list[float]:
    if not isinstance(value, list) or len(value) < 6 or len(value) % 2:
        _fail(index, "points must be an even list of at least 3 x/y pairs")
    out = []
    for v in value:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            _fail(index, "points must be normalized numbers between 0 and 1")
        out.append(float(v))
    return out


def _block(index: int, block: Any) -> dict:
    if not isinstance(block, dict):
        _fail(index, "must be an object")
    kind = block.get("type")
    if kind not in BLOCK_TYPES:
        _fail(index, f"unknown block type {kind!r}")
    if kind in ("model", "ocr"):
        out = {"type": kind, "model_ref": _model_ref(block.get("model_ref"), index)}
        if kind == "ocr":
            prompt = block.get("prompt") or DEFAULT_OCR_PROMPT
            if not isinstance(prompt, str) or not prompt.strip():
                _fail(index, "prompt must be text")
            out["prompt"] = prompt.strip()
        else:
            conf = block.get("conf")
            out["conf"] = None if conf is None else _number(conf, index, "conf", 0, 1)
            out["classes"] = _names(block.get("classes"), index)
        return out
    if kind == "filter":
        return {"type": "filter", "classes": _names(block.get("classes"), index),
                "min_conf": _number(block.get("min_conf") or 0, index, "min_conf", 0, 1)}
    if kind == "crop":
        return {"type": "crop", "expand": _number(block.get("expand") or 0, index, "expand", 0, 1)}
    if kind == "rule":
        rule_kind = block.get("kind")
        if rule_kind not in RULE_KINDS:
            _fail(index, "rule kind must be count or zone")
        cls = block.get("class")
        if not isinstance(cls, str) or not cls.strip():
            _fail(index, "rule class is required")
        out = {"type": "rule", "kind": rule_kind, "class": cls.strip()}
        if rule_kind == "count":
            k = block.get("k", 1)
            if isinstance(k, bool) or not isinstance(k, int) or not 0 <= k <= 100_000:
                _fail(index, "k must be an integer between 0 and 100000")
            op = block.get("op") or ">="
            if op not in RULE_OPS:
                _fail(index, f"op must be one of {', '.join(RULE_OPS)}")
            out.update(k=k, op=op, for_s=_number(block.get("for_s") or 0, index, "for_s", 0, 86_400))
        else:
            out["points"] = _points(block.get("points"), index)
        return out
    sink = block.get("kind")
    if sink not in SINK_KINDS:
        _fail(index, f"sink kind must be one of {', '.join(SINK_KINDS)}")
    return {"type": "sink", "kind": sink}


def validate_blocks(blocks: Any) -> list[dict]:
    """Return the canonical config or raise ValueError with a block-numbered message."""
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("a workflow needs at least one block")
    if len(blocks) > MAX_BLOCKS:
        raise ValueError(f"a workflow can hold at most {MAX_BLOCKS} blocks")
    out = [_block(i, b) for i, b in enumerate(blocks)]
    if not any(b["type"] in ("model", "ocr") for b in out):
        raise ValueError("a workflow needs a model or OCR block")
    sinks = [i for i, b in enumerate(out) if b["type"] == "sink"]
    if len(sinks) != 1:
        raise ValueError("a workflow needs exactly one sink block")
    if sinks[0] != len(out) - 1:
        raise ValueError("the sink block must be last")
    return out


def _check_models(db: Session, project: Project, blocks: list[dict]) -> None:
    """A saved ref must resolve now: a known adapter family or a ready trained model of this workspace.

    Without this the user only learns at the first run, and a foreign id would leak as "unknown".
    """
    for i, block in enumerate(blocks):
        if block["type"] not in ("model", "ocr"):
            continue
        family, rest = parse_ref(block["model_ref"])
        if family == "trained":
            model = db.get(TrainedModel, rest)
            if model is None or model.workspace_id != project.workspace_id or model.status != "ready":
                _fail(i, f"unknown trained model {rest!r}")
        elif family not in ADAPTERS:
            _fail(i, f"no adapter for family {family!r}")


def _name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")
    name = name.strip()
    if len(name) > 120:
        raise ValueError("name must be 120 characters or fewer")
    return name


def _duplicate(db: Session, project_id: str, name: str, skip_id: str | None = None) -> bool:
    row = db.scalar(select(Workflow.id).where(Workflow.project_id == project_id, Workflow.name == name))
    return row is not None and row != skip_id


def _snapshot(db: Session, wf: Workflow, note: str = "") -> None:
    db.add(WorkflowVersion(workflow_id=wf.id, number=wf.version, name=wf.name,
                           blocks=copy.deepcopy(wf.blocks), note=note, created_by=wf.created_by))


def out(wf: Workflow) -> dict:
    return {"id": wf.id, "name": wf.name, "version": wf.version, "blocks": wf.blocks,
            "created_by": wf.created_by, "created": wf.created, "updated": wf.updated}


def version_out(v: WorkflowVersion) -> dict:
    return {"id": v.id, "number": v.number, "name": v.name, "blocks": v.blocks,
            "note": v.note, "created_by": v.created_by, "created": v.created}


def create(db: Session, project: Project, name: str, blocks: Any, user_id: str | None) -> Workflow:
    name = _name(name)
    canonical = validate_blocks(blocks)
    _check_models(db, project, canonical)
    if _duplicate(db, project.id, name):
        raise ValueError("a workflow with this name already exists")
    wf = Workflow(workspace_id=project.workspace_id, project_id=project.id, name=name,
                  blocks=canonical, version=1, created_by=user_id)
    db.add(wf)
    db.flush()
    _snapshot(db, wf, "created")
    db.commit()
    db.refresh(wf)
    return wf


def update(db: Session, wf: Workflow, name: str | None, blocks: Any, user_id: str | None) -> Workflow:
    blocks_changed = False
    if name is not None:
        name = _name(name)
        if name != wf.name and _duplicate(db, wf.project_id, name, wf.id):
            raise ValueError("a workflow with this name already exists")
        if name != wf.name:
            wf.name = name
    if blocks is not None:
        canonical = validate_blocks(blocks)
        if canonical != wf.blocks:
            _check_models(db, db.get(Project, wf.project_id), canonical)
            wf.blocks, blocks_changed = canonical, True
    if blocks_changed:
        wf.version += 1
        wf.updated = now()
        _snapshot(db, wf, "edited")
    else:
        wf.updated = now()
    db.commit()
    db.refresh(wf)
    return wf


def restore(db: Session, wf: Workflow, number: int, user_id: str | None) -> Workflow:
    snap = db.scalar(select(WorkflowVersion).where(WorkflowVersion.workflow_id == wf.id,
                                                   WorkflowVersion.number == number))
    if snap is None:
        raise ValueError(f"version {number} does not exist")
    wf.blocks = copy.deepcopy(snap.blocks)
    wf.version += 1
    wf.updated = now()
    _snapshot(db, wf, f"restored from v{number}")
    db.commit()
    db.refresh(wf)
    return wf


def versions(db: Session, wf: Workflow) -> list[WorkflowVersion]:
    return list(db.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_id == wf.id)
                           .order_by(WorkflowVersion.number.desc())))


def list_for_project(db: Session, project: Project) -> list[Workflow]:
    return list(db.scalars(select(Workflow).where(Workflow.project_id == project.id)
                           .order_by(Workflow.updated.desc())))


def get(db: Session, project: Project, workflow_id: str) -> Workflow | None:
    """Project-scoped lookup: another tenant's id reads as missing, never as forbidden."""
    return db.scalar(select(Workflow).where(Workflow.id == workflow_id, Workflow.project_id == project.id))
