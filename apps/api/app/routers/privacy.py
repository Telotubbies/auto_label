"""PDPA: retention, face blur, residency and the Data Processing Agreement (LabelDesk = processor)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..config import RETENTION_PRESETS
from ..deps import Ctx, audit, project_ctx, ws_ctx
from ..models import DATA_REGIONS, Image, Job, Project, User, now
from ..services import retention

router = APIRouter(prefix="/api/ws/{ws}", tags=["privacy"])

REGION_LABELS = {"th": "Thailand", "sg": "Singapore", "us": "United States"}
DPA_VERSION = "2026-11-01"
MAX_RETENTION_DAYS = 3650
MIN_LEGAL_BASIS = 10
MAX_LEGAL_BASIS = 4000


class ResidencyIn(BaseModel):
    data_region: str


class PrivacyPatch(BaseModel):
    retention_days: int | None = None
    face_blur: bool | None = None
    biometrics: bool | None = None
    legal_basis: str | None = None


def _label(region: str) -> str:
    return REGION_LABELS.get(region, region)


def _live_projects(c: Ctx) -> list[Project]:
    return list(
        c.db.scalars(
            select(Project)
            .where(Project.workspace_id == c.ws.id, Project.deleted_at.is_(None))
            .order_by(Project.created)
        )
    )


def _cutoff(days: int | None) -> float | None:
    return now() - days * retention.DAY if days and days > 0 else None


def _summary(c: Ctx, project: Project) -> dict:
    cutoff = _cutoff(project.retention_days)
    images = 0
    snapshots = 0
    if cutoff is not None:
        images = (
            c.db.scalar(
                select(func.count(Image.id)).where(
                    Image.project_id == project.id, Image.deleted_at.is_(None), Image.created < cutoff
                )
            )
            or 0
        )
        snapshots = retention.count_events(c.db, project.id, cutoff)
    return {
        "retention_days": project.retention_days,
        "face_blur": bool(project.face_blur),
        "biometrics": bool(project.biometrics),
        "legal_basis": project.legal_basis or "",
        "retention_presets": list(RETENTION_PRESETS),
        "images_expiring": int(images),
        "snapshots_expiring": int(snapshots),
        "data_region": c.ws.data_region,
    }


@router.get("/privacy")
def privacy_overview(c: Ctx = Depends(ws_ctx)):
    """Workspace-level privacy posture: residency, per-project settings, retention presets."""
    return {
        "data_region": c.ws.data_region,
        "regions": list(DATA_REGIONS),
        "region_label": _label(c.ws.data_region),
        "projects": [
            {
                "slug": p.slug,
                "name": p.name,
                "retention_days": p.retention_days,
                "face_blur": bool(p.face_blur),
                "biometrics": bool(p.biometrics),
            }
            for p in _live_projects(c)
        ],
        "retention_presets": list(RETENTION_PRESETS),
    }


@router.patch("/privacy")
def set_residency(body: ResidencyIn, c: Ctx = Depends(ws_ctx)):
    """Declare where the workspace's data is processed; owner/admin only."""
    c.perm("workspace.update")
    if body.data_region not in DATA_REGIONS:
        raise HTTPException(400, f"data_region must be one of: {', '.join(DATA_REGIONS)}")
    c.ws.data_region = body.data_region
    audit(c.db, c.ws.id, c.uid, "privacy.residency", body.data_region, data_region=body.data_region)
    c.db.commit()
    return {"data_region": c.ws.data_region, "region_label": _label(c.ws.data_region)}


@router.get("/projects/{project}/privacy")
def project_privacy(c: Ctx = Depends(project_ctx)):
    """Per-project retention, anonymisation and how much would be deleted on the next run."""
    return _summary(c, c.project)


@router.patch("/projects/{project}/privacy")
def set_project_privacy(body: PrivacyPatch, c: Ctx = Depends(project_ctx)):
    """Update retention/face blur/biometrics; enabling biometrics demands a documented legal basis."""
    c.perm("project.privacy")
    project, supplied = c.project, body.model_fields_set
    changed: dict = {}

    if "retention_days" in supplied:
        days = body.retention_days
        if days is not None and not 0 <= days <= MAX_RETENTION_DAYS:
            raise HTTPException(400, f"retention_days must be between 0 and {MAX_RETENTION_DAYS} (0 = keep)")
        project.retention_days = days or None
        changed["retention_days"] = project.retention_days

    if "legal_basis" in supplied:
        basis = (body.legal_basis or "").strip()
        if len(basis) > MAX_LEGAL_BASIS:
            raise HTTPException(400, f"legal_basis is limited to {MAX_LEGAL_BASIS} characters")
        project.legal_basis = basis
        changed["legal_basis"] = basis[:200]

    if "face_blur" in supplied:
        project.face_blur = bool(body.face_blur)
        changed["face_blur"] = project.face_blur

    if "biometrics" in supplied:
        if body.biometrics and len((project.legal_basis or "").strip()) < MIN_LEGAL_BASIS:
            raise HTTPException(400, "biometrics require a documented legal basis (PDPA s.26)")
        project.biometrics = bool(body.biometrics)
        changed["biometrics"] = project.biometrics

    if changed:
        project.updated = now()
        audit(c.db, c.ws.id, c.uid, "privacy.update", project.name, **changed)
    c.db.commit()
    return _summary(c, c.project)


@router.post("/projects/{project}/privacy/retention/run")
def run_retention_now(c: Ctx = Depends(project_ctx)):
    """Queue an immediate cleanup for this project; the worker executes it asynchronously."""
    c.perm("project.privacy")
    project = c.project
    job = Job(
        workspace_id=c.ws.id,
        project_id=project.id,
        kind="retention",
        params={"project_id": project.id},
        created_by=c.uid,
    )
    c.db.add(job)
    audit(c.db, c.ws.id, c.uid, "retention.request", project.name, job=job.id)
    c.db.commit()
    return {"job_id": job.id}


def _retention_line(project: Project) -> str:
    if project.retention_days and project.retention_days > 0:
        return f"{project.retention_days} days after capture (automatic deletion)"
    return "keep until deletion"


def _dpa_markdown(c: Ctx, projects: list[Project]) -> str:
    owner = c.db.get(User, c.ws.owner_id)
    contact = owner.email if owner else ""
    retention_text = (
        "\n".join(f"- **{p.name}** (`{p.slug}`): {_retention_line(p)}" for p in projects) or "- No projects yet."
    )
    return f"""# Data Processing Agreement

Version {DPA_VERSION} · Region: {_label(c.ws.data_region)} · Last updated: {DPA_VERSION}

## 1. Parties

- **Controller:** {c.ws.name} ("the Customer"), contact: {contact}
- **Processor:** LabelDesk ("the Processor"), acting on the Customer's documented instructions.

## 2. Scope and instructions

The Processor processes personal data only to provide the labelling, training, playground and CCTV
analytics features the Controller enables. The Controller decides which cameras, projects and roles
exist; the Processor does not determine the purposes of processing.

## 3. Categories of data and data subjects

- CCTV footage: images and video frames, timestamps, camera metadata (stream identifiers and URLs)
  and annotations created by the Controller's staff or models.
- Faces visible in footage are **personal data**; any biometric template or face-recognition feature
  is **sensitive personal data** under PDPA s.26 and is off unless explicitly enabled.
- Data subjects: employees, visitors and other persons captured by the Controller's cameras.

## 4. Purpose limitation

Data is used solely for labelling, model training, evaluation and event review requested by the
Controller. No advertising, profiling, resale or unrelated secondary use is permitted.

## 5. Retention

Each project follows the Controller's retention setting; expired frames, snapshots and stream
events are deleted by a scheduled job and by manual runs:

{retention_text}

Deleting a frame also invalidates cached dataset exports: export archives built from a dataset
version that contains a deleted frame are removed, while the dataset version snapshot itself is
removed only when the Controller deletes that version.

## 6. Sub-processors

Model inference (LLM and vision) runs on the Controller's own GPU host. The Controller may connect a
remote GPU worker (for example a cloud notebook); that worker is a sub-processor whose location the
Controller records before connecting it. No other third-party transfer is used by default, and adding
a new sub-processor requires the Controller's prior consent.

## 7. Security measures

- Encryption at rest for credentials and secrets (camera URLs, API keys, TOTP seeds).
- Role-based access control at workspace and project level, least privilege by default.
- An audit log records administrative actions and every view of stream footage served by the stream manager.
- Face blur is on by default for uploaded video frames before they enter a dataset; stream coverage
  is added with the stream manager.
- Multi-factor authentication is available and can be enforced per workspace.

## 8. Data subject rights and assistance

The Processor assists the Controller in answering access, rectification, erasure, restriction and
objection requests, and in any PDPA s.30–36 request, within the statutory timelines.

## 9. Breach notification

The Processor notifies the Controller without undue delay and **within 72 hours** of becoming aware
of a personal-data breach, with the known facts, affected data and containment measures.

## 10. Cross-border transfer

Data is declared in the **{_label(c.ws.data_region)}** region. A remote GPU worker must be in the
same region, or the Controller records a lawful transfer basis under PDPA s.28–29 before sending data
to it. Moving data to another region requires the Controller's instruction and that basis.

## 11. Deletion and return on termination

On termination the Processor returns the Controller's data on request and deletes it, including
derived snapshots and events, within 30 days, except where law requires retention.

## 12. Audit rights

The Controller may request evidence of the security measures above and reasonable audit access,
subject to confidentiality and the Processor's operational security.

## 13. Contact

{c.ws.name} — owner: {contact}. Processor privacy contact: privacy@labeldesk.dev.
"""


@router.get("/dpa")
def dpa(project: str = "", c: Ctx = Depends(ws_ctx)):
    """A filled-in Data Processing Agreement for this workspace, optionally scoped to one project."""
    projects = _live_projects(c)
    if project:
        projects = [p for p in projects if p.slug == project]
        if not projects:
            raise HTTPException(404, "project not found")
    return {
        "workspace": c.ws.name,
        "version": DPA_VERSION,
        "updated": DPA_VERSION,
        "region": c.ws.data_region,
        "markdown": _dpa_markdown(c, projects),
    }
