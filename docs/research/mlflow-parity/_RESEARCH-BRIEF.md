# MLflow parity lane — research brief (read fully before writing anything)

Owner directive, 2026-11-17: "copy Roboflow and MLflow entirely". Roboflow is closed by
[`../roboflow-parity/PARITY.md`](../roboflow-parity/PARITY.md) and its backlog. This lane does the same for
**MLflow**: every feature in its current docs site and the release notes of the last 12 months, LabelDesk
branding, with an explicit integrate-the-library-or-build decision per feature.

Baseline: `feat/labeldesk-v2` at `f6feb09`. Read-only lane. You may write **only**:

- `docs/research/mlflow-parity/**`
- `docs/research/roboflow-parity/backlog/T-9xx.md` (new cards only, ids in your band)
- nothing else. No application code, tests, config, `board.md`, git state. No merge, rebase, push,
  branch delete, or process kill.

Never invent a path. Every file you cite was verified with a read, glob or grep in this session. A file the
card will create is marked `(new)`.

---

## 1. Rules that bind every row and card

**Status**
- **HAVE** — the flow exists end to end; a user can finish it without leaving the product.
- **PARTIAL** — a real implementation exists but a documented part of the flow is missing (an option, a
  state, a permission path, a second surface).
- **MISSING** — no implementation, or a data field with no flow behind it.

**Priority for a commercial CV SaaS:** Must = a buyer evaluates on it; Should = gap a buyer notices in a
trial; Could = long-tail or differentiation.

**Size:** S ≤ 1 day, M 2–5 days, L > 1 week (one engineer).

**Evidence** — two kinds, both required per row:
1. **MLflow claim** → the exact docs URL you fetched. Quote the behaviour in your own words.
2. **LabelDesk status** → verified repo path plus line where it matters.

A claim with no URL is written `UNVERIFIED — <why>` and gets no card. A status with no path is not
allowed.

**Branding.** LabelDesk names, copy and icons only. MLflow may appear once per card or area file as a
source label (`(MLF: tracking/runs.html)`), never as a product name a user reads, never as a UI heading, and
its logo/wordmark is never used. Its code is Apache-2.0: reuse is allowed **with attribution**; its name and
logo are trademarks and are not ours to use as branding.

---

## 2. Integrate the library, or build it

Ponytail applies to features, not only to code: the smallest complete change that gives the behaviour.

**Integrate** (add `mlflow-skinny` as an optional extra, never a hard requirement) when the feature is a
library contract that is expensive to reproduce and cheap to call:
- packaging/loading a model in a portable flavour (`mlflow.pyfunc`) — the flavour zoo is thousands of
  lines and we already ship our own runtime;
- `mlflow.evaluate`-style metric bundles where the metric definition is the value (and only then);
- the **client** side of run logging in notebooks (`mlflow.log_*` pointed at LabelDesk).

**Build** (our tables, our routes, our UI) when the feature is tenancy, identity, storage or a screen:
- the tracking store, registry store, UI, auth, workspaces, experiments — MLflow's own server has no
  workspace isolation, no per-tenant RBAC and a second database; embedding it would put a second auth
  boundary in front of customer data. That is a security decision, not a preference.
- anything a user clicks.

**Wire compatibility beats server reuse.** Where an external MLflow client should be able to log into
LabelDesk, we implement the small subset of the MLflow REST wire format we need
(`/api/2.0/mlflow/runs/*`) behind our own auth. That is the integration: their client, our tenancy.

Every row states one of: `Integrate (mlflow-skinny, optional extra)`, `Build (our store/UI)`,
`Wire-compatible (MLflow REST subset)`, or `Integrate + Build` with the split named.

Any card that adds the library must add an attribution block to `THIRD_PARTY_LICENSES.md` (Apache-2.0,
project URL, version) — the card says so under Backend changes. Any card that copies MLflow source into
our tree says so explicitly and keeps the Apache-2.0 header.

---

## 3. Row ids and area ownership

Row id = `ML<area>-T<feature>.<n>`, numbered `1..n` inside the area, e.g. `ML1-T1.4`.

| Area | Scope | Row prefix | Card band | Cards ≤ |
| --- | --- | --- | --- | --- |
| 1 | Tracking — runs, params, metrics, artifacts, system metrics, autolog, nested runs, run comparison, charts, search/filter syntax | `ML1-T1.x` | `T-900`–`T-917` | 18 |
| 2 | Model Registry — models, versions, aliases, tags, stages/lineage, model cards/signature, input examples | `ML2-T2.x` | `T-918`–`T-931` | 14 |
| 3 | Models & deployment — flavours, pyfunc, serving, batch, docker build, deployment plugins | `ML3-T3.x` | `T-932`–`T-945` | 14 |
| 4 | Evaluation & GenAI — `mlflow.evaluate`, metrics, custom judges, datasets, tracing, prompt registry | `ML4-T4.x` | `T-946`–`T-967` | 20 |
| 5 | Platform — projects, recipes/pipelines, auth/permissions, REST API, client SDKs, UI navigation, experiments, workspaces | `ML5-T5.x` | `T-968`–`T-999` | 24 |

Cards are numbered **contiguously, ascending, from the start of your band**, in dependency order. Leave the
tail of the band unused rather than spilling into another band. Report the highest id you used.

**Deduplicate against Roboflow.** A feature that an existing card already delivers gets **no new card**;
your mapping row cites the existing card id and your area file says `covered by T-<id> (RF row <row>)`.
Look the card up by grepping `docs/research/roboflow-parity/backlog/INDEX.md` for the parity row id. Known
overlaps to check first:

| MLflow area | Roboflow rows / cards likely to already cover it |
| --- | --- |
| Tracking: run list, metric charts, run comparison | `5-F5.16` live training graphs, `5-F5.27` comparison, `4-F4.45` version analytics, `4-F4.44` cached report staleness |
| Tracking: params/config capture | `5-F5.7`, `5-F5.9` recipe editor and speed preset (the run's hyper-parameters) |
| Registry: versions, aliases, production pointer, lineage | `5-F5.33` stable identity, `5-F5.34` per-version alias, `5-F5.35` production pointer, `6-F6.11` immutable identity + pointer, `5-F5.36` starred candidate |
| Models/deploy: serving, batch, docker, runtime picker | `6-F6.1`, `6-F6.2`, `6-F6.4`, `6-F6.5`, `6-F6.8`, `6-F6.10`, `6-F6.12`, `6-F6.45` |
| Eval: metrics, per-class, confusion, eval for uploaded weights, regression evals | `5-F5.20`–`5-F5.30`, `5-F5.53`–`5-F5.54` |
| Platform: API keys, audit, workspaces, members | `1-F5.4`, `7-F7.25`–`7-F7.29`, `7-F7.38`, `7-F7.39` |
| Platform: pipelines/recipes | `6-F6.21`–`6-F6.30` (workflow builder) — recipes are *not* the same thing; judge honestly |

---

## 4. Code map (verified 2026-11-17, `f6feb09`)

Backend — `apps/backend/app/`:
- routers: `training.py` (models, leaderboard, train, predict, autolabel), `registry.py` (workspace model
  registry), `deployments.py` (aliases + rollback), `insights_lineage.py`, `insights_models.py`
  (`/training`, `/compare`), `versions.py`, `images.py`, `workflows.py`, `batch_inference.py`,
  `devapi.py` (public API v1), `rbac.py`, `workspaces.py`, `audit.py`, `flags.py`, `admin.py`.
- models: `training.py` (`Job`, `TrainedModel(metrics, history, classes, weights, family, variant,
  license, runtime_refs)`, `AnomalyStation`, `DeploymentAlias(alias, model_id, previous_model_id)`,
  `DeploymentEvent`, `DriftSample`), `project.py`, `identity.py`, `insights.py`, `streams.py`, `alerts.py`.
- services: `ml.py`, `evaluate.py`, `drift.py`, `deployments.py`, `insights_*.py` (dataset, embedding, eval,
  jobs, lineage, query, selection, stream), `metering.py`, `flags.py`, `secretbox.py`, `safefetch.py`,
  `exporters.py`, `versioning.py`, `workflow_runner.py`, `capabilities.py`.
- schema blocks: `app/schema/{columns,dataset,identity,streams,training}.py`, applied by `schema.apply`.
- SDK: `packages/sdk/labeldesk/{client.py,cli.py}`.

Frontend — `apps/frontend/src/`:
- `features/insights/{Insights.tsx,TrainingTab.tsx,EvaluationTab.tsx,CompareTab.tsx,charts.tsx,useInsights.ts,modelSelection.ts}`
- `features/evaluation/EvalPanel.tsx`, `features/lineage/{Lineage.tsx,lineageModel.ts}`
- `features/project/{Models.tsx,Train.tsx,Deploy.tsx,Versions.tsx,Insights.tsx,ProjectLayout.tsx,Dataset.tsx,Workflows.tsx}`
- `routes/project/{models,deploy,data,studio,settings}.routes.tsx`, `lib/nav/project/*.ts`,
  `lib/nav/registry.ts`, `lib/api/*.ts`, `components/glass.tsx`, `components/ui.tsx`, `index.css`.

Before you claim MISSING, grep twice: once for the noun, once for the verb a user would perform.

---

## 5. What you deliver

### 5.1 One area file: `docs/research/mlflow-parity/<area>.md`

Names: `01-tracking.md`, `02-model-registry.md`, `03-models-deploy.md`, `04-evaluation-genai.md`,
`05-platform.md`.

```markdown
# MLflow parity — Area <n>: <name>

Baseline `feat/labeldesk-v2` @ `f6feb09`. MLflow docs read at <date>. Release notes window
2025-11-17 → 2026-11-17 checked at <url>.

**Doc pages covered (full navigation walk).** <one URL per line, grouped by docs section>

## Area count
<n> rows: <h> HAVE · <p> PARTIAL · <m> MISSING.

## <n>.1 <feature name in LabelDesk words>
**What it does.** <2–4 sentences, behaviour only.> `(MLF: <docs url>)`
**UX flow, click by click.**
1. **<Screen>** — <action>. [empty: …] [loading: …] [error: …]
2. …
**LabelDesk:** <HAVE|PARTIAL|MISSING> — <verified path:line, path, path>. <what exists, what is absent>
**Priority:** Must|Should|Could · **Size:** S|M|L
**Decision:** <Integrate …|Build …|Wire-compatible …> — <one line why>
**Roboflow overlap:** <RF row → T-xxx / none>
**Sources:** <url>[, <url>]

… repeat …

## Judgment calls
- <row> — <decision and the one-line reason, where the docs allowed two readings>
```

Every row carries **What · UX flow · LabelDesk status+evidence · Priority · Size · Decision · Overlap ·
Sources**. A row without a click-by-click flow is a doc summary, not a plan, and is rejected.

The "Doc pages covered" list is your proof of a full navigation walk: the docs sidebar you actually
fetched, not a guess. Include the pages that produced no row (a page with nothing new still gets listed and
one line saying why).

### 5.2 Cards: `docs/research/roboflow-parity/backlog/T-9xx.md`

Read `docs/research/roboflow-parity/backlog/_BRIEF.md` §2 **fully** and copy its template exactly: same
headings, same order, same field table. Deviations for this wave, and only these:

- `| Wave | M |`
- `| Parity rows | `ML1-T1.3`, `ML1-T1.4` (PARTIAL) |` — MLflow row ids, not Roboflow ids.
- `| Feature flag | `task_mlruns` (new line in `services/flags.py`) / none |`
- Under **Notes for the implementer**, first line must be
  `Overlap: <RF row> → <T-xxx|none>.` so the merge captain sees why this is not a duplicate.
- Every card's Backend changes names the `THIRD_PARTY_LICENSES.md` line when it adds `mlflow-skinny`.

Everything else is unchanged: one agent 1–3 hours, exact verified files, Exclusive vs Shared file split,
pytest **and** node test lines (or `none: no frontend surface`), 3–7 acceptance criteria, and these three
always:
- `[ ] Empty, loading and error states above all render.`
- `[ ] Workspace A cannot see or change workspace B's data (404, not 403, for cross-workspace ids).`
- `[ ] Flag off ⇒ surface absent and the old behaviour unchanged.`

No card asks for a refactor the gap does not need. No new dependency for a few lines. A card that adds a
route or schema says `OpenAPI: yes` and names the two commands.

### 5.3 One part index: `docs/research/mlflow-parity/parts/area-<n>.md`

Exactly the shape of `_BRIEF.md` §6, with `Part <n> — Area <n> <name>` and the same five sections
(Mapping · Shared-file users · Cards · Judgment calls). Mapping lists **every row of your area exactly
once**, including HAVE rows (`—` plus the guard card that asserts it, or a note that no guard exists yet).
Hours in the header = sum of your cards.

---

## 6. Self-check before you report back

- [ ] Full docs navigation walked; "Doc pages covered" lists every page you read.
- [ ] Release notes of the last 12 months read; features that only exist there are rowed.
- [ ] Every row: what · click-by-click flow · status+verified path · priority · size · decision · overlap · URL.
- [ ] Every PARTIAL/MISSING row has ≥ 1 card, in band, contiguous, ≤ 3 h each, template-exact.
- [ ] No card duplicates an existing `T-` card; the mapping cites it instead.
- [ ] No file path you did not verify; `(new)` on files that do not exist yet.
- [ ] No MLflow name, logo or string presented as our UI copy.
- [ ] Part index matches the cards (ids, hours, files).
