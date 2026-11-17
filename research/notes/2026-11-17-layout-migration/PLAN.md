# Repository layout migration plan

- Date: 2026-11-17
- Branch measured: `feat/labeldesk-v2` at `2fb1f02` (1,373 tracked files). **The branch moved to `3c8fbc8` while this audit ran** — another actor is merging into it right now (see §0 item 7). Re-confirm the tree before executing step 1.
- Author lane: independent planning (read-only on the repo except `docs/layout-migration/` and `.superpowers/sdd/2026-10-31-labeldesk-v2/`)
- Supersedes: nothing. Refines [ADR 0001](../adr/0001-repository-layout.md). Records the refinement as ADR 0003 (§9).
- Research inputs: [A polyglot monorepo](research/A-polyglot-monorepo.md), [B ML code and data](research/B-ml-data-layout.md), [C docs layout](research/C-docs-layout.md), [D repo hygiene](research/D-repo-hygiene.md).

**Goal.** One working branch, one recognised layout: deployables in `apps/`, importable code in `packages/`, the ML layer in `ml/`, provider-side reports and notes in `research/`, and a root that holds only ecosystem files.

**Non-goals.** No history rewrite. No renaming of `apps/backend`, `apps/frontend`, `apps/worker`, `apps/inference`. No new build tooling (Turborepo, Nx, pnpm workspaces, uv workspaces). No restructuring of `docs/` into Diátaxis folders. No deletion of tracked content.

---

## 0. Constraints every executor inherits

1. Every step below ends on a green tree (§7.0 defines the two gate tiers). The full gate is serial: `python -m pytest -q` in `apps/backend` (1,223 tests, ~6 min 23 s), `python -m pytest -q` at the repo root, `python -m pytest tools/tests -q`, `npm test` and `npm run build` in `apps/frontend`.
2. Never run the suite with `-n`/xdist. It shares one SQLite database and fails (`docs/OPENCODE_TEAM_FLOW.md:138`).
3. Use `git mv` for every move, one commit per step, moves and their reference edits in the *same* commit (§7.0 explains why this does not hurt rename detection).
4. Never `git add -A` on this repository until step 1 lands. `apps/api/data/.secret` is an unignored runtime secret and `apps/web/node_modules/` is an unignored 12,483-file tree (§2.2).
5. `docs/superpowers/plans/2026-10-31-labeldesk-v2.md` is frozen. It carries 38 `apps/api`/`apps/web` references on purpose. Add a path-mapping note, do not rewrite it.
6. Do not move `apps/*` anywhere. `apps/backend/app/config.py:7` computes the repo root as `Path(__file__).resolve().parents[3]`; every adapter, router and test resolves paths through it, so a depth change is a repo-wide edit for no layout gain.
7. **The checkout is live.** Between the first and last command of this audit, `feat/labeldesk-v2` advanced from `2fb1f02` to `3c8fbc8` and another actor staged `design/labeldesk-v3/VISUAL-OVERRIDE.md` (`git diff --cached`). Step 1 must therefore begin with `git status --porcelain` and an explicit decision on anything already staged, and must start from a quiet checkout: no other agent, no `git gc`, no merger mid-run. The 2026-11-03 `repo-audit.md` hit the same problem.

---

## 1. Research summary

Four parallel lanes, 100+ citations, all inline in `docs/layout-migration/research/`. The load-bearing findings:

**1.1 Apps versus packages is a deployability test, not a folder name.**
Turborepo defines an *Application Package* as one that "will be deployed from your workspace" and must be "the 'end' of your Package Graph", and a *Library Package* as "code that you intend to share around your workspace. They aren't independently deployable" (<https://turborepo.com/docs/core-concepts/package-types>). Nx says the same in the same words and notes `libs/` is an accepted alias (<https://nx.dev/docs/getting-started/tutorials/crafting-your-workspace>). pnpm prescribes no split at all; the apps/packages shape in pnpm repos comes from Turborepo/Nx docs (<https://pnpm.io/workspaces>).

Consequence for this repo: there are four deployables with separate deploy targets (`backend` container, `frontend` container/Vercel, `worker` pip package installed on a GPU box, `inference` container) and one published library (the Python SDK). That is past the threshold where the split pays for itself, which is the condition the tools themselves name (<https://turborepo.com/docs/guides/single-package-workspaces>).

**1.2 The published SDK is a package, not an app.**
Turborepo's publishing guide is written around a library under `./packages` being promoted to published (<https://turborepo.com/docs/guides/publishing-libraries>). uv calls the same thing a *library member* (<https://docs.astral.sh/uv/concepts/projects/init/>). The SDK is imported by another tree in this repo today (`apps/backend/tests/test_sdk_cli.py:26-28`), which is exactly the edge that makes it a package.

**1.3 A polyglot repo must not adopt a JS workspace root just because it has a `apps/` folder.**
If Turborepo ever orchestrates this repo, Python members are listed explicitly because "every matched directory must contain a `pyproject.toml`" (<https://docs.astral.sh/uv/concepts/projects/workspaces/>), and Turborepo's Python support is flagged experimental (<https://turborepo.com/docs/guides/tools/python>). Adopting a root `package.json` + `turbo.json` today buys caching for one JS package. Skip it; revisit when a second JS package exists.

**1.4 Data and weights live outside git; only small fixtures are committed.**
Cookiecutter Data Science v2 gitignores `data/` and treats raw data as immutable (<https://cookiecutter-data-science.drivendata.org/>). DVC: "No data tracked by DVC should ever be pushed to the Git repository" (<https://dvc.org/doc/start/data-management/data-versioning>). GitHub warns at 50 MiB, blocks at 100 MiB, and asks for repositories under 1 GB (<https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github>). This repo already ships 19.8 MB `epoch*.pt` checkpoints and a 6.8 MB GIF in git (§2.4).

**1.5 Docs: do not pre-create Diátaxis folders, do not duplicate a document, do not bury health files.**
Diátaxis explicitly warns against "empty structures for tutorials/howto guides/reference/explanation with nothing in them" (<https://diataxis.fr/how-to-use-diataxis/>). ADRs are append-only: a reversed decision is kept and marked superseded (<https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>). `README`, `CONTRIBUTING`, `SECURITY` are recognised only at `.github/`, root, or `docs/` (<https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file>). The OpenAPI document is tooling input, not a doc page, and must not exist twice (<https://openapi-generator.tech/docs/usage/>).

**1.6 Hygiene: one root `.gitignore`, immutable `rev` pins, no path filters on required checks.**
Canonical patterns come from `github/gitignore` Python and Node templates (<https://github.com/github/gitignore/blob/main/Python.gitignore>, <https://github.com/github/gitignore/blob/main/Node.gitignore>). pre-commit requires `rev` to be an immutable ref (<https://pre-commit.com/#using-the-latest-version-for-a-repository>) and recommends `--all-files` in CI (<https://pre-commit.com/#usage-in-continuous-integration>). A skipped path-filtered workflow leaves required checks "Pending" and blocks the PR (<https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs>). Renames are reconstructed at diff time at 50% similarity, per-file-pair, capped by `diff.renameLimit` (default 1000) (<https://git-scm.com/docs/diff-options>, <https://git-scm.com/docs/git-config>).

---

## 2. Audit of the repository as it is

### 2.1 Every top-level entry

| Entry | Tracked | On disk | Referenced by | Verdict |
|---|---|---|---|---|
| `apps/backend/` | 268 | 737 files / 61.8 MB | CI env `BACKEND_APP`, `tools/ld-task:23`, compose ×2, 322 backlog cards | keep |
| `apps/frontend/` | 231 | 12,722 files / 241.6 MB | CI env `FRONTEND_APP`, `tools/ld-task:22`, compose, 370 backlog cards | keep |
| `apps/worker/` | 3 | 3 | 4 backlog cards, `docs/STANDARDS.md` | keep |
| `apps/inference/` | 12 | 12 | compose profile, `deploy/.env.example` | keep |
| `apps/sdk/` | 6 | 6 | `tools/gen_sdk.py:22`, `apps/backend/tests/test_sdk_cli.py:26-28`, 7 cards + INDEX + FILE-OWNERSHIP | move to `packages/sdk` (§5) |
| `apps/api/` | 0 | 209 files / 70.1 MB | nothing | **delete**: 100% residue (§2.2) |
| `apps/web/` | 0 | 12,483 files / 236.6 MB | nothing | **delete**: 100% build output (§2.2) |
| `api/` | 0 | 7 files / 0.16 MB | nothing | **delete**: dead prototype (§2.3) |
| `web/` | 0 | 11,348 files / 153.7 MB | nothing | **delete**: dead prototype (§2.3) |
| `sam3_auto_label/` | 540 | 96,188 files / 21.8 GB | 41 tracked files (§6.2) | move to `ml/sam3_auto_label/` |
| `yolo26_ppe/` | 148 | 7,014 files / 6.9 GB | 95 tracked files (§6.3) | move to `ml/yolo26_ppe/` |
| `pipeline_cli.py` | 1 | 0.1 MB | `auto_label.sh`, 8 docs, 4 tests | move to `ml/` |
| `auto_label.sh` | 1 | 4 KB | `setup.sh`, 8 docs | move to `ml/` |
| `setup.sh` | 1 | 8 KB | `README.md`-family docs | move to `ml/` |
| `data/` | 81 | 1,447 files / 1.6 GB | offline pipeline only, never the app (§2.5) | keep at root, ignore new bytes |
| `reports/` | 2 | 4 files | `docs/OPENCODE_PM_RULES.md:12` | move to `research/reports/` |
| `research_notes/` | 8 | 16 files | none tracked | move to `research/notes/` |
| `design/` | 0 | 165 files / 46.8 MB | none | gitignore (§2.6) |
| `design-ref/` | 0 | 58 files / 34.5 MB | `tools/README.md` | already ignored, keep |
| `docs/` | 30 | 445 files / 3.4 MB | everything | keep, no restructure (§3.4) |
| `tests/` | 12 | 36 files | `pytest.ini testpaths` | keep, relabel in ADR 0003 |
| `tools/` | 12 | 19 files | CI `tools` job, pre-commit | keep, commit the 3 untracked ones |
| `deploy/` | 3 | 3 files | compose, Caddy | keep |
| `.github/workflows/ci.yml` | 1 | 1 | — | keep, extend (§7.6) |
| `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage` | 0 | small | — | ignored, delete from disk |
| `.claude/` | 0 | 33,953 files / 13.1 GB | — | fully ignored; delete a stale worktree only after `git worktree prune` |
| `.superpowers/` | 0 | 1,264 files / 114 MB | PM rules, ledger | fully ignored by `.superpowers/sdd/.gitignore` (`*`); local-only by design |
| `.devin/` | 0 | 2 | — | ignored |

### 2.2 `apps/api/` and `apps/web/` — pre-rename residue, 307 MB

The rename `apps/api → apps/backend` and `apps/web → apps/frontend` moved the *tracked* files and left everything untracked behind:

- `apps/api/` contains **zero source files**. Every `.py` is a `__pycache__/*.cpython-311.pyc`; the rest is `.pytest_cache/`, `.ruff_cache/`, the runtime store `data/` (including `data/.secret`), and a stray 66.5 MB `rtdetr-l.pt`.
- `apps/web/` contains **no source files at all**: `dist/`, `node_modules/`, `tsconfig.tsbuildinfo`.

Neither is ignored by `.gitignore` (verified with `git check-ignore -v`: `apps/api/app/main.py`, `apps/web/node_modules`, `apps/api/rtdetr-l.pt` all resolve to nothing). A single `git add -A` would commit 24,692 files, 307 MB, a 66 MB model, and a live `LD_SECRET`. **This is the highest-severity finding in the audit.**

### 2.3 `api/` and `web/` — the superseded prototype

`.gitignore:85-88` already labels them: `# Old LabelDesk prototype (superseded by apps/)`. The 2026-11-03 `repo-audit.md` verified file by file that `api/main.py` is the pre-router monolith (30 routes vs 218 tracked handlers), `api/auth.py` is an older subset, and every `web/src` file is a strict subset of its `apps/frontend` replacement. They are still not ignored as directories (`api/main.py`, `web/package.json` resolve to no rule), so they carry the same `git add -A` hazard.

### 2.4 Tracked blobs that violate §1.4

| Path | Size | Note |
|---|---|---|
| `yolo26_ppe/models/archive/.../weights/epoch{0,50,100,150,200,250}.pt` | 19.8 MB each | LFS-routed by `.gitattributes`, still 6 checkpoint dumps of one run |
| `.../best.pt`, `.../last.pt` | 5.2 MB each | same run |
| `.../best.onnx` | 9.6 MB | generated export |
| `sam3_auto_label/sam3/assets/dog.gif` | 6.8 MB | vendored asset |
| `data/raw/**` | 81 files | real blurred face captures (PII), not fixtures |

Removing these from history is a rewrite and is explicitly out of scope (§11). Stopping new ones is in scope: `tools/check_large_files.py:20` already fails a commit that adds `data/`, `yolo26_ppe/models/` or `sam3_auto_label/checkpoints/` — it must learn the new prefixes in the same step that moves them.

### 2.5 Two unrelated things are called `data/`

- `LD_DATA_DIR` (default `apps/backend/data`) is the **app's runtime store**: `config.py:36` defines it, every adapter reads it, and many backend test modules patch it. Not touched by this plan.
- Repo `data/` is read **only** by the offline pipeline: `pipeline_cli.py` (17 refs), `sam3_auto_label/setup.py:639`, six `yolo26_ppe/scripts/pipeline/*.py`, and `tests/integration/test_yolo_training.py`.

Keeping repo `data/` at the root is therefore safe and correct: no application code reads it.

### 2.6 Untracked trees that are one `git add -A` away from the index

| Path | Files | MB | Currently | Action |
|---|---|---|---|---|
| `design/` | 165 | 46.8 | not ignored | ignore (local design workspace, same class as the already-ignored `design-ref/`) |
| `apps/frontend/artifacts/` | 19 | tracked | not ignored | leave tracked (QA evidence), ignore for future artefacts |

`.claude/` and `.superpowers/` are already fully ignored (`.claude/worktrees/`, `.claude/settings.local.json`, and `.superpowers/sdd/.gitignore` = `*`); they need no rule, only discipline about not adding one. `design/` is the only large unignored tree left.

---

## 3. How far the repo is from ADR 0001

| ADR 0001 target | Today | Gap |
|---|---|---|
| `apps/frontend, backend, worker, inference, sdk` | all five exist and are correctly named | `sdk` is in the wrong bucket for its role (§9.2) |
| `packages/` shared code | does not exist | no shared code exists either; the SDK is the only importable artefact |
| `deploy/`, `tools/`, `tests/`, `docs/` | match | none |
| `ml/` = `yolo26_ppe` + `sam3_auto_label` | still at root | not started |
| `research/` = reports + notes | `reports/` + `research_notes/` at root | not started |
| `data/` = datasets task worktrees skip | at root, 81 files tracked | ignore rules missing |
| "The layout is a convention, not enforced by tooling" | true | §7.6 adds the enforcement that is cheap |

So: two of eight decisions landed (the app-folder rename), six are open, and ADR 0001 itself needs one correction (`sdk`) plus one clarification (`tests/`).

### 3.1 Deliberate deviations from ADR 0001, and why

| ADR 0001 says | Plan says | Reason |
|---|---|---|
| `apps/sdk` | `packages/sdk` | the SDK is published and imported, not deployed (§1.2); `packages/` otherwise stays empty forever |
| `packages/` = shared code | contains only the SDK today | no other shared code exists; an empty `packages/` teaches nothing (§1.1, Diátaxis' "don't create empty structures" spirit) |
| `ml/` = the two pipeline dirs | `ml/` also owns `pipeline_cli.py`, `auto_label.sh`, `setup.sh` | they are the ML layer's entry points; root then holds only ecosystem files (§3.3) |
| `research/` = reports and research notes | plus nothing else | `docs/research/` **stays in `docs/`** — it is product research that feeds 384 backlog cards, and there is no docs build to exclude it from (§3.4) |
| `tests/` = cross-app tests | `tests/` = repo-level pipeline tests | the 12 files test the pipeline, not the app; relabelling the ADR is cheaper than moving them and re-deriving `REPO_ROOT` |

### 3.2 `docs/research/` stays put

Moving it would rename the paths of 384 working backlog cards and break every reference in `.superpowers/` ledgers for zero functional gain. Lane C's exclusion advice (MkDocs `exclude_docs`) does not apply: this repo has no docs site (`docs/README.md` is previewed with Markdown Preview Enhanced). The boundary is documented instead: `docs/research/` = product and competitive research that shapes the roadmap; `research/` = provider-side reports and investigation notes.

### 3.3 The root becomes ecosystem-only

After this plan the root holds: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `THIRD_PARTY_LICENSES.md`, `CODEOWNERS`, `.gitignore`, `.gitattributes`, `.pre-commit-config.yaml`, `pytest.ini`, `.github/`, and the eight directories. That matches the health-file precedence rule (§1.5) and removes the last three loose layer entry points.

### 3.4 `docs/` is not restructured

No `docs/tutorials|how-to|reference|explanation` folders are created: Diátaxis warns against exactly that (§1.5), and this repo's docs are a mixed spec/architecture/runbook set with no docs site. What the plan *does* fix: the two stale folder names in `apps/README.md`, the `apps/sdk` path in `docs/adr/0002` and `docs/architecture/overview.md`, and one index link per moved directory (step 7).

---

## 4. Target tree

```text
E:/02_Projects/auto_label/
├── apps/                                deployables only
│   ├── backend/                         FastAPI + SQLAlchemy, embedded job worker, pytest suite
│   ├── frontend/                        React 19 + Vite 6 + Tailwind v4 (TypeScript)
│   ├── worker/                          labeldesk-worker, pip package run on a GPU box
│   └── inference/                       standalone self-hosted inference container
├── packages/                            imported, never deployed alone
│   ├── README.md                        one-paragraph rule: deployable → apps/, imported → packages/
│   └── sdk/                             labeldesk-sdk: Python client + CLI (was apps/sdk)
├── ml/                                  the ML layer and its entry points
│   ├── README.md                        what lives here, and that models/weights are not committed
│   ├── pipeline_cli.py                  (was pipeline_cli.py)
│   ├── auto_label.sh                    (was auto_label.sh)
│   ├── setup.sh                         (was setup.sh)
│   ├── sam3_auto_label/                 (was sam3_auto_label/)
│   └── yolo26_ppe/                      (was yolo26_ppe/)
├── research/                            provider-side material, not product docs
│   ├── README.md                        boundary with docs/research/
│   ├── reports/                         (was reports/)
│   └── notes/                           (was research_notes/)
├── data/                                offline pipeline datasets; new bytes ignored
├── deploy/                              compose, Caddyfile, env template
├── tools/                               scripts apps and tests need
├── tests/                               repo-level pipeline tests
├── docs/                                spec, architecture, ADRs, runbooks, product research
│   ├── adr/                             0001, 0002, 0003 (new)
│   ├── design/ architecture/ pipeline/ qa/ runbooks/ sdlc/ superpowers/
│   └── research/                        roboflow-parity (384 cards), beyond-roboflow — unchanged
├── .github/workflows/ci.yml
├── .gitignore  .gitattributes  .pre-commit-config.yaml  CODEOWNERS  pytest.ini
└── README.md  CONTRIBUTING.md  SECURITY.md  CHANGELOG.md  THIRD_PARTY_LICENSES.md
```

Removed from disk (untracked, dead): `apps/api/`, `apps/web/`, `api/`, `web/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage`.

---

## 5. Move table

`git mv` throughout. "Files whose content changes" counts the tracked files that must be edited in the same commit; "code/config" is the subset that can turn a suite red (the rest are prose paths in `docs/`). The two large-tree counts are approximate to ±2; the per-file lists in §6 are exact.

| # | From | To | Tracked files | Files whose content changes | Of which code/config | Step |
|---|---|---|---|---|---|---|
| 1 | `apps/sdk/` | `packages/sdk/` | 6 | 8 | 3 | 2 |
| 2 | `sam3_auto_label/` | `ml/sam3_auto_label/` | 540 | ~31 | ~13 | 4 |
| 3 | `yolo26_ppe/` | `ml/yolo26_ppe/` | 148 | ~26 | ~12 | 5 |
| 4 | `pipeline_cli.py` | `ml/pipeline_cli.py` | 1 | ~14 | 4 | 6 |
| 5 | `auto_label.sh` | `ml/auto_label.sh` | 1 | (same commit as 4) | — | 6 |
| 6 | `setup.sh` | `ml/setup.sh` | 1 | (same commit as 4) | — | 6 |
| 7 | `reports/` | `research/reports/` | 2 | 3 | 0 | 3 |
| 8 | `research_notes/` | `research/notes/` | 8 | (same commit as 7) | — | 3 |

Total: **8 moves, 707 tracked files, 1 history-preserving rename per move.** The remaining "content changes" are prose paths in `docs/` and `README.md`; the 13 + 12 + 4 code/config files are the ones that can turn a suite red, and both gates catch them.

| Delete from disk (untracked, no history to lose) | Evidence |
|---|---|
| `apps/api/` (209 files, 70.1 MB) | zero source files; caches + `data/.secret` + stray `rtdetr-l.pt` (§2.2) |
| `apps/web/` (12,483 files, 236.6 MB) | `dist/` + `node_modules/` + `tsconfig.tsbuildinfo` only (§2.2) |
| `api/` (7 files) | `.gitignore:85` calls it superseded; monolith replaced by 218 router handlers (§2.3) |
| `web/` (11,348 files, 153.7 MB) | every `src/` file is a strict subset of `apps/frontend` (§2.3) |
| `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage` | caches |

Deletion requires owner confirmation per `CONTRIBUTING.md` rule 3 ("Never delete untracked files that you did not create"). Alternative if the owner prefers zero deletion: `Move-Item` them to `E:/02_Projects/ld-archive/2026-11-17-pre-layout/` first.

| Gitignore (keep on disk, block the index) | Rule added |
|---|---|
| `design/` | same class as the already-ignored `design-ref/` |
| `apps/frontend/artifacts/` | future QA screenshots; the 19 tracked ones stay |
| `data/**` except `data/README.md` | stop new dataset bytes (§1.4) |
| `ml/**/data/`, `ml/**/models/`, `ml/**/artifacts/` | stop new weights and run output |
| generic `node_modules/`, `dist`, `coverage`, `.vite/`, `*.tsbuildinfo`, `.env` + `!.env.example` | canonical Python/Node templates (§1.6) |

---

## 6. Every reference that must change

### 6.1 Step 2 — `apps/sdk` → `packages/sdk`

| File | Line | Change |
|---|---|---|
| `tools/gen_sdk.py` | 22 | `OUT = REPO_ROOT / "packages" / "sdk" / ...` |
| `tools/gen_sdk.py` | 5-6 | usage docstring (`cd packages/sdk`) |
| `apps/backend/tests/test_sdk_cli.py` | 26-28 | `REPO_ROOT / "packages" / "sdk"` instead of `APP_ROOT / "sdk"` |
| `apps/sdk/README.md` | 9 | `pip install -e packages/sdk` |
| `CODEOWNERS` | 16 | `/apps/sdk/` → `/packages/sdk/` |
| `docs/adr/0002-front-back-contract.md` | 13 | `apps/sdk/labeldesk/_generated.py` → `packages/sdk/...` |
| `docs/architecture/overview.md` | 32, 79 | SDK row and generator sentence |
| `README.md` | 17 | status table row |
| `docs/research/roboflow-parity/backlog/*` | see §10 | 7 cards + `INDEX.md` (4 lines) + `_FILE-OWNERSHIP.md` (5 lines) |

### 6.2 Step 4 — `sam3_auto_label/` → `ml/sam3_auto_label/`

| File | Line(s) | Change |
|---|---|---|
| `apps/backend/app/config.py` | 79 | default of `LD_SAM_ROOT` |
| `apps/backend/app/services/segment.py` | 118 | comment only (`sam3_auto_label/src/config.py`) |
| `apps/backend/app/adapters/sam3_ad.py` | — | none: verified, it reaches the pipeline through `SAM_ROOT` |
| `tests/conftest.py` | 28 | `repo_root / "ml" / "sam3_auto_label" / "src"` |
| `tests/integration/test_sam_batch.py` | 17, 23, 24, 56, 73, 123, 160, 188 | checkpoint and `src` paths |
| `tests/unit/test_provenance.py` | 29, 55, 67, 86, 105, 127, 141, 154, 167, 180, 193, 214, 228, 240, 256, 278 | 16 `sys.path` inserts |
| `tests/unit/test_config_static.py` | 46, 53 | docstring + `setup.py` path |
| `tools/check_large_files.py` | 20 | `FORBIDDEN_PREFIXES` → `ml/sam3_auto_label/checkpoints/` |
| `tools/ld-task` | 26, 33 | `ml` sparse profile lists `sam3_auto_label`; update the comment at 26 and the entry at 33 |
| `tools/tests/test_ld_task.py` | 96, 217, 275 | fixture paths (must match the fixture's own tree) |
| `README.md` | 18, 42, 47 | status row, tree, "approved target" paragraph |
| `docs/DEPLOY.md` | 70 | `--sam-root sam3_auto_label` |
| `docs/adr/0001-*`, `docs/00-overview.md`, `docs/01-requirements.md`, `docs/README.md`, `docs/architecture/{01,02,03,overview}.md`, `docs/clone_plan.md`, `docs/labeldesk-plan.md`, `docs/pipeline/{02,03}.md`, `docs/qa/qa-test-design.md`, `docs/sdlc/{01,02,03,10}.md`, `data/README.md` | many | prose paths |
| `.gitignore` | 9, 10, 14, 15, 18, 91 | venv, checkpoint, zip, `dinov3` rules |

### 6.3 Step 5 — `yolo26_ppe/` → `ml/yolo26_ppe/`

| File | Line(s) | Change |
|---|---|---|
| `apps/backend/app/config.py` | 81 | default of `LD_PRETRAINED_DIR` |
| `apps/backend/app/seed_v2.py` | 34-35 | `MODEL_RUN` |
| `apps/backend/app/adapters/ultralytics_ad.py` | 19 | comment |
| `tools/prefetch_weights.py` | 30 | `DEFAULT_PRETRAINED_DIR` |
| `tools/check_large_files.py` | 20 | `ml/yolo26_ppe/models/` |
| `tools/ld-task` | 33 | sparse profile `ml` |
| `tools/tests/test_ld_task.py` | 95, 129, 175, 183, 216, 266, 274 | fixture paths |
| `tests/conftest.py` | 44, 51 | `01_prepare_dataset.py`, `focal_patch.py` |
| `tests/integration/test_yolo_training.py` | 19, 28, 34, 57, 66, 73, 111, 118, 127, 135 | model/data/artifact dirs |
| `tests/unit/test_config_static.py` | 18 | `MLFLOW_CONFIG` |
| `README.md` | 18, 43, 47, 121 | tree and metric path |
| `docs/DEPLOY.md` | 69 | `--pretrained-dir` |
| `docs/pipeline/05-yolo26-training.md`, `docs/architecture/*`, `docs/sdlc/*`, `docs/qa/*`, `data/README.md` | many | prose paths |
| `.gitignore` | 22-34 | mlflow, ultralytics runs, dataset images, cache |

### 6.4 Step 6 — the three root entry points → `ml/`

| File | Line(s) | Change |
|---|---|---|
| `auto_label.sh` | 26-28 | `VENV_PYTHON="${SCRIPT_DIR}/sam3_auto_label/sam3_venv/bin/python"`, `exec ... "${SCRIPT_DIR}/pipeline_cli.py"` |
| `setup.sh` | 29, 130, 133 | `SETUP_PY="${SCRIPT_DIR}/sam3_auto_label/setup.py"`, subshell `cd` |
| `pipeline_cli.py` | 76-83, 704 | split `REPO_ROOT` into `ML_ROOT` + `REPO_ROOT` (§7 step 6), `SAM_DIR`/`YOLO_DIR` off `ML_ROOT`, hint text |
| `tests/conftest.py` | 19-26 | `repo_root / "ml"` on `sys.path` for the `pipeline_cli` fixture |
| `tests/unit/test_path_safety.py`, `test_security_static.py` | fixture-only | no change expected; re-run to prove |
| `README.md`, `docs/00-overview.md`, `docs/01-requirements.md`, `docs/README.md`, `docs/architecture/01-system-architecture.md`, `docs/clone_plan.md`, `docs/labeldesk-plan.md`, `docs/qa/qa-test-design.md`, `docs/sdlc/{01,02,03}.md` | many | `./setup.sh` → `./ml/setup.sh`, `./auto_label.sh` → `./ml/auto_label.sh` |

The 8 tracked `yolo26_ppe/*.sh` helpers and 6 `sam3_auto_label/scripts/*` helpers need no change: they resolve paths relative to themselves and move with their parent.

### 6.5 Step 3 — `reports/` and `research_notes/` → `research/`

| File | Line | Change |
|---|---|---|
| `docs/OPENCODE_PM_RULES.md` | 12 | `reports/` → `research/reports/` (also fix the stale `B:/02_Projects/ld-worktrees` path per the 2026-11-03 audit) |
| `README.md` | — | add `research/` to the layout block |
| new `research/README.md` | — | the boundary with `docs/research/` (§3.2) |

### 6.6 Step 7 — documentation hygiene (no moves)

| File | Change |
|---|---|
| `apps/README.md` (structure block, ~lines 6-10) | still says `api/` and `web/`; replace with `backend/`, `frontend/`, `worker/`, `inference/`, and point at `packages/sdk` |
| `.superpowers/sdd/2026-10-31-labeldesk-v2/OPENCODE.md` (22-38) | structure block: add `packages/sdk`, `ml/`, `research/` |
| `docs/adr/0001-repository-layout.md` | status → `superseded by ADR 0003` (keep the body) |
| `docs/adr/README.md` | new if absent: the ADR index (it does not exist yet; `docs/adr/` holds two files and no index) |
| `docs/superpowers/plans/2026-10-31-labeldesk-v2.md` | one "path mapping" note at the top, body frozen |
| `CHANGELOG.md:28` | historical; leave |
| `docs/STANDARDS.md` §1 | add one line: "deployable code in `apps/`, importable code in `packages/`, ML in `ml/`" |

---

## 7. Ordered steps

### 7.0 The two gates

**MIN gate** (steps 1, 3, 7): `git status --porcelain` shows only intended paths; `git check-ignore -v` returns a rule for every entry in §5's ignore table; `git ls-files | grep -cE '(^|/)(__pycache__|node_modules|dist)/'` → `0`.
**FULL gate** (steps 2, 4, 5, 6, and once at the end): the four commands in §0 item 1, serial, all green.

Rationale for two tiers: a step that touches no executable code cannot break a suite, and a 7-minute suite run per `.gitignore` edit is how a migration gets abandoned half-done. Steps that touch `config.py`, `conftest.py`, `gen_sdk.py` or the frontend get the FULL gate — no exceptions.

**Why move + reference edits go in one commit.** git stores no rename metadata; renames are reconstructed per file pair at 50% similarity with a 1000-pair cap (`git diff-options`, `diff.renameLimit`). The moved files are byte-identical in both cases, so `-M` still reports `rename … (100%)`; the only difference is that a pure-move commit cannot be green (imports break between it and its fix). Splitting would trade a green history for revert granularity that §8 recovers with tags. Keep one commit per step and verify with `git show --stat -M` before pushing.

### Step 1 — hygiene, no moves (MIN gate)

```bash
git tag -a pre-layout-migration -m "layout migration baseline"
```

1. Rewrite `.gitignore` from the canonical Python + Node templates, keeping every existing repo-specific rule (venv, checkpoint, DVC-less dataset rules) in a clearly marked section.
2. Add the ignore table from §5.
3. With owner confirmation, delete the four dead directories (§5) and every cache directory.
4. Commit `tools/README.md`, `tools/cdp.py`, `tools/rf/` and `docs/STANDARDS.md` (untracked but binding; the 2026-11-03 audit recommends committing `STANDARDS.md` first and parameterising the `E:\chrome-rf` path in `tools/README.md`).
5. Commit `docs/layout-migration/` and this plan.

Expected `git status` after: clean except `design/`-class ignored trees.

### Step 2 — `apps/sdk` → `packages/sdk` (FULL gate)

```bash
mkdir -p packages
git mv apps/sdk packages/sdk
```

Apply §6.1. Create `packages/README.md` with the one-paragraph rule. Verify the generator and its guard:

```bash
python tools/gen_sdk.py && git diff --stat packages/sdk/labeldesk/_generated.py   # expect no diff
cd apps/backend && python -m pytest tests/test_sdk_cli.py -q
```

### Step 3 — `research/` consolidation (MIN gate)

```bash
mkdir -p research
git mv reports research/reports
git mv research_notes research/notes
```

Apply §6.5. Note: `research/` is not under `docs/`, so no docs link resolution changes.

### Step 4 — `sam3_auto_label/` → `ml/sam3_auto_label/` (FULL gate)

```bash
mkdir -p ml
git mv sam3_auto_label ml/sam3_auto_label
```

Apply §6.2. Then prove the two seams that matter:

```bash
cd apps/backend && python -m pytest tests/test_segment_autocast.py -q
python -m pytest tests/unit/test_config_static.py tests/unit/test_provenance.py -q   # from the repo root
python -m pytest tools/tests -q
```

The directory rename is same-volume and instant, but it also carries 21.8 GB of ignored content (`.venv_windows`, `dinov3`, `checkpoints`). If `Move-Item`/`git mv` has to copy instead of rename, stop and use `robocopy /MOVE` for the ignored subtrees first. Verify nothing ignored entered the index: `git status --porcelain | grep -c '\.venv\|dinov3\|checkpoints'` → `0`.

### Step 5 — `yolo26_ppe/` → `ml/yolo26_ppe/` (FULL gate)

```bash
git mv yolo26_ppe ml/yolo26_ppe
```

Apply §6.3. Then:

```bash
cd apps/backend && python -m pytest tests/test_seed_v2.py -q
python -m pytest tests/integration/test_yolo_training.py -q   # marked integration; expect skip without weights
python tools/prefetch_weights.py --dry-run
```

Keep `LD_PRETRAINED_DIR` and `LD_SAM_ROOT` as the only contract: where the code already reads an env var, change its *default* and nothing else.

### Step 6 — root entry points → `ml/` (FULL gate)

```bash
git mv pipeline_cli.py ml/pipeline_cli.py
git mv auto_label.sh ml/auto_label.sh
git mv setup.sh ml/setup.sh
```

Apply §6.4. `pipeline_cli.py` currently sets `REPO_ROOT = Path(__file__).resolve().parent` twice (lines 77 and 79 — an `if os.name == "nt"` branch that is identical on both sides) and derives `SAM_DIR`, `YOLO_DIR`, `RAW_DIR`, `SAM_OUTPUTS_DIR` from it. In `ml/` that must become two constants:

```python
ML_ROOT = Path(__file__).resolve().parent          # ml/
REPO_ROOT = ML_ROOT.parent                          # repo root, still the parent of data/
SAM_DIR = ML_ROOT / "sam3_auto_label"
YOLO_DIR = ML_ROOT / "yolo26_ppe"
RAW_DIR = REPO_ROOT / "data" / "raw"                # unchanged on disk
```

Keep `REPO_ROOT` as the name the rest of the file uses for `data/`. Then:

```bash
python -m pytest -q                      # repo root: 75 tests
bash -n ml/auto_label.sh && bash -n ml/setup.sh
./ml/setup.sh --check-only               # dry check; must not install anything
```

If `setup.sh --check-only` is not hermetic on this machine, record that and rely on `bash -n` plus a `--dry-run` invocation of the CLI.

### Step 7 — documentation and ADRs (MIN gate)

Apply §6.6, add `docs/adr/0003-repository-layout-v2.md` from §9, flip ADR 0001's status, create `docs/adr/README.md`, add `research/README.md` and `ml/README.md`, and add the path-mapping note to the frozen plan.

Then close the loop: move this plan and its four research files to `research/notes/2026-11-17-layout-migration/` and leave a one-line pointer in `docs/design/`. `docs/` should hold current documents, not the working record.

### Step 8 — enforcement (FULL gate, last)

| Change | Why |
|---|---|
| `.pre-commit-config.yaml`: `ruff` → `ruff-check`, pin `v0.17.3` → a tag matching the CI pin, widen `files:` to `^(apps/backend\|apps/worker\|apps/inference\|packages/sdk\|ml\|tools\|tests)/` once the 196 pre-existing findings are fixed | §1.6; the current `files: ^tools/` gate cannot see app code |
| `.pre-commit-config.yaml`: `check-added-large-files` `--maxkb=2048` → `1024` | §1.4 |
| `.github/workflows/ci.yml`: add a `pipeline` job running `python -m pytest -q` at the repo root, and a `paths`-free `gate` aggregator | the root suite is not in CI today; a required check must never be path-filtered (§1.6) |
| `.github/workflows/ci.yml`: keep `FRONTEND_APP`/`BACKEND_APP` unchanged; add `SDK_DIR: packages/sdk` if a job needs it | single source with `tools/ld-task` |
| `tools/ld-task`: sparse profiles gain `packages/sdk` and `ml` | keeps task worktrees correct after the move |

```bash
pre-commit run --all-files --show-diff-on-failure
git tag -a post-layout-migration -m "layout migration complete"
```

---

## 8. Rollback

1. **Whole migration:** `git revert -n <step-1-sha>^..<step-8-sha>` then one commit, or `git revert -m 1 <merge-sha>` for the merged branch. Prefer reverting the individual commits: reverting a merge commit "declares that you will never want the tree changes brought in by the merge", which poisons any future re-merge of the same branch (<https://git-scm.com/docs/git-revert>).
2. **One step:** each step is one commit, so `git revert <sha>` undoes it. Steps 2-6 are move + refs in one patch; the patch reverses cleanly because the moved files are byte-identical.
3. **Tags:** `pre-layout-migration` and `post-layout-migration` give fixed comparison points: `git diff pre-layout-migration..HEAD --stat`.
4. **Nothing tracked is destroyed by a revert.** The only irreversible act is step 1's deletion of four untracked directories, which git cannot recover, so it needs owner confirmation and the archive-alternative in §5; test the archive path before running it.
5. **Do not `reset --hard`** on a shared branch (<https://git-scm.com/docs/git-reset>).
6. **The rollback path must not be blocked by CI.** Step 8 adds a required aggregator check with no `paths` filter precisely so a revert PR can merge on the worst day.

---

## 9. ADR 0003 draft

Save as `docs/adr/0003-repository-layout-v2.md`.

```markdown
# ADR 0003: Packages, ML layer, and research split

- Status: proposed
- Date: 2026-11-17
- Supersedes: ADR 0001 in part (the `apps/sdk` location, the `tests/` description, and the `packages/` scope)
- Owner decision: the 2026-11-17 directive to reorganise once one working branch remains

## Context

ADR 0001 fixed one repository with one directory per deployable app, plus `packages/`, `ml/`, `research/`, `data/`, `deploy/`, `tools/`, `tests/` and `docs/`. The app-folder decision landed: `apps/backend` and `apps/frontend` are renamed. Four did not: `ml/` and `research/` do not exist, `packages/` was never created, `data/` grew 81 tracked files with no ignore rules, and the pre-rename directories `apps/api/` and `apps/web/` were left on disk as 307 MB of untracked residue that `.gitignore` does not cover.

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
```

---

## 10. Parity backlog cards whose paths change

`docs/research/roboflow-parity/backlog/` holds 384 cards. **No card's own path changes** — the backlog is not moved (§3.2). What changes is the file paths *named inside* them.

| Card | Lines naming a moved path | Path named |
|---|---|---|
| `INDEX.md` | 1123, 1124, 1130, 1194 | `apps/sdk/labeldesk/{client,cli,config}.py` |
| `_FILE-OWNERSHIP.md` | 79, 89, 117, 255, 256 | same, plus `apps/sdk/README.md`, `_generated.py` |
| `T-022.md` | 38, 39 | `apps/sdk/labeldesk/{client,cli}.py` |
| `T-075.md` | 37, 47, 67, 68 | same |
| `T-342.md` | 22, 36, 38, 40, 41, 42 | `apps/sdk/{README.md,labeldesk/*}` |
| `T-343.md` | 37, 40, 41, 42 | same |
| `T-344.md` | 36, 39, 40 | same |
| `T-348.md` | 36, 39, 40, 41 | same |
| `T-441.md` | 38, 39, 42, 43, 47 | `apps/sdk/{labeldesk/*,tests/test_auth.py}` |

Also stale, worth fixing while in there: `INDEX.md:135` says "`web/` is frozen; all frontend cards target `apps/frontend`" — `web/` is being deleted, so that sentence becomes "the pre-rename prototype was removed on 2026-11-17".

Everything else in the backlog is unaffected: 322 cards name `apps/backend`, 370 name `apps/frontend`, 4 name `apps/worker`/`apps/inference`, 1 names `deploy/models/`, 2 name `data/` — none of those paths move.

Cards are content-only edits; do them as one `docs:` commit after step 2, so a reviewer sees a single mechanical diff.

---

## 11. What this plan does not do

1. **No history rewrite.** The 19.8 MB checkpoints, the PII in `data/raw/`, and the vendored `sam3/assets/dog.gif` stay in history. `workspace-plan.md:79` already sequences that as a separate, owner-approved `git filter-repo` run with a verified mirror backup.
2. **No `untracking` of tracked data or weights.** Ignore rules affect new paths only; removing tracked files is a content decision with its own review.
3. **No workspace tooling.** No root `package.json`, `turbo.json`, `pnpm-workspace.yaml`, `pyproject.toml` or `uv.lock` (ADR 0003 alternatives).
4. **No Diátaxis restructure of `docs/`**, no docs site.
5. **No `CODE_OF_CONDUCT.md` or `LICENSE`.** Both are missing and both are owner decisions, not layout.
6. **No move of `tests/`**, no rename of `apps/*`, no change to `LD_DATA_DIR`.
7. **No re-running of the 384 backlog cards' content** beyond the SDK path substitution.

---

## 12. Executor verification checklist

Run at the end of every step; the full list at the end of step 8.

1. `git status --porcelain` → only the paths the step intends.
2. `git show --stat -M HEAD` → `rename … (100%)` lines for the moved trees, no content hunks inside moved files.
3. `git diff-tree -r -M -l0 --name-status HEAD` → renames even if a step exceeds `diff.renameLimit`.
4. `git ls-files | grep -c '<old-prefix>/'` → `0` for every old prefix (`apps/sdk/`, `sam3_auto_label/`, `yolo26_ppe/`, `reports/`, `research_notes/`).
5. `git check-ignore -v apps/api apps/web api/ web/ design/ node_modules dist .env` → every one resolves to a rule.
6. `git ls-files | grep -E '(^|/)(__pycache__|node_modules|dist|\.venv)/'` → no output.
7. `git grep -n 'apps/sdk\|sam3_auto_label/\|yolo26_ppe/' -- ':!docs/superpowers' ':!CHANGELOG.md' ':!docs/adr/0001-repository-layout.md'` → only intended references.
8. FULL gate green, serial, in this order: `apps/backend pytest`, root `pytest`, `tools/tests pytest`, `npm test`, `npm run build`.
9. `npm run build` must print no `gen-api-types --check` failure — that single check proves `apps/backend/openapi.json` and `apps/frontend/src/lib/api-types.gen.ts` still agree after the moves.
10. `git tag -l 'pre-layout-*' 'post-layout-*'` lists both annotated tags.
11. `python tools/check_large_files.py --base pre-layout-migration --head HEAD` → "no large files added".
12. `pre-commit run --all-files --show-diff-on-failure` → exit 0.
