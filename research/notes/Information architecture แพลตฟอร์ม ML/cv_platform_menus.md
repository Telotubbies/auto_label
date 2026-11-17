# Navigation and menu structure of CV / data-labeling platforms (2025-2026)

Method note: fetched ~17 pages on 2026-11-01. Docs landing pages and llms.txt indexes gave reliable page-level structure; live in-app sidebars are behind login and mostly NOT verifiable. Items marked (docs-derived) are inferred from docs section names, not from a screenshot of the app. Several fetches failed (SuperAnnotate docs root 401, Labelbox docs/home 404, LandingLens nav not exposed).

## Per-platform menu trees (what could be verified)

### Takeaway
Ultralytics Platform, CVAT and FiftyOne Enterprise have the best-verified in-app menus. Roboflow, Encord, V7 are verified at docs-structure level only. Labelbox, SuperAnnotate, Supervisely, LandingLens, Scale are partial. The cross-platform pattern is: Data/Datasets -> Annotate/Label -> Train/Models -> Deploy/Monitor, plus Explore/curation, Workflows/automation, Analytics, and Admin/Settings.

### Cited Findings

**Roboflow**
- Docs top-level cards: Datasets, Models, Deployments, Workflows, Developer Reference, Agents — [docs.roboflow.com](https://docs.roboflow.com/)
- Docs index (llms.txt) sections: Workspaces (Create/Rename/Delete Workspace, Asset Library, Trash); Projects and Datasets (Create a Project, Upload, Datasources + cloud credentials); Teams and Roles (Invite/Change Role/Remove member, RBAC, SSO, Audit Logs and SIEM Export, Workspace Announcements, Teams Add-On with Labeler/Reviewer roles and Review Mode); Billing and Plans (Credits, Billing Folders, Usage Projection); Models (Train, Roboflow Instant, Neural Architecture Search, Evaluate/Compare, Upload/Download weights, Rapid); Workflows (Build, Test, Workflows AI Assistant, Workflow Evals, Versions, Share, Deploy, Blocks, Custom Blocks); Deployment (Serverless Cloud API, Batch Processing, Cloud Streaming, Dedicated Deployments, Self-Hosted Inference Server, Deployment Manager with devices/streams/alerts); Monitoring and Analytics (Model Monitoring, Alerting, Vision Events with Query/Automations/Operator Feedback/Summary Reports, Active Learning) — [llms.txt](https://docs.roboflow.com/llms.txt)
- Llms.txt was truncated before the Annotate and Universe sections (153k chars, read first 100k). In-app project sidebar labels (e.g. Upload Data, Annotate, Dataset, Versions, Models, Deploy, Active Learning) are NOT verified here — see Gaps.

**Encord**
- Docs landing: Data (Supported Data, Data Integrations, Import Cloud Data, Data Curation), Platform (Annotation, Export Labels, Model Evaluation), SDK — [docs.encord.com](https://docs.encord.com/)
- Product areas from index: Index (metadata schema, curate and explore visual/audio, custom embeddings); Active (label collections, bulk actions, issues and comments, data visualization, label validation, import predictions, compare model performance, model predictions and evaluation); Annotate (Label Editor with annotation/review modes, SAM segmentation and tracking, interpolation, modalities: images, video, time series, scenes, audio, documents, text/HTML, DICOM/NifTI, multimodal groups, automatic annotation, review tasks, issues); Workflows (templates, consensus, task queue, webhooks and notifications, annotator training, automated QA); Analytics (dashboards, project analytics, workspace analytics, embedding plots, duplicate image finder); Admin (workspace settings, user and resource management, external workforces, SSO, SDK access keys); Roles (Admins, Workspace/Project Admins, Managers, Workforce Managers, Team Managers, Taskers = Annotators and Reviewers, Tasker Quickstart); Agents (built-in and custom, task-ready notifications); Ontologies; Datasets; Projects (settings, copy/split/merge, adding users, timers) — [llms.txt](https://docs.encord.com/llms.txt)

**V7 (Darwin)**
- Docs sections: Workflows (stages: Annotate, Review, Model, Webhook, Consensus, Logic, Archive, Sampling; add team, assign tasks), Datasets (create, import, export versions, classes, properties, tags, filter and sort, bulk changes, merge/duplicate), Models (train, auto-label, BYOM, HuggingFace), Teams (Workspaces for multiple teams, SSO/SAML), Roles (User roles, User Tags), Settings (External Storage, credit/storage calculation), Annotator/Reviewer (Annotation Workview, Layouts, Annotate Stage, Review Stage, time tracking, labelling workforce) — [docs.v7labs.com/llms.txt](https://docs.v7labs.com/llms.txt)
- Third-party vendor page says member invites are at Settings > Members (not V7 primary source) — via search summary of [opentrain.ai](https://www.opentrain.ai/tools/v7-labs)
- No dedicated Dashboard or Data Explorer page found in the index.

**Labelbox**
- Primary-doc overview: products Annotate, Catalog (25+ cloud sources, vector and traditional search, curation, bulk classification), Model (custom models, import predictions, error analysis), Foundry (foundation models in labeling) — [docs.labelbox.com/docs/overview](https://docs.labelbox.com/docs/overview)
- 2023 release notes: nav panel moved to the left with Annotate, Model, Catalog, Schema tabs plus dark mode, notifications, help center, account settings — summarised from [Labelbox Q3 2023 blog](https://labelbox.com/blog/q3-2023/) (search snippet only; may be outdated)
- Roles and workspace settings: overview only points to a Team management guide; not verified.

**SuperAnnotate**
- Overview: Import (Integrations, Attach URLs via CSV), Pre-annotations, Explore (item status/assignments, native query language, Subsets, Zoom View, bulk actions), Orchestrate (canvas of components and custom actions, monitoring graphs/tables), Python SDK — [doc.superannotate.com overview](https://doc.superannotate.com/docs/superannotate-overview)
- Docs sidebar lists Analytics subpages: overview, status distribution, team performance, class distribution, filter — via search summary of [analytics-filter](https://doc.superannotate.com/docs/analytics-filter)
- Roles (annotator, QA, project admin, team/organization owner): referenced ("organization owner" learning hub) but not detailed — [learning hub](https://superannotate.com/learning-hub-categories/organization-owner)

**Supervisely**
- Left-sidebar items mentioned in docs: Tasks & Apps (Tasks tab, Apps tab), Projects, Team Files, Current Team members (Invite button), Team Cluster (connected agents), Labeling jobs, More Features (Categories incl. Import), Ecosystem (app store). Team roles named: Admin, Labeler (reviewer/manager not found in fetched part) — [llms-full.txt](https://docs.supervisely.com/llms-full.txt) (first 100k of 584k chars read)
- Docs sections: Data Organization, Labeling, Neural Networks, Kubernetes "Connect cluster", Collaboration — [docs.supervisely.com](https://docs.supervisely.com)

**CVAT**
- Docs Workspace section = in-app top-level pages: Projects, Tasks, Jobs, Cloud storages (Attach cloud storage), Requests, Models, Bulk actions, Search — [docs.cvat.ai/docs](https://docs.cvat.ai/docs/)
- Account management: registration, User roles, Organization, Subscription, SSO and social auth — same source
- Annotation editor: Menu and Navbar, Workspace, Objects sidebar, Controls sidebar, Settings, Layers, 3D workspace; annotation modes (single shape, track, attribute annotation, 3D, tags); tools (join/slice, filter, multi-select, OpenCV tools); Audio editor — same source
- QA and Analytics: Quality control, Manual QA, Automated QA, Consensus, Immediate job feedback, Analytics — same source
- Automated annotation: SAM2 Tracker, AI assistance, AI models. Integrations: FiftyOne, Human Protocol — same source
- Site header: Docs, Quickstart, Guides, Sign in, Get started (Community/Online/Enterprise), Contact us — same source

**Landing AI (LandingLens)**
- Seven-step workflow: create project, upload images, create classes, label, train, review predictions, deploy — [landinglens-workflow](https://landinglens.docs.landing.ai/landinglens-workflow)
- Project roles: Owner, Labelers (label only), Standard (permissions: Upload Data, Train Model, Deploy Model, Direct Label) — via search summary of [collaborate-on-projects](https://support-landingai.document360.io/regulated/docs/collaborate-on-projects) (older doc, 2022; may have changed)
- "Member Roles" page exists in docs nav; contents not retrieved.

**Ultralytics Platform (best verified)**
- Sidebar top: Search (Ctrl/Cmd+K), Home, Explore, Agents. Content: Annotate (datasets), Train (projects), Deployments (each shows 5 most recent items). Footer: Help, Settings, Account menu (workspace switcher, activity, Redo Tour, log out). Trash reachable from search at /trash — [Quickstart](https://docs.ultralytics.com/platform/quickstart/)
- Home: welcome card with workspace stats (datasets, images, annotations, projects, models, exports, deployments), quick actions, recent activity table — same source
- Annotate: dataset sources Upload, URL, Cloud (Pro+), On Premise (Enterprise). Train: model tabs Metrics, Validation, Console, System. Deploy: latency map region picker, dedicated endpoints start/stop/delete. Deployments page: global map, 24h metrics, endpoint list. Per-model Predict tab (confidence, IoU, image size, Python/JS/cURL code). Settings: profile, billing, API keys, preferences — same source
- Onboarding: sign up (Google/GitHub/email) -> profile (name, permanent username, org, use case) -> data region (US/EU/AP, latency-recommended, permanent) -> claim credits ($25 work email, $5 personal); guided tours Nav, Project, Dataset — same source
- Platform docs nav: Overview, Quickstart, Agents, Data, Train, Deploy, Integrations, Account, Explore, REST API; Monitoring = real-time metrics, request logs, dashboards; Trash keeps items 30 days; Teams and Organizations with roles/invites (roles not defined) — [docs.ultralytics.com/platform](https://docs.ultralytics.com/platform/)

**Scale AI**
- Nucleus described as dataset management platform; docs at scale.com/docs and separate Nucleus docs site; no in-app navigation found — [scale.com/docs/nucleus](https://scale.com/docs/nucleus)

**FiftyOne (open source + Enterprise)**
- Enterprise homepage = Datasets page: "All datasets" count, table (20/page), New dataset button (name, description, tags), Pinned datasets widget, search bar (name, tags, media type), sort (size, created, recent use, name) — [enterprise/app](https://docs.voxel51.com/enterprise/app.html)
- Dataset view: Samples tab, Manage tab with Basic info (edit, clone), Access (users and permissions: "Can view", "Can manage"), Danger zone (delete). Discussion panel with comments/threads, anchored comments Enterprise-only — same source
- Docs sections: Fundamentals incl. Roles and permissions (Enterprise), Plugins, Secrets, Model Evaluation, Visualize in App (images/video/3D). App panels Histograms/Embeddings/Map/Model Evaluation not described on pages fetched — [docs.voxel51.com](https://docs.voxel51.com/)

### Inferences
- Persona views are mostly implemented as role-gated pages rather than separate apps: Encord (Taskers vs Managers vs Admins), Roboflow (Labeler/Reviewer via Teams add-on), LandingLens (Labelers = label only), Supervisely (Labeler restricted to annotating), V7 (Annotate and Review stages, user roles).
- Data scientist view = Explore/Catalog/Index/Active/Model evaluation; reviewer view = review stage/queue + issues; admin = workspace settings, SSO, billing, audit logs.

### Gaps
- Exact live in-app sidebar labels for Roboflow, Encord, V7, Labelbox, SuperAnnotate, Landing AI, Scale (login-walled; docs only).
- Roboflow Universe and Annotate doc sections (truncated) and Roboflow project sidebar names.
- Per-persona landing dashboards: only Encord (Analytics dashboards, workspace/project analytics), CVAT (Analytics), SuperAnnotate (Analytics, Orchestrate monitoring), Ultralytics (Home) verified.
- Global search: verified only for Ultralytics (Ctrl+K), CVAT (Search page), FiftyOne Enterprise (dataset search), Labelbox Catalog (vector search), SuperAnnotate Explore (query language). Not verified for others.
- Onboarding: verified only for Ultralytics (and LandingLens 7-step workflow); Encord Tasker Quickstart exists but not read.
- Scale Data Engine/Studio/Donovan/Rapid navigation: nothing found.

## Union list of menu items and features

### Takeaway
A reusable IA covers about 15 top-level areas; those present in at least 3 platforms are the safest to adopt.

### Cited Findings (union, with platforms where verified above)
- Home/Dashboard with workspace stats and recent activity (Ultralytics; analytics dashboards in Encord, CVAT, SuperAnnotate)
- Explore/Discover public projects and datasets (Ultralytics Explore; Roboflow Universe per name only, unverified section)
- Search: global command palette (Ultralytics), Search page (CVAT), dataset search/sort (FiftyOne), query language + Subsets (SuperAnnotate), vector search (Labelbox Catalog)
- Projects (CVAT, Supervisely, Encord, Roboflow, Ultralytics Train, LandingLens)
- Datasets/Data/Catalog/Index (all)
- Tasks and Jobs (CVAT), Labeling jobs (Supervisely), Task Queue (Encord), Annotate/Review stages (V7)
- Annotation editor with objects sidebar, controls sidebar, settings, layers (CVAT); Label Editor (Encord)
- Review/QA/Consensus/Issues (CVAT, Encord, V7, Roboflow Review Mode)
- Ontology/Classes/Schema (Encord Ontologies, Labelbox Schema, V7 classes, LandingLens classes)
- Models/Train/Evaluate/Compare (Roboflow, Ultralytics, V7, Encord Active, Labelbox Model, CVAT Models)
- Auto-annotation/AI assist (CVAT SAM2, Encord SAM, V7 auto-label, Roboflow Rapid/Workflows assistant, SuperAnnotate pre-annotations, Labelbox Foundry)
- Workflows/automation/Agents/Orchestrate (Roboflow Workflows, V7 Workflows, Encord Workflows+Agents, SuperAnnotate Orchestrate, Ultralytics Agents)
- Deploy/Deployments/Monitoring (Roboflow, Ultralytics)
- Cloud storage/Integrations/Datasources (CVAT, Roboflow, Encord, SuperAnnotate, V7)
- Requests/background jobs (CVAT Requests), Bulk actions (CVAT, Encord, SuperAnnotate, V7)
- Team/Members/Roles/Organization/Workspace switcher/SSO (all)
- Settings: profile, billing, API keys, preferences (Ultralytics); credits/billing (Roboflow, V7)
- Trash with 30-day restore (Ultralytics, Roboflow)
- Ecosystem/app store/plugins (Supervisely, FiftyOne)
- Help, guided tours, feedback (Ultralytics)
- Audit logs and SIEM export, announcements (Roboflow Enterprise)
- Webhooks and notifications (Encord, V7), SDK/CLI/API tokens (CVAT, Encord, Roboflow)

### Inferences
- A minimal MVP nav for a small labeling SaaS: Home, Datasets, Annotate (task queue), Review, Models, Deployments, Explore, Team, Settings, Trash, plus Cmd+K search.

### Gaps
- Same as above; union list is only as complete as the verified docs.
