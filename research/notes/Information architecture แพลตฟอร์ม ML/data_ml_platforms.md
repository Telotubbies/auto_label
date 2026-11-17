# Navigation, IA and feature surfaces of major data/ML platforms (2025-2026)

Research coverage is uneven. Databricks, Snowflake, Vertex and SageMaker got primary doc fetches. Azure, W&B, HF, Dataiku and DataRobot rest mostly on search snippets. Anything uncited is in Gaps.

## Databricks (sidebar, Unity Catalog, Mosaic AI, MLflow, monitoring, Genie)

### Takeaway
Databricks uses a flat left sidebar grouped by product area (general, SQL, Data Engineering, AI/ML), with Unity Catalog as the metadata spine that Genie and monitoring reuse.

### Cited Findings
- Top-level sidebar: Workspace, Recents, Catalog, Jobs & Pipelines, Compute, Discover, Marketplace. A lock icon marks items needing an entitlement you lack. — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- SQL group: SQL Editor, Queries, Dashboards, Genie Agents, Alerts, Query History, SQL Warehouses. — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- Data Engineering group: Runs, Data Ingestion. — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- AI/ML group: Playground, Agents, AI Gateway, Experiments, Features, Models, Serving. — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- Top-bar search covers notebooks, queries, dashboards, alerts, files, folders, libraries, UC tables, jobs, repos, plus recently viewed. No separate command palette is described. — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- AI assistant is "Genie Code" (formerly Databricks Assistant), opened from a sparkle icon in the top bar; it cites doc sources and declines when none are found. — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- Workspace switcher is the workspace name in the top bar (multi-workspace accounts only). — [Navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)
- Genie uses Unity Catalog metadata (table definitions, column descriptions, lineage, permissions) for accuracy and security; admins enable it from a Previews page. — search summary of [Databricks docs/release notes](https://docs.databricks.com/aws/en/release-notes/product/2026/june)
- Lakehouse Monitoring tracks statistical properties and quality of tables; docs for data quality monitoring were moved under Data governance (Unity Catalog). — search summary, see [release notes](https://docs.databricks.com/aws/ja/release-notes/product)

### Checklist (feature -> why it matters)
- [ ] Sidebar grouped by workflow area, not one long list -> scanability. Source: navigate-workspace above
- [ ] Locked items shown with an entitlement lock instead of hidden -> discoverability and upsell. Same source
- [ ] Unified search across object types plus recents -> one entry point. Same source
- [ ] Catalog as first-class nav item with lineage and permissions -> governance visible daily. Same source
- [ ] Assistant that cites sources and refuses when ungrounded -> trust. Same source
- [ ] Experiments / Models / Serving adjacent in nav -> lifecycle order. Same source

### Inferences
- The AI/ML group order (Experiments, Features, Models, Serving) roughly follows the lifecycle.
- Sidebar sections are partly entitlement-driven, so the layout differs by workspace type.

### Gaps
- No fetched source on MLflow UI tabs, Mosaic AI Model Serving specifics, or Lakehouse Monitoring dashboard layout.
- No source on persona-based switching; the nav page does not cover personas.

## Snowflake (Snowsight, Cortex, Horizon)

### Takeaway
Snowsight regrouped its menu into Work with data, Horizon Catalog and Manage, with governance and catalog elevated to their own group, and a 3-slot pinned shortcuts area.

### Cited Findings
- Work with data: Projects (Worksheets, Notebooks, Streamlit, Dashboards, Native Apps), Ingestion, Transformation (Dynamic tables, Tasks, dbt projects), AI & ML (Cortex AI, Snowflake ML), Monitoring (query history, container services, job history, traces and logs), Marketplace. — [Snowsight navigation](https://docs.snowflake.com/en/user-guide/snowsight-navigation)
- Horizon Catalog group: Catalog (Explorer, Internal Marketplace, Apps), Data sharing (Private sharing, Provider Studio), Governance & security (Trust Center, Tags & policies, Users & roles, Network policies). — [Snowsight navigation](https://docs.snowflake.com/en/user-guide/snowsight-navigation)
- Manage: Compute (Warehouses, Compute pools), Admin. — [Snowsight navigation](https://docs.snowflake.com/en/user-guide/snowsight-navigation)
- Pin up to three pages as Shortcuts; drag to reorder. — [Snowsight navigation](https://docs.snowflake.com/en/user-guide/snowsight-navigation)
- AI & ML > Studio is where Cortex features such as Cortex Search services are created. — search summary of [same page](https://docs.snowflake.com/en/user-guide/snowsight-navigation)
- Cortex Code in Snowsight went GA on 2026-03-09 (German release note) and uses Horizon Catalog context. — [Release note](https://docs.snowflake.com/de/release-notes/2026/other/2026-03-09-cortex-code-snowsight-ga); [Cortex Code doc](https://docs.snowflake.com/de/user-guide/cortex-code/cortex-code-snowsight)
- Cortex AI Guardrails (part of Horizon) GA 2026-04-20. — [Release note](https://docs.snowflake.com/en/release-notes/2026/other/2026-04-20-cortex-ai-guardrails-ga)
- Snowflake Intelligence uses agents over semantic views and search services and respects policies on underlying objects (translated pages, secondary). — [Horizon doc](https://docs.snowflake.com/de/user-guide/snowflake-horizon)

### Checklist
- [ ] Governance & security as its own nav group (policies, roles, trust) -> admin audit in one place. Source: snowsight-navigation
- [ ] User-pinned shortcuts (max 3) -> personalization without clutter. Same
- [ ] Monitoring group incl. traces and logs -> ops visibility. Same
- [ ] Assistant inheriting catalog permissions and guardrails -> safe AI. Cortex Code / Guardrails release notes

### Inferences
- Snowflake separates "work" from "govern" from "manage", which maps to builder, steward, admin personas.

### Gaps
- English Horizon and Snowflake Intelligence pages not retrieved; individual AI & ML children unlisted.
- Object search behavior unverified.

## Google Vertex AI

### Takeaway
Vertex organizes by ML lifecycle stage: develop, features, registry, evaluate, pipelines, metadata/lineage, experiments, monitoring, deploy; plus a separate generative AI lifecycle starting at Model Garden.

### Cited Findings
- Custom ML stages: Feature Store, Model Registry (versioning, aliases, labels), model evaluation incl. fairness, Pipelines (scheduling, retries, caching, lineage), ML Metadata (artifacts, executions, schemas), Experiments with TensorBoard, Model Monitoring (drift, skew), endpoints with online/batch inference. — [Vertex AI intro](https://docs.cloud.google.com/vertex-ai/docs/start/introduction-unified-platform)
- Gen AI stages: Model Garden (Google, partner, open models), Studio/prompt design, tuning, grounding, function calling, evaluation, deploy (Provisioned Throughput, PayGo, batch, context caching), administer. — [Vertex AI intro](https://docs.cloud.google.com/vertex-ai/docs/start/introduction-unified-platform)
- Console sidebar snapshots show Dashboard, Model Garden, Vertex AI Studio, Pipelines, Model Registry, Monitoring, Endpoints; order varies by version. — [Console page](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/text-multilingual-embedding-002)
- Model Garden described as a hub of 200+ models (search summary, secondary). — same console page

### Checklist
- [ ] Docs/nav follow lifecycle stages -> mental model for new users. Vertex intro
- [ ] Pipelines show lineage and caching -> reproducibility. Vertex intro
- [ ] Model Monitoring for skew and drift -> production trust. Vertex intro
- [ ] Model hub as start point for gen AI -> choose before build. Vertex intro

### Gaps
- Agent Builder not described on the fetched page. Last ~14k characters unread. No official current sidebar list.

## AWS SageMaker (AI Studio and Unified Studio)

### Takeaway
SageMaker has two shells: AI Studio with a left pane (Models etc.) and Unified Studio with a Build dropdown scoped to projects. Lineage lives on registry model versions.

### Cited Findings
- Lineage: Models > Registered models > Model Groups > model > Versions > version > Lineage tab, an interactive map of datasets, training jobs, approvals, models, endpoints; visualization only; not in Studio Classic; limited regions. — [Lineage in Studio](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-lineage-view-studio.html)
- Unified Studio: Model Registry reached from Build dropdown; shows models registered to the project; Model Groups and Collections tabs; packages versioned within groups. — [Unified Studio registry](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/sagemaker-register-models.xml.html)

### Checklist
- [ ] Project-scoped workspace -> permission boundary. Unified Studio doc
- [ ] Model groups with versions and approval state -> promotion flow. Lineage doc
- [ ] Lineage graph from model version -> audit. Lineage doc

### Gaps
- Full top-level nav, Pipelines, Jobs, Clarify/Model Monitor, JumpStart not researched. Lineage in Unified Studio unconfirmed.

## Azure AI Foundry (now Microsoft Foundry)

### Takeaway
Foundry portal centers on model catalog, agents, and evaluation, with trace-based evaluation from Application Insights.

### Cited Findings
- Evaluation: left pane Evaluation > Create, or a model's Evaluation tab; Traces option evaluates agent interactions from Application Insights by agent and time range. — [Evaluate generative AI app](https://learn.microsoft.com/en-us/Azure/foundry/how-to/evaluate-generative-ai-app)
- Roles renamed to Foundry User/Owner/Account Owner/Project Manager. — same page
- Product renamed Microsoft Foundry (secondary). — [Foundry overview](https://nicheelab.com/en/articles/azure/azure-ai-foundry-guide/)

### Checklist
- [ ] Evaluate from both a global page and the object page -> two entry points. Evaluate doc
- [ ] Evaluate from production traces -> closes the loop. Evaluate doc
- [ ] Role names tied to project hierarchy -> clear permissions. Evaluate doc

### Gaps
- Full sidebar, Azure ML studio nav, registry, lineage not retrieved. Catalog size claim (1,900+) is vendor-only, unverified.

## Hugging Face

### Takeaway
Hub is a resource-centric (models, datasets, Spaces) public/community product; model pages bundle card, widget/inference, stats, discussions; paid orgs add governance.

### Cited Findings
- Model pages: model card, usage examples, interactive widgets, download stats, discussions, license. — [Inference Providers docs](https://huggingface.co/docs/inference-providers/hub-integration)
- Inference Providers: widget and snippets honor user provider order; billing centralized. — same
- Dataset viewer public free, private PRO; Spaces Gradio/Streamlit with GPU. — [Review](https://www.modern-datatools.com/tools/hugging-face) (secondary)
- Enterprise: SSO, audit logs, storage regions, resource groups. — [HF docs index](https://docsearch.algolia.com/mcp/docs/repo/huggingface/hub-docs)

### Checklist
- [ ] Try-it widget on every model page -> instant value. Inference docs
- [ ] Dataset viewer in browser -> inspect before use. Review
- [ ] Resource groups and audit logs for orgs -> enterprise readiness. HF docs

### Gaps
- Official tab list and current pricing not verified.

## Weights & Biases

### Takeaway
W&B products: experiments, artifacts, reports, sweeps, registry, Weave (traces, evaluations). Docs now redirect to CoreWeave.

### Cited Findings
- Menus list Experiments, Reports, Artifacts, Tables, Sweeps, Models, Launch, Prompts, Weave; newer menus add Registry and Weave Traces, Evaluations, Guardrails. — [wandb.ai site](https://site.wandb.ai/?p=1170)
- docs.wandb.ai redirected to docs.coreweave.com/forge-home; Registry described as a versioned hub with lineage and deployment handoff; Weave for LLM and agent evaluation; existing users keep projects. — [CoreWeave docs](https://docs.coreweave.com/forge-home)

### Checklist
- [ ] Shareable Reports -> collaboration around results. Site menu
- [ ] Registry with lineage to runs/artifacts. CoreWeave docs
- [ ] Traces plus evaluations for LLM/agents. Site menu

### Gaps
- Redirect is from an unverified server header; details of panels, automations not read.

## Dataiku

### Takeaway
Dataiku separates design (Flow) from a Govern node for governance, with workflows over governed items.

### Cited Findings
- Govern has a main navigation menu and Application menu; top-bar pages hold synced and governed items; Administration covers security, logs, users, auth, notifications. — [Dataiku 14 Govern nav](https://doc.dataiku.com/dss/14/governance/navigation.html)
- Governance tutorial: surface items from Design nodes, add governance layer, move through workflows. — [Tutorial](https://knowledge.dataiku.com/14/govern/usage/basics/tutorial-index.html)

### Checklist
- [ ] Separate governance view over project items with sign-off workflow. Govern nav
### Gaps
- Flow, Lab, Deployer, assistant not retrieved.

## DataRobot

### Takeaway
DataRobot docs split Data, Modeling, Predictions, Notebooks, Apps, with an MLOps hub for deployments.

### Cited Findings
- UI docs sections: Get Started, NextGen, Data, Modeling, Predictions, Notebooks, No-Code AI Apps. — [DataRobot docs](https://docs.datarobot.com/en/index.html)
- MLOps hub: deploy, monitor, manage, govern any model; areas Deployments, Batch monitoring, Jobs, Key values. — [MLOps](https://docs.datarobot.com/en/docs/classic-ui/mlops/index.html.md); [Python API](https://docs.datarobot.com/en/docs/api/dev-learning/python/mlops/index.html)

### Checklist
- [ ] Deployments as the central monitored object, including external models. MLOps hub
### Gaps
- Governance/registry/assistant pages not read.

## Recurring patterns for a CV SaaS (inferences)

### Takeaway
Across the platforms with solid evidence, nav groups follow lifecycle (data, build, evaluate, deploy, monitor), governance is a distinct area, and AI assistants inherit catalog permissions.

### Inferences
- Lifecycle-ordered nav: Databricks AI/ML group, Vertex stages. Suggested: Datasets, Label, Train, Evaluate, Models (registry), Deploy, Monitor.
- Governance/admin group separate (Snowflake Horizon, Dataiku Govern): roles, audit log, policies.
- Registry with versions, aliases, approval, and lineage tab (Vertex, SageMaker, W&B): dataset version -> run -> model -> endpoint.
- Unified search plus recents; user pins (Snowflake 3 shortcuts).
- Assistant grounded in workspace metadata and permissions, citing sources (Databricks, Snowflake).
- Evaluate from both a global page and object page; trace/production-based evaluation (Foundry).
- Entitlement-locked items visible (Databricks).
- Inline try-it and data viewer (HF) fit CV: image viewer, predictions overlay.
- Shareable reports (W&B).
- Project-scoped workspaces (SageMaker Unified Studio).

### Gaps
- Command palette (Cmd-K) not documented in any fetched source; verify live UIs. Persona-based navigation not substantiated by sources.
