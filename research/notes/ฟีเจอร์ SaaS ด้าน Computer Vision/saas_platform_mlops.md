# SaaS Platform and MLOps Requirements for a CV Labeling + Training + Deployment SaaS (LabelDesk)

Research date: 2026-10-31. Vendor pages were fetched live on that date unless noted. Where a vendor page did not state something, it is listed under Gaps instead of being inferred.

## 1. Multi-tenancy, RBAC, SSO/SCIM, API keys, audit logs (vendor comparison)

### Takeaway
Every serious competitor puts SSO, RBAC/custom roles, scoped API keys and audit logs behind an Enterprise or Team paywall. A two-level role model (workspace role + project role), per-user revocable API keys, and BYO cloud storage (data stays in the customer's bucket) are the baseline. Hard isolation (VPC, on-prem, air-gapped, customer KMS) is the top tier.

### Cited Findings
**Roboflow**
- SSO, RBAC, custom roles, folder permissions, billing folders and scoped API keys are Enterprise-only and not in Core ($39/mo). Audit logs and SIEM log exports are listed as Enterprise add-ons. Data sovereignty (US or EU) is Enterprise-only. On-prem install is an optional professional service, and air-gapped deployment is a Manufacturing add-on. — [Roboflow Pricing](https://roboflow.com/pricing)
- Workspace API keys can be created, listed, renamed, disabled, protected and revoked through the REST API (the same surface backs the `roboflow api-key` CLI and an MCP server). A scope of `null` means a full-access key. An array of scope strings restricts the key, for example to managing images in one project but not models. Explicit scopes, folder restrictions and key metadata need the "Advanced API Keys" plan feature and return 403 otherwise. Publishable keys (`rf_<workspaceId>`) are rejected by management endpoints. — [Roboflow Scoped API Keys](https://docs.roboflow.com/developer/authentication/scoped-api-keys); [Manage API Keys](https://docs.roboflow.com/developer/rest-api/manage-api-keys)
- Audit logs are a premium feature covering team membership, roles, projects, datasets, workflows, devices, API keys and exports. They are searchable back 365 days by default, and a SIEM tab exports over OTLP (gRPC or HTTP/Protobuf). — [Roboflow Audit Logs & SIEM Export](https://docs.roboflow.com/roboflow/roboflow-hi/workspaces/audit-logs-and-siem-export) (the 365-day detail is from the Hindi-localized page)
- The Trust Center lists MFA, Audit Logging and Data Erasure as product-security items, and AES-256 encryption. — [Roboflow Trust Center](https://security.roboflow.com/)

**Encord**
- Two-level RBAC. Workspace roles are Admin, Workforce Manager, Member and Tasker. Separate project roles are Admin, Team Manager, Annotator, Reviewer and Annotator+Reviewer. API keys are per user, revocable, and limited to that user's permissions. — [Encord Security & Compliance](https://docs.encord.com/solutions-documentation/enterprise-ai/security-and-compliance)
- Audit events cover logins, task creation and state changes, label submit/approve/reject, and user or permission changes. Enterprise customers get audit logs on request through their CSM, not self-serve. SSO with an existing IdP is set up through support. — [Encord Security & Compliance](https://docs.encord.com/solutions-documentation/enterprise-ai/security-and-compliance)
- Deployment ladder: default hosted on GCP, then BYO storage (raw files stay in the customer's AWS/GCP/Azure buckets and are not copied), then VPC (full stack in the customer cloud), then on-prem/air-gapped. VPC and on-prem can use the customer's own KMS. — [Encord Security & Compliance](https://docs.encord.com/solutions-documentation/enterprise-ai/security-and-compliance)

**Labelbox**
- With IAM delegated access, the customer's cloud provider authenticates every platform action. Each time Labelbox assumes the IAM role to read a file, the customer's cloud audit log records the role, object, time and source IP. — [Labelbox Docs: Access storage](https://docs.labelbox.com/docs/access-storage); [Labelbox blog, Feb 2021 (older)](https://labelbox.com/blog/simplify-your-data-security-with-iam-delegated-access)
- SSO (via Auth0) is available for all Enterprise accounts. A 2021 post lists SAML, Okta, OneLogin, Google Apps, ADFS and Azure. MFA is supported. — [Labelbox Security](https://labelbox.com/security); [Labelbox blog 2021 (older)](https://labelbox.com/blog/cloud-integrations-and-hipaa)
- Labelbox has a dedicated audit-log docs page. — [Labelbox Audit Logs](https://docs.labelbox.com/docs/audit-logs)

**V7 Darwin**
- SSO supports SAML and Google OAuth 2.0. Admins can "Enforce SSO", which disables password login. New SAML users join with a configured default role. — [V7 Docs: SSO configuration](https://docs.v7labs.com/docs/single-sign-on-sso-configuration)
- Some tiers offer direct S3 integration so image and video data never sits on V7 servers. Default Darwin storage is AWS S3 in Ireland (EU). — [V7 Darwin Security](https://www.v7darwin.com/security)
- The current v7labs.com pricing page sells V7 Go (document agents), not Darwin. It lists role-based and fine-grained access, audit logs, SOC 2 Type II, GDPR, private deployment and E2E encryption, with "no feature tiers" and an annual agreement. — [V7 Pricing](https://www.v7labs.com/pricing)

**Label Studio Enterprise (HumanSignal)**
- Enterprise offers SSO with SAML or LDAP plus SCIM, and roles Owner/Admin/Manager/Reviewer/Annotator. Shared Workspaces (by team, department or product) and Activity Logs ("system of record that tracks every action") are Enterprise-only. — [HumanSignal Pricing](https://humansignal.com/pricing/)

**CVAT Online**
- SSO (annual Team plans only), RBAC, and audit logs (via API only) are on Team plans, not Free or Solo. Webhooks are metered per plan: 1 on Free, 10 on Solo, 30/50/100 on Team tiers. — [CVAT Cloud Pricing](https://www.cvat.ai/pricing/cloud)

**SuperAnnotate**
- Users are assigned a role on invite that scopes their actions in teams and projects. Cloud integrations are read-only (items stay in the customer's storage and are only displayed). An on-prem option stores data on the customer's own hardware. — [SuperAnnotate Security](https://www.superannotate.com/security-at-superannotate)

**Ultralytics Platform (formerly HUB)**
- Enterprise adds SSO/SAML, on-prem data and compute, and an Enterprise license instead of AGPL-3.0. Pro adds team collaboration for up to 5 members. — [Ultralytics Pricing](https://www.ultralytics.com/pricing)

### Inferences
- The industry-standard RBAC model has two levels. Workspace/org roles cover admin and billing. Project roles cover annotator, reviewer and manager. Custom roles are an enterprise upsell, as at Roboflow and Label Studio.
- "Data stays in your bucket" (BYO storage with signed URLs or IAM role assumption) is the cheapest strong isolation story. Encord, Labelbox, SuperAnnotate and V7 all offer it. For LabelDesk it is likely a should-have that is cheaper than VPC or on-prem.
- Scoped API keys plus publishable (inference-only) keys are a recurring pattern (Roboflow). A distinct publishable key type for edge and browser inference is worth copying.
- Audit-log retention (365 days at Roboflow) and SIEM export (OTLP) are concrete enterprise acceptance criteria.

### Gaps
- Scale AI (Scale Rapid/Nucleus) and CVAT Enterprise (self-hosted) features were not fetched. No verified data on their SSO, SCIM or audit features.
- No vendor documents per-tenant encryption keys (BYOK) for its multi-tenant SaaS. Encord mentions customer KMS only for VPC and on-prem.
- SCIM is confirmed only for Label Studio Enterprise. It is unverified for Roboflow, Encord, V7 and Labelbox.
- I found no public detail on how vendors isolate tenants inside a shared DB (row-level security vs. schema per tenant).
- Labelbox custom roles were not confirmed.

## 2. Pricing, billing models, quotas and metering

### Takeaway
CV SaaS pricing has converged on hybrid models: a low monthly base (or per-seat fee) plus a usage currency (credits/LBUs) that meters training, inference and auto-labeling, with free tiers capped by credits, storage or projects. Ultralytics publishes raw per-GPU-hour rates, while Roboflow abstracts GPU time into credits. Encord and V7 have no public prices.

### Cited Findings
- **Roboflow**
  - Free: $0 with 10 credits/month and unlimited admin seats (the page says this is enough for ~30 model trainings or 80,000 inferences).
  - Core: $39/mo with 10 credits, 20 projects and uncapped dataset size. Add-on packs run from +10 credits for $39 ($3.90/credit) to +490 for $1,399 ($2.86/credit). Extra prepaid credits start at $4 and on-demand credits cost $6.
  - Included credits reset monthly and do not roll over. Prepaid credits expire after 1 year.
  - Hosted inference rates: RF-DETR/YOLO Nano 0.000125 credits/image (8,000 images/credit), 0.1 credits per stream-hour. SAM 3 0.0005 credits/image (2,000/credit), 0.4 credits per stream-hour.
  - Enterprise: custom.
  - Source: [Roboflow Pricing](https://roboflow.com/pricing)
- **Ultralytics Platform**
  - Free: $0, with a $25 one-time credit (FAQ says $5, or $25 with a work email; the page contradicts itself), 100 GB storage, 100 models, 3 concurrent cloud trainings, 3 deployments, 1 member.
  - Pro: $29/seat/mo, including $30/seat/mo in credits, 500 GB, 10 concurrent trainings, up to 5 members, plus S3/GCS/Azure dataset connectors.
  - Enterprise: custom, with unlimited usage, SSO/SAML, HIPAA BAA and on-prem.
  - Cloud GPU rates per hour range from $0.24 (RTX 2000 Ada). Examples: L4 $0.39, RTX 4090 $0.69, A100 SXM $1.49, H100 SXM $3.29, B200 $5.89, B300 $7.39. Downgrades take effect at the next billing cycle.
  - Source: [Ultralytics Pricing](https://www.ultralytics.com/pricing)
- **CVAT Online**
  - Solo: $33/mo monthly or $23/mo yearly. Team: $33/user/mo or $23/user/mo yearly, for 2–50 seats.
  - Hard quotas by plan: Free has 1 project, 3 tasks, 1 GB storage and 100 AI calls/mo. Team Large has 100 projects, 2,500 tasks, 250 GB and 100,000 AI calls/mo.
  - The Free plan exports annotations only, without images.
  - Source: [CVAT Cloud Pricing](https://www.cvat.ai/pricing/cloud)
- **Label Studio**: Community is open source. Starter Cloud is $99/mo plus $49 per extra user, up to 12 users. Enterprise is custom. — [HumanSignal Pricing](https://humansignal.com/pricing/)
- **Labelbox**
  - The official pricing page returned HTTP 404 on 2026-10-31 (fetched [labelbox.com/pricing](https://labelbox.com/pricing)).
  - Aggregators report that the public pricing page and LBU calculator were retired on 2026-09-11 and Annotate LBU metering was redefined. — [usagepricing.com activity log](https://www.usagepricing.com/blueprint/activity/labelbox-2026-09-11-pricing-page-retired); [LBU metering redefined](https://www.usagepricing.com/blueprint/activity/labelbox-2026-09-11-annotate-lbu-metering-redefined)
  - Older reports put the free tier at about 500 LBUs/mo and paid use at about $0.10/LBU. These are aggregator figures that conflict with each other and are not verified. — [PricingSaaS Labelbox](https://pricingsaas.com/companies/labelbox); a contradicting $500/$3,500 tier claim appears at [CostBench](https://www.costbench.com/software/ai-data-labeling/labelbox/)
- **Encord**: no public dollar prices. Aggregators describe Starter/Team/Enterprise tiers and no permanent free plan (secondary sources only). — [PricingSaaS Encord](https://pricingsaas.com/companies/encord)
- **V7**: no public price list. One annual agreement is quoted within 48 hours, priced on platform + role-based users + document/page volume (this is the V7 Go product). — [V7 Pricing](https://www.v7labs.com/pricing)
- **Landing AI**
  - The live pricing page now covers only Agentic Document Extraction, not LandingLens: $1 = 100 credits, 1,000 free credits, Team from $250/mo for 25k–200k credits/mo.
  - VPC/on-prem is on Enterprise, ZDR on Team+, and HIPAA requires ZDR plus a BAA.
  - Source: [Landing AI Pricing](https://landing.ai/pricing)

### Inferences
- A practical LabelDesk billing design would be:
  1. A free tier capped by credits plus projects/storage.
  2. A low flat paid tier.
  3. Credit packs with volume discounts.
  4. Non-rollover monthly credits plus prepaid credits that expire after 12 months, which limits liability.
  5. A higher on-demand overage rate.

  All of these mirror Roboflow.
- Metering units to implement: GPU-seconds per GPU class for training (Ultralytics style), per-image inference by model size, per-stream-hour for video, AI-assist calls (CVAT counts them), storage GB, and projects/tasks counts.
- Hard caps on Free (CVAT exports annotations only on Free) are a common, cheap conversion lever.
- Per-GPU-hour list prices (L4 ~$0.39, RTX 4090 ~$0.69) give a reference markup ceiling for a Thai GPU-worker offering.

### Gaps
- Current LandingLens (CV) pricing was not found. The pricing page now covers document extraction only.
- No verified current Labelbox or Encord dollar pricing.
- No public information on how vendors technically enforce quotas (soft vs. hard limits, grace periods) beyond Roboflow's on-demand overage rate.

## 3. Security and compliance (SOC 2, ISO 27001, HIPAA, GDPR, Thailand PDPA, CCTV/faces, residency, deployment options)

### Takeaway
SOC 2 Type II is table stakes for every vendor reviewed. ISO 27001 and HIPAA BAAs differentiate and are often enterprise-gated. For Thailand, CCTV footage showing identifiable people is personal data under the PDPA. Biometric data is a sensitive category under Section 26 that generally needs explicit consent. PDPC sector guidance on CCTV and image analysis was still in draft and consultation in 2026.

### Cited Findings
**Certifications by vendor**
| Vendor | SOC 2 Type II | ISO 27001 | HIPAA | GDPR |
|---|---|---|---|---|
| Roboflow | Yes, all plans ([Pricing](https://roboflow.com/pricing); [Trust Center](https://security.roboflow.com/)) | Not stated | HIPAA + BAA as an Enterprise add-on | Not stated on these pages |
| Encord | Certified | Not mentioned | Compliant | Compliant |
| Labelbox | Yes | Only "informs" the program; no certificate found | HIPAA program | — |
| V7 Darwin | Yes | Certified | Yes (see note) | Yes (on V7 Go page) |
| SuperAnnotate | Yes (security, availability, confidentiality) | ISO/IEC 27001:2022 | Third-party claims only, unverified | — |
| Label Studio Enterprise | Yes | — | Yes, cloud or on-prem | — |
| Ultralytics Enterprise | Yes | Yes | HIPAA BAA for eligible customers | — |
| Landing AI | Yes | — | With ZDR + BAA | — |

- Encord: [Encord Security & Compliance](https://docs.encord.com/solutions-documentation/enterprise-ai/security-and-compliance)
- Labelbox: [Labelbox Security](https://labelbox.com/security)
- V7 Darwin: [V7 Darwin Security](https://www.v7darwin.com/security). The V7 terms say V7 "follows HIPAA guidelines" with yearly audits, which is softer than the security page's "fully HIPAA compliant" ([V7 Terms](https://www.v7darwin.com/terms)).
- SuperAnnotate: [SuperAnnotate Trust Center](https://www.superannotate.com/trust-center)
- Label Studio: [HumanSignal Pricing](https://humansignal.com/pricing/)
- Ultralytics: [Ultralytics Pricing](https://www.ultralytics.com/pricing)
- Landing AI: [Landing AI Pricing](https://landing.ai/pricing)

**Encryption and residency**
- Encord uses AES-256 at rest and TLS 1.2+ in transit, with the application on GCP. Customer data is deleted at contract end per agreed schedules, with no specific periods published. — [Encord Security & Compliance](https://docs.encord.com/solutions-documentation/enterprise-ai/security-and-compliance)
- Roboflow offers US or EU data sovereignty on Enterprise only. — [Roboflow Pricing](https://roboflow.com/pricing)
- V7 Darwin stores data in AWS S3 Ireland (EU). — [V7 Darwin Security](https://www.v7darwin.com/security)

**Deployment options advertised**
- Encord: BYO storage, VPC, on-prem/air-gapped. — [Encord](https://docs.encord.com/solutions-documentation/enterprise-ai/security-and-compliance)
- Roboflow: on-prem as a professional service, air-gapped as a Manufacturing add-on, and self-hosted Inference included on Core. — [Roboflow Pricing](https://roboflow.com/pricing)
- Labelbox: IAM delegated access. — [Labelbox Docs](https://docs.labelbox.com/docs/access-storage)
- SuperAnnotate: read-only cloud integration plus on-prem. — [SuperAnnotate Security](https://www.superannotate.com/security-at-superannotate)
- CVAT: Enterprise on-prem or private cloud. — [CVAT Pricing](https://www.cvat.ai/pricing/cloud)
- Label Studio: on-prem. — [HumanSignal](https://humansignal.com/pricing/)

**Thailand PDPA B.E. 2562**
- The PDPA lists biometric data as a sensitive category, and collecting it generally needs explicit consent. — [Hunton, PDPA enters into force](https://www.hunton.com/privacy-and-cybersecurity-law-blog/thailands-personal-data-protection-act-enters-into-force)
- Administrative fines reach THB 5 million. Civil and criminal liability also apply, and criminal penalties for certain sensitive-data breaches include up to 1 year in prison. — [KPMG Thailand Legal News Flash 14 (2022, older)](https://kpmg.com/th/en/home/insights/2022/06/legal-news-flash-issue-14.html)
- In 2026 the PDPC consulted on draft sector-specific PDPA guidelines, with a public hearing on 1–2 April 2026. The drafts are non-binding but expected to be persuasive. — [Tilleke & Gibbins](https://www.tilleke.com/insights/thailands-public-consultation-on-proposed-pdpa-guidelines-key-updates); [HLC, July 2026](https://hlc.com/en/publications/thailand-pdpc-consults-on-sectorspecific-pdpa-guidelines)
- What the drafts say about CCTV and biometrics. Source for all three: [HLC](https://hlc.com/en/publications/thailand-pdpc-consults-on-sectorspecific-pdpa-guidelines)
  - CCTV, including systems with image-analysis capabilities (real estate draft): clear notice of monitoring, restricted access to footage, defined retention periods, and security measures.
  - Facial recognition or fingerprint access control (energy draft): needs a Section 26 legal basis, otherwise explicit consent, and alternative authentication may be considered.
  - Biometric verification (IT/telecom draft): must be proportionate to risk.

**EU reference**
- EDPB Guidelines 3/2019 on processing of personal data through video devices, final version dated 30 Jan 2020 (older, but still the reference text). — [EDPB](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-32019-processing-personal-data-through-video_en)

### Inferences
- For LabelDesk customers uploading CCTV footage, LabelDesk is most likely a data processor under the PDPA. That implies:
  - a Data Processing Agreement template;
  - access restriction on footage (RBAC + audit);
  - configurable retention and auto-deletion per project;
  - deletion on contract end;
  - optional face blurring/anonymization before labeling.

  Face blurring would reduce the data to non-identifiable form and is a plausible differentiator.
- Using face recognition embeddings (vs. merely detecting "person") likely moves processing into Section 26 biometric territory. A product policy that limits the platform to detection/segmentation by default is the lower-risk option.
- Data residency in Thailand or a Thai/SEA region is a differentiator against Roboflow (US/EU only) and V7 (EU) for Thai government and enterprise buyers.
- SOC 2 Type II is a must-have to sell to enterprises eventually, but it is costly. Early on, publish a Trust page with controls (AES-256, TLS 1.2+, MFA, audit logs, pentest) as Roboflow's Trust Center does.

### Gaps
- I could not locate the text or status of any existing final PDPC guideline specific to CCTV (some practitioners reference earlier PDPC CCTV guidance). Check pdpc.or.th directly.
- Cross-border transfer rules (PDPA s.28–29 and the subordinate notifications) were not researched in this pass.
- The EDPB PDF contents (e.g. retention suggestions, Art. 9 threshold for video) were not extracted. Only the metadata was fetched.
- Whether Thai PDPA fines are per violation was not confirmed from a primary source.

## 4. MLOps: lineage, reproducibility, experiment tracking, registry, CI, drift monitoring, feedback loops

### Takeaway
Google and Microsoft maturity models both define progress as moving from manual, notebook-driven training to automated continuous training. Monitoring and drift then trigger retraining, backed by an ML metadata store (lineage), a model registry and CI/CD for pipelines. Sculley et al. (2015) supplies the rationale: hidden feedback loops, data dependencies and configuration debt dominate ML maintenance cost.

### Cited Findings
- **Sculley et al.**, "Hidden Technical Debt in Machine Learning Systems", NIPS 2015 (older, but foundational). It names ML-specific risk factors: boundary erosion, entanglement, hidden feedback loops, undeclared consumers, data dependencies, configuration issues, changes in the external world, and system-level anti-patterns. — [NeurIPS proceedings](https://papers.nips.cc/paper_files/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html)
- **Google Cloud MLOps levels** (page last updated 2024-08-28). — [Google Cloud Architecture](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
  - Level 0 is manual, notebook-driven, has no CI/CD and no active monitoring, and risks training-serving skew.
  - Level 1 adds continuous training: an orchestrated pipeline deployed to production, automated data and model validation, triggers, and metadata management.
  - Level 2 adds CI/CD for pipeline components, with unit tests, convergence/NaN checks and staged deploys.
  - Level 2 components: source control, test/build services, deployment services, model registry, feature store, ML metadata store and pipeline orchestrator.
  - The metadata store records component versions, timing, parameters, artifact locations and evaluation metrics, which supports lineage, reproducibility, rollback and debugging.
  - Continuous-training triggers: on demand, on schedule, new data, performance degradation, distribution shift.
- **Microsoft Azure MLOps Maturity Model** (updated 2026-06-03), five levels. — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model)
  - Level 0: No MLOps.
  - Level 1: DevOps but no MLOps.
  - Level 2: Automated training, with centralized tracking, managed environments and reproducible models.
  - Level 3: Automated model deployment, with A/B testing, full traceability from deployment back to data, and registries to promote artifacts across workspaces.
  - Level 4: Full MLOps, where drift/regression signals trigger automatic retraining and promotion is policy-based.
- **Rabanser, Günnemann & Lipton**, "Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift", NeurIPS 2019 (older). Across the shifts studied, two-sample testing on dimensionality-reduced representations from pre-trained classifiers (black-box shift detection) performed best. The paper also covers characterizing shift exemplars and malignancy. Reviewers noted it covers only natural shifts. — [NeurIPS 2019](https://proceedings.neurips.cc/paper/2019/hash/846c260d715e5b854ffad5f70a516c88-Abstract.html); [Reviews](https://proceedings.neurips.cc/paper/2019/file/846c260d715e5b854ffad5f70a516c88-Reviews.html)

### Inferences
- A minimal reproducibility record per training run for LabelDesk would be:
  - dataset version ID plus a content hash of images and labels;
  - split assignment;
  - augmentation/preprocess config;
  - model architecture and weights origin;
  - hyperparameters;
  - random seed;
  - code/container image digest and library versions;
  - GPU type.

  This maps directly to Google's "ML metadata store" fields.
- Mapped to the maturity ladders:
  - Must-have (Level 1/2): versioned datasets, tracked runs and a model registry.
  - Should-have (Level 3): promotion/deploy from the registry with traceability back to the dataset version.
  - Differentiator (Level 4): production drift monitoring that queues low-confidence or shifted frames for relabeling (active-learning feedback loop), then triggers retraining.
- For CV drift, the Rabanser result suggests a cheap implementation: embed production images with the deployed backbone and run a two-sample test (e.g. MMD/KS on embeddings) against the training-set embeddings.
- "Hidden feedback loops" (Sculley) are a real risk if model-assisted pre-labels are accepted without review and then used for retraining. Track label provenance (human vs. model vs. SAM-assisted) per annotation.

### Gaps
- Official docs for MLflow, W&B and ClearML integrations with each CV vendor (e.g. Ultralytics integrations, Roboflow model upload) were not fetched in this pass.
- No 2024–2026 survey paper on vision-specific production drift was retrieved. Only Rabanser 2019 is cited.
- Vendor model-registry and CI features (e.g. Roboflow versions, Encord Active) were not verified.

## 5. Observability, operations and developer experience

### Takeaway
Within the vendor docs fetched, developer-experience features appear mainly as plan-metered items: webhooks, cloud storage connectors, integrations, API key management via REST/CLI/MCP, and SIEM export. Internal operations tooling (job queues, worker heartbeats, status pages, admin consoles) is not publicly documented by these vendors and remains a gap.

### Cited Findings
- CVAT meters webhooks (1 to 100), cloud storage connections (1 to 30), Hugging Face/Roboflow integrations (1 to 30), internal AI calls per month, and "reports & analytics" (Solo and up) per plan. — [CVAT Cloud Pricing](https://www.cvat.ai/pricing/cloud)
- Roboflow manages API keys through REST, the `roboflow api-key` CLI and an MCP server, and exports audit logs to a SIEM via OTLP. — [Roboflow Manage API Keys](https://docs.roboflow.com/developer/rest-api/manage-api-keys); [Audit Logs & SIEM](https://docs.roboflow.com/roboflow/roboflow-hi/workspaces/audit-logs-and-siem-export)
- Roboflow sells an uptime SLA on Enterprise only. — [Roboflow Pricing](https://roboflow.com/pricing)
- Ultralytics Pro adds GCS, S3 and Azure Blob dataset connectors, export to 22 formats, and caps concurrent cloud trainings (3 on Free, 10 on Pro). — [Ultralytics Pricing](https://www.ultralytics.com/pricing)
- Labelbox gives delegated-access events with source IP, recorded in the customer's own cloud audit trail. — [Labelbox Docs](https://docs.labelbox.com/docs/access-storage)
- Google's MLOps guidance treats monitoring of live performance and data as a trigger source for pipeline runs. — [Google Cloud](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)

### Inferences
- Concurrency limits on cloud training (Ultralytics) are both a product quota and an operational backpressure mechanism. LabelDesk's GPU-worker queue should enforce per-tenant concurrency caps tied to plan.
- Must-have DX: REST API with docs, a Python SDK/CLI, API keys, cloud storage import, standard export formats (YOLO/COCO/VOC). Should-have: webhooks for job and export completion, scoped keys. Differentiator: an MCP server/agent integration (Roboflow already has one) and notebook templates.
- Ops must-haves for a GPU-worker architecture include a job queue with status, worker heartbeats and stale-job reaping, per-tenant usage metering tied to billing, and an internal admin console. The fetched vendor sources do not cite these, so treat them as engineering inference.

### Gaps
- No vendor docs on job queues, worker heartbeats, public status pages (e.g. status.roboflow.com) or admin consoles were fetched. This is the weakest-sourced area.
- Roboflow webhooks were not confirmed by the search.
- Python SDK and CLI feature parity across vendors was not compared from primary docs.
