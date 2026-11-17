# Inference Hub — operator runbook

For the person who installs, watches and undoes the Inference Hub on a real deployment. A workspace
admin reads [`INFERENCE-HUB-USERS.md`](INFERENCE-HUB-USERS.md) instead; this page is about the
machine.

**Status of the evidence.** Everything in this page was verified with mocked tests: fake
`uv`/`python`/`docker` executables, a local HTTP fixture in place of Hugging Face, and an HTTP fake of
the Ollama API. One install, one download and one model load still have to be run on the demo GPU by
the owner, and no number in this page comes from that run. Section 11 says exactly what is proven and
what is not.

---

## Rollback

Read this before you turn the hub on. It is four steps and it is reversible at every one of them.

1. **Turn the flag off.** Settings → Feature flags → the row whose key is `task_inference` off, for the
   workspace. For a whole deployment, remove `task_inference` from `LD_FLAGS_ON` in the API's `.env`
   and restart the API. Effect: `GET /api/ws/<ws>/inference/hosts` and every other hub route answer
   `404`, the **Inference** rail entry disappears, the page is gone, and no new install or download
   can be queued. Jobs already finished keep their history.
2. **Unset `LD_ALLOW_ENGINE_INSTALL` on every worker** (delete the line, or set it to `0`) and restart
   the worker. Effect: a job already running finishes or is cancelled from the page; a job still
   queued fails with `installs_disabled`. Nothing new can install or download. Training and
   auto-label claim are unaffected.
3. **Remove what was installed, with the product's own action.** Engines → row menu → **Uninstall**;
   Models → **Manage on host** → **Remove**. Both are jobs, both are logged. If the host is already
   gone, do it by hand on that host:
   - container runtime: `docker rmi <the @sha256 digest from the engine catalogue>`
   - venv runtime: `rm -rf <engines-dir>/<engine-id>-<version>`
   - a downloaded model: `rm -rf <models-dir>/<model-id>`
4. **What stays behind, on purpose.** The `workers.inventory` column, the `engine_apply` and
   `model_pull` job kinds, and the audit rows. All three are inert with the flag off; removing them is
   a schema change for a later release. A rollback never deletes audit history.

Verify the rollback: the rail has no **Inference**, a hub URL returns `404`, and
`/api/readyz` is still green. The database needs no migration in either direction.

---

## 1. What the hub does

The hub is where an admin prepares a machine to run models: install an engine, download a model onto
a host, size a model against a card, and hand a segmentation model to auto-label. It does **not**
serve inference, benchmark anything, or start an engine for you.

Four surfaces, all under `/:workspace/inference` (tab in the URL as `?tab=`):

| Tab | Question it answers | Who may open it | What it writes |
| --- | --- | --- | --- |
| **Engines** | Can this host run vLLM / Ollama / llama.cpp / SGLang, and what exactly will be installed? | owner, admin | one `engine_apply` job + audit, per confirmed action |
| **Models** | Which model fits this host, and what does it cost in disk? | owner, admin | one `model_pull` job + audit |
| **Calculator** | Does this model fit this card, and how fast will it roughly be? | any member (API); page is admin-gated in this release | nothing |
| **Segmentation** | Which segmentation model is provisioned here, and which project may use it? | owner, admin | nothing; the handoff is a link |

What runs where:

```
browser ──► API (/api/ws/<ws>/inference)  ── plan, catalogue, estimate, one Job row, one audit row
                │
                ▼  existing job queue
            worker host (labeldesk-worker) ── engine_apply: venv or container, catalogue argv only
                                           └─ model_pull:  metadata → disk check → resume → sha256 → rename
```

The API never runs `pip`, never pulls an image, never reads a model file and never holds the Hugging
Face token. Deleting the hub's router leaves the rest of the product working.

---

## 2. The three locks

Three separate switches, in three places, all closed by default. An install needs all three open plus
an admin role.

| Lock | Where it lives | What it stops | How to check it |
| --- | --- | --- | --- |
| `task_inference` | workspace flag, default off; `LD_FLAGS_ON` forces it on for a whole deployment | every hub route (`404`) and the rail entry | Settings → Feature flags lists it |
| `LD_INFERENCE_WORKSPACE` | API process env, a workspace slug or id; unset = not pinned | every other workspace's hub (`404`) on a shared deployment | `echo $LD_INFERENCE_WORKSPACE` on the API host |
| `LD_ALLOW_ENGINE_INSTALL=1` | worker process env | every install and download; without it the job fails `installs_disabled` | the host row shows installs enabled in `workers.inventory` |

The fourth gate is the role: every hub route except the calculator answers `403` to a member, and a
project manager role never grants it.

Why all three: the flag keeps an unfinished surface out of the product, the workspace pin keeps a
multi-tenant deployment from letting one tenant install software on another tenant's host, and the
worker lock means a worker that somebody started for training cannot be talked into installing
software by a leaked admin session.

---

## 3. Environment reference

API process:

| Name | Default | What it does |
| --- | --- | --- |
| `task_inference` | off | the workspace flag; on enables the routes and the rail |
| `LD_FLAGS_ON` | empty | comma-separated flags forced on for every workspace, e.g. `task_inference` |
| `LD_INFERENCE_WORKSPACE` | empty | pins the hub to one workspace (slug or id); empty means the deployment serves any workspace |
| `LD_WORKER_TOKEN` | — | the shared worker secret the API already uses; unchanged by the hub |

Worker process:

| Name | Default | What it does |
| --- | --- | --- |
| `LD_ALLOW_ENGINE_INSTALL` | unset | `1` accepts install and download jobs; anything else refuses them |
| `LD_MODELS_DIR` | `~/.labeldesk/models` | where downloaded weights live; also the free-space figure the hub reports |
| `LD_ENGINES_DIR` | `~/.labeldesk/engines` | where venv engines are built, and the boundary every argv path is checked against |
| `LD_MODELS_MAX_GB` | unset | **not read in v1.** The owner's disk policy is one model per host, so there is no GB cap setting. The Models tab's low-disk line still names this variable; what actually protects the disk is the one-model rule plus the downloader's 20 % free-space margin. If a deployment sets it, nothing honours it yet |
| `HF_TOKEN` | unset | the Hugging Face token, **only** here. Read at pull time, passed to the hub call, never written to a log, an error, a job payload, an audit row or an API response |

`HF_TOKEN` also decides one thing the UI shows: a gated model is offered only on a host whose
inventory says a token is present. The API stores a boolean, never the value.

---

## 4. Worker flags

```bash
labeldesk-worker \
  --server https://api.example.com \
  --token <LD_WORKER_TOKEN> \
  --kinds train,autolabel,engine_apply,model_pull \
  --engines-dir /srv/labeldesk/engines \
  --models-dir /srv/labeldesk/models \
  --name gpu-demo \
  --device 0
```

| Flag | Why it matters here |
| --- | --- |
| `--kinds` | the worker only claims what it lists. The default is `train,autolabel`; **add `engine_apply,model_pull`** or no hub job is ever claimed |
| `--engines-dir` | the install target and the sandbox: a path argument that would land outside it is refused before anything runs (`LD_ENGINES_DIR`) |
| `--models-dir` | the download target, the `.part` trees, and the free-space number the hub shows (`LD_MODELS_DIR`) |
| `--name` | the host id the hub lists and jobs are aimed at; keep it stable |
| `--once` | one job then exit; for a smoke run, not for a service |

A worker that lists the two extra kinds and does not set `LD_ALLOW_ENGINE_INSTALL=1` still heartbeats
its inventory; it just refuses the work with one sentence instead of failing halfway.

---

## 5. Disk layout

| Path | Contents | Back it up? |
| --- | --- | --- |
| `<models-dir>/<model-id>/<variant>/…` | verified weights, renamed into place only after the checksum matches | no, re-download |
| `<models-dir>/<model-id>/<variant>/*.part` | an interrupted or failed download; deleted on the next attempt | never |
| `<engines-dir>/<engine-id>-<version>/` | one venv per engine (`uv`/`pip` runtime) | no, reinstall |
| container runtime | an image pinned by `@sha256:` digest; no directory in `--engines-dir` | no, re-pull |
| API `LD_DATA_DIR` | database, uploads, exports — **never** weights | yes, as today |

Two rules keep this safe: a model download refuses to touch the last 20 % of free space, and a host
holds at most one downloaded model, so the ceiling is the largest single model plus an engine.
`LD_MODELS_DIR` should be its own filesystem when you can afford it: a full model disk should not be
the disk the database sits on.

---

## 6. First install, step by step

Assumes a running API (`/api/readyz` green), a workspace where you are owner or admin, and a GPU host
with Docker, an outbound route to the container registry and to `huggingface.co`, and nothing else
installed. Substitute your own hostname, workspace slug and host name.

1. **Open the API's locks.** In the API `.env`: `LD_FLAGS_ON` gets `task_inference`, and
   `LD_INFERENCE_WORKSPACE` gets the workspace slug if this deployment serves more than one
   workspace. Then `sudo docker compose up -d` (or restart the API process).
2. **Prepare the worker host.**
   ```bash
   sudo mkdir -p /srv/labeldesk/models /srv/labeldesk/engines
   sudo chown "$USER" /srv/labeldesk/models /srv/labeldesk/engines
   ```
3. **Install the worker with its inference extra.** The base worker is enough for training; a model
   download needs `huggingface_hub`, and the job says so if it is missing.
   ```bash
   pip install "git+https://github.com/Telotubbies/auto_label.git#subdirectory=apps/worker"
   pip install "labeldesk-worker[inference]"
   ```
4. **Give it a token only if a gated model is in scope.** `export HF_TOKEN=<the token from the
   Hugging Face account that accepted the model's terms>`. Leave it unset otherwise; the hub will
   mark gated rows as needing a token instead of failing them mid-download.
5. **Open the worker locks and start it.**
   ```bash
   export LD_ALLOW_ENGINE_INSTALL=1
   export LD_MODELS_DIR=/srv/labeldesk/models
   export LD_ENGINES_DIR=/srv/labeldesk/engines
   labeldesk-worker --server https://api.example.com --token <LD_WORKER_TOKEN> \
     --kinds train,autolabel,engine_apply,model_pull --name gpu-demo --device 0
   ```
6. **Confirm the host reported.** Open `/:workspace/inference`. The host picker lists `gpu-demo` with
   its GPU, driver, CUDA and free disk. No host means the worker never claimed: check the token, the
   `--kinds` list and the API's `labeldesk.inference` log.
7. **Install the engine.** Engines tab: **Ollama** is the first row and the default selection. Tick
   it, choose the `docker` runtime, press **Review install plan**. The sheet shows the digest-pinned
   argv, the bytes and the free disk after the install; tick the acknowledgement and press
   **Install**. The job card shows `Installing ollama`, then `Installed 0.40.16`.
8. **Start Ollama itself.** The install pulls the image; it does not start a server. On the host:
   ```bash
   docker run -d --gpus all --name labeldesk-ollama -p 127.0.0.1:11434:11434 \
     ollama/ollama@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592
   ```
   The worker checks `GET http://127.0.0.1:11434/api/version` before a pull, so a stopped server
   fails one job with one sentence instead of a stack trace. That address is loopback only; do not
   publish it.
9. **Pull the first model.** `qwen3:4b` is the smallest catalogue tag. The Models tab lists it; in
   this release its **Pull** action is the endpoint, because the tab's Download button covers Hugging
   Face variants only:
   ```bash
   curl -X POST "https://api.example.com/api/ws/<workspace>/inference/models/ollama/pull" \
     -H "Authorization: Bearer <a workspace admin API key>" \
     -H "Content-Type: application/json" \
     -d '{"host": "gpu-demo", "tag": "qwen3:4b", "confirm": true}'
   ```
   `confirm` must be the JSON boolean `true`; a quoted `"true"` is refused, by design.
   Or download a Hugging Face variant from the tab: pick a model, pick a variant, **Download**, read
   the files/bytes/disk-after sheet, confirm, watch `Downloading` → `Verifying` → `Installed`.
   A host that already holds a model refuses the second one until you remove the first.
10. **Check the calculator.** Calculator tab: RTX 4090 preset, 7B, BF16, 8192 context, batch 4 →
    **Fits** and a tok/s estimate with its range. You should see the same weights/KV/overhead
    breakdown the user page documents. Nothing is stored by this tab.
11. **Check the segmentation handoff.** Segmentation tab: choose a project, find a row that says
    **Ready**, press **Use for auto-label**. The dataset opens with the Auto label dialog and that
    model already selected. A row that is not ready says why instead of offering the button.

Success looks like: one host with fresh inventory, one engine `Installed`, one model `Installed`, a
Fits verdict in the calculator, and a dataset dialog with a segmentation model preselected. If any of
the four is missing, section 8 is the table to read.

---

## 7. Day-2 operations

- **One job per host.** A second install or download on the same host is refused with `409` and the
  id of the job that is running. Cancel that job first.
- **Four actions a minute per user.** Alternating installs and downloads share the budget; the
  `429` carries `Retry-After`.
- **Cancel** is on the job card. It stops the process group and removes what was being built; a
  download leaves its `.part` tree, which the next attempt overwrites.
- **Uninstall** and **Remove** are confirmed jobs too; they name the engine/model and the host.
- **Audit.** Every enqueue writes `inference.engine_install`, `inference.engine_uninstall`,
  `inference.model_download` or `inference.model_remove` with the actor, the host, the catalogue ids,
  the plan id and the job id. No token, no home path.
- **Logs.** The API logs to the `labeldesk.inference` logger with `ws`, `role`, `host`, `outcome`,
  `job` and `ms`. `inference.host_miss` and `inference.rate_limited` are the two you will see when an
  admin is guessing ids or clicking too fast.

Watch these, in this order:

| Signal | Where | Alert at |
| --- | --- | --- |
| Job outcome by kind (`engine_apply`, `model_pull`) | `jobs.status`, `result.phase` | 3 consecutive failures on one host |
| Install / download duration | `jobs.started`, `jobs.finished` | > 60 min install, > 6 h download |
| Free disk on the models volume | `workers.inventory.disk.models_free_gb` | < 10 GB or < 10 % free |
| Heartbeat staleness | `workers.last_seen` | offline mid-job (the reaper fails the job) |
| Checksum failures | `result.phase == "checksum_failed"` | any occurrence |
| Audit volume | `audit` where `action LIKE 'inference.%'` | an unexpected actor or host |
| Log tail size | `result.log` | never above 200 lines |

---

## 8. Troubleshooting

Each row gives the symptom the console shows, the cause, the fix, and what to quote when you ask for
help: **the job id**. It is on the job card, in the job's URL, and in `GET /api/jobs/<id>`; the API
log line for the same job carries it too. Never paste a token: the job's log tail is scrubbed of
anything token-shaped and of a home directory path before it is stored, but an engine's own output
can still name a file, so paste the job id and let support read the log.

| Failure | Symptom | Cause | Fix | Quote |
| --- | --- | --- | --- | --- |
| **Driver mismatch** | Row is disabled with "Needs driver 575.51 or newer; the host reports 550.54." | The engine pin needs a newer NVIDIA driver or CUDA than the host has | Update the driver on the host and restart the worker so inventory is fresh, or install an engine the host supports (llama.cpp, Ollama) | the job id if a job exists, else the host name and the two version numbers |
| **Disk full** | `disk_full: download needs 41.2 GB, 27.9 GB free; the download keeps 20% of the disk free, short by 5.4 GB.` | The model does not fit the volume, or a previous `.part` tree is still there | Remove a model (one model per host), move `LD_MODELS_DIR` to a bigger filesystem, or pick a smaller quantisation | the job id; the message already names the numbers |
| **Gated repo** | The row says **Gated** and the download is blocked with "This model needs a Hugging Face token on the worker." | The weights need accepted terms on a Hugging Face account and a token on the host | Accept the model's terms with the account that owns the token, put the token in the worker's `HF_TOKEN`, restart the worker | the job id, if one was queued; never the token |
| **Host offline** | Host chip offline; the plan says "This host is offline; its last report is shown, but installs are blocked." | The worker stopped, lost the network, or was started without the two job kinds | Restart the worker with `--kinds …,engine_apply,model_pull`, confirm the inventory timestamp moves again | the host name and the job id of the stuck job |
| **Checksum failed** | `checksum_failed: <file> does not match the repository's digest` and the partial tree is gone | A truncated or corrupted transfer, or a changed upstream file | Retry the download; if it fails twice, re-verify the catalogue pin against the upstream revision | the job id and the file name from the message |
| **Stale plan** | `stale_plan: this install plan no longer matches the host; review the install plan again` | The host's inventory moved between reviewing the plan and running it: a driver update, a new engine, or free disk changed by more than 1 GB | Press **Review install plan** again and confirm the new sheet | the job id and the old plan id from the audit row |

Two more conditions worth knowing, because they are not the hub's fault:

- `installs_disabled: this worker does not accept engine installs (set LD_ALLOW_ENGINE_INSTALL=1 on
  it)` means the worker lock is closed. That is a configuration state, not a failure; fix it on the
  host and re-queue.
- `ollama_unreachable: no answer from http://127.0.0.1:11434/api/version` means the image is installed
  but no Ollama server is running on that port. Step 8 starts it.

The log tail in a job carries the engine's own last line, capped at 200 lines and scrubbed of anything
token-shaped and of a home directory path. If the last line is not enough, the full log is on the
worker's stdout.

---

## 9. Security limits

- **The token rule.** `HF_TOKEN` lives in the worker's environment. It is not sent to the API, not
  stored in the database, not put in a job payload, not written to a log or an error, and never
  accepted from the UI. The inventory reports only that a token is present. Anything token-shaped in
  host output is redacted before it is stored.
- **What the guards stop.** Engine and model ids are catalogue ids, never client strings; the argv is
  built on the server from the catalogue; the worker re-checks the executable against an allowlist,
  refuses shell metacharacters, refuses a path that leaves `--engines-dir`, and runs with a minimal
  environment so `HF_TOKEN` cannot reach an installer. Containers are pulled by digest, never by tag.
- **Outbound URLs.** A download may only reach an `owner/name` repository on the allowlisted Hugging
  Face hosts; there is no URL field anywhere in the UI.
- **Untrusted weights.** The catalogue prefers `safetensors` and does not offer pickle rows in v1.
  This reduces exposure; it does not make an untrusted model safe to run, and the hub does not claim
  otherwise.
- **Deployment caveat.** A multi-tenant deployment that leaves `LD_INFERENCE_WORKSPACE` unset exposes
  the hub to every workspace, because the hub is deployment-scoped by design. Set it.

---

## 10. What this release replaces, and what it does not

- Training and auto-label payloads are unchanged. A worker that does not send inventory still claims
  `train` and `autolabel`.
- The hub does not replace `docs/DEPLOY.md`; that page still owns the API, the database and the
  training worker.
- The hub does not serve inference. Pointing a project's deploy page at a self-hosted endpoint is a
  different feature.

---

## 11. What was verified, and what still needs the real GPU

| Claim | How it was verified |
| --- | --- |
| Routes, flag-off `404`, admin `403`, cross-workspace `404` | pytest against the real app with a test database |
| Plan argv, catalogue-only ids, injection payloads refused | pytest; fake `uv`/`python`/`docker` record the exact argv |
| Download resume, checksum match and mismatch, disk-full before and during | pytest against a local HTTP fixture, 1 MiB file |
| Install and download jobs end to end, cancel, log cap, host targeting | pytest with fake executables and a fake hub |
| The four surfaces, the states, light/dark/375 px | Playwright on a mocked worker, plus UI QA screenshots |
| Ollama as the first engine, its tag catalogue and its health check | pytest against an HTTP fake of the Ollama API |

| Claim | Status |
| --- | --- |
| One real `docker pull` of the Ollama image, then one `ollama pull qwen3:4b` | **owner-run smoke on the demo GPU** |
| One real Hugging Face download with a real `HF_TOKEN` | **owner-run smoke** |
| A real vLLM or Ollama load and a measured tok/s | **not done; the calculator is an estimate, not a benchmark** |
| Driver/CUDA compatibility against a real card | **only as good as the pin's `checked_on` date; re-verify per release** |

Nothing above may be quoted as a benchmark. The calculator says "Estimate, not a benchmark" on the
page, and the range is `×0.6 … ×1.2` of the estimate by construction.

---

## 12. Where the rest lives

| Document | What it covers |
| --- | --- |
| [`INFERENCE-HUB-USERS.md`](INFERENCE-HUB-USERS.md) | the user page: the four tabs, the estimate, gated licences, auto-label |
| [`research/inference-hub/PLAN.md`](research/inference-hub/PLAN.md) | the plan, the formulas with sources, the threat model, the owner decisions |
| [`adr/0005-inference-hub.md`](adr/0005-inference-hub.md) | why installs run on the worker and not in the API |
| [`DEPLOY.md`](DEPLOY.md) | API, database, web and the training worker |
