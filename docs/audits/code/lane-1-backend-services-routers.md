# Lane 1 — backend services, routers, streams, handlers, ot

Audit of `apps/backend/app/{services,routers,streams,handlers,ot}` on `feat/labeldesk-v2`.
Read-only: nothing under `apps/` was modified. Every claim below is measured, not inferred; the
throwaway scripts that produced the lists live in `B:/02_Projects/ld-tmp/pytest/lane1_*.py`.

Baseline reused as given: ruff 0.17.3 `ruff check --line-length=120 apps/backend` = 825 findings;
radon 1734 blocks, avg 4.95; vulture 80 → no unused app functions; CI does not lint `apps/backend`
(`.github/workflows/ci.yml:45` lints `tools/` only; a lint chore is pending, `progress.md:181`).

Extra measurements taken for this lane:

| measurement | command | result in scope |
|---|---|---|
| dead top-level names | AST walk, reference count over `app/` + `tests/` + frontend | 4 real (finding 6) |
| dead module constants | AST + ref count | 2 (`ml.SIZES`, `suspects.KINDS`) |
| unused function params | AST + body scan | 23, of which 19 are FastAPI gate markers |
| kwonly params never passed | AST + call-site scan | 1 (`tiling.sliced_predict(merge_iou)`) |
| forward-only wrappers | AST (body = single `return f(...)`) | 58, all but 2 are named queries or test seams |
| cross-file copy-paste | 8-line normalised window hash, different files only | 7 pairs, 3 substantive |
| swallowed excepts | AST (except body: pass/continue/return, no log) | 98 candidates, 6 worth a log |
| TODO/FIXME/`print`/`breakpoint` | grep | **none** |
| files >400 lines (STANDARDS.md:8) | `wc -l` | 15 |

Radon, per function (cc ≥ 15 or length > 50): 106 functions at cc ≥ 15, 52 functions > 50 lines.
The five worst in scope: `versioning.generate` (cc 60, 112 lines), `images._check_ann` (cc 56, 61),
`insights_lineage.build` (cc 53, 229), `handlers/streams.run_extract_frames` (cc 53, 129),
`batch_inference.run` (cc 44, 131).

---

## Finding 1 — `embeddings._own_clip` is a second CLIP loader that can never run

`app/services/embeddings.py:57` (`_own_clip`), called only at `:83`; `_insights()` at `:48`.

**Evidence:** `_load_clip` returns `insights._clip_backend()` whenever `_insights()` is not `None`, and
`_own_clip()` is reached only in the `None` branch. `_insights()` does
`from . import insights_embedding` inside `try/except Exception`. That module is a hard dependency of
the app, not an optional one: `app/worker.py:35` imports `insights_jobs`, which imports
`insights_embedding` at `services/insights_jobs.py:23`, and `services/semantic_search.py:17` imports it
at module level from a router. `insights_embedding` needs only `numpy`/`sqlalchemy` at import time
(`insights_embedding.py:13-20`), both in `requirements.txt`. So in any process that can serve a
request, `_insights()` is never `None`; the `embeddings.py:59-71` body is 13 lines of duplicate model
loading (identical to `insights_embedding._clip_backend`, `insights_embedding.py:114-127`) that no
test exercises — `tests/test_embeddings.py:136` monkeypatches `_insights` to a fake in every test.
The same never-taken branch also owns the no-insights halves of `_cache_path` (`:226-231`),
`_load_cached` (`:234-241`) and `_store_cached` (`:245-252`).

**Why safe:** removing `_own_clip` and the `return _own_clip()` arm changes behaviour only in a state
where the module import already fails, and then `embed_image` raises instead of loading a private
copy — which is what the drift/AL/event-search callers already handle (`drift.features_with_source`
catches and falls back to colour features). Keep `_insights()` itself: it is the test seam.

**Risk:** low. **LOC removed:** ~25 (13 in `_own_clip`, ~12 in the three cache fallbacks).
**Test coverage:** `tests/test_embeddings.py` — covers the insights path only; the removed branch has
no test, so the card needs no new test, but must not touch the `_insights` seam.
**Card candidate:** yes — "drop the private CLIP loader in `services/embeddings`, keep one seam".

---

## Finding 2 — four byte-identical box-IoU implementations

`services/evaluate.py:250`, `services/insights_eval.py:64`, `services/health_scan.py:79`,
`services/suspects.py:43`.

**Evidence:** all four bodies are the same 8 lines (`ax, ay, aw, ah = a` … `return inter / union if
union > 0 else 0.0`); only the annotation differs (`list[float]` vs `tuple`). The cross-file window
finder reports `evaluate.py:250 ↔ insights_eval.py:64` and `health_scan.py:80 ↔ insights_eval.py:65`
as duplicate 8-line runs. `services/labeling.py:22` (`bbox_iou`) is the existing shared helper, and it
is explicitly reused rather than copied (`suspects.py:59` imports `health_scan.box` "avoids a third
copy") — the IoU was the part that got copied anyway.

**Why safe:** moving the *identical* function into one module (e.g. `services/labeling.py` beside
`_clamped_iou`, or a new `services/geometry.py`) and importing it keeps every call site's numbers
bit-identical. Do **not** swap in `labeling.bbox_iou`: it clamps to `[0, 1]` and returns `0.0` for
degenerate boxes, while `_check_ann` accepts coordinates in `[-0.5, 1.5]` (`images.py:457`), so
clamping is a semantics change, not a cleanup. Two further variants stay separate on purpose:
`streams/manager.py:172` (dict, centre-based) and `services/tiling.py:92` (dict) are different input
shapes, and `evaluate._pair_iou` (`:362`) is IoU-type dispatch for pycocotools.

**Risk:** low. **LOC removed:** ~22 (three 8-line copies out, one shared helper stays).
**Test coverage:** `tests/test_evaluate.py`, `tests/test_health.py`, `tests/test_drift.py`,
`tests/test_labeling_qa.py` exercise all four through their public callers.
**Card candidate:** yes — "one `iou_xywh` helper, four call sites".

---

## Finding 3 — the `task_30` tiling gate is written six times, four different ways

`routers/training.py:327` and `:633`, `routers/streams.py:212`, `routers/versions.py:56`,
`routers/playground.py:80`, `routers/images.py:742`.

**Evidence:** every site does "parse `Tiling` → 400 on bad input → 404 when
`is_enabled('task_30', …)` is false", with four shapes: a helper returning `Tiling | None`
(`training._tiling_or_404`), a helper returning a dict and accepting raw settings
(`streams.check_tiling`), two inline blocks (`versions.py:56-63`, `playground.py:80-85`), and one
inline block that re-parses a second form (`images.py:742-748`). The shapes differ in what sits
between the two checks: `versions.py` inserts the project-type rule (`:60-61`), `training.py:633`
runs inside a credit-charging helper, and only `streams.check_tiling` returns the dict form the stream
row stores. A seventh read, `projects.py:500-501`, only advertises the capability and is a different
concern.

**Why safe:** one helper `tiling_or_404(db, ws_id, raw) -> Tiling | None` in `services/tiling.py`,
using the existing `Tiling.parse` messages, reproduces each block exactly (same 400 text, same
`404 "not found"`). `versions.py` keeps its project-type check in front of the call.

**Risk:** low (the 404-before-credit ordering must be preserved — commented at `versions.py:63` and
`training.py:634`). **LOC removed:** ~20.
**Test coverage:** `tests/test_tiling_predict.py`, `tests/test_tiling_version.py`,
`tests/test_streams.py:1398`, `tests/test_editor_assist.py`.
**Card candidate:** yes — "one tiling flag gate".

---

## Finding 4 — `drift.production_model` probes a signature that no longer exists

`app/services/drift.py:294` (probing loop `:296-316`).

**Evidence:** the function wraps `from . import deployments` in `try/except Exception` (same package,
always importable), then loops `for args in ((db, project), (db, project, "production"))` calling
`getter(*args)` inside `try/except TypeError: continue`. `deployments.alias_model` is defined as
`alias_model(db, project, alias)` (`services/deployments.py:129`) — a required third argument — so the
first attempt raises `TypeError` on **every** call — drift scans (`drift.py:398`, `routers/ops.py:34`)
and active-learning runs (`active_learning.py:26,158`) alike. The `getattr(...)` and
`isinstance(m, str)` handling (`:312`) covers return shapes the current function cannot produce.
`grep -rn production_model apps/backend/tests` → no test.

**Why safe:** `from . import deployments` at module top plus one direct
`deployments.alias_model(db, project, "production")` call returns exactly what the surviving branch
returns today, removes two exceptions per scan, and keeps the `status == "ready"` guard and the
newest-ready fallback query.

**Risk:** low on the code, medium on coverage — this path has no test, so the card must add one
(alias set → aliased model wins; alias unset → newest ready model).
**LOC removed:** ~15 plus two silent exception raises per call.
**Test coverage:** none for `production_model`; `tests/test_drift.py` covers `analyse`/`schedule_daily`
and `tests/test_deployments.py:291` covers `alias_model` alone.
**Card candidate:** yes — "call `deployments.alias_model` directly in drift; add the missing test".

---

## Finding 5 — unreachable duplicate face-blur guard inside the frame loop

`app/handlers/streams.py:105-106`.

**Evidence:** `run_extract_frames` fails the job at `:39-42` when `p.face_blur and not
faceblur.available()`, before `cap.read()`. The second check inside the loop is
`if p.face_blur and not faceblur.available(): raise RuntimeError(...)`. `available()` is
`_cascade() is not None` and `_cascade` is `@lru_cache(maxsize=1)` (`services/faceblur.py:23-40`), so
its value cannot change between the two checks. The inner branch can never fire.

**Why safe:** deleting the two lines leaves the outer guard doing the same job. The neighbouring
`if p.face_blur: im, _ = faceblur.blur_faces(im)` at `:107` stays.

**Risk:** low. **LOC removed:** 2.
**Test coverage:** `tests/test_r1_video_privacy.py:77-110` (four face-blur cases),
`tests/test_video_tools.py:290`, `tests/test_image_quality.py:336`.
**Card candidate:** yes, bundled with any `run_extract_frames` split (Finding 13).

---

## Finding 6 — small dead code: three unused helpers, two dead constants, one speculative parameter

- `app/routers/projects.py:539` `latest_versions(db, p)` — **Evidence:** `findstr /s /c:"latest_versions"
  apps\backend\app\*.py apps\backend\tests\*.py` → only the definition. 2 lines.
- `app/services/semantic_search.py:31` `_project_tags(rows)` — same grep: definition only. 3 lines.
- `app/services/ml.py:4` `SIZES = ("n","s","m","l","x")` and `app/services/suspects.py:17`
  `KINDS` — constant-reference scan over `app/` + `tests/`: one reference each (the definition).
- `app/routers/streams.py:23` imports `display_source` from `streams.manager`; ruff
  `--select F401` on the five scope dirs returns exactly this one unused import (only line in scope).
- `app/routers/images.py:749` `from .projects import classes_out` — already imported at `:32`;
  a redundant in-function re-import.
- `app/services/tiling.py:135` `merge_iou: float = MERGE_IOU` — keyword-only param; no caller in
  `app/` or `tests/` passes it (call-site scan). `ost` calls pass `conf`/`classes` only.

**Why safe:** no caller, no test, no external reference; `KINDS` and `SIZES` are plain tuples with no
registration side effect (unlike the flag registry, which is read).
**Risk:** low. **LOC removed:** 8.
**Test coverage:** none for these names (they are unreferenced by definition).
**Card candidate:** yes — one "delete unreferenced names" commit.

---

## Finding 7 — BUG: mojibake in seven user-facing strings (comment prefix, error texts)

`app/routers/images.py:96, 170, 476, 484, 492, 611, 724`.

**Evidence:** the source bytes for the em dash are `\xe0\xb9\x82\xe2\x82\xac\xe2\x80\x9d`
(`python -c` over `read_bytes`), i.e. UTF-8 `—` double-decoded and re-encoded — the file is valid
UTF-8, the *content* is corrupted. Visible strings today:

- `:96` `"no images found (supported: jpg, png, bmp, webp, tif โ€” loose or in a .zip)"`
- `:170` `"max 2000 files per request โ€” the web uploader sends batches"`
- `:476` `"polygon needs 3โ€“10,000 normalised points"`
- `:484` `"obb angle must be a finite number of radians within ยฑ2ฯ€"`
- `:492` `"keypoints need 3โ€“3000 flat normalised x,y,v values (v in 0,1,2)"`
- `:611` comment prefix `"โ "` on approve and `"โ— Rejected: "` on reject — every review comment a
  reviewer writes is stored with a corrupted glyph in front of it
- `:724` `"could not find an object at those points โ€” try clicking nearer its centre"`

`app/services/ocr.py` has Thai text that is correct; `images.py` is the only mojibake file in `app/`
(scan of every `*.py` for `[โ€ยใปง€]` plus Thai ranges).

**Why safe:** replacing each corrupted run with the intended ASCII/UTF-8 text changes no control flow.
`:611` is the only one that writes to the database (a `Comment.text`), and only for new rows.
**Risk:** low for the messages; the comment prefix means existing rows keep the corrupt glyph
(a one-row data fix can be offered separately).
**LOC removed:** 0 (7 lines edited).
**Test coverage:** none — no test asserts these strings (`test_e2e.py:90` posts a comment but never
reads back a review comment prefix).
**Card candidate:** yes — small, and it is a visible defect, so it should jump the cleanup queue.

---

## Finding 8 — BUG: `safefetch.post` ignores its `timeout` argument

`app/services/safefetch.py:68` (`post(url, body, headers, timeout=DEFAULT)`), `:78` → `:58-65`
(`_pinned_connection` hardcodes the module `TIMEOUT`).

**Evidence:** `post` accepts `timeout` and never passes it on: `_pinned_connection(u, ip, port)` builds
`HTTPSConnection(ip, port, timeout=TIMEOUT …)` / `HTTPConnection(ip, port, timeout=TIMEOUT)`. Both
callers pass 5 s and get 10 s (`alerts.TIMEOUT_S = 5.0` at `services/alerts.py:32`,
`webhooks.TIMEOUT_S = 5.0` at `services/webhooks.py:28`, used at `alerts.py:228,242` and
`webhooks.py:121`). A hung receiver therefore blocks an alert/ webhook worker twice as long as
configured; `webhooks.flush_due` delivers serially, so a slow endpoint multiplies it.

**Why safe to fix:** threading `timeout` through `_pinned_connection(u, ip, port, timeout)` and using
it in `post` leaves `_get`/`fetch`/`fetch_bytes` untouched and every other behaviour identical.
**Risk:** low, but this is a behaviour change (shorter worst-case block) — it needs its own test.
**LOC removed:** 0; ~3 lines changed.
**Test coverage:** `tests/test_task24_security.py:105,232` call `post(..., 5)` and assert status, not
the timeout; no test would catch the regression or the fix.
**Card candidate:** yes — fix + one test that asserts the connection is created with the passed timeout.

---

## Finding 9 — the "91 unused imports" number is mostly deliberate re-exports, not dead code

`app/models/__init__.py:8-19` (67 findings), `app/worker.py:28-33` (12), plus
`app/adapters/base.py:4`, `app/models/insights.py:2`, `app/routers/streams.py:23`.

**Evidence:** `ruff check app --select F401` = 82, grouped by file: `models/__init__.py` 67,
`worker.py` 12, `adapters/base.py` 1, `models/insights.py` 1, `routers/streams.py` 1. The
`models/__init__.py` block is the ORM registry (`"""Every name is re-exported here…"""`, `:4-5`) and
the package needs every model imported for `Base.metadata` — deleting those imports breaks table
registration. `worker.py:20-37` already marks its intentional seams with `# noqa: F401  seam`
(`:20,:21,:24,:26,:26,:35,:37`) but the twelve handler imports at `:28-33` lack the marker, so ruff
counts them.

**Why safe:** adding `__all__` to `models/__init__.py` (or a single per-file `F401` ignore) and the
same `# noqa: F401  seam` comment on `worker.py:28-33` changes no runtime behaviour; only
`routers/streams.py:23` is a genuine deletion (Finding 6).
**Risk:** low, and lower than the alternative — deleting the models imports is a hard break.
**LOC removed:** 0 (2 markers + an `__all__`), clears ~79 of the 82 F401s.
**Test coverage:** `tests/test_openapi_contract.py`, `tests/test_env_pinning.py` and the whole suite
would fail loudly if a model stopped being registered.
**Card candidate:** yes — and it should land **with** the pending lint chore (`progress.md:181`), not
before, so apps/backend (untouched by CI today, `.github/workflows/ci.yml:45`) gains a gate in the
same change.

---

## Finding 10 — `versioning.generate`: cc 60, 112 lines, three clean seams

`app/services/versioning.py:95-206`.

**Evidence:** radon `60 112 app/services/versioning.py:95 generate` — the worst function in the lane.
It contains three independent jobs: (a) split assignment + leakage move (`:109-128`), (b) per-image
materialisation — tile, preprocess, augment, write, accumulate `items/per_split/per_class`
(`:130-187`), (c) the canonical hash + manifest write (`:192-203`).

**Why safe:** (a) becomes `_assign_splits(rows, cfg, cls_idx) -> tuple[dict, int]`, (b) becomes
`_write_items(...) -> tuple[list, Counter, Counter, int]`, (c) becomes `_version_hash(...)`; the
cancel checkpoints (`:148`, `:189`) and the `shutil.rmtree` cleanup stay in `generate`, so
cancellation still leaves no ready version.

**Risk:** low (pure relocation, no shared state). **LOC removed:** 0 net; cc 60 → ~12 per helper.
**Test coverage:** `tests/test_parity_guard_area2.py:257`, `tests/test_parity_guard_area4.py:108`,
`tests/test_r1_cancel_artifacts.py:66`, `tests/test_versioning_v2.py` — the cancel case is covered.
**Card candidate:** yes — behaviour-preserving split, no new tests required.

---

## Finding 11 — `insights_lineage.build`: cc 53, 229 lines, five identical node-shaping loops

`app/services/insights_lineage.py:74-302`.

**Evidence:** radon `53 229 app/services/insights_lineage.py:74 build`. The body is five
`for … in …: nodes.append({…})` blocks (batches `:126`, versions `:149`, runs `:187`, models `:222`,
streams `:269`) plus edge emission, all sharing one 10-key node literal (`id/kind/label/sub/created/
counts/metrics/detail/artifacts/log`).

**Why safe:** each loop becomes a pure mapper `_batch_node(b, count) -> dict`,
`_version_node(v, reached, images, anns)`, `_run_node(j, models)`, `_model_node(m)`,
`_stream_node(s, count)`; `build` keeps the queries, the edge conditionals and the final
`node_ids` filter (`:300-301`). No query changes, no ordering changes.

**Risk:** low. **LOC removed:** 0 net; the function drops to ~40 lines and cc ~10.
**Test coverage:** `tests/test_insights_lineage.py` (API-level DAG contract),
`tests/test_flags.py:198` (gate off).
**Card candidate:** yes — the cleanest large-function split in the lane.

---

## Finding 12 — `images._check_ann`: cc 56 for what is five independent shape validators

`app/routers/images.py:460-520`.

**Evidence:** radon `56 61 app/routers/images.py:460 _check_ann`. The body is a dispatch on
`shape.kind` with one self-contained validation block each for bbox (`:469`), polygon (`:473`), obb
(`:478`), keypoints (`:486`) and class, followed by attribute/OCR normalisation (`:496-519`).

**Why safe:** `_shape_bbox(s)`, `_shape_polygon(s)`, `_shape_obb(s)`, `_shape_keypoints(s)` returning
the same normalised dicts, with `_check_ann` keeping the shared id/classId checks and the post-shape
fields. Every `HTTPException` message and code is copied verbatim.

**Risk:** low — and this function is one of the few with direct unit tests.
**LOC removed:** 0 net; cc 56 → ~10 per validator.
**Test coverage:** `tests/test_obb_keypoints.py:134,162` calls `_check_ann` directly;
`tests/test_labeling_qa.py:1130-1194` covers the OCR-enabled branch via the API.
**Card candidate:** yes — do it before any change to shape validation, not after.

---

## Finding 13 — two long job handlers: `run_extract_frames` (cc 53/129) and `batch_inference.run` (cc 44/131)

`app/handlers/streams.py:26-154`, `app/services/batch_inference.py:227-357`.

**Evidence:** radon lists both in the lane's top five. `run_extract_frames` mixes three jobs: opening and
probing the container (`:46-66`), deciding per frame whether to keep it (`:85-101`), and writing the
kept frame — blur, encode, dedupe, store, meter, commit every 10 (`:103-137`). `batch_inference.run`
mixes source preparation (connector vs project images, `:263-297`) with the per-item inference loop and
result serialisation (`:299-356`).

**Why safe:** `run_extract_frames` → `_open_and_probe(v, cap, P)`, `_keep(index, mode, …) -> bool`,
`_store_frame(db, …, data, index) -> bool`; `run` → `_prepare_source(db, …) -> (total, connector,
objects, project_images, out_batch, capacity)` and `_process_one(...)`. Quota raises
(`QuotaExhausted` at `:100`, `:113`), `db.commit()` cadence and progress reporting stay at their
current level.

**Risk:** medium — both run inside a worker with commits and quota side effects; the split must not
move a `commit()` across a raise. **LOC removed:** 0 net.
**Test coverage:** `tests/test_video_tools.py:290`, `tests/test_r1_video_privacy.py`,
`tests/test_image_quality.py:336`, `tests/test_batch_inference.py`, `tests/test_z2_split.py:52`.
**Card candidate:** yes for `batch_inference.run` (pure orchestration); **optional** for
`run_extract_frames` — see Finding 5 for the free 2 lines there.

---

## Finding 14 — two cache implementations for one concern

`app/services/insights.py:91` (`_cached`, hand-rolled `_CACHE` + FIFO trim at `:99`) vs
`app/services/insights_common.py:78` (`cached`, `TTLCache`, per-scope LRU, bounded concurrent builds).

**Evidence:** `insights.py` imports `cached` from `insights_common` (`:18`) and uses it for the model
eval/compare surfaces (`:491`, `:721`), while the dataset aggregates use the local `_cached`
(`:199,:212,:220,:259`). The two have different staleness models: `_cached` is
signature-invalidated only, `cached` adds `CACHE_TTL = 1800`. Both cap at 256 (`insights.py:25`,
`insights_common.py:23`).

**Why it is not a card:** swapping `_cached` onto `cached` would add TTL expiry to the dataset
aggregates — a behaviour change with no defect behind it. The duplication costs nothing today beyond
one reader's confusion. Record the rule ("aggregates: signature-only; model surfaces: TTL") in the
module docstring and move on.

**Risk:** n/a. **LOC removed:** 0. **Test coverage:** `tests/test_insights.py` (cache hit/miss,
signature invalidation). **Card candidate:** no.

---

## Finding 15 — two permission helpers; a custom role that works on one surface 403s on the other

`app/deps.py:88-102` (`can`/`perm` vs `need`), used across the lane.

**Evidence:** `need(role)` is a legacy two-level threshold over `NEED` (`deps.py:21-27`); `perm(perm)`
is the RBAC check (`rbac.has`). Counts in scope: `need` 104 calls, `perm` 58, and eight routers mix
them — `workspaces.py` (14/1), `projects.py` (8/3), `streams.py` (8/3), `training.py` (6/5),
`connectors.py` (4/1), `dashboards.py` (4/2), `versions.py` (3/1), `insights.py` (1/5). The gap is
observable: `rbac.validate_permissions` allows a custom bundle to grant `project.review` (only
`workspace.members`/`workspace.delete` are denied, `rbac.py:46`), and `tests/test_workflows.py:308`
already builds exactly that kind of bundle for `project.infer` and expects it to work — through
`perm`. The same user calling `labeling.review_queue` (`routers/labeling.py:38` `need("reviewer")`),
`streams.patch_event` (`:547`) or `projects.suspect_feedback` (`:451`) gets 403.

**Why being careful matters:** migrating `need → perm` widens access on 104 call sites; that is a
security change, not a cleanup. The behaviour-preserving half is to pin the intended semantics with a
test per surface and only then migrate the endpoints where the grant is meant to apply.
**Risk:** medium (security surface). **LOC removed:** 0.
**Test coverage:** `tests/test_rbac.py:158-169,250`, `tests/test_r1_permissions.py:177`,
`tests/test_nogo_access.py`, `tests/test_workflows.py:299-323` — the RBAC matrix is tested; the
`need`/`perm` divergence is not.
**Card candidate:** yes — "decide and test whether a custom `project.review` grant reaches the
labeling/streams endpoints", med risk, no code deletion.

---

## Finding 16 — `workflows.update`/`restore` take a `user_id` they never use, and history blames the creator

`app/services/workflows.py:194` and `:218` (params), `:163-165` (`_snapshot`).

**Evidence:** both functions accept `user_id: str | None` and never reference it (unused-param scan).
Callers pass a real one: `routers/workflows.py:74` and `:90` pass `c.uid`. `_snapshot` writes
`created_by=wf.created_by`, so every version row of every edit and restore records the workflow's
creator, not the editor. `create` does use it (`:185`).

**Why safe for the narrow card:** dropping the two parameters and their call arguments changes no
output; `test_workflows.py:154-183` asserts versions and notes, not attribution. Attributing snapshots
to the editor is a separate, small improvement (needs a column value that already exists —
`WorkflowVersion.created_by`) and would change stored data, so it should be its own card with a test.
**Risk:** low for the parameter removal; medium for the attribution change.
**LOC removed:** 4.
**Test coverage:** `tests/test_workflows.py` (versioning, restore, permissions, flag-off).
**Card candidate:** yes (parameter removal); attribution as a separate card with a test.

---

## Finding 17 — six silent `except` blocks in data paths that could log one line

`services/insights_embedding.py:225-232`, `services/insights_jobs.py:66-74`,
`services/importers.py:362-369`, `services/segment.py:167`, `services/segment.py:182`,
`services/versioning.py:65-75`.

**Evidence:** produced by an AST scan of every `except` whose body is only `pass`/`continue`/a plain
return with no `log.`/`logger.`/`warn` call (98 candidates in scope). These six drop real inputs with
no trace: a CLIP batch that fails twice loses the row (`insights_embedding.py:227-232`), an unreadable
thumbnail silently leaves the brightness/blur distribution (`insights_jobs.py:73` — the comment says
so, but nothing is logged), a malformed VOC box silently yields no annotations
(`importers.py:368`), an unreadable image during phash grouping silently becomes its own group
(`versioning.py:74`). The others (`drift`, `retention`, `webhooks`, `streams/guard`, `segment`
fallbacks) all carry an explanatory comment and a safe fail-closed default — deliberately left alone.

**Why safe:** adding `log.debug("…", exc_info=True)` (all six modules already have a `log`) changes no
control flow and no return value.
**Risk:** low. **LOC removed:** 0 (6 lines added).
**Test coverage:** `tests/test_insights.py:880-911`, `tests/test_drift.py`,
`tests/test_importers_formats.py` exercise the happy paths; the swallowed paths are not asserted, so
adding a log needs no test change.
**Card candidate:** yes — one commit, six lines.

---

## Finding 18 — files over the 400-line rule: split two, leave one

`docs/STANDARDS.md:8` ("Files that grow past ~400 lines get split along a real seam") and `:18`
("routers stay thin"). Files in scope over 400 lines (line counts measured):

| lines | file | recommendation |
|---|---|---|
| 1093 | `streams/manager.py` | **no card** — see below |
| 829 | `services/insights.py` | **yes** — move the model surfaces out |
| 762 | `routers/images.py` | **yes** — thin the router |
| 689 | `routers/training.py` | optional — sits on adapters/CLI seams, high churn |
| 639 | `services/drift.py` | optional — `_colour_features`/`analyse` are cohesive |
| 575 | `routers/streams.py` | optional |
| 540 | `routers/projects.py` | optional |
| 517 | `services/labeling_ops.py` | no — feature-cohesive |
| 512 | `services/evaluate.py` | no |
| 485 | `routers/auth.py` | no |
| 461 | `services/insights_query.py` | no |
| 442 | `routers/workspaces.py` | no |
| 427 | `services/connectors.py` | no |
| 426 | `services/insights_eval.py` | no |
| 403 | `services/ot.py` | no |

**18a — `services/insights.py` → `services/insights_model.py`.** Evidence: lines 424-829 are exactly
three public functions (`version_diff`, `model_insights`, `model_detections`, `training_insights`,
`compare`) plus their private builders (`_build_model`, `_model_head`, `_eval_files`, `_files_in`,
`_metric_keys`, `_label`, `_build_compare`, `_pareto`, `_disagreement`). Only one module imports them
(`routers/insights_models.py:29,38,47,56`) and no test imports them by name. Moving them and
re-exporting from `insights` (its `__all__` at `:476-484` already lists them) drops the file to ~470
lines with no behaviour change. Risk: low. LOC: 0 net.

**18b — `routers/images.py` is a service, not a router.** Evidence: the module holds
`ingest` (`:85-162`, 78 lines of persistence, quota, dedupe, split assignment), `_check_ann` (`:460`),
`image_out` (`:46`), `_visible`/`_labeler`/`_assigned` (`:57-69`), `_ann_box` (`:645`) — about 280
lines that are not routing. `docs/STANDARDS.md:18` puts this in `services/`. Moving `ingest` +
annotation validation into `services/ingest.py` (imported by `routers/images.py`, `routers/connectors.py`
and `routers/streams.py`'s event path — grep before moving) brings the router to ~480 lines. Risk:
medium (several routers call `ingest`), LOC: 0 net.

**18c — `streams/manager.py`: explicitly not worth it.** Evidence: 40+ test targets monkeypatch
`app.streams.manager.resolve` / reference `app.streams.manager._Worker`, `_Tracker`, `display_source`,
`manager` by module path (`tests/test_streams.py` alone has ~25 of them). Any module split renames
those targets and rewrites the suite for zero behaviour gain; `_Worker` (719 lines) is one lifecycle
object whose state is shared across its methods. Recommend leaving it and recording the reason.

**Card candidate:** yes for 18a (low risk, immediate), yes for 18b (med risk, real standards win),
no for 18c.

---

## Checked and deliberately not reported

- **Feature flags.** All 15 keys in `services/flags.py:21-37` have a backend gate and a UI consumer
  (`require_flag`/`require_workspace_flag` at 26 sites; `FlagGate`/`useFlag` in the frontend); none is
  always-on, and `LD_FLAGS_ON` is used by tests. No dead flag.
- **`GET /api/ws/{ws}/drift` (`routers/ops.py:62`).** The frontend never calls it, but
  `tests/test_drift.py:399` asserts it — a kept API surface, not dead code.
- **`GET /api/gpu` (`routers/registry.py:18`).** Used by `components/shell/TopBar.tsx:18`.
- **Routers.** All 35 modules in `routers/__init__.py:10-23` are mounted; no unregistered router.
- **Error envelopes.** `{"ok": …}` is used consistently (37 sites); the `"error"` keys found in
  routers are job/stream payload fields, not a second error shape.
- **Debug leftovers.** No `TODO`, `FIXME`, `XXX`, `HACK`, `print(` or `breakpoint(` anywhere in
  `app/`.
- **Duplicate routes.** No two routers serve the same method+path.
- **Protocols/factories.** The only `Protocol` is `adapters.base.Adapter` (5 implementations, outside
  this lane); 58 forward-only wrappers are named queries or documented test seams
  (`alerts._post`, `webhooks._post`, `webhooks.check_url` — replaced by tests via monkeypatch).
- **`need()` gate markers.** 19 of the 23 unused parameters are `_gate`/`_u`/`_flag` FastAPI
  dependencies, which are load-bearing in the signature.
