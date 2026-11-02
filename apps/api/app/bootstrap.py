"""Schema creation + first-run demo seed."""
import logging
import os
import time
from pathlib import Path

from sqlalchemy import inspect, select, update

from .config import REPO_ROOT, SEED_DEMO
from .db import Base, SessionLocal, engine
from .models import User

log = logging.getLogger("labeldesk")
DEMO_EMAIL, DEMO_PW = "demo@labeldesk.dev", "demo1234"


def init_db():
    Base.metadata.create_all(engine)
    ensure_columns(engine, "trained_models", {
        "family": "VARCHAR(32) DEFAULT 'ultralytics'", "variant": "VARCHAR(64) DEFAULT ''",
        "license": "VARCHAR(64) DEFAULT 'AGPL-3.0'", "runtime_refs": "JSON"})
    ensure_columns(engine, "api_keys", {"scopes": "JSON", "publishable": "BOOLEAN DEFAULT FALSE"})
    ensure_columns(engine, "connectors", {"last_sync": "FLOAT", "last_status": "VARCHAR(16) DEFAULT ''"})
    ensure_columns(engine, "users", {
        "email_verified": "FLOAT", "totp_secret": "VARCHAR(255)", "mfa_enabled": "BOOLEAN DEFAULT FALSE",
        "recovery_codes": "JSON", "totp_last_step": "INTEGER DEFAULT 0",
        "platform_admin": "BOOLEAN DEFAULT FALSE"})
    ensure_columns(engine, "workspaces", {"require_mfa": "BOOLEAN DEFAULT FALSE",
                                          "data_region": "VARCHAR(16) DEFAULT 'th'"})
    ensure_columns(engine, "projects", {"retention_days": "INTEGER", "face_blur": "BOOLEAN DEFAULT TRUE",
                                        "biometrics": "BOOLEAN DEFAULT FALSE", "legal_basis": "TEXT DEFAULT ''"})
    ensure_columns(engine, "members", {"custom_role_id": "VARCHAR(32)"})
    ensure_columns(engine, "project_members", {"custom_role_id": "VARCHAR(32)"})
    ensure_columns(engine, "refresh_tokens", {
        "created": "FLOAT DEFAULT 0", "last_seen": "FLOAT DEFAULT 0",
        "ip": "VARCHAR(64) DEFAULT ''", "user_agent": "VARCHAR(255) DEFAULT ''"})
    _widen_totp_secret()
    _backfill_sessions()
    from .services.secretbox import migrate as _encrypt_secrets
    # One-time upgrade of connector/webhook secrets, legacy TOTP seeds, and any key rotation.
    _encrypt_secrets()
    _seal_stream_sources()
    _backfill_image_classes()
    if SEED_DEMO:
        seed()


def _backfill_sessions():
    """Sessions created before Task 21 have no metadata; give them a real timestamp instead of 1970."""
    from .models import RefreshToken
    with SessionLocal() as db:
        db.execute(update(RefreshToken).where(RefreshToken.created == 0)
                   .values(created=time.time(), last_seen=time.time()))
        db.commit()


def _seal_stream_sources():
    """Encrypt RTSP credentials already stored by a Task-10b build (no-op until Stream exists)."""
    from .streams.creds import seal_existing
    with SessionLocal() as db:
        changed = seal_existing(db)
    if changed:
        log.info("encrypted %s stream source(s) at rest", changed)


def _widen_totp_secret():
    """Ciphertext is longer than the old 64-char plaintext column. SQLite ignores the length."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as cn:
            cn.exec_driver_sql("ALTER TABLE users ALTER COLUMN totp_secret TYPE VARCHAR(255)")


def ensure_columns(eng, table: str, cols: dict[str, str]) -> None:
    """Idempotent ALTER TABLE ... ADD COLUMN; cols maps name -> DDL fragment (type + default)."""
    have = {c["name"] for c in inspect(eng).get_columns(table)}
    with eng.begin() as cn:
        for name, ddl in cols.items():
            if name not in have:
                cn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')


def seed():
    from .deps import Ctx
    from .routers.auth import create_workspace
    from .routers.images import ingest
    from .models import LabelClass, Member, Project
    from .security import hash_password

    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            return
        admin = User(email=DEMO_EMAIL, name="Demo Admin", pw_hash=hash_password(DEMO_PW), email_verified=time.time())
        labeler = User(email="labeler@labeldesk.dev", name="Lee Labeler", pw_hash=hash_password(DEMO_PW),
                       email_verified=time.time())
        reviewer = User(email="reviewer@labeldesk.dev", name="Rae Reviewer", pw_hash=hash_password(DEMO_PW),
                        email_verified=time.time())
        db.add_all([admin, labeler, reviewer]); db.flush()
        ws = create_workspace(db, admin, "LabelDesk Demo")
        db.add_all([Member(workspace_id=ws.id, user_id=labeler.id, role="annotator"),
                    Member(workspace_id=ws.id, user_id=reviewer.id, role="reviewer")])
        p = Project(workspace_id=ws.id, slug="ppe-detection", name="PPE Detection", type="object-detection",
                    annotation_group="ppe", settings={})
        db.add(p); db.flush()
        for name, color in (("person", "#8b5cf6"), ("helmet", "#22c55e"), ("closed footwear", "#3b82f6"), ("harness", "#f97316")):
            db.add(LabelClass(project_id=p.id, name=name, color=color))
        db.commit()

        # sample images + SAM ground truth from the repo's PPE data, when present
        src = Path(os.environ.get("LD_SEED_IMAGES", REPO_ROOT / "data" / "raw" / "custom_capture"))
        ann = src.parent.parent / "sam_outputs_ground_truth" / src.name / "coco"
        files = []
        for f in sorted(src.glob("*.jpg"))[:40] if src.exists() else []:
            files.append((f.name, f.read_bytes()))
            if (ann / f"{f.stem}.json").exists():
                files.append((f"{f.stem}.json", (ann / f"{f.stem}.json").read_bytes()))
        if files:
            ctx = Ctx(user=admin, ws=ws, role="admin", db=db, project=p)
            res = ingest(db, ctx, files, "Demo seed", "auto", [], to_dataset=False, user_id=admin.id)
            log.info("seeded demo project with %s images", res["uploaded"])
        log.info("demo login: %s / %s", DEMO_EMAIL, DEMO_PW)


def _backfill_image_classes():
    """DBs created before the image_classes index existed: build it once."""
    from .models import Image, ImageClass, set_annotations
    with SessionLocal() as db:
        if db.scalar(select(ImageClass.image_id).limit(1)) or not db.scalar(select(Image.id).where(Image.n_annotations > 0).limit(1)):
            return
        for img in db.scalars(select(Image).where(Image.n_annotations > 0, Image.deleted_at.is_(None))):
            updated = img.updated
            set_annotations(db, img, img.annotations or [])
            img.updated = updated
        db.commit()
        log.info("backfilled image_classes index")
