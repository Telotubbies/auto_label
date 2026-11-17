"""T-1011: the worker's only door to Hugging Face.

``huggingface_hub`` is an optional extra, so every import here is lazy: the base worker install
stays small and a missing extra fails the job with the exact pip command. The token is read from
``HF_TOKEN`` and passed only to the hub call; it is never written to a log, an error or a result.
"""
import hashlib
import importlib
import os
import re
from pathlib import Path

MISSING_EXTRA = ('missing_extra: this model download needs Hugging Face support on the worker. '
                 'Install it with: pip install "labeldesk-worker[inference]"')
TOKEN = re.compile(r"hf_[A-Za-z0-9_-]{4,}")     # T-1018: `hf_secret…` has an underscore in it


class MissingExtra(RuntimeError):
    """The worker was installed without the ``inference`` extra."""


def redact(text: str) -> str:
    """Strip anything shaped like a Hugging Face token from host-supplied text."""
    return TOKEN.sub("hf_***", text)


def _hub():
    try:
        return importlib.import_module("huggingface_hub")
    except ImportError as exc:
        raise MissingExtra(MISSING_EXTRA) from exc


def token() -> str | None:
    """The worker's token, or None; it is never an argument a caller keeps around."""
    return os.environ.get("HF_TOKEN") or None


def metadata(repo: str, revision: str, token: str | None) -> dict[str, dict]:
    """One pinned repository's files: ``{path: {bytes, lfs_oid}}``; ``lfs_oid`` is None off LFS."""
    info = _hub().HfApi().model_info(repo, revision=revision, token=token, files_metadata=True)
    files = {}
    for sibling in info.siblings or []:
        lfs = getattr(sibling, "lfs", None)
        oid = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
        files[sibling.rfilename] = {"bytes": sibling.size, "lfs_oid": oid}
    return files


def _progress_class(on_progress):
    """The ``tqdm`` shape the hub constructs, so byte progress comes from the client's own resume."""

    class Bar:
        def __init__(self, *args, total=0, initial=0, **kw):
            self.total = total or 0
            self.n = initial or 0
            on_progress(self.n)

        def update(self, n=1):
            self.n += n
            on_progress(self.n)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __iter__(self):
            return iter(())

    return Bar


def download(repo: str, revision: str, filename: str, local_dir, token: str | None,
             on_progress) -> Path:
    """Fetch one file into ``local_dir``; the hub owns resume through its ``.incomplete`` file."""
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    path = _hub().hf_hub_download(repo_id=repo, revision=revision, filename=filename,
                                  local_dir=str(local_dir), token=token, resume=True,
                                  tqdm_class=_progress_class(on_progress))
    return Path(path)


def sha256(path) -> str:
    """The digest of a downloaded file, read in chunks so a 5 GB weight does not fill memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
