# LabelDesk v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn LabelDesk's hard-wired ML (SAM-only auto-label, YOLO-only training) into a pluggable model hub that auto-labels, trains, tests (playground) and runs on CCTV streams, demoable end to end on one RTX 3080 Ti on 2026-11-01.

**Architecture:** One FastAPI process hosts an adapter registry (`ultralytics`, `sam3`, `vlm`, `tensorrt`, later `rfdetr`/`hf`/`mmdet`), a GPU scheduler, the existing embedded job worker and a StreamManager (one thread per stream). vLLM serves Qwen2.5-VL-7B-AWQ as a separate localhost process. All model output goes through one prediction schema; evaluation uses one pycocotools evaluator.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, ultralytics ≥ 8.3, pycocotools, imagehash, httpx, OpenCV; vLLM (WSL2); React 19, Vite 6, Tailwind v4, TanStack Query, react-konva, recharts, `@material/material-color-utilities`.

**Spec:** [docs/sdlc/10-labeldesk-v2-sdlc.md](../../sdlc/10-labeldesk-v2-sdlc.md). UI direction: [reports/UX UI และฟีเจอร์ SaaS Computer Vision.md](../../../reports/) (final section "design direction"). Research backing: [reports/ฟีเจอร์ SaaS ด้าน Computer Vision.md](../../../reports/).

## Global Constraints

- Hardware budget: 1× RTX 3080 Ti **12 GB VRAM**, 32 GB RAM; `nvidia-smi` peak must stay **< 11.5 GB**.
- vLLM command (spec 3.4), verbatim: `VLLM_SERVER_DEV_MODE=1 vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ --host 127.0.0.1 --port 8000 --quantization awq --max-model-len 4096 --gpu-memory-utilization 0.55 --max-num-seqs 4 --limit-mm-per-prompt '{"image": 1}' --mm-processor-kwargs '{"max_pixels": 589824}' --enable-sleep-mode`.
- vLLM structured output only via `response_format` json_schema or `extra_body={"structured_outputs": ...}`; **never** `guided_json` / `guided_choice` (removed in v0.12.0).
- Env: `LD_VLM_URL=http://localhost:8000/v1`, `LD_VLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct-AWQ`; VLM fallback model `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`.
- API runs as a **single uvicorn process without `--reload`** (StreamManager and the latest-frame slot are in-process).
- `model_ref` format: `<family>:<variant>` for zoo/VLM models, `trained:<id>` for in-platform models. Existing endpoints keep their old `model_id` parameter; `model_ref` is an added optional field.
- Every annotation dict gains `source` ∈ {`human`, `sam3`, `vlm+sam3`, `trained:<id>`, `<family>:<variant>`}; a human edit sets `source = "human"`.
- VLM boxes are **never** saved without SAM 3.1 refinement; VLM output ignores the `conf` threshold and uses `confidence = 0.5`.
- Leaderboard numbers come only from the shared pycocotools evaluator on the **test** split (fallback valid).
- No credits charged for playground, stream or VLM calls; an auto-label batch that yields 0 annotations is not charged.
- Streams: Admin creates/starts/stops; any project member views. Every stream starts `stopped` after a restart. No SSRF filter on stream URLs (demo).
- Migration: `create_all` + idempotent `ALTER TABLE … ADD COLUMN` helper; demo DB is disposable.
- Licensing: every registry entry has `license`; `ultralytics` family = `"AGPL-3.0"`, `sam3` = `"SAM License"`, `vlm` (Qwen2.5-VL-7B) = `"Apache-2.0"`, `rfdetr` N–L / `hf` = `"Apache-2.0"`.
- Visual: Liquid Glass only on chrome (sidebar, top bar, floating toolbars, dialogs, command palette, job tray, stream overlays); **solid** surfaces for the annotation canvas, dense tables and charts. Solid is the default under `prefers-reduced-transparency: reduce` and when the user setting "Reduce transparency" is on.

## Review Focus

1. **Thai or multi-word class names** ("หมวกนิรภัย", "safety vest") — must survive the VLM JSON-schema enum, SAM text prompts and YOLO-World `set_classes` without mangling. Test owners: Task 3, Task 4.
2. **VLM server down or asleep mid auto-label batch** — the job must fail with a readable reason (not a stack trace), annotations written so far stay, and the registry shows `vlm` unavailable. Test owner: Task 4.
3. **Tiny or lopsided datasets** (a class with 1 image, an empty test split) — stratified split must not crash, and evaluation falls back to valid with a visible note. Test owners: Task 7, Task 8.
4. **Stream source that dies or never opens** (bad RTSP URL, video file deleted) — status becomes `reconnecting` / `error` with `last_error`, `stop` always returns and the thread exits. Test owner: Task 10.
5. **Very large images** (IC-defect images ≥ 6000 px) — VLM box rescaling from the `smart_resize` space back to original pixels must be exact, and SAM refinement must receive original-pixel boxes. Test owner: Task 3.

---

## File Structure

**API (`apps/api/app/`)**

| Path | Responsibility |
| --- | --- |
| `adapters/base.py` | `Adapter` protocol, `Availability`, `TrainResult`, `parse_ref()`, `validate_prediction()` |
| `adapters/__init__.py` | registry: `ADAPTERS`, `resolve(model_ref, db)`, `catalog(db, workspace_id)` |
| `adapters/catalog.py` | static zoo list (family, variant, name, capabilities, license, weights hint) |
| `adapters/ultralytics_ad.py` | YOLO / RT-DETR / YOLO-World predict + train + export (moves logic out of `services/ml.py`) |
| `adapters/sam3_ad.py` | SAM 3.1 text / box predict (wraps `services/segment.py`) |
| `adapters/vlm_ad.py` | HTTP client to vLLM: ground, verify, parse_prompt, ask; sleep/wake |
| `adapters/tensorrt_ad.py` | predict from `.engine` (P1) |
| `adapters/refine.py` | `refine_with_sam(pred, im) -> pred` box → SAM box prompt → polygon/bbox |
| `gpu.py` | `GpuScheduler`: VRAM ledger, LRU evict, `exclusive()` for training |
| `services/ml.py` | thin wrapper kept for v1 call sites (`predict`, `train`, `to_annotations`, `final_metrics`) |
| `services/evaluate.py` | pycocotools evaluator, confusion matrix, F1-optimal threshold |
| `services/health.py` | v2 health checks (box-size buckets, label quality, missing boxes, recommendations) |
| `services/versioning.py` | + stratified split, pHash grouping, `recipe.json`, export cache |
| `streams/rules.py` | pure rule engine (count, zone, line, dwell, cooldown) |
| `streams/manager.py` | `StreamManager`, grabber, watchdog, latest-frame slot |
| `routers/registry.py` | `GET /api/ws/{ws}/registry` |
| `routers/playground.py` | `POST /api/ws/{ws}/playground/predict` |
| `routers/streams.py` | stream CRUD, start/stop, upload-video, mjpeg, events, to-dataset |
| `models.py` | + `TrainedModel` columns, `Stream`, `StreamEvent` |
| `bootstrap.py` | + `ensure_columns()` |
| `worker.py` | `run_train` / `run_autolabel` use adapters, scheduler, evaluator |

**Tests (`apps/api/tests/`)**: `test_adapters.py`, `test_vlm.py`, `test_autolabel_v2.py`, `test_gpu.py`, `test_versioning_v2.py`, `test_evaluate.py`, `test_health.py`, `test_rules.py`, `test_streams.py`, `test_playground.py`. All set `LD_SAM_ENABLED=0` and mock vLLM with `httpx.MockTransport` unless marked `@pytest.mark.gpu`.

**Web (`apps/web/src/`)**: `lib/api.ts`, `lib/types.ts`, `features/project/Train.tsx`, `features/project/AutoLabelDialog.tsx` (extracted from `AnnotateBoard.tsx`), `features/project/Models.tsx` (+ leaderboard, evaluation), `features/project/Analytics.tsx` (+ v2 checks), `features/playground/Playground.tsx`, `features/streams/{Streams,StreamDetail,ZoneEditor}.tsx`, `components/shell.tsx` (nav), `components/glass.tsx`, `lib/theme.ts`, `index.css`.

**Tools**: `tools/demo_smoke.py`, `tools/serve_vllm.sh`, `tools/prefetch_weights.py`.

Web has no unit-test runner; web tasks verify with `npm run build` (tsc + vite) and a Playwright check via the `webapp-testing` skill.

---

### Task 0: Baseline commit on a feature branch

**Files:** none created; commits existing untracked v1 work.

- [ ] **Step 1: Branch** — `git switch -c feat/labeldesk-v2`
- [ ] **Step 2: Verify ignores** — `git status --porcelain -uall | grep -E 'node_modules|dinov3|\.pt$|\.db$'` → expected: no output.
- [ ] **Step 3: Commit baseline in the groups below** (old prototype `api/` and `web/` at repo root are **not** committed):
  1. `.gitignore` → `chore: gitignore updates for LabelDesk`
  2. `apps/api` → `feat(labeldesk): API`
  3. `apps/web` → `feat(labeldesk): web UI`
  4. `apps/worker apps/README.md` → `feat(labeldesk): GPU worker package`
  5. `deploy docs/DEPLOY.md` → `feat(deploy): compose stack + docs`
  6. `docs/labeldesk-plan.md docs/clone_plan.md docs/sdlc/10-labeldesk-v2-sdlc.md docs/superpowers` → `docs: LabelDesk plans and v2 SDLC`
  7. `README.md` → `docs: README status`
- [ ] **Step 4: Baseline tests** — `cd apps/api && pytest -q` → expected: all pass (record the count; every later task keeps it green).

---

### Task 1: Adapter protocol, catalog, registry, ultralytics + sam3 adapters

**Files:**
- Create: `apps/api/app/adapters/{__init__,base,catalog,ultralytics_ad,sam3_ad}.py`, `apps/api/app/routers/registry.py`
- Modify: `apps/api/app/services/ml.py` (delegate to `ultralytics_ad`), `apps/api/app/main.py` (include router), `apps/api/app/models.py` (`TrainedModel.family/variant/license/runtime_refs`), `apps/api/app/bootstrap.py` (`ensure_columns`)
- Test: `apps/api/tests/test_adapters.py`

**Interfaces:**
- Produces:
  - `parse_ref(ref: str) -> tuple[str, str]` — `"ultralytics:rtdetr-l"` → `("ultralytics", "rtdetr-l")`; `"trained:abc"` → `("trained", "abc")`; anything else raises `ValueError`.
  - `@dataclass Availability(ok: bool, reason: str = "", vram_mb: int = 0)`
  - `@dataclass TrainResult(weights: str, run_dir: str, history: list[dict])`
  - `class Adapter(Protocol)`: `family: str`; `probe() -> Availability`; `capabilities(variant: str) -> set[str]`; `predict(variant: str, im: PIL.Image, *, classes: list[str] | None = None, prompt: str | None = None, conf: float = 0.4, iou: float = 0.5) -> dict`; optional `train(variant, dataset_dir: Path, task: str, opts: dict, on_epoch, should_stop) -> TrainResult`, `export(weights: str, fmt: str) -> Path`.
  - `validate_prediction(d: dict) -> None` — raises `ValueError` unless d has `model: str`, `image: {width:int,height:int}`, `time: float`, `predictions: list` whose items have `class, class_id, confidence, x, y, width, height` (optional `points`, `track_id`), optional `text`.
  - `ADAPTERS: dict[str, Adapter]`; `resolve(model_ref: str, db) -> tuple[Adapter, str]` — for `trained:<id>` returns the adapter of `TrainedModel.family` and the weights path.
  - `catalog(db, workspace_id: str) -> list[dict]` — items `{ref, family, variant, name, capabilities: list[str], license, available: bool, reason: str, kind: "zoo"|"trained"|"vlm"}`.
  - `GET /api/ws/{ws}/registry` returns `catalog(...)`.
  - `ensure_columns(engine, table: str, cols: dict[str, str]) -> None` (DDL fragments, idempotent).

- [ ] **Step 1: Write failing tests** in `test_adapters.py`:

```python
def test_parse_ref():
    assert parse_ref("ultralytics:rtdetr-l") == ("ultralytics", "rtdetr-l")
    assert parse_ref("trained:abc123") == ("trained", "abc123")
    with pytest.raises(ValueError): parse_ref("rtdetr")

def test_catalog_lists_families_with_license(c):
    items = c.get(f"/api/ws/{WS}/registry").json()
    refs = {i["ref"] for i in items}
    assert {"ultralytics:yolo26n", "ultralytics:rtdetr-l", "ultralytics:yolov8s-worldv2", "sam3:sam3.1", "vlm:qwen2.5-vl-7b"} <= refs
    assert all(i["license"] for i in items)
    sam = next(i for i in items if i["ref"] == "sam3:sam3.1")
    assert sam["available"] is False and "LD_SAM_ENABLED" in sam["reason"]

def test_every_available_adapter_returns_valid_schema():   # contract test
    im = PImage.new("RGB", (64, 48))
    for fam, ad in ADAPTERS.items():
        if ad.probe().ok and fam == "ultralytics":
            validate_prediction(ad.predict("yolo26n", im))

def test_ensure_columns_is_idempotent(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'x.db'}"); eng.connect().exec_driver_sql("CREATE TABLE t (id TEXT)")
    ensure_columns(eng, "t", {"family": "VARCHAR(32) DEFAULT 'ultralytics'"}); ensure_columns(eng, "t", {"family": "VARCHAR(32)"})
    assert "family" in [c["name"] for c in inspect(eng).get_columns("t")]
```

- [ ] **Step 2: Run** `pytest tests/test_adapters.py -q` → FAIL (`ModuleNotFoundError: app.adapters`).
- [ ] **Step 3: Implement** the interfaces above. Catalog entries (variant → weights): `yolo26{n,s,m}` (+`-seg`) from `PRETRAINED_DIR`, `yolo11{n..x}`, `yolov8{n..x}`, `rtdetr-l`, `rtdetr-x`, `yolov8s-worldv2`, `yolov8m-worldv2`, `sam3.1`, `qwen2.5-vl-7b`. Ultralytics picks the class by variant prefix (`rtdetr` → `RTDETR`, `*world*` → `YOLOWorld` with `set_classes(classes)`, else `YOLO`). Move `base_weights`, `train`, `predict`, `_model` cache from `services/ml.py` into `ultralytics_ad.py`; `ml.predict/ml.train` become one-line delegations so v1 tests stay green. `predict` output adds `"model": f"{family}:{variant}"`.
- [ ] **Step 4: Run** `pytest -q` → all pass (new + baseline).
- [ ] **Step 5: Commit** — `feat(api): adapter registry with ultralytics and sam3 adapters`

---

### Task 2: Train families, run cap, resume, license badges

**Files:**
- Modify: `apps/api/app/routers/training.py` (`train_options`, `TrainIn`, `train`), `apps/api/app/worker.py:run_train`, `apps/web/src/features/project/Train.tsx`, `apps/web/src/lib/{api,types}.ts`
- Test: `apps/api/tests/test_adapters.py` (append)

**Interfaces:**
- Consumes: `catalog`, `ADAPTERS["ultralytics"].train`.
- Produces:
  - `GET .../train/options` → `{supported, task, families: [{family, label, license, available, reason, variants: [{id, label, weights}]}]}`.
  - `TrainIn` adds `family: str = "ultralytics"`, `variant: str = "yolo26n"`, `max_minutes: int | None = None`, `resume_from: str | None = None` (model id). Old `size` still accepted → `variant = f"yolo26{size}"`.
  - `TrainedModel.family/variant/license` filled at creation.

- [ ] **Step 1: Failing tests**

```python
def test_train_options_groups_families(c):
    o = c.get(f"{BASE}/train/options").json()
    fams = {f["family"]: f for f in o["families"]}
    assert {"yolo", "rtdetr", "yolo-world"} <= set(fams)
    assert fams["rtdetr"]["license"] == "AGPL-3.0"

def test_train_rtdetr_one_epoch_cpu(c, version_id):      # @pytest.mark.slow
    m = c.post(f"{BASE}/train", json={"version_id": version_id, "family": "ultralytics", "variant": "rtdetr-l", "epochs": 1, "imgsz": 160}).json()
    assert m["arch"] == "rtdetr-l"
    j = wait_job(c, m["jobId"]); assert c.get(f"{BASE}/models/{m['id']}").json()["status"] == "ready"

def test_max_minutes_stops_and_keeps_best(c, version_id, monkeypatch): ...  # patch time so cap trips after epoch 1; status "ready", history len == 1
def test_old_size_field_still_works(c, version_id): ...                     # body {"size": "n"} → variant "yolo26n"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Families in the UI are display groups over the `ultralytics` adapter: `yolo` (yolo26/11/v8 variants), `rtdetr`, `yolo-world`. `max_minutes` → `should_stop` also returns true after the deadline. `resume_from` → weights = that model's `last.pt` and ultralytics `resume=False, model=<last.pt>` (fine-tune continuation). Train.tsx: family cards (name, license badge, disabled + reason when `!available`) → variant chips → existing hyperparameter card + "Max minutes" field.
- [ ] **Step 4: Run** `pytest -q` and `cd apps/web && npm run build` → pass.
- [ ] **Step 5: Commit** — `feat: train page with model families, run cap and resume`

---

### Task 3: vLLM adapter (grounding, verify, prompt parser, ask, sleep/wake) + serve script

**Files:**
- Create: `apps/api/app/adapters/vlm_ad.py`, `tools/serve_vllm.sh`
- Modify: `apps/api/app/config.py` (`VLM_URL`, `VLM_MODEL`), `apps/api/requirements.txt` (+`httpx>=0.27`)
- Test: `apps/api/tests/test_vlm.py`

**Interfaces:**
- Produces (`VlmAdapter`, family `"vlm"`):
  - `probe() -> Availability` — `GET {VLM_URL}/models`; unreachable → `ok=False, reason="vLLM not reachable at …"`.
  - `ground(im, classes: list[str]) -> dict` — prediction schema, boxes in **original** pixels, `confidence=0.5`, `source` set later by caller.
  - `verify(im, box: tuple[float,float,float,float], cls: str) -> bool` — crop with 15 % margin, `structured_outputs={"choice": ["yes","no"]}`.
  - `parse_prompt(text: str) -> list[str]` — JSON schema `{"phrases": [string]}`, max 8 phrases.
  - `ask(im, question: str) -> str` and `ask_yes_no(im, question: str) -> bool`.
  - `sleep(level: int = 1) -> None`, `wake() -> None`, `is_sleeping() -> bool` — call the server root (strip `/v1`).
  - `smart_resize(h: int, w: int, factor: int = 28, max_pixels: int = 589824, min_pixels: int = 3136) -> tuple[int, int]` — Qwen2.5-VL rule (round to factor, scale down to `max_pixels`, up to `min_pixels`).
- Request shape (grounding): `POST /chat/completions` with `model=VLM_MODEL`, one user message `[{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,…"}}, {"type":"text","text": <prompt>}]`, `response_format={"type":"json_schema","json_schema":{"name":"boxes","schema":{"type":"object","properties":{"objects":{"type":"array","items":{"type":"object","properties":{"label":{"enum": classes},"bbox_2d":{"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4}},"required":["label","bbox_2d"]}}},"required":["objects"]}}}`, `temperature=0`. The image sent is resized client-side to `smart_resize(h, w)`; returned coordinates are scaled by `(W/w', H/h')`.

- [ ] **Step 1: Failing tests** (mock vLLM with `httpx.MockTransport`):

```python
def test_ground_rescales_to_original_pixels():          # Review Focus 5
    ad = vlm_with_reply({"objects": [{"label": "helmet", "bbox_2d": [28, 28, 56, 56]}]})
    im = PImage.new("RGB", (6000, 4000))
    h2, w2 = smart_resize(4000, 6000)
    p = ad.ground(im, ["helmet"])["predictions"][0]
    assert p["x"] == pytest.approx((28 + 56) / 2 * 6000 / w2, rel=1e-3)
    assert p["confidence"] == 0.5

def test_request_uses_json_schema_enum_and_never_guided(captured):   # Review Focus 1
    vlm_with_reply({"objects": []}, capture=captured).ground(PImage.new("RGB", (64, 64)), ["หมวกนิรภัย", "safety vest"])
    body = captured[0]
    assert body["response_format"]["type"] == "json_schema"
    assert "guided_json" not in json.dumps(body) and "หมวกนิรภัย" in json.dumps(body, ensure_ascii=False)

def test_bad_json_returns_empty(): ...                 # reply "not json" → predictions == []
def test_verify_uses_choice(): ...                     # extra_body structured_outputs.choice == ["yes","no"]; "no" → False
def test_probe_unreachable_reason(): ...               # ConnectError → ok False, "not reachable" in reason
def test_sleep_hits_root_not_v1(captured): ...         # POST http://localhost:8000/sleep?level=1
```

- [ ] **Step 2: Run** `pytest tests/test_vlm.py -q` → FAIL.
- [ ] **Step 3: Implement** `vlm_ad.py`; register in `ADAPTERS`. `tools/serve_vllm.sh` = the Global Constraints command with `${LD_VLM_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct-AWQ}`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: GPU check (manual, demo box):** `bash tools/serve_vllm.sh` in WSL, then `curl -s localhost:8000/v1/models` lists the model; `curl -X POST localhost:8000/sleep?level=1 && curl localhost:8000/is_sleeping` → `{"is_sleeping": true}`.
- [ ] **Step 6: Commit** — `feat(api): vLLM adapter with schema-constrained grounding and sleep control`

---

### Task 4: Auto-label v2 (model_ref, SAM refine, VLM verify, prompt parser, preview, source)

**Files:**
- Create: `apps/api/app/adapters/refine.py`, `apps/web/src/features/project/AutoLabelDialog.tsx`
- Modify: `apps/api/app/routers/training.py` (`AutoLabelIn`, `autolabel`, new `autolabel/preview`), `apps/api/app/worker.py:run_autolabel`, `apps/web/src/features/project/AnnotateBoard.tsx` (use the dialog), `apps/web/src/features/editor/*` (human edit sets `source="human"`)
- Test: `apps/api/tests/test_autolabel_v2.py`

**Interfaces:**
- Consumes: `resolve`, `VlmAdapter.ground/verify/parse_prompt`, `sam3_ad.predict(..., box=...)`.
- Produces:
  - `refine_with_sam(pred: dict, im, project_type: str) -> dict | None` — returns refined prediction; `None` when SAM unavailable.
  - `AutoLabelIn` adds `model_ref: str | None`, `prompt: str | None` (free text), `vlm_verify: bool = False`. v1 `method/model_id` still work.
  - `POST .../autolabel/preview` body = `AutoLabelIn` + `sample: int = 4` (3–5) → `{images: [{id, url, annotations}], counts: {class_name: n}}`; no credits, no writes.
  - Job result adds `annotations: int`; credits charged **after** the run as `CREDIT_COST["autolabel_image"] * labeled_images`, zero when `annotations == 0`.

- [ ] **Step 1: Failing tests**

```python
def test_vlm_ref_without_sam_is_rejected(c):             # spec 3.3
    r = c.post(f"{BASE}/autolabel", json={"model_ref": "vlm:qwen2.5-vl-7b"})
    assert r.status_code == 400 and "SAM" in r.json()["detail"]

def test_preview_writes_nothing_and_charges_nothing(c, fake_adapter): ...
def test_annotations_carry_source(c, fake_adapter): ...         # source == "ultralytics:yolo26n"
def test_zero_annotations_not_charged(c, fake_adapter_empty): ...  # credits unchanged
def test_vlm_down_mid_batch_fails_readably(c, fake_vlm_then_connect_error):   # Review Focus 2
    j = run_and_wait(c, {"model_ref": "vlm:qwen2.5-vl-7b", "sam": "fake"})
    assert j["status"] == "failed" and "vLLM not reachable" in j["error"] and "Traceback" not in j["error"]
    assert labeled_count_before_failure(c) >= 1
def test_thai_class_names_reach_sam_prompts(c, spy_sam): ...    # Review Focus 1: prompts == ["หมวกนิรภัย"]
def test_prompt_parser_feeds_sam(c, fake_vlm_phrases, spy_sam): ...   # prompt "workers without helmets" → SAM prompts == parsed phrases
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Per image: predictions from `resolve(model_ref)`; if family is `vlm` → every box through `refine_with_sam` (box = mask bbox for detection projects, polygon for segmentation), `source="vlm+sam3"`; if `prompt` given → `parse_prompt` → SAM text prompts mapped to the class chosen in the dialog; if `vlm_verify` → drop items where `verify` is false. Errors from `httpx` become `RuntimeError("vLLM not reachable at …")`. Dialog: model dropdown from `/registry` filtered to `detect|segment|open-vocab`, class prompt list, free-text box, "VLM verify" checkbox, **Preview** button (grid of 3–5 thumbnails + per-class counts) before **Run**. Confidence slider hidden for `vlm:*`. Review queue order: images whose lowest AI confidence is below the model's default threshold + 0.15 first, then `vlm+sam3` items (spec active-learning loop). In the editor and Review queue, AI annotations are drawn with a dashed outline and a source chip; `vlm+sam3` items show a "no confidence" badge instead of `0.50` (a fixed score would read as a real one).
- [ ] **Step 4: Run** `pytest -q`, `npm run build` → pass.
- [ ] **Step 5: Commit** — `feat: model-agnostic auto-label with SAM refine, VLM verify and preview`

---

### Task 5: GPU scheduler

**Files:**
- Create: `apps/api/app/gpu.py`
- Modify: `ultralytics_ad.py`, `sam3_ad.py` (load through scheduler), `worker.py:run_train` (wrap in `exclusive()`), `routers/registry.py` (`GET /api/gpu` → holder state)
- Test: `apps/api/tests/test_gpu.py`

**Interfaces:**
- Produces: `class GpuScheduler(budget_mb: int, vlm: VlmAdapter | None)` with
  - `lease(key: str, vram_mb: int, loader: Callable[[], Any], unloader: Callable[[Any], None]) -> Any` — LRU-evicts other non-pinned leases until `used + vram_mb <= budget_mb`.
  - `exclusive(reason: str) -> ContextManager` — evicts all leases, pauses streams (`StreamManager.pause_all()` hook, no-op until Task 10), `vlm.sleep(1)`; on exit `vlm.wake()` and resumes streams. If sleep fails → records `vlm_stopped=True` and continues.
  - `state() -> {"used_mb", "budget_mb", "holder": str | None, "leases": [...]}`.
  - Module singleton `scheduler = GpuScheduler(budget_mb=int(env LD_GPU_BUDGET_MB or 4500), vlm=ADAPTERS.get("vlm"))` — 4.5 GB left after vLLM's cap (spec 3.6).

- [ ] **Step 1: Failing tests** — `test_lru_evicts_oldest`, `test_exclusive_sleeps_and_wakes_vlm` (fake vlm records calls `["sleep:1", "wake"]`), `test_exclusive_survives_sleep_failure`, `test_state_reports_holder`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `pytest -q` → PASS.
- [ ] **Step 5: Commit** — `feat(api): GPU scheduler with LRU leases and exclusive training`

---

### Task 6: Playground

**Files:**
- Create: `apps/api/app/routers/playground.py`, `apps/web/src/features/playground/Playground.tsx`
- Modify: `apps/api/app/main.py`, `apps/web/src/App.tsx` (route `/:ws/playground`), `apps/web/src/components/shell.tsx` (workspace nav item "Playground")
- Test: `apps/api/tests/test_playground.py`

**Interfaces:**
- Produces: `POST /api/ws/{ws}/playground/predict` multipart `file`, `model_refs` (comma-separated, 1–3), `prompt?`, `confidence=0.25` → `{"results": [{"ref", "prediction": <schema>, "latency_ms": float, "error": str | None}]}`. VLM refs with `prompt` → `ask()` into `text`; without prompt → `ground()` with project-agnostic classes from `prompt` field split by comma. No credits.

- [ ] **Step 1: Failing tests** — `test_rejects_more_than_three_refs` (400), `test_one_failing_model_does_not_fail_others` (fake adapter raising → that result has `error`, others have predictions), `test_vlm_question_returns_text`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**; page = drop zone + model multi-select (max 3) + side-by-side canvases (react-konva overlay, solid surface) + latency chips + threshold slider that re-filters client-side + VLM question box. **Step 4:** `pytest -q`, `npm run build` → pass.
- [ ] **Step 5: Commit** — `feat: playground with side-by-side models and VLM questions`

---

### Task 7: Versioning v2 (stratified split, pHash grouping, recipe, export cache)

**Files:**
- Modify: `apps/api/app/services/versioning.py`, `apps/api/app/services/exporters.py` (cache), `apps/api/requirements.txt` (+`imagehash>=4.3`)
- Test: `apps/api/tests/test_versioning_v2.py`

**Interfaces:**
- Produces:
  - `stratified_split(items: list[tuple[str, set[int]]], ratios: dict[str, int], seed: int, groups: dict[str, str] | None = None) -> dict[str, str]` — image id → split. `groups` maps image id → group id; a group is placed as one unit.
  - `phash_groups(rows: list[Image], max_dist: int = 6) -> dict[str, str]` — union-find over pHash Hamming ≤ 6.
  - `version_dir(v)/recipe.json` = `{"resize": ..., "grayscale": bool, "contrast": ...}` copied from `settings.preprocessing`.
  - `cached_export(version, fmt) -> Path` — `versions/<id>/exports/<fmt>/`, built once.
  - Manifest gains `version_hash` (sha256 of config + sorted source sha256s).

Algorithm for `stratified_split` (greedy iterative stratification): compute desired count per (split, class) = ratio × class total; repeatedly take the class with the fewest remaining units, and for each unit containing it assign to the split with the largest remaining desired count for that class (ties → largest remaining overall, then seeded random); decrement desired counts for every class in the unit.

- [ ] **Step 1: Failing tests**

```python
def test_rare_class_lands_in_valid():
    items = [(f"i{k}", {0}) for k in range(40)] + [("r1", {1}), ("r2", {1}), ("r3", {1}), ("r4", {1}), ("r5", {1})]
    s = stratified_split(items, {"train": 70, "valid": 20, "test": 10}, seed=1)
    assert any(s[i] == "valid" for i in ("r1", "r2", "r3", "r4", "r5"))

def test_single_image_class_does_not_crash():          # Review Focus 3
    s = stratified_split([("a", {0}), ("b", {1})], {"train": 70, "valid": 20, "test": 10}, seed=1)
    assert set(s) == {"a", "b"}

def test_near_duplicates_share_a_split(): ...          # two identical images + 1 shifted copy → same split
def test_version_writes_recipe_and_hash(c): ...        # generate version → recipe.json exists, manifest["version_hash"] len 64
def test_same_inputs_same_hash(c): ...
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4:** `pytest -q` → PASS.
- [ ] **Step 5: Commit** — `feat(api): stratified, leakage-safe versions with recipe and export cache`

---

### Task 8: Unified evaluator, train stepper, OOM retry, watchdog, leaderboard

**Files:**
- Create: `apps/api/app/services/evaluate.py`
- Modify: `apps/api/app/worker.py:run_train`, `apps/api/app/routers/training.py` (`GET .../leaderboard`), `apps/api/requirements.txt` (+`pycocotools>=2.0.7`), `apps/web/src/features/project/Models.tsx`
- Test: `apps/api/tests/test_evaluate.py`

**Interfaces:**
- Consumes: `cached_export(version, "coco")`, `resolve`, `adapter.predict`.
- Produces:
  - `evaluate(model_ref: str, version_dir: Path, task: str) -> dict` → `{"split": "test"|"valid", "note": str, "coco": {12 COCO keys: "AP", "AP50", "AP75", "APs", "APm", "APl", "AR1", "AR10", "AR100", "ARs", "ARm", "ARl"}, "per_class": [{"class", "AP", "AP50"}], "f1_best": {"conf": float, "f1": float}, "confusion": {"labels": [...], "matrix": [[int]]}, "pr_curve": [{"recall", "precision"}], "worst": [image file names, up to 12], "latency_ms": float}`.
  - Job log stages written to `job.result["stages"]`: `queue, acquire_gpu, materialise, resolve_weights, build_config, train, evaluate, register, release` each with `status` and `t`.
  - `TrainedModel.metrics` = `evaluate(...)` output; default threshold = `f1_best.conf`.
  - `GET .../leaderboard` → models sorted by `coco.AP` desc with `version`, `latency_ms`, `comparable: bool` (same version as the top model).
  - Watchdog: fail with `RuntimeError("no training progress for N s")` when no epoch callback within `3 × median epoch time` (min 120 s).
  - OOM: `torch.cuda.OutOfMemoryError` in epoch 1 → retry once with `batch // 2`, stage note "retried with batch=N".

- [ ] **Step 1: Failing tests**

```python
def test_matches_pycocotools_reference():               # perfect predictions → AP == 1.0; shifted half → reference value from a fixture computed once with pycocotools
def test_empty_test_split_falls_back_to_valid(): ...    # Review Focus 3: split == "valid", note mentions fallback
def test_f1_best_conf_in_range(): ...
def test_leaderboard_marks_other_versions_not_comparable(c): ...
def test_oom_retries_with_half_batch(monkeypatch): ...  # fake train raises OutOfMemoryError once → second call batch == 4
def test_watchdog_fails_stalled_run(monkeypatch): ...
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**; Models page: stage stepper while training, evaluation panel (12 metrics, per-class table, confusion heatmap with viridis and a confidence slider starting at `f1_best.conf`; clicking a cell opens those images with GT vs prediction side by side, PR curve, worst-images gallery), leaderboard tab. Train page gets a one-click **Fast** preset next to Advanced and shows an estimated time before Start. **Step 4:** `pytest -q`, `npm run build` → pass.
- [ ] **Step 5: Commit** — `feat: shared COCO evaluator, training stages and model leaderboard`

---

### Task 9: Health check v2

**Files:**
- Create: `apps/api/app/services/health.py`
- Modify: `apps/api/app/routers/projects.py:_analytics` (merge `health.checks(...)` under key `"checks"` and `"recommendations"`), `apps/web/src/features/project/Analytics.tsx`
- Test: `apps/api/tests/test_health.py`

**Interfaces:**
- Produces: `checks(db, project, imgsz: int = 640) -> dict` → `{"size_buckets": {"small","medium","large"}, "label_quality": [{"kind": "tiny"|"out_of_bounds"|"zero_area"|"duplicate", "image_id", "annotation_id"}], "missing_boxes": [{"image_id", "box", "class"}] (only when a ready trained model exists: predictions with conf ≥ model default threshold and IoU < 0.3 to every GT), "leakage_pairs": int}` and `recommendations(checks) -> list[{"key", "message", "suggest": dict}]` (e.g. `{"key": "imgsz", "message": "41 % objects are small at 640 → try 1024 or tiling", "suggest": {"imgsz": 1024}}`). COCO buckets in pixels at `imgsz`: small < 32², medium < 96².

- [ ] **Step 1: Failing tests** — `test_size_buckets_scale_with_imgsz`, `test_label_quality_flags_tiny_and_oob`, `test_missing_box_found_when_model_predicts_unlabeled_object` (fake model), `test_recommendation_for_small_objects`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**; Analytics page adds "Health" cards; each flagged item links to the editor; charts filter the dataset on click. **Step 4:** pass.
- [ ] **Step 5: Commit** — `feat: health check v2 with label-quality and missing-box detection`

---

### Task 10: Streams (rules, manager, API, UI)

**Files:**
- Create: `apps/api/app/streams/{__init__,rules,manager}.py`, `apps/api/app/routers/streams.py`, `apps/web/src/features/streams/{Streams,StreamDetail,ZoneEditor}.tsx`
- Modify: `apps/api/app/models.py` (`Stream`, `StreamEvent`), `apps/api/app/main.py` (startup: mark all streams `stopped`; shutdown: `manager.stop_all()`), `apps/api/app/gpu.py` (wire `pause_all/resume_all`), `apps/web/src/App.tsx`, `apps/web/src/components/shell.tsx` (project nav "Streams")
- Test: `apps/api/tests/test_rules.py`, `apps/api/tests/test_streams.py`

**Interfaces:**
- Produces:
  - Models: `Stream(id, workspace_id, project_id, name, source, model_ref, sample_fps: float = 5, zones: list, rules: list, status: str = "stopped", last_error: str = "", created)`; `StreamEvent(id, stream_id, ts, rule, summary, snapshot_path, predictions)`.
  - `rules.Engine(rules: list[dict], zones: list[dict], cooldown_s: float = 30)` with `step(ts: float, preds: list[dict]) -> list[dict]` (events `{rule, summary}`). Rule dicts: `{"kind": "count", "class", "op": ">=", "k", "for_s"}`, `{"kind": "zone", "class", "zone_id"}`, `{"kind": "line", "class", "line": [x1,y1,x2,y2], "direction": "in"|"out"|"both"}`, `{"kind": "dwell", "class", "zone_id", "seconds"}`, `{"kind": "vlm", "question", "every_s"}` (vlm rules are evaluated by the manager, not the engine). Geometry normalized 0–1; anchor = bottom-centre `(x, y + h/2)`.
  - `StreamManager`: `start(stream_id)`, `stop(stream_id)` (returns within 5 s, joins thread), `pause_all()`, `resume_all()`, `latest_jpeg(stream_id) -> bytes | None`, `status(stream_id) -> dict`. Grabber keeps only the newest frame; file sources loop; watchdog reopens the capture when no new frame or identical frame hash for 10 s; reconnect backoff 1→30 s with status `reconnecting`.
  - Routes under `/api/ws/{ws}/projects/{project}/streams`: `GET`, `POST`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/start`, `POST /{id}/stop`, `POST /upload-video` (→ `{source: "file:videos/<name>"}`), `GET /{id}/mjpeg?token=` (signed, bound to stream, 12 h), `GET /{id}/events`, `POST /{id}/events/{eid}/to-dataset` (uses `images.ingest`, tag `stream`, `source="stream"`).
  - Stream model must be `ultralytics:*`, `trained:*` (ultralytics family) or `tensorrt:*`; otherwise 400.

- [ ] **Step 1: Failing tests**

```python
def test_line_crossing_counts_once_per_track():
    e = Engine([{"kind": "line", "class": "person", "line": [0, .5, 1, .5], "direction": "both"}], [])
    ev = []
    for t, y in enumerate([.3, .4, .6, .7, .6]): ev += e.step(t, [box("person", track_id=1, y=y)])
    assert len(ev) == 1      # crossing back within cooldown is suppressed

def test_zone_uses_bottom_centre(): ...
def test_count_for_seconds(): ...
def test_dwell_per_track(): ...
def test_stop_returns_when_source_never_opens(c):      # Review Focus 4
    sid = create_stream(c, source="rtsp://10.255.255.1/none")
    c.post(f".../streams/{sid}/start"); t = time.time(); c.post(f".../streams/{sid}/stop")
    assert time.time() - t < 5 and c.get(f".../streams/{sid}").json()["status"] == "stopped"
def test_deleted_video_reports_error(c): ...           # status "error", last_error mentions the file
def test_rejects_sam_as_stream_model(c): ...
def test_mjpeg_requires_valid_token(c): ...
def test_event_to_dataset_creates_image(c, fake_event): ...
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**; UI: stream list (status dots), detail = live `<img src=mjpeg>` with glass overlay chips, ZoneEditor (click to add polygon points / two-point line on a paused frame, solid canvas), rules form, event timeline (snapshot thumbnail with the trigger anchor point and zone/line drawn on it, rule, time, "Reviewed" toggle, filters by rule/class/reviewed, "Send to dataset"). `StreamEvent` gains `reviewed: bool = False` and `PATCH .../events/{eid}` sets it; test `test_event_reviewed_toggle`. **Step 4:** `pytest -q`, `npm run build` → pass; manual: looping demo video ≥ 5 FPS shown in the status panel.
- [ ] **Step 5: Commit** — `feat: CCTV streams with tracking rules, watchdog and event timeline`

---

### Task 11: Liquid Glass + Material dynamic colour theme

**Files:**
- Create: `apps/web/src/lib/theme.ts`, `apps/web/src/components/glass.tsx`, `apps/web/public/fonts/` (Anuphan or IBM Plex Sans Thai, OFL)
- Modify: `apps/web/src/index.css`, `apps/web/src/components/shell.tsx`, `apps/web/src/components/ui.tsx` (Dialog, Toast, Popover use glass), `apps/web/src/features/settings/Settings.tsx` ("Reduce transparency" toggle, seed colour picker), `apps/web/package.json` (+`@material/material-color-utilities`)

**Interfaces:**
- Produces:
  - `applyTheme(seed: string, mode: "light"|"dark", contrast: 0 | 0.5 | 1, scheme: "tonal-spot"|"vibrant"|"expressive" = "vibrant") -> void` — builds the scheme from the seed via HCT (`material-color-utilities`), converts each role to OKLCH, and writes CSS variables on `:root` under the existing names (`--primary`, `--primary-foreground`, `--secondary…`) so components need no change; Tailwind v4 reads them through `@theme`.
  - Class palette (separate from brand): Okabe-Ito 8 colours, then Glasbey extension — `classColor(i: number) -> string`; heatmaps use viridis.
  - `<Glass as="div" strength="chrome"|"overlay">` → `-webkit-backdrop-filter` and `backdrop-filter: blur(16px) saturate(180%)` (literal values, Safari needs them), translucent surface token, 1px inner highlight border. Max blur 20px. Motion animates opacity only, never blur.
  - **Solid is the default**: glass turns on only under `@supports (backdrop-filter: blur(1px))` and when neither `prefers-reduced-transparency: reduce` nor `html[data-reduce-transparency]` (Settings toggle; needed because Safari ignores the media query). `@media (prefers-contrast: more)` → 2px borders.
  - Fonts: `"IBM Plex Sans", "Anuphan", "Noto Sans Thai", system-ui`; Thai line-height 1.6. Dates default to Gregorian (`th-TH-u-ca-gregory`), Buddhist Era as a setting. Never truncate Thai with `slice()`; use CSS `text-overflow` or `Intl.Segmenter`.
  - Long jobs (train, auto-label, version) show in a glass **job tray** (bottom-right) with determinate progress, so users can leave the page. The top bar shows a GPU holder badge from `GET /api/gpu` (e.g. "GPU: training rtdetr-l", "vLLM asleep").
  - Accessibility floor (WCAG 2.2 AA): targets ≥ 24×24 px, focus never hidden under sticky panels or the tray, 3:1 non-text contrast for controls and focus rings.
- Glass applies to: sidebar, top bar, editor floating toolbar, dialogs, command palette, job tray, stream overlay chips. Solid: editor canvas, Dataset grid, tables, charts.

- [ ] **Step 1:** Implement theme + glass; replace sidebar/top bar/dialog surfaces.
- [ ] **Step 2: Verify** `npm run build` → pass; Playwright (webapp-testing skill) screenshots of Home, Train, Editor, Stream detail in light and dark plus with `prefers-reduced-transparency: reduce` emulated; check text contrast ≥ 4.5:1 on glass surfaces with axe (`@axe-core/playwright`) → no `color-contrast` violations.
- [ ] **Step 3: Commit** — `feat(web): Liquid Glass chrome with Material dynamic colour`

---

### Task 12: Demo seed, weight prefetch, smoke script

**Files:**
- Create: `tools/prefetch_weights.py`, `tools/demo_smoke.py`, `apps/api/app/seed_v2.py`
- Modify: `apps/api/app/bootstrap.py` (call `seed_v2` when `LD_SEED_DEMO=1`), `docs/sdlc/10-labeldesk-v2-sdlc.md` (record measured VRAM / sleep / wake numbers in 3.6)

**Interfaces:**
- `prefetch_weights.py`: downloads `rtdetr-l.pt`, `yolov8s-worldv2.pt`, `yolov8m-worldv2.pt` (and the CLIP text encoder by calling `set_classes(["person"])` once), `yolo11{n,s}.pt`, and the vLLM model via `huggingface-cli download`.
- `seed_v2`: PPE project gets a ready version, one trained `yolo26n` model with evaluation, and a stream "Gate camera" with source `file:videos/demo.mp4`, a zone, a line rule and a count rule (stopped).
- `demo_smoke.py` runs, in order, and prints PASS/FAIL per line: vLLM `/v1/models`; VLM→SAM ground on 5 seed images (≥ 1 box); SAM text auto-label (≥ 1 annotation); `/sleep?level=1` → `/is_sleeping` true (time recorded) → train `yolo26s` 3 epochs → `/wake_up` (time recorded); stream start → ≥ 5 FPS for 60 s → stop; `nvidia-smi --query-gpu=memory.used` sampled every 1 s with peak < 11 500 MiB.

- [ ] **Step 1:** Implement the three tools/seed.
- [ ] **Step 2: Verify on the demo box:** `python tools/demo_smoke.py` → all PASS. If sleep fails → set `LD_VLM_MODEL` to the 3B fallback, rerun, and note it in spec 3.6.
- [ ] **Step 3: Rehearse** the spec 1.2 loop twice (timed); record times.
- [ ] **Step 4: Commit** — `chore: demo seed, weight prefetch and GPU smoke test`

---

### P1 tasks (after the P0 loop is rehearsed)

### Task 13: VLM stream rule + dwell UI

- Modify `streams/manager.py`: every `every_s` seconds call `VlmAdapter.ask_yes_no(frame, question)`; "yes" → event `rule="vlm"`; skipped while vLLM sleeps. Test `test_vlm_rule_fires_on_yes_and_skips_while_sleeping` (fake adapter). Commit `feat: VLM yes/no stream rule`.

### Task 14: TensorRT export

- `POST .../models/{mid}/export` body `{"format": "engine"}` → job `export_engine` → `ultralytics` `export(format="engine", half=True)`; store in `runtime_refs.engine`; `tensorrt_ad` loads `.engine` via `YOLO(path)`; persistent cache dir `LD_DATA_DIR/engines/`. Test (gpu-marked) `test_engine_predict_matches_pt_within_tolerance` (same top-1 class, box IoU ≥ 0.9). Pre-build engines before the demo. Commit `feat: TensorRT export and runtime`.

### Task 15: Apache-2.0 families (`rfdetr`, `hf`)

- `adapters/rfdetr_ad.py` (package `rfdetr`, variants `nano, small, medium, large`; trains from `cached_export(version, "coco")`), `adapters/hf_ad.py` (`transformers` `AutoModelForObjectDetection` for `ustc-community/dfine-*` and `PekingU/rtdetr_v2_*`; Trainer with COCO dataset collator). Both report metrics through `on_epoch` with the common keys of spec P4 and are scored by `evaluate()`. Contract test from Task 1 must pass for both. Train page cards appear automatically via catalog. Commit `feat: RF-DETR and D-FINE/RT-DETRv2 families`.

### Task 16: TIDE breakdown

- `evaluate()` adds `"tide": {"cls", "loc", "both", "dupe", "bkg", "missed"}` (dAP per error type) using the `tidecv` package; Models page shows a bar chart. Test with a fixture where all errors are localisation → `loc` dominates. Commit `feat: TIDE error breakdown`.

### Task 17: Editor and upload UX gaps from the UX research

- Upload: end-of-upload summary "uploaded N · duplicates skipped N · failed N (reasons)" from the existing `ingest` result.
- Smart Polygon: positive click / negative click (Alt+click or right-click) in addition to the box prompt; click outside the mask expands, click inside the edge shrinks; Enter commits, Esc cancels.
- Object list panel with hide / lock per annotation; display-only brightness / contrast sliders (CSS filter on the Konva stage container, not pixel filters).
- VLM class suggestion: selected annotation → "Suggest class" asks `VlmAdapter.verify` over the project classes and offers the top answer.
- Verification: `npm run build`; Playwright flow draws with clicks only (no drag) to satisfy WCAG 2.5.7. Commit `feat(web): editor click prompts, object list and upload summary`.

### P2 (not scheduled for the demo)

- MMDet adapter (RTMDet / RTMDet-Ins) in a separate env worker; playground video and webcam input; custom weights upload with `RegistryModel` table (spec 3.7); editor video timeline; compound stream rules with a "VLM verified" event badge; everything in spec Phase 7.

---

## Order and parallelism

Sequential dependencies: 0 → 1 → {2, 3} → 4 → 5 → {6, 7} → 8 → 9 → 10 → 11 → 12. Tasks 6 and 7 touch disjoint files and can run in parallel; 11 can start any time after 1 if a second implementer is free. Cut order if time runs short is spec Phase 4 (scheduler → minimal; drop leaderboard/recommendations/missing-box; drop zone editor; drop side-by-side). The auto-label → train → stream loop is never cut.
