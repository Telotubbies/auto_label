# MLflow parity — Area 3: Models and deployment

Baseline `feat/labeldesk-v2` @ `f6feb09`. MLflow docs read at 2026-11-17. Release notes window
2025-11-17 → 2026-11-17 checked at https://github.com/mlflow/mlflow/releases (via
`api.github.com/repos/mlflow/mlflow/releases`, 60 releases, docs version at read time **3.18.0**).

**Doc pages covered (full navigation walk).** The seed `/docs/latest/models.html` is now a redirect
stub to `/docs/latest/ml/model/`; the sidebar under *Build → MLflow Model* plus *Deploy* and
*GenAI* was walked from there, and the URL list was cross-checked against
`https://mlflow.org/docs/latest/sitemap.xml` so no page in the section is missed.

Models
- https://mlflow.org/docs/latest/ml/model/ (redirect target of `models.html`)
- https://mlflow.org/docs/latest/ml/model/signatures/
- https://mlflow.org/docs/latest/ml/model/dependencies/
- https://mlflow.org/docs/latest/ml/model/python_model/
- https://mlflow.org/docs/latest/ml/model/models-from-code/
- https://mlflow.org/docs/latest/ml/community-model-flavors/
- https://mlflow.org/docs/latest/ml/tracking/pickle-free-models/
- https://mlflow.org/docs/latest/ml/deep-learning/transformers/large-models/
- https://mlflow.org/docs/latest/ml/model-registry/ (only the version/alias/URI contract; the rest is area 2)

Deployment
- https://mlflow.org/docs/latest/ml/deployment/
- https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/
- https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-sagemaker/
- https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-modal/
- https://mlflow.org/docs/latest/ml/docker/
- https://mlflow.org/docs/latest/ml/plugins/
- https://mlflow.org/docs/latest/cli.html (`mlflow models serve|predict|build-docker|generate-dockerfile`,
  `mlflow deployments create|update|delete|predict|explain|run-local`, `mlflow sagemaker deploy`)
- https://mlflow.org/docs/latest/api_reference/python_api/mlflow.deployments.html

GenAI (only what touches packaging/serving)
- https://mlflow.org/docs/latest/genai/flavors/
- https://mlflow.org/docs/latest/genai/serving/

Pages that produced no row: `ml/docker/` (30 lines, only the `ghcr.io/mlflow/mlflow` image and its
tags — nothing a LabelDesk user clicks), `ml/model/models-from-code/` (reached from the Models sidebar;
its behaviour — `set_model()`, no pickle, the script is executed once at log time — is described on the
model overview page, so it is folded into row 3.3 rather than rowed twice),
`ml/deep-learning/transformers/large-models/` (folded into row 3.13). `ml/projects/`, `ml/search/*` and
`self-hosting/*` belong to areas 5 and 1.

## Area count

15 rows: 0 HAVE · 10 PARTIAL · 5 MISSING.

## 3.1 Every model family states what it can do

**What it does.** A model is a directory whose `MLmodel` file lists the *flavours* it can be read as;
each built-in flavour (python_function, sklearn, pytorch, onnx, transformers, …) adds the
`python_function` flavour so any downstream tool can load it as a plain Python callable. A flavour is
a declared contract — what input shapes it accepts (DataFrame for tabular, tensors for deep learning)
and how it is loaded — not a code path hidden in the server. `(MLF: https://mlflow.org/docs/latest/ml/model/)`
**UX flow, click by click.**
1. **Models** (`/:ws/:project/models`) — each card shows the family that produced the model, the task,
   the class count and the licence. [empty: "No models yet."] [loading: the list shows three skeleton
   cards] [error: the list request fails → one inline line "Models could not load — retry", the Train
   action stays usable]
2. **Model detail** — a "Runs on" block lists every runtime that can execute this artefact, the input
   it expects (image / tensor / text+image) and the reason a runtime is unavailable, instead of
   dropping the runtime.
3. **Export** — the dialog only offers the formats the family can actually produce; a disabled format
   keeps its label and shows why.
**LabelDesk:** PARTIAL — `apps/backend/app/adapters/base.py:26` (`Adapter` protocol: `probe()`,
`capabilities(variant)`, `predict(...)`), `apps/backend/app/adapters/__init__.py:2` (six built-in
families registered on import), `apps/backend/app/services/edge.py:25` (`PRESETS`, each with `format`,
`requires`, `needs_data`, `verified`). The capability set exists in code but is never written into the
artefact and never shown: no format lists `input_kind`, and `verified` is only surfaced inside the
edge dialog.
**Priority:** Must · **Size:** M
**Decision:** `Build (our store/UI)` — our six families are ours; the flavour registry is a lookup
table, not a library contract worth a dependency.
**Roboflow overlap:** `6-F6.1` → T-310, T-311 (runtime catalogue) — this row is the *model-family*
capability, which that catalogue does not carry.
**Sources:** https://mlflow.org/docs/latest/ml/model/, https://mlflow.org/docs/latest/ml/deployment/

## 3.2 One interface that loads any model

**What it does.** `mlflow.pyfunc.load_model(uri)` returns a `PyFuncModel` whose `predict` accepts a
DataFrame, ndarray, list, dict or string and returns a scalar/collection; `predict_stream` yields
chunks. `load_model` assumes dependencies are present and installs nothing; a training/serving version
mismatch prints a warning, and `get_model_dependencies` reports what the model was built with.
`(MLF: https://mlflow.org/docs/latest/ml/model/)`
**UX flow, click by click.**
1. **Deploy & test** (`/:ws/:project/deploy`) — a tester drops one image and gets boxes back from
   whichever model the alias resolves to, without knowing the family. [empty: the tester is disabled
   with "Deploy a model first" until an alias exists] [loading: the button shows "Running…" and the
   result card keeps the previous prediction dimmed] [error: 409 "model is not ready", 402 quota, or
   503 "runtime not available on this server" render as a single line above the result, never a blank
   card]
2. **Any caller** — the same response shape comes back from the hosted endpoint, the playground, a
   batch job and a workflow step, so a client written once keeps working.
**LabelDesk:** PARTIAL — `apps/backend/app/adapters/base.py:85` (`Resolved.predict(im, **kw)` applies
the model's own threshold and the TensorRT→PyTorch fallback), `apps/backend/app/adapters/catalog.py`
(`resolve(ref, db, workspace_id=…)` binds any `trained:<id>` or `<family>:<variant>` to its adapter),
used by `apps/backend/app/routers/training.py:354`, `:642`, `apps/backend/app/routers/playground.py:38`.
The interface is universal *inside* the product; it takes a PIL image and returns our dict, so an
outside artefact cannot be loaded through it.
**Priority:** Must · **Size:** M
**Decision:** `Integrate (mlflow-skinny, optional extra)` — a portable loader for a third-party
artefact is the `pyfunc` contract (flavour dispatch, `_load_pyfunc`, code paths); rebuilding it is
thousands of lines for one call site.
**Roboflow overlap:** `5-F5.31` → T-288, `6-F6.37` → T-342 (load a model from Python) — T-342 is the
client SDK against our API, not an artefact loader.
**Sources:** https://mlflow.org/docs/latest/ml/model/, https://mlflow.org/docs/latest/api_reference/python_api/mlflow.deployments.html

## 3.3 A model you write yourself

**What it does.** A `PythonModel` subclass implements `predict(self, model_input, params=None)` (the
`context` argument is optional since 2.20) and optionally `load_context(context)`, which receives a
`PythonModelContext` holding artifacts. A bare callable also works, and `set_model()` in a standalone
script logs a "model from code" without pickle. MLflow runs that file once at log time to prove it
imports. `(MLF: https://mlflow.org/docs/latest/ml/model/python_model/)` `(MLF: https://mlflow.org/docs/latest/ml/model/models-from-code/)`
**UX flow, click by click.**
1. **Workflow builder** (`/:ws/:project/workflows`) — the user composes preprocess → model → postprocess
   steps instead of writing Python; each step declares the fields it needs.
2. **Test a draft** — a still, clip or camera runs through the chain and the per-step output is shown.
   [empty: no steps yet → "Add a block to start"] [loading: per-step progress] [error: the failing
   step is named with its message]
3. **Upload code** — absent by design; there is no surface that accepts a Python file, and the API
   refuses to execute one.
**LabelDesk:** PARTIAL — the code-free equivalent exists as `apps/backend/app/services/workflow_runner.py:185`
(validates each step's output against the shared prediction schema) behind flag `task_31`
(`apps/backend/app/services/flags.py:30`); no user-supplied code path exists anywhere.
**Priority:** Could · **Size:** L
**Decision:** `Build (our store/UI)` — executing customer Python inside the API process is a
remote-code-execution surface for a multi-tenant service; MLflow's own answer to that is
`MLFLOW_ALLOW_MODEL_CODE_EXECUTION=false` in 3.18.0, i.e. refuse the code, which is what we do.
**Roboflow overlap:** `6-F6.21`–`6-F6.30` → T-320…T-332 (workflow builder) is the sanctioned answer.
**Sources:** https://mlflow.org/docs/latest/ml/model/python_model/, https://mlflow.org/docs/latest/ml/model/models-from-code/, https://github.com/mlflow/mlflow/releases (v3.18.0)

## 3.4 A declared input and output contract, enforced

**What it does.** A signature records the input schema (column names/types, or tensor shape/dtype), the
output schema and the extra inference parameters, so a mismatched request is rejected before it reaches
the model; an input example is turned into a signature automatically and a serving payload example is
derived from it. JSON carries no types, so MLflow casts to the schema and recommends one for
type-sensitive deep models. `(MLF: https://mlflow.org/docs/latest/ml/model/signatures/)`
**UX flow, click by click.**
1. **Model detail** — a "Contract" block lists the input fields with types, the output fields, and the
   runtime parameters (`confidence`, `overlap`, `prompt`) with their defaults and ranges. [empty: a
   model with no recorded contract shows "Contract not recorded — predictions are accepted as sent"]
   [loading: skeleton lines] [error: "Contract unavailable" plus a retry]
2. **Deploy & test** — the tester renders one field per declared input instead of a raw file picker
   once a contract exists; an unknown field is refused with the field name.
3. **Hosted predict** — a request that breaks the contract returns 422 naming the field, before any
   credit is charged.
**LabelDesk:** PARTIAL — the *output* contract is enforced (`apps/backend/app/adapters/base.py:107`
`validate_prediction`, called at `apps/backend/app/routers/playground.py:58` and
`apps/backend/app/services/workflow_runner.py:185`), and the request parameters are fixed in the route
signature (`apps/backend/app/routers/training.py:664`). There is no stored input/output schema on the
model: `TrainedModel` carries `classes` and `task` only (`apps/backend/app/models/training.py:43`,
`:47`) and nothing validates the incoming image payload's declared shape.
**Priority:** Must · **Size:** M
**Decision:** `Build (our schema, their field names)` — enforcement has to run in our request path
before the credit charge and inside our workspace scope, and the vocabulary is a handful of type names,
so the check is ours; the library is only needed to *read* a foreign schema, which is row 3.6's card.
**Roboflow overlap:** `6-F6.10` → T-315, T-316 (a workflow declares its inputs) — that is the workflow
contract; a *model* artefact contract is not covered by it. Inside our own backlog the read-only
declaration is T-926 (`ML2-T2.7`, area 2), which ships no validator; this row is the enforcement on top
of it, so it must reuse T-926's `param_specs()` rather than a second range table.
**Sources:** https://mlflow.org/docs/latest/ml/model/signatures/, https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/

## 3.5 The environment travels with the model

**What it does.** Logging a model writes `conda.yaml`, `python_env.yaml` and `requirements.txt` beside
it, so the training environment can be recreated with conda or virtualenv; extras and custom code can
be declared, and `MLFLOW_LOCK_MODEL_DEPENDENCIES` (or a `uv.lock`, uv ≥ 0.6.10) pins exact transitive
versions. `(MLF: https://mlflow.org/docs/latest/ml/model/dependencies/)`
**UX flow, click by click.**
1. **Model detail** — a "Built with" block lists the runtime versions the model was trained under
   (framework, CUDA, Python) and offers "Download environment" (a `requirements.txt`-shaped file).
   [empty: an imported model shows "Environment not recorded"] [loading: skeleton] [error: "Environment
   could not be read" plus retry]
2. **Container export** — the generated Dockerfile installs from that file, so the image and the
   recorded environment cannot drift.
**LabelDesk:** MISSING — dependencies are deployment-global, not per model:
`apps/backend/requirements.txt:23-32` holds the optional families as comments, and `TrainedModel` has
no environment field (`apps/backend/app/models/training.py:34`), only `runtime_refs` (`:52`), which the
worker fills with runtime detail but is never rendered as an environment.
**Priority:** Should · **Size:** M
**Decision:** `Build (our store)` — our families are six known runtimes, so capture is six
`importlib.metadata` lookups written at training time, not MLflow's import scanner.
**Roboflow overlap:** none.
**Sources:** https://mlflow.org/docs/latest/ml/model/dependencies/, https://github.com/mlflow/mlflow/releases (v3.11.1)

## 3.6 Save, load, and the metadata document

**What it does.** `Model.save(path)` / `Model.load(uri)` write and read the `MLmodel` YAML, which holds
`time_created`, `run_id`, `signature`, `input_example`, `mlflow_version` and the flavour map; metadata
files are copied into a `metadata/` subdirectory, and `environment_variables.txt` records the *names*
(never values) of inference-time secrets. `load_model` does not install or check dependencies.
`(MLF: https://mlflow.org/docs/latest/ml/model/)`
**UX flow, click by click.**
1. **Model detail → Download artefact** — one zip with the weights, a `model.json` describing family,
   variant, task, classes, contract, environment and licence, and a README. [empty: a model that is
   still training has the action disabled with "Available when training finishes"] [loading: the button
   shows a percentage while the zip is built] [error: 409 "the weights file is missing on disk" with the
   path the operator must restore]
2. **Upload artefact** — the same zip dropped back in is validated (format, magic, metadata) before a
   single byte is stored, and the resulting model row is what every screen already reads.
3. **Nothing in the zip is a URL to us** — the artefact runs on the customer's machine.
**LabelDesk:** PARTIAL — exports already carry a machine-readable spec (`apps/backend/app/services/exporters.py:67`
writes the YOLO `data.yaml` with class names), edge exports are zipped per preset
(`apps/backend/app/services/edge.py:114`), and weights are downloadable
(`apps/frontend/src/features/project/Models.tsx:235`). There is no metadata document, no licence or
environment in the artefact, and no import of an artefact (weights import is a separate, unbuilt row —
`5-F5.31` → T-288).
**Priority:** Must · **Size:** M
**Decision:** `Integrate + Build` — write/read the document and load it with `mlflow-skinny` (so a
third-party MLflow artefact is readable), while the file layout, the route and the UI stay ours.
**Roboflow overlap:** `5-F5.32` → T-291 (dataset bundle and the way back), `5-F5.31` → T-288 (weights
upload), `6-F6.37` → T-342 (load a model from Python) — none of them ships a metadata document.
**Sources:** https://mlflow.org/docs/latest/ml/model/, https://mlflow.org/docs/latest/ml/community-model-flavors/

## 3.7 Build a container that serves this model

**What it does.** `mlflow models build-docker -m <uri> -n <name>` builds an image whose entrypoint
serves the model on port 8080 behind nginx (`DISABLE_NGINX=true` removes it, `MLFLOW_MODELS_WORKERS`
sets the uvicorn worker count, CPU count by default); `--env-manager` picks local/virtualenv/uv/conda,
`--install-mlflow` pins the same MLflow version into the activated environment, and
`generate-dockerfile` writes the equivalent Dockerfile for review. `(MLF: https://mlflow.org/docs/latest/cli.html)`
**UX flow, click by click.**
1. **Model detail → Container** — the user picks a target (CPU / CUDA / Jetson) and clicks "Build
   container files". [empty: models whose family has no generated container show the reason and the
   supported targets] [loading: "Preparing…" then the file list appears when done] [error: "This model
   cannot be containerised: <reason>" — the reason names the missing export]
2. **Download** — a zip with `Dockerfile`, `serve.sh`, the artefact and a README whose first command is
   `docker build -t <name> . && docker run -p 8080:8080 <name>`.
3. **Verify** — the README quotes the health path and one `curl` with a real payload taken from the
   model's own input example, so the command works on the first try.
**LabelDesk:** MISSING — no Dockerfile is generated anywhere; `apps/backend/app/services/edge.py:114`
plans Ultralytics export formats only and `apps/frontend/src/features/project/EdgeExport.tsx` downloads
model files, not a runnable service.
**Priority:** Should · **Size:** M
**Decision:** `Build (our artefact, our image)` — a 20-line Dockerfile over our own export is smaller
than making a customer image depend on the `python_function` server, and our runtime is
ultralytics/ONNX, not sklearn.
**Roboflow overlap:** `6-F6.5` → T-312, `6-F6.45` → T-312 (self-hosted server + install paths) — T-312
is the platform's own server; this row is one model's image.
**Sources:** https://mlflow.org/docs/latest/cli.html, https://mlflow.org/docs/latest/ml/deployment/, https://mlflow.org/docs/latest/ml/docker/

## 3.8 A local server with a contract you can probe

**What it does.** `mlflow models serve -m <uri> -p 5000 -h 127.0.0.1 -w 1 -t 60` starts a FastAPI
scoring server with four endpoints: `POST /invocations`, `GET /ping`, `GET /health` (same as `/ping`)
and `GET /version`; input is CSV or JSON in `dataframe_split`, `dataframe_records`, `instances` or
`inputs` form, plus an optional `params` object allowed only when the signature declares parameters.
`(MLF: https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/)`
**UX flow, click by click.**
1. **Deploy & test** — the endpoint card shows the model endpoint, a status pill (Ready / Degraded /
   Warm-up) and the version string. [empty: no alias → the card reads "Nothing deployed" with a link to
   Models] [loading: the pill pulses "Checking…"] [error: the probe fails → "Endpoint did not answer —
   the deployed model may have been deleted" with the reason and a retry]
2. **Health check** — a "Check now" button calls the probe and shows the round trip in ms.
3. **Callers** — `GET <endpoint>/health` and a version header answer 200 for a monitor without an API
   key that can read data.
**LabelDesk:** PARTIAL — prediction is served (`apps/backend/app/routers/training.py:662`
`POST /api/v1/models/{model_id}/predict`, alias-aware via `_hosted_model` at `:592`) and each request is
metered and audited (`:635`–`:649`). There is no health/version probe on the model endpoint and no
JSON-list input form — the body is multipart/URL only (`:664`–`:666`).
**Priority:** Must · **Size:** S
**Decision:** `Build (our route)` — one probe on our own endpoint; standing up MLflow's scoring server
would add a second auth boundary in front of customer data.
**Roboflow overlap:** `6-F6.2` → T-317 (cold start), `6-F6.8` → T-313, T-314 (endpoint card and
deploy-and-test), `6-F6.12` → T-318 (error codes) — health/version is absent from all of them.
**Sources:** https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/, https://mlflow.org/docs/latest/cli.html, https://mlflow.org/docs/latest/genai/serving/

## 3.9 Batch inference as a repeatable job

**What it does.** `mlflow models predict -m <uri> -i input.csv -o output.csv -t csv|json` scores a file
in one shot, and the same job can run against a Spark cluster or a served endpoint; output is written
as a file or to stdout. `(MLF: https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/)`
`(MLF: https://mlflow.org/docs/latest/cli.html)`
**UX flow, click by click.**
1. **Batch** (`/:ws/:project/batch`) — pick a source (batch, video, connector), a model, an output
   format, then Run. [empty: "No batch runs yet."] [loading: a row appears immediately in queued with
   progress] [error: 400 for a format the model cannot produce, 402 for quota, and the error text on the
   run row]
2. **Result** — the finished run links the result file; a failed run keeps the message.
**LabelDesk:** PARTIAL — `apps/backend/app/routers/batch_inference.py:46` queues a `batch_infer` job with
source/limit/output validation (`:50`–`:80`), a listing route (`:107`) and a signed result URL (`:24`);
a job is a row in `Job` (`apps/backend/app/models/training.py:9`). Missing parts: the `workflow` source
returns 501 (`:51`) and the input is always stored images — there is no file upload with a content type.
**Priority:** Should · **Size:** M
**Decision:** `Build (our job queue)` — the queue, metering and signed results already exist; adding
JSON/parquet input is a field, not a library.
**Roboflow overlap:** `6-F6.4` → T-354, T-355 already deliver the batch screen and the result set; this
row's remaining formats are inside T-354's scope, so no card here.
**Sources:** https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/, https://mlflow.org/docs/latest/cli.html

## 3.10 A documented way to add a family

**What it does.** Deployment targets and model flavours are plugins: a Python package declares an
entry point (`deployment` group, e.g. `my-target=my_plugin.deployment`) and MLflow discovers it, so a
company can add a target without forking. Community flavours follow the same interface
`save_model`/`log_model`/`load_model`. `(MLF: https://mlflow.org/docs/latest/ml/plugins/)`
`(MLF: https://mlflow.org/docs/latest/ml/community-model-flavors/)`
**UX flow, click by click.**
1. **Settings → Model runtimes** — the installed families are listed with their version and state, and
   an operator sees "Dropped-in family <name> is not loadable: <reason>" instead of a silent absence.
   [empty: "Only the built-in families are installed."] [loading: skeleton rows] [error: a family that
   raises on import is listed as failed with its message, and the rest of the page still renders]
2. **Model detail** — a model whose family is no longer installed shows "Runtime <family> is not
   installed on this server" with the export alternative, instead of failing at predict time.
**LabelDesk:** MISSING — families are registered by importing a module
(`apps/backend/app/adapters/__init__.py:2`), so adding one means editing that file and redeploying;
`ADAPTERS` is a plain dict (`apps/backend/app/adapters/base.py:43`) with no entry-point discovery and no
listing surface.
**Priority:** Could · **Size:** S
**Decision:** `Build (our registry)` — one `importlib.metadata.entry_points(group="labeldesk.adapters")`
loop; the MLflow plugin system buys us nothing at six families.
**Roboflow overlap:** none.
**Sources:** https://mlflow.org/docs/latest/ml/plugins/, https://mlflow.org/docs/latest/ml/community-model-flavors/

## 3.11 A deployment is a resource with a state

**What it does.** `create_deployment(name, model_uri, flavor, config)` blocks until inference is
possible and raises on a name conflict; `get_deployment(name)` returns a target-specific dict,
`list_deployments` an array, `update_deployment` a redeploy, `delete_deployment` is idempotent. There is
no standard status field — progress and failure are target-specific, and the registry side carries a
`deployment_job_state` for hosted targets only. `(MLF: https://mlflow.org/docs/latest/ml/deployment/)`
`(MLF: https://mlflow.org/docs/latest/api_reference/python_api/mlflow.deployments.html)`
**UX flow, click by click.**
1. **Deploy & test** — each alias row shows Who / When / From which model, a Ready·Warm-up·Failed pill,
   and the last probe result. [empty: "Nothing deployed — pick a model to go live"] [loading: the row
   shows "Checking…" and keeps the last known state] [error: a failed switch keeps the previous model
   live and says so: "Switch failed — production still serves <model>"]
2. **History** — the event list names the actor, the model and the action, and shows when a rollback
   happened.
**LabelDesk:** PARTIAL — switches and rollbacks are recorded
(`apps/backend/app/services/deployments.py:43`, `:84`, events rendered by `:174`) and exposed at
`apps/backend/app/routers/deployments.py:30`, `:40`; `DeploymentEvent` stores action, user and models
(`apps/backend/app/models/training.py:91`). Missing: any readiness/health state per alias — a switch is
recorded as done the moment the pointer moves, and nothing ever checks that the new model can actually
answer.
**Priority:** Should · **Size:** S
**Decision:** `Build (our store)` — we already have the event table and the Job machinery; a health
outcome is one column plus one probe.
**Roboflow overlap:** `6-F6.11` → T-006 (immutable identity + production pointer, guard). That guard
asserts the pointer, not the health of what it points at.
**Sources:** https://mlflow.org/docs/latest/api_reference/python_api/mlflow.deployments.html, https://mlflow.org/docs/latest/ml/deployment/, https://github.com/mlflow/mlflow/releases (v3.17.0)

## 3.12 Ship to someone else's machine

**What it does.** A model URI plus target-specific config deploys to a managed endpoint: SageMaker
builds the image, pushes to ECR, uploads the artefact to S3 and creates the endpoint with
`--region-name`, `--instance-type`, `--instance-count` and an execution role; Modal does the same
through `mlflow-modal-deploy` with a GPU class; Azure goes through `azureml-mlflow`. Community plugins
cover Ray Serve, TorchServe, RedisAI and OCI. `(MLF: https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-sagemaker/)`
`(MLF: https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-modal/)`
**UX flow, click by click.**
1. **Deploy & test → Add a target** — the user pastes the URL of an inference service they run
   elsewhere, picks an auth header, and saves. [empty: "No external targets yet."] [loading: "Verifying
   the target…" then the probe result] [error: "The target did not answer: <status>" and the target is
   saved as Unverified, never silently active]
2. **Verify** — one probe from our worker, with the stored secret, records the outcome as a
   `DeploymentEvent`.
3. **Route traffic** — the alias row says which target it resolves to, and the endpoint card shows the
   external host instead of ours.
**LabelDesk:** MISSING — every prediction runs in-process through an adapter
(`apps/backend/app/adapters/catalog.py`); the alias table has no target concept
(`apps/backend/app/models/training.py:77`) and no cloud SDK is installed
(`apps/backend/requirements.txt:1-22`).
**Priority:** Could · **Size:** L
**Decision:** `Build (one generic target)` — three cloud SDKs and their credentials are a maintenance
liability; a registered external endpoint with a stored secret covers "runs on our hardware" without
inventing a billing relationship.
**Roboflow overlap:** `6-F6.5` → T-312, `6-F6.45` → T-312 (self-host).
**Sources:** https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-sagemaker/, https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-modal/, https://mlflow.org/docs/latest/ml/plugins/

## 3.13 Size, storage and what you actually ship

**What it does.** Large models are logged by path so the weights never enter memory, a
HuggingFace-backed model can be logged as a reference (repo + commit) instead of a copy — saving
roughly 150 GB for a fine-tune — and ONNX defaults to `save_as_external_data=True` precisely so files
over 2 GB work, at the cost of a multi-file artefact. Pickle-free formats (`torch.export`, `skops`) are
the safer default because loading cannot execute arbitrary code. `(MLF: https://mlflow.org/docs/latest/ml/deep-learning/transformers/large-models/)`
`(MLF: https://mlflow.org/docs/latest/ml/model/)`
**UX flow, click by click.**
1. **Model detail** — a "Size" block shows the weights size, the size of each built export and the
   project total, with a warning row once a single artefact crosses 2 GB. [empty: "Size not measured
   yet" while the job runs] [loading: skeleton] [error: "Size unavailable — the weights file is missing"
   with the path]
2. **Export** — a format that would produce a multi-file artefact says so before the build, and the zip
   lists every part.
3. **Delete** — the confirmation names what will be freed.
**LabelDesk:** MISSING — nothing measures or shows artefact size; `TrainedModel.weights` is a path
(`apps/backend/app/models/training.py:48`) and the detail screen shows metrics, classes and licence only
(`apps/frontend/src/features/project/Models.tsx:231`).
**Priority:** Should · **Size:** S
**Decision:** `Build (our files)` — one `os.stat` per artefact; the library has nothing to add.
**Roboflow overlap:** `5-F5.31` → T-288, T-289 (upload with format/magic) — size is not in their scope.
**Sources:** https://mlflow.org/docs/latest/ml/deep-learning/transformers/large-models/, https://mlflow.org/docs/latest/ml/model/, https://mlflow.org/docs/latest/ml/tracking/pickle-free-models/

## 3.14 Vision-language models served like any other

**What it does.** LLM and agent packaging is a flavour too: LangChain, LlamaIndex, ChatModel and plain
`PythonModel` all log into the same artefact and serve with the same command, including
OpenAI-compatible chat bodies and `predict_stream` for token streams; the OpenAI logging flavour is
deprecated in favour of the prompt registry. `(MLF: https://mlflow.org/docs/latest/genai/flavors/)`
`(MLF: https://mlflow.org/docs/latest/genai/serving/)`
**UX flow, click by click.**
1. **Model detail** — a VLM model's contract includes a free-text `prompt` field with the default
   grounding sentence, and a "Try it" panel takes a sentence plus an image. [empty: no prompt typed →
   the default from the training config is shown as placeholder] [loading: "Thinking…"] [error: the
   adapter's message verbatim, e.g. the VLM endpoint URL is unreachable]
2. **Hosted predict** — `prompt` is an accepted query parameter for a `vlm`-family model and a 422
   names it as unsupported for any other family, rather than being silently ignored.
**LabelDesk:** PARTIAL — the VLM family exists and takes a prompt
(`apps/backend/app/adapters/base.py:35` `predict(..., prompt=...)`, adapter
`apps/backend/app/adapters/vlm_ad.py`), gated on an operator-provisioned endpoint
(`apps/backend/app/services/capabilities.py:21`), and the playground passes a prompt
(`apps/backend/app/routers/playground.py:76`). The public predict route does not accept `prompt`
(`apps/backend/app/routers/training.py:664`), so a served VLM can only answer its default question.
**Priority:** Could · **Size:** S
**Decision:** `Build (our adapter)` — the model already runs; the gap is one parameter and its 422.
**Roboflow overlap:** none (Roboflow's VLM surface is area 6's workflow grounding).
**Sources:** https://mlflow.org/docs/latest/genai/flavors/, https://mlflow.org/docs/latest/genai/serving/

## 3.15 Serving an immutable version, and what may change under it

**What it does.** A registered model has versions; `models:/<name>/<version>` is an immutable handle
while `models:/<name>@alias` is a mutable pointer you reassign to move production traffic. Serving by
version is therefore reproducible; serving by alias is a deliberate, auditable switch.
`(MLF: https://mlflow.org/docs/latest/ml/model-registry/)`
**UX flow, click by click.**
1. **Deploy & test** — the endpoint card names the exact model it serves (name + trained date), not just
   the alias. [empty: nothing deployed] [loading: the name shows a skeleton until the model loads]
   [error: "The deployed model no longer exists" when the pointer was emptied, with a link to switch]
2. **Delete a model** — the deletion is recorded per alias, and the deployment history shows who deleted
   the model that production was serving, so a caller can see why the alias is empty.
**LabelDesk:** PARTIAL — a model id is an immutable handle and the alias is a pointer with a rollback
target (`apps/backend/app/models/training.py:83`, `:85`), rendered by
`apps/backend/app/services/deployments.py:157`; deleting a model is unguarded
(`apps/backend/app/routers/training.py:314`) and the alias foreign key is `ondelete="SET NULL"`
(`apps/backend/app/models/training.py:84`), so a live alias silently loses its model and the endpoint
starts answering 404 "alias is not deployed" (`:619`) with nothing in the deployment history to explain
it.
**Priority:** Must · **Size:** S
**Decision:** `Build (our guard)` — one tombstone and one event; nothing to integrate.
**Roboflow overlap:** `6-F6.11` → T-006 (guard) and `5-F5.33` → T-268 plan the pointer; the delete path
itself is T-920 (`ML2-T2.2`, area 2, with `5-F5.37` → T-267 for the typed confirm), which tombstones the
row and writes a `deleted` event per alias before clearing it. That card is the fix; this row must not
open a second one on `delete_model`.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/, https://mlflow.org/docs/latest/cli.html

## Judgment calls

- **3.2 and 3.6 are the only rows that integrate, and they share one card (T-933).** MLflow's server,
  serve command, docker build and deployment plugins all rebuild as storage/serving/UI, which the brief
  says we own. The library earns its place only on the *reader* side of a portable artefact: flavour
  dispatch, `_load_pyfunc` and code paths are thousands of lines to reproduce, and a customer who
  arrives with an MLflow model directory must be able to get in. It still ships as an optional extra
  that degrades with a named reason, like `transformers` in `apps/backend/requirements.txt:25`.
- **3.4 is Build even though it is a schema, and it is not a second contract feature.** The read-only
  declaration is already planned as T-926 (`ML2-T2.7`, area 2) with no validator by design; the
  enforcement — 422 before the credit charge — is the only part left, it must read T-926's
  `param_specs()`, and the panel already exists. One card, no new table.
- **3.15 hands the fix to area 2.** MLflow does not refuse a delete behind an alias either; it leaves a
  dangling handle. T-920 tombstones the row and records a `deleted` event per alias, which is the audit
  trail plus the serving consequence. A card here would fight T-920 over `delete_model`.
- **3.3 is PARTIAL, not MISSING.** A user can express a custom model as a workflow chain with no code;
  MLflow's own 3.18 answer to untrusted code is to refuse it, so refusing is parity, not a gap, and the
  remaining work belongs to the workflow cards in area 6.
- **3.9 gets no card.** `6-F6.4` → T-354/T-355 already plan the batch screen, source and result set;
  the content-type field is inside that card's scope. Duplicating it would put two agents in
  `routers/batch_inference.py`.
- **`--enable-mlserver` is gone.** MLflow 3.13.0 removed it, so no row or card may offer it; the built-in
  scoring server is the only backend.
- **0 HAVE rows is deliberate.** Every mechanism in this area — artefact, signature, environment,
  container, plugin contract — is genuinely absent; what exists is a strong in-product serving path
  (3.8) that this area extends rather than replaces.
