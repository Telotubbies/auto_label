# LabelDesk dev-team flow for opencode

Owner directive 2026-11-16. This file extends `docs/OPENCODE_PM_RULES.md` (rules there still bind).
Goal now: close every side branch (finish → review → QA → merge into `feat/labeldesk-v2`) so only
`main` and `feat/labeldesk-v2` remain; then migration and folder restructure.

Model for every agent: `opencode-go/deepseek-v4.1-flash`. Scope: `E:/02_Projects/auto_label` and its
worktrees only. Never push, never touch `main`.

## 1. Team roles

Every agent loads `ponytail` and `verification-before-completion`, plus the skills in its row. Every
dispatch prompt names the role, the skills, the worktree path, the brief path and the definition of done.

| # | Role | Owns | Extra skills | Definition of done |
| --- | --- | --- | --- | --- |
| R0 | **PM / merge captain** (exactly ONE session) | queue, dispatch, merges, ledger | requesting-code-review, receiving-code-review, dispatching-parallel-agents | branch merged, suites green, branch + worktree deleted, ledger line |
| R1 | **Release engineer (triage)** | read-only classification | — | table MERGED / SUPERSEDED / UNFINISHED with git evidence |
| R2 | **Tech lead / planner** | splits a big branch into parts, writes `task-N-brief.md` | writing-plans, codebase-design | brief lists files per part, no two parts share a file |
| R3 | **Backend / ML engineer** | API, jobs, services, models | test-driven-development, systematic-debugging, codebase-design | RED then GREEN shown, touched tests pass, ruff clean, report written |
| R4 | **Frontend engineer** | React pages, nav, components | test-driven-development, frontend-design, impeccable, react-best-practices, composition-patterns | node tests pass, `npm run build` passes, report written |
| R5 | **Port engineer** | moves pre-Z2 work (`apps/api`, `apps/web`) onto `apps/backend`, `apps/frontend` | codebase-design, test-driven-development | same behaviour and tests on the new layout, old paths untouched |
| R6 | **Code reviewer** (fresh session, never the author) | spec check, then quality check on the diff | requesting-code-review, receiving-code-review, codebase-design | verdict APPROVED, or findings with file:line and severity C/I/m |
| R7 | **Security reviewer** | only when the diff touches auth, RBAC, secrets, uploads, outbound URLs, webhooks, connectors, PLC/OT | security-review | no Critical/High left; workspace isolation, secretbox, safefetch checked |
| R8 | **QA engineer** | runs the real checks on the merged candidate | webapp-testing, e2e-testing, verification-before-completion | API suite + web build + node tests + smoke of the feature's page; numbers recorded |
| R9 | **UI QA** | UI-touching branches only | impeccable, web-design-guidelines, uxui-law, webapp-testing | page checked light/dark/375 px, no console errors, screenshots saved |
| R10 | **Regression fixer** | any red test on `feat/labeldesk-v2` | systematic-debugging, test-driven-development | feat green again; fix on a `fix/*` branch for R0 to merge |
| R11 | **Doc / ledger keeper** | report, ledger, rulings | documentation-writer | `branch-consolidation-report.md` and `progress.md` current |

## 2. Per-branch pipeline

```
R1 triage ──► UNFINISHED? ──► (big?) R2 plan ──► R3/R4/R5 build in worktree
                                                     │
                                                     ▼
                         R6 review (+R7 if security surface) ──findings──► same builder fixes (max 5 rounds)
                                                     │ APPROVED
                                                     ▼
                         R0 rebase onto feat in the worktree ──► R8 QA on the rebased branch (+R9 if UI)
                                                     │ green
                                                     ▼
                         R0 merge --no-ff ──► R8 full suites on feat ──red──► R10 fixes, merges paused
                                                     │ green
                                                     ▼
                         R0 delete branch + worktree, delete its SUPERSEDED old branch, R11 ledger
```

Rules:
- Only R0 merges, one branch at a time. Never two PM sessions. Before starting, R0 checks
  `git log -5 feat/labeldesk-v2` and stops if commits it does not recognise keep appearing.
- QA runs on the rebased branch BEFORE merge, and the full suite runs again on feat AFTER merge.
- A red feat stops all merges until R10 is green.
- Fix rounds go back to the same builder session with only the findings; R6 re-reviews only the fix diff.
- Builders run only touched test files; full suites are R8's job.
- Every agent ends with a report (what changed, RED/GREEN or command output, risks). No report = not done.

## 3. Concurrency

At most 4 heavy agents at once (machine lost power under load). R1, R6, R7, R11 are light.
Pipeline example: R6 reviews branch A while R3 fixes B, R5 ports C and R8 QA's D.

## 4. Current queue (from `B:/02_Projects/ld-tmp/triage-report.md`, 21:56)

Merged: 29, 33, 28-v2, fix/streams-regression.

| Order | Branch | State | Next role |
| --- | --- | --- | --- |
| 1 | `oc-task-30-v2` | re-review APPROVED + new streams-seam commit `ec4ab3f` | R6 re-review of `ec4ab3f` → R8 → merge |
| 2 | `oc-task-4-v2` | APPROVED, +31 lines | R8 → merge |
| 3 | `oc-task-32-v2` | fixes committed (`9bfa781`) | R6 re-review → R8 → merge |
| 4 | `oc-task-31-v2` | fixes committed (`c47bcd1`) | R6 re-review (+R7: AI allowance/money) → R8 → merge |
| 5 | `oc-fix-insights` | pre-Z2 paths, +30/−14 test-only | R5 port → R6 → R8 → merge |
| 6 | `oc-task-36-v2` | review findings pending | R3 fix → R6 (+R7: connectors, CSV escape) → R8 → merge |
| 7 | `oc-task-34-v2` | 2 Critical, 2 Important | R3 fix → R6 + R7 → R8 → merge |
| 8 | `oc-task-27-38-v2` | 33 files, not reviewed | R6 + R9 → fixes → R8 → merge |
| 9 | `oc-task-40` | PLC/OT, pre-Z2, nothing on feat | R2 plan → R5 port (backend) + R4 (UI) → R6 + R7 → R8 + R9 → merge |
| last | old SUPERSEDED branches (27, 30, 31, 32, 34, 36, 4, 5, 25, r1-*, worktree-agent-a5ca…, a805…) | covered by merged work | delete after their cover merges |
| — | Task 12 (GPU smoke) | needs real GPU, vLLM, SAM 3.1 | list for the owner, do not fake |

## 4b. Squads (productivity plan, 2026-11-16 22:30)

Measured remaining work vs feat (`git diff --shortstat feat...branch`):

| Branch | Files | +lines | Domain |
| --- | --- | --- | --- |
| 4-v2 | 1 | 31 | autolabel test |
| fix-insights | 1 | 30 | test port |
| 34-v2 edge export | 19 | 1034 | inference/export |
| 30-v2 tiling | 26 | 1382 | inference/streams |
| 36-v2 batch inference | 14 | 1412 | inference/jobs |
| 32-v2 OCR | 23 | 2096 | labeling/data |
| 31-v2 workflows | 28 | 2701 | automation |
| 40 PLC/OT (pre-Z2 port) | 17 | 2062 | automation/OT |
| 27-38-v2 search + events | 33 | 3726 | data/search |

Three squads work in parallel, each owns its branches end to end (build → review → QA-before-merge)
and hands a merge-ready branch to the integration crew. One heavy agent per squad at a time + one
for integration = the 4-agent machine limit.

| Squad | Branches, in order | Builder role | Reviewer focus |
| --- | --- | --- | --- |
| A Inference | 30-v2 → 34-v2 → 36-v2 | R3 backend/ML | R6 + R7 for 34 (artifact download) and 36 (connectors, CSV escape) |
| B Data & labeling | 4-v2 → fix-insights (R5 port) → 32-v2 → 27-38-v2 | R3 + R4 | R6 + R9 UI for 32 and 27-38 |
| C Automation & OT | 31-v2 → 40 (R2 plan, R5 port backend, R4 UI) | R3/R5 | R6 + R7 for both (money/allowance, PLC fail-safe) |
| Integration crew | merge train | R0 + R8 + R10 | full suites after each merge |

Speed rules:
1. **Quick wins first**: 4-v2 and fix-insights merge in the first slot (tiny, shrink the queue).
2. **Merge train**: R0 merges whichever branch is QA-green first; it does not wait for queue order.
3. **Hot-spot conflict rule**: six branches touch `apps/backend/openapi.json`,
   `apps/frontend/src/lib/api-types.gen.ts`, `services/flags.py`, `lib/types.ts`,
   `routers/__init__.py`. On rebase: never hand-merge the two generated files; take feat's copy and
   regenerate (`npm run gen:api-types`, backend openapi export). For registries (`flags.py`,
   `routers/__init__.py`, `test_flags.py` SURFACES, `config.py` job kinds) keep both sides' entries.
4. **Rebase right before QA**, not earlier, so each branch is rebased once onto the latest feat.
5. **Test budget**: builders run touched test files only; R8 runs the full API suite + node tests +
   web build once before and once after each merge.
6. **Reviews in parallel with builds**: while a squad's builder works on its next branch, its reviewer
   reviews the previous one.
7. **Reuse**: existing review/re-review files and committed fixes are evidence; never redo them.

## 4c. Best practices (measured on this repo, 2026-11-16)

Git and merging
1. **`git config rerere.enabled true`** (repo-local, R0 sets it once): git remembers each conflict
   resolution, so the same registry/openapi conflict across six branches is resolved once.
2. **Generated files are never merged by hand.** After any rebase or merge that touches
   `apps/backend/openapi.json` or `apps/frontend/src/lib/api-types.gen.ts`: take feat's copy, then
   regenerate (backend openapi export, then `npm run gen:api-types`); `npm run build` runs
   `gen-api-types --check` and catches drift.
3. **Merge queue with batching** (bors/GitHub merge-queue style): when 2+ branches are QA-green,
   R0 builds a temporary `queue/batch-N` = feat + those branches, runs the full suite once; green →
   merge all in order; red → bisect (merge them one by one). Saves one full-suite run per branch.
4. **Smallest/independent first, hot-spot owners last**: branches that touch no hot-spot file merge
   first; the biggest hot-spot branch (27-38-v2) rebases last, once.

Tests (full API suite = 1223 tests, 6 min 23 s serial)
5. **Full suite runs serially** (`python -m pytest -q`, about 6-7 min). Measured 2026-11-16: `pytest -n 4` gives 12 failed / 45 errors because xdist workers share one SQLite database, and it was slower (7 min). Do not use xdist until the suite gets a per-worker database.
6. **Test impact during work**: builders run only the test files for modules they touched, plus
   `pytest --lf` after a failure. Never the full suite inside a builder.
7. **Flake rule**: a test that fails then passes on rerun is logged in the ledger as a flake with the
   seed/timing, not silently retried; R10 fixes it if it recurs.

Agents
8. **Orchestrator-worker with written handoffs**: every dispatch is a short task card (role, skills,
   worktree, brief path, inputs, definition of done, report path). Every worker writes its report to
   `.superpowers/sdd/2026-10-31-labeldesk-v2/task-<N>-<role>-<round>.md`; R0 reads reports, never
   the worker's transcript.
9. **WIP limit**: max 4 heavy agents, max 1 branch in "rebase + QA" per squad, max 1 merge at a time.
10. **Status board**: R0 keeps `.superpowers/sdd/2026-10-31-labeldesk-v2/board.md` (one row per
    branch: squad, stage, owner session, last update, blocker) and updates it after every state
    change. The owner and the 10-min check read only this file.
11. **Review quality gates**: reviewers use a fixed checklist (spec match, tests prove behaviour,
    workspace isolation, secrets/safefetch, error messages, ponytail: no speculative code). Only
    Critical/Important block; Minor goes to the ledger.
12. **Bounded loops**: max 5 fix rounds; after round 3 R0 re-plans (R2) instead of another blind fix.
    A worker that produces no commit and no report in 40 min is interrupted and re-dispatched once.
13. **Idempotent resume**: R0 derives state from git + board + report files only, so any restart
    continues exactly where work stopped.

## 4d. Owner rules for AI-written code (adopted 2026-11-17)

AI writes the code, the owner sets direction. Keep tasks small, review every result, test first.

14. **Options first.** Before production code, an implementation lane lists 2-3 designs that satisfy the
    card, each with estimated lines of code, files touched and trade-offs, picks the smallest one that
    fully satisfies the card, and puts that table at the top of its report. Test-only cards skip it.
15. **Report in plain words.** Every report says what was done, files changed with lines added/removed,
    and the RED/GREEN and test/build output, so the merge captain can decide go or adjust.
16. **R6 checks over-engineering.** The reviewer checks the options table, and raises as a finding any
    code, option, abstraction or dependency the card did not need.
17. **Tests are the safety net.** The merge gate is the full serial backend suite, root and tools
    suites, node tests, the web build, and (after T-008) the Playwright e2e smoke.

## 5. Finish line

`git branch` shows only `main` and `feat/labeldesk-v2`; `git worktree list` shows only the main
checkout; full API suite, node tests and web build are green on feat with real numbers in the report;
ledger updated. Then R0 stops and reports to the owner in Thai. The PR from feat to `main` and any
push wait for the owner.
