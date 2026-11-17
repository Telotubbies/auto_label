# ADR 0003: Packages, ML layer, and research split

- Status: Accepted
- Date: 2026-11-17
- Supersedes: ADR 0001 in part (the `apps/sdk` location, the `tests/` description, and the `packages/` scope)
- Owner decision: the 2026-11-17 directive to reorganise once one working branch remains

## Context

ADR 0001 fixed one repository with one directory per deployable app, plus `packages/`, `ml/`, `research/`, `data/`, `deploy/`, `tools/`, `tests/` and `docs/`. The app-folder decision landed: `apps/backend` and `apps/frontend` are renamed. Four did not: `ml/` and `research/` did not exist, `packages/` was never created, `data/` grew 81 tracked files with no ignore rules, and the pre-rename directories `apps/api/` and `apps/web/` were left on disk as 307 MB of untracked residue that `.gitignore` does not cover.

Three findings from the 2026-11-17 layout audit force the refinement:

1. The Python SDK is published and imported (`apps/backend/tests/test_sdk_cli.py` puts it on `sys.path`), but it is deployed nowhere. ADR 0001 files it under `apps/`, which is the bucket for deployables.
2. `packages/` as "shared code" has stayed empty because there is no shared code to move. An empty directory teaches contributors nothing.
3. `tests/` holds pipeline tests, not cross-app tests, so ADR 0001's description misleads.

## Decision

Keep one repository. Refine the layout to:

    apps/       deployables: backend, frontend, worker, inference
    packages/   importable, never deployed alone: sdk
    ml/         sam3_auto_label, yolo26_ppe, pipeline_cli.py, auto_label.sh, setup.sh
    research/   reports/, notes/
    data/       offline pipeline datasets; new bytes are ignored
    deploy/ tools/ tests/ docs/

A directory is an app if it has its own deploy or release target and sits at the end of the dependency graph; otherwise it is a package. `tests/` means "repository-level tests"; app tests stay in `apps/*/tests/`. `docs/research/` is product research and stays in `docs/`.

## Alternatives considered

**Leave the layout as it is.** Rejected: 307 MB of unignored dead residue plus three loose entry points at the root make every `git add -A` a hazard, and the owner directive names the reorganisation explicitly.

**Adopt Turborepo or Nx with a root `package.json`, `turbo.json` and a pnpm workspace.** Rejected for now: one JavaScript package cannot amortise the extra manifests, and Turborepo's Python support is experimental. Revisit when a second JS package exists.

**Adopt a uv workspace with a root `pyproject.toml`.** Deferred: uv enforces a single `requires-python` and one lockfile, and the three Python trees have independent requirement sets today. Path dependencies are the lower-risk route until they converge.

**Move the SDK to `packages/sdk` (chosen) versus keep `apps/sdk`.** Keeping it satisfies ADR 0001 literally and costs nothing. Moving it matches how Turborepo, Nx and uv classify a published library, and gives `packages/` one real member instead of an empty convention.

**Move `docs/research/` under `research/`.** Rejected: it renames 384 working backlog cards and breaks the ledger references for no functional gain, and there is no docs build to exclude it from.

## Consequences

Positive: one rule per bucket; the dead 307 MB is gone and unignorable; a fresh clone no longer needs the pre-rename directories; `packages/` has a member; root holds only ecosystem files.

Negative: `ml/` and `research/` moves touch about 60 documents and 100+ code lines, concentrated in `config.py`, `conftest.py` and the integration tests. `docs/` still carries historical paths, deliberately.

Risks and mitigations: the 21.8 GB `sam3_auto_label` move must be a same-volume rename, not a copy; `tools/check_large_files.py` must learn the new prefixes in the same commit or the next data commit slips past the gate; the frozen plan keeps stale names on purpose and carries a mapping note.
