# MLflow parity — Area 2: Model Registry

Baseline `feat/labeldesk-v2` @ `f6feb09`. MLflow docs read 2026-11-17. Release notes window
2025-11-17 → 2026-11-17 checked at https://github.com/mlflow/mlflow/releases (v3.7.0 … v3.18.0).

**Doc pages covered (full navigation walk).**
Registry section:
- https://mlflow.org/docs/latest/model-registry.html — 301 shell, redirects to the page below (fetched, kept for completeness)
- https://mlflow.org/docs/latest/ml/model-registry/
- https://mlflow.org/docs/latest/ml/model-registry/tutorial/
- https://mlflow.org/docs/latest/ml/model-registry/workflow/
Model pages the registry leans on:
- https://mlflow.org/docs/latest/ml/model/signatures/
- https://mlflow.org/docs/latest/ml/model/ — no row: it is the flavour/`MLmodel` packaging format, owned by area 3
Self-hosting pages the registry leans on:
- https://mlflow.org/docs/latest/self-hosting/webhooks/
- https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/
- https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/ — no row: login and the auth app only; per-model grants live in the RBAC page
- https://mlflow.org/docs/latest/self-hosting/workspaces/
- https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/ — no row: "the registry needs a database-backed store"; LabelDesk is already SQLAlchemy (`app/db.py`), so there is nothing to copy
Release notes (feature-level only, fixes not rowed):
- https://github.com/mlflow/mlflow/releases/tag/v3.13.0 — RBAC roles + workspace-scoped grants
- https://github.com/mlflow/mlflow/releases/tag/v3.17.0 — sub-resource tiers (incl. `registered_model_version`), source logged-model link on the version page, stale aliases removed on version delete, `@latest` fix
- https://github.com/mlflow/mlflow/releases/tag/v3.18.0 — registry name spelling and `*` name rejection under auth
- https://github.com/mlflow/mlflow/releases/tag/v3.10.0 — model-version search filtered by permission
- https://github.com/mlflow/mlflow/releases/tag/v3.9.0 — registration with KMS auth from another workspace
- https://github.com/mlflow/mlflow/releases/tag/v3.12.0 — cross-workspace `copy_model_version` fix

## Area count
15 rows: 1 HAVE · 7 PARTIAL · 6 MISSING · 1 UNVERIFIED.

## 2.1 A registered model is a named container, not a training run
**What it does.** A registered model is a named container with its own unique name that holds versions, aliases, tags and metadata; the registry page lists those names and each one opens its version table. Registering the same name again adds a version instead of a new model. Models are found from the registry page or from a run's artifact folder, and the list is searchable by name and filter string. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/)`
**UX flow, click by click.**
1. **Project → Models** (`/:ws/p/:project/models`) — the left rail becomes a list of model names, not runs: each entry shows `ppe-detection`, `3 versions`, the best held-out score and a *production* chip when an alias points at one of its versions. [empty: "No models yet — train a version to register the first one."] [loading: four name skeletons] [error: "Models could not be loaded" + Retry]
2. **Search the registry** — one box above the rail filters by name and by tag (`q=`, `tag=`), keeping the selected model when it still matches. [empty: "No model matches “ppe”." + Clear] [loading: the rail dims, the last result stays visible]
3. **Open a model** — the right pane lists its versions newest first with version number, dataset version, arch, score and aliases; selecting a version reuses today's detail pane. [empty: a model with zero versions shows "This model has no versions — register one from a finished run."]
4. **Register from a run** — the run's row menu gains *Register as model…*; the dialog offers a new name or an existing one, and states that an existing name adds a version. [error: a duplicate new name shows "That name is taken in this project."] [loading: the button reads "Registering…" and the dialog stays open]
**LabelDesk:** MISSING — `TrainedModel` is one row per training run with no grouping name (`apps/backend/app/models/training.py:34-53`); `apps/frontend/src/features/project/Models.tsx:216-224` renders every run as a flat rail button; there is no search parameter on the list route (`apps/backend/app/routers/training.py:146-165`); the workspace "registry" is the adapter zoo plus ready trained models, not a named registry (`apps/backend/app/routers/registry.py:13-15`, `apps/backend/app/adapters/catalog.py:58-77`).
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — the container is a name and a counter on rows we already own; no library reproduces tenancy or a screen.
**Roboflow overlap:** `5-F5.3` → `T-257` — that card delivers a workspace list with a star and a share flag; it has no name grouping, version table or search. This row is the grouping on top, not a second registry screen.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://mlflow.org/docs/latest/model-registry.html

## 2.2 A model version is immutable and numbered per model
**What it does.** Adding a model under an existing name creates the next version number, and the version is immutable — its artifacts, source and metadata do not change. Versions are addressed as `models:/<name>/<number>`; deleting a version is irrevocable and leaves the numbering alone, and a version delete also drops the aliases that pointed at it. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://github.com/mlflow/mlflow/releases/tag/v3.17.0)`
**UX flow, click by click.**
1. **Model version list** — each row starts with `v1`, `v2`… assigned at registration, never renumbered, gaps kept after a delete; the number is copyable as `ppe-detection/2`. [empty: the model's first version is "v1"] [error: two simultaneous registrations resolve to consecutive numbers, never the same one]
2. **Version detail** — the pane shows *trained on dataset v3*, arch, family/variant, classes, licence, creation time and the source run link, all read-only. [loading: header renders from the list row, then fills]
3. **Delete a version** — the row menu offers *Delete version*; the confirm names every alias that currently points at it ("production would stop serving"). [error: a version still referenced by an external caller is not blockable, so the confirm is the only guard]
**LabelDesk:** MISSING — the model row's `version_id` is the *dataset* version (`apps/backend/app/models/training.py:39`) and the UI prints it as "trained on v3" (`apps/backend/app/routers/training.py:159`, `apps/frontend/src/features/project/Models.tsx:231`); there is no per-model counter, no immutability statement and no version-level delete distinct from deleting the run row (`apps/backend/app/routers/training.py:314-324`).
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — one integer and one assignment rule at registration time.
**Roboflow overlap:** `5-F5.33` → `T-268` gives one stable reference per run; it does not give a per-name sequence or version-level deletion.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## 2.3 Aliases: several mutable pointers, resolved at call time
**What it does.** An alias is a named, mutable pointer to one version; several aliases may point at the same version, a version may carry several, and reassigning an alias changes what `models:/name@alias` loads without touching the caller's code. `@latest` resolves to the highest version. Aliases carry no access control of their own. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://mlflow.org/docs/latest/ml/model-registry/)`
**UX flow, click by click.**
1. **Version row → aliases cell** — the cell lists chips (`production`, `champion`, `field-trial`) with an *Add* link and a pencil. Adding offers the existing alias names and a free-text new one; the same alias moved from another version asks "Move `champion` from v2 to v3?" first. [empty: the cell reads "no aliases"] [loading: the chip shows a spinner while the call is in flight] [error: moving an alias out of *production* states that the endpoint changes immediately]
2. **Model header** — every alias on the selected version is a chip that copies its model reference on click. [error: copy failure falls back to selecting the text]
3. **Deploy & Test** — the model picker groups by alias first ("production — ppe-detection v3") and the snippet header names the alias, not the id. [empty: no alias yet ⇒ the picker stays on plain model names]
4. **Caller view** — `GET /api/v1/models/<name>@champion/predict` resolves the pointer at request time, so a repoint needs no redeploy; an unknown alias is a 404 naming the model.
**LabelDesk:** PARTIAL — `DeploymentAlias(alias, model_id, previous_model_id)` exists with rollback and an append-only `DeploymentEvent` (`apps/backend/app/models/training.py:77-101`), but the alias set is the fixed pair `production`/`staging` (`apps/backend/app/services/deployments.py:20-24`), one model per alias per project, moved only by an admin (`apps/backend/app/routers/deployments.py:30-48`); there is no user-defined alias name, no second alias on one version, no alias chip on the model row and no `@latest`.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — extend `DeploymentAlias` to free-form names; do not add a second pointer table.
**Roboflow overlap:** `5-F5.34` → `T-268` (per-version legacy alias) and `5-F5.35` → guard `T-005` (production pointer). Those stay; this row is user-defined alias names only.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/tutorial/

## 2.4 Tags on models and versions
**What it does.** Tags are free key-value pairs on a registered model and on each version, set and deleted independently, shown as `key:value` in the UI, and usable to sort and filter the registry (e.g. `validation_status:approved`). `(MLF: https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/)`
**UX flow, click by click.**
1. **Model header → tags** — chips under the name; *Edit tags* opens a two-column editor (key, value) that saves on blur. [empty: "No tags — add one to mark the validation state."] [loading: the editor is disabled while saving one row] [error: an empty key or a duplicate key names the offending row]
2. **Version row → tags** — the same editor per version, and the tag cell shows the first two chips plus `+2`.
3. **Filter** — a tag chip in the rail filter (`tag=validation_status:approved`) narrows the list; a tag that matches nothing shows the no-match state with Clear. [error: an unknown key is an allowed zero-result filter, not a 422]
4. **Export/predict callers** — tags appear in the model payload; they never change inference.
**LabelDesk:** MISSING — `TrainedModel` has classification columns `family`, `variant`, `license` and nothing free-form (`apps/backend/app/models/training.py:34-53`, `apps/backend/app/schema/training.py:3-5`); no tag route exists on the model router (`apps/backend/app/routers/training.py:146-192`).
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — a JSON column on the row we already load.
**Roboflow overlap:** none — the licence badge (`5-F5.38` → `T-005`) is a fixed field, not user metadata.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/

## 2.5 Deprecation, and why there are no stages
**What it does.** Stages (`Staging`, `Production`, `Archived`, `None`) were the original lifecycle labels and are deprecated since 2.9; the documented replacement is aliases for pointers and tags for status, with separate registered models per environment for access control. The migration guide maps each stage use-case onto aliases, tags or a separate model, and archiving is a label, not a delete. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/workflow/ — "Deprecated: Using Model Stages" and "Migrating from Stages")`
**UX flow, click by click.**
1. **Version row menu** — *Deprecate version…* asks for one optional reason and stores `deprecated` plus the reason and the actor; the row gains a muted *Deprecated* chip and stays selectable and downloadable. [empty: nothing deprecated ⇒ no chip and no filter] [loading: the row dims until the write returns] [error: a failed write keeps the row unchanged and names the reason]
2. **Default surfaces skip deprecated versions** — the Deploy picker and the Compare picker leave them out of the default selection but list them under "Show deprecated". [empty: everything deprecated ⇒ Deploy says "No current model — 2 versions are deprecated."]
3. **Reinstate** — *Reinstate version* clears the flag and appends an alias-free history entry; no stage ever appears in the UI.
**LabelDesk:** PARTIAL — the only state is the training lifecycle `queued|training|ready|failed` (`apps/backend/app/models/training.py:44`), with no deprecated/archived state; the only removal is a hard delete (`apps/backend/app/routers/training.py:314-324`); a production pointer exists as an alias (`apps/backend/app/services/deployments.py:43-81`).
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — one boolean and a reason; deliberately do not build stages, because the alias already covers the pointer and stages are deprecated upstream.
**Roboflow overlap:** `5-F5.35` → guard `T-005`.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://mlflow.org/docs/latest/ml/model-registry/

## 2.6 Lineage: which run, dataset and parameters produced this version
**What it does.** Every registered version points back at the run, logged model or notebook that produced it, and the version page shows the source run and, since 3.17, a link to the source logged model, so a version can be reproduced from its data and parameters. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://github.com/mlflow/mlflow/releases/tag/v3.17.0)`
**UX flow, click by click.**
1. **Version detail → "Produced by"** — a block names the dataset version (`v3 · 1,284 images · 812/236/236`), the training run id with its start time and duration, and the variant that ran. [empty: a model imported outside the queue shows "source run unknown" and no link] [loading: the block renders the fields it has, then fills counts]
2. **Parameters** — a disclosure lists the hyper-parameters the job actually ran with (epochs, image size, batch, patience) as read-only key/value rows. [empty: "This run recorded no parameters."]
3. **Open the chain** — *Show in lineage* navigates to Lineage with this model selected. [error: the graph failing leaves the panel intact and shows an inline "Lineage is unavailable" link]
4. **Data provenance** — *Open dataset version* goes to the frozen version, where the image list and splits already live.
**LabelDesk:** PARTIAL — the model carries `version_id` and `job_id` (`apps/backend/app/models/training.py:39-40`), the detail header prints "trained on v{n}" (`apps/frontend/src/features/project/Models.tsx:231`), and a full batch→version→run→model→stream graph already exists (`apps/backend/app/services/insights_lineage.py:74-264`, `apps/frontend/src/features/lineage/Lineage.tsx:231-256`); what is absent is a per-model panel that states split counts, the frozen dataset version and the recorded hyper-parameters without leaving the model page.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — read existing rows and the job's `params`; no new store.
**Roboflow overlap:** `4-F4.45` → guard `T-004` (per-version analytics), `5-F5.33` → `T-268`.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## 2.7 A signature: input, output and inference-parameter contract
**What it does.** A model signature declares the input schema (column or tensor), the output schema and an optional parameter schema with defaults; it is inferred from an input example or written explicitly, the UI shows the requirements, and managed registries refuse a version without one. Inference parameters such as a threshold belong in the parameter schema, not in prose. `(MLF: https://mlflow.org/docs/latest/ml/model/signatures/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/)`
**UX flow, click by click.**
1. **Version detail → Contract** — three small tables: *Input* (`image` — file or URL, JPEG/PNG, ≤ 20 MB), *Output* (`predictions[]` with `class`, `confidence`, `x`, `y`, `width`, `height`, `points` for segmentation), *Parameters* (`confidence` 0–1 default 0.40, `overlap` 0–1 default 0.50, `tile_size` px default 0). [empty: a model whose task is unknown shows "Contract unavailable for this task" and keeps the call working] [loading: the panel shows the task-derived shape immediately]
2. **Deploy & Test** — the snippets are generated from the contract, so a class name in the response example is never hard-coded to the first class. [error: copying a snippet before a model is picked keeps the button disabled]
3. **Callers** — `GET /api/v1/models/{id}/contract` returns the same JSON the panel renders; an unknown model id is a 404 and another workspace's id is a 404.
**LabelDesk:** MISSING — no signature or schema field exists (`apps/backend/app/models/training.py:34-53`); "signature" in the backend means a cache key or an HMAC (`apps/backend/app/services/insights_common.py:34`, `apps/backend/app/security.py:98`); the response shape lives in prose and a hand-written snippet (`apps/frontend/src/features/project/Deploy.tsx:98-121`) and the accepted parameters in the handler signature (`apps/backend/app/routers/training.py:340-359`).
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a task-derived contract, not a general type system; `mlflow-skinny` would add a schema language we do not need for one input type.
**Roboflow overlap:** none — `6-F6.10` is a workflow's declared inputs, a different callable.
**Sources:** https://mlflow.org/docs/latest/ml/model/signatures/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/

## 2.8 A written description on the model and on each version
**What it does.** The top-level model and every version can carry a description in Markdown — algorithm, dataset, method, caveats — edited from the version page and travelling with the version rather than with the project. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/ — "Annotations and Descriptions" · https://mlflow.org/docs/latest/ml/model-registry/workflow/ — "Adding or Updating an MLflow Model Descriptions")`
**UX flow, click by click.**
1. **Model header → About** — the description renders under the metadata line; *Edit* swaps to a textarea with Save and Cancel and a character count. [empty: "No description yet — say what this model detects and what it should not be used for."] [loading: Save reads "Saving…" and the textarea stays editable] [error: a failed save keeps the draft and shows "Not saved — retry" beside the button]
2. **Version detail** — the version's own description sits above the metrics, with the model-level text as a collapsed fallback ("Inherited from the model").
3. **Read-only roles** — a reader sees the text with no Edit control (permission-dimmed, not hidden silently).
4. **Copy** — the description is offered in the model payload so the Deploy page can show a one-line summary.
**LabelDesk:** MISSING — no `description` or notes column on `TrainedModel` (`apps/backend/app/models/training.py:34-53`), and the header prints only arch, dataset version, date and class count (`apps/frontend/src/features/project/Models.tsx:230-231`).
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — one text column; render paragraphs only, no Markdown dependency (shortcut: no tables or links rendered, upgrade when a customer asks).
**Roboflow overlap:** none.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/ · https://mlflow.org/docs/latest/ml/model-registry/workflow/

## 2.9 A stored input example per version
**What it does.** An input example is stored alongside the model, shown with the signature so a caller sees a valid request, and used at logging time to validate the model and infer the signature. `(MLF: https://mlflow.org/docs/latest/ml/model/signatures/ · https://mlflow.org/docs/latest/ml/model/ — "Additional Logged Files")`
**UX flow, click by click.**
1. **Version detail → Example input** — the evaluation's first correctly detected image is shown as a thumbnail beside a copyable `curl` call for this exact version. [empty: a model with no evaluation shows "No example yet — run a test inference to create one."] [loading: the thumbnail box holds its aspect ratio while the signed URL resolves] [error: a deleted image file shows "Example unavailable" and hides the copy button]
2. **Deploy & Test → Use the example** — one click loads that image into the tester. [error: a missing file states that the example must be regenerated]
3. **Contract panel** (2.7) links to the same example, so the schema and a valid body are one screen.
**LabelDesk:** MISSING — the evaluation keeps per-image detections and signs their URLs (`apps/backend/app/routers/training.py:131-143`) and the Deploy page can upload a local file (`apps/frontend/src/features/project/Deploy.tsx:52-58`), but no example is attached to the model row or shown on the model page.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — derive it from the existing evaluation report; store only a file name plus the produced JSON.
**Roboflow overlap:** none — `5-F5.16` is live training curves.
**Sources:** https://mlflow.org/docs/latest/ml/model/signatures/ · https://mlflow.org/docs/latest/ml/model/

## 2.10 Deleting a version, and what stops serving
**What it does.** Deleting a version or a whole registered model is irrevocable and cascades to its aliases, so an endpoint that resolved `@production` stops loading after the delete; the docs warn explicitly to delete judiciously. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/workflow/ — "Deleting MLflow Models" · https://github.com/mlflow/mlflow/releases/tag/v3.17.0)`
**UX flow, click by click.**
1. **Version row menu → Delete version** — the confirm names the version, its aliases and the consequence: "production would stop serving within one request. Callers get 404 until you point the alias at another version." The name must be typed. [empty: a model with one version says "This is the only version — deleting it removes the model."]
2. **Model header → Delete model** — same typed confirm, listing every version and alias that goes with it.
3. **After the delete** — the alias chip disappears with the row, the deployment history keeps a `deleted` event naming who and when, and the Deploy page shows "production has no model" rather than a stale name. [error: an in-flight prediction keeps its already-loaded weights and is not interrupted]
**LabelDesk:** PARTIAL — `delete_model` is a hard delete behind `admin`, erases files and 409s when files cannot go (`apps/backend/app/routers/training.py:314-324`); the confirm is a browser `confirm('Delete this model?')` (`apps/frontend/src/features/project/Models.tsx:248`); `DeploymentAlias.model_id` is `ON DELETE SET NULL` (`apps/backend/app/models/training.py:84`), so production silently stops with no statement to the user and no history entry.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) via the existing card — no new card in this area.
**Roboflow overlap:** `5-F5.37` → `T-267` already plans the typed name, the serving consequence and the alias binding to move. Covered; do not re-plan.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## 2.11 Permission on one model, not only on the project
**What it does.** Roles grant `READ`, `USE`, `EDIT`, `MANAGE` or `DENY` on a registered model, and since 3.17 on the `registered_model_version` tier; grants are keyed by model name, so a rename is refused while a named role holds an exact-name grant, and roles are workspace-scoped. A model version can be created only with read access to its source run. `(MLF: https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/ · https://mlflow.org/docs/latest/self-hosting/workspaces/ · https://github.com/mlflow/mlflow/releases/tag/v3.15.0)`
**UX flow, click by click.**
1. **Model header → Access** (managers only) — a list of project roles with a level picker (`No access` / `View` / `Use` / `Manage`), defaulting to the project's own roles. [empty: "This model follows the project's access — no exception yet."] [loading: the panel is read-only until the role list resolves] [error: a save that would lock out every manager is refused with "At least one manager must keep access."]
2. **Restricted model** — a workforce labeler opening the Models page sees the name and status with the weights and evaluation dimmed and a lock icon; the tooltip is "Your role cannot download weights for this model." [empty: a project with no restricted model shows no lock anywhere]
3. **API** — another project in the same workspace reads the row without weights, matching the existing lean masking; a foreign workspace id is a 404.
4. **Predict** — a caller whose role is below *Use* gets a 403 that names the model, while an unknown id stays a 404.
**LabelDesk:** PARTIAL — access is per project, not per model: `project.models` gates the list and detail (`apps/backend/app/routers/training.py:151,306`), `admin` gates delete and alias moves (`apps/backend/app/routers/training.py:316`, `apps/backend/app/routers/deployments.py:32,42`), and labelers get masked rows (`apps/backend/app/routers/training.py:162-163`); there is no per-model or per-version grant and no access panel.
**Priority:** Could · **Size:** M
**Decision:** Build (our store/UI) — the project stays the tenancy boundary; add one visibility level on the model with the existing role vocabulary, never a second auth boundary.
**Roboflow overlap:** `5-F5.39` → guard `T-005` covers the train/read split only.
**Sources:** https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/ · https://github.com/mlflow/mlflow/releases/tag/v3.13.0 · https://github.com/mlflow/mlflow/releases/tag/v3.17.0 · https://github.com/mlflow/mlflow/releases/tag/v3.10.0

## 2.12 Registry events on the webhook channel
**What it does.** Registry webhooks POST on `registered_model.created`, `model_version.created`, `model_version_tag.set`, `model_version_tag.deleted`, `model_version_alias.created` and `model_version_alias.deleted`; delivery is HMAC-signed, each webhook can be tested with a sample payload, and managing them needs admin. `(MLF: https://mlflow.org/docs/latest/self-hosting/webhooks/)`
**UX flow, click by click.**
1. **Settings → Webhooks** — the event picker gains a *Model registry* group with six checkboxes, each with a one-line description ("a version was registered", "an alias moved"). [empty: no webhook yet ⇒ today's empty state, plus the group is visible on create] [error: saving zero events keeps today's 400 message]
2. **Test** — *Send test* on a registry-only webhook delivers a sample `model_version.created` envelope with the version number and model name. [loading: the test button shows a spinner and the last status code] [error: a non-2xx target records the delivery row with the status and error]
3. **Delivery log** — each row names the event and the model, and the payload includes workspace and project ids so a receiver can route it.
4. **No new secret path** — the existing HMAC header and the SSRF-guarded fetcher are reused; an admin-only rule stays as today.
**LabelDesk:** PARTIAL — workspace webhooks exist with three events `job.done`, `model.ready`, `stream.event` (`apps/backend/app/models/common.py:16`), HMAC verification (`apps/backend/app/services/webhooks.py:41-52`), retries and a test endpoint (`apps/backend/app/routers/webhooks.py:128-135`), and `model.ready` already fires when a run registers (`apps/backend/app/handlers/training.py:176`); there is no version, tag or alias event, so a CI pipeline cannot react to a promotion.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — four event names and three emit calls on the existing channel.
**Roboflow overlap:** `7-F7.49` → `T-435` (sink inside a workflow) and `7-F7.51` → `T-438` (per-message cost) do not add registry events.
**Sources:** https://mlflow.org/docs/latest/self-hosting/webhooks/

## 2.13 Shared and cross-workspace registries
**What it does.** When workspaces are enabled, registered models and their versions are workspace-scoped and inherit their workspace; roles are workspace-scoped too, and the docs are explicit that workspaces are logical separation, not a hard isolation boundary. Managed registries add cross-workspace access to one registered model and a copy of a version into another registry. `(MLF: https://mlflow.org/docs/latest/self-hosting/workspaces/ · https://mlflow.org/docs/latest/ml/model-registry/ · https://github.com/mlflow/mlflow/releases/tag/v3.9.0)`
**UX flow, click by click.**
1. **Workspace → Models** — one list of every project's models, filterable by project and task, with a share action whose dialog states the consequence in place.
2. **Use a shared model** — another project's Train screen lists it as a starting checkpoint, priced before the run starts. [empty: nothing shared ⇒ the checkpoint picker shows only the built-in catalogue]
3. **Foreign workspace** — a model id from another workspace is a 404 everywhere, including the predict route.
**LabelDesk:** PARTIAL — the workspace registry endpoint returns the adapter catalogue plus ready models (`apps/backend/app/routers/registry.py:13-15`), the workspace deployment state aggregates every project (`apps/backend/app/routers/deployments.py:13-16`, `apps/backend/app/services/deployments.py:244-266`), and sharing is already planned.
**Priority:** Could · **Size:** S
**Decision:** Build — already planned; no new card.
**Roboflow overlap:** `5-F5.3` → `T-257` (workspace list + share), `7-F7.56` → `T-258` (shared checkpoint catalogue). Covered by `T-257`, `T-258` (area 5).
**Sources:** https://mlflow.org/docs/latest/self-hosting/workspaces/ · https://mlflow.org/docs/latest/ml/model-registry/ · https://github.com/mlflow/mlflow/releases/tag/v3.9.0

## 2.14 Comparing versions
**What it does.** The registry itself documents no version-to-version diff; a version page links its source run, and comparison is done on the runs' metrics and artifacts in the tracking UI. `(MLF: https://mlflow.org/docs/latest/ml/model-registry/workflow/ — version details list signature, source run, source logged model, timestamp; no comparison feature is stated)`
**UX flow, click by click.**
1. **Insights → Compare** — pick up to four models from the same dataset version, see overlaid precision–recall, per-class AP and a latency scatter, and open a disagreement image. [empty: "Pick two models to compare" and every pill enabled] [loading: a skeleton chart per panel] [error: "Comparison failed" + Retry]
2. **From a model** — *Compare* in the version row preselects it and its nearest peer.
**LabelDesk:** HAVE — `CompareTab` with a four-model cap, equal-version rule, disagreement detail and three chart types (`apps/frontend/src/features/insights/CompareTab.tsx:181,256,264,282-285`, `apps/frontend/src/features/insights/modelSelection.ts:13-35`), plus per-version analytics (`apps/backend/app/routers/insights_models.py:43-53`).
**Priority:** — · **Size:** —
**Decision:** none — parity already exceeded; keep.
**Roboflow overlap:** `4-F4.45` → guard `T-004`.
**Sources:** https://mlflow.org/docs/latest/ml/model-registry/workflow/ · https://mlflow.org/docs/latest/ml/model-registry/

## 2.15 Deployment-job state on a version
**What it does.** UNVERIFIED — the model-version entity carries deployment-job fields (`deployment_job_id`, `deployment_job_state`) that a managed deployment orchestrator sets, but no OSS docs page fetched in this session documents the behaviour: the only trace is the 3.17 release note about preserving `deployment_job_state` in converters and returning `None` when unset. LabelDesk has no managed deployment orchestrator, and its own serving state is the alias plus the deploy target. No card is written against a claim the docs do not make. `(MLF: https://github.com/mlflow/mlflow/releases/tag/v3.17.0 — release note only)`
**UX flow, click by click.** none — no documented flow, so none is invented.
**LabelDesk:** MISSING by design — serving state is `DeploymentAlias` plus the deployment page (`apps/backend/app/services/deployments.py:207-226`, `apps/frontend/src/features/project/Deploy.tsx:44-48`); there is no job-state field and none is needed.
**Priority:** — · **Size:** —
**Decision:** none — do not build a managed-deployment job model.
**Roboflow overlap:** `6-F6.11` → guard `T-006`.
**Sources:** https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## Judgment calls
- **2.1 grouped on the project, not the workspace** — MLflow's registry is server-wide; LabelDesk's tenancy is the workspace and the model list is already project-scoped, so grouping on the project reuses every existing route and leaves the cross-project view to `T-257`. A workspace-level group would duplicate that card.
- **2.5 no stages built** — the docs call stages deprecated and the alias already exists; copying a deprecated mechanism would add a second lifecycle vocabulary next to the deployment pointer.
- **2.7 contract derived, not imported** — a general schema language is the expensive half of signatures and LabelDesk has one input type (image) and three parameters, so the contract is derived from the task; `mlflow-skinny` buys nothing here.
- **2.8 plain text, not Markdown** — no renderer dependency is installed (`apps/frontend/package.json` has no Markdown package) and a model description is one paragraph plus a caveat; the shortcut is recorded in the card.
- **2.10 and 2.13 produce no card** — `T-267` and `T-257`/`T-258` already plan the same work; re-planning them would create a duplicate merge.
- **2.12 four events, not six** — tag events and alias events collapse into two emits on the same write paths, so the picker offers four names a receiver can actually act on.
- **2.15 no card** — the behaviour is only in release notes; the brief forbids a card on an unverified claim.
