# Rust hot paths — plan (wave R)

Owner decision 2026-11-17: LabelDesk uses Rust together with Python. Python stays the product language
(FastAPI, jobs, ML, SDK, MCP). Rust is used **only for measured hot paths**, as Python extension modules
built with PyO3 + maturin (`abi3` wheels) and imported like any other Python module. No wholesale
rewrite. ADR: `docs/adr/0006-rust-python-hybrid.md`.

Planning lane only: docs and cards, no product code. Cards: `T-1400`–`T-1402` (wave R).

Read for this note: `docs/OPENCODE_PM_RULES.md`, `docs/OPENCODE_TEAM_FLOW.md` §1/§4c–4e,
`docs/architecture/` (all), `docs/adr/` (all), `docs/ops/PERFORMANCE-PLAN.md`, wave O cards
`T-1318`–`T-1324`, and the services named in §2.

---

## 1. The one rule

> **No Rust card without a perf baseline that shows at least 2x on a real scenario.**

Both halves are load-bearing:

- *perf baseline*: a number from `docs/ops/perf/baseline.json` (T-1320) plus a kernel measurement from
  `tools/perf/bench_kernels.py` (T-1400). A guess, a micro-benchmark alone, or "this is known to be slow
  in Python" is not a baseline.
- *real scenario*: the kernel's share of a **request or job that a user waits for**, measured end to end,
  not the kernel in isolation. A 50x kernel that is 1 % of a job is a 1 % win and does not ship.
- *2x*: the job or route gets at least twice as fast in the part the kernel owns, i.e. the kernel itself
  improves by at least `2 / share` (a kernel that is 10 % of a job must be 20x faster to halve it). When
  the share is small, the honest entry in the card is "close this card", not "port it anyway".

Two corollaries, applied below:

1. **A slow path is not automatically a Python path.** Most cost in this app is inside libjpeg, opencv,
   torch, pycocotools and OpenSSL. Rust does not beat those from a distance; it only removes Python
   bytecode.
2. **An algorithmic fix in Python beats a port.** If reducing a decode to 1/8 scale or caching a hash
   removes 90 % of a job, that lands as a Python card and the Rust card is closed. Section 4 lists two
   candidates where exactly that happens.

## 2. Method and what was measured

Measurements below were taken on 2026-11-17 on the owner's Windows machine (AMD64, Python 3.11.9,
Pillow 12.2, opencv 4.11, numpy 2.3.5) with a throwaway script that imports the real service modules —
`app.services.evaluate`, `tiling`, `imaging`, `versioning`, `segment`, `exporters` — and times them on
synthetic inputs of realistic size. Each row is a median of repeated calls. **These are not the wave O
harness numbers**: there is no `tools/perf/` yet (T-1319/T-1320 are still cards), no seeded 10k fixture,
and no committed baseline. They are enough to rank candidates and to decide which cards to write; every
card still has to reproduce the number on the harness before it starts.

Reproduce (no product code, temp directory only):

```
python - <<'PY'
import sys, time, random; sys.path.insert(0, "apps/backend")
from app.services import evaluate
random.seed(1)
rows = [{"file": "x", "width": 1280, "height": 720,
         "gt":  [{"cls": "c0", "bbox": [random.random()*1000, random.random()*700, 40, 40]} for _ in range(25)],
         "pred":[{"cls": "c0", "conf": random.random(),
                  "bbox": [random.random()*1000, random.random()*700, 40, 40]} for _ in range(300)]}
        for _ in range(200)]
t = time.perf_counter(); evaluate._sweep(rows); print((time.perf_counter()-t)*1000, "ms per 200 images")
PY
```

| # | Measurement | Result |
| --- | --- | --- |
| M1 | `evaluate._sweep`, 200 images, 10 gt / 50 pred | 290 ms (1.45 ms/image) |
| M2 | `evaluate._sweep`, 200 images, 10 gt / 200 pred | 1 180 ms (5.90 ms/image) |
| M3 | `evaluate._sweep`, 200 images, 25 gt / 300 pred | 3 947 ms (19.73 ms/image) |
| M4 | `evaluate._match` alone, 500 × (20 gt × 30 pred) | 106 ms |
| M5 | numpy one-shot matcher on the same 500 records (reference floor) | 22 ms |
| M6 | `versioning.phash_groups` pairing step, 300 hashes (44 850 pairs) | 70 ms → 1.56 µs/pair |
| M7 | `imagehash.phash` of a decoded 512×512 RGB image | 9.0 ms |
| M8 | `imaging.open_image` of a 12 MP (4000×3000) JPEG | 117.6 ms; + `thumbnail(480)` = 132.3 ms |
| M9 | `PIL` resize 12 MP → 640×480 | 50.2 ms |
| M10 | `tiling.tile_annotations`, 8 tiles × 20 polygon annotations | 3.1 ms/image |
| M11 | `tiling.stitch`, 100 tiles × 8 boxes (800 boxes, greedy NMS) | 3.3 ms |
| M12 | `exporters.export_coco`, 200 items × 20 polygon annotations | 186 ms (0.93 ms/image, 64 px copies) |
| M13 | `exporters.export_yolo`, 200 items × 1 bbox | 77 ms (0.38 ms/image) |
| M14 | `segment.mask_to_polygon` on a 640×640 mask (opencv) | 44.1 ms |
| M15 | `hashlib.sha256` of an 11.6 MB JPEG | 5.4 ms (≈2.1 GB/s) |

## 3. Hot-path ranking

Share = the kernel's estimated slice of the scenario's wall clock today, using M1–M15 and the job shapes
in `docs/ops/PERFORMANCE-PLAN.md` §4.1 (version 10k ≤ 120 s, export 1k ≤ 30 s). "Speedup" is what the
*native kernel* is expected to give, not the job.

| # | Candidate | Scenario and share today | Expected native speedup | Verdict | Card |
| --- | --- | --- | --- | --- | --- |
| 1 | **Evaluation matching sweep** (`_match` / `_sweep` / `_confusion` / `_worst`, `evaluate.py:251-331`) | `evaluate` job on a 2 000-image val split: 2.9 s (M1 shape) to 39.5 s (M3 shape), +10 % for confusion and worst. Against 50–80 s of CPU inference that is **5–45 % of the job**, and on a GPU worker it is the majority of the wall clock | **15–40x** on the kernel (flat `f64`/`i64` arrays, no dict access, no `sorted()` per threshold, one call for all 19 thresholds) → job −5 to −40 % | **PORT** — the only candidate that clears the rule on today's numbers | T-1401 |
| 2 | **Dedupe grouping** (`versioning.phash_groups:59-92`; also `insights_jobs.py:123-138`) | `version` job, 10k distinct images: 50 M pairs × 1.56 µs ≈ **78 s** of a job that is currently ~21 min (decode-bound, see #7) → **6 % today, ~35 % once the decode is fixed** | **30–100x** on the pairing (XOR + `count_ones`, disjoint-set, no `imagehash` objects) → 78 s becomes ~1 s | **PORT after #7 lands**, and only if the post-fix baseline confirms the share | T-1402 |
| 3 | Suspect scoring (`suspects.score_image:45-90`, called per image by `health_scan.py:163`) | `health` job, 10k images: 20 anns × 50 preds ≈ 1 000 IoU ≈ 1 ms/image → **10 s**, against ~300 s of model inference → **3 %** | 20–50x on the kernel, ≈10 s saved | **REJECT** — the job does not halve | — |
| 4 | Tiling / augmentation geometry (`imaging._map_points`, `_clip`, `tiling.tile_annotations`) | tiled `version` job, 10k images × 8 tiles: 31 s of geometry (M10) against ~2 400 s of crops, resizes and JPEG writes → **1.3 %** | 20–50x | **REJECT** — wins 30 s of a 40-minute job; fix the job, not the loop | — |
| 5 | Export/import annotation writers (`exporters.export_*`, `importers._normalize`) | `export` job, 1k images: 0.4–0.9 s (M12/M13) of a 30 s budget → **≤3 %**; the rest is file copy | 10–20x on the geometry | **REJECT** — 1 s is not a card | — |
| 6 | Tile stitch / NMS (`tiling.stitch:118-132`) | 400-tile inference: 50–100 ms of Python (M11 extrapolated) behind a multi-second GPU call → **<1 %** | 10–30x | **REJECT** | — |
| 7 | Image decode / resize / thumbnail (`imaging.open_image`, `store`, `load`) | `version` job, 10k × 12 MP images: **118 ms + 9 ms phash per image ≈ 21 min**, against a 120 s ceiling. This is the biggest number in the app and it is **inside libjpeg and `imagehash`'s own numpy work, not in Python bytecode** | Rust ~1–1.2x (same libjpeg-turbo class of decoder) | **REJECT the port, keep the finding**: the Python fix is a reduced-scale decode (`cv2.IMREAD_REDUCED_COLOR_4`, 8–64x) and a hash cache keyed by `sha256`, which is a separate Python card, not wave R | — |
| 8 | Mask RLE / polygon conversion (`segment.mask_to_polygon`, `evaluate._poly_mask`) | interactive Smart Polygon: 44 ms per 640×640 mask (M14) in opencv; RLE in pycocotools (Cython) | ~1x | **REJECT** — already native C | — |
| 9 | Hashing (`sha256` on upload/ingest) | 5.4 ms per 11.6 MB (M15), 2 GB/s in OpenSSL | ~1x | **REJECT** — already native | — |
| 10 | Embedding / PCA helpers (`insights_embedding._projection`, `_features`, `drift.mmd2`) | ≤500 vectors: `numpy` SVD ~10 ms, MMD kernels vectorised | ~1x | **REJECT** — numpy is the port | — |
| 11 | Video frame sampling (`handlers/streams.py:77-130`, `video.plan_frames`) | per kept frame: ~1–3 ms of `cvtColor` + `PIL.fromarray` + JPEG encode behind a 10–20 ms decode *(estimate, not measured — no 1080p sample video on hand)* | ~1.2x on the glue | **REJECT** — decode-bound, and the glue is already calls into C | — |

Result: of eleven candidates, **two** are Python-bound enough to clear the rule, and one of them only
after a different (Python) fix lands. Wave R is therefore three cards, not eleven.

## 4. Options, with size

Ranked by size. Sizes are production lines (Rust + Python glue + CI), not test lines.

| # | Option | Prod LOC | Verdict |
| --- | --- | --- | --- |
| A | **PyO3 crate inside this repo** at `packages/labeldesk-core/`, maturin + `abi3-py311`, dispatcher `app/kernels.py` with a Python fallback | **~230** (Rust ~120, Python glue ~70, CI job ~35, Dockerfile stage ~8) | **Chosen.** One repo, one review, one release; sits next to `packages/sdk` per ADR 0003; the fallback keeps the suite green for anyone without Rust |
| B | Separate `labeldesk-core` repository | ~230 + a second CI, a release pipeline and a version pin in `requirements.txt` (~120 more lines of infrastructure) | Rejected. ADR 0004 shows the cost of a split: two commits per change, an env/version contract, and worktrees that must clone both. Revisit past ~3 000 lines or a second consumer |
| C | Stay in Python with numpy/numba | ~60 for numpy (per-image call overhead eats the win: M5 shows 5x where the kernel needs 20x); numba adds a ~90 MB dependency and a per-process JIT warm-up inside jobs that run once | Rejected for the sweep; **kept as the default for every path in §3 marked REJECT**, and it already wins candidate #7 outright |

What option A must cover, and how:

| Requirement | How |
| --- | --- |
| Windows, Linux, WSL builds | `maturin` on the host toolchain: MSVC Build Tools on Windows, `build-essential` + `pkg-config` on Linux/WSL. Documented in `packages/labeldesk-core/README.md`; the build is never needed to *run* the app |
| CI wheels | one `rust` job builds `abi3` wheels for `manylinux_2_28_x86_64` (the Debian-slim image and the ubuntu runner) and `win_amd64` (the owner's machine), uploads them as an artifact; wheels are never committed |
| Pure-Python fallback, identical results | `apps/backend/app/kernels.py` is the only importer. Without the module, `kernels_py.py` (the current code, moved not rewritten) runs. Property tests assert equal results on 200 seeded random cases per kernel; the native run and the forced-fallback run both execute in CI |
| Effect on gate time | **+0 minutes of wall clock.** The new `rust` job runs in parallel with `api` (4 min, cargo cache warm), while the 15-minute `api` job is unchanged and runs the fallback path. The `gate` aggregator gains one `needs` entry. Local dev without Rust: unchanged |

## 5. Crate layout

```
packages/labeldesk-core/
  Cargo.toml            # cdylib, pyo3 = { version = "0.2x", features = ["abi3-py311", "extension-module"] }
  Cargo.lock            # committed: the audit and deny jobs must see resolved versions
  pyproject.toml        # [build-system] maturin; module-name = "labeldesk_core"
  deny.toml             # licence allowlist, duplicate-crate and source policy
  README.md             # build on Windows/Linux/WSL, install, force the fallback
  src/
    lib.rs              # #[pymodule] registration + #![deny(unsafe_code)] + panic boundary
    boxes.rs            # box_iou                      (T-1400)
    sweep.rs            # the evaluation matching sweep (T-1401)
    dedupe.rs           # hash pairing + disjoint set   (T-1402)
  tests/
    boxes.rs, sweep.rs, dedupe.rs   # Rust unit tests, run by `cargo test`
```

Python side (one seam, no scattered imports):

```
apps/backend/app/kernels.py       # picks native or fallback, reads LD_FORCE_PY_KERNELS
apps/backend/app/kernels_py.py    # the reference implementation (today's code, moved)
apps/backend/tests/test_kernels_parity.py   # property + parity tests, both paths
tools/perf/bench_kernels.py       # median ms per kernel, Python vs native, --json
```

Rules for the seam: callers import `from .kernels import ...`; nothing outside `kernels.py` may
`import labeldesk_core`; the native module is a private implementation detail and may disappear on any
given machine.

## 6. Panic and error policy

A Rust failure never crashes the API and never changes a result.

1. **No panics on input.** Kernels validate shapes and ranges and return `Err(PyValueError)` for a bad
   argument. `unwrap`/`expect`/`panic!`/indexing that can panic are forbidden in kernel code; clippy
   runs with `-D warnings` and `unwrap_used`/`expect_used` denied.
2. **Panics are contained.** Each exported function body runs inside `catch_unwind`; a panic becomes a
   `PyRuntimeError("kernel panic: <name>")` at the boundary. The process survives, the request or job
   fails with a user-safe message, and the panic is logged with the kernel name and inputs' shape (never
   their contents).
3. **Import failure is not an error.** A missing wheel, a wrong ABI or an `ImportError` selects the
   Python fallback and logs one line at startup (`kernels: native unavailable, using python`). A
   *result* mismatch is different: it is a bug, it fails the parity test, and it blocks the merge.
4. **Jobs fail, the worker does not.** The job runner already turns an exception into a failed job with a
   stored message; the policy here is that the exception type carries no internals and no file paths.
5. **No silent divergence.** `LD_KERNELS_STRICT=1` disables the fallback and raises on any native error;
   it is set in the parity test so a broken kernel can never hide behind the fallback in CI.
6. **Determinism.** Kernels take and return flat arrays and integers; no threads, no global state, no
   time, no randomness. The same input gives the same output on every platform, which is what makes the
   property tests meaningful.

## 7. Security

- **No `unsafe` without review.** The crate carries `#![deny(unsafe_code)]`. Any future need must be
  raised as its own card with an R7 security review and a written safety argument next to the block; a
  reviewer who sees `unsafe` in a diff without that record rejects it.
- **`cargo-audit` in the gate.** RUSTSEC advisories fail the `rust` job; the pinned versions and the
  committed `Cargo.lock` are what make the audit meaningful.
- **`cargo-deny` in the gate.** Licences: allow MIT, Apache-2.0, BSD-2/3-Clause, ISC, Unicode-3.0,
  Zlib; deny GPL/AGPL/LGPL (the tree already carries AGPL Ultralytics — do not add more copyleft);
  MPL-2.0 needs an explicit entry and review. Also deny duplicate crate versions and unknown registries
  or git sources: crates.io and the local path only.
- **No new network, no new file access.** Kernels take arrays and return arrays. If a kernel ever needs
  to read a path, that is a redesign, not a parameter.
- **The wheel is an artefact, not source.** Built in CI from a pinned lockfile, attached to the release,
  never committed (`tools/check_large_files.py` keeps it out), and installed in the image from the
  builder stage only.
- **No user data leaves the box.** A Rust kernel runs in-process; there is no new outbound call, and the
  safefetch/secretbox boundaries are untouched.

## 8. Phases

| Phase | Card | Ships | Needs |
| --- | --- | --- | --- |
| **R0 Toolchain** | T-1400 | crate skeleton, dispatcher + fallback pattern, one tiny kernel (`box_iou`), `bench_kernels.py`, the `rust` CI job with audit and deny, Dockerfile builder stage, build docs | T-1320 (baseline + compare) for `bench_kernels.py` to write into the same shape |
| **R1 The measured win** | T-1401 | the evaluation matching sweep as one native call per image, parity tests, benchmark, `evaluate` job before/after | T-1400; a baseline row for the `evaluate` job |
| **R2 Conditional** | T-1402 | hash pairing + disjoint set for dedupe | T-1400; **and** the decode/hash-cache Python fix merged (or the baseline showing ≥10 % share); closes if the profile says no |
| **R3 Review** | — (ledger) | 30-day check of the exit criterion in ADR 0006: did any kernel give 2x on a real job? If no, remove the crate | R1, R2 |

Order is strict: R0 before R1, R1 before R2. Nothing else in the backlog is blocked by wave R, and no
card changes a route, a response, a schema or a flag.

## 9. Test strategy

| Layer | Proves | Where |
| --- | --- | --- |
| Rust unit tests | each kernel on hand-written cases, including empty inputs, zero-area boxes, identical boxes, `u64::MAX` distance | `packages/labeldesk-core/tests/*.rs`, `cargo test` |
| Parity | native and Python give the same answer on 200 seeded random cases per kernel: exact for counts and indices, `1e-9` relative for floats | `apps/backend/tests/test_kernels_parity.py`, both paths in CI |
| Fallback | the whole existing suite passes with `LD_FORCE_PY_KERNELS=1`, so a contributor without Rust is not a second-class citizen | the `api` job, unchanged |
| Behaviour | the existing `test_evaluate.py` (27 tests) and `test_versioning_v2.py` pass unmodified — the kernel must not change a metric | `api` job |
| Benchmark | `tools/perf/bench_kernels.py` prints median ms for Python and native on the T-1319 fixture and fails `--min-speedup 2` in the nightly | nightly (T-1324), never the gate |
| Job-level | the `evaluate` job duration in the nightly report moves the right way | `docs/ops/perf/report-<sha>.md` |

## 10. What is deliberately not planned

- A Rust service, a Rust worker, a Rust CLI or a Rust web layer.
- Rust for new features. A new feature is written in Python; if it turns out hot, it earns a card.
- Replacing PIL, opencv, pycocotools, torch or OpenSSL call sites with Rust equivalents.
- A shared memory arena, zero-copy buffers across the FFI boundary or GIL-release tuning. If the profile
  ever shows the boundary itself costing more than the kernel, that is a new card with numbers.
- Prebuilt wheels on PyPI. Wheels are CI artefacts until there is an outside consumer.
- Cross-compilation, macOS wheels, ARM (the deployment is x86_64 Linux and Windows).
- SIMD hand-tuning. Correct scalar code first; `target-cpu` tuning only with a measured case.

## 11. Owner questions

1. **Toolchain on the build machines.** Windows needs MSVC Build Tools (~4 GB) and CI/WSL need
   `build-essential`. Is installing that on the owner's box and allowing a Rust toolchain in the app
   image build acceptable, or must the wheel come only from CI?
2. **Gate cost.** The `rust` job adds ~4 minutes of parallel CI (cargo cache ~300 MB) and two pinned
   third-party binaries for `cargo-audit`/`cargo-deny`. Accept, or run audit/deny nightly only?
3. **Scope after measurement.** Only one kernel (the evaluation sweep) clears 2x on today's numbers.
   Approve T-1400 + T-1401 now and leave T-1402 conditional, or hold the whole wave until the wave O
   baseline exists?
4. **The bigger finding.** The `version` job fails its 120 s budget by roughly 10x on 10k real 12 MP
   images, because every version build decodes all images for perceptual hashing (M8). Fixing that is a
   Python card worth 8–64x. Does it jump the queue ahead of wave R?
5. **Licence policy** for `cargo-deny`: confirm deny-GPL/AGPL/LGPL with MPL-2.0 by review, or a different
   allowlist for a future sale or OEM install?
6. **abi3 and the Python floor.** One `abi3-py311` wheel serves 3.11+. Should the floor stay at 3.11
   (today's CI and image), or do you want 3.10 wheels for older client installs?
