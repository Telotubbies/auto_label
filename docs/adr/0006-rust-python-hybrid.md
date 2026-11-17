# ADR 0006: Rust only as Python extension modules for measured hot paths

- Status: Proposed (draft for the owner, 2026-11-17)
- Deciders: owner, PM/merge captain, R7 security
- Related: `docs/research/rust-hybrid/PLAN.md`, `docs/ops/PERFORMANCE-PLAN.md`, ADR 0003 (packages layout), ADR 0004 (ML pipelines live in their own repository)

## Context

The owner decided on 2026-11-17 that LabelDesk uses Rust together with Python. Python stays the
product language: FastAPI, jobs, the SDK, the MCP app, adapters and ML glue are Python, and the ML
pipelines already live in their own repository (ADR 0004). Rust is allowed only where a profile shows
Python itself is the cost.

That distinction matters in this codebase, because most "slow" paths here are not Python: a 12 MP JPEG
opens in 118 ms inside libjpeg, a gradient runs in torch, a 640×640 contour trace runs in opencv, and
sha256 runs in OpenSSL at 2 GB/s. Rewriting any of those in Rust would be a new implementation of
somebody else's C for no gain. The paths that are Python are the small arithmetic loops over
annotation dicts and detection lists, where every IoU is a dict lookup and a function call.

Measured on this repository's own services (throwaway script, 2026-11-17, Windows AMD64, Python 3.11,
numbers in `docs/research/rust-hybrid/PLAN.md` §2):

| Path | Today | Python share |
| --- | --- | --- |
| `evaluate._sweep` over 19 confidence thresholds | 1.45–19.7 ms per image depending on gt/pred counts | ~100 % (dict `box_iou`, `sorted()` per call) |
| `versioning.phash_groups` pairing | 78 s extrapolated for 10k images | O(n²) Python loop over `imagehash` objects |
| `tiling.tile_annotations` | 3.1 ms per image at 8 tiles | ~100 %, but only 1.3 % of a tiled version build |
| COCO/YOLO export geometry | 0.4–0.9 ms per image | ~5 % of an export job, the rest is file copy |
| image decode, resize, mask→polygon, sha256, PCA | 5–132 ms per call | ~0 % (already native C) |

So the honest scope is one to three kernels, not a port.

## Decision

1. **Python remains the product language.** No service, route, job runner, SDK or CLI is rewritten.
2. **Rust ships only as a Python extension module** built with PyO3 + maturin, `abi3-py311`, imported
   as `labeldesk_core` like any other module. The application never links Rust directly.
3. **The crate lives in this repository at `packages/labeldesk-core/`** (option A). Option B, a separate
   repository, was rejected: it buys nothing at two kernels and adds a cross-repo release, a second CI
   and a version-skew question for every deploy.
4. **Every kernel has a pure-Python fallback with the same results.** `apps/backend/app/kernels.py` is
   the only place that imports the native module; callers import the dispatcher. Without Rust installed,
   the fallback runs the reference implementation, so a developer with no toolchain runs the full suite,
   every job and the whole product. `LD_FORCE_PY_KERNELS=1` forces the fallback on a machine that has it.
5. **A card may only port a path whose wave O baseline shows at least 2x on a real scenario.** Estimate
   is not evidence; the micro-benchmark plus the job duration from `docs/ops/perf/baseline.json` is.
   A path that fails the gate stays in Python, and the reason is written in the card and the plan.
6. **Option C, stay in Python with numpy/numba, is the default for every path that fails the gate**, and
   it already wins two of the candidates: a reduced-scale decode makes perceptual hashing 8–64x faster
   without Rust, and `numpy` SVD/UMAP already cover the embedding helpers. numba was rejected as a
   general answer because it is a ~90 MB dependency, compiles per process (seconds added to every job
   start) and does nothing for the dict/list code that is actually hot here.
7. **The crate is `#![deny(unsafe_code)]`.** No `unsafe` block without an R7 review and a written safety
   argument. `cargo-audit` (RUSTSEC advisories) and `cargo-deny` (licences, duplicate crates, sources)
   run in the merge gate, not in the nightly.
8. **A Rust failure never crashes the API and never changes a result.** Kernels return `PyResult`;
   panics are caught at the FFI boundary and become a Python exception; a fault in a job fails that job
   with a user-safe message, never the process. Import failure (missing wheel, ABI mismatch) selects the
   fallback silently and logs one line at startup.

## Alternatives considered

**Wholesale Rust rewrite of the API or the worker.** Rejected by the owner decision: the bottleneck is
not the language, and this codebase's value is in ~1 600 Python tests, the adapter seams and the job
semantics, none of which survive a rewrite that nobody asked for.

**A separate `labeldesk-core` repository (option B).** Rejected: two kernels do not justify a second
release process, and ADR 0004 shows what a split costs — every cross-repo change needs two commits and
an environment contract. Revisit if the crate grows past roughly 3 000 lines or gets a consumer outside
this repository (for example the ML repository).

**Stay in Python with numpy/numba (option C) for the surviving kernel.** Rejected for the evaluation
sweep specifically: numpy's per-image call overhead (22 ms for the same 500 images that take 106 ms in
plain Python, measured) eats most of the win, because the loop is over 19 thresholds × 500 small
matrices. numba's JIT warm-up per worker process is unacceptable inside jobs that run once. Both remain
the right answer for the other candidates.

**Cython or a C extension.** Rejected: the same build complexity as Rust, no memory-safety gain and no
`abi3` wheel story. If the owner ever refuses the Rust toolchain, this is the fallback plan, not a
parallel one.

## Consequences

- The merge gate grows one parallel job: build, clippy, `cargo test`, audit, deny and a parity run
  (about 4 minutes, cached). It does not lengthen the 15-minute gate because it is not in the `api` job's
  dependency chain; the gate aggregator just gains one `needs` entry.
- The Docker image gains a builder stage. Only the built wheel enters the runtime stage; the Rust
  toolchain and the cargo registry stay out of the shipped image.
- The dev machine, WSL and CI each need a Rust toolchain **only to build**, never to run. Windows needs
  MSVC Build Tools; WSL and CI need build-essential + pkg-config.
- Two implementations of each kernel exist forever. That is the cost, and the parity/property tests plus
  the 2x rule are what keeps it honest. A kernel is deleted, not maintained, if its profile share drops.
- Wheel matrix: `win_amd64` and `manylinux_2_28_x86_64` at Python 3.11 ABI (`abi3`), built in CI and
  attached to the release, not committed to the repository.
- No new runtime service, no new deploy unit, no schema change and no change to any API response.

## Exit criterion

If, 30 days after T-1400 merges, no kernel card has shown a 2x improvement on the recorded baseline in a
real job, the crate is removed and this ADR becomes "Rejected after measurement". Keeping a second
toolchain that does not pay for itself is a cost with no return.
