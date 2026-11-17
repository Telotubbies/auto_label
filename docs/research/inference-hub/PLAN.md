# Inference Hub — plan

Planning lane, 2026-11-17. Baseline `feat/labeldesk-v2` at `0e62dc5`, read in the worktree
`B:/02_Projects/ld-worktrees/plan-inference` on `plan/inference`. Docs only: no application code, no
tests, no merge, no push.

Owner request this plan answers: *a LabelDesk "Inference Hub" with four surfaces — engine installs,
a model catalogue, a VRAM/throughput calculator, and a segmentation-model catalogue wired to the
existing auto-label flow — engineered so that nothing installs or downloads inside the API process,
only on a chosen worker host, and only by a workspace admin.*

Sources read for this plan: `docs/OPENCODE_PM_RULES.md`, `docs/OPENCODE_TEAM_FLOW.md` §1/§4/§4d,
`docs/research/mcp/MCP-PLAN.md` (format), `docs/research/beyond-roboflow/02-training-mlops.md` and
`04-vlm-foundation.md`, `docs/architecture/03-deployment.md`, `docs/adr/0004-ml-own-repo.md`,
`design/labeldesk-v3/VISUAL-OVERRIDE.md`, and the repository itself — `apps/backend/app/{worker,gpu,
config}.py`, `routers/{remote,admin,registry}.py`, `services/{flags,heartbeat,topology,capabilities,
segment}.py`, `models/{training,insights}.py`, `schema/`, `apps/worker/labeldesk_worker/cli.py`,
`apps/frontend/src/{lib/nav,lib/api,routes,features/admin,features/project}`.

**What it contains.** Four surfaces, 23 cards `T-1000`–`T-1022`, ~62.5 agent-hours, and one ADR
([`docs/adr/0005-inference-hub.md`](../../adr/0005-inference-hub.md)). The hub reuses the shipped job
queue, remote-worker claim protocol and heartbeat instead of adding a second control plane: the API
plans and records, the worker executes, and every install/download is a job row with a log tail. The
calculator is one pure Python module behind one endpoint so the numbers have one source and one test
suite, not two.

---

## 0. Team findings, then the merged decision

The plan was written as eight team passes over the same repository, then reconciled. Each subsection
is what that pass found; §0.9 records how the conflicts were settled. §1–§10 are the merged result,
so nothing below is repeated as a separate voice.

### 0.1 R1 — product / PM

- The owner asked for four surfaces but only two of them *act* on a machine (engines, model
  downloads). The calculator and the segmentation catalogue are read-only and can ship first, with no
  privilege, which is the cheapest way to put something useful in front of the owner while the worker
  work lands.
- Buyer value is not "install vLLM"; it is "will this model fit my card, and how fast will it be".
  The calculator is therefore the demo surface, not a side tab.
- The hub is an **admin** surface: a labeler must never see it, and a project manager must not be able
  to install software on the host that serves production inference.
- Smallest complete loop: pick a host → read compatibility → dry-run → confirm → install → see log.
  Model download and segmentation reuse the same loop rather than inventing a second one.
- Non-goals that keep the wave small: serving inference through the hub, benchmark runs that start
  engines, multi-host scheduling, auto-upgrades, fine-tuning. Named in §1.4.

### 0.2 R2 — research

- The public calculators the owner named are consumer tools: `apxml.com/tools/vram-calculator` was
  attempted twice in this lane and returned a multi-megabyte JS payload that the fetch tool refuses,
  so its exact field list is **not** asserted here. What can be asserted is the category: parameter
  count, precision, context, batch/concurrency, GPU preset, tensor parallel, and a fit verdict.
  Labels and layout are ours; no text, screenshot or asset is copied.
- The formulas do have citable primary sources, and they are enough:
  EleutherAI's *Transformer Math 101* (weights = params × bytes/param; inference total ≈ 1.2 ×
  weights), Kipply's *Transformer Inference Arithmetic* (KV cache bytes per token; the memory-vs-FLOPs
  roofline; tensor parallel divides both), and vLLM's *Conserving Memory* (`tensor_parallel_size`,
  `max_model_len`, `max_num_seqs`, CUDA-graph overhead).
- The honest limit: a calculator is an estimate, not a benchmark. Every result must carry its
  assumptions and a range; a number presented without them is a support ticket.
- Engine facts that shape compatibility: vLLM and SGLang are Linux/CUDA-first Python servers;
  llama.cpp runs almost anywhere including CPU and Apple silicon; TensorRT-LLM is the strictest
  (driver, CUDA, TensorRT, often container-only); ONNX Runtime only serves LLMs with
  `onnxruntime-genai`; "Triton" is ambiguous (NVIDIA Triton Inference Server, not the compiler) and
  must be labelled as the server in the catalogue.
- Segmentation memory is a different problem (activations at image resolution, not a KV cache), so
  the catalogue carries measured/vendor figures per resolution instead of pretending the LLM formula
  applies.

### 0.3 UX / UI

- Four surfaces are four tabs of one workspace page (`/:ws/inference`), not four nav entries: the
  owner asked for a hub.
- Visual language is the shipped Liquid Glass system per `VISUAL-OVERRIDE.md`: glass on the tab bar,
  host picker, confirm sheets and job popovers; solid `Card` for dense tables, calculator results and
  logs; no new token, palette, radius or hex.
- The dangerous action is a sheet, never an inline button: the confirm sheet shows the host, the exact
  engines and versions, the bytes to download, the disk after, and a typed acknowledgement. This is
  the same shape as the existing deploy/rollback confirmations, so nothing new is learned.
- Every surface needs the four states the backlog already mandates: empty, loading, error, and a
  permission/flag state. A disabled action always states why ("Not provisioned on this host",
  "Requires a Hugging Face token on the worker").
- Mobile at 375 px: tabs become a select, tables scroll horizontally with a sticky first column, the
  calculator stacks form above results, and the confirm sheet is full-height. Thai strings use the
  shipped Thai-capable stack, never Inter alone.

### 0.4 Backend / API

- The queue already exists and is the right seam: `Job` (workspace-scoped, `project_id` nullable),
  `POST /api/worker/claim` with `X-Worker-Token`, progress/complete/fail, a reaper, and a job kind
  registry. A new control plane would duplicate tenancy, auth, progress and cancellation.
- `REMOTE_JOB_KINDS` currently names `train` and `autolabel`; the worker CLI has a handler map. Adding
  `engine_apply` and `model_pull` there is additive and cannot run in the API process, because the
  embedded worker claims only `LOCAL_JOB_KINDS` and these kinds are never added to it.
- `Worker` is the only host record and has no inventory: `id`, `host`, `kinds`, `current_job`,
  `started`, `last_seen`. One JSON column `inventory` (schema block, no backfill) carries OS, GPU
  name/VRAM, driver, CUDA, free disk, installed engines and model files. Remote workers currently
  write no heartbeat row at all, so the claim path must upsert one.
- Download/install status does not need a new table: the job row plus its log tail is the record, and
  `Audit` is the "who asked" record. A new `host_assets` table would duplicate the worker's own
  inventory and drift from it.
- All routes sit under one router (`routers/inference.py`) and one flag (`task_inference`), so
  "off ⇒ 404" is one dependency, matching `require_flag`.

### 0.5 ML-infra

- Installs must run on the worker, in a per-engine virtual environment under
  `~/.labeldesk/engines/<engine>-<version>`, or as a digest-pinned container. Installing into the
  worker's own environment would let one engine upgrade break training.
- The worker, not the API, resolves what is installed (filesystem + `pip show`/`docker image
  inspect`) and reports it upward. The API never scans a remote host.
- Downloading weights is worker work for the same reason plus a second one: the token and the disk
  live there. Use `huggingface_hub` in the worker extra rather than hand-rolling resume, metadata and
  gated-repo handling; it is the one dependency worth adding because reimplementing it is ~200 lines
  of edge cases.
- Target directory is `LD_MODELS_DIR` (default `~/.labeldesk/models`), separate from `DATA_DIR`, so a
  model download can never fill the database volume.
- Concurrency: one install job and one download job per host at a time; the second enqueue is refused
  with a 409 naming the running job. Two pip installs in parallel on one box is how a working venv
  gets corrupted.
- VRAM: at most one engine server may be started by a future card; v1 installs and reports, it does
  not start servers, so the existing in-process GPU ledger is untouched.

### 0.6 R7 — security

- The boundary that matters is **who may cause code to run on a host**. That is workspace
  `owner`/`admin` only, plus an explicit worker opt-in (`LD_ALLOW_ENGINE_INSTALL=1`), plus a
  deployment-level switch for multi-tenant installs (`LD_INFERENCE_WORKSPACE`). Three locks, one
  action.
- Command injection is designed out, not filtered: the client sends catalogue ids and enum choices;
  the server builds `argv` lists; the worker runs `subprocess.run(argv, shell=False)` with a fixed
  executable allowlist. No user string ever reaches a shell, a path join or a version field.
- Supply chain: exact version pins in the catalogue, container images by `@sha256:` digest, a
  recorded `pip freeze` after install, and no user-supplied index URL. A hash-locked wheelhouse is
  the hardening follow-up, not a v1 claim.
- HF tokens live in the worker's environment (`HF_TOKEN`), never in the database, the job payload,
  the log or an API response. The UI only ever learns "token present: yes/no" from inventory.
- Gated licences are the operator's acceptance on their own Hugging Face account; the UI links to the
  licence and refuses the download with a reason when the worker has no token. LabelDesk never
  accepts a licence on a customer's behalf.
- Disk exhaustion: pre-flight free-space check with a 20% margin in the API, a second check on the
  worker before and during the transfer, a per-host cap (`LD_MODELS_MAX_GB`), partial-file cleanup on
  failure, and a remove action so the remedy is in the product.
- Every enqueue, completion and failure writes an `Audit` row with host, catalogue id, version and
  job id — never a token, never a full path.

### 0.7 QA

- The suite that matters is the one that never touches the network. A fake `pip`/`uv`/`docker` on
  `PATH`, a local HTTP server standing in for the Hugging Face metadata and file endpoints, and an
  assertion that the real hosts were never called. CI must fail if a test opens `huggingface.co`.
- Tests to prove per card: the estimator against hand-computed fixtures; catalogue validation (every
  row has a licence, source URL, size and pin); plan building (argv exactness, rejection of unknown
  ids); permissions (labeler 403, foreign workspace 404, flag off 404); job plumbing (host targeting,
  cancel, log truncation, reaper interaction); download semantics (resume from byte N, checksum
  mismatch deletes the part file, disk-full aborts before writing).
- A mocked end-to-end run is the release gate: hub loads → calculator answers → engine plan → confirm
  → simulated progress → installed state → model download → segmentation handoff.
- Real-hardware verification is a separate, owner-scheduled step and is never claimed by CI.

### 0.8 DevOps / release

- Flag off by default, one flag for the whole hub (`task_inference`), one worker env switch
  (`LD_ALLOW_ENGINE_INSTALL`), one deployment scope (`LD_INFERENCE_WORKSPACE`). Rollback is turning
  the flag off; the only schema change is an additive JSON column, which can stay.
- Release order is calculator → hosts/catalogue → installs → models → segmentation → hardening. Each
  stage is independently shippable and each stage's flag-off state is tested.
- Docs: an operator runbook (which host, which token, which disk, how to undo), a user page (what the
  four tabs do and what the estimates mean), and a support note for the three common failures
  (driver mismatch, disk full, gated repo).
- Monitoring: job outcomes by kind, install duration, free disk per host, heartbeat staleness,
  checksum failures, audit volume. Alerts at disk < 10 GB, three consecutive install failures, and a
  host that stops reporting mid-job.

### 0.9 Conflicts and how they were settled

| Conflict | Ruling | Cost if wrong |
| --- | --- | --- |
| R2 wanted engine compatibility checked in the browser; backend wanted it server-side | **Server-side.** The same rules gate the API, the plan and the job; a browser copy would let the UI offer an install the server then refuses. | One extra round-trip per keystroke-class change; negligible. |
| UX wanted an install button per row; ML-infra wanted one batch job | **One confirm sheet, one job per host, N engines in the payload.** One sheet is the smallest safe confirmation; one job avoids interleaved pip runs. | A failed engine fails the batch and the log names it; retry the remaining row. |
| Backend proposed a `host_assets` table; ML-infra wanted the worker to own truth | **Worker inventory JSON on `Worker`, no new table.** The API renders what the host reports; a table would be a second truth. | History of installed assets is only in audit + job rows, not queryable per asset; acceptable for v1. |
| Security wanted `LD_INFERENCE_WORKSPACE` mandatory; PM wanted the hub to just work on a single-box install | **Optional, defaulting to the deployment's first workspace.** A single-box install needs no configuration; multi-tenant installs must set it. | A multi-tenant deployment that forgets the variable exposes the hub to every workspace admin. The docs and the empty state say so, and the card tests the configured case. |
| QA wanted Playwright against a real worker; ML-infra refused real installs in CI | **Playwright against a mocked worker API**; real hardware is an owner-run smoke, recorded separately. | The e2e proves flow and states, not engine behaviour. Stated on the report. |

---

## 1. Requirements

### 1.1 Personas

| Persona | What they need | What they must never do |
| --- | --- | --- |
| **Workspace owner / admin** (the only actor) | Know whether a model fits the card, install an engine once, download a model once, hand a segmentation model to auto-label | Install on a host that is not theirs, or install without a plan |
| **ML engineer (member)** | Nothing in v1; the hub is an admin surface, and the calculator is admin-only until the owner says otherwise | See or act on the hub |
| **Labeler / reviewer** | Nothing here; they meet the result in auto-label | See the hub at all |
| **Deployment operator (superadmin)** | Bound the hub to one workspace, cap disk, supply `HF_TOKEN` and `LD_ALLOW_ENGINE_INSTALL` | Be bypassed by a workspace admin |

### 1.2 User stories and acceptance criteria

**US-1 — Understand the hardware.** As an admin, I open Inference → Hosts and see each worker's OS,
GPU, VRAM, driver, CUDA, free disk and last heartbeat, so that I choose a host that can actually run
what I am about to install.
*AC:* a host that has not beaten for 45 s reads `offline` with its last-seen time; a host with no GPU
reads `CPU only` and every GPU-only engine is blocked with that reason; an empty deployment shows one
sentence and the worker install command.

**US-2 — Know what is compatible before touching anything.** As an admin, I tick engines and see
compatible / warning / blocked per engine with the reason, the pinned version and the disk needed.
*AC:* compatibility is computed server-side from the host inventory and the catalogue; a blocked row
cannot be selected; changing the host recomputes without a page reload.

**US-3 — See the plan, then install.** As an admin, I press *Review install plan*, read the exact
commands, the bytes and the disk after, tick the acknowledgement, and only then install.
*AC:* the plan endpoint performs no side effect; install without `confirm: true` returns the plan and
a 400-class refusal; a second install on the same host returns 409 naming the running job; progress,
log tail and cancel are visible; failure keeps the log and a safe message.

**US-4 — Uninstall cleanly.** As an admin, I uninstall an engine and the host reports it gone.
*AC:* uninstall runs only for an installed catalogue id; it removes the engine's own environment,
never shared system packages; the confirmation names the engine and host.

**US-5 — Pick a model that fits.** As an admin, I filter the catalogue by family, size, quantisation
and licence, and see the estimated VRAM on the selected host, the download size, and whether it is
already installed.
*AC:* every row shows size and quantisation; a gated row shows the gate and the token state; a row
that does not fit is marked and the download is disabled with the reason; a disk shortfall disables
the action and names the shortfall.

**US-6 — Download safely and resumably.** As an admin, I download a model and can resume after a
network drop.
*AC:* the transfer keeps a partial file, resumes from its offset, verifies the published sha256, and
renames atomically only on success; a mismatch deletes the part file and reports `checksum failed`;
a disk-full condition aborts before writing and again during the transfer.

**US-7 — Estimate VRAM and throughput.** As a workspace admin, I enter parameters, precision,
context, batch, concurrent users and GPU count, and read per-GPU memory, fits/does not fit, and a
tokens/s estimate with its assumptions.
*AC:* results are labelled estimates with a ± range; the assumption panel names every input default
and links the formulas; changing tensor parallel divides weights and KV per GPU and warns when the KV
head count is not divisible; a custom GPU can be entered; nothing is stored.

**US-8 — Choose a segmentation model for auto-label.** As an admin, I see SAM 3.1, SAM2, YOLO-seg and
Mask2Former with VRAM, licence and whether this host is provisioned, and press *Use for auto-label*.
*AC:* the button is enabled only when the model is provisioned and a project is chosen; it opens the
existing auto-label dialog with that model preselected; AGPL is shown for Ultralytics; a missing
checkout names `LD_SAM_ROOT` / `LD_PRETRAINED_DIR` and links the setup doc.

**US-9 — Stay inside the permission boundary.** As a labeler or a plain member, I never see the hub; as
an admin I see it, and every write is gated.
*AC:* the nav entry is absent without the flag or admin role; the routes answer 404 with the flag off
and 403 for a non-admin; workspace isolation returns 404 for a foreign host or project.

**US-10 — Audit the action.** As an owner, I can answer who installed what, on which host, when.
*AC:* one `Audit` row per enqueue with action `inference.engine_install` / `inference.model_download` /
`inference.engine_uninstall` / `inference.model_remove`, naming host, catalogue id, version and job
id, with no token and no absolute path.

### 1.3 Success measures

- An admin can go from opening the hub to a confirmed engine install in under two minutes, without
  reading docs, on the demo host.
- The calculator's VRAM verdict agrees with a real vLLM load for three catalogue models on the demo
  card (owner-run smoke; tolerance ±15% memory).
- Zero install/download work executes in the API process (proved by a test that queues the job with
  only the API running and asserts it stays queued).
- No secret appears in any API response, job row, log tail or audit row (proved by a seeded-token
  test).

### 1.4 Non-goals

Serving inference through the hub (no proxy, no OpenAI-compatible endpoint), starting/stopping engine
servers, benchmark runs, multi-host scheduling or queues, automatic upgrades, fine-tuning, model
conversion, embeddings/rerankers, Kubernetes/Helm, and **Ollama in any form — never installed,
downloaded or invoked**. Model removal is included only as the disk-exhaustion remedy.

---

## 2. Analysis and research

### 2.1 What exists today

| Need | Today | Gap |
| --- | --- | --- |
| Job queue, progress, cancel, retries | `Job` + `app/worker.py` + `routers/remote.py` | no engines/models kinds |
| Remote execution on a GPU host | `labeldesk-worker` claim/progress/complete/fail | no host targeting, no log tail, no inventory |
| Host list | `Worker` rows, admin console table | no OS/GPU/driver/CUDA/disk, no remote heartbeat row |
| GPU state | in-process VRAM ledger (`gpu.py`) | one machine, no per-host truth |
| Model catalogue | `adapters/catalog.py` (detection/VLM refs, not downloadable weights) | no size/quant/licence/gating/checksum |
| SAM / YOLO provisioned state | `SAM_ENABLED`, `LD_SAM_ROOT`, `LD_PRETRAINED_DIR` (`config.py`) | not surfaced anywhere |
| Auto-label | `AutoLabelDialog`, registry, worker `autolabel` handler | no way to arrive with a model preselected |
| Feature flags | `services/flags.py` + `require_flag` | no hub key |
| Audit | `Audit` + `deps.audit` | nothing to audit yet |

### 2.2 Feature matrix against public tools

The owner named `apxml.com/tools/vram-calculator`; in this lane the page returned a >5 MB script
payload and could not be read, so its exact fields are **not** asserted. The matrix records the
capability categories such calculators expose, checked against the sources that *were* read (Eleuther,
Kipply, vLLM docs) and against what LabelDesk needs. "Public calculators" is therefore a category, not
a claim about one vendor's screen. Nothing is copied: no text, layout, screenshot or asset.

| Capability | Public LLM calculators (category) | LabelDesk v1 | Why |
| --- | --- | --- | --- |
| Parameter count → weights | yes | **yes**, catalogue autofill + custom | base of every estimate |
| Precision / quantisation | yes | **yes**: FP32, BF16/FP16, FP8, INT8, INT4 (AWQ/GPTQ), GGUF Q8/Q4_K_M | owner requirement |
| Context length | yes | **yes** | KV cache driver |
| Batch / concurrent users | varies | **yes**, separate batch and users | owner requirement |
| KV cache shown separately | sometimes | **yes**, with GQA head count | the thing buyers get wrong |
| Activations + framework overhead | rarely itemised | **yes**, one itemised line with a stated default | honesty; the weakest term is named |
| Single / multi GPU, tensor parallel | yes | **yes**, with divisibility warning | owner requirement |
| GPU preset + custom | yes | **yes** | owner requirement |
| Fit / does-not-fit verdict | yes | **yes**, per GPU, with usable-VRAM factor | the buyer's question |
| Tokens/s estimate | sometimes | **yes**, memory-bound and compute-bound ceilings, min taken, ± range | owner requirement |
| Assumptions / formula sources | rarely | **yes**, always visible, linked | owner requirement |
| Share / permalink | sometimes | **no** (copy as text instead) | smallest useful form |
| Engine compatibility + install | no | **yes** | differentiator, owner requirement |
| Model download with licence/gating/checksum | no | **yes** | owner requirement |
| Segmentation model catalogue + auto-label handoff | no | **yes** | owner requirement |

### 2.3 Formulas, with sources

Notation: `P` total parameters, `P_a` active parameters (MoE; `P_a = P` otherwise), `b_w` bytes per
weight, `L` layers, `H_kv` key/value heads, `d` head dimension, `s` context tokens, `B` concurrent
sequences, `T` tensor-parallel degree, `V` GPU VRAM, `U` usable fraction.

1. **Weights.** `W = P × b_w`.
   Source: EleutherAI, *Transformer Math 101* — int8 1 B/param, fp16/bf16 2 B/param, fp32 4 B/param.
   <https://blog.eleuther.ai/transformer-math/>
2. **KV cache per token.** `kv_token = 2 × L × H_kv × d × b_kv` (the leading 2 is K and V; `b_kv` is
   the cache dtype, usually 2 for fp16, 1 for fp8).
   Source: Kipply, *Transformer Inference Arithmetic* — `[batch, 2, heads, seq, features]`, and the
   fp16 per-token figure `2·2·L·H·d`.
   <https://kipp.ly/transformer-inference-arithmetic/>
3. **KV cache total.** `KV = kv_token × s × B`, divided by `T` across tensor-parallel ranks.
4. **Activations / workspace.** `A = max(0.05 × W, 256 MiB) × (1 + 0.02 × B)`, per GPU, not divided
   by `T`. This is a **heuristic**, calibrated against a measured load on the demo card; the plan says
   so in the UI. Inference activations are not the training formula (activations are not retained
   across layers); using Eleuther's training formula here would overestimate by an order of magnitude.
5. **Framework overhead.** `O` from the engine's catalogue row (vLLM ~2 GiB with CUDA graphs and one
   `max_num_seqs` capture set; llama.cpp ~0.5 GiB; SGLang ~1.5 GiB; TensorRT-LLM ~2 GiB; plus the
   CUDA context). Sources: vLLM *Conserving Memory* (CUDA graphs consume memory; `enforce_eager`
   removes them; `max_model_len` / `max_num_seqs` bound the profile).
   <https://docs.vllm.ai/en/latest/configuration/conserving_memory.html>
6. **Per-GPU memory.** `M = W/T + KV/T + A + O`. Fits when `M ≤ U × V`, `U` default `0.9` (vLLM's
   `gpu_memory_utilization` default; llama.cpp has no such knob, so the UI uses 0.95 there and says
   so).
7. **Decode throughput, memory-bound.** `tok/s ≈ B × BW_eff / (W + KV_read)` where `KV_read` is the
   cache bytes read per step for the batch and `BW_eff = 0.7 × BW_peak`. This is Kipply's small-batch
   case: time per step ≈ bytes moved / bandwidth, batch divides nothing because the weights are read
   once for the whole batch.
8. **Decode throughput, compute-bound ceiling.** `tok/s ≈ (T × F_peak × MFU) / (2 × P_a)`, `MFU`
   default 0.25 for decode. Kipply: 2 FLOPs per parameter per token; Eleuther: `C ≈ 6PD` for training,
   `2PD` forward.
9. **Time to first token.** `TTFT ≈ (2 × P_a × s + attention term) / (T × F_peak × MFU_prefill)`,
   `MFU_prefill` default 0.4; the attention term is omitted and the omission is stated.
10. **Estimate.** `tok/s_est = 0.8 × min(memory-bound, compute-bound)`, displayed with a `×0.6 … ×1.2`
    range. The factors (`0.7` bandwidth, `0.25`/`0.4` MFU, `0.8` efficiency) are labelled as
    assumptions, not measurements.

**Worked example** (also a unit-test fixture): Qwen2.5-VL-7B-class, `P = 7.6e9`, `b_w = 2` (BF16),
`L = 28`, `H_kv = 4`, `d = 128`, `s = 8192`, `B = 4`, `T = 1`, RTX 4090 (24 GB, 1008 GB/s),
vLLM overhead 2 GiB.

- `W = 7.6e9 × 2 = 15.2e9 B ≈ 14.2 GiB`
- `kv_token = 2 × 28 × 4 × 128 × 2 = 57,344 B ≈ 56 KiB`
- `KV = 57,344 × 8192 × 4 ≈ 1.88e9 B ≈ 1.75 GiB`
- `A = max(0.05 × 14.2, 0.25) × 1.08 ≈ 0.77 GiB`
- `M ≈ 14.2 + 1.75 + 0.77 + 2.0 = 18.7 GiB` → fits in `0.9 × 24 = 21.6 GiB`.
- Decode step: `0.7 × 1008 / (15.2 + 1.75) ≈ 41.6 steps/s`, which is `4 × 41.6 ≈ 166 tok/s`
  across the batch (`≈ 42 tok/s` per sequence).
- Compute-bound: `(1 × 165e12 × 0.25) / (2 × 7.6e9) ≈ 2,700 tok/s` → memory-bound wins; estimate
  `0.8 × 166 ≈ 133 tok/s`, range 80–200.

That last line is the point of the exercise: on one consumer card a 7B VLM is bandwidth-bound, which
is why the calculator must show both ceilings instead of one number.

### 2.4 Engine facts that drive compatibility

| Engine | Runtime | OS | Accelerator | Notes for the catalogue |
| --- | --- | --- | --- | --- |
| vLLM | pip/uv or container | Linux | NVIDIA (CUDA), some ROCm | Python server; CUDA graphs and `gpu_memory_utilization`; version pin must match torch/CUDA |
| SGLang | pip/uv or container | Linux | NVIDIA | Python server; RadixAttention; pin `sglang[all]` |
| llama.cpp | prebuilt binary or container | Linux, macOS, Windows | CPU, Metal, CUDA, Vulkan | GGUF only; smallest footprint; the fallback when no CUDA |
| TensorRT-LLM | container (recommended) or pip | Linux | NVIDIA | strict driver/CUDA/TensorRT match; compiled engines are per-GPU |
| ONNX Runtime | pip (`onnxruntime-gpu`) | all | CPU, CUDA, DirectML | LLM serving needs `onnxruntime-genai`; otherwise it is a runtime for exported vision models |
| Triton (NVIDIA Inference Server) | container | Linux | NVIDIA | **not** the OpenAI Triton compiler; label it "Triton Inference Server" in the UI |

Pins are exact strings in the catalogue with a `source_url` per row; the row is verified when the pin
is set, not guessed in this plan. Docker images are pinned by digest, never by tag.

---

## 3. Architecture

### 3.1 Options considered

| # | Design | New code (LOC, est.) | Verdict |
| --- | --- | --- | --- |
| **1** | **Reuse the job queue and the remote worker**: API plans/records/audits, worker executes `engine_apply` / `model_pull`, inventory rides the heartbeat, one router, one flag | backend ~700, worker ~420, frontend ~900, tests ~750 → **~2,770** | **Chosen.** No second control plane, no new auth model, cancel/progress/reaper already work. |
| 2 | A separate inference-manager service with its own HTTP API and websocket log stream | ~3,400 plus a new deploy unit, Caddy route and health check | Rejected: duplicates tenancy, progress, cancellation, reaper and deploy surface for four screens. |
| 3 | API drives hosts over SSH/Ansible | ~900 | Rejected outright: adds host credentials to the API, a shell boundary, and a second privilege model; command injection risk is the whole feature. |
| 4 | Calculator in TypeScript only (no endpoint) | ~300 | Rejected: the estimate is needed by the catalogue ("fits this host") and by tests; two implementations would drift. Kept as the smaller option if the endpoint is cut. |
| 5 | Hand-rolled Hugging Face downloader (no `huggingface_hub`) | ~200 + edge cases | Rejected for v1: resume, LFS metadata, gated repos and cache layout already solved; the dependency is worker-only and optional. |

### 3.2 Components

```
Browser  :ws/inference  ──►  API (FastAPI)
                              ├─ routers/inference.py     plan, catalogue, estimator, enqueue
                              ├─ services/inference_*     catalogue, compat, estimator, jobs
                              ├─ Job row (kind engine_apply | model_pull)
                              └─ Audit row
                                     │  (existing queue)
                                     ▼
                         Remote worker (labeldesk-worker)
                              ├─ claim: kinds + inventory (upsert Worker)
                              ├─ engine_apply: venv/docker, argv only, log tail
                              ├─ model_pull: HF metadata → disk guard → resume → sha256 → rename
                              └─ progress/complete/fail (existing endpoints)
```

The API never imports an engine, never runs `pip`, never holds `HF_TOKEN` and never reads a model
file. Deleting `routers/inference.py` leaves the rest of the product working, which is the deletion
test.

### 3.3 Data model

No new tables. Two additive changes:

1. `workers.inventory` — `JSON`, nullable, no backfill. Shape:
   ```json
   {"os":"linux","arch":"x86_64","python":"3.12.4","gpus":[{"name":"NVIDIA GeForce RTX 4090",
     "vram_mb":24564,"driver":"550.54","cuda":"12.4"}],"disk":{"models_free_gb":812,
     "models_total_gb":1863},"hf_token":true,"allow_install":true,
     "engines":[{"id":"vllm","version":"<pin>","runtime":"uv","path":"...","ok":true}],
     "models":[{"id":"qwen2.5-vl-7b","variant":"awq","bytes":4700000000,"sha256":"…"}]}
   ```
   Written by the worker on claim and on completion; never by the browser.
2. `jobs.kind` gains two values (`engine_apply`, `model_pull`); `jobs.result` gains `log` (list of
   strings, capped at 200 lines) and `phase`. Both are JSON already in use.

`Audit` gains four action names; `Worker` keeps its existing columns.

### 3.4 API

All under `/api/ws/{ws}/inference`, `Depends(require_flag("task_inference"))`; every route resolves
the workspace from the session, never from a body id.

| Method + path | Who | Purpose |
| --- | --- | --- |
| `GET /hosts` | staff | workers with inventory, online flag, chosen default host |
| `GET /engines?host=` | staff | catalogue rows joined with compatibility + installed state |
| `POST /engines/plan` | admin | dry-run: argv, bytes, disk after, warnings; no side effect |
| `POST /engines/install` | admin | `{host, engines:[{id,version,runtime}], confirm}` → `Job`; 409 if a job runs on that host |
| `POST /engines/uninstall` | admin | `{host, id, confirm}` → `Job` |
| `GET /models?host=` | staff | catalogue + size/quant/licence/gate/installed/fits |
| `POST /models/plan` | admin | dry-run: files, bytes, disk after, gate/token state |
| `POST /models/download` | admin | `{host, id, variant, confirm}` → `Job` |
| `DELETE /models/{id}?host=` | admin | remove a downloaded model (confirm) → `Job` |
| `POST /estimate` | staff | VRAM/throughput estimate; pure, stores nothing |
| `GET /segmentation?host=&project=` | staff | segmentation catalogue + provisioned state; the "use for auto-label" action is a client navigation, not a route |

Job status reuses `GET /api/jobs/{id}` (existing) and its `result.log` / `result.phase`.

### 3.5 Job types and worker protocol

Two kinds, added to `REMOTE_JOB_KINDS` and to the worker's handler map:

- **`engine_apply`** — `params: {host, action: "install"|"uninstall", engines:[{id, version,
  runtime}], plan_id}`. The worker re-validates the plan against its own inventory, runs each engine in
  order, appends a log line per step, reports progress per engine, and fails the job on the first
  non-zero exit while keeping earlier successes listed in `result`.
- **`model_pull`** — `params: {host, model, variant, expected_sha256?, action: "download"|"remove"}`.
  The worker fetches metadata, checks disk, downloads to a partial directory, resumes, verifies, renames, reports
  bytes as progress.

Protocol additions: the inventory field is T-1001's; the job-plumbing additions are all in one card
(T-1008) so later cards extend a service, not the router:

- `POST /api/worker/claim` accepts `inventory` and filters candidates by `params.host` when set.
- The claim upserts the `Worker` row for a remote worker (today only the embedded worker writes one).
- `POST /api/worker/jobs/{id}/progress` accepts `log: list[str] | null` and `phase: str | null`; the
  API appends, caps at 200 lines, and never stores a token.
- `_payload()` gains one dispatch to `services/inference_jobs.payload(db, job)` for the two kinds, so
  later cards extend a service, not the router.

### 3.6 ADR

Drafted at [`docs/adr/0005-inference-hub.md`](../../adr/0005-inference-hub.md): *engine installs and
model downloads run as worker jobs from a server-owned catalogue; the API never executes them; host
truth is the worker's inventory.*

---

## 4. UX

### 4.1 Information architecture

`/:ws/inference` — one page, four tabs, one host picker in the page header (default: the first online
host with a GPU). Nav entry **Inference** in the workspace rail, `owner`/`admin` only, only when
`task_inference` is on. Route added to `RESERVED_WORKSPACE_SEGMENTS` and `WORKSPACE_PAGE_LABELS`.
No project nav entry: the hub is workspace-level; the segmentation handoff deep-links into a project.

### 4.2 Screens and states

**Hosts strip (always visible).** Host name, GPU + VRAM, driver/CUDA, free disk, heartbeat age.
`[empty]` "No worker has reported. Start one with `labeldesk-worker --kinds train,autolabel,
engine_apply,model_pull`." `[loading]` three skeleton chips. `[error]` "Hosts did not load." + Retry.
`[permission]` absent for non-admin (the whole page 404s when the flag is off).

**Tab 1 — Engines.**
1. Table: checkbox, engine, pinned version, runtime (`uv`/`pip`/`docker`), accelerator/OS, disk,
   status (`Not installed` / `Installed <version>` / `Update available` — v1 shows no update flow, so
   the state is `Installed <version>` only), compatibility badge with reason.
2. Blocked row: disabled checkbox, lock icon, reason inline ("Needs CUDA 12.4+; host reports 12.1").
3. Footer: selected count, total disk, `Review install plan` (disabled at zero).
4. Confirm sheet: host, per-engine argv in a monospace block, total bytes, free disk after, a
   checkbox "I understand this installs software on <host>", `Install` / `Cancel`.
   `[error]` inline from the plan endpoint, verbatim but scrubbed; `[loading]` button spinner.
5. Progress: one card per job with phase, percent, last 20 log lines, `View full log` (sheet),
   `Cancel`. `[error]` "Install failed: <safe reason>" + `Copy log`. `[empty]` "Nothing is running."
6. Uninstall: row menu → confirm sheet naming the engine and host; disabled while a job runs.

**Tab 2 — Models.**
1. Filters: family, size band, quantisation, licence, "fits this host", "installed".
2. Table/cards: name, params, quant chips (GGUF Q4_K_M / Q8_0, AWQ, GPTQ, FP8), download size,
   licence badge (link), gate badge (`Gated` / `Open`), engine target, estimated VRAM, installed
   state, action.
3. Download sheet: file list with bytes, total, free disk after, gate/token state, `Download` /
   `Cancel`; a shortfall blocks with "Needs 41 GB, host has 28 GB free."
4. Row states: `Downloading 43%` with resume note; `Verifying`; `Installed`; `Checksum failed` (with
   `Retry`), `Stopped` (with `Resume`).
5. `[empty]` no catalogue match → "No model matches these filters." + `Clear filters`; no host →
   "Pick a host to see what fits."
6. Remove: row menu → confirm; names bytes reclaimed.

**Tab 3 — Calculator.** Two columns on desktop, stacked at 375 px.
Inputs: preset model (catalogue or Custom), params (B), active params (B, MoE), layers, KV heads,
head dim, precision/quant, context, batch, concurrent users, prompt/output tokens, GPU preset or
custom (VRAM, bandwidth, FP16 TFLOPS), GPU count and tensor parallel, engine overhead (default from
engine).
Results: per-GPU table (weights, KV, activations, overhead, total, usable, verdict), total across
GPUs, fit verdict, decode tok/s (memory-bound, compute-bound, estimate + range), TTFT, and an
assumptions panel listing every default with a link to §2.3. `[error]` "KV heads must divide by tensor
parallel." `[loading]` a 150 ms skeleton only if the request exceeds that. `Copy as text`.

**Tab 4 — Segmentation.**
Cards: SAM 3.1, SAM2, YOLO-seg (n/s/m), Mask2Former; VRAM at 512/1024 px, params, licence (AGPL badge
for Ultralytics), source, provisioned state per host (`Ready` / `Missing checkpoint` /
`Not supported on this OS`). Project picker above the grid. `Use for auto-label` → deep link
`/:ws/p/:project/dataset?autolabel=<ref>`; disabled with the reason otherwise. `[empty]` "No
segmentation model is provisioned on this host." + link to setup docs.

### 4.3 Copy rules

LabelDesk voice, sentence case, no vendor marketing. Engine names are product names (vLLM, SGLang,
llama.cpp) and may appear as labels; no engine logo, tagline or screenshot. Numbers always carry a
unit and a qualifier (`estimate`, `pinned`, `reported by the host`). "Install" is never softened to
"add"; the confirm sheet says what will happen.

### 4.4 Accessibility and glass

Glass on the tab bar, host picker, sheets and job popovers; solid `Card` for tables, results and logs.
Focus ring visible on glass, `prefers-reduced-transparency` falls back to `--glass-solid`, contrast AA
at 12 px, log text `tabular-nums`, tables with `caption`/`scope`, sheets trap focus and restore it,
progress uses `role="progressbar"` with a text value. Thai-capable font stack, `text-sm`/`text-xs`
only, no new token.

---

## 5. Security threat model

| # | Threat | Impact | Control (card that proves it) |
| --- | --- | --- | --- |
| 1 | **Command injection** through engine id, version, runtime, host or model id | Arbitrary code on a GPU host | Catalogue-only ids and enums; server-built `argv`; worker `shell=False`; executable allowlist; UUID/host matching; tests send `; rm -rf`, `$(…)`, `../` and assert 400/404 (T-1003, T-1007, T-1008, T-1018) |
| 2 | **Supply-chain substitution** (typosquat, moved tag, rewritten wheel) | Malicious code with the worker's privileges | Exact pins + `source_url`; docker by `@sha256:` digest; no user index URL; post-install `pip freeze` recorded; hash-locked wheelhouse listed as follow-up (T-1002, T-1008) |
| 3 | **HF token leakage** into DB, job payload, log, audit, response | Account takeover, gated-model access | Token only in worker env; inventory reports presence boolean; one scrubber on log tails and error text; a seeded-token test greps every response (T-1011, T-1017, T-1018) |
| 4 | **Gated licence bypass / misrepresentation** | Legal exposure | Gate and licence URL shown; download refused without a worker token; UI states the operator accepted the terms; AGPL badge on Ultralytics (T-1010, T-1012, T-1014) |
| 5 | **Disk exhaustion** filling the data volume or the OS disk | API/DB outage | Separate `LD_MODELS_DIR`; pre-flight with 20% margin; per-host cap; in-transfer checks; `.part` cleanup; remove action (T-1011, T-1013) |
| 6 | **Privilege escalation** — a member or labeler installs software | Host compromise, tenant escape | Workspace `owner`/`admin` only; flag; `LD_INFERENCE_WORKSPACE`; worker `LD_ALLOW_ENGINE_INSTALL`; 403/404 tests (T-1000, T-1017, T-1018) |
| 7 | **Cross-workspace host/project access** through a guessed id | Information leak or install on another tenant's host | Host must come from the workspace's own inventory view; project resolution via `project_ctx`; foreign id → 404 (T-1015, T-1018) |
| 8 | **Arbitrary URL fetch** (SSRF) through a model repo or file URL | Internal network access | Repo id regex, fixed host allowlist (`huggingface.co`, `cdn-lfs*.huggingface.co`), no user URL field (T-1010, T-1011) |
| 9 | **Untrusted model code** (`trust_remote_code`, pickle) | Code execution on load | Prefer `safetensors`; `trust_remote_code=False`; `.bin`/pickle rows warned and not offered in v1 (T-1010) |
| 10 | **Audit blind spot** | Cannot answer who installed what | One audit row per enqueue/terminal state, no secrets; admin screen already renders `Audit` (T-1017) |
| 11 | **Job starvation / stuck host** | Queue wedged, disk half-written | Host-targeted claim, 409 on a second job per host, existing reaper, cancel path, `.part` cleanup (T-1008, T-1011) |
| 12 | **Estimate mistaken for a guarantee** | Wrong purchase/deployment | Results labelled estimate with range; assumptions visible; docs say "not a benchmark" (T-1004, T-1005, T-1022) |

Explicitly out of scope for v1: malicious model weights that exploit the inference runtime, host
root compromise, and subverting the operator's `HF_TOKEN` account. The mitigations above reduce
exposure; they do not make untrusted weights safe, and the docs say so.

---

## 6. Implementation phases and dependencies

| Phase | Cards | Ships | Depends on |
| --- | --- | --- | --- |
| **P0 Shell + estimate** | T-1000, T-1002, T-1004, T-1005 | Page, nav, flag; engine/GPU catalogue; calculator endpoint and screen | none |
| **P1 Host truth** | T-1001, T-1003 | Inventory heartbeat, hosts endpoint, compatibility rules | P0 catalogue |
| **P2 Installs** | T-1006, T-1007, T-1008, T-1009 | Plan/enqueue, engines screen + confirm, worker job, progress/log/cancel/uninstall | P1 inventory + compatibility |
| **P3 Models** | T-1010, T-1011, T-1012, T-1013 | Model catalogue, download job, download UI, assets/remove | P2 job plumbing |
| **P4 Segmentation** | T-1014, T-1015, T-1016 | Segmentation catalogue, screen, auto-label prefill | P1; T-1016 needs only the existing dialog |
| **P5 Hardening** | T-1017–T-1022 | Permissions/audit, adversarial suite, mocked installer, e2e, UI QA, docs | everything above |

Rules: each phase merges with the flag off; a phase is demoable before the next starts. P0 and P1
have no side effects at all. Nothing in P2+ runs on a developer machine without
`LD_ALLOW_ENGINE_INSTALL=1`.

---

## 7. Test strategy

| Layer | What it proves | Where |
| --- | --- | --- |
| Unit — estimator | weights, KV, activation, overhead, TP division, divisibility warning, fit boundary, worked example in §2.3 | `apps/backend/tests/test_inference_estimator.py` |
| Unit — catalogue | every engine/model/GPU/segmentation row has id, licence, source URL, pin/digest, bytes; repo-id regex; no duplicate ids | `test_inference_catalog.py` |
| Unit — compatibility | OS/GPU/driver/CUDA matrix; blocked reasons are stable strings | `test_inference_compat.py` |
| Unit — plan builder | exact argv per engine/runtime; unknown id refused; no shell metacharacter survives | `test_inference_plan.py` |
| Contract | route shapes, 400/403/404/409, OpenAPI regenerated, flag-off 404 for every route | `test_inference_api.py` |
| Worker job | fake `uv`/`pip`/`docker` on `PATH`; success, non-zero exit, cancel, log cap, host targeting | `test_inference_jobs.py`, `apps/worker/tests/` |
| Download | local HTTP fixture: resume from offset, sha256 match/mismatch, disk-full before and during, partial cleanup | `test_model_pull.py` |
| Isolation/adversarial | foreign host/project 404, member 403, injection payloads, token never echoed | `test_inference_isolation.py` |
| CI guard | a socket guard fails the suite on any connection to `huggingface.co`/`pypi.org`/docker registries; no weights in the repo or cache | `conftest` fixture + CI job |
| E2E (mocked) | hub loads, calculator answers, plan → confirm → progress → installed, download → installed, segmentation handoff | Playwright against a mocked worker fixture (T-1020) |
| UI QA | light/dark/375, focus, contrast, no console errors | screenshots in the report (T-1021) |
| Real hardware | one install + one download + one vLLM load on the demo GPU | owner-run smoke, recorded, never claimed by CI |

Test budget: builders run only the touched files; the merge gate is the full serial API suite, worker
tests, node tests, the web build, and the OpenAPI/types check. Download tests use a 1 KiB fixture file,
never a real checkpoint.

---

## 8. Release and rollout

- **Flags.** `task_inference` (workspace override, default off) gates routes (404) and the nav/page.
  `LD_ALLOW_ENGINE_INSTALL=1` on a worker gates execution. `LD_INFERENCE_WORKSPACE=<ws id>` scopes
  the hub when the deployment has more than one workspace; unset means the first workspace.
  `LD_MODELS_DIR`, `LD_MODELS_MAX_GB`, `HF_TOKEN` are worker env.
- **Migration.** One `ADD COLUMN workers.inventory JSON` via `schema/insights.py` + `STEPS`; no
  backfill; safe on an existing database (tested on both empty and populated).
- **Rollout.** P0/P1 to the demo workspace with the flag on; P2 in a lab host with
  `LD_ALLOW_ENGINE_INSTALL=1`; then the demo host; P3/P4 after one clean install and one clean
  download. Each stage is announced in the ledger.
- **Rollback.** Turn `task_inference` off (routes 404, nav gone, no job can be enqueued); unset
  `LD_ALLOW_ENGINE_INSTALL` (running jobs finish or are cancelled; no new ones). Schema stays. An
  installed engine or downloaded model is removed with the product's own uninstall/remove jobs, or by
  the operator on the host.
- **Compatibility.** No change to `train`/`autolabel` payloads; the claim filter only narrows when
  `params.host` is present; existing workers that do not send inventory still claim train/autolabel.

---

## 9. Operations and monitoring

| Signal | Source | Alert |
| --- | --- | --- |
| Job outcomes by kind (`engine_apply`, `model_pull`) | `jobs` status + `result.phase` | 3 consecutive failures on one host |
| Install/download duration | `jobs.started`/`finished` | > 60 min for an install, > 6 h for a download |
| Free disk per host | `workers.inventory.disk` | < 10 GB or < 10% |
| Heartbeat staleness | `workers.last_seen` | offline mid-job (existing reaper fails the job) |
| Checksum failures | `result.phase == "checksum_failed"` | any occurrence |
| Audit volume | `audit` where `action LIKE 'inference.%'` | unexpected actor or host |
| Log size | `result.log` length cap | never exceeds 200 lines (test) |

Runbook: driver mismatch → show the required/allowed range and the host's reported value; disk full →
remove a model or raise the cap; gated repo → provision `HF_TOKEN` on the worker, never in the UI; host
offline → restart the worker with the install kinds and confirm the inventory appears. Logs never
contain tokens or full paths; support asks for the job id.

---

## 10. Risks and open owner questions

### 10.1 Risks

| # | Risk | Likelihood / impact | Mitigation |
| --- | --- | --- | --- |
| 1 | Estimate is wrong enough to mislead a purchase | Medium / medium | range + assumptions + "not a benchmark"; calibrate on the demo card; a measured-benchmark card later |
| 2 | Engine pins rot (CUDA/torch matrix moves) | High / medium | pins carry `source_url` and a checked date; a compatibility test fails loudly when a pin is stale; docs say re-verify per release |
| 3 | An install breaks the worker's training environment | Medium / high | per-engine venv or container; never install into the worker env; uninstall removes only its own venv |
| 4 | Model download fills the disk | Medium / high | separate dir, cap, pre-flight and in-transfer checks, remove action |
| 5 | Multi-tenant install on a shared host | Low / high | `LD_INFERENCE_WORKSPACE`; admin-only; audit; documented |
| 6 | `huggingface_hub` API drift | Medium / low | pin the worker extra; wrap in one `services/hf.py` with a narrow surface |
| 7 | GPU host has no outbound network | Medium / medium | the job fails with the engine's own message; docs offer an offline `LD_MODELS_DIR` pre-seed (manual, out of scope for v1) |
| 8 | The calculator's custom-model path accepts nonsense | Low / low | ranges validated server-side; 422 names the field |

### 10.2 Open questions for the owner

1. **Host scope.** Is v1 for the single demo GPU box, or must it target a fleet from day one? This plan
   targets a host by name and allows many hosts, but schedules no pools or quotas.
2. **Docker allowed?** May the hub run digest-pinned containers on the demo host, or is pip/uv only?
   Container support is more reproducible but needs a working container runtime on the host.
3. **HF token placement.** Recommended: operator sets `HF_TOKEN` on each worker. Alternative: store it
   per workspace via `secretbox` and hand it to the worker in the job payload (weaker). Confirm.
4. **Mandatory engines.** vLLM, llama.cpp and SGLang in v1, with TensorRT-LLM / ONNX Runtime GenAI /
   Triton Inference Server as catalogue rows that can be flagged off? Or all six in v1?
5. **Tenant model.** Is the hub deployment-scoped (one workspace) or per-workspace on shared hosts?
   This plan assumes deployment-scoped with `LD_INFERENCE_WORKSPACE`, and no per-workspace quotas.
6. **Auto-label default.** Does *Use for auto-label* only prefill the dialog once, or also save the
   project's default auto-label model? This plan prefills only.
7. **Disk policy.** What is the per-host cap (`LD_MODELS_MAX_GB`) and may an admin delete downloaded
   weights from the UI? This plan allows remove with confirmation.
8. **Licence acceptance.** Confirm that accepting Llama/Gemma terms is the operator's action on their
   own Hugging Face account, and LabelDesk only records that a token is present.
9. **Measured benchmarks.** Is "estimate only" acceptable for v1, with a follow-up card that starts an
   engine and measures real tok/s?
10. **Ollama.** Confirm the permanent exclusion (no install, no download, no invocation) is a product
    rule, not just this wave's rule.
11. **Member access to the calculator.** v1 is admin-only. Should a plain member get a read-only
    calculator (no hosts, no catalogue), or is that an admin tool too?

---

## 11. Card index

`T-1000`–`T-1022`, 23 cards, ~62.5 agent-hours, every card 1–3 h, tests first. Full cards live in
[`docs/research/roboflow-parity/backlog/`](../../roboflow-parity/backlog/) and the wave table is
appended to `INDEX.md` as **wave I**.

| Phase | Cards |
| --- | --- |
| P0 shell + estimate | T-1000, T-1002, T-1004, T-1005 |
| P1 host truth | T-1001, T-1003 |
| P2 installs | T-1006, T-1007, T-1008, T-1009 |
| P3 models | T-1010, T-1011, T-1012, T-1013 |
| P4 segmentation | T-1014, T-1015, T-1016 |
| P5 hardening | T-1017, T-1018, T-1019, T-1020, T-1021, T-1022 |

Merge order is the id order except where a card names a dependency; the file sets are disjoint except
the shared registries listed in the wave section and in each card.
