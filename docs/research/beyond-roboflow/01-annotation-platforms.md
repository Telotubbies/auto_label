# G1 — Annotation and labeling platforms

Lane: CVAT, Label Studio, Labelbox, SuperAnnotate, V7 Darwin, Encord, Dataloop, Kili. Read at
`feat/labeldesk-v2` / `fe8ef1a`, 2026-11-17. Every card cites a page fetched in this session.

Scope note that shapes the statuses below: this branch already ships QA that the Roboflow matrix has
no row for. `routers/labeling.py` exposes consensus jobs and honeypots, `services/video.py`
interpolates video tracks, and `features/project/QA.tsx` puts four tabs in front of it (Workforce,
Review queue, Consensus, Honeypots). All of it sits behind feature flags `task_23` (QA) and `task_22`
(video interpolation), so a trial that has not enabled the flags sees none of it. Anything marked
HAVE was checked end to end against that code; the gap is stated instead of pretending it is absent.

| ID | Capability | Nearest source | Status | Pri | Size |
| --- | --- | --- | --- | --- | --- |
| G1.1 | Duplicate passes merged by majority | CVAT, Labelbox, Encord, Kili | HAVE | Should | M |
| G1.2 | Answer-key rows seeded into the live queue | CVAT, Kili, Labelbox | PARTIAL | Should | M |
| G1.3 | Score at submit, with capped retries and hints | CVAT | MISSING | Could | M |
| G1.4 | Quality dashboard down to class and confusion | Label Studio, SuperAnnotate | PARTIAL | Must | M |
| G1.5 | Work queue with priority, stage scope and caps | Encord, Labelbox, V7 | MISSING | Must | M |
| G1.6 | Labeling workflow with human, model and consensus stages | V7, Labelbox, Encord | MISSING | Must | L |
| G1.7 | Region-anchored comments with mentions and resolve | V7, CVAT, Encord | PARTIAL | Should | M |
| G1.8 | Instructions attached to the job and opened on first visit | CVAT, Kili, Labelbox | MISSING | Must | S |
| G1.9 | Track objects with keyframes and an out-of-frame state | CVAT, Encord, V7 | PARTIAL | Should | M |
| G1.10 | Review screen with the answer key and a mismatch list | CVAT | PARTIAL | Should | M |
| G1.11 | Trial project that scores a labeler before real work | Encord, Labelbox | MISSING | Could | M |
| G1.12 | Event-triggered extension runtime | Kili, Dataloop | PARTIAL | Could | L |
| G1.13 | Label form defined as a document, not a task type | Label Studio, Kili, SuperAnnotate | MISSING | Could | L |
| G1.14 | 3D point-cloud and cuboid annotation | CVAT, SuperAnnotate | MISSING | Could | L |
| G1.15 | DICOM / NIfTI series with windowing | Encord, V7 | MISSING | Could | L |
| G1.16 | Time-in-stage and speed accounting | CVAT | PARTIAL | Should | S |
| G1.17 | Quality metric chosen per field, with thresholds | Label Studio, CVAT | PARTIAL | Could | S |

---

### G1.1 Duplicate passes merged by majority (CVAT, Labelbox, Encord, Kili)

- **What the user does:** picks a set of unlabelled images, says how many independent passes each image gets, and lets the system merge the drafts into one image once everyone has handed in.
- **Who uses it:** a QA lead on a project where one labeler's judgement is not trusted enough to ship, or where the customer contract names inter-annotator agreement.
- **Flow:** 1. **QA → Consensus**, "Create job" form: image count, passes per image, IoU floor (`[empty]` when the project has fewer members than passes — the form disables and says how many annotators exist). 2. Each pass lands in the labeler's **My tasks** strip and in the editor's consensus banner; autosave is private, "Submit consensus draft" is the hand-in. 3. The job row moves collecting → ready when every draft is in `[loading: agreement recomputing]`. 4. "Merge consensus" writes the majority shape, parks each image in **Review**, and reports `merged` and `skipped`; images with no strict majority are listed by id and left untouched. 5. **Review queue** puts the most disputed images first.
- **Why it is easy:** the merge is one button with a counted outcome, and a tie never destroys the drafts — they stay readable in the job detail.
- **Products with it:** CVAT replica jobs with automatic merge (https://docs.cvat.ai/docs/qa-analytics/consensus/); Labelbox consensus with % coverage and a reviewer winner override (https://docs.labelbox.com/horizon/guides/consensus); Encord consensus block with an annotate and a review stage plus "determine consensus" (https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-workflows-consensus); Kili consensus with labeler count, coverage and a blind parallel pass (https://docs.kili-technology.com/docs/consensus-overview).
- **Why it matters for LabelDesk:** it is the clearest difference from Roboflow for an outsourced-workforce buyer, and we already built it — but a reviewer cannot overrule the majority, and a job cannot be sampled as a percentage of a batch instead of a hand-picked set.
- **LabelDesk code evidence:** `apps/backend/app/routers/labeling.py:42-78` (list/create/merge, `ConsensusIn` k and IoU at `:52-56`), `services/labeling_ops.py:66-109` (round-robin assignment), `:217-239` (per-image agreement cache), `:270-326` (strict-majority merge, `no_consensus` list), `services/labeling.py:155-162,183-231` (pairwise agreement, cluster merge), `models/insights.py:58-89`, `features/project/qa/Consensus.tsx:49-140`.
- **Suggested status:** HAVE — create → draft → submit → merge → review completes today; the missing winner override is an addition, not a broken step. Flag `task_23` at `routers/labeling.py:11-12` hides the whole surface.
- **Suggested priority / size:** Should / M (per-image reviewer override + a sampled-coverage mode).

### G1.2 Answer-key rows seeded into the live queue (CVAT, Kili, Labelbox)

- **What the user does:** marks a small set of already-correct images as the answer key and lets the queue hand them to labelers at a chosen rate, so accuracy is measured without the labeler knowing which rows count.
- **Who uses it:** QA lead or ops manager who must report a per-labeler accuracy number every week and cannot review every image.
- **Flow:** 1. **QA → Honeypots**: pick an image, pin it (its current labels or a fresh set become the key). 2. The labeler opens it from the ordinary queue; header, counts, filters and ordering give nothing away. 3. Save is scored and discarded, so the key is never overwritten. 4. **Honeypots** shows attempts and accuracy per labeler, **Workforce** shows the project average. 5. `[error: 409 image is already a honeypot]`.
- **Why it is easy:** the answer key never leaves the reviewer's screen, and the labeler is scored on the save they were making anyway.
- **Products with it:** CVAT honeypot mode with a total pool %, an overhead per job and a random seed (https://docs.cvat.ai/docs/qa-analytics/auto-qa/); Kili honeypot on one chosen workflow step, ground truth uploaded through the SDK, score visible in the queue and analytics (https://docs.kili-technology.com/docs/honeypot-overview); Labelbox benchmark rows that open the queue and reappear at roughly one in ten after the first five (https://docs.labelbox.com/horizon/guides/benchmark).
- **Why it matters for LabelDesk:** accuracy per labeler is a procurement question in outsourced work. Today a reviewer pins honeypots one image at a time, so nobody keeps a steady trickle in the queue and the metric decays to whatever was tested in week one.
- **LabelDesk code evidence:** `routers/labeling.py:95-126`, `services/labeling_ops.py:120-122` (image → key lookup), `:204-213` (score written on save, one attempt row per labeler), `:454-479` (create, round-robin delivery, key hidden from reviewers), `services/labeling.py:239-240`, `features/project/qa/Honeypots.tsx`, `lib/api/qa.ts:22-25`.
- **Suggested status:** PARTIAL — scoring and dashboards work; delivery is manual per image, there is no rate, pool or seed, and `HoneypotAttempt` (`models/insights.py:104-112`) holds one row per labeler, so a second look silently replaces the first score.
- **Suggested priority / size:** Should / M (screen the pool by percentage of each batch; keep attempt history).

### G1.3 Score at submit, with capped retries and hints (CVAT)

- **What the user does:** finishes an image, sees a score against the hidden key, and gets two more attempts before the verdict is final — with short hints about what kind of mistake it was, never where.
- **Who uses it:** a new or struggling labeler, and the lead who does not want to spend a review cycle on work already known to be weak.
- **Flow:** 1. **Editor** → "Submit for review" on a scored image. 2. Dialog: score, target, accept or disagree. 3. On disagree, "fix and re-check" returns to the same image with the attempt counter visible. 4. A final rejection shows up to three hints (class A confused with B, missing objects of C) and the image goes back to annotating. 5. `[empty: attempts exhausted]`, `[error: scoring timed out, the job is accepted as if the feature were off]`.
- **Why it is easy:** the labeler learns inside the job they are already doing, and the reviewer receives fewer bad images.
- **Products with it:** CVAT immediate job feedback with a target metric, a threshold, a max validation count per job and top-problem hints (https://docs.cvat.ai/docs/qa-analytics/immediate-feedback/).
- **Why it matters for LabelDesk:** we score honeypots but tell nobody. A score the labeler never sees is a management number, not a training loop, and the reviewer still explains the same mistake image after image.
- **LabelDesk code evidence:** none found (searched `attempt`, `feedback`, `hint`, `threshold` in `apps/backend/app` and `apps/frontend/src`; the only hits are the single `HoneypotAttempt` row at `models/insights.py:104-112` and its score write at `services/labeling_ops.py:204-213`).
- **Suggested status:** MISSING — no post-submit surface, no attempt cap, no hint derivation.
- **Suggested priority / size:** Could / M.

### G1.4 Quality dashboard down to class and confusion (Label Studio, SuperAnnotate)

- **What the user does:** opens one screen that answers "is this dataset ready, which class is weak, and which pair of labels do people keep swapping".
- **Who uses it:** project owner before generating a version, and the account manager defending the dataset in a customer review.
- **Flow:** 1. **QA → Workforce** or **Insights**: agreement between passes, agreement per class, top swapped pairs, member × member matrix. 2. Click a cell → filtered image list. 3. Window switch 7/30/90 days `[loading]`. 4. `[empty: no consensus job yet — the next action is named]`.
- **Why it is easy:** every chart is a filter, so the number and the images behind it are one click apart.
- **Products with it:** Label Studio task agreement with per-control-tag metrics, weights, consensus vs pairwise methodology and a data-quality dashboard with distribution, confusion pairs and a members matrix (https://docs.humansignal.com/guide/stats); SuperAnnotate quality gates combining agreement, honeypots and expert audits on a per-project dashboard (https://www.superannotate.com/platform); CVAT quality reports at project, task and job level (https://docs.cvat.ai/docs/qa-analytics/quality-control/).
- **Why it matters for LabelDesk:** we store per-image agreement and per-labeler honeypot accuracy but never join them to classes, so "where is my data weak" is still answered in a spreadsheet after export.
- **LabelDesk code evidence:** `services/labeler_stats.py:89-158` (throughput, AI acceptance, rejection rate, honeypot average per member), `services/labeling_ops.py:419-425`, `features/project/qa/Workforce.tsx:13-70` (daily throughput only), `models/insights.py:68-70` (per-image agreement cached with no class dimension).
- **Suggested status:** PARTIAL — member-level numbers exist; class-level agreement, confusion pairs and cross-filtering are absent.
- **Suggested priority / size:** Must / M.

### G1.5 Work queue with priority, stage scope and caps (Encord, Labelbox, V7)

- **What the user does:** opens a queue listing only the tasks their role can act on, ordered by priority, and stops receiving work at the cap the manager set.
- **Who uses it:** labeler starting a shift, reviewer clearing a backlog, lead redistributing a stalled batch.
- **Flow:** 1. **Project → Queue**: one list per stage with counts; columns priority, dataset, assignee, status, issue state. 2. Filter by assignee/status. 3. Select rows → assign, release, change priority, move stage. 4. "Start" opens the editor on that task alone. 5. `[empty: nothing assigned in this stage]`, `[error: already claimed by another user]`.
- **Why it is easy:** one ordered list replaces hunting through batch cards, and the cap stops a contractor being handed three days of work by accident.
- **Products with it:** Encord queue tab with role-scoped stages, priority numbers and assign/release (https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-workflow-queue); Labelbox workflow tasks with instructions, group assignment, per-contributor and per-group caps (https://docs.labelbox.com/horizon/guides/workflows); V7 self-assignment with a chosen batch size and a priority action on selected files (https://docs.v7labs.com/docs/assign-and-complete-tasks).
- **Why it matters for LabelDesk:** our unit of assignment is the batch card on a four-column board, so a 400-image batch is one indivisible lump, there is no priority, and "my tasks" only knows consensus drafts. Five people cannot share work without a manager editing the board by hand.
- **LabelDesk code evidence:** `routers/images.py:356-385` (board grouped by batch+assignee), `models/project.py:107-109` (status and assignee only — no priority, due date or stage), `features/project/AnnotateBoard.tsx:15-16,81-121` (three columns, assign dialog with one select), `services/labeling_ops.py:428-440`.
- **Suggested status:** MISSING — batch assignment is not a task queue, and no priority field exists in `apps/backend/app/models`.
- **Suggested priority / size:** Must / M.

### G1.6 Labeling workflow with human, model and consensus stages (V7, Labelbox, Encord)

- **What the user does:** draws the path an image takes — annotate, model pre-label, compare two passes, review, send back to a named stage — instead of accepting four fixed columns.
- **Who uses it:** ops lead setting up a pipeline where first-pass and expert review are different teams, or where a model labels first and a human only verifies low confidence.
- **Flow:** 1. **Project → Workflow** canvas: drag stage nodes, connect arrows, rename stages. 2. Stage config: assignees, instructions, cap, whether edits are allowed. 3. A review stage picks where a rejection goes (previous assignee, a named earlier stage, or a separate rework stage). 4. Publish; live images follow the new path `[loading: rerouting]`. 5. `[error: a stage with no assignee cannot accept files]`.
- **Why it is easy:** the picture is the configuration, so a second review tier is one more node rather than a second project.
- **Products with it:** V7 stages (Dataset, Annotate, Review, Model, Webhook, Archive, Consensus, Logic, Sample, Complete) with explicit reject paths (https://docs.v7labs.com/docs/use-workflows-to-manage-your-projects, https://docs.v7labs.com/docs/the-review-stage); Labelbox node-based workflow of initial label, review, rework and done with per-task caps (https://docs.labelbox.com/horizon/guides/workflows); Encord blocks for annotate, review, consensus and agent stages with an archive for rejected work (https://docs.encord.com/platform-documentation/Annotate/annotate-projects/annotate-workflows-consensus).
- **Why it matters for LabelDesk:** parity's workflow builder is an inference pipeline (model → filter → sink); the labeling path is still `unassigned → annotating → review → done` plus a project-level review flag. A buyer with two review tiers has to run two projects.
- **LabelDesk code evidence:** `services/workflows.py:17-22` (`BLOCK_TYPES = model, filter, crop, ocr, rule, sink`, max 12 blocks — no human, review or consensus block), `routers/workflows.py:54-95`, `models/project.py:107-109` (flat status string), `routers/images.py:575-580` (status changes gated by role with no destination choice).
- **Suggested status:** MISSING — there is no stage graph on the labeling side.
- **Suggested priority / size:** Must / L.

### G1.7 Region-anchored comments with mentions and resolve (V7, CVAT, Encord)

- **What the user does:** draws a box around the wrong part of the image, writes a note, tags the person who should fix it, and later marks it resolved.
- **Who uses it:** reviewer explaining a correction; labeler asking a question without leaving the image.
- **Flow:** 1. **Editor** → comment tool → drag a region → type, `@` picks a teammate. 2. The comment pins to that region and appears in the Review tab with author and age. 3. The tagged user is notified and lands on the image with the region highlighted. 4. Author or reviewer resolves it; resolved items hide behind a toggle. 5. `[empty: no comments on this image]`.
- **Why it is easy:** the note is attached to the pixels, so "this corner" needs no description, and resolving removes it from the list without deleting history.
- **Products with it:** V7 comment tool with box anchoring, mentions, notifications and resolve (https://docs.v7labs.com/docs/the-comment-tool); CVAT issue tool with region-anchored reports, quick-issue presets, resolve and hide-resolved (https://docs.cvat.ai/docs/qa-analytics/manual-qa/).
- **Why it matters for LabelDesk:** our comments are a flat per-image text list (image, user, text, date). On a 40-object frame a thread degrades to "the second forklift from the left", which is the ambiguity review exists to remove.
- **LabelDesk code evidence:** `models/project.py:160-166` (no anchor, parent or resolved field), `routers/images.py:617-634`, `features/editor/Panels.tsx:123-165`, `features/editor/Editor.tsx:247,1050`.
- **Suggested status:** PARTIAL — text threads work; no anchor, mention, resolve state or notification.
- **Suggested priority / size:** Should / M.

### G1.8 Instructions attached to the job and opened on first visit (CVAT, Kili, Labelbox)

- **What the user does:** writes the rules once — what counts as occluded, which parts are ignored, how the edge cases look — and every labeler meets them before the first image.
- **Who uses it:** project owner onboarding a labeler or a vendor team; QA lead after a recurring mistake.
- **Flow:** 1. **Project → Settings → Instructions**: markdown with text, images, lists and checklists. 2. Save; the text attaches to the project and optionally to one batch with a shorter note. 3. The labeler's first image opens with the panel over the canvas and a "Got it" button `[empty: nothing written yet — a prompt links to the editor]`. 4. Reopen from a header button at any time. 5. A one-line hint shows next to the class in the picker.
- **Why it is easy:** the rules live where the work happens instead of in a chat thread, and the first-visit open needs no discipline from the labeler.
- **Products with it:** CVAT markdown guide on project and task, auto-opened on the first new job, with editor-only comments (https://docs.cvat.ai/docs/annotation/specification/); Kili instructions as a project link plus per-category metadata on hover (https://docs.kili-technology.com/docs/adding-instructions); Labelbox per-task instructions in the workflow node (https://docs.labelbox.com/horizon/guides/workflows).
- **Why it matters for LabelDesk:** there is no instructions field anywhere; the only backend hit for "instructions" is the DPA legal text. Each new vendor team relearns the rules through rejected images.
- **LabelDesk code evidence:** none found (searched `instructions`, `guideline`, `guide`, `note` across `apps/backend/app` and `apps/frontend/src`; `models/project.py:19-40` has settings JSON but no instruction field, `:43-52` classes carry name, colour and skeleton only).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Must / S.

### G1.9 Track objects with keyframes and an out-of-frame state (CVAT, Encord, V7)

- **What the user does:** labels one object on two frames, gets the frames between filled in, then marks where the object leaves the frame so a later pass does not read the gap as a miss.
- **Who uses it:** anyone annotating video — traffic, conveyor, PPE — where one object must keep one identity across frames.
- **Flow:** 1. **Video timeline** → mark frame A as keyframe, draw the box. 2. Jump to frame B, draw the same object, "Interpolate" fills the span `[loading: N frames]`. 3. A track list shows one row per tracked object with its keyframe count and previous/next jumps. 4. Mark the object outside the frame from frame X so the track stops without ending the label. 5. `[error: 409 no shared track between these frames]`, `[error: span over 240 frames]`.
- **Why it is easy:** two boxes replace thirty, and a track id lets the reviewer watch one object move instead of thirty unrelated boxes.
- **Products with it:** CVAT track mode with automatic interpolation, keyframe jumps, merge/split and the Outside property (https://docs.cvat.ai/docs/annotation/manual-annotation/modes/track-mode-basics/); Encord interpolation per instance with a confidence marker on derived labels (https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-interpolation); V7 interpolation with re-run and auto-track (https://docs.v7labs.com/docs/auto-annotate).
- **Why it matters for LabelDesk:** we interpolate between two marked frames and can SAM-propagate 30 frames, but there is no track list, no outside state and no split/merge — occlusion and re-entry produce duplicate identities that poison any tracking metric downstream.
- **LabelDesk code evidence:** `services/video.py:155-231` (`pair_tracks`, `merge_interpolated`, `interpolate_tracks`, `MAX_INTERPOLATION_SPAN` at `:14`), `routers/videos.py:112-185` (interpolate endpoint, `task_22` gate at `:117`), `:187-210` (SAM track-forward), `services/track.py:91-134`, `features/project/VideoTimeline.tsx:171-225`, `lib/types.ts:88-93` (`trackId`, `keyframe`, `source: interpolated`).
- **Suggested status:** PARTIAL — geometry interpolation works; identity management (track list, outside, split/merge, per-track attribute edit) does not exist.
- **Suggested priority / size:** Should / M.

### G1.10 Review screen with the answer key and a mismatch list (CVAT)

- **What the user does:** opens an image in review, sees the trusted labels and the submitted ones together with disagreements highlighted, and edits nothing until they choose to.
- **Who uses it:** reviewer on a project with a gold set; also the trainer explaining a rejection.
- **Flow:** 1. **Review queue** → open image → review mode (edit tools hidden, answer-key overlay on). 2. Toggle answer key / submitted / both; conflicts listed as rows (missing C, extra C, class A vs B). 3. Click a conflict → the canvas centres on it. 4. Approve, or leave a region comment and send back. 5. `[empty: no conflicts on this image]`, `[error: no answer key for this project]`.
- **Why it is easy:** the reviewer confirms a difference list instead of hunting for what changed.
- **Products with it:** CVAT review mode with ground-truth display, conflict highlighting and a reviewer/corrector split (https://docs.cvat.ai/docs/qa-analytics/manual-qa/); CVAT quality report with confusion matrices per requirement (https://docs.cvat.ai/docs/qa-analytics/auto-qa/).
- **Why it matters for LabelDesk:** "review mode" today is a warning banner and two buttons; ground truth appears only in the evaluation screens. The reviewer has no way to see what the honeypot says, so a rejection is still an assertion.
- **LabelDesk code evidence:** `features/editor/Editor.tsx:236,726-731,855-857,869` (banner, approve/reject only), `routers/images.py:599-614` (verdict plus optional note), `features/project/qa/ReviewQueue.tsx`, `features/evaluation/EvalPanel.tsx:145` (ground truth lives only here).
- **Suggested status:** PARTIAL — verdict and queue exist; no overlay, conflict list or tool lock.
- **Suggested priority / size:** Should / M.

### G1.11 Trial project that scores a labeler before real work (Encord, Labelbox)

- **What the user does:** gives a new labeler a fixed set with known answers, gets a score per class, and decides whether they join the live queue.
- **Who uses it:** vendor manager onboarding a team, or a lead adding a contractor mid-project.
- **Flow:** 1. **QA → Calibration**: new trial → pick the reference set (honeypot pool or an approved version), image count, pass mark. 2. The labeler sees a normal queue with a trial banner. 3. Submit → scorecard: overall, per class, worst three images with the key. 4. Pass grants project access; fail saves the scorecard and sets a retry date. 5. `[empty: no reference set yet]`.
- **Why it is easy:** same editor, same queue; only the pass mark is new, and the scorecard is evidence for the customer instead of a manager's opinion.
- **Products with it:** Encord annotator training (benchmark project plus one training project per annotator, scored by SDK against the benchmark) (https://docs.encord.com/end-to-end/BenchmarkQA/annotator-training); Encord automated QA comparing a production project to a benchmark project (https://docs.encord.com/end-to-end/BenchmarkQA/automated-qa); Labelbox benchmark quality mode (https://docs.labelbox.com/horizon/guides/benchmark).
- **Why it matters for LabelDesk:** hires in this market start on live customer data. We have per-honeypot scores; without a gate, the first customer batch is the trial.
- **LabelDesk code evidence:** none found for a trial or gate (searched `trial`, `calibration`, `onboarding`, `benchmark`, `pass_mark`); the nearest primitives are `services/labeling.py:239-240` and `models/insights.py:104-112`.
- **Suggested status:** MISSING — honeypot scoring is the raw material, not the flow.
- **Suggested priority / size:** Could / M.

### G1.12 Event-triggered extension runtime (Kili, Dataloop)

- **What the user does:** uploads a small script or installs an app that runs whenever a label is submitted, to enforce a business rule, add issues, or combine several labelers' boxes.
- **Who uses it:** a customer with a compliance rule (an ID format, a mandatory attribute) or an integrator shipping one checker to several workspaces.
- **Flow:** 1. **Settings → Extensions**: upload a package (entry file plus requirements), choose events (label submitted, reviewed, skipped). 2. Test on one image → run log with output `[loading]`. 3. Enable per project; failures appear in a run history with the payload. 4. `[error: package over the size limit]`, `[error: no runner available]`.
- **Why it is easy:** the rule stays in code the customer owns, and the platform triggers it instead of a cron job polling the API.
- **Products with it:** Kili plugins triggered by submit, review or any project event, with a programmatic-QA example that adds issues and sends work back (https://docs.kili-technology.com/docs/kili-plugins); Dataloop packages, functions and services with organisation-level apps and a serverless budget (https://docs.dataloop.ai/docs/apps-overview).
- **Why it matters for LabelDesk:** we have outbound webhooks only (`job.done`, `model.ready`, `stream.event`), so a customer-side checker has to be a listener with its own auth and retries, and there is nowhere to install it.
- **LabelDesk code evidence:** `routers/webhooks.py:1,18-32` (event whitelist, public-URL guard), `services/webhooks.py`, `services/workflows.py:17-22` (no custom-code block).
- **Suggested status:** PARTIAL — signed webhook delivery with retries exists; there is no inbound or in-process extension point on label events.
- **Suggested priority / size:** Could / L.

### G1.13 Label form defined as a document, not a task type (Label Studio, Kili, SuperAnnotate)

- **What the user does:** composes the labeling screen from parts — boxes plus a rating plus a required dropdown plus a free-text rationale — and sets which parts are required and which count toward quality.
- **Who uses it:** a customer whose label is not a box: a defect with severity and disposition, an inspection with pass/fail plus a note, a document with nested fields.
- **Flow:** 1. **Project → Settings → Labeling interface**: template gallery, then add or remove controls, mark required, add help text and a default. 2. Preview on a real image `[loading]`. 3. Save; the editor renders the new form beside the canvas. 4. Removing a control already in use is refused with a count `[error: 412 controls in use]`. 5. Export carries the extra fields.
- **Why it is easy:** adding a severity field is a form edit rather than an engineering ticket, and the required flag cannot be skipped under time pressure.
- **Products with it:** Label Studio templates plus a tag config with autocomplete and JavaScript plugin hooks (https://docs.humansignal.com/guide/setup); Kili JSON interface with nested jobs, required flags, per-category shortcuts and metadata (https://docs.kili-technology.com/docs/customizing-the-interface-through-json-settings); SuperAnnotate drag-and-drop form components with conditional logic and per-component roles (https://www.superannotate.com/platform).
- **Why it matters for LabelDesk:** every project has the same four fixed attribute flags and no per-class schema, so a customer with a severity grade renames a class or keeps the field in a spreadsheet beside the product.
- **LabelDesk code evidence:** `features/editor/Panels.tsx:21` (`ATTRIBUTE_KEYS = occluded, truncated, difficult, crowd`), `models/project.py:43-52` (class has name, colour, skeleton only), `models/project.py:111` (annotations are free JSON, so nothing validates extra fields).
- **Suggested status:** MISSING — no schema, no form builder, no validation on save.
- **Suggested priority / size:** Could / L.

### G1.14 3D point-cloud and cuboid annotation (CVAT, SuperAnnotate)

- **What the user does:** loads a lidar sweep, draws a cuboid around each object in a perspective view, and checks it against top/side/front projections so the depth is right.
- **Who uses it:** industrial and automotive customers whose sensor is a lidar, not a camera.
- **Flow:** 1. Upload a point cloud with its camera images. 2. **Editor → 3D**: perspective view, three projections, context image. 3. Draw a cuboid, move or resize in one view and see it in the others. 4. Class counts and a 3D export. 5. `[empty: no 3D frames in this project]`.
- **Why it is easy:** three orthogonal views plus a camera overlay make depth judgement possible without rotating the world.
- **Products with it:** CVAT 3D task workspace with perspective, projections and contextual images (https://docs.cvat.ai/docs/annotation/annotation-editor/3d-task-workspace/); SuperAnnotate lidar with cuboids and track ids (https://www.superannotate.com/platform).
- **Why it matters for LabelDesk:** uploader and editor are 2D-only, so a lidar prospect is disqualified at the first screen. This is a new modality, not a feature of the current one.
- **LabelDesk code evidence:** none found (searched `dicom|point_?cloud|lidar|\.pcd|cuboid|nifti|3d` across `apps/backend/app` and `apps/frontend/src`; zero hits).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / L.

### G1.15 DICOM / NIfTI series with windowing (Encord, V7)

- **What the user does:** opens a CT or MRI series, sets window width and level, moves through slices, and interpolates an object between slices the way a video is interpolated.
- **Who uses it:** a medical-imaging customer, or an industrial radiography team using the same formats.
- **Flow:** 1. Upload a series (multi-file, ordered). 2. **Editor → DICOM**: slice slider, axial/coronal/sagittal toggle, window presets and a custom width/level. 3. Label with boxes or bitmasks on the primary view; interpolate between slices. 4. Metadata panel shows the study fields policy allows. 5. `[error: series has inconsistent slice spacing]`.
- **Why it is easy:** windowing is one drag and the three planes stay linked, so an object is judged from three directions without leaving the frame.
- **Products with it:** Encord DICOM/NIfTI editor with windowing, three planes, slice interpolation and a browser note for large series (https://docs.encord.com/platform-documentation/Annotate/annotate-label-editor/annotate-dicom); V7 interpolation documented for video and DICOM (https://docs.v7labs.com/docs/use-interpolation-in-video-and-dicom).
- **Why it matters for LabelDesk:** same gap as G1.14 with a stricter procurement story (de-identification, retention). Nothing in our import path understands a multi-file series.
- **LabelDesk code evidence:** none found (searched `dicom|nifti|series|window_?width|slice` across `apps/backend/app` and `apps/frontend/src`; zero hits).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / L.

### G1.16 Time-in-stage and speed accounting (CVAT)

- **What the user does:** sees hours per stage, objects per hour per labeler, and how much of the work was derived rather than drawn.
- **Who uses it:** ops manager pricing the next batch, and a lead spotting the bottleneck stage.
- **Flow:** 1. **QA → Workforce → Time**: date range and stage selector. 2. Per-member row: hours, images, objects, objects/hour, share of derived objects. 3. Click a row → that member's daily chart. 4. `[empty: no activity in this range]`.
- **Why it is easy:** the estimate for the next batch comes from the last batch's own numbers, and the derived share explains a sudden speed jump.
- **Products with it:** CVAT analytics with total working time, average annotation speed, time per stage, interpolation rate and event export (https://docs.cvat.ai/docs/qa-analytics/analytics/).
- **Why it matters for LabelDesk:** one `LabelEvent` per save already carries a timestamp and a count, so hours and speed are derivable, but the dashboard shows only daily images and annotations. Quoting a customer is still manual arithmetic.
- **LabelDesk code evidence:** `services/labeler_stats.py:70-86` (per-day throughput), `:159-190` (member rows), `models/insights.py:115-129` (no stage, no duration), `models/project.py:107-115` (no status-change timestamp).
- **Suggested status:** PARTIAL — counts exist; time, speed and stage attribution do not.
- **Suggested priority / size:** Should / S.

### G1.17 Quality metric chosen per field, with thresholds (Label Studio, CVAT)

- **What the user does:** decides that boxes are judged by IoU at 0.6, that a severity dropdown must match exactly, and that severity counts twice in the overall score.
- **Who uses it:** QA lead whose label set mixes geometry with categorical decisions, where one number for everything hides the disagreement that matters.
- **Flow:** 1. **Project → Settings → Quality**: one row per field or class — metric, threshold, weight. 2. Save → existing scores marked stale with a recompute action `[loading]`. 3. Consensus and honeypot scoring read the config on the next save. 4. `[error: metric not available for this field type]`.
- **Why it is easy:** the threshold sits next to the number it produced, so "0.71 agreement" can be argued about instead of trusted blindly.
- **Products with it:** Label Studio per-control-tag metrics, weights for the overall score and a consensus-vs-pairwise choice (https://docs.humansignal.com/guide/stats); CVAT quality settings with a target metric, threshold and validation count (https://docs.cvat.ai/docs/qa-analytics/immediate-feedback/).
- **Why it matters for LabelDesk:** the IoU floor is chosen once per consensus job, and honeypots are always scored at 0.5, so two projects with different tolerance look equally good or bad.
- **LabelDesk code evidence:** `routers/labeling.py:52-56` (per-job IoU only), `services/labeling_ops.py:205` (honeypot score called with the default threshold), `services/labeling.py:239-240`, no quality section in `features/project/ProjectSettings.tsx`.
- **Suggested status:** PARTIAL — one threshold per consensus job works; nothing is configurable per class or per field.
- **Suggested priority / size:** Could / S.

---

## Already covered by PARITY.md

- `3-F3.46` — per-image approve/reject at keyboard speed, bulk verdicts, reject reason. Our verdicts live there; G1.10 only adds the answer-key view.
- `3-F3.48` — pinned, threaded comments on the image. G1.7 extends the same row (anchor, mentions, resolve) and the row already names the missing anchor.
- `3-F3.45` — assignment with instructions and notifications. G1.8 supplies the instructions that row says are absent; implement them once, under that task.
- `3-F3.50` — per-labeler and per-project label statistics. G1.4 and G1.16 are the class-level and time-level halves the row leaves open.
- `3-F3.51` — keyboard reference and remapping; a per-account profile is already listed as its gap.
- `3-F3.38` — per-class annotation attributes. The four fixed flags belong to that row; G1.13 is about a form document, not attribute names.
- `3-F3.15` — video timeline with per-class action segments. The row owns the video surface; G1.9 is the identity half.
- `1-F2.4`, `3-F3.40` — shared class sets across projects. Labelbox's reusable ontology (https://docs.labelbox.com/horizon/guides/import-prelabels) proves the shape; the rows already ask for it.
- `6-F6.19` — active learning as a sampling rule. `services/active_learning.py` implements uncertainty plus diversity picks into a review batch; that is this row's territory.
- `6-F6.21`, `6-F6.10` — inference workflow canvas and callable workflow. G1.6 is the labeling-side stage graph; the builder stays with these rows.
- `2-F2.36` — near-duplicate discovery as a ranked queue. Labelbox Catalog slices (https://docs.labelbox.com/horizon/guides/catalog-overview) are close, but the row owns it.
- `7-F7.49` — webhook push from a pipeline. Outbound webhooks are counted there; G1.12 is the inbound extension point.
- `7-F7.54`, `1-F5.2` — public project page; not a reviewer link, and the row owns it.
- `1-F4.3`, `2-F2.27` — one query language over class, tag and split; Labelbox catalog queries are the same idea and the rows own them.

## Title-only / unverified

- **SuperAnnotate documentation** (`doc.superannotate.com`): every documentation URL returned a bot-wall or 404 this session, so pixel-level QA, consensus scoring detail and the editor SDK were not verified. Only the product page (https://www.superannotate.com/platform) was read, and it is marketing — "quality gates", "agreement scores" and "custom forms" are claims there, not documented flows.
- **Client or guest review links without an account** (a named target in the brief): no fetched page documents one. V7's comment and task pages describe team members only; Labelbox workflows assign groups inside the workspace. Left unverified rather than carded.
- **Labelbox ontology management as a versioned object**: only the pre-labels page names a reusable ontology; no page describing versioning or change propagation was fetched.
- **CVAT serverless functions (Nuclio)** and the **Label Studio ML backend**: located but not read in full, and the auto-label half is parity's `3-F3.21`/`3-F3.26` anyway.
- **Dataloop task assignment, analytics and marketplace pricing**: only the pipeline and app overviews were read; their assignment model is not evidenced here.
- **V7 dataset versioning and lineage**: the sitemap lists an export-version page, but the lineage claim was not verified and is not carded (parity's Area 4 owns versions).

## Notes for the lead

- Three items here are not greenfield: consensus (G1.1), honeypots (G1.2) and video interpolation (G1.9) already ship behind `task_23`/`task_22`. The cheapest trial-visible work is enabling those flags, adding instructions (G1.8), and putting existing agreement data on a class dimension (G1.4).
- The two structural gaps are the task queue (G1.5) and the labeling stage graph (G1.6). Both are workforce features; neither can be faked with a settings switch, and both are what an outsourced-labeling buyer compares line by line.
