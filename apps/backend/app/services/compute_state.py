"""What the Compute page says about the GPU: one headline from workers and jobs, never one ledger alone.

The header badge once read only the API process's own GPU lease, so a pip worker training on another GPU
still showed "GPU idle". The headline here looks at the running jobs and the online workers first.
"""
GPU_KINDS = frozenset({"train", "autolabel", "batch_infer", "anomaly_train", "insights_embedding", "export_engine"})
KIND_LABEL = {"train": "Training", "autolabel": "Auto-label", "batch_infer": "Batch inference",
              "anomaly_train": "Anomaly training", "insights_embedding": "Embeddings", "export_engine": "Engine build"}


def headline(*, workers_online: int, jobs: list[dict], api_holder: str | None) -> dict:
    """``{"state": training|working|idle|offline, "label": ...}`` for the badge and the page's first band."""
    running = [j for j in jobs if j.get("status") in ("running", "cancelling") and j.get("kind") in GPU_KINDS]
    queued = [j for j in jobs if j.get("status") == "queued" and j.get("kind") in GPU_KINDS]
    if running:
        job = next((j for j in running if j["kind"] == "train"), running[0])
        state = "training" if job["kind"] == "train" else "working"
        return {"state": state, "label": f"{KIND_LABEL.get(job['kind'], 'Working')} · {round(job.get('progress') or 0)}%"}
    if api_holder:
        return {"state": "working", "label": f"GPU: {api_holder}"}
    if not workers_online:
        waiting = f" · {len(queued)} waiting" if queued else ""
        return {"state": "offline", "label": f"No worker online{waiting}"}
    if queued:
        return {"state": "working", "label": f"Starting · {len(queued)} queued"}
    return {"state": "idle", "label": "Idle"}


def eta_seconds(progress: float | None, started: float | None, now: float) -> int | None:
    """Time left from the pace so far; unknown until the job has made progress."""
    if not started or not progress or progress <= 0 or progress >= 100:
        return None
    return round((now - started) / progress * (100 - progress))
