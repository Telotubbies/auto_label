"""Runtime settings — everything comes from env vars so the same image runs dev and prod."""
import os
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]          # auto_label/
API_ROOT = Path(__file__).resolve().parents[1]           # apps/api/


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


DATA_DIR = Path(_env("LD_DATA_DIR", str(API_ROOT / "data"))).resolve()
DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'labeldesk.db').as_posix()}")
PUBLIC_URL = _env("LD_PUBLIC_URL", "http://localhost:5173").rstrip("/")
CORS_ORIGINS = [o for o in _env("LD_CORS_ORIGINS", "*").split(",") if o]
SIGNUP_ENABLED = _env("LD_SIGNUP_ENABLED", "1") == "1"
EMBEDDED_WORKER = _env("LD_EMBEDDED_WORKER", "1") == "1"     # run jobs inside the api process
SEED_DEMO = _env("LD_SEED_DEMO", "1") == "1"
# job kinds the in-process worker runs; drop train/autolabel when GPU jobs go to remote workers
LOCAL_JOB_KINDS = [k for k in _env("LD_LOCAL_JOBS",
                                   "version,export,export_engine,train,autolabel,health,connector_sync,retention,"
                                   "extract_frames,track_forward,drift,active_learning,"
                                   "insights_images,insights_leakage,insights_embedding").split(",") if k]
for _kind in ("connector_sync", "retention", "extract_frames", "track_forward"):
    if _kind not in LOCAL_JOB_KINDS:
        LOCAL_JOB_KINDS.append(_kind)     # CPU/network/SAM work: never leave it unclaimed by every process
REMOTE_JOB_KINDS = ("train", "autolabel")
WORKER_TOKEN = _env("LD_WORKER_TOKEN")                        # shared secret for `labeldesk-worker`


def runs_locally(kind: str) -> bool:
    """True when *this* process executes ``kind``.

    ``LOCAL_JOB_KINDS`` only says what the embedded worker may run; a process with
    ``LD_EMBEDDED_WORKER=0`` runs nothing, even though the default list still names train.
    Remote-worker restrictions key off this answer, never off the list alone.
    """
    return EMBEDDED_WORKER and kind in LOCAL_JOB_KINDS

# ML integration — all optional; features degrade with a clear error when missing
SAM_ROOT = Path(_env("LD_SAM_ROOT", str(REPO_ROOT / "sam3_auto_label")))
SAM_ENABLED = _env("LD_SAM_ENABLED", "auto")                  # auto | 1 | 0
PRETRAINED_DIR = Path(_env("LD_PRETRAINED_DIR", str(REPO_ROOT / "yolo26_ppe" / "models" / "pretrained")))
TRAIN_DEVICE = _env("LD_TRAIN_DEVICE", "")                    # "" = ultralytics auto, "cpu", "0"

VLM_URL = _env("LD_VLM_URL", "http://localhost:8000/v1").rstrip("/")
VLM_MODEL = _env("LD_VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct-AWQ")

GB = 1024 ** 3
# Plans — limits enforced server-side; billing integration is out of scope.
# gpu_seconds / stream_hours / ai_calls are monthly; storage_bytes is current usage.
PLANS = {
    "free":       {"label": "Free",       "projects": 3,   "images": 10_000,    "seats": 3,   "credits": 30,
                   "gpu_seconds": 3_600, "stream_hours": 20, "ai_calls": 2_000, "storage_bytes": 5 * GB},
    "pro":        {"label": "Pro",        "projects": 50,  "images": 250_000,   "seats": 20,  "credits": 500,
                   "gpu_seconds": 36_000, "stream_hours": 200, "ai_calls": 20_000, "storage_bytes": 50 * GB},
    "enterprise": {"label": "Enterprise", "projects": 10_000, "images": 10_000_000, "seats": 10_000, "credits": 100_000,
                   "gpu_seconds": 360_000, "stream_hours": 2_000, "ai_calls": 200_000, "storage_bytes": 500 * GB},
}
# Automatic active-learning sampling: per-project daily cap and the uncertainty band (spec 3.3).
AL_DAILY_CAP = int(_env("LD_AL_DAILY_CAP", "25"))
AL_BAND = (0.3, 0.5)
# Drift monitor: two-sample MMD p-value below this raises the alert.
DRIFT_P = float(_env("LD_DRIFT_P", "0.05"))
DRIFT_MAX_SAMPLES = int(_env("LD_DRIFT_MAX_SAMPLES", "500"))
DRIFT_MIN_SAMPLES = int(_env("LD_DRIFT_MIN_SAMPLES", "12"))
# credits charged per action (mirrors Roboflow's credit-metered model)
CREDIT_COST = {"train": 3, "autolabel_image": 0.01, "infer": 0.001, "version": 0.5}

DATA_DIR.mkdir(parents=True, exist_ok=True)


def _secret() -> str:
    """LD_SECRET, else a random key persisted in DATA_DIR so restarts don't log everyone out."""
    s = _env("LD_SECRET") or _env("AL_SECRET")
    if s:
        if len(s) < 32:
            raise RuntimeError("LD_SECRET must be at least 32 characters (openssl rand -hex 32)")
        return s
    f = DATA_DIR / ".secret"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip()


SECRET = _secret()
SECRET_OLD = _env("LD_SECRET_OLD")           # comma-separated previous secrets, for rotation of encrypted rows
MAX_UPLOAD_MB = int(_env("LD_MAX_UPLOAD_MB", "1024"))        # per upload request
RETENTION_CHECK_S = int(_env("LD_RETENTION_CHECK_S", "3600"))  # how often the worker looks for due cleanup
RETENTION_PRESETS = (7, 30, 90, 180, 365)                    # choices offered by the privacy page
WORKER_STALE_S = int(_env("LD_WORKER_STALE_S", "45"))        # a heartbeat older than this shows offline
if WORKER_TOKEN and len(WORKER_TOKEN) < 24:
    raise RuntimeError("LD_WORKER_TOKEN must be at least 24 characters")
