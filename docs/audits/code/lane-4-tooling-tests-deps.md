# Lane 4 audit — tooling, tests, dependencies, CI

Scope: `tools/`, `tools/tests/`, root `tests/`, `apps/frontend/scripts/`, `apps/frontend/tests/`,
`apps/frontend/e2e/`, `packages/`, `.github/workflows/`, `.pre-commit-config.yaml`,
`apps/backend/requirements.txt`, `apps/frontend/package.json`, `apps/worker/`, `apps/inference/`, `deploy/`.

Branch `feat/labeldesk-v2`. Read-only audit: nothing was edited, deleted or installed.

## How this was measured

| # | Command | Result |
|---|---------|--------|
| 1 | `python -m ruff check --line-length=120 apps/backend` | `Found 825 errors. [*] 273 fixable` (exit 1) |
| 2 | `python -m ruff check --line-length=120 apps/backend apps/worker apps/inference packages tests tools` | `Found 836 errors` |
| 3 | `python -m ruff check --select E,F,I,B,UP,SIM --line-length=120 apps/backend apps/worker apps/inference packages tests` | `Found 996 errors` (the rule set `docs/STANDARDS.md:17` claims is active) |
| 4 | `python -m ruff check --select E,F,I,B,UP,SIM --line-length=120 tools/ld-task tools` | `Found 3 errors` — i.e. the documented rule set fails on the one directory CI lints |
| 5 | `python -m ruff check --line-length=120 tools/ld-task tools` | `All checks passed!` (what CI actually runs) |
| 6 | `python -m pytest --collect-only -q` in `apps/backend` (TMP/TEMP/LD_TEST_TMP = `B:/02_Projects/ld-tmp/pytest`) | `1519 tests collected in 5.20s`, exit 0 |
| 7 | `git ls-files tests` | empty — root `tests/` has no tracked file |
| 8 | `Get-ChildItem tests -Recurse -File \| Measure-Object Length -Sum` | 24 files, 333,119 bytes (all `.pyc`) |
| 9 | `git check-ignore -v apps/backend/yolo26n.pt apps/worker/yolo11n.pt apps/frontend/tsconfig.tsbuildinfo .ruff_cache` | all four matched by `.gitignore` |
| 10 | AST scans (script in `B:/02_Projects/ld-tmp/pytest/lane4_*.py`) | fixtures, unused imports, unused functions, duplicate bodies |
| 11 | `node -e "import('@playwright/test').then(m=>console.log('chromium' in m, 'request' in m))"` | `true true` |

## Suites and whether a gate runs them

| Suite | Size | Run by |
|-------|------|--------|
| `tools/tests` | 4 files | CI `tools` job (`ci.yml:49`) + pre-push hook (`.pre-commit-config.yaml:32-37`) |
| `apps/backend/tests` | 1519 tests | CI `api` job (`ci.yml:74`) |
| `ml/tests` | 9 files | CI `pipeline` job (`ci.yml:115`) |
| `apps/frontend/tests` | 197 `node --test` cases | CI `web` job (`ci.yml:95`) |
| `apps/frontend/e2e` | 1 spec (`core-loop.spec.ts`) | **nothing** |
| `apps/inference/tests` | 10 tests | **nothing** |
| `apps/worker` | 224-line CLI, no tests | **nothing** |

---

## Finding 1 — Root `tests/` is an empty leftover, and three places still describe it as the test home

`tests/` (directory), `ci.yml:2-3`, `docs/adr/0003-repository-layout-v2.md:29`, `docs/qa/qa-test-design.md` (18 refs)

**Evidence:**
- `git ls-files tests` → no output. Nothing under `tests/` is tracked.
- `Get-ChildItem tests -Recurse -File` → 24 files, 333,119 bytes, every one a `.pyc` under `tests/__pycache__`,
  `tests/unit/__pycache__`, `tests/integration/__pycache__` (Python 3.11 **and** 3.12 bytecode).
- `git log --oneline -1 -- tests/` → `61671c0 chore(ml): move the ML tests and pytest config into ml/ for the split`.
  The sources now live in `ml/tests/{unit,integration}/`.
- `.github/workflows/ci.yml:2-3` still says: `pipeline (the repository-level tests at the root)`, while the job
  at `ci.yml:113-115` runs `working-directory: ml`.
- `docs/adr/0003-repository-layout-v2.md:29`: "`tests/` means "repository-level tests"".
- `docs/qa/qa-test-design.md` cites `tests/unit/test_path_safety.py`, `tests/integration/test_sam_batch.py`, … 18 times.

**Why safe:** the directory holds no tracked content and no source; deleting ignored `.pyc` files cannot change any
build, test or deploy outcome. The two comment/doc edits are text-only.
**Risk:** low.
**LOC removed:** 0 source LOC; −333,119 bytes on disk (24 generated files). Plus 3 doc/comment lines to correct.
**Test coverage:** none needed — no code. Verify with `git ls-files tests` staying empty afterwards.
**Card candidate:** yes — "delete the orphan `tests/` tree; repoint the ci.yml comment at `ml/tests`; fix the 18 stale
paths in `docs/qa/qa-test-design.md` and the ADR sentence". Shape: 1 delete + 3 text edits.

## Finding 2 — The documented frontend lint gate (`biome check`) does not exist

`docs/STANDARDS.md:28`, `CONTRIBUTING.md:24`

**Evidence:**
- `docs/STANDARDS.md:28`: "Format and lint: Biome (`biome check`), 2-space indent, single quotes."
- `CONTRIBUTING.md:24`: "for TypeScript … `biome check`".
- `git ls-files | Select-String "biome|eslint|prettier"` → nothing. No `biome.json`, no `@biomejs/*` entry in
  `apps/frontend/package.json` or `package-lock.json`, no lint step in `ci.yml`.
- The real frontend gates are `npm run build` (`tsc -b && vite build`, `package.json:9`) and `npm test`.

**Why safe:** correcting the docs to describe `tsc -b` (the actual gate) is text-only; adding Biome is a new pinned
tool and needs its own card.
**Risk:** low (docs) / medium (actually adding Biome: 1 new devDependency + a CI step + first-run findings).
**LOC removed:** 2 doc lines replaced.
**Test coverage:** none; `tools/tests/test_tooling_config.py:55-61` already pins the real web gate and is unaffected.
**Card candidate:** yes — shape: either "replace the Biome sentence with `tsc -b` + `node --test`" (text, 2 lines) or
"add Biome at a pinned version behind a new card". Ponytail says take the text fix until someone wants formatting.

## Finding 3 — The documented ruff rule set is configured nowhere, and would fail if it were

`docs/STANDARDS.md:17`, `.github/workflows/ci.yml:45`, `.pre-commit-config.yaml:23-28`

**Evidence:**
- `docs/STANDARDS.md:17`: "`ruff format` + `ruff check` (rules: E, F, I, B, UP, SIM). Line length 120."
- There is no `ruff.toml`, no `[tool.ruff]` section in any `pyproject.toml` (`pyproject.toml` exists only in
  `apps/worker`, `packages/sdk`, `ml/sam3_auto_label/sam3`), so `--line-length=120` on the command line is the only
  enforced setting.
- Measurement 4 vs 5 above: with the documented selection `tools/ld-task tools` yields
  `3 errors` (`tools/demo_smoke.py:557`, `:598` SIM105; `tools/inference_smoke.py:131` SIM300) — a green CI plus a
  documented rule set that CI does not run.

**Why safe:** adding a `[tool.ruff]` block or a `ruff.toml` changes what the linter reports, not what the code does.
Fixing the 3 findings is behaviour-preserving (`contextlib.suppress`, remove the yoda comparison).
**Risk:** low for the 3 findings; adding the config is medium only if the whole repo is selected at once (996 findings).
**LOC removed:** 0; ~3 changed lines.
**Test coverage:** `tools/tests/test_tooling_config.py:21-29` asserts the current `^tools/` scope and the TODO text, so
it must be updated in the same card (see Finding 5).
**Card candidate:** yes — shape: "add `[tool.ruff]` with `line-length = 120` and the documented select list for
`tools/` only; fix the 3 SIM findings; leave app code to the existing lint chore."

## Finding 4 — The lint-chore TODO's finding count is stale, and no gate lints app code at all

`.pre-commit-config.yaml:19-22`, `.github/workflows/ci.yml:6-7`

**Evidence:**
- `.pre-commit-config.yaml:19-22`: "…once their **196** pre-existing ruff findings are fixed (progress.md:181)".
- Measured now: `apps/backend` alone = **825**; in-scope Python = **836**; the documented rule set = **996**
  (measurements 1-3). The number is off by 4-5×.
- Neither the hook (`files: ^tools/`) nor CI (`ci.yml:45` `tools/ld-task tools`) touches
  `apps/backend`, `apps/worker`, `apps/inference`, `packages/sdk`, `tests`.
- Cost of the gap is visible: 8 unused imports in test modules that F401 would delete (Finding 8).

**Why safe:** the comment is documentation; correcting it cannot change behaviour.
**Risk:** low.
**LOC removed:** 0 (1 comment line corrected).
**Test coverage:** `tools/tests/test_tooling_config.py:28-29` asserts the literal strings `TODO(lint-chore)` and
`progress.md:181` — it will break when the comment is fixed (Finding 5 is the same knot).
**Card candidate:** yes — shape: "re-measure and restate the count; state the repo scope the chore must clear".

## Finding 5 — Two tests assert that the lint gap *stays* open, so the chore cannot land

`tools/tests/test_tooling_config.py:25-29`, `tools/tests/test_tooling_config.py:51-52`

**Evidence:**
```python
# test_tooling_config.py:25-29
assert hooks["ruff-check"]["files"] == "^tools/"
assert hooks["ruff-format"]["files"] == "^tools/"
assert "TODO(lint-chore)" in text
assert "progress.md:181" in text

# test_tooling_config.py:51-52  (inside test_ci_runs_the_full_api_suite)
# TODO(lint-chore): drop this once progress.md:181 adds ruff to the api job.
assert not any("ruff" in run for run in runs)
```
These are regression guards inverted into gap guards: the exact change the backlog wants (widen `files:`, add ruff to
the api job) turns CI red. This is the only place in the repo where a *fix* fails a gate.

**Why safe:** rewriting them to assert the *target* state (or deleting the two negative assertions) changes no
application behaviour — it unblocks a documented chore.
**Risk:** low (test-only), medium if done together with Finding 4 because the count has to be re-measured.
**LOC removed:** 4 assertion lines removed, 1 comment line removed.
**Test coverage:** self — these are the tests.
**Card candidate:** yes — and it should be the *first* commit of the lint chore, not the last: "invert the two
gap-locking assertions to the target state (`files: ^(tools|apps|packages|tests)/`, ruff present in the api job),
then widen."

## Finding 6 — `apps/inference/tests` (10 tests) and the Playwright e2e spec are never run

`.github/workflows/ci.yml` (jobs: `tools`, `api`, `web`, `pipeline`, `gate`, `large-files`),
`apps/inference/tests/test_inference.py`, `apps/frontend/e2e/core-loop.spec.ts`

**Evidence:**
- `Select-String .github/workflows/*.yml -Pattern "inference|e2e|playwright|worker"` → **no matches**.
- `apps/inference/tests/test_inference.py` holds 10 tests plus `apps/inference/requirements-dev.txt`
  (`pytest==8.3.4`, `httpx==0.28.1`) and `apps/inference/pytest.ini` — a complete suite nobody starts.
- `apps/frontend/package.json:12` defines `"e2e": "playwright test"`; `playwright.config.ts` wires both servers
  (`python -m uvicorn app.main:app` + `npm run dev`) and `e2e/core-loop.spec.ts` is 1 spec / 6,021 bytes.
- The public API of the shipped inference image (`/predict`, `/models`, `/healthz`) therefore has zero CI signal,
  and the full-stack smoke (backend + frontend together) has none either.

**Why safe:** adding a job only *reads* the repo; it does not change app behaviour. It does add runner minutes
(~2-4 min for inference once `onnxruntime` is installed; the e2e needs a browser download).
**Risk:** low to add the inference job; medium for e2e (needs `npx playwright install --with-deps chromium` and a
working `python -m uvicorn`, i.e. the api job's dependency install).
**LOC removed:** 0 — this adds ~20 YAML lines. It is the one place where "add" beats "delete", because the tests
already exist and are maintained.
**Test coverage:** +10 inference tests, +1 e2e spec in CI.
**Card candidate:** yes (two separate cards). Shape: card A "inference job: pip install -r apps/inference/requirements.txt
+ requirements-dev.txt, `cd apps/inference && python -m pytest -q`"; card B "e2e job: npm ci, playwright install,
`npm run e2e`". Card A is the cheap one and needs no new tooling.

## Finding 7 — Five Windows-only erasure tests never execute on the Ubuntu runner

`apps/backend/tests/test_r1_erasure.py:192, 218, 247, 281, 324`

**Evidence:**
```python
@pytest.mark.skipif(os.name != "nt", reason="POSIX allows unlinking a file that is still open")
```
CI runs `runs-on: ubuntu-latest` (`ci.yml:33, 53, 78, 99, 124, 142`); every one of these five tests is therefore
skipped on every CI run and only ever runs on a developer's Windows box. They cover the *Windows-only* branch of
the delete/erase code (`409` + row kept when a file is locked) — the platform this product actually ships to.

**Why safe:** the fix is CI configuration, not code. Running the module on `windows-latest` executes the same
assertions on the intended platform.
**Risk:** low — one extra job; the module is self-contained (`_schema` + `SessionLocal`), but a Windows runner cannot
install the Linux-only `libgl1` package, so it needs `opencv-python` wheels only (they ship manylinux/win wheels, so
`pip install -r requirements.txt` works on Windows).
**LOC removed:** 0 (removes 5 permanent skips in practice).
**Test coverage:** +5 tests actually executed.
**Card candidate:** yes — shape: "`erasure-windows` job on `windows-latest`, run
`python -m pytest tests/test_r1_erasure.py -q`, and keep the `skipif` (it is still correct for Linux runs)".

## Finding 8 — Eight unused imports in the backend tests (the bill for Finding 4)

`apps/backend/tests/test_home.py:14`, `test_insights.py:11`, `test_openapi_contract.py:5`,
`test_r1_class_name_safety.py:4`, `test_r1_error_hygiene.py:8`, `test_r1_permissions.py:13` (two names), `:18`

**Evidence:** AST scan, each name occurring exactly once in its file:
- `test_home.py:14 from sqlalchemy import select` — 1 occurrence
- `test_insights.py:11 from datetime import datetime, timezone` — `timezone` 1 occurrence
- `test_openapi_contract.py:5 import sys` — 1
- `test_r1_class_name_safety.py:4 from pathlib import Path` — 1
- `test_r1_error_hygiene.py:8 from sqlalchemy import select` — 1
- `test_r1_permissions.py:13 from sqlalchemy import Text, cast, select` — `Text` (only inside the string `"AS TEXT"`)
  and `cast` unused; `:18` imports `Connector` unused.

**Why safe:** an unused import has no runtime effect here (none is a side-effect import; none is referenced from a
`__all__` or a string annotation).
**Risk:** low. One caution: `test_r1_class_name_safety.py` may import `Path` for an annotation under
`from __future__ import annotations`; the file has no `Path` anywhere, so it is genuinely dead.
**LOC removed:** 8 lines (6 edited import statements).
**Test coverage:** none needed; `python -m pytest --collect-only` still collects 1519.
**Card candidate:** yes — trivial, and it is the visible proof of why the widened ruff (Finding 4) pays for itself.

## Finding 9 — Twelve `_schema` fixtures duplicate the conftest's session-scoped `_seeded_database`

`apps/backend/tests/conftest.py:96-104` vs 12 modules (see list below)

**Evidence:** every module below defines a module-scoped autouse fixture whose body is
`Base.metadata.create_all(engine)` — the same tables `conftest.py:103 bootstrap.init_db()` already created for the
whole session, idempotently:

| file:line | body |
|---|---|
| `test_r1_drift_status.py:16`, `test_r1_erasure.py:12`, `test_r1_error_hygiene.py:16`, `test_r1_remote_finalize.py:20`, `test_r1_remote_reaper.py:15`, `test_r1_upload_privacy.py:23`, `test_r1_video_privacy.py:20` | `Base.metadata.create_all(engine)` (7 byte-identical) |
| `test_r1_bootstrap.py:17` | same, with a local import |
| `test_r1_cancel_artifacts.py:24` | `create_all` + `bootstrap.init_db()` |
| `test_workflow_runner.py:29` | `init_db(); yield` |
| `test_metering.py:29` | `with TestClient(app): yield` |
| `test_worker_schedule.py:16` | `create_all` + `assert "workers" in inspect(...)` (a real regression guard) |

Total: 12 definitions, 34 lines.

**Why safe:** `_seeded_database` is `scope="session", autouse=True` in the same `conftest.py`, so it always runs before
the first test of any module selected from that directory, including a single-module run.
**Risk:** medium — test-suite ordering is the one thing that breaks silently. Delete one fixture at a time, run the
full suite once, and keep two of them: `test_worker_schedule.py:16` (its `inspect` assert is a real guard) and
`test_metering.py:29` (it uses the TestClient lifespan path, not `create_all`).
**LOC removed:** ~30 lines (10 of 12 fixtures), 0 application LOC.
**Test coverage:** the suite itself; verify with `python -m pytest -q` (1519 collected) plus a standalone run of each
touched module (`python -m pytest tests/test_r1_erasure.py -q`).
**Card candidate:** yes, but low priority — shape: "delete 10 `_schema` fixtures, keep `test_worker_schedule.py` and
`test_metering.py`; prove with one full run and one per-touched-module run".

## Finding 10 — 61 module-local login fixtures, 30 distinct bodies: ~130 lines of test boilerplate

`apps/backend/tests/` — `c` (25 defs, 162 lines), `client` (22 defs, 109 lines), `admin` (14 defs, 43 lines)

**Evidence** (normalised bodies compared byte-for-byte after stripping indentation):

| fixture | defs | distinct bodies | largest identical groups |
|---|---|---|---|
| `c` | 25 | 15 | ×6 `test_home.py:26, test_parity_guard_area1.py:36, area2:38, area5:37, area6:40, area7:38`; ×3 `test_adapters.py:22, test_e2e.py:25, test_editor_assist.py:30`; ×3 `test_image_quality.py:35, test_insights.py:40, test_suspects.py:97`; ×2 `test_tiling_predict.py:49, test_tiling_version.py:29` |
| `client` | 22 | 7 | ×6 `test_capabilities.py:16, test_event_search.py:45, test_labeling_qa.py:127, test_ot_outputs.py:70, test_parity_guard_area3.py:33, test_video_api.py:35`; ×6 `test_faceblur.py:41, test_gpu.py:293, test_nogo_access.py:125, test_privacy_api.py:25, test_task25_integration.py:55, test_usage_limits.py:31`; ×5 `test_anomaly.py:117, test_deployments.py:71, test_edge_export.py:33, test_engine.py:36, test_workflows.py:80`; ×2 `test_playground.py:43, test_playground_runtime.py:25` |
| `admin` | 14 | 8 | ×6 `test_admin_console.py:35, test_api_keys_scopes.py:31, test_audit_log.py:42, test_connectors.py:44, test_flags.py:56, test_task24_security.py:29`; ×2 `test_security.py:30, test_webhooks.py:35` |

Also duplicated: `db_ready` (`test_account.py:40`, `test_rbac.py:65`, `test_video_tools.py:272`),
`_own_project_headroom` (3 defs, 42 lines, `test_batch_inference.py:74`, `test_event_search.py:102`,
`test_semantic_search.py:77`), `_database` (`test_active_learning.py:41`, `test_drift.py:35`), `_started`
(`test_audit_log.py:36`, `test_flags.py:50`).

**Why safe:** the duplicate bodies are identical, not merely similar — same `TestClient(app)` context manager, same
token mint, same headers. Copying one body verbatim into `conftest.py` and deleting the identical module-local copies
cannot change what a test does; module-local fixtures still win over conftest if any remains.
**Risk:** medium — 1519 tests sit behind this. Several variants look similar but are *not* identical on purpose
(unique client host for the login rate limiter in `test_streams.py:33`, `test_insights_lineage.py:46`), so only the
byte-identical groups may move.
**LOC removed:** ~130 lines (10 `c` + 15 `client` + 6 `admin` + 2 `db_ready` definitions), 0 application LOC.
**Test coverage:** full suite; the login fixtures are used by ~1100 of the 1519 tests, so a mistake is loud, not silent.
**Card candidate:** yes — the largest single cleanup here. Shape: "move the ×6/×6/×5 `client` and ×6 `c`/`admin`
bodies into `conftest.py` as `client`/`c`/`admin`; delete the module copies; run the suite once."

## Finding 11 — `playwright` is a redundant devDependency next to `@playwright/test`

`apps/frontend/package.json:38`, used by 11 scripts

**Evidence:**
- `package.json:33` `"@playwright/test": "^1.64.1"`, `:38` `"playwright": "^1.64.1"` — same version, and
  `node_modules/@playwright/test/index.mjs` is literally `export * from 'playwright/test'`.
- `node -e "import('@playwright/test').then(m=>console.log('chromium' in m, 'request' in m))"` → `true true`, so every
  `import { chromium, request } from 'playwright'` (11 scripts: `contrast-audit:4`, `deep-link-check:5`,
  `editor-click-flow:6`, `editor-g4-flow:6`, `editor-g5-flow:6`, `g5-baseline:4`, `landing-shot:4`, `nav-drawer-keyboard:10`,
  `nav-legacy-redirects:8`, `ocr-shots:3`, `ot-shot:4`, `qa-shot:7`) works against `@playwright/test`.

**Why safe:** same package version, and `@playwright/test` re-exports the same `chromium`/`request` browser types from
`playwright-core`; the browser binaries are resolved through `playwright-core` either way.
**Risk:** low, with one caveat: **no CI job runs those scripts**, so a bad import would only be caught by hand.
Change one script, run it, then change the rest.
**LOC removed:** 0 source LOC (11 import lines edited), −1 `devDependencies` entry and one duplicate package tree in
`node_modules`.
**Test coverage:** none — this is exactly why the caveat above matters.
**Card candidate:** yes — shape: "switch the 11 scripts to `@playwright/test`, drop `playwright` from
`devDependencies`, `npm ci`, run one script".

## Finding 12 — Eight QA driver scripts have no consumer outside historical SDD reports

`apps/frontend/scripts/{deep-link-check,editor-click-flow,editor-g4-flow,editor-g5-flow,g5-baseline,nav-drawer-keyboard,nav-legacy-redirects,qa-shot}.mjs`

**Evidence** (references searched in `.github/`, `package.json`, `tools/ld-task`, `playwright.config.ts`, `docs/`,
`.superpowers/`, tests):

| script | bytes | referenced by |
|---|---|---|
| `deep-link-check.mjs` | 1,596 | `.superpowers/.../task-18-report.md` only |
| `editor-click-flow.mjs` | 10,663 | `task-17-report.md` only |
| `editor-g4-flow.mjs` | 19,721 | `task-G4-report.md` only |
| `editor-g5-flow.mjs` | 20,632 | `task-G5-report.md` only |
| `g5-baseline.mjs` | 2,240 | `task-G5-report.md` only |
| `nav-drawer-keyboard.mjs` | 6,052 | `task-51-report.md` only |
| `nav-legacy-redirects.mjs` | 3,380 | `task-51-{report,review}.md` only |
| `qa-shot.mjs` | 9,890 | task-23 / task-40 reports only |
| **total** | **74,174** | no CI, no npm script, no current doc |

Kept deliberately, with reasons: `gen-api-types.mjs` (`package.json:8-9` + `tests/api-types.test.mjs:6`),
`ot-shot.mjs` (**`tests/ot-outputs-ui.test.mjs:11` reads its source** and asserts on two of its lines),
`contrast-audit.mjs` / `landing-shot.mjs` / `ocr-shots.mjs` (cited by `docs/` research and the landing briefing).

**Why safe:** deleting files no gate and no current doc references changes no build, test or runtime path. The one
hard constraint is `ot-shot.mjs`, which a test asserts against — it must stay (or the test must change, which is a
different card).
**Risk:** medium — these are the reproduction harnesses for the G4/G5/task-51 QA passes; a reviewer may want to re-run
one. The cheap alternative is a 10-line `apps/frontend/scripts/README.md` index instead of deleting.
**LOC removed:** 74,174 bytes / ~1,050 lines if deleted; 0 if indexed.
**Test coverage:** none of them is covered; `ot-shot.mjs` is *implicitly* covered by the source-scraping test.
**Card candidate:** yes — shape: "either add `scripts/README.md` listing each driver with its task id and the exact
command, or delete the 7 unreferenced drivers and keep `ot-shot.mjs` (test-coupled)".

## Finding 13 — The same 6-line Playwright login preamble is copied into 8 scripts

`apps/frontend/scripts/*.mjs` (`editor-g4-flow.mjs:35-41`, `editor-g5-flow.mjs:31-37`, `editor-click-flow.mjs:40-46`,
`qa-shot.mjs`, `ocr-shots.mjs`, `nav-drawer-keyboard.mjs`, `nav-legacy-redirects.mjs`, `g5-baseline.mjs`)

**Evidence:** `Select-String -Pattern "auth/login"` hits 2 lines in each of 8 scripts; the block is
```js
const api = await request.newContext({ baseURL: base })
const login = await api.post('/api/auth/login', { data: { email, password } })
assert.equal(login.status(), 200, 'demo login failed')
const token = (await login.json()).token
const auth = { Authorization: `Bearer ${token}` }
```
plus the same `WS`/`PR`/`base`/`shots` constants. ~48 duplicated lines. They also duplicate the `check(name, value)`
console helper (`editor-click-flow.mjs:60`, `editor-g4-flow.mjs:55`, `editor-g5-flow.mjs:59`).

**Why safe:** extracting a `scripts/_lib.mjs` with `login(base)`, `WS`, `PR`, `check()` keeps the emitted output and
the assertions identical.
**Risk:** low, but it only pays off if the scripts survive Finding 12. **Do Finding 12 first.**
**LOC removed:** ~40 lines net (48 duplicated − ~8 in the shared module).
**Test coverage:** none (no gate runs these scripts), which is why this is the lowest-value item in this report.
**Card candidate:** no — if Finding 12 keeps them, the shared module is worth ~40 lines and one more file; if it
deletes them, there is nothing left to dedupe. Ponytail: do not do both.

## Finding 14 — Two large-file gates with different thresholds (1024 KB locally, 2048 KB in CI)

`.pre-commit-config.yaml:9-10`, `tools/check_large_files.py:33`

**Evidence:**
- `.pre-commit-config.yaml:9-10`: `id: check-added-large-files`, `args: ["--maxkb=1024"]` (from `pre-commit-hooks v5.0.0`).
- `tools/check_large_files.py:33`: `DEFAULT_MAX_KB = 2048`, and `ci.yml:154` passes only `--base`/`--head`, so CI uses 2048.
- The two gates also differ in kind: the hook checks *staged file size*, the CI script checks *added paths + forbidden
  prefixes/suffixes* (`data/`, `ml/yolo26_ppe/models/`, `*.pt`, `*.onnx`, …).

**Why safe:** aligning the local threshold to the CI one (or dropping the redundant hook, since `check_large_files.py`
is strictly stronger and already tested by `tools/tests/test_check_large_files.py`) changes only *when* a developer is
told, never whether CI blocks.
**Risk:** low — flipping the hook to `2048` makes local commits more permissive (they then pass locally but might hit
the forbidden-suffix rule in CI); dropping the hook means developers learn at push time.
**LOC removed:** 0; 1 line changed (`--maxkb=1024` → `2048`), or 2 lines removed if the hook is dropped.
**Test coverage:** `tools/tests/test_check_large_files.py` (4.8 KB) covers the CI script and is unaffected.
**Card candidate:** yes — shape: "set the hook to `--maxkb=2048` so both gates agree on size; leave the forbidden
prefixes/suffixes to the script."

## Finding 15 — BUG: `LD_SMTP_SSL` is read by the mailer but can never be set through Compose

`apps/backend/app/mailer.py:23`, `deploy/docker-compose.yml:47-52`, `deploy/.env.example:57-63`

**Evidence:**
- `apps/backend/app/mailer.py:23`: `SMTP_SSL = os.environ.get("LD_SMTP_SSL", "0") == "1"` and `:76`
  `cls = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP`.
- `deploy/docker-compose.yml:47-52` forwards `LD_SMTP_HOST/PORT/USER/PASSWORD/FROM/TLS` — **not** `LD_SMTP_SSL`.
- `deploy/.env.example:57-63` does not list it. A grep for `LD_SMTP_SSL` across the repo returns exactly one hit
  (the `mailer.py` line above).
- Compose only injects variables it lists, so a self-hoster on an implicit-TLS provider (port 465 — the common
  consumer/SMTP-relay case) cannot enable it without editing the compose file; setting it in `.env` is silently inert.

**Why safe (to fix):** adding one passthrough line and one documented env var changes no default (`"0"` stays the
default), so plain-text/STARTTLS deployments behave exactly as today.
**Risk:** low.
**LOC removed:** 0 (−0); +1 compose line, +1 `.env.example` line, +1 docs line.
**Test coverage:** no test in `apps/backend/tests` references `smtplib` or `SMTP_SSL` at all, so the TLS/SSL mail
path is uncovered; a fix needs a 5-line test that monkeypatches `smtplib.SMTP_SSL`.
**Card candidate:** yes — **flag as BUG, do not fix in this lane.** Same class, worth fixing in the same card:
`LD_MULTI_TENANT` is in `deploy/.env.example:73` but **not** forwarded by `docker-compose.yml` either, so the
documented self-hosted opt-out (`LD_MULTI_TENANT=0`, `apps/backend/app/services/connectors.py:93-111`) does nothing
for a Compose deployment.

## Finding 16 — ~17 MB of ignored local junk; no committed build output anywhere in scope

Paths: `tests/` (Finding 1), `apps/backend/yolo26n.pt`, `apps/worker/yolo11n.pt`, `*.pytest_cache/`, `__pycache__/`,
`.ruff_cache/`, `apps/frontend/{dist,test-results,tsconfig.tsbuildinfo}`

**Evidence** (`git check-ignore -v` shows the covering rule for every one):

| path | size | covered by |
|---|---|---|
| `apps/backend/yolo26n.pt` | 5,544,453 B | `.gitignore:124` `apps/backend/*.pt` |
| `apps/worker/yolo11n.pt` | 5,613,764 B | `.gitignore:123` `apps/worker/*.pt` |
| `apps/frontend/dist/` | 3.6 MB / 57 files | `.gitignore:26` `dist/` |
| `apps/backend/.pytest_cache/` | 98,719 B | `.gitignore:14,119` |
| `tests/` leftovers | 333,119 B | `.gitignore:8` `__pycache__/` |
| `tools/`, `packages/sdk`, `apps/inference`, `apps/worker` `__pycache__` | 163,000 B | `.gitignore:8` |
| `.ruff_cache/` | ~18 KB | `.gitignore:16` |
| `apps/frontend/tsconfig.tsbuildinfo` | 6,028 B | `.gitignore:36` `*.tsbuildinfo` |
| `apps/frontend/test-results/` | 1 file | `.gitignore:apps/frontend/test-results/` |

`git status --porcelain` shows only two untracked doc directories (`docs/layout-migration/`,
`docs/research/mlflow-parity/`) — **no committed build output, no committed cache, no tracked `*.pt`** in this scope.
(The 8 tracked `.pt` files under `ml/yolo26_ppe/models/archive/` are outside this lane; `check_large_files.py` would
reject re-adding them, and they predate the guard.)

**Why safe:** everything listed is generated or downloaded and ignored; deleting it cannot change a build result.
Both weights are ultralytics downloads that land in the process CWD on first use — the worker asks for them by bare
name (`apps/worker/labeldesk_worker/cli.py:52` returns `yolo11{size}{suffix}.pt`), and nothing in the backend reads
`apps/backend/yolo26n.pt` by path (grep for the literal name: 0 hits).
**Risk:** low — the only cost is re-downloading 11 MB of weights on the next local run.
**LOC removed:** 0; −17 MB on disk.
**Test coverage:** none needed.
**Card candidate:** yes (trivial) — shape: "document one cleanup command in `CONTRIBUTING.md`
(`git clean -Xdf -- apps tools packages tests`) and let it ride with Finding 1".

---

## Unused dependencies

### `apps/backend/requirements.txt` — 18 direct pins, 0 removable

Top-level names were resolved through their import names (`pillow`→`PIL`, `pyjwt`→`jwt`,
`python-multipart`→`multipart`, `opencv-python*`→`cv2`) and grepped across `apps/backend`, `tools`, `ml`, `tests`.

| name | file | evidence | verdict |
|---|---|---|---|
| `fastapi` | `requirements.txt:1` | 56 module imports | keep |
| `uvicorn[standard]` | `:2` | **0 imports**; `apps/backend/Dockerfile:20` `CMD ["uvicorn", ...]`, `tools/ld-task:155` writes the dev command | keep — ASGI runtime side-dep |
| `sqlalchemy` | `:3` | 155 imports | keep |
| `psycopg2-binary` | `:4` | **0 imports**; `deploy/docker-compose.yml:28,62` `DATABASE_URL: postgresql://…`, `app/db.py:1` "Postgres in prod" | keep — DBAPI driver side-dep, loaded by SQLAlchemy from the URL scheme |
| `pyjwt` | `:5` | `app/oidc.py:28`, `app/security.py:10` | keep |
| `python-multipart` | `:6` | **0 imports**; 9 routers use `Form`/`File`/`UploadFile` (e.g. `app/routers/training.py` 21 uses) | keep — Starlette form parser side-dep |
| `pillow` | `:7` | 20 `PIL` imports | keep |
| `numpy` | `:8` | 13 imports | keep |
| `opencv-python-headless` | `:12` | 10 `cv2` imports | keep |
| `opencv-python` | `:13` | same `cv2` module | keep — comment at `:9-11` documents that ultralytics requires the GUI distribution and both must stay on 4.x |
| `ultralytics` | `:15` | 3 imports + 19 `torch` imports | keep (also pulls torch) |
| `httpx` | `:16` | `app/adapters/refine.py:5`, `app/adapters/vlm_ad.py:9` | keep — not test-only |
| `imagehash` | `:17` | `services/insights_jobs.py:13`, `services/versioning.py:62` | keep |
| `cryptography` | `:18` | `services/secretbox.py:15` | keep |
| `defusedxml` | `:19` | `services/importers.py:15` | keep |
| `pycocotools` | `:20` | 5 imports | keep |
| `segno` | `:21` | `app/totp.py:64` | keep |
| `cachetools` | `:22` | `services/insights_common.py:16` | keep |

Optional imports are deliberately unpinned and degrade gracefully — no action: `asyncua` (`app/ot/drivers.py:140`),
`boto3`/`azure`/`google` (`services/connectors.py:141-157`), `rfdetr` (`adapters/rfdetr_ad.py:43`),
`transformers`/`umap` (`adapters/hf_ad.py`, `services/insights_embedding.py:292`), and the SAM `config`/`inference`
modules imported after a `sys.path` insert (`services/segment.py:118-119`). The commented-out block at
`requirements.txt:23-32` already explains this.

### `apps/frontend/package.json` — 26 entries, 1 removable

| name | section | evidence | verdict |
|---|---|---|---|
| `@material/material-color-utilities` | deps | `src/lib/theme.ts:6` | keep |
| `@tanstack/react-query` | deps | 65 refs, e.g. `src/components/shell/AppSidebar.tsx` | keep |
| `@tanstack/react-virtual` | deps | `src/features/project/Dataset.tsx:4`, `src/features/editor/ObjectList.tsx:2` | keep |
| `clsx` | deps | `src/lib/utils.ts:1` | keep |
| `echarts` | deps | 41 refs (`dashboardExport.ts:2`, `WidgetCard.tsx:3`, `charts.tsx:9`) | keep — note: second chart lib next to recharts; consolidation is a feature card, not a cleanup |
| `echarts-for-react` | deps | `src/features/insights/charts.tsx:4`, `project/insights/Chart.tsx:2` | keep |
| `konva` | deps | 0 direct `from 'konva'` imports | keep — **peer** of `react-konva` (`node_modules/react-konva/package.json` → `"konva": "^8 \|\| ^7.2.5 \|\| ^9 \|\| ^10"`), must be listed |
| `lucide-react` | deps | 73 refs, e.g. `src/components/shell/icons.ts` | keep |
| `react` | deps | 390 refs | keep |
| `react-dom` | deps | `src/main.tsx`, `src/features/project/ProjectLayout.tsx:2` | keep |
| `react-konva` | deps | `src/features/editor/Editor.tsx:4`, `playground/Playground.tsx:4` | keep |
| `react-router-dom` | deps | 60 refs | keep |
| `recharts` | deps | `EvalPanel.tsx:2`, `Models.tsx:4`, `Settings.tsx:5`, `qa/Workforce.tsx:4` | keep |
| `tailwind-merge` | deps | `src/lib/utils.ts:2` | keep |
| `zustand` | deps | `src/lib/store.ts:1` | keep |
| `@axe-core/playwright` | devDeps | `scripts/landing-shot.mjs:5`, `ocr-shots.mjs:4`, `qa-shot.mjs:8` | keep |
| `@playwright/test` | devDeps | `playwright.config.ts:1`, `e2e/core-loop.spec.ts:1` | keep |
| `@tailwindcss/vite` | devDeps | `vite.config.ts:3` | keep |
| `@types/react` | devDeps | 0 textual refs | keep — required by `tsc -b` for `react` types |
| `@types/react-dom` | devDeps | 0 textual refs | keep — same |
| `@vitejs/plugin-react` | devDeps | `vite.config.ts:2` | keep |
| **`playwright`** | **devDeps** | 11 scripts import `chromium`/`request`; `@playwright/test` re-exports both (verified at runtime) | **remove** — duplicate of `@playwright/test` (Finding 11) |
| `tailwindcss` | devDeps | `src/index.css:1` `@import "tailwindcss"`, `vite.config.ts` | keep |
| `typescript` | devDeps | no source import; `package.json:9` `tsc -b` | keep — build tool |
| `vite` | devDeps | `vite.config.ts`, `package.json:7,9,10` | keep |

### Other manifests in scope

| file | pin | evidence | verdict |
|---|---|---|---|
| `apps/worker/pyproject.toml:10` | `requests` | `labeldesk_worker/cli.py:20` | keep |
| | `ultralytics` | `cli.py:56,130` | keep |
| | `opencv-python-headless` | `cli.py:112` (`cv2` in `_poly`) | keep |
| | `pillow` | `cli.py:124` | keep |
| `packages/sdk/pyproject.toml:11` | `httpx` | `labeldesk/client.py:12` | keep |
| `apps/inference/requirements.txt:3-8` | `fastapi`, `uvicorn[standard]`, `python-multipart`, `pillow`, `numpy`, `onnxruntime` | `main.py:17-28`, `detect.py` (ort at `detect.py`), `requirements-dev.txt:3-4` for pytest/httpx | all keep (`uvicorn`/`python-multipart` are the same runtime side-deps as the backend) |

---

## Not findings (checked, nothing to remove)

- **Dead fixtures:** none. Every one of the 191 fixtures in `apps/backend/tests` that is never *requested* by name
  (43 of them) is `autouse=True` — verified by AST. `apps/backend/tests/conftest.py` has 3 fixtures, all autouse or
  session-scoped by design.
- **Tests that assert nothing:** an AST scan of the 1384 `test*` functions (pytest collects 1519 cases once
  parametrisation is applied) found 5 with no `assert`/`raises`/`fail`
  (`test_adapters.py:48`, `test_alerts.py:171`, `test_alerts.py:408`, `test_connectors.py:68`,
  `test_r1_connector_ssrf.py:109`). All five are "the call must not raise" checks around
  `validate()`/`notify()`; none is worthless. One wording issue: `test_adapters.py:48`
  `test_every_available_adapter_returns_valid_schema` only exercises the `ultralytics` family because of
  `if ad.probe().ok and fam == "ultralytics"` — the name overstates what it checks (coverage note, not a deletion).
- **Long-dead skips:** no `xfail` anywhere; 6 `skipif` (5 Windows-only, Finding 7) + 1 GPU-only
  (`test_engine.py:759-760`, `LD_GPU_TESTS=1`, no job sets it) + 6 runtime `pytest.skip` guards
  (`test_adapters.py:196-204` slow/offline, `test_ot_drivers.py:234`, `test_r1_permissions.py:140`,
  `test_video_tools.py:283`). All carry a reason and are environment guards, not dead tests.
- **Unused functions in `tools/*.py`, `tools/ld-task`, `packages/sdk`, `apps/inference`, `apps/frontend/scripts` and
  `apps/worker`:** zero. Every module-level function is referenced (AST free-name count), including the 5
  `detect.py` helpers that only `main.py` imports.
- **Leftover debug prints:** none. Every `print`/`console.log` in scope is CLI output (`ld-task:361-447`,
  `check_large_files.py:120-148`, `gen_sdk.py:103`, `export_openapi.py:49`, the `check()` progress helpers in the QA
  scripts). No `pdb`, no `breakpoint()`, no bare `console.log(debugValue)`.
- **Duplicated `_git()` helper** (`tools/ld-task:57` 8 lines, `tools/check_large_files.py:40` 14 lines): real
  duplication, but extracting it needs `importlib` gymnastics because `tools/ld-task` has no `.py` suffix, and the
  two versions differ (`encoding=`/`errors=` vs plain, `LdTaskError` vs `CheckError`). Not worth a shared module —
  **card candidate: no**.
- **Frontend test helper duplication:** `read`/`source` defined 13 times, `lineWith` 3 times
  (`models-permissions:26`, `parity-guard-area4:15`, `project-screen-permissions:20`), `component` twice with
  *different* signatures (`parity-guard-area5:15` vs `area7:13`). A `tests/_helpers.mjs` saves ~12 lines net after 15
  import lines are added — **card candidate: no** (negative value).
- **Duplicated configs:** three `pytest.ini` files (`apps/backend`, `apps/inference`, `ml`) each hold
  `testpaths = tests`; they are per-app and each is required for a standalone run. Nothing to merge.
