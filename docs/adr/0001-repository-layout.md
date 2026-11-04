# ADR 0001: One repository with an app-per-directory layout

- Status: Accepted
- Date: 2026-11-03
- Owner decision: approved in the workspace plan for the LabelDesk v2 clean-up

## Context

The repository grew from a research pipeline into a labeling application without a single layout. Pipeline code sits in `sam3_auto_label/` and `yolo26_ppe/`. The application sits in `apps/backend`, `apps/frontend`, `apps/worker`, `apps/inference`, and `apps/sdk`. Deployment, tools, tests, and docs are separate root directories.

Agents work in parallel on frontend, backend, ML, and platform tasks. That exposed two problems. Shared files such as `main.py`, `models.py`, `App.tsx`, and `lib/api.ts` collect edits from every feature and conflict repeatedly. And a split into separate repositories would make a cross-cutting change, such as an API field used by the editor, require coordinated releases in two places.

The owner also wants an ML boundary that does not mix datasets and weights with application code.

## Decision

Keep one repository. Use one directory per deployable app, with shared code and operational assets in fixed top-level directories:

```text
apps/frontend, apps/backend, apps/worker, apps/inference, apps/sdk
packages/    shared code
deploy/      Compose and environment examples
tools/       scripts used by apps and tests
tests/       cross-app tests
docs/        specification, architecture, runbooks, ADRs
ml/          yolo26_ppe and sam3_auto_label
research/    reports and research notes
data/        datasets that task worktrees do not check out
```

The application folders are `apps/frontend` and `apps/backend`; they were renamed from the earlier layout, which older documents and the frozen plan still use.

Features add their own file instead of appending to a shared registration file: one router per feature, one worker handler module, one web route and navigation registration, one API client file, and per-domain model modules with migrations for schema.

There is no repository split. A future change that needs both halves is two tasks in this repository, backend first.

## What is implemented today

| Target | Current state |
|---|---|
| `apps/frontend` | Renamed from the earlier web folder. The React app lives here. |
| `apps/backend` | Renamed from the earlier API folder. The FastAPI app, its routers, services, and tests live here. |
| `packages/` | Not created. Shared Python code is under `apps/backend/app`. |
| `ml/` | Not created. The pipeline is still `sam3_auto_label/` and `yolo26_ppe/`. |
| `research/` | Not created. Reports are in `reports/` and `research_notes/`. |
| Feature registration split | Partly in place. Routers are separate modules; several shared frontend files are still central. |

The application folders have been renamed and the `ml/`, `research/` and `packages/` moves are still pending. Documentation uses the current folder names. Do not move or rename an app folder as a side effect of an unrelated change.

## Consequences

- One clone, one history, and one review gate for a change that crosses the front and back.
- Task worktrees can be sparse by team. The planned profiles are frontend, backend, full, and ml. They are not implemented yet, and `tools/ld-task` does not exist yet.
- Shared files stay a conflict risk until the per-feature splits are complete. The split work is a platform task with no feature work running.
- Moving the pipeline under `ml/` changes paths in configuration, tests, and reports. It needs its own task and a search for hard-coded paths.
- The layout is a convention, not enforced by tooling. Reviewers check it.

## Alternatives considered

**Split into a frontend repository and a backend repository.** Rejected. It would double the release coordination for every contract change and break the rule that a contract change is reviewed in one place.

**Keep a flat root and add `api/` and `web/`.** Rejected. It does not scale to worker, inference, and SDK, and it gives no clear place for shared code.

**Move everything at once with the rename.** Rejected for now. The workspace plan sequences the layout and hot-file splits as one platform branch with no feature work running, then the rename can follow without mixing concerns.
