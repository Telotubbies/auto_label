# Group 5 — Enterprise SaaS table stakes: identity, evidence, money, locale

Method: public pages only, fetched 2026-11-17 (~26 URLs; every card cites at least one). Code read on `feat/labeldesk-v2`, `fe8ef1a`: `oidc.py`, `totp.py`, `security.py`, `routers/{audit,privacy,workspaces,auth,admin,ops,connectors,rbac}.py`, `services/{retention,erasure,metering,alerts}.py`, `models/{identity,insights,project}.py`, `config.py`, `frontend/src/index.css`, `lib/theme.ts`, `lib/nav/**`, `features/{governance,settings}/`, `features/editor/{Editor,ObjectList}.tsx`, `package.json`, `scripts/*.mjs`. Nothing here is a certification claim about LabelDesk.

Parity dedupe note: three PARITY rows are stale on this branch — 7-F7.51 says alert channels are "webhook/email only" while `alerts.py` ships LINE, Slack and email; 7-F7.59 says no deletion path exists while 7-F7.7 defines owner-protected removal; 7-F7.35 is marked MISSING while `oidc.py` already validates bearer tokens. Treat the cards below, not those rows, as current.

---

## Identity and access

### G5.1 SCIM 2.0 directory provisioning (Okta, Entra ID, WorkOS)
- **What the user does:** an IT admin pastes our SCIM base URL and a one-time workspace token into their IdP's provisioning app, assigns people and groups there, and stops touching our member list.
- **Who uses it:** the customer's IT administrator at 50+ seats, on day one and at every joiner, mover and leaver.
- **Flow:** 1. Settings → Access → **Directory sync**; `[empty]` shows the base URL, "Generate token" and one line saying the token is shown once. 2. Save URL and token in the IdP app. 3. The IdP calls `GET /scim/v2/Users`; `[loading]` "checking connection", then "first sync found 84 people, 6 groups". 4. Group table: IdP group → workspace role, optional project scope; unmapped groups land on the workspace default role. 5. Each member row carries a "managed by directory" badge, last sync time, and a disabled role select reading "change this in your IdP". 6. `[error: 401 — the token was revoked, generate a new one]`, `[error: 429 — your IdP will retry in 5 minutes]`. 7. Deactivation marks the member inactive and routes their open work through the G5.4 offboarding policy instead of deleting their labels.
- **Why it is easy:** one screen owns the token, the group map and the sync log, so "why is this person still here" needs no second system; the badge stops the support loop where someone edits a role the next sync overwrites.
- **Products with it:** Okta SCIM concepts — https://developer.okta.com/docs/concepts/scim/ ; WorkOS Directory Sync — https://workos.com/docs/directory-sync ; Microsoft Entra app provisioning — https://learn.microsoft.com/en-us/entra/identity/app-provisioning/user-provisioning ; Linear's changelog shows live SCIM defects such as an invalid PATCH partially applying an email change — https://linear.app/changelog
- **Why it matters for LabelDesk:** a 300-labeler outsourced operation changes staff weekly and manual removal is the first thing a PDPA or ISO auditor tests. Parity's 7-F7.41 maps IdP attributes to roles at sign-in but cannot deactivate an account that never signs in again.
- **LabelDesk code evidence:** none found (searched `scim|saml|directory|provision` across `apps/backend/app`; the only identity code is `oidc.py:59-91` token verification plus manual invite/remove in `routers/workspaces.py:156-233`).
- **Suggested status:** MISSING — no endpoint, token, group map or sync state.
- **Suggested priority / size:** Must / M.

### G5.2 Enforced single sign-on, IdP-initiated entry and break-glass access
- **What the user does:** turns on "require SSO for these domains"; password and emailed links stop for those addresses, the IdP tile opens straight into the requested project, and one named break-glass account survives an IdP outage.
- **Who uses it:** the IT admin who owns the IdP, and the on-call engineer during an outage.
- **Flow:** 1. Sign-in shows one field, "work email"; the domain routes to that tenant's IdP with `[loading]` "checking your organisation" under two seconds. 2. A password attempt on an enforced domain returns `[error: your organisation requires single sign-on — continue with your company login]` plus a button, not a dead end. 3. IdP-initiated launch reads the relay state and lands on the deep link that was requested. 4. Settings → Access shows enforcement, verified domains, the break-glass account and certificate expiry. 5. `[error: the IdP signing certificate expires in 14 days]` with a metadata download.
- **Why it is easy:** the person never picks between three buttons — their domain decides — and break-glass is one visible row with an owner, so no shared admin password lives in a drawer.
- **Products with it:** WorkOS SSO, including IdP-initiated flow and relay-state handling — https://workos.com/docs/sso ; Entra Conditional Access, which can require a factor and block legacy authentication per app — https://learn.microsoft.com/en-us/entra/identity/conditional-access/overview
- **Why it matters for LabelDesk:** parity's 7-F7.35 builds the wizard; without enforcement SSO is decorative and a security review fails. IdP-initiated entry is also how Thai enterprise staff reach internal tools, from the intranet tile.
- **LabelDesk code evidence:** `oidc.py:35-36` reads issuer and client from env, `:59-91` verifies RS256 bearer tokens against a cached JWKS. No redirect, no domain table, no enforcement flag; `routers/auth.py:227-246` still issues and refreshes password sessions.
- **Suggested status:** MISSING — the token validator is real but no browser login exists, so there is nothing to enforce. Size is M on top of 7-F7.35's L.
- **Suggested priority / size:** Must / M.

### G5.3 Workspace sign-in policy: session life, step-up, MFA and network rules
- **What the user does:** sets idle and absolute session limits, requires a second factor, restricts access to office or VPN ranges, and asks for re-authentication before destructive acts.
- **Who uses it:** the admin configuring the workspace, and a labeler on a shared factory tablet who needs to know why they were signed out.
- **Flow:** 1. Settings → Security; each control carries a live consequence line ("shared tablets will be signed out after 30 minutes"). 2. Saving any control prompts for password or TOTP. 3. A blocked request lands on a 403 that names the rule and the caller's IP and offers "request access". 4. **Sessions** table per member: device label, last seen, revoke; a member's own view shows `[empty]` "no other sessions". 5. Key reveal, export, role change and workspace deletion prompt for the factor inside a live session. 6. `[error: this action needs a second factor, and none is enrolled]` links to enrolment.
- **Why it is easy:** one page answers the four identity questions a questionnaire asks, and the consequence line is the difference between a safe policy and locking out the night shift.
- **Products with it:** Auth0 session lifetime, with separate idle and absolute limits — https://auth0.com/docs/manage-users/sessions/configure-session-lifetime ; GitHub IP allow list, CIDR, covering UI, API and tokens, with a lockout warning — https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/managing-allowed-ip-addresses-for-your-organization ; Entra Conditional Access for trusted locations — https://learn.microsoft.com/en-us/entra/identity/conditional-access/overview
- **Why it matters for LabelDesk:** per-workspace MFA already beats most self-serve competitors; what an auditor asks next is how long a stolen session lives and whether a password alone can export the dataset.
- **LabelDesk code evidence:** PARTIAL. `deps.py:142,170` refuses requests when `ws.require_mfa` and the user has no factor; `models/identity.py:37` stores the flag; `routers/workspaces.py:47-70` toggles it and `:64` refuses to enable unless the admin enrolled; `routers/auth.py:420-434` lists and revokes the caller's sessions, `:135-137` revokes other devices after password or MFA change, `:440` returns login history. Missing: configurable lifetimes (`security.py:15-16` hardcodes 15-minute access, 30-day refresh), step-up prompts, device labels, admin revoke of another member's session, and any IP allowlist — the only one is the stream SSRF guard at `streams/allowlist.py:1-8`.
- **Suggested status:** PARTIAL — enforcement exists, policy and network scoping do not.
- **Suggested priority / size:** Should / M.

### G5.4 Ownership transfer and an offboarding sweep
- **What the user does:** hands the workspace to another admin before leaving, and clears everything the departing account still owns.
- **Who uses it:** the owner of a client workspace at an agency, or the IT lead when a champion changes job.
- **Flow:** 1. Settings → Members → owner row → **Transfer ownership** → pick a member → re-enter password or TOTP → recipient confirms by email. 2. A sweep panel lists dependencies on the old account: projects where they are the only manager, API keys they created, alert channels pointed at their LINE account, three review queues, saved dashboards. 3. Each row offers "reassign to…" or "revoke"; `[empty]` reads "nothing depends on this account". 4. Removing a member who still owns something is blocked with that list inline. 5. The transfer writes one audit row plus one per reassignment.
- **Why it is easy:** the checklist is generated from relations the database already has, and it appears at the moment of leaving rather than a month later when a camera stops alerting.
- **Products with it:** Okta SCIM deprovisioning, which revokes access and group membership on termination — https://developer.okta.com/docs/concepts/scim/ ; WorkOS Directory Sync deprovisioning — https://workos.com/docs/directory-sync
- **Why it matters for LabelDesk:** today a workspace cannot change hands at all, so a departing owner either keeps access forever or the workspace is abandoned. Both fail a PDPA access review, and agencies reselling to Thai clients hit this at every handover.
- **LabelDesk code evidence:** `routers/workspaces.py:160` and `:199` reject `role=owner` with "ownership transfers are not supported"; `:202-203` pins the owner as admin; `:217-218` blocks removing the owner; `:213-233` clears assignee and project roles for ordinary removals only.
- **Suggested status:** MISSING — the refusal is explicit in code, not an oversight.
- **Suggested priority / size:** Must / M.

---

## Audit and records

### G5.5 Tamper-evident audit trail with a retention floor
- **What the user does:** verifies that a date range of audit events has not been edited, and locks the log for the retention period the contract promises.
- **Who uses it:** the security lead during an incident, and the auditor sampling a quarter.
- **Flow:** 1. Audit → **Integrity** tab. 2. Pick a range → **Verify** → `[loading]` → "12,430 events, chain intact, 2 gaps (2026-03-02 04:00–04:12, planned maintenance)". 3. Download the digest beside the CSV, or hand the verifier one command. 4. **Retention lock** sets a minimum (one year or contract term) and warns it cannot be undone. 5. `[error: chain break at event 88,201 — stop deleting logs and open a ticket]`. 6. Every verification is itself logged.
- **Why it is easy:** the export already exists, so the proof travels with it; a security team that can verify locally does not need a SIEM integration first.
- **Products with it:** AWS CloudTrail log-file integrity validation — SHA-256 hashes, an hourly RSA-signed digest, each digest carrying the previous one, verifiable offline — https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html
- **Why it matters for LabelDesk:** parity's 7-F7.40 wants SIEM streaming, a much bigger build. A hash chain is the cheaper half and answers the only question that matters: could our team have changed this row.
- **LabelDesk code evidence:** PARTIAL. `routers/audit.py:30-55` queries by action, user, date and text; `:77-94` exports CSV or JSON and writes an `audit.export` row at `:88`; `:19` caps a pull at 50k. `models/insights.py:23-30` shows the row shape (id, created, user_id, action, target, meta) with no hash or previous-hash column; no verify route, no immutability, no retention floor.
- **Suggested status:** PARTIAL — export works, integrity does not.
- **Suggested priority / size:** Should / M.

### G5.6 Object-scoped activity history
- **What the user does:** opens one image, version or model and reads its own timeline, including who changed which label, with a way back.
- **Who uses it:** a reviewer disputing a label change, and a support engineer answering "why did this version lose 40 images".
- **Flow:** 1. Image detail → right rail → **History** (or `i`), newest first, grouped by day. 2. Each row names actor, time and field delta ("box 3: person → worker", "status: review → approved"). 3. Reviewers get **Restore this label set**, which creates a new revision rather than rewriting history. 4. Version header: "built from 1,204 images, exported 3 times, last served 2 h ago" with a link per event. 5. `[empty]` "no changes since upload"; `[loading]` five skeleton rows.
- **Why it is easy:** the audit table already records what happened; this is a scoped read plus a diff renderer, not a second logging system.
- **Products with it:** Google Docs version history and per-range or per-cell edit history, including restore and named versions — https://support.google.com/docs/answer/190843
- **Why it matters for LabelDesk:** review arguments are about one image, never the workspace. Our audit target is a display string, so the data is close but not addressable — the gap that keeps a spreadsheet running beside the tool.
- **LabelDesk code evidence:** PARTIAL. `routers/workspaces.py:286-311` filters the workspace log and `:304-307` does free-text matching over `Audit.target` and `meta`, so an image id sometimes finds events; `routers/audit.py:18` shows the flat CSV columns. Missing: an object-scoped route, field-level diff, restore action, and any guarantee that `target` holds a stable id.
- **Suggested status:** PARTIAL — searchable by text, not by object.
- **Suggested priority / size:** Should / M.

### G5.7 Retention policy builder with dry-run and legal hold
- **What the user does:** writes retention rules per data class, previews exactly what will be deleted, schedules the sweep, and freezes a project while a dispute is open.
- **Who uses it:** the DPO, and the project manager who owns the CCTV contract.
- **Flow:** 1. Settings → Privacy → **Policies** → add rule: scope (project, class, status), clock (captured, modified, exported), action (delete or anonymise). 2. **Preview** returns counts, twenty sample thumbnails and a storage figure, stating that nothing is deleted by preview. 3. Schedule daily at 02:00 Asia/Bangkok with a per-project run log. 4. **Legal hold** per project (reason, owner, review date) adds a red banner and makes every delete path answer `[error: this project is under legal hold until 2026-12-01]`. 5. `[error: 3 files were locked by another process — retried at 03:10]`. 6. `[empty]` "no rules yet — nothing is deleted automatically".
- **Why it is easy:** the deletion engine already handles locked files and partial failures; the missing layer is the customer writing the rule and seeing the blast radius first.
- **Products with it:** Microsoft Purview retention policies and labels — retain-then-delete, delete-only, event-based start, disposition review, longest-period-wins precedence — https://learn.microsoft.com/en-us/purview/retention
- **Why it matters for LabelDesk:** retention is a promise in our DPA, and it is only credible when the customer can preview and prove a run. Legal hold is what stops a scheduled job destroying evidence in a labour dispute.
- **LabelDesk code evidence:** PARTIAL. `services/retention.py:196-285` deletes frames, thumbnails, stream events, drift samples, orphan uploads, cached exports and snapshots, reports failures and keeps rows for retry; `:288-337` runs per project with an audit row; `:350-377` schedules one global run behind a 23-hour guard. `routers/privacy.py:122-127` stores days per project, `:153-168` queues a manual run, `:50-73` counts what is expiring. Missing: workspace default, per-class rules, preview with samples, schedule UI, legal hold (nothing overrides `retention_days`), retention for audit rows or backups.
- **Suggested status:** PARTIAL — deletion is solid, the policy surface is not.
- **Suggested priority / size:** Should / M.

---

## Workspace environments

### G5.8 Sandbox and production separation
- **What the user does:** tries a workflow on sample or copied data in a sandbox that cannot alert a real LINE group, spend real credits or deploy to a live camera, then promotes the result.
- **Who uses it:** the champion running a pilot, and the reviewer who signs off promotion.
- **Flow:** 1. Workspace switcher lists "ACME (production)" and "ACME (sandbox)" with distinct badges. 2. Sandbox pages carry a sticky strip: "Sandbox — alerts suppressed, no billing". 3. Keys minted there start `ld_test_` and production inference rejects them with `[error: this is a test key]`. 4. Deploy refuses `[error: sandbox models cannot be attached to a production camera]`. 5. **Promote** shows a diff (dataset versions, class list, metric deltas) and needs a second approver; `[empty]` before anything is promotable.
- **Why it is easy:** the mode is a workspace property, so every existing query inherits it and no screen needs a second branch to decide what is real.
- **Products with it:** Stripe sandboxes — separate objects, test keys, isolated settings, per-sandbox access levels, up to five per account — https://docs.stripe.com/test-mode
- **Why it matters for LabelDesk:** a Thai factory will not let a trial touch the running line, and the only workaround today is a second workspace, which duplicates billing and splits the model registry.
- **LabelDesk code evidence:** none found (searched `sandbox|environment|test_mode` across the backend — the only hits are one stream comment and the substring inside `latest_model`; `models/identity.py` has no environment or sandbox column, `apikeys.py:21,83` knows only the `ld_pub_` prefix and no test key, and `services/alerts.py` sends on any configured channel).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / M.

---

## Data protection and trust

### G5.9 DSAR workbench: find, export and erase one person
- **What the user does:** enters a name, staff id or one reference frame, sees every appearance, and produces either a redacted export or a signed erasure record.
- **Who uses it:** the customer's privacy officer answering a PDPA s.30–36 request, with our support engineer assisting.
- **Flow:** 1. Compliance → **Requests** → New (access, erasure or objection; subject identifiers; due date 30 days out with a countdown). 2. **Find** searches frames and embeddings, annotations naming the person, audit rows and alert deliveries; hits group by project with thumbnails and a match note. 3. **Export** builds a ZIP with a manifest and redaction log. 4. **Erase** runs a job showing per-store results (frames, thumbnails, snapshots, exports, drift, audit kept by law), then prints a certificate with hash, operator and time. 5. `[error: 4 frames could not be deleted — locked, retry scheduled]`. 6. Every step writes an audit row.
- **Why it is easy:** erasure already knows every byte prefix a project owns, so the work is a subject index and a case object with a clock, not new deletion logic.
- **Products with it:** GDPR Art 15 access and copy — https://gdpr-info.eu/art-15-gdpr/ ; Art 17 erasure — https://gdpr-info.eu/art-17-gdpr/ ; PDPC notification on erasure, destruction and de-identification (listing page; PDF not read) — https://www.pdpc.or.th/en/22864/
- **Why it matters for LabelDesk:** the controller carries the statutory clock but cannot search our object store. Without this, the honest answer to a data subject is "ask engineering", which is how deadlines are missed and the first PDPA complaint is lost.
- **LabelDesk code evidence:** PARTIAL. `services/erasure.py:85-112` enumerates every project path (project, snapshots, drift, batch inference, videos, models, engines, versions, streams), `:115-117` deletes them, `:120-151` handles single image, model and version; `retention.py:209-249` reuses the primitives. Missing: any subject identity store, request object with deadline, cross-project search, export bundle, redaction, certificate — `routers/privacy.py` has no request route.
- **Suggested status:** PARTIAL — byte-level erasure is real, person-level tooling is not.
- **Suggested priority / size:** Must / M.

### G5.10 Processing register: purpose, lawful basis, consent and transfers
- **What the user does:** keeps the DPA's facts as structured, exportable records instead of prose, and records every transfer outside Thailand with its basis.
- **Who uses it:** the DPO preparing for an audit, and the account manager answering a procurement questionnaire.
- **Flow:** 1. Compliance → **Processing register**; one row per project auto-filled from settings (camera count, retention, face blur, biometrics, legal basis) plus manual purpose and data-category fields. 2. **Add transfer** records destination, recipient, basis (adequacy, SCC, consent) and attaches the signed document. 3. A biometrics project without a basis is flagged, and the existing API refusal is explained inline. 4. Export CSV/PDF for the auditor; `[empty]` before the first project.
- **Why it is easy:** the DPA generator already assembles most of these facts per workspace; this turns the same data into rows a DPO can filter and a file they can hand over.
- **Products with it:** GDPR Art 30 records of processing, including recipients, third-country transfers and safeguards — https://gdpr-info.eu/art-30-gdpr/ ; PDPC's Section 29 cross-border notification (listing page; PDF not read) — https://www.pdpc.or.th/en/10547/
- **Why it matters for LabelDesk:** our DPA already asserts a transfer basis the product never captures, the kind of claim that fails a review on the second question.
- **LabelDesk code evidence:** PARTIAL. `routers/privacy.py:177-267` renders a per-workspace DPA with categories, retention, sub-processors, 72-hour breach, cross-border clause (`:248-252`) and deletion on termination (`:254-257`); `:129-134` stores a free-text `legal_basis` per project. Missing: structured register, consent records, transfer rows with documents, export.
- **Suggested status:** PARTIAL — prose, not records.
- **Suggested priority / size:** Should / M.

### G5.11 Sub-processor register with change notice and objection window
- **What the user does:** reads a public list of everyone who can touch their data, and is told before it changes.
- **Who uses it:** the customer's DPO or procurement lead, and our account manager publishing a change.
- **Flow:** 1. Public `/subprocessors` page, no login: name, purpose, data categories, region, safeguard, listed since. 2. **Subscribe to changes** → email confirmation → each change becomes a dated entry. 3. In-app, an admin sees "1 change needs acknowledgement by 12 Dec" with **Accept** and **Object**, where objecting records a case and notifies us. 4. `[empty]` before the first subscription, while the list stays readable.
- **Why it is easy:** a table plus a subscription, and it makes the existing DPA clause true instead of aspirational.
- **Products with it:** Atlassian Trust Center, which publishes compliance, security and resilience material as a public surface — https://www.atlassian.com/trust ; the duty to record recipients and third-country transfers — https://gdpr-info.eu/art-30-gdpr/
- **Why it matters for LabelDesk:** the DPA we generate already says a new sub-processor needs the controller's prior consent (`privacy.py:222-227`), and remote GPU workers are described there but listed nowhere. That is a promise we cannot keep.
- **LabelDesk code evidence:** none found (searched `subprocessor|sub-processor` across the backend; the only two hits are the DPA prose at `routers/privacy.py:225,227`).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / S.

### G5.12 Trust centre
- **What the user does:** finishes procurement from one page: DPA download, questionnaire answers, pen-test summary request, sub-processor list, and an honest statement of what is and is not certified.
- **Who uses it:** a Thai enterprise procurement officer who will not book a call to get a PDF.
- **Flow:** 1. Footer **Trust** → Certifications, Data protection, Security practices, Sub-processors, Reports. 2. Every claim carries a status word — "not certified", "in progress", "audited <date>" — and links to evidence; no bare logos. 3. **Request pen-test summary** asks company, work email and NDA acceptance, then creates a tracked request in our admin console. 4. **Download DPA** returns the workspace's filled agreement when signed in, a template otherwise. 5. `[empty]` for a claim without evidence reads "not yet available" rather than hiding the row.
- **Why it is easy:** the DPA renderer exists; the page is a public read of documents we should already own plus one form that opens a case.
- **Products with it:** Atlassian Trust Center (resilience, security, compliance, AI, plus a customer trust portal for questionnaires) — https://www.atlassian.com/trust ; the same vendor's published key-management model shows the depth buyers expect — https://support.atlassian.com/security-and-access-policies/docs/what-is-cmk-encryption/
- **Why it matters for LabelDesk:** parity files DPA, MSA and security review under "sales motion". For a Thai mid-market buyer that is a lost week, and the page forces us to stop writing claims we cannot evidence. LabelDesk holds no certification today and the page must say so.
- **LabelDesk code evidence:** PARTIAL. `routers/privacy.py:270-284` serves the DPA and `features/governance/Dpa.tsx` renders it; `lib/nav/workspace/footer.ts:4-10` has Activity, Settings and Admin only — no Trust entry, nothing serves certifications, questionnaire answers or a public page.
- **Suggested status:** PARTIAL — one document, not a trust surface.
- **Suggested priority / size:** Must / M.

### G5.13 Breach notification runbook with a 72-hour clock
- **What the user does:** opens an incident, counts affected subjects, drafts the controller notice and keeps the evidence in one file.
- **Who uses it:** the on-call engineer at 02:00, and the DPO who signs the notification.
- **Flow:** 1. Ops → **Incident** → New (severity, discovered at, systems, suspected cause); a 72:00 countdown starts with named owners. 2. **Scope** asks which workspaces, projects, cameras and window, then returns an approximate subject count with the query it ran. 3. **Draft notice** fills the four required items (nature and volume, contact point, likely consequences, measures) into editable text with a per-item checklist. 4. **Send** mails every affected workspace owner and records delivery. 5. The timeline appends every action; **Close** produces a PDF pack. 6. `[error: scope query timed out — narrow the window]`.
- **Why it is easy:** the audit log already answers "who touched what when", so the incident is a wrapper with a clock and a template, not a forensics tool.
- **Products with it:** GDPR Art 33 — 72 hours, a processor notifying the controller without undue delay, documented facts and effects — https://gdpr-info.eu/art-33-gdpr/ ; PDPC publishes a breach-report channel — https://www.pdpc.or.th/en/
- **Why it matters for LabelDesk:** our DPA promises notification within 72 hours (`privacy.py:245-246`), but the clock lives in someone's inbox and the affected-customer list is assembled by hand.
- **LabelDesk code evidence:** PARTIAL (promise only). `routers/privacy.py:243-246` is prose; there is no incident model, countdown, notification job or evidence pack, and `routers/ops.py` is drift and active learning, not operations.
- **Suggested status:** PARTIAL.
- **Suggested priority / size:** Should / M.

### G5.14 Pinned data region with a residency receipt
- **What the user does:** sees where the workspace's data actually lives, downloads a receipt listing which stores are in-region and which are not, and requests a move with a downtime estimate.
- **Who uses it:** the customer's security lead, and our operator running the migration.
- **Flow:** 1. Settings → Privacy → **Region**: current region read-only, "pinned at creation". 2. **Request move** shows downtime, out-of-scope data and requires typing the region name. 3. **Residency receipt** lists object store, database, backups, model artefacts, logs and audit, each marked "in TH" or "outside TH" with the reason. 4. `[error: this workspace has data in two regions — complete the migration before a receipt can be issued]`.
- **Why it is easy:** the receipt is generated from configuration we control, so it cannot drift from reality the way a marketing page does.
- **Products with it:** Atlassian data residency — pinning per app, supported locations including Singapore, an explicit list of what cannot be pinned such as audit logs and user account data, and downtime during a move — https://support.atlassian.com/security-and-access-policies/docs/understand-data-residency/
- **Why it matters for LabelDesk:** PDPA s.28–29 makes the transfer the controller's problem, and "we selected Thailand" while bytes sit in Singapore is worse than no control. The honest out-of-scope list is what makes the receipt worth anything.
- **LabelDesk code evidence:** PARTIAL. `routers/privacy.py:14` maps th/sg/us labels; `:97-106` writes `data_region` and audits the change; `:185` prints it into the DPA; `admin.py:50` shows it to the operator. Nothing pins storage — `config.DATA_DIR` is a local path — and any admin can change the label at any time.
- **Suggested status:** PARTIAL — a label, not a location.
- **Suggested priority / size:** Must / L.

### G5.15 Customer-owned bucket and customer-managed keys
- **What the user does:** points us at their S3-compatible bucket and their KMS key; images, models and exports are written there, and disabling the key stops our access.
- **Who uses it:** a bank or hospital security team that will not sign while data sits on our disk.
- **Flow:** 1. Settings → Storage → **Connect bucket** (endpoint, bucket, region, prefix, credential or role). 2. **Test write** creates and deletes a probe object and reports latency. 3. **Use as primary store** warns that existing data must migrate and shows per-project progress. 4. The key section takes the ARN and region, then shows "last successful decrypt" and revoke instructions. 5. `[error: bucket policy denies PutObject on prefix/acme/]`, `[error: key disabled — exports paused]`.
- **Why it is easy:** the connector already speaks S3, GCS and Azure; the new part is write access, a primary-store switch, and a key reference the storage layer uses.
- **Products with it:** Atlassian customer-managed keys — customer AWS KMS keys, revoking access suspends access to the apps, CloudTrail visibility, encryption context bound to the ciphertext — https://support.atlassian.com/security-and-access-policies/docs/what-is-cmk-encryption/
- **Why it matters for LabelDesk:** it turns a residency objection into a configuration step, and it is the only credible answer for a customer whose policy forbids vendor-side storage.
- **LabelDesk code evidence:** MISSING for write or primary storage. `routers/connectors.py:1-4` states the connector is read-only import from S3, GCS and Azure with no write, move or delete endpoint; `config.DATA_DIR` is the only store; `secretbox` encrypts our credentials, not customer keys.
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / L.

---

## Money

### G5.16 Thai invoiced billing: PromptPay, bank transfer, VAT tax invoice, PO and dunning
- **What the user does:** requests an invoice in baht with our tax id, pays by PromptPay QR or bank transfer against a PO, and downloads a tax invoice their accountant accepts.
- **Who uses it:** the customer's finance team, not the engineer who signed up.
- **Flow:** 1. Plan & Billing → **Request invoice**: company name, tax id, address, PO number, billing email, withholding note. 2. The PDF carries the elements Thai law requires, with 7% VAT as its own line. 3. **Pay** shows a PromptPay QR for the exact amount plus bank details with a unique reference; the invoice stays "awaiting payment" until the transfer matches. 4. Reminders at 7, 14 and 30 days, then the configured end state (pause new jobs, read-only, or cancel) with an in-app banner and an email. 5. Receipts and credit notes download from the same row. 6. `[error: the PromptPay QR expired — regenerate]`.
- **Why it is easy:** one invoice object feeds the PDF, the QR, the reminder clock and the credit note, so finance never reconciles two systems.
- **Products with it:** Revenue Department VAT — 7% general rate and the mandatory invoice elements (the words "tax invoice", issuer name/address/tax id, buyer name/address, serial numbers, description/value/quantity, VAT amount, issue date) — https://www.rd.go.th/english/6043.html ; Stripe PromptPay — THB only, QR scanned in a bank app, invoice collection method only, no saved mandate for recurring charges — https://docs.stripe.com/payments/promptpay ; Stripe Invoicing — PDF or link, tax support, bank-payment reconciliation — https://docs.stripe.com/invoicing ; Stripe Smart Retries — retry windows, hard declines that cannot retry, end states of unpaid, cancelled or paused — https://docs.stripe.com/billing/revenue-recovery/smart-retries
- **Why it matters for LabelDesk:** the most localised blocker in the list. Card-only USD billing excludes Thai companies that pay by transfer and need a tax invoice to expense us, and because PromptPay has no reusable mandate the design must be invoice-first, not subscription-first.
- **LabelDesk code evidence:** MISSING. `config.py:88-97` defines plans and quotas with no price, currency or tax; `features/settings/Settings.tsx:973-975` tells the user to contact the operator (matching parity 7-F7.12); no invoice, tax-id or payment model exists.
- **Suggested status:** MISSING.
- **Suggested priority / size:** Must / M.

### G5.17 Budget guardrails: per-project budget, pre-flight estimate and pause
- **What the user does:** caps one project's monthly spend, sees the cost of a training run before clicking, and knows who can raise the cap when it is hit.
- **Who uses it:** a team lead on one production line, and the workspace admin who owns the contract.
- **Flow:** 1. Project → Settings → **Budget**: monthly credits, alerts at 50/80/100%, recipients. 2. The Train button shows "≈1,850 credits, 42 min" before the click, from image count and epochs. 3. Starting with 900 left → `[error: needs 1,850, 900 remaining — raise this project's budget or wait for the cycle]` plus **Request more**, which mails the admin with project and amount. 4. Usage → **Budgets** lists each project as a bar with burn rate and "projected to exceed on the 22nd". 5. Optional alert to the existing LINE or Slack channel.
- **Why it is easy:** usage is already metered per project, so a budget is a comparison and one alert rule, not a new accounting path.
- **Products with it:** Stripe usage monitoring with threshold alerts — https://docs.stripe.com/billing/subscriptions/usage-based ; Linear's changelog describes a usage explorer by team, feature and user plus spend limits at workspace and user level that pause usage when reached — https://linear.app/changelog
- **Why it matters for LabelDesk:** a Thai factory runs several lines under one contract; a single workspace cap lets one noisy project starve the others, and the person who hits the wall is never the person who can raise it.
- **LabelDesk code evidence:** PARTIAL. `services/metering.py:91-97` resolves a per-workspace quota with overrides, `:100-106` raises 402 naming the plan, `:109-113` exposes remaining units for long jobs, `:116-127` and `:130-148` feed the usage page; `routers/workspaces.py:119-132` returns meters. Missing: project budget, pre-flight estimate on train/deploy/autolabel, 80% notice (parity 7-F7.21), requester-to-approver handoff, pause semantics.
- **Suggested status:** PARTIAL.
- **Suggested priority / size:** Should / M.

---

## Operations, support and help

### G5.18 Public status page with incident history and postmortems
- **What the user does:** checks one URL before filing a ticket, subscribes to updates, and reads what went wrong afterwards.
- **Who uses it:** the customer's operations lead, and our on-call engineer posting updates.
- **Flow:** 1. Public status URL, no login: overall state, then API, annotation, training queue, stream ingest, inference and billing. 2. An open incident shows impact, the four lifecycle states (investigating, identified, monitoring, resolved) and timestamped updates. 3. **Subscribe** by email or LINE. 4. Ninety-day uptime bars per component; the incident page carries the postmortem once published. 5. `[empty]` "no incidents in the last 90 days"; `[loading]` renders skeletons so the page never looks down because it is slow.
- **Why it is easy:** `admin.py` already computes the six components; publishing them is a read-only route plus an incident table, and it removes a whole class of "is it just me" tickets.
- **Products with it:** Atlassian Statuspage — public or private page, subscribers, four incident statuses, component statuses, history after 14 days, uptime metrics — https://support.atlassian.com/statuspage/docs/what-is-statuspage/ ; postmortems written after resolve with autosaved drafts — https://support.atlassian.com/statuspage/docs/create-a-postmortem/
- **Why it matters for LabelDesk:** we cannot promise 99.9% in a contract while the only status signal is a super-admin JSON endpoint. The page is also the cheapest evidence that an incident happened, which G5.19 needs.
- **LabelDesk code evidence:** PARTIAL. `routers/admin.py:144-192` builds api, database, worker, gpu, vllm and queue components with operational/degraded states and serves them at `/api/admin/status` behind `require_superadmin`. No public route, incident model, subscribers, history or postmortem.
- **Suggested status:** PARTIAL — internal health only.
- **Suggested priority / size:** Should / M.

### G5.19 SLA with measured uptime and a self-serve credit claim
- **What the user does:** reads the month's measured uptime, and claims the contractual credit in the product when it misses.
- **Who uses it:** the customer's finance or vendor manager at quarter end.
- **Flow:** 1. Trust → **SLA**: current month, formula, exclusions, credit table. 2. If the month misses, the billing page shows "November: 99.42% — you may claim 10%". 3. **Claim** pre-fills incident ids and window, asks for the invoice number, and issues a credit note on approval. 4. `[error: the claim window closed — claims must be filed within one billing cycle]`. 5. Every claim appears in the audit log with its approver.
- **Why it is easy:** uptime comes from the same probes that feed G5.18, and the credit note is the object G5.16 already needs.
- **Products with it:** AWS Compute SLA — tiered credits by measured uptime, a claim naming dates, times, region and resource ids with supporting logs, a deadline of two billing cycles, credit applied to future invoices — https://aws.amazon.com/compute/sla/
- **Why it matters for LabelDesk:** an SLA number without measurement is marketing, and a claim process run through email is a dispute. This is where our own incident record pays for itself.
- **LabelDesk code evidence:** MISSING. No uptime samples, SLA object or credit note; `admin.py:184-192` returns instantaneous component states with no history.
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / M.

### G5.20 In-product help: what's new, docs search and feedback
- **What the user does:** opens one panel for the changelog since their last visit, searchable docs, the keyboard map, and a feedback box that attaches the current screen.
- **Who uses it:** a labeler mid-task, and an admin after a release.
- **Flow:** 1. `?` or the header **Help** opens a three-tab panel. 2. **What's new** lists dated entries with a seen marker and deep links into the exact setting. 3. **Docs** returns five results and opens a side panel without losing the canvas. 4. **Something is wrong** captures route, workspace, the last twenty console lines and a screenshot, then returns a ticket id. 5. `[empty]` "no updates since you joined"; `[error: feedback could not be sent — details copied to clipboard]`.
- **Why it is easy:** the app already knows the route and workspace, so a useful bug report is one button instead of a paragraph, and the changelog is a static list with links.
- **Products with it:** Linear's changelog — dated entries, fixed/improved grouping, deep links into settings, in-app command menu — https://linear.app/changelog ; the GitHub command palette — one shortcut, context-scoped navigation, `?` for help — https://docs.github.com/en/get-started/using-github/github-command-palette
- **Why it matters for LabelDesk:** every support email answered by hand is a documentation gap we keep paying for. WCAG 2.2 also requires help to sit in the same relative place on every page, which this panel gives us for free.
- **LabelDesk code evidence:** none found (searched `help|docs|changelog|whats|feedback|support` across `src/lib/nav` and `src/features/settings`; no entry exists, and the only "feedback" is per-annotation suspect feedback in `models/project.py:147`, unrelated).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / S.

### G5.21 Guided onboarding and admin adoption analytics
- **What the user does:** follows a five-step path that ends with a working model, and later sees which teams actually use the product.
- **Who uses it:** the champion running a pilot, and the admin preparing a renewal conversation.
- **Flow:** 1. First sign-in offers three intents (find defects, count people, read plates); each creates a project with a sample image set and a suggested model. 2. The checklist advances only on real actions — upload 20, label 5, train, deploy — and can be dismissed and reopened from Help. 3. Admin → **Adoption** shows weekly active labelers, images per labeler, median review time, unused features, and "3 invited members never signed in" with **Resend**. 4. `[empty]` before seven days: "not enough activity yet".
- **Why it is easy:** it reuses existing project creation, usage tables and invite resend; the checklist is one row per workspace.
- **Products with it:** Linear's changelog ships onboarding validation, a usage explorer and workspace administration as one adoption story — https://linear.app/changelog ; WCAG 2.2's redundant-entry and consistent-help criteria set the floor for the same screens — https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- **Why it matters for LabelDesk:** Thai factory teams are onboarded by one champion, not by our docs. A checklist plus "who never logged in" is what turns a 30-day pilot into a renewal, and both are cheap on tables we have.
- **LabelDesk code evidence:** PARTIAL. `features/settings/Settings.tsx:1102-1118` renders the first-run card (parity 7-F7.57), `:973-1000` renders plan meters, `routers/workspaces.py:119-132` returns 30-day activity counts. Missing: checklist or goal state, sample dataset, per-member activation view, "never signed in" list.
- **Suggested status:** PARTIAL.
- **Suggested priority / size:** Could / M.

---

## Locale and accessibility

### G5.22 Thai locale end to end
- **What the user does:** switches the interface to Thai and the product follows: menus, buttons, validation, empty states, Buddhist Era dates, Thai line breaking that does not stretch spaces, and exports whose headers match the UI.
- **Who uses it:** a labeler on a factory floor who does not read English, and the admin who sets the workspace default.
- **Flow:** 1. Account → **Language** (ไทย / English, default from browser); the page re-renders without losing the open project. 2. Dates read 17 พ.ย. 2569, with a per-workspace override so an export to a Japanese parent stays Gregorian. 3. Long Thai class names wrap at phrase boundaries and keep their spacing, never mid-syllable. 4. CSV headers and the audit export follow the locale while ids and enums stay stable. 5. `[error: this report has no Thai translation yet — showing English]` rather than a blank string. 6. `[loading]` keeps the Thai face to avoid a layout jump.
- **Why it is easy:** the typography groundwork is already in the stylesheet, so the work is strings and two formatters, not a redesign.
- **Products with it:** W3C Thai script resources — spaces separate phrases rather than words, no conjuncts, syllable boundaries hard to detect algorithmically, native digits in common use, with sections on line breaking and data formats — https://www.w3.org/TR/thai-lreq/ ; WCAG 2.2 carries notes for different languages — https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- **Why it matters for LabelDesk:** the first thing a Thai buyer tests, and we are half-built: the Thai face, line rules and Buddhist calendar already ship, but every string is English. Finishing it is the highest-credibility localisation work available.
- **LabelDesk code evidence:** PARTIAL. `src/index.css:3-4` declares Anuphan and Noto Sans Thai, `:43` puts them in the UI stack, `:92` sets `:lang(th)` line-height, word-break and overflow-wrap; `lib/theme.ts:131-136` selects `th-TH` plus the Buddhist calendar; `Settings.tsx:609-610` exposes the era toggle. No catalogue, no switcher, no translated string (searched `i18n|useTranslation|locale|th-TH|lang=|Intl.|Buddhist|thai` — thirteen hits, all formatting or font, none a translation).
- **Suggested status:** PARTIAL — typography and dates, no language.
- **Suggested priority / size:** Must / L.

### G5.23 Locale infrastructure and right-to-left readiness
- **What the user does:** nothing directly; adding a language becomes a translation file, and a right-to-left customer gets a mirrored layout instead of a broken one.
- **Who uses it:** the engineer adding the third locale, and the reviewer checking direction-sensitive layout.
- **Flow:** 1. Add keys to `en.json`; CI fails when `th.json` lacks one. 2. A pseudo-locale build lengthens strings by 30% and flips direction, so overflow and unmirrored icons surface in review instead of in a customer screenshot. 3. The language menu lists only locales above 95% coverage, marking the rest beta. 4. `[error: missing translation for audit.export]` appears in dev only.
- **Why it is easy:** a provider, one catalogue and one lint rule — strictly cheaper before the next ten screens than after.
- **Products with it:** W3C Thai resources, which call for an explicit direction and data-format check per script — https://www.w3.org/TR/thai-lreq/ ; WCAG 2.2 internationalization notes — https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- **Why it matters for LabelDesk:** the RTL flip is the cheapest test for hardcoded left/right and icon direction, and the same catalogue makes G5.22 a data change instead of a rewrite.
- **LabelDesk code evidence:** none found (searched `i18n|locale|messages|translations|dir=` across `apps/frontend/src`; no provider or catalogue directory exists, every string is inline JSX).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / M.

### G5.24 WCAG 2.2 AA with an automated gate
- **What the user does:** labels and reviews with a keyboard or screen reader, including adjusting a box without dragging, and CI refuses a change that breaks contrast or focus.
- **Who uses it:** a labeler with a motor impairment, an older reviewer, and the engineer who would otherwise ship a regression.
- **Flow:** 1. Tab reaches the canvas; arrow keys nudge the selected box, the object list supports arrow navigation, Enter commits and Esc cancels. 2. Focus is never hidden behind the sticky toolbar or the right rail, and a skip link jumps to the canvas. 3. Every icon button has a name and a target of at least 24×24. 4. The review queue announces "3 of 12, image 4471, 2 boxes" on navigation. 5. `npx playwright test a11y` runs axe across twelve routes and fails on serious or critical findings. 6. The trust page carries an accessibility statement listing known gaps.
- **Why it is easy:** the editor already exposes nudge buttons and a shortcut overlay, and axe is already a dependency, so this is wiring plus the gate.
- **Products with it:** W3C's summary of WCAG 2.2's nine new criteria — focus not obscured, a single-pointer alternative for dragging, 24×24 minimum targets, consistent help, redundant entry, accessible authentication — https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- **Why it matters for LabelDesk:** the core interaction is dragging boxes on an image, which 2.5.7 targets directly; keyboard nudging exists but is not a full alternative, and without a gate the next editor change can silently remove it.
- **LabelDesk code evidence:** PARTIAL. `features/editor/Editor.tsx:204-206` renders named nudge buttons, `:777-791` implements global keys (`/` search, arrows, Enter, Esc, Backspace delete, `?`), `:785` toggles the shortcut overlay; `features/editor/ObjectList.tsx:59-60` supports arrow navigation; `src/index.css:105` sets a focus-visible outline; `package.json:31` depends on `@axe-core/playwright`, with ad-hoc runs in `scripts/landing-shot.mjs:31-32` and `scripts/ocr-shots.mjs:4`, and `scripts/contrast-audit.mjs:2` covering axe's contrast gaps. Missing: a CI gate, axe over the editor and review flows, keyboard resize (nudge only), an accessibility statement.
- **Suggested status:** PARTIAL — good raw material, no enforcement.
- **Suggested priority / size:** Should / M.

---

## Already covered by PARITY.md (no card here)

- **7-F7.35** self-serve SSO with DNS proof — owns the connection wizard; G5.2 adds enforcement, IdP-initiated entry and break-glass.
- **7-F7.41** directory-group sync and workspace gating — maps attributes at sign-in; G5.1 is the push API with deactivation, which that mechanism cannot do.
- **7-F7.38 / 7-F7.39** audit table, filters and category coverage — G5.5 and G5.6 add integrity and object scope, not another log screen.
- **7-F7.40** SIEM export — still a gap, but an integration task rather than a table-stakes control; the hash chain is the cheaper first step.
- **7-F7.43** 30-day trash — G5.7 is policy and hold, not restore.
- **7-F7.20 / 7-F7.21** flex billing, spend cap and 80% notices — G5.17 is project scope, estimation and the approval handoff.
- **7-F7.12 / 7-F7.22 / 7-F7.23** plan home, cancellation, billing portal — G5.16 is the Thai payment and tax layer underneath them.
- **7-F7.44** private-data licensing opt-out — separate from consent recording (G5.10).
- **7-F7.45** contractual and regional controls — narrowed to G5.12 (trust surface) and G5.14 (real pinning), because that row lumps them together.
- **7-F7.51** notification sinks — LINE, Slack and email already ship (`services/alerts.py:1-10`), so the row is stale; no new card.
- **7-F7.57 / 7-F7.59** create and delete a workspace — G5.4 is transfer, not creation or deletion.

## Title-only / unverified

- PDPC's Section 28 and Section 29 cross-border notifications and the erasure notification are PDFs; only their listing pages were fetched, so no clause is quoted.
- No public page states what LabelDesk holds; nothing here should be read as a certification claim. Google Vault's hold page redirected to a generic index, so legal hold is described from Purview's retention model only.
- Sub-processor list pages for large vendors were not opened; the obligation is cited from GDPR Art 30, the practice from the Atlassian trust page.
- PromptPay behaviour is taken from Stripe's documentation; Thai banks' own direct-debit products were not researched, so "no recurring" may be too strong outside Stripe.
- Whether Anuphan renders correct Thai line breaks inside the canvas and label list is untested; the CSS rules exist, but no visual test was run.
- SSO and SCIM setup screens in Okta, Entra and WorkOS were read as documentation, not operated, so error copy and edge cases there are inferred.
- The generated DPA text has not been legally reviewed; several cards assume its clauses are the contract of record.
- Statuspage's SLA reporting and Atlassian's credit process were not opened; the credit tiers come from the AWS Compute SLA.

## Status and priority summary

- **MISSING (10):** G5.1, G5.2, G5.4, G5.8, G5.11, G5.15, G5.16, G5.19, G5.20, G5.23.
- **PARTIAL (14):** G5.3, G5.5, G5.6, G5.7, G5.9, G5.10, G5.12, G5.13, G5.14, G5.17, G5.18, G5.21, G5.22, G5.24.
- **HAVE (0).** Nothing in this group works end to end today.
- **Must (8):** G5.1, G5.2, G5.4, G5.9, G5.12, G5.14, G5.16, G5.22. **Should (12):** G5.3, G5.5, G5.6, G5.7, G5.10, G5.11, G5.13, G5.17, G5.18, G5.19, G5.20, G5.24. **Could (4):** G5.8, G5.15, G5.21, G5.23.
- **Size:** S — G5.11, G5.20. L — G5.14, G5.15, G5.22. M — the other nineteen.
