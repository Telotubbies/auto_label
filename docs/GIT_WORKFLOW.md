# Git workflow

This repository uses long-lived integration branches and short-lived task branches in separate worktrees. One integrator checkout owns the integration branch. Task agents never push, never commit on `main`, and never commit on `feat/labeldesk-v2`.

## Branches

| Branch | Purpose | Who writes |
|---|---|---|
| `main` | Release. Fast-forward only after the release gate and review. | Merger only |
| `feat/labeldesk-v2` | Integration. One merger writes here. | Merger only |
| `task/<team>/<id>-<slug>` | One agent job. Starts from the integration tip. Deleted after merge. | One task owner |

Teams are `frontend`, `backend`, `ml`, and `platform`. Example: `task/platform/Z3-docs`.

Do not create a branch from `main` for feature work. Start from the current `feat/labeldesk-v2` tip so the task sees the integration state it will merge into.

## Disk layout

E: is the only working drive.

```text
E:\02_Projects\
  auto_label\              integrator checkout; merger only, no task work
  ld-worktrees\<task>\     one worktree per task
  ld-tmp\<task>\           TMP, TEMP, LD_TEST_TMP and test data for that task
  ld-cache\                shared npm and uv caches, model weights
  ld-assets\               datasets and YOLO outputs, outside task worktrees
```

Keep task output inside the task's worktree or `ld-tmp\<task>`. Do not write datasets, model weights, or YOLO runs into the repository.

## Starting a task

`tools/ld-task` is planned but is not in the repository yet. Until it lands, create the worktree by hand from the integrator checkout. The command below uses a placeholder branch name; replace it.

```bash
git -C E:/02_Projects/auto_label fetch --all --prune
git -C E:/02_Projects/auto_label worktree add \
  -b task/platform/Z3-docs \
  E:/02_Projects/ld-worktrees/task/platform/Z3-docs \
  feat/labeldesk-v2
```

Then set the task environment in that shell:

```bash
export TMP=E:/02_Projects/ld-tmp/platform/Z3-docs/tmp
export TEMP="$TMP"
export LD_TEST_TMP=E:/02_Projects/ld-tmp/platform/Z3-docs/test
export LD_DATA_DIR=E:/02_Projects/ld-tmp/platform/Z3-docs/data
mkdir -p "$TMP" "$LD_TEST_TMP" "$LD_DATA_DIR"
```

The planned `tools/ld-task new <team> <id> <slug> <profile>` will create the branch, worktree, sparse checkout, ports, and `.env.task` in one step. The planned sparse profiles are:

```text
frontend   apps/frontend packages docs
backend    apps/backend packages tools docs
full       apps packages tools deploy docs
ml         ml tools docs
```

None of those profiles is implemented yet, and `packages/` and `ml/` do not exist. Do not write a script or CI job that depends on `tools/ld-task` until it is merged.

## Working rules

- Stay inside your task worktree. Do not edit the integrator checkout.
- Do not touch `main` or `feat/labeldesk-v2`. If you think the integration branch is wrong, report it to the merger.
- Never push. The merger decides what leaves the machine.
- Never delete untracked files you did not create. If a build left artifacts you need to remove, list them first.
- Keep the branch small. One task, one concern.
- Commit with a conventional subject: `feat:`, `fix:`, `chore:`, or `docs:`.
- Do not rewrite shared history. Do not force-push anything.
- Do not remove a worktree with `--force` to get past untracked files.

## Shared files and target conventions

These files caused repeated conflicts: `main.py`, `models.py`, `bootstrap.py`, `App.tsx`, `shell.tsx`, and `lib/api.ts`. Add a feature in its own file instead of appending to them. The per-feature split is the target; several shared files are still central today.

| Area | Target convention |
|---|---|
| API routers | One router module per feature, registered in the app's router list |
| Worker handlers | One handler module per feature, with its kind registered in `HANDLERS` |
| Web routes and navigation | One registration file per feature |
| API client | One client file per feature |
| Models and columns | Per-domain module; schema changes go through migrations or `ensure_columns` |

If a task must edit a shared registration file, keep the edit to a single import or one line and say so in the handoff.

## Frontend and backend work

A change that crosses the contract is two tasks, not one branch with both halves half-finished:

1. Backend task: change the API, update the OpenAPI-visible schema, run the SDK lockstep test, merge first.
2. Frontend task: use the merged endpoint behind a `task_<id>` feature flag, default off, merge second.

The contract and its current gap are described in [ADR 0002](adr/0002-front-back-contract.md).

## Handing off

Before you hand off:

```bash
git status --short
git diff --stat
```

Run the checks that cover the change. At minimum, backend changes run `pytest -q` from `apps/backend`, and frontend changes run `npm run build` from `apps/frontend`. Report the commands you ran and anything you skipped.

Commit your work on the task branch, then tell the merger:

- branch name,
- one-line summary,
- checks run and their result,
- known gaps or follow-ups,
- any shared file you had to edit.

Do not merge your own branch and do not push.

## Merging

Only the merger writes to `feat/labeldesk-v2`.

1. Review the branch diff and its tests.
2. Confirm the checks in the handoff actually ran.
3. Merge in batches of up to four branches.
4. Resolve conflicts on the integration branch, not in a task worktree.
5. Re-run the full backend suite and the frontend build after the batch.

When a task branch is merged and clean, remove the worktree and branch:

```bash
git -C E:/02_Projects/auto_label worktree remove E:/02_Projects/ld-worktrees/task/platform/Z3-docs
git -C E:/02_Projects/auto_label branch -d task/platform/Z3-docs
```

If `worktree remove` refuses, there are modified or untracked files. Inspect them. Do not force the removal.

## Release

`main` moves only by fast-forward from `feat/labeldesk-v2` after the release gate passes. Any force-push to a shared branch needs separate owner approval and is outside the normal workflow.
