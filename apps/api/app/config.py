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
                                   "insights_images,insights_leakage,insights_embedding").split(",") if k]
if "connector_sync" not in LOCAL_JOB_KINDS:
    LOCAL_JOB_KINDS.append("connector_sync")      # CPU/network job: never leave it unclaimed by every process
if "retention" not in LOCAL_JOB_KINDS:
    LOCAL_JOB_KINDS.append("retention")            # PDPA deletion never waits on a GPU host
REMOTE_JOB_KINDS = ("train", "autolabel")
WORKER_TOKEN = _env("LD_WORKER_TOKEN")                        # shared secret for `labeldesk-worker`

# ML integration — all optional; features degrade with a clear error when missing
SAM_ROOT = Path(_env("LD_SAM_ROOT", str(REPO_ROOT / "sam3_auto_label")))
SAM_ENABLED = _env("LD_SAM_ENABLED", "auto")                  # auto | 1 | 0
PRETRAINED_DIR = Path(_env("LD_PRETRAINED_DIR", str(REPO_ROOT / "yolo26_ppe" / "models" / "pretrained")))
TRAIN_DEVICE = _env("LD_TRAIN_DEVICE", "")                    # "" = ultralytics auto, "cpu", "0"

VLM_URL = _env("LD_VLM_URL", "http://localhost:8000/v1").rstrip("/")
VLM_MODEL = _env("LD_VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct-AWQ")

# Plans — limits enforced server-side; billing integration is out of scope
PLANS = {
    "free":       {"label": "Free",       "projects": 3,   "images": 10_000,    "seats": 3,   "credits": 30},
    "pro":        {"label": "Pro",        "projects": 50,  "images": 250_000,   "seats": 20,  "credits": 500},
    "enterprise": {"label": "Enterprise", "projects": 10_000, "images": 10_000_000, "seats": 10_000, "credits": 100_000},
}
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
