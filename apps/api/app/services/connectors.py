"""Read-only cloud storage connectors (S3 / GCS / Azure Blob).

Credentials live in Connector.config and never leave the API: public_config() masks them.
The bucket side is strictly read-only — objects are listed and downloaded through
short-lived presigned GET URLs; nothing here writes or deletes remote objects.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, update

from ..db import SessionLocal
from ..deps import Ctx, plan
from ..models import CONNECTOR_KINDS, Connector, Image, Project, Workspace, now
from . import imaging

log = logging.getLogger("labeldesk.connectors")

KIND_LABELS = {"s3": "Amazon S3", "gcs": "Google Cloud Storage", "azure": "Azure Blob Storage"}
SECRET_FIELDS = ("secret_key", "credentials_json", "sas_token", "account_key", "access_key")

URL_TTL_SECONDS = 900                  # presigned GET lifetime (15 min)
MAX_LIST_LIMIT = 1000
MAX_SYNC_LIMIT = 500
MAX_FETCH_BYTES = 64 * 1024 * 1024     # 64 MB per object
FETCH_TIMEOUT = 30.0
SYNC_CHUNK = 25                        # download + ingest in small batches so memory stays bounded


# --- validation / presentation -------------------------------------------------------

def validate(kind: str, config: dict) -> None:
    """Raise ValueError with a readable message when the connector config is unusable."""
    cfg = config if isinstance(config, dict) else {}
    if kind not in CONNECTOR_KINDS:
        raise ValueError(f"unknown connector kind {kind!r} (expected one of: {', '.join(KIND_LABELS)})")
    if kind in ("s3", "gcs"):
        if not str(cfg.get("bucket") or "").strip():
            raise ValueError(f"{kind} connector requires a bucket")
    elif kind == "azure":
        if not str(cfg.get("container") or "").strip():
            raise ValueError("azure connector requires a container")
        if not (str(cfg.get("account_url") or "").strip() or str(cfg.get("account_name") or "").strip()):
            raise ValueError("azure connector requires account_url or account_name")
        sas = str(cfg.get("sas_token") or "").lstrip("?")
        if sas:
            from urllib.parse import parse_qs
            perms = (parse_qs(sas).get("sp") or [""])[0]
            if perms and set(perms) - set("rl"):
                raise ValueError("azure sas_token must be read-only (sp=r or sp=rl)")


def public_config(conn) -> dict:
    """Copy of the stored config with every secret value replaced by '***'."""
    out = dict(conn.config or {})
    for field in SECRET_FIELDS:
        if out.get(field):
            out[field] = "***"
    for field in ("endpoint_url", "account_url"):
        value = str(out.get(field) or "")
        if not value:
            continue
        parts = urlsplit(value)
        if parts.username or parts.password or "sig=" in parts.query:
            port = f":{parts.port}" if parts.port else ""
            out[field] = f"{parts.scheme}://{parts.hostname or ''}{port}{parts.path}"
    return out


# --- SDK helpers ---------------------------------------------------------------------

def _import_boto3():
    try:
        import boto3
    except ImportError:
        raise HTTPException(501, "s3 connector support requires boto3 — install boto3")
    return boto3


def _import_gcs():
    try:
        from google.cloud import storage
    except ImportError:
        raise HTTPException(501, "gcs connector support requires google-cloud-storage — install google-cloud-storage")
    return storage


def _import_azure():
    try:
        from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas
    except ImportError:
        raise HTTPException(501, "azure connector support requires azure-storage-blob — install azure-storage-blob")
    return BlobServiceClient, generate_blob_sas, BlobSasPermissions


def _s3_client(boto3, cfg: dict):
    kw = {"region_name": cfg.get("region") or None, "endpoint_url": cfg.get("endpoint_url") or None}
    if cfg.get("access_key"):
        kw["aws_access_key_id"] = cfg["access_key"]
    if cfg.get("secret_key"):
        kw["aws_secret_access_key"] = cfg["secret_key"]
    return boto3.client("s3", **kw)


def _gcs_client(storage, cfg: dict):
    if cfg.get("credentials_json"):
        return storage.Client.from_service_account_info(json.loads(cfg["credentials_json"]))
    return storage.Client()


def _azure_account_url(cfg: dict) -> str:
    url = str(cfg.get("account_url") or "").strip()
    if url:
        return url
    account = str(cfg.get("account_name") or "").strip()
    return f"https://{account}.blob.core.windows.net"


def _azure_account_name(cfg: dict) -> str:
    name = str(cfg.get("account_name") or "").strip()
    if name:
        return name
    host = urlsplit(_azure_account_url(cfg)).hostname or ""
    return host.split(".")[0]


def _azure_service(BlobServiceClient, cfg: dict):
    return BlobServiceClient(account_url=_azure_account_url(cfg),
                             credential=cfg.get("sas_token") or cfg.get("account_key"))


def _azure_blob_url(cfg: dict, blob, generate_blob_sas=None, permissions=None) -> str:
    """Blob URL + sas_token, or a freshly signed read URL from account_key."""
    base = getattr(blob, "url", "") or ""
    if not base:
        base = (f"{_azure_account_url(cfg).rstrip('/')}/{quote(cfg.get('container') or '')}/"
                f"{quote(blob.name)}")
    base = base.split("?", 1)[0]                 # drop any SAS the SDK already attached: no duplicates
    if cfg.get("sas_token"):
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{str(cfg['sas_token']).lstrip('?')}"
    if cfg.get("account_key") and generate_blob_sas:
        try:
            sas = generate_blob_sas(
                account_name=_azure_account_name(cfg), container_name=cfg.get("container"),
                blob_name=blob.name, account_key=cfg["account_key"],
                permission=permissions.read if permissions else "r",
                expiry=datetime.now(timezone.utc) + timedelta(seconds=URL_TTL_SECONDS))
            return f"{base}?{sas}"
        except Exception:                       # fall back to the plain URL
            log.exception("could not sign azure blob %s", getattr(blob, "name", "?"))
    return base


def _stamp(value):
    if value is None:
        return None
    return value.timestamp() if hasattr(value, "timestamp") else value


def _with_date(obj: dict, value) -> dict:
    stamp = _stamp(value)
    if stamp is not None:
        obj["last_modified"] = stamp
    return obj


# --- listing -------------------------------------------------------------------------

def list_objects(conn, prefix: str = "", limit: int = 100) -> list[dict]:
    """List up to `limit` objects with a read-only presigned GET URL for each."""
    limit = max(1, min(int(limit or 100), MAX_LIST_LIMIT))
    cfg = conn.config or {}
    prefix = prefix or ""

    if conn.kind == "s3":
        boto3 = _import_boto3()
        try:
            client = _s3_client(boto3, cfg)
            resp = client.list_objects_v2(Bucket=cfg["bucket"], Prefix=prefix, MaxKeys=limit)
            return [_with_date({
                "key": o["Key"], "size": int(o.get("Size") or 0),
                "url": client.generate_presigned_url(
                    "get_object", Params={"Bucket": cfg["bucket"], "Key": o["Key"]}, ExpiresIn=URL_TTL_SECONDS),
            }, o.get("LastModified")) for o in (resp.get("Contents") or [])]

        except Exception:
            log.exception("s3 connector listing failed for %s", conn.id)
            raise HTTPException(502, "connector listing failed")

    if conn.kind == "gcs":
        storage = _import_gcs()
        try:
            bucket = _gcs_client(storage, cfg).bucket(cfg["bucket"])
            return [_with_date({
                "key": blob.name, "size": int(blob.size or 0),
                "url": blob.generate_signed_url(version="v4", expiration=timedelta(seconds=URL_TTL_SECONDS),
                                                method="GET"),
            }, getattr(blob, "updated", None)) for blob in bucket.list_blobs(prefix=prefix, max_results=limit)]

        except Exception:
            log.exception("gcs connector listing failed for %s", conn.id)
            raise HTTPException(502, "connector listing failed")

    if conn.kind == "azure":
        BlobServiceClient, generate_blob_sas, permissions = _import_azure()
        try:
            container = _azure_service(BlobServiceClient, cfg).get_container_client(cfg["container"])
            out = []
            for blob in container.list_blobs(name_starts_with=prefix):
                if len(out) >= limit:
                    break
                out.append(_with_date({
                    "key": blob.name, "size": int(blob.size or 0),
                    "url": _azure_blob_url(cfg, blob, generate_blob_sas, permissions),
                }, getattr(blob, "last_modified", None)))
            return out

        except Exception:
            log.exception("azure connector listing failed for %s", conn.id)
            raise HTTPException(502, "connector listing failed")

    raise HTTPException(400, f"unknown connector kind {conn.kind!r}")


# --- single-object download ----------------------------------------------------------

def _signed_url(conn, key: str) -> str:
    """Presign one GET; used by fetch_bytes so downloads never re-list the bucket."""
    cfg = conn.config or {}

    if conn.kind == "s3":
        boto3 = _import_boto3()
        try:
            return _s3_client(boto3, cfg).generate_presigned_url(
                "get_object", Params={"Bucket": cfg["bucket"], "Key": key}, ExpiresIn=URL_TTL_SECONDS)
        except Exception:
            log.exception("s3 presign failed for %s", key)
            raise HTTPException(502, "connector signing failed")

    if conn.kind == "gcs":
        storage = _import_gcs()
        try:
            blob = _gcs_client(storage, cfg).bucket(cfg["bucket"]).blob(key)
            return blob.generate_signed_url(version="v4", expiration=timedelta(seconds=URL_TTL_SECONDS),
                                            method="GET")
        except Exception:
            log.exception("gcs presign failed for %s", key)
            raise HTTPException(502, "connector signing failed")

    if conn.kind == "azure":
        BlobServiceClient, generate_blob_sas, permissions = _import_azure()
        try:
            blob = _azure_service(BlobServiceClient, cfg).get_container_client(cfg["container"]).get_blob_client(key)
            return _azure_blob_url(cfg, blob, generate_blob_sas, permissions)
        except Exception:
            log.exception("azure presign failed for %s", key)
            raise HTTPException(502, "connector signing failed")

    raise HTTPException(400, f"unknown connector kind {conn.kind!r}")


def fetch_bytes(conn, key: str) -> bytes:
    """Download one object over its presigned HTTP(S) GET URL, aborting past the size cap."""
    url = _signed_url(conn, key)
    if urlsplit(url).scheme.lower() not in ("http", "https"):
        raise RuntimeError("refusing to download from a non-http(s) object URL")
    chunks: list[bytes] = []
    total = 0
    with httpx.stream("GET", url, timeout=FETCH_TIMEOUT, follow_redirects=True) as resp:
        if not 200 <= resp.status_code < 300:
            raise RuntimeError(f"download failed (HTTP {resp.status_code})")
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > MAX_FETCH_BYTES:
                raise RuntimeError(f"object is larger than {MAX_FETCH_BYTES // (1024 * 1024)} MB")
            chunks.append(chunk)
    return b"".join(chunks)


# --- worker handler ------------------------------------------------------------------

def sync_job(job) -> dict:
    """Import every image under a connector prefix into a project (worker job)."""
    if job.kind != "connector_sync":
        raise RuntimeError(f"wrong handler for job kind {job.kind!r}")

    params = job.params or {}
    with SessionLocal() as db:
        conn = db.get(Connector, params.get("connector_id") or "")
        if not conn:
            raise RuntimeError("connector not found")

        try:
            project = db.get(Project, params.get("project_id") or "")
            if not project or project.deleted_at:
                raise RuntimeError("project not found")
            workspace = db.get(Workspace, project.workspace_id)
            if not workspace:
                raise RuntimeError("project workspace not found")
            if conn.workspace_id != project.workspace_id:
                raise RuntimeError("connector belongs to a different workspace than the project")

            limit = max(1, min(int(params.get("limit") or 200), MAX_SYNC_LIMIT))
            objects = list_objects(conn, prefix=params.get("prefix") or "", limit=limit)
            image_objects = [o for o in objects if imaging.ext_ok(o["key"])]
            if not image_objects:
                raise RuntimeError("no image objects found at that prefix")

            have = db.scalar(select(func.count(Image.id)).join(Project)
                             .where(Project.workspace_id == workspace.id, Image.deleted_at.is_(None)))
            remaining = plan(workspace)["images"] - int(have or 0)
            if len(image_objects) > remaining:
                raise RuntimeError(f"plan image limit: {len(image_objects)} objects requested, {remaining} slots left")

            from ..routers.images import ingest
            uploaded = duplicates = annotated = failed = 0
            for start in range(0, len(image_objects), SYNC_CHUNK):
                batch = []
                for obj in image_objects[start:start + SYNC_CHUNK]:
                    try:
                        batch.append((obj["key"], fetch_bytes(conn, obj["key"])))
                    except Exception as exc:             # one bad object never fails the batch
                        failed += 1
                        log.warning("connector %s: could not download %s: %s", conn.id, obj["key"], exc)
                if not batch:
                    continue
                result = ingest(db, Ctx(user=None, ws=workspace, role="admin", db=db, project=project), batch,
                                params.get("batch_name") or f"{conn.name} sync",
                                params.get("split") or "auto", [], source="connector", to_dataset=True,
                                user_id=job.created_by)
                uploaded += result["uploaded"]
                duplicates += result["duplicates"]
                annotated += result["annotated"]

            if not uploaded and not duplicates:
                raise RuntimeError(f"no images could be downloaded from {conn.name} ({failed} failed)")

            conn.last_sync, conn.last_status = now(), "ok"
            db.commit()
            return {"connector_id": conn.id, "listed": len(objects), "uploaded": uploaded,
                    "duplicates": duplicates, "annotated": annotated, "failed_files": failed}

        except Exception:
            log.exception("connector %s sync failed", conn.id)
            try:
                db.rollback()
                db.execute(update(Connector).where(Connector.id == conn.id)
                           .values(last_sync=now(), last_status="error"))
                db.commit()
            except Exception:
                log.exception("could not record sync failure on connector %s", conn.id)
            raise
