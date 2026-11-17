# ADR 0005: The Inference Hub installs and downloads through worker jobs

- Status: Proposed (draft for the owner, 2026-11-17)
- Deciders: owner, PM/merge captain, R7 security
- Related: `docs/research/inference-hub/PLAN.md`, ADR 0004 (ML pipelines live in their own repository)

## Context

LabelDesk needs four inference surfaces: engine installs, a model catalogue, a VRAM/throughput
calculator, and a segmentation catalogue wired to auto-label. Two of them run software on a GPU host.
The product already has a job queue, a remote worker protocol with claim/progress/complete/fail and a
reaper, a worker heartbeat, workspace feature flags and an append-only audit table. The API process
does not have, and must not acquire, shell access to a GPU host.

The alternatives were a separate inference-manager service with its own control plane (~3,400 LOC and
a new deploy unit) and API-driven SSH/Ansible (~900 LOC but host credentials and a shell boundary in
the API). Both duplicate or weaken what exists.

## Decision

1. **Installs and downloads are ordinary jobs.** Two new kinds, `engine_apply` and `model_pull`, are
   added to `REMOTE_JOB_KINDS` and to the `labeldesk-worker` handler map. They are never added to
   `LOCAL_JOB_KINDS`, so the API process cannot claim them even with the embedded worker on.
2. **The catalogue is server-owned and the client sends ids, not commands.** Engine, version, runtime,
   model, variant, GPU preset and segmentation rows live in `services/inference_catalog.py`. The server
   builds `argv` lists; the worker runs them with `shell=False` and a fixed executable allowlist.
3. **Host truth belongs to the host.** A worker reports OS, GPU, driver, CUDA, free disk, installed
   engines and downloaded models in a JSON `inventory` on the existing `workers` row; the API renders
   it and never scans a remote filesystem.
4. **The API holds no model secrets.** `HF_TOKEN` lives in the worker environment; the API only learns
   whether one is present. Gated-licence acceptance stays with the operator's Hugging Face account.
5. **One flag, one workspace scope, one worker opt-in.** `task_inference` gates routes and UI;
   `LD_INFERENCE_WORKSPACE` bounds the hub when a deployment has several workspaces;
   `LD_ALLOW_ENGINE_INSTALL=1` is required on the host before any job executes.
6. **The estimator is server-side.** One Python module computes VRAM and throughput, serves the
   calculator and the catalogue's "fits this host" state, and carries the formulas' sources and
   assumptions.

## Consequences

- The API stays a control plane: no `pip`, no engine import, no model file, no host credentials.
- Progress, cancellation, reaping and audit are inherited; the new surface is a router, a service, two
  worker handlers and a JSON column.
- Host asset truth is not queryable as rows. History lives in `jobs` and `audit`, and the current state
  is whatever the host last reported. Acceptable for v1; a table would be a second truth.
- Installing an engine costs a per-engine virtual environment or a container; the worker's own
  environment is never modified.
- A multi-tenant deployment that does not set `LD_INFERENCE_WORKSPACE` exposes the hub to every
  workspace admin. The docs, the empty state and the permission test state this explicitly.
- A hash-locked wheelhouse and a measured-benchmark flow are follow-ups, not v1 claims.
