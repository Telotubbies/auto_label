"""Schema creation + first-run demo seed."""
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import exists, func, inspect, select, update
from sqlalchemy.exc import OperationalError

from .config import DATA_DIR, ENVIRONMENT, REPO_ROOT, SEED_DEMO
from .db import Base, SessionLocal, engine
from .models import Image, ImageClass, Project, UsageEvent, User, Workspace

log = logging.getLogger("labeldesk")
DEMO_EMAIL, DEMO_PW = "demo@labeldesk.dev", "demo1234"
_LOCK_ID = 0x1ABE1DE5                 # one advisory-lock number for the whole schema upgrade


@contextmanager
def _schema_lock():
    """Run the upgrade once across processes: advisory lock on Postgres, file lock on SQLite."""
    if engine.dialect.name == "postgresql":
        cn = engine.connect()
        try:
            cn.exec_driver_sql(f"SELECT pg_advisory_lock({_LOCK_ID})")
            yield
        finally:
            cn.exec_driver_sql(f"SELECT pg_advisory_unlock({_LOCK_ID})")
            cn.close()
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = open(DATA_DIR / ".schema.lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            while True:                            # LK_LOCK gives up after ~10 s; keep waiting
                try:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def init_db():
    with _schema_lock():
        _init_db()


def _init_db():
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
                                          "data_region": "VARCHAR(16) DEFAULT 'th'",
                                          "quotas": "JSON"})
    ensure_columns(engine, "projects", {"retention_days": "INTEGER", "face_blur": "BOOLEAN DEFAULT TRUE",
                                        "biometrics": "BOOLEAN DEFAULT FALSE", "legal_basis": "TEXT DEFAULT ''"})
    ensure_columns(engine, "members", {"custom_role_id": "VARCHAR(32)"})
    ensure_columns(engine, "project_members", {"custom_role_id": "VARCHAR(32)"})
    ensure_columns(engine, "classes", {"skeleton": "JSON"})
    ensure_columns(engine, "images", {"video_id": "VARCHAR(32)", "frame_index": "INTEGER",
                                      "sharpness": "FLOAT", "luminance": "FLOAT"})
    ensure_columns(engine, "label_events", {"ai_ids": "JSON"})
    ensure_columns(engine, "consensus_jobs", {"image_metrics": "JSON"})
    ensure_columns(engine, "refresh_tokens", {
        "created": "FLOAT DEFAULT 0", "last_seen": "FLOAT DEFAULT 0",
        "ip": "VARCHAR(64) DEFAULT ''", "user_agent": "VARCHAR(255) DEFAULT ''"})
    _widen_totp_secret()
    _widen_text_columns()
    _backfill_sessions()
    from .services.secretbox import migrate as _encrypt_secrets
    # One-time upgrade of connector/webhook secrets, legacy TOTP seeds, and any key rotation.
    _encrypt_secrets()
    _seal_stream_sources()
    ensure_columns(engine, "stream_events", {
        "clean_path": "VARCHAR(1024) DEFAULT ''",
        "rule_index": "INTEGER", "rule_kind": "VARCHAR(16) DEFAULT ''",
        "rule_label": "VARCHAR(255) DEFAULT ''", "classes": "TEXT DEFAULT ''"})
    with engine.begin() as cn:
        cn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_stream_events_stream_ts ON stream_events (stream_id, ts)")
    _backfill_event_fields()
    _backfill_image_classes()
    _backfill_storage()
    if _should_seed():
        seed()
        from .seed_v2 import seed_demo_v2
        seed_demo_v2()


def _should_seed() -> bool:
    """M7: never ship the known demo credentials into production or a live installation."""
    return SEED_DEMO and ENVIRONMENT != "production"


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


def _widen_text_columns():
    """C4: encrypted webhook secrets and long audit targets outgrow their old columns.

    SQLite has no length enforcement; Postgres truncates or rejects. ``ALTER ... TYPE TEXT``
    is idempotent, so an already-widened database is safe.
    """
    if engine.dialect.name == "postgresql":
        with engine.begin() as cn:
            cn.exec_driver_sql("ALTER TABLE webhooks ALTER COLUMN secret TYPE TEXT")
            cn.exec_driver_sql("ALTER TABLE audit ALTER COLUMN target TYPE TEXT")


def _backfill_event_fields() -> None:
    """Events recorded before the SQL-filter fix carry these fields only inside their JSON snapshots."""
    from .models import StreamEvent
    from .streams.event_fields import filter_fields

    with SessionLocal() as db:
        rows = db.scalars(select(StreamEvent).where(StreamEvent.rule_kind == "")).all()
        for ev in rows:
            for name, value in filter_fields(ev.rule or {}, ev.predictions or []).items():
                setattr(ev, name, value)
        db.commit()


def ensure_columns(eng, table: str, cols: dict[str, str]) -> None:
    """Idempotent ALTER TABLE ... ADD COLUMN; cols maps name -> DDL fragment (type + default)."""
    have = {c["name"] for c in inspect(eng).get_columns(table)}
    with eng.begin() as cn:
        for name, ddl in cols.items():
            if name in have:
                continue
            try:
                cn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
            except OperationalError as e:      # a concurrent process won the race after our inspect
                msg = str(e).lower()
                if "duplicate column" not in msg and "already exists" not in msg:
                    raise


def seed():
    from .deps import Ctx
    from .routers.auth import create_workspace
    from .routers.images import ingest
    from .models import LabelClass, Member, Project
    from .security import hash_password

    with SessionLocal() as db:
        # Seed only a pristine database. A demo user check let a restart add known credentials to a
        # live installation that already had real accounts (M7).
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
    """Repair a missing or partial image_classes index; safe to run on every boot (I2).

    Requesting rows ahead of a cursor guarantees progress. A legacy row can hold annotations
    that can never produce an ``ImageClass`` row (``[null]`` or a v1 dict); selecting it again
    by the same predicate would loop forever while holding the schema lock (C1).
    """
    from .models import set_annotations
    cursor = ""
    done = 0
    with SessionLocal() as db:
        while True:
            rows = db.scalars(select(Image).where(
                Image.n_annotations > 0,
                Image.deleted_at.is_(None),
                Image.id > cursor,
                ~exists(select(ImageClass.image_id).where(ImageClass.image_id == Image.id)),
            ).order_by(Image.id).limit(500)).all()
            if not rows:
                break
            cursor = rows[-1].id
            for img in rows:
                updated = img.updated
                set_annotations(db, img, img.annotations or [])
                img.updated = updated
                if any(isinstance(a, dict) and a.get("classId") for a in (img.annotations or [])):
                    done += 1
                else:
                    log.warning("image %s has no annotation with a classId; image_classes stays empty", img.id)
            try:
                db.commit()
            except Exception:                   # another process inserted the same rows first
                db.rollback()
    if done:
        log.info("backfilled image_classes index for %s images", done)


def _backfill_storage():
    """Give every workspace a storage meter from its live images when it has none (I20)."""
    with SessionLocal() as db:
        sums = dict(db.execute(select(Image.project_id, func.sum(Image.size))
                               .where(Image.deleted_at.is_(None)).group_by(Image.project_id)).all())
        projects = db.execute(select(Project.id, Project.workspace_id)).all()
        totals: dict[str, float] = {}
        for pid, ws_id in projects:
            totals[ws_id] = totals.get(ws_id, 0.0) + float(sums.get(pid) or 0)
        for ws in db.scalars(select(Workspace)):
            total = totals.get(ws.id, 0.0)
            if total <= 0:
                continue
            has = db.scalar(select(UsageEvent.id).where(UsageEvent.workspace_id == ws.id,
                                                        UsageEvent.metric == "storage_bytes").limit(1))
            if not has:
                db.add(UsageEvent(workspace_id=ws.id, metric="storage_bytes", quantity=total,
                                  meta={"backfill": True}))
        db.commit()
