# ADR 0004: ML pipelines live in their own repository

- Status: Accepted
- Date: 2026-11-17
- Owner decision: "separate repo + env paths" (approved 2026-11-17)

## Context

After ADR 0003 the SAM 3.1 and YOLO26 pipelines sat under `ml/`: about 700 tracked files, 9 Git LFS
weights, and roughly 28 GB of local datasets, checkpoints and virtual environments. The web app only
needs three things from it at run time: the SAM source and checkpoints for auto-label, the pretrained
YOLO weights, and one archived training run used by the demo seed. Every agent worktree still carried
the whole ML tree, and the ML tests ran as part of the app repository.

## Decision

Move `ml/` to its own private repository, `Telotubbies/labeldesk-ml`, with its full history (rewritten
with `git filter-repo`, LFS objects included), checked out next to this one at `../labeldesk-ml`.

The app finds the ML checkout through environment variables, each defaulting to the sibling checkout:

| Variable | Default | Used for |
| --- | --- | --- |
| `LD_SAM_ROOT` | `../labeldesk-ml/sam3_auto_label` | SAM auto-label source and checkpoints |
| `LD_PRETRAINED_DIR` | `../labeldesk-ml/yolo26_ppe/models/pretrained` | pretrained YOLO weights |
| `LD_DEMO_MODEL_RUN` | the archived nano run under `../labeldesk-ml/yolo26_ppe/models/archive/` | demo seed model |

When a path is missing the app degrades instead of failing: SAM reports unavailable, pretrained falls
back to the hub model name, and the demo seed skips the trained-model row.

## Consequences

- App worktrees are smaller and agents no longer read ML code by accident.
- ML tests run in the ML repository (`python -m pytest -q` there), not in this repository's gate.
- A cross-repo change (e.g. a new SAM entry point) needs a commit in each repository; the env contract
  above is the interface between them.
- The WSL virtual environment `sam3_auto_label/sam3_venv` was left at its old path in this checkout
  because it contains symlinks that a move would break; recreate it inside `../labeldesk-ml` when needed.
