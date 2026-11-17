# Beyond Roboflow — what else LabelDesk should have

Owner directive 2026-11-17: parity is already planned in
`docs/research/roboflow-parity/PARITY.md` (334 rows). This document is the layer above it:
the capabilities a buyer meets after they stop comparing us to Roboflow and start comparing
us to CVAT, Encord, Labelbox, Ultralytics, NVIDIA, Edge Impulse — or to the factory down the
road that bought a Cognex.

Read at `feat/labeldesk-v2`, `c9e907d` (2026-11-17). `PARITY.md` was audited at `fe8ef1a`,
two merges earlier; where a parity row is now stale it is marked in the notes, not edited.

Evidence base: the six group files in this folder, one card per feature with the full flow,
states, sources and code evidence.

| File | Group | Cards written |
| --- | --- | --- |
| `01-annotation-platforms.md` | CVAT, Label Studio, Labelbox, SuperAnnotate, V7, Encord, Dataloop, Kili | 17 |
| `02-training-mlops.md` | Ultralytics, Landing AI, HF AutoTrain, W&B, ClearML, FiftyOne | 17 |
| `03-edge-industrial.md` | NVIDIA, Edge Impulse, Viso, Cognex/Keyence, Axis/Milestone | 18 |
| `04-vlm-foundation.md` | SAM 3 family, open-vocabulary, VLM QA, agentic, synthetic, active learning | 18 |
| `05-enterprise-table-stakes.md` | SSO/SCIM, audit, residency, BYO storage, PDPA, billing, support, i18n | 24 |
| `06-repo-research-thai-market.md` | this repo's `reports/` + `research/notes/`, Thai verticals | 22 |

**116 cards written → 101 features survive dedupe.** 2 HAVE · 58 PARTIAL · 41 MISSING.
14 Must · 61 Should · 26 Could. 14 S · 67 M · 20 L.

Status and priority rules are `PARITY.md`'s. One calibration applies here: **Must** means it
blocks a trial of a named segment or creates legal exposure — not "a competitor has it".
PARITY.md already marks 37 of its 334 rows Must; that number is a wish list, not a plan, and
this document does not add to it.

---

## 1. What dedupe removed

Thirteen cards were dropped or folded, and two more were moved to §4 as deliberate non-goals.
Each was either already owned by a parity row or a second name for another card in this set.
Deleting them is the honest part of this document.

### Already owned by PARITY.md

| Card | Why it is not new | Parity row |
| --- | --- | --- |
| G1.8 instructions attached to a job | The parity row already names the missing instructions field and the missing notification as its gap | 3-F3.45 |
| G1.7 region-anchored comments | Same: the parity row's stated gap is exactly "no pixel anchor and no resolve state" | 3-F3.48 |
| G5.1 SCIM 2.0 provisioning | "Directory-group sync and workspace gating" is the same capability; SCIM is its implementation choice | 7-F7.41 |
| G5.2 enforced SSO, IdP-initiated, break-glass | "Self-serve SSO with DNS proof" already owns the whole login; break-glass is a clause inside it | 7-F7.35 |
| G5.14 pinned data region | "Contractual and regional controls" names the missing region choice and trust page | 7-F7.45 |

### Merged into another card here

| Absorbed | Into | Reason |
| --- | --- | --- |
| G4.2 prompt library becomes the class schema | G4.1 | One mechanism: prompts are stored per class and can seed classes. Splitting them produced two half-features. |
| G6.3 Modbus / OPC-UA / MQTT reject signal | G3.11 | Same feature, found twice from two directions. |
| G6.9 PPE pack | G6.6 | Same mechanism (an installable vertical pack); two instances, one build. |
| G6.17 camera readiness survey | G3.16 | Two camera-quality cards, one lifecycle. |
| G6.18 Thai tax documents | G5.16 | Billing cannot ship without its documents; one card. |
| G6.19 Buddhist-era dates in documents | G5.22 | Report rendering is part of the locale, not a separate feature. |
| G5.23 locale infrastructure / RTL | G5.22 | RTL is not a market we sell to; the framework requirement rides with Thai. |
| G6.21 PDPA pack | G5.9 + G5.10 | The pack was a bundle of the DSAR workbench and the processing register, both already cards. |

Two cards stay as deliberate near-neighbours, with the distinction written into the row:
G4.18 (a structural question answered as a number and a filter) against parity 2-F2.28
(similarity retrieval over unlabelled images), and G3.14 (calibration plus a tolerance verdict)
against parity 3-F3.5 (a measuring guide in the editor).

---

## 2. The matrix

Evidence is one or two anchors; the card in the group file holds the rest, including the
click-by-click flow and the URLs. `none found` means the group searched the named patterns
across `apps/backend/app` and `apps/frontend/src`.

### A. Labeling operations and quality — `01-annotation-platforms.md`

13 features · 1 HAVE · 7 PARTIAL · 5 MISSING. This is the group where we are strongest: the
334-row parity matrix contains no consensus, honeypot or task-queue row, so these capabilties
are ours to lose rather than to catch up on.

| ID | Feature | Status | Evidence | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G1.1 | Duplicate passes merged by majority, with a reviewer override | HAVE | `routers/labeling.py:42-78`, `services/labeling_ops.py:270-326`, `features/project/qa/Consensus.tsx`. Behind flag `task_23`. No winner override, no sampled coverage | Should | S |
| G1.2 | Answer-key rows seeded into the live queue at a rate | PARTIAL | `services/labeling_ops.py:204-213,454-479`; `models/insights.py:104-112` holds `UniqueConstraint(honeypot_id,user_id)`, so a second look overwrites the first score. No rate, pool or seed | Should | M |
| G1.3 | Score at submit, with capped retries and hints | MISSING | Only write is `labeling_ops.py:204-213`; `none found (attempt, hint, retry)` | Could | M |
| G1.4 | Quality dashboard down to class and confusion pairs | PARTIAL | `services/labeler_stats.py:89-158` (per member), `models/insights.py:68-70` (agreement cached with no class dimension) | Must | M |
| G1.5 | Work queue with priority, stage scope and a cap per labeler | MISSING | `models/project.py:107-109` has status+assignee only; `routers/images.py:356-385` groups by batch, not task; `AnnotateBoard.tsx:81-121` | Must | M |
| G1.6 | Labeling stage graph (human, model, consensus) | MISSING | `services/workflows.py:17-22` — `BLOCK_TYPES` has no human or review block; status is a flat string | Should | L |
| G1.9 | Object tracks with keyframes, an out-of-frame state, split and merge | PARTIAL | `services/video.py:155-231`, `routers/videos.py:112-185` (`task_22`); identity management absent | Should | M |
| G1.10 | Review screen with side-by-side answer key and a mismatch list | PARTIAL | `Editor.tsx:726-731,855-857` (approve/reject only), `routers/images.py:599-614`; ground truth lives only in `EvalPanel.tsx:145` | Should | M |
| G1.11 | Trial project that scores a labeler before real work | MISSING | `none found (trial, calibration, pass_mark)` | Could | M |
| G1.12 | Event-triggered extension runtime on label events | PARTIAL | `routers/webhooks.py:18-32` outbound only; `services/workflows.py:17-22` has no custom-code block | Could | L |
| G1.13 | Label form defined as a document, not a task type | MISSING | `Panels.tsx:21` — four fixed attribute keys; `models/project.py:111` free JSON, nothing validates | Could | L |
| G1.16 | Time-in-stage and labelling speed accounting | PARTIAL | `services/labeler_stats.py:70-86` (per day), `models/insights.py:115-129` (no stage, no duration) | Should | S |
| G1.17 | Quality metric chosen per field, with thresholds | PARTIAL | `routers/labeling.py:52-56` (one IoU per job), `labeling_ops.py:205` uses the default | Could | S |

### B. Training, evaluation and model governance — `02-training-mlops.md`

17 features · 1 HAVE · 12 PARTIAL · 4 MISSING. Sixteen are refinements of things we already
half-built; only four are new surfaces. The 12 PARTIALs are cheap because the data is already
stored and only the surface is missing.

| ID | Feature | Status | Evidence | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G2.1 | Sweep a version across a parameter space | MISSING | `routers/training.py:213-223` one value per field, `:267-279` one model per submit | Could | L |
| G2.2 | The run keeps its exact configuration, exportable and re-importable | PARTIAL | Params live on `Job.params` (`training.py:272-277`); `TrainedModel` (`models/training.py:34-53`) has no config | Should | S |
| G2.3 | One ledger row per run with configuration as sortable columns | PARTIAL | `routers/training.py:163-186` sorts by AP only; `CompareTab.tsx:301-323` has metrics, no params | Should | M |
| G2.4 | Promotion is a request naming an approver | PARTIAL | `models/training.py:77-101` (alias + append-only events), `routers/deployments.py:13-45`; no approver field | Should | M |
| G2.5 | Lineage carries its inputs and can re-run from any node | PARTIAL | `services/insights_lineage.py:1-5,74-76`, `features/lineage/Lineage.tsx:15-45`; nodes have counts only | Should | M |
| G2.6 | A model card ships with the weights | MISSING | `routers/training.py:90-98` returns licence/metrics/URL, no prose; `none found (card, intended use)` | Should | M |
| G2.7 | A slice of the score opens into the images that caused it | PARTIAL | `services/insights_eval.py:189-229` builds the file list at `:215` then drops it | Should | M |
| G2.8 | The hold-out score is audited for leakage | PARTIAL | `services/versioning.py:59-92` prevents leakage at split time; nothing measures it afterwards | Should | M |
| G2.9 | Coverage report for the conditions the model will meet | PARTIAL | `services/insights_embedding.py:276-306` scatter only; `none found (uniqueness, coverage)` | Could | L |
| G2.10 | Suspect labels ranked by model confidence | HAVE | `services/suspects.py:1-17`, `services/suspect_queue.py`, `routers/projects.py:433-455` (`task_28`) | Could | S |
| G2.11 | Benchmark sheet: latency and throughput per export format and device | MISSING | `routers/training.py:349-381` builds `engine` only; one mean latency in `services/evaluate.py:98` | Should | M |
| G2.12 | Queues with priorities, pools and quotas instead of one worker | PARTIAL | `models/training.py:9-31` (no priority), `worker.py:132-149` one at a time, `gpu.py:45-67` | Should | L |
| G2.13 | Bring your own GPU, and watch it in our dashboard | PARTIAL | `routers/remote.py:195-211` protocol works; `_REMOTE_UNSUPPORTED` (`training.py:252-255`); no UI | Could | M |
| G2.14 | A failed run explains itself and retries with the same arguments | PARTIAL | `handlers/training.py:160-173`, `services/remote_reaper.py`; `Models.tsx:206-244` offers stop only | Should | M |
| G2.15 | Per-run host telemetry, not just loss curves | PARTIAL | `gpu.py:45-67` live snapshot only, `routers/registry.py:18-23` | Could | S |
| G2.16 | A published run report a non-engineer can read | PARTIAL | `dashboardExport.ts:41-42,88-101` (one PNG); no narrative, link or PDF | Should | M |
| G2.17 | An extension point for our own and the customer's analysis | MISSING | `none found (plugin, extension point)`; adapter registry is server-side only | Could | L |

### C. Industrial and edge operations — `03-edge-industrial.md`

18 features · 0 HAVE · 10 PARTIAL · 8 MISSING. The most expensive group and the one with the
clearest commercial reason: this is what separates a SaaS labelling tool from a line-side
system, and it is the only group where a Thai factory buyer has no cloud alternative at all.

| ID | Feature | Status | Evidence | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G3.1 | Camera onboarding: discovery, profile choice, credential pre-test | PARTIAL | `features/streams/Streams.tsx:123-124` one URL field; `streams/creds.py:1-9`; no ONVIF route | Should | M |
| G3.2 | Site → line → station → camera hierarchy | PARTIAL | `models/training.py:56-73` — `AnomalyStation` is project-scoped, anomaly-only, no camera, no parent | Must | M |
| G3.3 | Operator verdict with reason codes and a piece id | PARTIAL | `routers/streams.py:540-553` — `reviewed: bool` is the whole vocabulary; `:61-64` no reason | Should | M |
| G3.4 | Rules that follow a schedule instead of always being on | MISSING | `streams/rules.py:88-106` evaluates every rule every frame; no window field | Should | S |
| G3.5 | Alarm ownership, snooze, cross-camera grouping and a queue | PARTIAL | `streams/rules.py:62-80` per-track cooldown; `routers/streams.py:506-537` filters, no owner | Should | M |
| G3.6 | Evidence clip with pre/post-roll and a hold | MISSING | `streams/manager.py:807-871,912-925` — snapshot JPEG only; `routers/streams.py:341-361` deletes with the stream | Should | M |
| G3.7 | Store-and-forward while the edge or the server is offline | MISSING | `streams/manager.py:835-857`: on quota the event row is inserted and the snapshot is dropped; no spool | Should | L |
| G3.8 | Device-bound engine registry with a golden replay | PARTIAL | `handlers/versioning.py:51-70` builds with `half=True` and records no TRT/CUDA profile | Should | M |
| G3.9 | Training that knows its deployment target | MISSING | `Train.tsx:92-114` has no target, memory or latency budget; `adapters/catalog.py:33-40` | Should | L |
| G3.10 | Prune / INT8 / QAT with an accuracy delta | PARTIAL | `handlers/versioning.py:51-70` one precision mode; `adapters/tensorrt_ad.py:31-39` | Should | M |
| G3.11 | Reject signal to the machine over Modbus / OPC-UA / MQTT | MISSING | `services/alerts.py` is HTTP push; `none found (modbus, opcua, mqtt, plc)` across the backend | Must | M |
| G3.12 | Barcode / QR / lot-code decoding | MISSING | `none found (barcode, qr, datamatrix, pyzbar)` | Should | M |
| G3.13 | OCR / OCV verification against an expected value | PARTIAL | `services/ocr.py:59-114` normalises and masks, never compares; `:152-192` exports the text | Should | S |
| G3.14 | Measurement in real units with calibration and a tolerance verdict | MISSING | `none found (mm_per_px, calibrat)`; shapes carry no scalar (`services/track.py:26-69`) | Should | M |
| G3.15 | Shift calendar, first-pass yield and reason breakdown | PARTIAL | `services/insights_stream.py:198-213` hourly totals; no shift, no yield | Should | M |
| G3.16 | Camera quality guard: readiness probe plus a per-camera baseline | PARTIAL | `services/quality.py:1-13,33-50` scores uploads; `streams/manager.py:628,713` watches liveness only | Should | S |
| G3.17 | Event envelope contract, broker transport, dead-letter and replay | PARTIAL | `routers/streams.py:61-64`, `streams/manager.py:807` whitelist payload; no broker | Should | M |
| G3.18 | On-camera analytics partitioning (metadata in, not pixels) | MISSING | `streams/manager.py:691-737` decodes on our side; `none found (edge agent, metadata ingest)` | Could | L |

### D. Foundation-model labeling — `04-vlm-foundation.md`

17 features · 0 HAVE · 9 PARTIAL · 8 MISSING. Nine PARTIALs sit inside code we already ship:
the model, the prompt field and the confidence slider exist; the controls that would make a
buyer trust the output do not.

| ID | Feature | Status | Evidence | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G4.1 | A per-class prompt pack (synonyms, exclusions) that can seed the class list | PARTIAL | `AutoLabelDialog.tsx:235-243` one free-text prompt per batch, `:117-127`; `sam3_auto_label/config/ppe_4class.yaml:7-22` already proves per-class prompt+threshold off-app | Must | M |
| G4.3 | Confidence bands with an escalation threshold and per-band counts | PARTIAL | `routers/training.py:384-397` one float one bool; `AutoLabelDialog.tsx:126` hard-codes `send_to_review: true` | Must | M |
| G4.4 | A VLM second pass that flags a box instead of deleting it | PARTIAL | `adapters/refine.py:150-152,171-173` drops the box; `vlm_ad.py:139-148` returns a bool and no reason | Must | M |
| G4.5 | A judge rubric returning a verdict, a reason and a score per label | MISSING | `vlm_ad.py:164-165` returns raw text used only in the playground; nothing stored | Should | M |
| G4.6 | A question checklist that answers into per-image attributes | MISSING | `models/project.py:86-110` tags only; no attribute map | Should | M |
| G4.7 | Caption and keyword extraction written back as tags | PARTIAL | `adapters/catalog.py:14` declares `caption`; `vlm_ad.py:92-97` returns text, no tag write | Could | S |
| G4.8 | Named clusters on the embedding map, with lasso-to-label | PARTIAL | `services/insights_embedding.py:276-303` projection only; `Embeddings.tsx:164-172` brush; no clustering | Should | M |
| G4.9 | A per-class coverage and gap report with targets | PARTIAL | `services/versioning.py:186-205` counts, `routers/projects.py:80-85`; no target or gap logic | Should | M |
| G4.10 | Active learning with margin sampling, a quota and a stated budget | PARTIAL | `services/active_learning.py:38-58` top-confidence only, `:224-255` score and reason never stored | Should | M |
| G4.11 | A discovery sweep that names classes nobody asked for | MISSING | `vlm_ad.py:108-125` filters output to requested classes; `sam3_ad.py:33-37` requires classes | Could | L |
| G4.12 | Track a concept from one text prompt across a video with stable IDs | PARTIAL | `services/track.py:105-134` forward only from a seed box; `routers/videos.py:187-204` (`task_22`) | Should | M |
| G4.13 | A disagreement queue between two auto-label models | MISSING | `routers/playground.py:38-65` runs up to 3 models and diffs nothing; single image | Should | M |
| G4.14 | A teacher → student loop with an agreement gate | PARTIAL | `adapters/refine.py:68-73` stamps source; no cross-model agreement artefact | Should | M |
| G4.15 | Synthetic and composited fills for a rare class, with provenance | MISSING | `services/imaging.py:189-238` geometric/photometric only; no provenance field | Could | L |
| G4.16 | Harvest the boxes the checker rejected as hard negatives | MISSING | `refine.py:150-152,167-173` discards rejections; `none found (negative)` | Could | S |
| G4.17 | A labelling job the agent plans, trials, then escalates | MISSING | `services/workflows.py:67-100` fixed block list, no planning; `none found (agent, plan, escalat)` | Should | L |
| G4.18 | Ask the dataset a structural question in words | MISSING | `routers/images.py:190-300` fixed params; `services/insights_query.py:25-30` widget specs only | Should | M |

### E. Enterprise trust — `05-enterprise-table-stakes.md`

20 features · 0 HAVE · 13 PARTIAL · 7 MISSING. Four are legal exposure, not features: ownership
transfer, DSAR, Thai invoicing, Thai language. The rest are RFP answers and can wait.

| ID | Feature | Status | Evidence | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G5.3 | Sign-in policy: session life, step-up, MFA, network rules | PARTIAL | `deps.py:142,170` enforces `require_mfa`; `security.py:15-16` hardcodes 15 min / 30 days; no IP list | Should | M |
| G5.4 | Ownership transfer and an offboarding sweep | MISSING | `routers/workspaces.py:160,199` — "ownership transfers are not supported"; `:217-218` blocks removing the owner | Must | M |
| G5.5 | Tamper-evident audit trail with a retention floor | PARTIAL | `routers/audit.py:30-94` query and export; `models/insights.py:23-30` has no hash chain | Should | M |
| G5.6 | Object-scoped activity history | PARTIAL | `routers/workspaces.py:286-311` free-text match over `target`; no per-object route | Should | M |
| G5.7 | Retention policy builder with dry-run and legal hold | PARTIAL | `services/retention.py:196-285` deletion works; `routers/privacy.py:122-127` days per project only | Should | M |
| G5.8 | Sandbox and production separation | MISSING | `none found (sandbox, environment)`; `apikeys.py` knows no test key | Could | M |
| G5.9 | DSAR workbench: find, export and erase one person | PARTIAL | `services/erasure.py:85-151` erases by prefix; no subject index, case, deadline or certificate | Must | M |
| G5.10 | Processing register: purpose, lawful basis, consent, transfers | PARTIAL | `routers/privacy.py:177-267` DPA prose, `:129-134` free-text basis; not structured records | Should | M |
| G5.11 | Sub-processor register with change notice and an objection window | MISSING | Only prose at `routers/privacy.py:225,227` | Should | S |
| G5.12 | Trust centre | PARTIAL | `routers/privacy.py:270-284` DPA only; no public page, no certification status | Should | M |
| G5.13 | Breach notification runbook with a 72-hour clock | PARTIAL | `routers/privacy.py:243-246` promise in prose; no incident object or countdown | Should | M |
| G5.15 | Customer-owned bucket and customer-managed keys | MISSING | `routers/connectors.py:1-4` read-only import; `config.DATA_DIR` is the only store | Could | L |
| G5.16 | Thai invoiced billing: PromptPay, bank transfer, VAT tax invoice, PO, dunning | MISSING | `config.py:88-97` plans carry no price or currency; `Settings.tsx:973-975` says contact the operator | Must | M |
| G5.17 | Per-project budget with a pre-flight estimate and pause | PARTIAL | `services/metering.py:91-113` workspace quota and 402; no project budget or estimate | Should | M |
| G5.18 | Public status page with incident history | PARTIAL | `routers/admin.py:144-192` internal components only, behind superadmin | Should | M |
| G5.19 | SLA with measured uptime and a self-serve credit claim | MISSING | `admin.py:184-192` instantaneous states, no history | Could | M |
| G5.20 | In-product help: what's new, docs search, feedback | MISSING | `none found (help, changelog, feedback)` in nav or settings | Should | S |
| G5.21 | Guided onboarding and admin adoption analytics | PARTIAL | `Settings.tsx:1102-1118` first-run card; `routers/workspaces.py:119-132` 30-day counts | Could | M |
| G5.22 | Thai locale end to end, including generated documents | PARTIAL | `src/index.css:3-4,43,92` fonts and `:lang(th)` rules; `lib/theme.ts:131-136` Buddhist calendar; zero translated strings | Must | L |
| G5.24 | WCAG 2.2 AA with an automated gate | PARTIAL | `Editor.tsx:204-206,777-791`, `index.css:105`, `@axe-core/playwright` in devDeps; no CI gate | Could | M |

### F. Thai market and verticals — `06-repo-research-thai-market.md`

16 features · 0 HAVE · 7 PARTIAL · 9 MISSING. Only three survive as Must: the lot record, the
yield report and the packs. The rest are options, and five are marked as not worth building.

| ID | Feature | Status | Evidence | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G6.1 | Lot-bound inspection record with an OK / NG / rework disposition | PARTIAL | `models/training.py:56-60` station + threshold; `models/project.py:86-110` no lot or disposition | Must | M |
| G6.2 | First-pass yield and defect Pareto per lot, line and shift | MISSING | `services/insights_stream.py:198-213` events only; `none found (yield, rework, lot)` | Must | M |
| G6.4 | Shift handover brief at the end of a shift | MISSING | `none found (handover, shift)` | Should | S |
| G6.5 | Glove-first Thai operator screen at the station | MISSING | No kiosk feature; `Anomaly.tsx:36-85` is a desktop layout | Should | L |
| G6.6 | Vertical starter packs (PPE safety, IC/PCB defect) installed in one step | PARTIAL | `sam3_auto_label/config/ppe_4class.yaml:1-16`, `sam3_auto_label/ic_defect_pipeline.py:2-20`; no pack installer | Must | M |
| G6.7 | LINE alert with evidence and an acknowledgement ladder | PARTIAL | `services/alerts.py:31,217` push; `:110-132` throttle; no postback route | Should | M |
| G6.8 | Daily safety summary PDF for an inspector | MISSING | `none found (pdf, reportlab, weasy)` | Should | M |
| G6.10 | Shelf-gap and planogram slot compliance | MISSING | `streams/rules.py:1-19` zones only; no slot or grid primitive | Could | L |
| G6.11 | Price-tag read-back against a price master | PARTIAL | `services/ocr.py:20-45` payloads; no master join or exception list | Could | M |
| G6.12 | Fruit grading station by size and defect | MISSING | `models/project.py:19-43` no grade or calibration; no label print | Could | L |
| G6.13 | Exporter lot report with grade mix and photographs | MISSING | no document renderer; `Batch` carries no grade or signatory | Could | M |
| G6.14 | Offline field capture with deferred sync and geotag | MISSING | `Upload.tsx:66-129` no persistence; `none found (geotag, offline, capture session)` | Should | M |
| G6.15 | Evidence package for police or insurer | PARTIAL | `services/streamaudit.py:50-64` records views; `routers/streams.py:61-66` snapshot only | Should | M |
| G6.16 | Redaction of faces and plates across capture, live view and export | PARTIAL | `services/faceblur.py:1-10,69`; no plate detector, no polygon mask, no export policy | Should | M |
| G6.20 | Air-gapped on-premises install with an offline licence | PARTIAL | `apps/inference/README.md:58-99` runs; no offline install path, licence or signed update | Should | L |
| G6.22 | Partner console for an SI: child workspaces, licence pool, statement | MISSING | `routers/workspaces.py` flat; `superadmin.py` is ours, not a reseller's | Could | L |

---

## 3. The ranked differentiators

Ranked by "can we win the deal with this, and can Roboflow follow us in a quarter".
Only the first four are worth scheduling this year.

1. **Thai operations end to end — G5.22, G5.16, G6.7, G5.9.**
   Thai UI and Thai documents; PromptPay, bank transfer and a 7% VAT tax invoice with a PO;
   LINE alerts a supervisor can acknowledge; a PDPA pack an auditor accepts. Nothing in the
   334-row parity matrix covers a Thai locale, a THB price, a LINE channel or a PDPA record —
   and a Thai factory cannot issue a purchase order against a USD card subscription, which ends
   most deals before the product is seen. This is not a feature race; it is a different country.
2. **The line-side loop — G3.2, G3.11, G6.1, G6.2.**
   Station → lot → disposition → yield, with a reject signal a PLC can read. Roboflow's workflow
   blocks stop at inference and HTTP sinks; no row in the parity matrix puts a reject on a line
   controller or a result into a lot record. Every industrial buyer asks "what does it do when it
   sees a bad part" and we currently have no answer that leaves the browser. This is also the
   hardest for a competitor to copy, because it needs hardware in the loop.
3. **Label quality as a product — G1.1, G1.2, G1.4, G1.5.**
   We already ship consensus, honeypots and suspect labels (HAVE) — three capabilities with no
   row anywhere in the parity matrix. Finishing the queue and the class-level quality report
   turns a hidden capability into the reason an outsourced-labelling shop picks us. Cheapest
   strategic win in this document: four of these five items are the last 30% of code that
   already exists.
4. **Auto-label you can defend — G4.1, G4.3, G4.4, G4.16.**
   Per-class prompts with exclusions, confidence bands with a stated escalation threshold, a
   checker that flags instead of silently deleting, and rejected boxes kept as hard negatives.
   Competing auto-labelers optimise the demo frame; buyers who tried one and got burned are
   buying auditability, and the parts are already in the repo (`refine.py` drops the evidence
   it should keep).
5. **Vertical packs — G6.6.** One click installs classes, prompts, thresholds, rules and a
   station for PPE or IC/PCB. We own a working SAM 3.1 PPE pipeline and an IC-defect pipeline
   that nobody can buy yet. A pack is the difference between a demo and a repeatable sale, and
   it is the only SKU in this document a reseller can quote without an engineer.
6. **On-premises and air-gapped — G6.20, G5.15, G5.8.** An inference container exists. Add an
   offline licence and signed model bundles and we can sell to a customer who will never send a
   frame outside Thailand. Roboflow's architecture cannot follow.
7. **Camera fleet hygiene — G3.1, G3.16, G3.6.** Discovery, a readiness probe, a per-camera
   baseline and an evidence clip. Low glamour, high trial conversion: most "the model does not
   work" reports are a dirty lens and a 4 Mbps sub-stream.
8. **Curation we already have the data for — G4.8, G4.9, G2.8, G2.7.** The embedding index,
   the slices and the pHash groups all exist; the surfaces that would let a user act on them
   do not. Four PARTIALs that read as one capability in a demo.
9. **Governance a procurement team can tick — G5.5, G5.7, G5.10, G5.12, G5.4.** Only after a
   customer asks. Cheap in a deal, worthless before one.
10. **Channel motion — G6.22, G5.19.** A partner console and an SLA matter when we sell through
    an SI, not before. Defer until the first partner signs.

### What would make these claims false

- Thai language only wins if the translation covers the editor and the operator screen, not the
  settings page. Half-translated is worse than English for a factory floor.
- The industrial loop only wins if the reject signal is fail-safe: a missed NG part that the
  line accepted is a liability, not a bug. G3.11 must ship with a defined behaviour for "model
  down" (default reject or default stop), and that decision is the owner's, not an engineer's.
- Consensus and honeypots are behind `task_23` today. A capability nobody can switch on is not
  a differentiator; flipping the flag is part of the work.

---

## 4. What not to build

Named here so they stop reappearing in every competitor comparison. Each was confirmed absent
in code; absence is the correct state.

| Tempting | Why not |
| --- | --- |
| 3D point-cloud / LiDAR / cuboid labelling (G1.14) | A different editor and a different buyer. No Thai customer in the research notes asks for it. CVAT and SuperAnnotate own it. |
| DICOM / NIfTI medical series (G1.15) | Regulatory surface (device classification) we cannot carry. Encord owns the niche. |
| Planogram slot compliance (G6.10) | Needs a shelf-plan import format and a retail template library; a different product with a different sales motion. |
| Fruit grading station (G6.12) | Requires mechanical handling, calibration targets and a label printer. We would be selling a machine, not software. |
| Sweeps and hyperparameter search (G2.1) | The buyer trains one model with defaults. Two weeks of work for a feature nobody will open. |
| Plugin marketplace (G1.12, G2.17) | A marketplace with no developers is a support burden. Webhooks already cover the real integration need. |
| Right-to-left and a second locale framework (G5.23) | Thai first. Do not build an i18n framework for markets we do not sell to. |
| On-camera analytics (G3.18) | Only matters when a customer refuses to send pixels. G6.20 (air-gap) solves the same objection with less code. |

---

## 5. Where this research is thin

- **Cognex, Keyence, Viso, Genetec, Dataloop, SuperAnnotate** were only partly readable (paywalls,
  client-side docs, bot walls). Their cards rest on one page each; the industrial cards that
  matter (G3.11, G3.2, G3.14) lean on NVIDIA and Edge Impulse documentation instead.
- **Every Thai regulatory claim** (PDPC cross-border rules, Revenue Department e-tax invoice,
  PromptPay mandate behaviour) is second-hand or from a listing page. Nothing here is legal
  advice; G5.9, G5.10 and G5.16 need a Thai lawyer and an accountant before build.
- **Two PARITY rows are now stale** against `c9e907d`: 7-F7.51 (notification sinks) and 7-F7.59
  (workspace deletion) were written before `task_33` shipped LINE/Slack/email channels. The
  parity lane should re-check before Wave D is estimated.
- **`sam3_auto_label/` is untracked** and its pipelines are not wired into the app. G6.6 treats
  it as a capability we own, not as a shipped feature; if that code is abandoned, the pack card
  loses its cheapest half.
- **No customer interviews.** Every "who uses it" is inferred from vendor documentation and the
  repo's own sector notes. One afternoon with two Thai factory QA managers would reorder
  section 3 faster than any further desk research.

---

## 6. Counts

| Group | Cards | Kept | HAVE | PARTIAL | MISSING | Must | Should | Could |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A annotation platforms | 17 | 13 | 1 | 7 | 5 | 2 | 6 | 5 |
| B training / MLOps | 17 | 17 | 1 | 12 | 4 | 0 | 11 | 6 |
| C edge / industrial | 18 | 18 | 0 | 10 | 8 | 2 | 15 | 1 |
| D VLM / foundation | 18 | 17 | 0 | 9 | 8 | 3 | 10 | 4 |
| E enterprise | 24 | 20 | 0 | 13 | 7 | 4 | 11 | 5 |
| F Thai market | 22 | 16 | 0 | 7 | 9 | 3 | 8 | 5 |
| **Total** | **116** | **101** | **2** | **58** | **41** | **14** | **61** | **26** |

Dropped as parity duplicates: 5. Merged into another card: 8. Moved to §4 as non-goals: 2
(G1.14, G1.15). 116 − 15 = 101 rows in the tables above.

The 14 Musts, in build order: G1.5, G1.4, G4.1, G4.3, G4.4, G5.16, G5.22, G5.4, G5.9, G3.2,
G3.11, G6.1, G6.2, G6.6.
