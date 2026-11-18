# Lane 2 audit — backend models, schema, job queue, config, adapters, worker CLI, inference

Scope: `apps/backend/app/models/`, `apps/backend/app/schema/`, `apps/backend/app/jobs.py`,
`worker.py`, `config.py`, `db.py`, `deps.py`, `main.py`, `bootstrap.py`, `adapters/`,
`apps/worker/`, `apps/inference/`.
Branch `feat/labeldesk-v2` @ `f6feb09`. Read-only: nothing here was changed.

Baseline reused (not re-run): ruff `--line-length=120 apps/backend` → 825 findings (B008 317,
BLE001 68, F401 91, S110 14, RUF012 11); radon 1734 blocks, avg 4.95 (A); vulture ≥80 clean.
Lane-scoped re-measurements used below: `radon cc -n C` on this lane's paths, an AST scan for
functions ≥45 lines, and targeted greps (every claim below names the grep it rests on).

Rule applied to every finding: behaviour-preserving only. A finding marked **BUG** is a real
correctness defect and is *not* a cleanup — do not fix it here.

---

## Finding 1 — **BUG** the job loop has no supervisor, so one transient error ends the only local executor

`apps/backend/app/worker.py:142-150`, `190-196`, `205-211`, `270-294`

`Evidence:`
- `_set()` runs `db.execute(update(Job)...)` and `db.commit()` **outside** its `try` (only the
  heartbeat call at 145-150 is guarded). A `sqlalchemy.exc.OperationalError` (SQLite "database is
  locked" after the 30 s `timeout` in `db.py:12`, a Postgres serialization failure, a dropped
  connection) propagates.
- `run_one()` calls `_set()` both on the success path (202) and from inside `except Exception`
  (210) — an exception raised by the handler *in the except block* escapes `run_one`.
- `loop()` (277-294) has no `try` around `_claim()` / `run_one()`; its only `try/finally` (288-291)
  refreshes the heartbeat. Nothing restarts the thread: `start_background()` (297-302) creates it
  once with `daemon=True`.
- Second, latent path: `job = db.get(Job, jid)` + `db.expunge(job)` (191-193) sit outside the `try`.
  If the row is gone, `expunge(None)` raises `sqlalchemy.orm.exc.UnmappedInstanceError` (an
  `InvalidRequestError`; verified with SQLAlchemy 2.0.36) and the `except` block then dereferences
  `job.kind` (208), failing a second time. Today `jobs` rows are never deleted (grep
  `delete(Job)` / `db.delete(j` across `apps/backend/app` → 0 hits) and project delete is a soft
  delete (`routers/projects.py:186`), so this path is latent, not live.
- Consequence is the exact failure `assert_handlers_claimed()` was written to prevent (comment at
  `main.py:40-42`): the API keeps serving, `/api/health` stays green, and every job queues forever.

`Why safe:` this is a bug report, not a change. The fix shape (`try/except Exception: log` around
`run_one` inside `loop()`, and moving the row read inside `run_one`'s `try`) adds lines, removes
none, and changes no successful behaviour.

`Risk:` med (a fix touches the hot loop; a wrong fix could swallow real failures silently).

`LOC removed:` −0 (+4 to fix).

`Test coverage:` partial — `tests/test_worker_schedule.py:25-39` drives `loop()` with a stub
`run_one` but never a raising one. **Card must add a test first**: `loop()` survives a `run_one`
that raises, and a claimed-but-missing job row fails the job instead of killing the thread.

`Card candidate:` maybe (bug card, not a cleanup card).

---

## Finding 2 — Dead: `deps.RANK`

`apps/backend/app/deps.py:19`

`Evidence:` `RANK = {"annotator": 1, ...}` is annotated "Kept for back-compat with existing
`need()` call sites", but `Ctx.need()` (97-102) uses `NEED`, not `RANK`. Grep `\bRANK\b` across
`apps/backend/app` and `apps/backend/tests` → only this definition.

`Why safe:` pure module-level data with no reader in app or tests.

`Risk:` low.

`LOC removed:` 1 (plus the back-compat comment on 18).

`Test coverage:` none needed; no test references `RANK`, so nothing can break.

`Card candidate:` yes — batch with Findings 3 and 5 into one "dead module-level registries in
deps/schema" card.

---

## Finding 3 — Dead: `NEED["billing"]` and `NEED["owner"]` are never queried

`apps/backend/app/deps.py:25-26`

`Evidence:` `NEED` has five keys; only `annotator`, `reviewer` and `admin` are ever passed to
`Ctx.need()`. Grep `need\("(billing|owner)"\)` across `apps/backend/app` → 0 hits. The
`k.need("read")` calls in `routers/devapi.py` are a different method (`KeyCtx.need` in
`apikeys.py`), not this table.

`Why safe:` unreachable dict entries.

`Risk:` low — but if `billing`/`owner` are reachable only from a *string* built at runtime, a grep
would miss it. Checked: the only dynamic call is
`c.need(need.get(body.action, "reviewer"))` (`routers/images.py:304`) whose map (303) contains only
`"reviewer"`.

`LOC removed:` 2.

`Test coverage:` `tests/test_rbac.py` exercises admin/reviewer/annotator only; nothing asserts the
billing/owner rows.

`Card candidate:` yes (same card as Finding 2).

---

## Finding 4 — Dead: `Invite.invited_by` is written once and read nowhere

`apps/backend/app/models/identity.py:92` (write at `apps/backend/app/routers/workspaces.py:170`)

`Evidence:` grep `invited_by` across `apps/backend/app` → the model column and the constructor
keyword only. The invite response (`workspaces.py:178`) returns `token`/`email`/`role`/`link`; the
seat check (163) reads `accepted`; there is no GET that lists invites.

`Why safe:` nothing reads the value. Removing the attribute means dropping the `invited_by=` kwarg
at 170 — one line each side. The column itself stays in existing databases (create_all never drops);
a new database simply never gets it.

`Risk:` low (audit trail loss is theoretical — the row already carries `created` and the audit
event at `workspaces.py:172` records the inviter).

`LOC removed:` 2.

`Test coverage:` `tests/test_account.py:244,506` and `tests/test_rbac.py:203,311` create and revoke
invites but never read `invited_by`, so removal is covered by existing round-trip tests.

`Card candidate:` yes — small, and it is the only write-only column found in the identity models.

---

## Finding 5 — Dead: `schema.DOMAIN_MODULES` is a second registry nobody reads

`apps/backend/app/schema/__init__.py:29`

`Evidence:` grep `DOMAIN_MODULES` repo-wide → three hits: this line, `models/__init__.py:21` (read
by `tests/test_z2_split.py:13`), and that test. The schema copy has no reader; `apply()` (32-34)
iterates `STEPS`, and the table-exists test uses `STEPS` too
(`test_z2_split.py:23-25`).

`Why safe:` dead tuple. The two registries also disagree in membership (models has six modules,
schema four), which is exactly the drift the comment at `models/__init__.py:4-5` warns about.

`Risk:` low.

`LOC removed:` 1.

`Test coverage:` none references it; `STEPS` coverage is unaffected.

`Card candidate:` yes (same card as Findings 2-3 — all three are dead module-level tables).

---

## Finding 6 — Dead: `Availability.vram_mb` is set by four adapters and read by nothing

`apps/backend/app/adapters/base.py:16` (set at `sam3_ad.py:18`, `sam3_ad.py:25`,
`tensorrt_ad.py:23`, `vlm_ad.py:83`)

`Evidence:` grep `vram_mb` across `apps/` → every other hit is `gpu.py`'s own lease field or tests
asserting the number passed to `scheduler.lease(...)`. `catalog.catalog()` (58-78) emits
`available`/`reason`/`capabilities`/`license` and drops `av.vram_mb`; no test reads
`probe().vram_mb` (grep `Availability\(.*vram` in tests → 0).

`Why safe:` the field is keyword-only in all four writers, so removing it changes no call shape;
`Availability(False, "…") == Availability(False, "…")` still holds (test_rfdetr_ad.py:190).

`Risk:` low — but this is the value a future "does this model fit the card?" check would want. If
the product intends to surface it, the cheaper fix is to emit it from `catalog()` instead of
deleting it. Deleting is the honest audit answer while nothing reads it.

`LOC removed:` 4 (one field + four keyword args).

`Test coverage:` none reads it; `tests/test_gpu.py` covers the scheduler's own `vram_mb`.

`Card candidate:` yes, but as "wire it up or delete it" — a one-line product decision.

---

## Finding 7 — Dead attribute: `OnnxDetector.task`

`apps/inference/detect.py:331`

`Evidence:` `self.task = meta.get("task", "detect")` is the only mention of `task` in
`apps/inference` (grep `\.task\b` → 1 hit). `predict()` (333-352) branches on output shape, never
on task. `tests/test_inference.py` has no assertion on it.

`Why safe:` write-only attribute on a per-file detector object.

`Risk:` low.

`LOC removed:` 1.

`Test coverage:` none found (no test reads `OnnxDetector.task`).

`Card candidate:` yes — trivially bundled with Finding 8 (same file, same decode path).

---

## Finding 8 — Over-engineering: `decode_onnx_output(num_classes=…)` duplicates `names`

`apps/inference/detect.py:230`, `242-253`, call site `346`

`Evidence:`
- `channels = 4 + num_classes if num_classes else (4 + len(names) if names else None)` (242) —
  both branches compute the same number whenever `names` is non-empty.
- The only caller passes `num_classes=len(self.names) or None` (346), i.e. it is always derived
  from the same dict it sits beside.
- Downstream `nc = num_classes or len(names) or max(1, arr.shape[1] - 4)` (251) has the same
  redundancy.

`Why safe:` a caller that passes `names` alone reaches identical numbers on every path taken by
`tests/test_inference.py:82-104` (neither test passes `num_classes`). Dropping the parameter
removes the `else` branch and three `if num_classes` guards.

`Risk:` low — one edge case: a caller with an *empty* `names` dict and an explicit `num_classes`
would lose the explicit count. No such caller exists.

`LOC removed:` ~6.

`Test coverage:` yes — `test_decode_onnx_output_maps_letterboxed_boxes_back_to_the_image`,
`test_decode_onnx_output_drops_low_confidence_rows`.

`Card candidate:` yes.

---

## Finding 9 — Duplicate index: `event_search_frames` indexes the unique key twice

`apps/backend/app/models/streams.py:93-94`

`Evidence:`
```python
__table_args__ = (UniqueConstraint("project_id", "source", "source_id"),
                  Index("ix_event_search_frames_project_source", "project_id", "source", "source_id"))
```
The unique constraint already creates a unique index over exactly those three columns (SQLite and
Postgres alike), so the second index duplicates it and pays a second write per inserted row.

`Why safe:` every query that can use the plain index is satisfied by the unique index (same leading
columns). New databases simply create one index; existing ones keep the extra index until it is
dropped by hand (no migration is introduced — this is a model-level cleanup).

`Risk:` low. One caveat: dropping the named index from the model does not drop it from a live
database, so no behaviour changes at all — only new databases get the smaller schema.

`LOC removed:` 1 (plus a trailing comma).

`Test coverage:` `tests/test_event_search.py` exercises the table; no test asserts this index's
existence (grep `ix_event_search` in tests → 0 hits).

`Card candidate:` yes — one-line schema cleanup, flagged for whoever owns the migration story.

---

## Finding 10 — Duplicate definition: the `stream_events` index is declared twice

`apps/backend/app/bootstrap.py:75-76` vs `apps/backend/app/models/streams.py:30`

`Evidence:` the model declares `Index("ix_stream_events_stream_ts", "stream_id", "ts")`, which
`create_all` creates for a fresh database; `_init_db()` then runs
`CREATE INDEX IF NOT EXISTS ix_stream_events_stream_ts ...` on every boot. Two sources of truth for
one index.

`Why safe:` deleting the bootstrap statement still leaves the index on new databases (from the
model) and on every existing database (created by this statement on a previous boot).
`tests/test_streams.py:325-330` asserts the index exists, not who created it, so it keeps passing.

`Risk:` low. Note the delete must not be a "migration cleanup" of the index itself — only the
duplicate DDL goes.

`LOC removed:` 2-3 (statement + comment).

`Test coverage:` yes — `test_stream_events_index_covers_stream_and_ts`.

`Card candidate:` yes (bundle with Finding 9 as one "schema duplication" card).

---

## Finding 11 — Over-engineering: `LD_SAM_ENABLED` advertises three states, implements two

`apps/backend/app/config.py:83` (`# auto | 1 | 0`)

`Evidence:` every consumer only distinguishes `"0"`:
`sam3_ad.py:14` (`if SAM_ENABLED == "0"`), `services/segment.py:109,129,148`,
`services/capabilities.py:18` (`SAM_ENABLED != "0"`). Nothing anywhere reads the string `"auto"`
or `"1"` specially, so `LD_SAM_ENABLED=auto` and `=1` are the same value and the documented
tri-state is fiction.

`Why safe:` the cleanup is to document it as a boolean (or rename to `LD_SAM_DISABLED`) — the code
paths do not change. Implementing a real "auto" (probe checkpoint presence) is a feature, not a
cleanup: `sam3_ad.probe()` already degrades to `Availability(False, "SAM checkpoint missing …")`,
which is the behaviour `auto` would have.

`Risk:` low (comment/doc only). `deploy/docker-compose.yml:38,66` sets `"0"`, still valid.

`LOC removed:` 0-1.

`Test coverage:` `tests/conftest.py` and most suites set `LD_SAM_ENABLED=0`; no test exercises
`"auto"` vs `"1"` (which is the point — they are indistinguishable).

`Card candidate:` yes, docs-only.

---

## Finding 12 — Config surface: `LD_OT_ALLOW_CIDR` gates PLC writes and is documented nowhere an operator looks

`apps/backend/app/config.py:152-156` (consumed by `routers/ot.py`, `services/ot.py`)

`Evidence:` name-by-name grep over `deploy/`, `docs/`, `apps/`, `README.md`:

| var | read at | in `deploy/.env.example` | in `deploy/docker-compose.yml` | in `docs/DEPLOY.md` |
| --- | --- | --- | --- | --- |
| `LD_OT_ALLOW_CIDR` | config.py:156 | no | no | no |
| `LD_STREAM_ALLOW_CIDR` | config.py:152 | yes (53) | yes (42) | yes |
| `LD_AL_DAILY_CAP` | config.py:108 | no | no | no |
| `LD_DRIFT_P` / `LD_DRIFT_MAX_SAMPLES` / `LD_DRIFT_MIN_SAMPLES` | config.py:111-113 | no | no | no |
| `LD_MAX_UPLOAD_MB` | config.py:139 | no | no | no |
| `LD_RETENTION_CHECK_S` | config.py:140 | no | no | no |
| `LD_TRAIN_DEVICE` | config.py:88 | no | no | no (`apps/README.md:53` names it in a list only) |

The asymmetry matters: the stream allowlist (read-only camera egress) is documented in three
places; the identical opt-in that permits a **write to plant equipment** is documented only in
`.superpowers/sdd/…/task-40-*.md` review notes and one parity backlog file
(`docs/research/roboflow-parity/backlog/T-696.md`). An operator following `deploy/.env.example`
cannot discover how to enable OT output, and the failure mode at runtime is a refusal
(`services/ot.py` uses `OT_ALLOW_CIDR`), not a hint.

`Why safe:` documentation-only change (add the commented block next to `LD_STREAM_ALLOW_CIDR`, or
delete the setting — but it is load-bearing for a shipped feature, so document it).

`Risk:` low to change, **med to leave as is** (operators will widen `LD_MULTI_TENANT` or the stream
list instead of naming the plant network).

`LOC removed:` 0 (+4 doc lines).

`Test coverage:` `tests/test_ot_outputs.py` covers the CIDR gate itself; `tests/test_r1_worker_coverage.py`
already greps `deploy/.env.example` and `docs/DEPLOY.md`, so a doc assertion can be added cheaply in
the same style.

`Card candidate:` yes — this is the highest-value finding in this file even though it removes no code.

---

## Finding 13 — Complexity: `label_image` is CC 57 / 68 lines, with two near-identical emit loops

`apps/backend/app/adapters/refine.py:121-188` (measured: `radon cc -s` → `F (57)`; AST → 68 lines)

`Evidence:` the sam3 branch and the vlm branch repeat the same four lines with different inputs:

| line | sam3 branch (145-152) | vlm branch (162-173) |
| --- | --- | --- |
| class id | `cid = chosen.id if (prompt and chosen) else by_name.get(p.get("class"))` | identical, on `refined` |
| display name | `name = chosen.name if (prompt and chosen) else p.get("class")` | identical |
| VLM verify | `if verify and not _verified(vlm, im, p, name): continue` | identical, on `refined` |
| append | `_ann(p, cid, ..., "sam3")` | `_ann(refined, cid, ..., "vlm+sam3")` |

Only the *source string* and the SAM refinement differ. Extracting
`_emit(pred, cid, name, im, project_type, source)` collapses both loops by ~10 lines and drops the
CC of the function materially.

`Why safe:` a pure extraction inside one function; the two call sites keep their existing inputs,
their `continue` guards and their source labels. Behaviour on `prompt`/`class_ids` combinations is
unchanged because the extracted lines are byte-identical logic.

`Risk:` med — this is the auto-label hot path (worker `run_autolabel` and the editor preview both
call it). Do it only with the tests green; do not "improve" the branch conditions while in there.

`LOC removed:` ~10 (net, including the helper).

`Test coverage:` yes — `tests/test_autolabel_v2.py` (incl. a fake `parse_prompt` adapter at 169),
`tests/test_tiling_predict.py`; the job-level path is covered by `tests/test_r1_cancel_artifacts.py`.

`Card candidate:` yes — one card, behaviour-preserving extraction only.

---

## Finding 14 — Duplicate adapter boilerplate: three copies of the same CUDA-release unloader, six copies of the probe preamble

`apps/backend/app/adapters/ultralytics_ad.py:116-121`, `rfdetr_ad.py:85-90`, `hf_ad.py:63-68`
(probe preamble: `ultralytics_ad.py:163-166`, `tensorrt_ad.py:18-23`, `rfdetr_ad.py:193-196`,
`hf_ad.py:248-253`, `sam3_ad.py:21-22`, `vlm_ad.py:76-83`)

`Evidence:`
- The `_drop` closure is byte-identical three times:
  ```python
  def _drop(_model):
      try:
          import torch
          torch.cuda.empty_cache()
      except Exception:            # CPU-only installs have nothing to free
          pass
  ```
  (only the parameter name differs).
- The probe preamble repeats `if importlib.util.find_spec("<mod>") is None: return
  Availability(False, "<mod> not installed")` in every family adapter.

`Why safe:` moving `_drop` to `base.py` as one `free_cuda(_obj)` and calling it from the three
`_load`s preserves behaviour exactly (same lazy `import torch`, same swallow). A `_missing(module)`
helper returning `Availability | None` reduces the probe blocks without changing any probe order —
but only do the probe part if the ordering (`ultralytics` before `tensorrt`, `torch` before the
checkpoint check in `sam3_ad`) is kept verbatim.

`Risk:` low for `_drop`, med for the probe rewrite (probe *order* is user-visible in
`GET /api/models` reason strings).

`LOC removed:` ~12 for `_drop`; ~10 more for the probe preamble if done.

`Test coverage:` `tests/test_gpu.py:243-254` (lease args), `tests/test_hf_ad.py:93`,
`tests/test_rfdetr_ad.py:455`, `tests/test_vlm.py` (probe/sleep), `tests/test_task25_integration.py`
(probe reasons). Coverage exists for both halves.

`Card candidate:` yes for `_drop` only (small, mechanical). The probe rewrite is not worth a card on
its own.

---

## Finding 15 — **Do not merge**: `jobs.is_cancelled` and `worker._cancelled` look duplicated but are two deliberate seams

`apps/backend/app/jobs.py:9-11` and `apps/backend/app/worker.py:153-155`

`Evidence:` the bodies are identical (`select(Job.status).where(Job.id == jid) == "cancelling"`), so
a dedupe looks free. It is not: `tests/test_r1_cancel_artifacts.py:81-82` patches them to
*different* values in the same test —

```python
monkeypatch.setattr(jobs, "is_cancelled", lambda _jid: False)   # the handler itself starts
monkeypatch.setattr(worker, "_cancelled", lambda _jid: True)    # then the user cancels
```

— to model "handler is mid-flight while the runner notices the cancel". Merging them would make that
test meaningless (and it is one of the tests guarding the cancel-artifact invariant).

`Why safe:` no action. Recorded so the next auditor does not "clean it up".

`Risk:` high if merged.

`LOC removed:` 0.

`Test coverage:` yes, and it is the reason not to merge.

`Card candidate:` no.

---

## Finding 16 — Dead parameter and a one-line wrapper in `deps.py`

`apps/backend/app/deps.py:195` (`def charge(db: Session, ws: Workspace, amount: float)`),
`apps/backend/app/deps.py:105-106` (`_custom_permissions`)

`Evidence:`
- `charge` never touches `db`: the body (197-200) only calls `_roll_period(ws)` and mutates `ws`.
  `ruff --select ARG` reports `ARG001 Unused function argument: db` at 195. Seven call sites pass it
  (`routers/training.py:271,349,636`, `routers/versions.py:64`, `routers/remote.py:153`,
  `services/workflow_runner.py:164`, `handlers/training.py:237`) — all seven also hold a session
  they could pass, which is why the parameter looks intentional but is not used.
- `_custom_permissions(db, role_id, level)` is a two-line forwarder to
  `rbac.custom_permissions(db, role_id, level)` with exactly two callers (113, 126, 129).

`Why safe:` the argument is unused; dropping it is mechanical at every call site. The wrapper adds
no behaviour (verified: same three positional args, no defaults, no error handling).

`Risk:` low — but it touches eight call sites in routers, i.e. outside this lane's files. Split the
card: `charge` in the deps card, call-site edits wherever that lane lives.

`LOC removed:` ~4.

`Test coverage:` `tests/test_usage_limits.py`, `tests/test_metering.py` cover `charge`'s 402 path;
removing an unused parameter keeps them green.

`Card candidate:` yes (low priority).

---

## Finding 17 — `apps/worker` is an untested 224-line duplicate of backend train/autolabel, with dead parameters

`apps/worker/labeldesk_worker/cli.py:111` (`def _poly(mask, W, H)`), `46-52`, `122-182`

`Evidence:`
- `_poly` never uses its `W`/`H` arguments — it divides by `mask.shape[1]` / `mask.shape[0]` (119).
  `ruff --select ARG` reports `ARG001 Unused function argument: W` and `H` at 111.
- `base_weights()` (46-52) is a near-copy of `adapters/ultralytics_ad.base_weights` (18-24), and
  `run_autolabel` (122-182) re-implements the same "model → annotations" mapping as
  `adapters/ultralytics_ad._run` + `services/ml.to_annotations`. This duplication is *justified*
  (the pip package must not import the backend), so it is a note, not a card.
- Grep `labeldesk_worker|apps/worker|worker/cli` across `apps/backend/tests` → **0 hits**: the whole
  package has no test anywhere in the repo.
- Minor: `handlers[job["kind"]]` (211) raises `KeyError` for any kind outside
  `{train, autolabel}`. Not reachable today because `routers/remote.py:87` filters claims to
  `REMOTE_JOB_KINDS`, so this is speculative only.

`Why safe:` removing the two unused parameters changes no call site (there is one, at 168).

`Risk:` low for `_poly`; **med** for the bigger picture — an untested package that runs on
customers' GPU boxes is the real risk here.

`LOC removed:` ~1 for `_poly`; 0 for the duplication.

`Test coverage:` **none found** — any card touching `apps/worker` must add a test first (a pure
`_poly`/`base_weights` unit test needs no ultralytics import and can live beside the package).

`Card candidate:` yes — but the card should be "add the missing test for the pip worker's pure
helpers", not "delete `W, H`".

---

## Finding 18 — Duplicated job-enqueue blocks (12 sites; two are near-identical) — hand-off to the routers lane

`apps/backend/app/routers/training.py:393-406` and `410-439`; other sites: `routers/ops.py:37,105`,
`routers/privacy.py:158`, `routers/event_search.py:96`, `routers/anomaly.py:187`,
`routers/batch_inference.py:91`, `routers/connectors.py:93`, `routers/versions.py:68,127`,
`routers/videos.py:75,205`, `services/drift.py:526`, `services/health_scan.py:230`,
`services/insights.py:340`, `services/retention.py:371`.

`Evidence:` twelve `Job(...)` constructions. The two export endpoints are the same seven steps
(dedupe query over `Job.status.in_(("queued","running"))`, `next(...)` match on `params`,
`Job(workspace_id, project_id, kind, created_by, params)`, `audit`, `commit`, `job_out`):

| step | `_export_edge` (393-406) | `export_model` (427-439) |
| --- | --- | --- |
| preflight | `export_preset` in `LOCAL_JOB_KINDS` | `export_engine` in `LOCAL_JOB_KINDS` |
| dedupe | `Job.kind == "export_preset"` + `params.model_id/preset` | `Job.kind == "export_engine"` + `params.model_id` |
| enqueue | `Job(kind="export_preset", params={model_id, preset})` | `Job(kind="export_engine", params={model_id, format})` |
| audit + commit + return | identical | identical |

All 18 kinds have both a producer and a handler (verified: `handlers/*.py` `HANDLERS` ∪
`config.LOCAL_JOB_KINDS` ∪ `REMOTE_JOB_KINDS` covers every `kind=` string) — **no dead job kinds**,
so this is duplication, not dead code.

`Why safe:` a `jobs.enqueue(db, *, workspace_id, project_id, kind, created_by, params)` helper plus
an `_active_job(db, project_id, kind)` helper would preserve every field; the risk is in subtle
per-site differences (`created_by=c.uid` vs `c.user.id`, extra `flush()` at `anomaly.py:195`).

`Risk:` med (per-site fields differ; a too-clever helper hides them).

`LOC removed:` ~8-10 if only the two export endpoints are merged.

`Test coverage:` `tests/test_edge_export.py`, `tests/test_engine.py`, `tests/test_anomaly.py` cover
the dedupe behaviour ("double click returns the in-flight job").

`Card candidate:` no for this lane (files belong to the routers lane); yes for that lane, scoped to
the two export endpoints only.

---

## Checked and found clean (no action)

- **Dead job kinds / handler branches:** none. Every kind produced by a `Job(...)` has an entry in
  `handlers/*.py:HANDLERS`; `missing_handlers()` is test-pinned empty
  (`tests/test_r1_worker_coverage.py:11-12`).
- **Dead `ADD COLUMN` blocks:** none. Every column in `schema/{identity,dataset,streams,training}.py`
  is read or written by app code (checked `skeleton`, `tiling`, `clean_path`, `snapshot_error`,
  `rule_index/kind/label`, `classes`, `quotas`, `custom_role_id`, `publishable`, `scopes`,
  `last_sync/last_status`, `executor`, `runtime_refs`, `family/variant/license`, `ai_ids`,
  `image_metrics`, `video_id/frame_index/sharpness/luminance`, `retention_days/face_blur/biometrics/legal_basis`,
  `platform_admin`, `totp_last_step`, `mfa_enabled`, `require_mfa`, `data_region`).
- **Orphan model classes / tables registered twice:** none. All 40-odd classes in
  `models/{identity,project,training,streams,insights,alerts}.py` are referenced by app code;
  `tests/test_z2_split.py` pins the re-export and the table/`STEPS` agreement.
- **Settings defined but never read:** none. Every `settings`-style constant in `config.py` has a
  reader (checked `AL_DAILY_CAP`, `AL_BAND`, `DRIFT_P`, `DRIFT_MAX_SAMPLES`, `DRIFT_MIN_SAMPLES`,
  `MAX_UPLOAD_MB`, `RETENTION_CHECK_S`, `RETENTION_PRESETS`, `WORKER_STALE_S`, `SECRET_OLD`,
  `MULTI_TENANT`, `SIGNUP_ENABLED`, `SEED_DEMO`, `ENVIRONMENT`, `CREDIT_COST`, all ten `PLANS` keys
  — the four metering keys are reached dynamically via `PLANS[...][metric]` at `services/metering.py:97`).
- **Debug prints / commented-out blocks / stale TODO:** none in this lane (`grep 'print\(|TODO|FIXME|XXX|breakpoint\(' `
  over every in-scope path → 0).
- **`worker.py` "seam" imports of `cv2` and `gc` (lines 9-10):** the comment is wrong — handlers import
  those modules themselves, and the tests reach *through* the module object
  (`tests/test_r1_video_privacy.py:62` patches `worker.cv2.VideoCapture`,
  `tests/test_train_stages.py:241` patches `worker.gc.collect`). They must stay (removing them breaks
  two tests); only the comment deserves a correction. Not worth a card.
- **Linter-only nits deliberately skipped:** `adapters/base.py:4` (`Path` unused),
  `models/insights.py:2` (`Boolean` unused) — `ruff --fix` territory, not audit material.
- **Project fields that round-trip but never branch:** `Project.annotation_group`
  (`models/project.py:31`; written at `routers/projects.py:133`, read only for the payload at 70 and
  the settings form) and `Project.visibility` (`models/project.py:29`; same round trip, plus the
  Home/ProjectSettings toggle). 0 hits of `visibility` in any authorization decision (grep over
  `apps/backend/app` → model, payload, patch loop, and unrelated keypoint-visibility code). The UI
  offers "Public"/"Private" and nothing consumes it — a product gap, **not** a cleanup: deleting a
  user-visible setting needs a product call. Reported here as an observation for lane 3/4.

---

## Summary

| # | Finding | file:line | LOC | Risk | Card |
| --- | --- | --- | --- | --- | --- |
| 1 | **BUG** loop has no supervisor | worker.py:142,190,270 | +4 | med | bug card |
| 2 | dead `RANK` | deps.py:19 | 1 | low | yes |
| 3 | dead `NEED` rows | deps.py:25-26 | 2 | low | yes |
| 4 | `Invite.invited_by` write-only | models/identity.py:92 | 2 | low | yes |
| 5 | dead `schema.DOMAIN_MODULES` | schema/__init__.py:29 | 1 | low | yes |
| 6 | `Availability.vram_mb` unread | adapters/base.py:16 | 4 | low | yes |
| 7 | `OnnxDetector.task` unread | inference/detect.py:331 | 1 | low | yes |
| 8 | redundant `num_classes` | inference/detect.py:230 | 6 | low | yes |
| 9 | duplicate index | models/streams.py:93-94 | 1 | low | yes |
| 10 | duplicate index DDL | bootstrap.py:75-76 | 3 | low | yes |
| 11 | tri-state flag, two states | config.py:83 | 1 | low | yes (docs) |
| 12 | `LD_OT_ALLOW_CIDR` undocumented | config.py:156 | 0 | med | yes |
| 13 | `label_image` CC 57 | adapters/refine.py:121 | 10 | med | yes |
| 14 | duplicate adapter boilerplate | adapters/*.py | 12 | low | yes (`_drop`) |
| 15 | do not merge the cancel seams | jobs.py:9 / worker.py:153 | 0 | high | no |
| 16 | `charge(db)` unused, wrapper | deps.py:195,105 | 4 | low | yes |
| 17 | untested pip worker | apps/worker/…/cli.py:111 | 1 | med | yes (test) |
| 18 | duplicated enqueue | routers/training.py:393,427 | 10 | med | other lane |

Behaviour-preserving total: **≈ 49 LOC removed** (excluding Findings 1, 12, 15, 17-18).
Highest-value item is Finding 12 (undocumented safety gate) and the only real defect is Finding 1.
