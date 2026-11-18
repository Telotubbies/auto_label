# LabelDesk code audit — 2026-11-17

Independent audit lane for branch `feat/labeldesk-v2` at `f6feb09`. Read-only on code: this document and
the ten G3 cards are the only deliverables. Measurement ran on Windows, Python 3.11.9, ruff 0.17.3
(the version CI pins), vulture 2.16, radon 6.0.1, Node 22.20.0, TypeScript 5.7.

Owner directive: **"clean all code, ponytail"** — the smallest code that fully does the job. Nothing here
adds a feature, a flag, an abstraction or a dependency.

Skills applied: `ponytail` (full), `codebase-design`, `plankton-code-quality`, `error-handling`,
`systematic-debugging`, `verification-before-completion`, `vercel-react-best-practices`,
`vercel-composition-patterns`.

---

## 1. Verdict

The codebase is in better shape than its size suggests. Backend average cyclomatic complexity is
**4.95 (A)**, `tsc --noEmit` is **clean**, there are **no dead frontend files** and **no unused backend
dependencies**. What it does have is a long tail of *unowned duplication* and *no lint gate over app
code at all*: 825 ruff findings exist, and two tests actively assert that the gate stays off.

Ten cards (T-050…T-059, wave G3, 22 h) remove an estimated **−1,940 lines**, delete **10 orphan
scripts** (1,510 lines), one npm dependency and one empty test tree, and turn the lint chore in
`progress.md:181` into a real gate. Everything else the audit found is listed in §6 as deliberately
deferred, with the reason.

---

## 2. Measured numbers

Every number below is a command's output, not an estimate.

### 2.1 Size

| Metric | Value | Command |
| --- | --- | --- |
| Backend Python files / bytes | 271 / 2,722,061 | `Get-ChildItem apps/backend -Recurse -Filter *.py` |
| Frontend src files / bytes | 162 / 1,418,879 | `Get-ChildItem apps/frontend/src -Recurse -Include *.ts,*.tsx` |
| Backend test cases collected | 1,519 | `python -m pytest --collect-only -q` |
| Files > 600 lines (backend, incl. tests) | 15 | line count per file |
| Files > 800 lines (backend app) | 2 — `streams/manager.py` 1,093, `services/insights.py` 829 | line count per file |
| Files > 800 lines (frontend) | 5 — `Editor.tsx` 1,288, `Settings.tsx` 1,168, `Auth.tsx` 1,072, `types.ts` 977, `StreamDetail.tsx` 866 | line count per file |

### 2.2 Complexity (`radon cc apps/backend/app`)

| Metric | Value |
| --- | --- |
| Blocks analysed | 1,734 in 152 files |
| Rank distribution | A 1,268 · B 284 · C 120 · D 45 · E 10 · F 7 |
| Average complexity | 4.95 (A) |
| Blocks with CC > 15 | 103 |
| Blocks longer than 50 lines | 61 |
| Blocks longer than 100 lines | 17 |
| Worst five | `versioning.generate` 60, `adapters/refine.label_image` 57, `routers/images._check_ann` 56, `handlers/streams.run_extract_frames` 53, `insights_lineage.build` 53 |

Frontend complexity is not machine-measured (no ESLint/oxlint in the repo); the grep pass found
**35 functions over 50 lines** and a **maximum JSX nesting depth of 17**.

### 2.3 Lint and dead code

| Tool | Command | Result |
| --- | --- | --- |
| ruff (broad, no config exists) | `ruff check --line-length=120 apps/backend` | **825 findings** in 13 rule families (B008 317, I001 168, F401 91, BLE001 68, RUF100 29, RUF059 21, S110 14, S112 7, …) |
| ruff (legacy default set) | `--select E4,E7,E9,F` | **279 findings** (E702 169, F401 91, E402 12, E741 3, F541 2, E731 1, F841 1) |
| ruff (pyflakes only) | `--select F` | **94 findings in 13 files** (91 F401, 2 F541, 1 F841); 79 of the F401s are re-export imports in `models/__init__.py` (67) and `worker.py` (12) |
| ruff config in repo | repo-wide glob | **none** — no `ruff.toml`, no `pyproject.toml` at the root; CI lints `tools/ld-task tools` only |
| vulture | `--min-confidence 80 apps/backend/app apps/backend/tests tools` | 59 findings, **all unused local variables in tests**; zero unused functions/classes in app code |
| tsc | `npx tsc --noEmit` (apps/frontend) | **0 errors** |
| knip / ts-prune / depcheck | `npx --no-install …` | **not installed**; nothing was installed, grep fallback used (below) |
| frontend export scan (grep fallback) | 632 exports in 160 files | 90 unreferenced outside their own file (23 values, 67 types); **2 truly dead** (`ui.tsx:113 Kebab`, `widgetModel.ts:50 MAX_WIDGETS`); **0 dead files** |
| frontend prop scan | 203 components | **4 props never passed by any call site** |
| frontend leftovers | grep | 0 `console.log`/`debugger`, 0 commented-out JSX, 1 orphaned CSS class (`.truncate-th`) |

### 2.4 Dependencies

| Surface | Pins | Removable | Evidence |
| --- | --- | --- | --- |
| `apps/backend/requirements.txt` | 18 direct | **0** | 4 pins have no import but are runtime side-deps: `uvicorn[standard]` (Dockerfile CMD), `psycopg2-binary` (`postgresql://` driver), `python-multipart` (Starlette `Form`/`File` in 9 routers), `opencv-python` (`cv2`, same wheel family). Optional imports (`asyncua`, `boto3`/`azure`/`google`, `rfdetr`, `transformers`, `umap`) are lazily guarded — correct. |
| `apps/frontend/package.json` | 26 entries | **1** — `playwright@^1.64.1` | `@playwright/test` is the real runner and re-exports `chromium`/`request`; the direct pin exists only because 12 hand-rolled scripts import it. |

### 2.5 Duplication (measured by reading every copy)

| Duplicate | Copies | Where |
| --- | --- | --- |
| xywh box IoU | **4** | `services/evaluate.py:250`, `services/insights_eval.py:64`, `services/health_scan.py:79`, `services/suspects.py:43` |
| percentage formatter | **9** | `AdminConsole`, `EvaluationTab`, `qa/shared`, `Overview`, `VersionsOps`, `DatasetHealth`, `HealthCheck`, `Models`, `StreamAnalytics` — three different roundings |
| integer formatter | 3 | `Streams.tsx:37`, `StreamDetail.tsx:17`, `StreamAnalytics.tsx:25` |
| byte formatter | 3 | `Streams.tsx:36`, `EdgeExport.tsx:8`, `StreamDetail` |
| clock formatter | 2, **different units** | `StreamDetail.tsx:20` = seconds, `Panels.tsx:38` = milliseconds |
| chart toolkit | 2 complete | `features/project/insights/Chart.tsx` (240) vs `features/insights/charts.tsx` (~440): both export `ChartTheme`, `useChartTheme`, `ChartCard`, `ChartSkeleton`, and a colour normaliser |
| login helper in tests | **61 functions, 30 distinct bodies** | every `apps/backend/tests/test_*.py` |
| `_schema` fixture in tests | 12 (7 byte-identical) | backend test modules, duplicating `conftest._seeded_database` |
| job-status sets | 4 copies + 12 inline poll predicates | frontend features (drift already visible: `Insights.tsx:30` lacks `cancelling`) |
| `task_30` 404 gate | 6 sites, 4 shapes | `routers/{training,streams,versions,playground,images}.py` |

### 2.6 Gates that do not run

| Gap | Evidence |
| --- | --- |
| No lint gate over `apps/backend` | `ci.yml:6-7` says so; no ruff config exists |
| Two tests assert the gap stays open | `tools/tests/test_tooling_config.py:25,26,28,51-52` — `assert hooks["ruff-check"]["files"] == "^tools/"`, `assert "TODO(lint-chore)" in text`, `assert not any("ruff" in run …)` |
| `apps/inference/tests` (10 tests) never run | no workflow references `apps/inference` |
| `apps/frontend/e2e/core-loop.spec.ts` never run | no workflow references `e2e` or `playwright` |
| Documented `biome check` gate does not exist | `docs/STANDARDS.md:28`, `CONTRIBUTING.md:24`; no `biome.json`, no `@biomejs/*` in `package.json` or the lockfile |
| Root `tests/` is an empty leftover | `git ls-files tests` → 0; 24 orphan `.pyc`, 333,119 B; `ci.yml:2-3` still calls it "the repository-level tests at the root" while the job runs `ml/` |
| 5 Windows-only erasure tests never execute | `apps/backend/tests/test_r1_erasure.py:192,218,247,281,324` `skipif(os.name != "nt")` on an Ubuntu runner |

---

## 3. Findings by category

Each finding cites `file:line`, the evidence, why removal is safe, the risk, and the LOC saved.
Lane detail with verbatim tool output: `lane-1-backend-services-routers.md`,
`lane-2-backend-models-jobs.md`, `lane-3-frontend.md`, `lane-4-tooling-tests-deps.md` (this directory).

### 3.1 Dead code

| # | Finding | Evidence | Safe because | Risk | LOC |
| --- | --- | --- | --- | --- | --- |
| D1 | `deps.RANK` (`deps.py:19`) | repo-wide grep: definition only; `need()` reads `NEED` | never read; its "back-compat for need()" comment is false | low | 2 |
| D2 | `NEED["billing"]`, `NEED["owner"]` (`deps.py:21-28`) | no `need("billing"|"owner")` call site | no caller | low | 2 |
| D3 | `schema.DOMAIN_MODULES` (`schema/__init__.py:29`) | only `models.DOMAIN_MODULES` is read (by `test_z2_split.py:13`); the two disagree in membership | second registry with no reader | low | 2 |
| D4 | `Availability.vram_mb` (`adapters/base.py:16`, set in `sam3_ad.py:18,25`, `tensorrt_ad.py:23`, `vlm_ad.py:83`) | no `.vram_mb` read outside `gpu.py`'s unrelated lease field; `catalog()` drops it | write-only field | low | 4 |
| D5 | `OnnxDetector.task` (`apps/inference/detect.py:331`) | assignment only | write-only attribute | low | 1 |
| D6 | `decode_onnx_output(num_classes=…)` (`apps/inference/detect.py:230,242-253`) | both branches compute `len(names)` | parameter can never differ from the default | low | 6 |
| D7 | `embeddings._own_clip` (`services/embeddings.py:57-73`) | reachable only if `insights_embedding` fails to import; `worker.py:35` imports it at startup | the fallback branch cannot execute in shipping builds | low | 25 |
| D8 | `projects.latest_versions`, `semantic_search._project_tags`, `suspects.KINDS`, `ml.SIZES` | no caller | unused helpers/constants | low | 8 |
| D9 | Unreachable face-blur guard (`handlers/streams.py:105`) | `faceblur._cascade` is `lru_cache`d, so the second guard is unreachable | duplicate condition | low | 2 |
| D10 | `Kebab` (`components/ui.tsx:113`), `MAX_WIDGETS` (`widgetModel.ts:50`), `.truncate-th` (`index.css:96`) | zero references | dead exports/CSS | low | 15 |
| D11 | `DataTable.rowHeader`, `Swatch.dashed`, `SectionShell.innerClassName`, `ProjectSettings.initialTab` | no call site passes them | dead props | low | 8 |
| D12 | `event_search_frames` double index; `ix_stream_events_stream_ts` declared in model and bootstrap | two declarations of one index | duplicate DDL | med (DDL) | 4 |

### 3.2 Duplicated logic

| # | Finding | Evidence | Safe because | Risk | LOC |
| --- | --- | --- | --- | --- | --- |
| U1 | Four xywh IoU bodies | byte-identical in 3 files, same maths in the 4th; `labeling.bbox_iou` is a *different* (clamped) function — do not merge into it | one pure function, four importers | low | 30 |
| U2 | 9 `pct`, 3 `fmtInt`, 3 `fmtBytes`, 2 `fmtTime` | grep; roundings already disagree (1 dp vs integer), `fmtTime` means seconds in one file and milliseconds in another | pure functions, one test file | low-med | 30 |
| U3 | Two chart toolkits | `Chart.tsx:20-95` re-implements `toRgb`/`ChartTheme`/`useChartTheme` from `charts.tsx:32-92` | the duplicated leaf helpers have one behaviour; the two `ChartCard` APIs stay | med | 70 |
| U4 | 61 login fixtures, 30 distinct | e.g. `test_account.py:72`, `test_admin_console.py:26`, `test_alerts.py:40`, `test_api_keys_scopes.py:22`, `test_audit_log.py:27` | one helper in `conftest.py`; the suite is the test | med | 130 |
| U5 | 12 `_schema` fixtures | 7 byte-identical, all superseded by `conftest._seeded_database` | session-scoped fixture already seeds | med | 30 |
| U6 | 3 CUDA-release `_drop` closures, 6 probe preambles | `adapters/{ultralytics,rfdetr,hf}_ad.py` | same body, different module-local name | low | 12 |
| U7 | 12 job-enqueue blocks | routers | two near-identical pairs | low | 20 |
| U8 | Two cache implementations | lane 1 finding 14 | one concern | low-med | 25 |

### 3.3 Over-engineering

| # | Finding | Evidence | Note |
| --- | --- | --- | --- |
| O1 | `Availability.vram_mb` advertises a capability nothing consumes | see D4 | speculative field |
| O2 | `LD_SAM_ENABLED` documents three states, implements two (lane 2 F11) | config read once | trim the doc, not the code |
| O3 | `decode_onnx_output(num_classes)` — a parameter whose only legal value is the other argument | see D6 | speculative option |
| O4 | `PanelError`/`ChartSkeleton`/`ChartCard` in `Chart.tsx` duplicate `ErrorState`/`ChartSkeleton`/`ChartCard` in `charts.tsx` | see U3 | keep both APIs for now; merge only the leaves |

### 3.4 Complexity (top of the 103 blocks over CC 15)

| Function | CC / lines | Smallest seam |
| --- | --- | --- |
| `services/versioning.generate` | 60 / 112 | assign-splits → write-items → hash (3 pure helpers) |
| `adapters/refine.label_image` | 57 / 68 | sam3 and vlm emit loops differ only in a source string |
| `routers/images._check_ann` | 56 / 61 | five independent shape validators, already unit-tested |
| `handlers/streams.run_extract_frames` | 53 / 129 | decode → sample → persist |
| `services/insights_lineage.build` | 53 / 229 | five identical `nodes.append` loops → five mappers |
| `streams/manager._Worker._grab` | 37 | **not planned** — see §6 |

### 3.5 Swallowed errors

Lane 1 found six `except` blocks in data paths that could log one line (`S110` 14 sites repo-wide;
`BLE001` 68, most deliberate at optional-import boundaries). Only the ones a one-line log fixes
without changing control flow are worth a card, and none of them changes a result — they are listed
in lane 1 findings 17 and left out of G3 to keep cards behaviour-preserving.

### 3.6 Corrupt text

`routers/images.py` carries **seven double-encoded strings** — UTF-8 bytes read as cp1252 and
re-encoded. Verified at byte level (`decode('utf-8')` succeeds, but the characters are
`โ€”`, `ยฑ`, `โ\x9c“`): lines 96, 170, 476, 484, 492, 611, 724. Line 611 is the worst: every
approve/reject writes `โ\x9c“ ` or `โ\x9c— Rejected: ` into `Comment.text` in the database. This is the
only file in the repo with the defect (a repo-wide scan over backend, frontend, tools, docs, ml,
packages, deploy found exactly 14 lines, 7 of them in this file and 7 quoting it in the lane report).

---

## 4. Top 20 by LOC saved over risk

| # | Finding | Where | LOC | Risk | Disposition |
| --- | --- | --- | --- | --- | --- |
| 1 | 10 QA driver scripts with no live consumer (1,510 lines, 75 KB) | `apps/frontend/scripts/` | 1,510 | low-med | **T-057** |
| 2 | `Settings.tsx` is 12 page components | `features/settings/Settings.tsx` | 541 moved | low | **T-058** |
| 3 | `Auth.tsx` is 7 page components behind one barrel | `features/auth/Auth.tsx` | ~800 moved | low | deferred §6.3 |
| 4 | `StreamDetail.tsx`: five panels above a 105-line component | `features/streams/StreamDetail.tsx` | ~450 moved | med | deferred §6.3 |
| 5 | Two complete chart toolkits | `insights/Chart.tsx` vs `insights/charts.tsx` | 200 (95 now) | med | **T-059** + deferred merge |
| 6 | `Editor.tsx`: 1,060-line component, 3 clean extractions | `features/editor/Editor.tsx` | ~175 | med | deferred §6.3 |
| 7 | 61 login fixtures, 30 distinct | `apps/backend/tests/` | ~130 | med | **T-056** |
| 8 | 12 `_schema` fixtures | `apps/backend/tests/` | ~30 | med | **T-056** |
| 9 | Four identical box-IoU bodies | 4 services | 30 | low | **T-051** |
| 10 | Dead frontend exports/props/CSS | `ui.tsx`, `widgetModel.ts`, `primitives.tsx`, `ProjectSettings.tsx`, `index.css` | 40 | low | **T-054** |
| 11 | 17 format helpers, 3 roundings, 1 unit collision | 13 frontend files | 30 | low-med | **T-055** |
| 12 | Dead backend surface (D1–D7, `drift` dead probe) | deps, schema, adapters, inference, embeddings, drift | 65 | low | **T-052** |
| 13 | Seven corrupt strings, one written to the DB | `routers/images.py` | 0 | low | **T-053** |
| 14 | 94 pyflakes findings, no gate, 2 tests asserting the gap | `apps/backend`, `tools/tests`, CI, pre-commit | 10 | low | **T-050** |
| 15 | Empty root `tests/`, stale gate docs, redundant `playwright` pin | `tests/`, docs, `package.json` | 0 (333 KB + 1 dep) | low | **T-057** |
| 16 | Duplicate adapter boilerplate (U6) | `adapters/{ultralytics,rfdetr,hf}_ad.py` | 12 | low | deferred §6.3 |
| 17 | Duplicate index declarations (D12) | `models/streams.py`, `bootstrap.py` | 4 | med (DDL) | deferred §6.4 |
| 18 | `workflows.update/restore` take `user_id` and discard it; history blames the creator | `services/workflows.py` | 6 | low | deferred §6.5 (behaviour decision) |
| 19 | Two cache implementations (U8) | services | 25 | low-med | deferred §6.3 |
| 20 | 12 job-enqueue blocks (U7) | routers | 20 | low | deferred (touches files T-050/T-052 own) |

---

## 5. Cards

| Card | Title | Hours | LOC | Files |
| --- | --- | --- | --- | --- |
| T-050 | Gate app code on pyflakes | 3 | ~10 | `ruff.toml` (new), CI, pre-commit, 13 backend files |
| T-051 | One box-IoU helper instead of four | 1.5 | 30 | 4 services + `boxes.py` (new) |
| T-052 | Delete the dead backend surface | 2.5 | 65 | deps, schema, 4 adapters, 2 inference, embeddings, drift |
| T-053 | Repair the seven double-encoded strings | 1 | 0 | `routers/images.py` |
| T-054 | Delete dead frontend exports, props and CSS | 1.5 | 40 | 5 frontend files |
| T-055 | One format module for numbers, bytes, percentages, clocks | 2.5 | 30 | `lib/format.ts` (new) + 13 files |
| T-056 | One login helper and one schema fixture | 3 | 160 | `conftest.py` + 61 test modules |
| T-057 | Remove the empty tests tree, orphan scripts and stale docs | 3 | 1,510 + 1 dep | `tests/`, 10 scripts, `package.json`, 4 docs |
| T-058 | Split `Settings.tsx` | 2 | 541 moved | `Settings.tsx` + 1 new file |
| T-059 | Point project insights at the shared chart helpers | 2 | 95 | `Chart.tsx`, `charts.tsx` |
| **Total** | | **22** | **−1,940 net** | |

Merge order: T-050 → T-053 → T-051 → T-052 → T-054 → T-055 → T-059 → T-056 → T-057 → T-058.
T-050 first because it touches the most files and every later card rebases on it; T-056 after it
because both edit backend test modules; T-058 last because it is the only large-file move.

G3 lands **after** wave G2 (the design audit's six UI cards, T-520–T-525, which joined this backlog in
the same window), and that interaction is declared: T-054 shares `src/index.css` with T-525, and T-055
shares `features/project/Models.tsx` with T-523. Both rebase after G2 and neither restructures its file.

---

## 6. Deliberately not planned

Ponytail says a cleanup must pay for itself. These do not, yet.

### 6.1 `streams/manager.py` (1,093 lines)

~40 tests monkeypatch `app.streams.manager.resolve` and import `_Worker`/`_Tracker` by module path.
A split costs more test churn than the file costs readers. Revisit only when wave F's stream cards
touch it anyway.

### 6.2 `jobs.is_cancelled` vs `worker._cancelled`

They look like a 4-line dedupe. `apps/backend/tests/test_r1_cancel_artifacts.py:81-82` patches them to
*different* values on purpose. Merging them silently guts that test. Not dead, not duplicated — two
deliberate seams.

### 6.3 Large-file moves that need their own lane

`Auth.tsx` (1,072), `StreamDetail.tsx` (866), `Editor.tsx` (1,288). `Editor.tsx` is rewritten by wave B
cards T-120–T-174, so a split now would be re-done; `Auth.tsx` and `StreamDetail.tsx` are the same
shape as T-058 and should land one per merge window to keep the diff reviewable.

Four unused helpers also sit here rather than in a card — `routers/projects.py:539 latest_versions`,
`services/semantic_search.py:31 _project_tags`, `services/suspects.py:17 KINDS`, `services/ml.py:4 SIZES`
(8 LOC): each is a one-line deletion in a file another card owns (T-051 owns `suspects.py`), so bundling
them would cost more review time than the deletion saves.

### 6.4 DDL changes

Removing a column (`Invite.invited_by`, written once, read nowhere) or an index (`event_search_frames`)
is an `ADD COLUMN`-style schema world without `DROP`. The indexes are 4 lines and the column is 2;
neither is worth a migration risk in a cleanup wave.

### 6.5 Behaviour decisions, not cleanups

- `workflows.update/restore` receive `c.uid` and discard it; `_snapshot` stamps the workflow's
  creator, so version history credits the wrong person. Fixing it changes what users see — needs an
  owner/PM call, not a silent cleanup.
- `drift.production_model` probes a 2-arg signature that no longer exists and swallows the
  `TypeError`; the cleanup is in T-052 with a test first.
- Two permission helpers (`deps.need(role)` vs `deps.perm(perm)`) diverge for custom-role grants: a
  bundle granting `project.review` passes `perm` endpoints and 403s on `labeling.py:38`,
  `streams.py:547`, `projects.py:451`. **Security-adjacent**: report to R7 before touching.

---

## 7. Defects found in passing (not cleanup — for PM triage)

These are real bugs the audit hit while measuring. None was fixed; none is hiding in a G3 card
except where noted.

| # | Severity | Defect | Evidence |
| --- | --- | --- | --- |
| B1 | **high** | The worker loop has no supervisor: `_set()`'s `commit` sits outside its `try`, so one transient DB error escaping `run_one` ends the only local executor for the life of the process — the API stays up and jobs queue forever. | `worker.py:142,190-196,270-294`; `daemon=True` thread, no restart |
| B2 | med | `safefetch.post(timeout=…)` is ignored: `_pinned_connection` hardcodes `TIMEOUT`. Both callers pass 5 s and get 10 s. | `services/safefetch.py:68` vs `:58-65`; callers `alerts.py:32`, `webhooks.py:28` |
| B3 | med | Any failed `GET /me` (500, offline) redirects to `/login` while the token is still valid; the store keeps `authed = true`, so the UI holds two contradictory states. | `routes/guards.tsx:36,47,88` |
| B4 | med | `upload()` is the only transport without the 401→refresh retry that `req` and `download` have; with a 15-minute access TTL every upload after 15 minutes fails. It also renders array `detail` as `[object Object]`. | `lib/api/client.ts:77-92` vs `:55`, `:114`; TTL `apps/backend/app/security.py:15` |
| B5 | med | `LD_SMTP_SSL` is read by the mailer but forwarded by neither `docker-compose.yml` nor `.env.example`, so implicit-TLS mail cannot be configured in the deployed stack. `LD_MULTI_TENANT` has the same defect. | `mailer.py:23`, `deploy/.env.example:73`, `deploy/docker-compose.yml:47-52` |
| B6 | med | `LD_OT_ALLOW_CIDR` — the opt-in that permits writes to PLC/plant equipment — is documented in no operator-facing file, while its sibling `LD_STREAM_ALLOW_CIDR` is in all three. | `config.py:156` |
| B7 | low | `Dataset` has no `isError` branch on four queries: a failed image request renders a blank grid with live-looking filters. | `features/project/Dataset.tsx:154-156`; correct pattern at `VideoTimeline.tsx:284` |
| B8 | low | Approve/reject writes a corrupt glyph into `Comment.text` (see §3.6). | `routers/images.py:611` — **T-053** |
| B9 | low | Workflow version history credits the workflow creator for someone else's edit. | see §6.5 |

---

## 8. What would make this audit wrong

- `knip`/`ts-prune`/`depcheck` were not installed, so frontend dead-export detection is grep-based.
  A symbol reached only through a string indirection would be missed; none was found — `routes/lazy.ts`
  uses static `import('@/…')`.
- vulture at 80 % confidence cannot see re-export-only symbols, which is why 79 of the 94 pyflakes
  findings are deliberate. That is a fact about the tool, and T-050 handles it with `# noqa`, not
  deletion.
- No runtime measurement was done: no dev server, no Playwright run, no full backend suite execution
  (collection only). Every "risk: low" above means *statically* low.
