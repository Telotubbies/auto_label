# Beyond Roboflow — group 4: VLM and foundation-model era (2025–2026)

Scope: open-vocabulary detection, the SAM 3 family, VLM QA and pre-labelling, agentic labelling,
synthetic data, active learning, embedding curation. One file, IDs `G4.1`–`G4.18`, read against
`feat/labeldesk-v2` (`fe8ef1a`).

Method: 14 pages fetched this session (Meta SAM 3 repo, Ultralytics SAM 3 / YOLO-World /
augmentation docs, IDEA DINO-X API, FiftyOne Brain and Agent pages, Encord docs index, llms.txt and
agent catalog, NVIDIA Omniverse Replicator, Gemini image-understanding docs, Qwen3-VL card). Code
read in `apps/backend/app/{adapters,services,routers}` and
`apps/frontend/src/features/{project,editor,playground}`. Untracked `sam3_auto_label/` is cited as
capability evidence only: its model is called from `services/segment.py`, but its batch pipeline
(checkpoint/resume, 11 export formats) is not wired. Roboflow's auto-label, SAM and workflow rows
already live in `docs/research/roboflow-parity/PARITY.md`; every card names the control parity does
not describe.

Repeated local finding: **the adapters are ahead of the surfaces.** `vlm_ad.py` already does
schema-constrained grounding, per-box yes/no, phrase parsing and free-text ask; `segment.py` runs
SAM 3.1 text and box prompts on the GPU ledger; `active_learning.py` already does uncertainty plus
diversity under a daily cap. Nearly every card below is PARTIAL for one missing control — a band, a
queue, a stored score, a report — not for a missing model.

---

## 4.1 Prompts, schemas, auto-label

### G4.1 Exclusion phrases and synonym sets on each class prompt (open-vocabulary prompt pack)
- **What the user does:** opens one class row in Auto label → Class prompts and adds the other names that object has on site ("hard hat", "safety helmet") plus what it must never match ("bicycle helmet", "helmet on a shelf"), then previews.
- **Who uses it:** a PPE or factory team whose class is one phrase while the floor says four.
- **Flow:** 1. Batch board → Auto label → Class prompts. 2. Expand a class → synonym chips, exclusion chips, one-line note. 3. `[error: "bicycle helmet" is an exclusion on Helmet and a synonym on Bike]` blocks Preview. 4. Preview shows per-class counts with excluded hits counted separately; Run carries the pack, and the pack is saved on the class, not the batch.
- **Why it is easy:** the prompt sits on the class row the labeler already reads, so a new synonym costs no workflow edit and no re-upload.
- **Products with it:** YOLO-World takes a free-form class list plus a documented empty-string background class that suppresses spurious hits (https://docs.ultralytics.com/models/yolo-world/); SAM 3 takes positive **and negative** image exemplars per concept (https://docs.ultralytics.com/models/sam-3/); DINO-X accepts text, visual and custom prompts together (https://github.com/IDEA-Research/DINO-X-API).
- **Why it matters for LabelDesk:** per-class *descriptions* and *thresholds* are parity 3-F3.27 and 3-F3.29; exclusions and synonyms are what decides whether a zero-shot run is usable, and our vocabulary is Thai-English mixed.
- **LabelDesk code evidence:** `features/project/AutoLabelDialog.tsx:201-233` (checkbox rows only), `:235-243` (one free-text field per batch), `:117-127` (payload has one `prompt`); `adapters/refine.py:133-143` (one prompt → `parse_prompt` → phrases); `services/segment.py:286-292` (loops prompts, one threshold). `sam3_auto_label/config/ppe_4class.yaml:7-22` already keeps a prompt **and** threshold per class in the working off-app pipeline; the app loads that repo's model (`services/segment.py:113-120`) but never reads its config.
- **Suggested status:** PARTIAL — class names plus one free-text line; no negative phrase, no synonyms, nothing saved on the class.
- **Suggested priority / size:** Must / M.

### G4.2 A prompt library that becomes the class schema
- **What the user does:** opens Project → Classes → "Build from prompts", pastes the customer's checklist ("helmet, hi-vis vest, harness, closed footwear, no helmet"), tests it on 20 samples, then creates the classes and their prompts at once.
- **Who uses it:** a consultant starting the fifth plant of a customer, reusing wording that already worked.
- **Flow:** 1. Classes → "Build from prompts". 2. Paste YAML/CSV of name → phrases. 3. Test → table per phrase: images with ≥1 hit, median boxes, collision with an existing class; zero-yield phrases get a rewrite hint, never auto-delete. 4. "Create N classes" → classes with prompts attached; the file is stored on the project for the next plant.
- **Why it is easy:** the vocabulary arrives as a file the customer already maintains instead of being retyped into a checkbox list.
- **Products with it:** YOLO-World bakes a custom class list into a saved model, making the vocabulary an artefact rather than a per-run setting (https://docs.ultralytics.com/models/yolo-world/); SAM 3 Text auto-annotates detection sets from 1–200 class names (https://docs.ultralytics.com/models/sam-3/#faq).
- **Why it matters for LabelDesk:** the direction today is classes → prompts only, classes are project-scoped (parity 1-F2.4), so plant five starts from zero.
- **LabelDesk code evidence:** manual class admin `routers/projects.py:266-334`, `features/project/Classes.tsx`; `refine.py:134-137` only maps phrases back onto classes that already exist; no prompt-import path in `routers/` (searched `prompt`, `ontology`, `schema`).
- **Suggested status:** MISSING — prompts cannot create classes.
- **Suggested priority / size:** Should / M.

### G4.3 Confidence-bucketed auto-label with an escalation threshold
- **What the user does:** sets three bands on one screen — accept at ≥ x, review between y and x, discard below y — and reads the predicted per-band count from the preview before spending.
- **Who uses it:** an ops lead running 20k images a week who cannot review all of it but will not ship unreviewed labels either.
- **Flow:** 1. Auto label → "Review policy" under the class list. 2. Preview table per class: accept / review / discard, plus implied batch totals. 3. `[error: review band is empty]` if y ≥ x. 4. Run writes accept-band as `done`, review-band as `review` plus a `bucket=review` tag, discards to the job report; the board shows two queues with counts.
- **Why it is easy:** "how much will I have to review" is answered before the job, beside the threshold that decides it.
- **Products with it:** FiftyOne Brain scores samples for hardness and human labels for mistakenness, so review can be ordered by risk rather than page number (https://docs.voxel51.com/brain/index.html).
- **Why it matters for LabelDesk:** one threshold and "everything goes to Review" is the current contract; a 50k-image buyer reads that as no automation.
- **LabelDesk code evidence:** `routers/training.py:384-397` (`confidence: float` single, `send_to_review` single bool), `:474-497` (preview returns per-class counts only); `AutoLabelDialog.tsx:255-258` (one slider), `:87`, `:126` (`send_to_review: true` hard-coded).
- **Suggested status:** PARTIAL — confidence exists; buckets and an escalation policy do not.
- **Suggested priority / size:** Must / M.

### G4.4 A VLM second pass that flags a box instead of deleting it
- **What the user does:** ticks "VLM check" on a batch, then reads a flagged count in the job report and finds the flagged boxes still on the image, one click from a reviewer's confirm/dismiss.
- **Who uses it:** a reviewer inheriting 4,000 auto-labels who needs the 300 the machine itself doubted.
- **Flow:** 1. Auto label → "Check each box with the VLM" (off by default). 2. Each box ends `checked=confirmed` or `checked=doubtful` plus the question that rejected it. 3. Job card shows confirmed / doubtful / unchecked. 4. Review opens doubtful first with a strip "the checker could not confirm this as Helmet"; `[empty]` "no doubtful boxes".
- **Why it is easy:** the check becomes evidence a human can overrule instead of a deletion nobody can audit.
- **Products with it:** SAM 3's data engine uses fine-tuned multimodal verifiers for mask quality and exhaustivity, keeping humans for cases the verifier fails (https://docs.ultralytics.com/models/sam-3/); Encord's VQA agent writes an answer into an attribute instead of touching geometry (https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-agents-catalog-reference.md).
- **Why it matters for LabelDesk:** silent deletion is the one auto-label behaviour a QA auditor will not sign, and keeping the box costs one field.
- **LabelDesk code evidence:** `adapters/refine.py:139` (flag), `:150-152`, `:171-173`, `:186-187` (the box is dropped); `adapters/vlm_ad.py:139-148` (crop + yes/no, no reason, no record); `AutoLabelDialog.tsx:245-248` (the checkbox text says so).
- **Suggested status:** PARTIAL — the check runs; its verdict is discarded.
- **Suggested priority / size:** Must / M.

---

## 4.2 VLM as reviewer

### G4.5 A judge rubric that returns a verdict, a reason and a score per label
- **What the user does:** picks a rubric ("class right? box tight? object fully inside?"), runs it on a filtered slice or the suspect queue, and gets one row per annotation with verdict, one-line reason and a 0–1 score they can filter and export.
- **Who uses it:** a QA lead answering a complaint about 40 labels without re-reading 40 images.
- **Flow:** 1. Project → Review → "Judge" tab beside suspect labels. 2. Rubric picker (default three questions, editable). 3. Scope: filter, selection, or suspect queue → `[loading]` with a per-item counter; `[error: vLLM not reachable]` + retry. 4. Results table (verdict, reason, score, open in editor) → save as report; human confirm/dismiss stays a separate field.
- **Why it is easy:** one sentence of reasoning is what lets a reviewer trust or overrule the judge; a bare yes/no gives them nothing to check.
- **Products with it:** Gemini returns schema-constrained JSON for detection and segmentation, so a rubric answer can be a typed object with label and comment (https://ai.google.dev/gemini-api/docs/image-understanding); Encord's per-image question agent stores a free-text answer per image (https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-agents-catalog-reference.md).
- **Why it matters for LabelDesk:** we already pay one VLM call per box in auto-label and up to 24 per shape in `suggest-class`; a reason is nearly free and is the demo-versus-tool line.
- **LabelDesk code evidence:** `adapters/vlm_ad.py:139-148` (15% crop margin, `choice: ["yes","no"]`, boolean), `:164-165` (`ask` returns raw text, unused outside playground); `routers/images.py:660-703` (buys ≤24 yes/no answers to pick a class, keeps the first match only).
- **Suggested status:** MISSING — no rubric, no reason, no score, nothing stored.
- **Suggested priority / size:** Should / M.

### G4.6 A question checklist that answers into per-image attributes
- **What the user does:** defines 3–5 questions once ("is the helmet worn, not carried?", "vest visible?", "inside the marked zone?"), applies them to a filtered batch, and gets filterable per-image attributes plus a review task per "no".
- **Who uses it:** a safety officer whose real label is compliance, not detection — the boxes already exist.
- **Flow:** 1. Classes & attributes → "Question set". 2. Dataset → select → "Answer questions" → `[loading]` per image; a failed image keeps old answers and is counted. 3. Answers show as grid columns, filterable ("vest = no"), and in the editor's image panel. 4. Rule "answer = no → tag `review:vest`" creates the work; the tag drives a query, not a new shape type.
- **Why it is easy:** an answer is a value on the image, so it filters, exports and counts like a tag — no new label type to learn.
- **Products with it:** Encord ships "Ask a Question About an Image" as a catalog agent whose output must land in an ontology TEXT attribute, from the editor or a workflow (https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-agents-catalog-reference.md); Qwen3-VL is an Apache-2.0 open-weight option when data cannot leave the site (https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct).
- **Why it matters for LabelDesk:** parity 3-F3.17 only wants a prefix field so VQA data can be authored; answering questions *about* an existing dataset turns each image into a row of facts a factory can query.
- **LabelDesk code evidence:** `models/project.py:86-110` (tags only, no attribute map); `features/editor/Editor.tsx:1031` (tag editing); no batch question endpoint in `routers/` (searched `attribute`, `vqa`, `question`).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / M.

### G4.7 Caption and keyword extraction written back as tags
- **What the user does:** selects a batch, presses "Describe", gets a caption and 3–8 keyword tags per image, edits them inline, and filters on them.
- **Who uses it:** a team with 8,000 unlabelled images where the quick win is finding and naming clusters ("night shift, wet floor, pallet stack") before drawing a box.
- **Flow:** 1. Dataset → select → "Describe" → `[loading]` with rate estimate; over the cap it asks to split. 2. Rows gain `caption` and tag chips (weak keywords greyed). 3. Edit inline, accept all, reject one keyword. 4. "contains wet floor" runs as a query; export has an "include captions" toggle.
- **Why it is easy:** the caption is editable on the row being triaged, so a wrong word costs a click, not a re-run.
- **Products with it:** Encord's description agents (OpenAI, Claude, or open models via CoreWeave) write a text classification per image with custom prompt and detail setting (https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-agents-catalog-reference.md); Gemini captions without a task-specific model (https://ai.google.dev/gemini-api/docs/image-understanding).
- **Why it matters for LabelDesk:** the registry already advertises a caption capability we do not deliver — a gap a technical evaluator finds in ten minutes.
- **LabelDesk code evidence:** `adapters/catalog.py:14` (`_VLM_CAPS` includes `caption` "until the vlm adapter registers"); the adapter reports `{"detect","open-vocab","vqa"}` (`adapters/vlm_ad.py:85-86`) and `predict()` returns raw text only when prompted (`:92-97`), with no tag write.
- **Suggested status:** PARTIAL — the model can answer; nothing turns an answer into tags.
- **Suggested priority / size:** Could / S.

---

## 4.3 Curation: clusters, coverage, sampling

### G4.8 Named clusters on the embedding map, with lasso-to-label
- **What the user does:** presses "Find clusters" on the map, sees sized coloured groups, names one "wet floor / night", and applies a class, tag or review batch to the whole group.
- **Who uses it:** a lead looking for the 2,000 near-identical images that add nothing and the one dense cluster nobody labelled.
- **Flow:** 1. Insights → map → "Cluster" (`[empty]` until a map is built). 2. `[loading]` grouping; `[error: map is stale — re-embed first]`. 3. Cluster list: size, share, dominant class, unlabelled share; click isolates, hover previews. 4. Rename; lasso → "Label as…" / "Send to review" / "Tag…"; footer "3 clusters have no annotations".
- **Why it is easy:** the map already says "these look alike"; naming the group is what turns a scatter into a batch action.
- **Products with it:** FiftyOne's Embeddings panel selects samples by lasso and syncs with the grid for images and object patches; representativeness finds each cluster's typical sample (https://docs.voxel51.com/brain/index.html).
- **Why it matters for LabelDesk:** we can open a lasso as a dataset selection (`Embeddings.tsx:56-61`), but with no cluster identity the same group is rediscovered next week.
- **LabelDesk code evidence:** `services/insights_embedding.py:276-303` (UMAP/PCA only), `:318-339` (points carry class/source/error, no cluster id); `Embeddings.tsx:164-172` (brush), `:56-61` (lasso → selection → `/browse`), `:196-201` (cap 1,000); no clustering in `apps/backend/app` (searched `dbscan`, `kmeans`, `cluster_`).
- **Suggested status:** PARTIAL — lasso works; clusters do not exist.
- **Suggested priority / size:** Should / M.

### G4.9 A per-class coverage and gap report
- **What the user does:** opens a report listing per class: images containing it, instance count, share of dataset, singles, clusters it never appears in, and a "thin" flag under a target they set.
- **Who uses it:** a team about to freeze a version, deciding whether "harness" can ship or needs another collection round.
- **Flow:** 1. Insights → Coverage. 2. `[empty]` "label something first" → board link. 3. Table sorted by thinness with target-per-class (default 100) and "missing from N clusters". 4. Row click filters to that class or to images *without* it; CSV export; the same table rides in the version summary.
- **Why it is easy:** "which class is short" becomes one sorted table with a target, instead of a distribution chart plus arithmetic.
- **Products with it:** FiftyOne's distribution agent reports per-class counts, flags imbalance and outliers; its curation agent analyses class distribution and data gaps (https://docs.voxel51.com/agents/index.html).
- **Why it matters for LabelDesk:** the raw numbers already exist (health check chart, version manifest), so the missing part is a verdict, not data.
- **LabelDesk code evidence:** `services/versioning.py:186-205` (per-class counts in the manifest), `features/project/DatasetHealth.tsx:193-…` (distribution chart); `routers/projects.py:80-85` (`classes_out` returns one image count per class); no gap logic (searched `coverage`, `imbalance`, `under-represent`).
- **Suggested status:** PARTIAL — counts exist; the report and its threshold do not.
- **Suggested priority / size:** Should / M.

### G4.10 Active learning with margin sampling, a per-class quota and a stated budget
- **What the user does:** sets a daily cap, a per-class floor and an exploration share, then reads why each image was picked (low margin, rare class, new cluster).
- **Who uses it:** a team with a live model whose next labelling week should target what the model cannot do yet.
- **Flow:** 1. Settings → Active learning: enable, cap, per-class floor, exploration %, "explain picks". 2. `[loading]` scoring; `[error: no ready model]` + train link; `[empty]` "cap reached, resets at midnight" with used/limit. 3. Batch card lists each pick with reason and score, sortable. 4. Later, the same screen shows how many picks the model got right after training.
- **Why it is easy:** the queue states why each image is there, so the labeler is not re-labelling at random and the manager can defend the spend.
- **Products with it:** FiftyOne Brain's hardness and uniqueness give both rankings without ground truth (https://docs.voxel51.com/brain/index.html); SAM 3's "active mining" spends human effort where the machine fails (https://docs.ultralytics.com/models/sam-3/).
- **Why it matters for LabelDesk:** parity 6-F6.19 is the rules form; the engine behind it is ours and already diversity-aware, but its decision is erased, so it can be neither explained nor tuned.
- **LabelDesk code evidence:** `services/active_learning.py:38-58` (uncertainty from the **top** confidence in a band, no top-1 vs top-2 margin), `:69-91` (greedy uncertainty − 0.5 × similarity), `:186-197` (newest 200 unannotated only), `:224-255` (batch + tag; score and reason never stored), `:266-307` (`below` + `sample_pct`).
- **Suggested status:** PARTIAL — selection is real; margin, quotas and explanation are missing.
- **Suggested priority / size:** Should / M.

### G4.11 A "what else is here" sweep that names things nobody asked for
- **What the user does:** runs a prompt-free pass on a sample and gets ranked object types with counts and crops, then promotes the useful ones into classes.
- **Who uses it:** a new project whose brief names three classes while the images also hold forklifts, ladders and cables that will hurt the model if unlabelled.
- **Flow:** 1. Dataset → "Discover objects" (50/200/500). 2. `[loading]` with cost; `[error: no open-vocabulary model available]`. 3. Ranked phrases, counts, crop strip, overlap warning with existing classes. 4. Tick → "Add as classes" or "Ignore for this project" (remembered); repeat runs show what is new.
- **Why it is easy:** it answers a question the user could not phrase, because they did not know the object was there.
- **Products with it:** DINO-X has a prompt-free mode that detects, segments and recognises with no prompt (https://github.com/IDEA-Research/DINO-X-API); Gemini will "detect all prominent items" and return a descriptive label per box, including custom instructions like "all green objects" (https://ai.google.dev/gemini-api/docs/image-understanding).
- **Why it matters for LabelDesk:** every path we ship needs a class list first, so an unknown object is found only by luck — the cheapest defence against a confidently wrong dataset.
- **LabelDesk code evidence:** `adapters/vlm_ad.py:108-125` (output filtered against the requested classes; nothing else survives), `adapters/sam3_ad.py:33-37` (raises without classes or prompt), `routers/training.py:406-409` (400 "add classes first — SAM uses class names as text prompts").
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / L.

---

## 4.4 Video, agreement, data supply

### G4.12 Track a concept from one text prompt across a video, with stable IDs
- **What the user does:** types "person without helmet" once, gets one track per instance across the timeline with a persistent id, reviews a track as a unit, and can delete a false track instead of 200 boxes.
- **Who uses it:** a site-safety team labelling 30-minute camera clips where the same eight people walk through.
- **Flow:** 1. Video page → "Track a concept": text prompt or seed box. 2. `[loading]` by frame; `[error: SAM 3 unavailable on this worker]`. 3. Track list: id, class, first/last frame, length, mean score, "interpolated" badge; edits become keyframes and survive re-runs. 4. "Extend backwards", "re-run from frame", "delete track"; unconfirmed frames stay unlabelled and are counted.
- **Why it is easy:** the unit of work is the object's life in the clip, which is how a reviewer already thinks, not frame 412 of 1,800.
- **Products with it:** SAM 3's video predictor takes a text prompt on any frame and returns masks for all instances with identities (https://github.com/facebookresearch/sam3); SAM 3.1's Object Multiplex runs many tracked objects together (~7× at 128 objects per Meta) (https://docs.ultralytics.com/models/sam-3/#sam-31).
- **Why it matters for LabelDesk:** parity 3-F3.34 is Roboflow's video *action segment* auto-label; ours is detection tracking that needs a drawn seed and walks forward 30 frames.
- **LabelDesk code evidence:** `services/track.py:105-134` (re-prompts SAM with the previous box, forward only), `:91-102` (keyframe beats interpolated); `routers/videos.py:187-204` (seed annotation id, `frames` 1–120, behind `task_22`); `VideoTimeline.tsx:208` (`frames: 30`); `lib/types.ts:88-91` (`trackId`, `keyframe`).
- **Suggested status:** PARTIAL — propagation with persistent ids works from a hand-drawn seed, one direction, one object at a time.
- **Suggested priority / size:** Should / M.

### G4.13 A disagreement queue between two auto-label models
- **What the user does:** runs two models (or a model and a VLM) over the same 500 images and gets only the images where they disagree, sorted by distance, as a review batch.
- **Who uses it:** a team choosing between a cheap YOLO and a foundation model, or auditing a new model against production, with no ground truth yet.
- **Flow:** 1. Playground or batch board → "Compare": A, B, sample size. 2. `[loading]` two count columns; `[empty]` "models agree on every sampled image". 3. Diff view: A in one colour, B in another, per-image score (missing, extra, class mismatch, IoU shift). 4. "Send the top 50 to Review" stores both predictions; summary shows per-class agreement and each model's cost.
- **Why it is easy:** disagreement is a free quality signal when nothing is labelled, and it points the reviewer at the images that decide the choice.
- **Products with it:** Ultralytics publishes a VLM leaderboard scoring SAM 3 Text against vision-language models on the same data — the same "which model do I trust here" question, answered offline (https://docs.ultralytics.com/models/sam-3/#faq).
- **Why it matters for LabelDesk:** the playground already runs three models side by side for one image and stops there; parity 5-F5.25 colours a map by one model's failures, which is a different question.
- **LabelDesk code evidence:** `routers/playground.py:22-23` (`MAX_MODELS = 3`), `:38-65` (`_run` returns each prediction, no diff), `:75-100` (single uploaded image); `features/playground/Playground.tsx` (side-by-side, no batch, no queue).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / M.

### G4.14 A teacher → student loop with an agreement gate
- **What the user does:** auto-labels with a foundation model, reviews only the doubtful part, trains the small production model, then reads a student-versus-teacher table on a held-out slice before promoting.
- **Who uses it:** a team that cannot afford SAM 3 or a 7B VLM at inference but can afford it once, offline.
- **Flow:** 1. Auto label (teacher) → review band only → version. 2. Train → run card offers "compare with teacher on 100 held-out images". 3. `[loading]`; per class: agreement %, student-only, teacher-only, mean IoU on matches, note where the student wins. 4. "Promote to production" only above the user's threshold, else the card names the failing classes; labels keep their origin (`sam3`, `vlm+sam3`, model).
- **Why it is easy:** promotion becomes one table against a threshold the user owns, not two mAP numbers computed on different data.
- **Products with it:** SAM 3's pipeline is this loop at scale — AI annotators propose, AI verifiers check, active mining spends the humans (https://docs.ultralytics.com/models/sam-3/); Ultralytics documents auto-annotation from class names as the fast path to a dataset a small YOLO then trains on (same page).
- **Why it matters for LabelDesk:** auto-label, review, version, train and leaderboard all exist; teacher-versus-student is the one artefact that proves the distillation worked.
- **LabelDesk code evidence:** `adapters/refine.py:68-73` (annotations stamped `sam3`, `vlm+sam3`, model), `routers/training.py:164` (leaderboard over trained models on the project eval set, no teacher reference), `services/versioning.py:95-185` (version as training input).
- **Suggested status:** PARTIAL — every step exists; no cross-model agreement artefact.
- **Suggested priority / size:** Should / M.

### G4.15 Synthetic and composited fills for a rare class, with provenance
- **What the user does:** picks a thin class, asks for N extra examples, and gets train-only images built from real crops or a rendered scene, each tagged `synthetic` with its recipe and source ids.
- **Who uses it:** a defect team with 40 images of a scratch that must not be confused with a dent.
- **Flow:** 1. Coverage report → thin class → "Add examples". 2. Method: paste (needs polygons) or render job (assets, camera and light ranges). 3. `[loading]` generated/accepted; `[error: class has no polygon labels — paste needs masks]`. 4. Preview strip with boxes, reject or regenerate. 5. Accept → next version's train split only, tagged and in the manifest; filter `provenance:synthetic` lists them later.
- **Why it is easy:** a generated image carries its own perfect label, so cost per example is a render second rather than a labelling minute — and the tag keeps the audit honest.
- **Products with it:** Omniverse Replicator randomises assets, materials, lights and cameras and writes ground-truth annotators to disk, naming the appearance and content gap as the two risks (https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html); Ultralytics ships copy-paste augmentation aimed at rare classes, polygon-only, IoA < 0.3 (https://docs.ultralytics.com/guides/yolo-data-augmentation/).
- **Why it matters for LabelDesk:** version-time augmentation is flips, rotation, brightness, blur and noise — it cannot create an instance of a class that is not in the image, which is the only thing a thin class needs.
- **LabelDesk code evidence:** `services/imaging.py:189-238` (geometric/photometric only), `services/versioning.py:130-172` (applies them, `copies` per example); no provenance field on `models/project.py:86-110` (searched `synthetic`, `copy_paste`, `generate`).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / L.

### G4.16 Harvest the boxes the checker rejected as hard negatives
- **What the user does:** opens the post-batch report, inspects the rejected crops, exports a negative pack ("not Helmet" plus a JSON list), trains with it, and reads per-class deltas on the model card.
- **Who uses it:** a team whose model keeps boxing the same wrong object — a bottle that reads as a helmet — despite more positives.
- **Flow:** 1. Job report → "Rejected by checker: 412" → Inspect. 2. Crop grid with the phrase asked and the near-miss class. 3. Tick the systematic ones → "Add as hard negatives" (stored per project with source ids). 4. Train options show "hard negatives: 380"; after training a per-class line reads "Helmet FP −18%".
- **Why it is easy:** the rejection already happened and cost money; keeping the crop is the only step between a wasted call and a better model.
- **Products with it:** Meta's SAM 3 ablations report 0 → 30 hard negatives per image lifts image-level recognition (IL_MCC 0.44 → 0.68) (https://docs.ultralytics.com/models/sam-3/); YOLO-World documents an empty-string background class to suppress spurious detections (https://docs.ultralytics.com/models/yolo-world/).
- **Why it matters for LabelDesk:** the checker throws the evidence away, and false positives on look-alike parts are the commonest PPE complaint.
- **LabelDesk code evidence:** `adapters/refine.py:150-152`, `:167-173` (rejections not recorded), `:124-125` (out-of-list label skipped silently); no negative store in `models/` (searched `negative`, `hard_negative`).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Could / S.

---

## 4.5 Agentic labelling and question answering

### G4.17 A labelling job the agent plans, trials, then escalates
- **What the user does:** writes the job ("label helmets and vests on the night-shift batch, show me 20 images first"), approves or edits the plan, and returns to a report of what was labelled, escalated and spent.
- **Who uses it:** an ops lead who knows the outcome they want, not the model, prompt or threshold that produces it.
- **Flow:** 1. Batch board → "New job": one text box plus the batch. 2. Plan card: classes and prompts, model, review policy, trial size, cost — each row editable. 3. "Run trial" → 20 images, `[loading]`, yield table plus three samples. 4. Approve runs the batch; Revise updates the card. 5. Report: labelled, escalated, skipped with reasons, spend, and the plan as the audit record; escalations become an ordinary review batch with a named reviewer.
- **Why it is easy:** the trial is the negotiation, so nobody has to guess a threshold to find out whether their sentence was understood.
- **Products with it:** Encord runs catalog and custom agents from the label editor or as a workflow stage, with per-agent model, prompt and credential settings (https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-agents-catalog-reference.md); FiftyOne's agents take one prompt and run import, inference, duplicate-finding and curation as tools (https://docs.voxel51.com/agents/index.html); SAM 3 Agent lets an MLLM propose phrases and iterate against masks (https://docs.ultralytics.com/models/sam-3/).
- **Why it matters for LabelDesk:** parity 3-F3.30 is feedback on a preview; nothing plans a job, spends a budget or escalates, and our workflow blocks are deterministic and cannot label at all.
- **LabelDesk code evidence:** `services/workflows.py:67-100` (model, filter, crop, rule, ocr, sink — no planning, no escalation), `workflow_runner.py` runs a saved spec; no agent module in `routers/` (searched `agent`, `plan`, `escalat`); the only conversational surface is the batch prompt field (`AutoLabelDialog.tsx:235-243`).
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / L.

### G4.18 Ask the dataset a question in words
- **What the user does:** types "how many helmets are missing on night-shift images" or "show every pallet with no label", gets a number or a filtered grid, and sees the filter that produced it.
- **Who uses it:** a plant manager preparing a weekly review who does not know our filter syntax, and a reviewer checking a vendor's claim.
- **Flow:** 1. Dataset or Insights search box → "Ask" mode. 2. `[loading]` reading the schema; `[error: that needs image content, not labels — run a question set instead]` separates structural from visual questions. 3. Answer card: number, equivalent filter chips, counted images. 4. "Save as view" keeps the chips; visual questions are handed to G4.6 rather than guessed.
- **Why it is easy:** the answer arrives with its own filter, so a wrong answer is debuggable and a right one becomes a reusable view.
- **Products with it:** FiftyOne's curation and distribution agents answer natural-language questions and open the resulting view in the App (https://docs.voxel51.com/agents/index.html).
- **Why it matters for LabelDesk:** our query surface is 16 fixed parameters plus chips (parity 2-F2.27), and a manager has nowhere to ask in their own words — the commonest request in a Thai review meeting.
- **LabelDesk code evidence:** `routers/images.py:190-300` (fixed params), `features/project/Dataset.tsx:31-41` (URL-synced chips), `services/insights_query.py:25-30` (widget specs: source + measure + dimension, no language layer); `insights_embedding.py` feeds suspects, not search.
- **Suggested status:** MISSING.
- **Suggested priority / size:** Should / M.

---

## Already covered by PARITY.md (no card here)

- Per-class *description* rows and duplicate-description rejection — 3-F3.27; per-class *confidence*
  carried into the job, and keypoint threshold — 3-F3.29.
- Free preview on samples, and cost estimate with keep/merge/replace — 3-F3.28, 3-F3.32;
  conversational correction of a preview — 3-F3.30.
- Semantic search over unlabelled images and "more like this" — 2-F2.28, 2-F2.29; near-duplicate
  ranked search and pHash leakage guards — 2-F2.36, 2-F2.35.
- Active-learning rules form (threshold, sample %, include-empty) — 6-F6.19.
- Editor text prompt and foundation assist — 3-F3.22, 3-F3.23; score-coloured failure clusters —
  5-F5.25.

Deliberately out of scope: model fine-tuning UX (parity area 5), vendor-billed third-party AI keys
(7-F7.50), chat over project documents.

## Title-only / unverified

- Encord ontology pages, "Find Duplicate Images", "Embedding Plots", "SAM Segmentation & Tracking",
  "Compare Model Performance", "Consensus Workflows", "Label Sets (BETA)" — titles in
  https://docs.encord.com/llms.txt only; not used as evidence.
- FiftyOne enterprise skills ("auto-labeling", "data quality", "dataset discovery") are named as
  delegation targets in the agents index but their pages were not opened.
- Anyverse, Skyyork and other synthetic vendors — no page fetched; the synthetic card rests on
  Replicator plus Ultralytics copy-paste.
- Lightly / Encord Active — no page fetched; active-learning evidence is FiftyOne Brain and SAM 3
  active mining, both fetched.
- SAM 3.1 "~7× at 128 objects" is Meta's figure as repeated by Ultralytics, not measured here.
- Gemini model name/behaviour come from the fetched docs page; pricing and regional availability
  were not checked. Roboflow's own SAM/VLM blog posts were not opened (parity owns its rows).

## Counts

18 features: **0 HAVE · 9 PARTIAL · 9 MISSING.**

- PARTIAL: G4.1, G4.3, G4.4, G4.7, G4.8, G4.9, G4.10, G4.12, G4.14.
- MISSING: G4.2, G4.5, G4.6, G4.11, G4.13, G4.15, G4.16, G4.17, G4.18.
- Priority: **3 Must** (G4.1, G4.3, G4.4) · **11 Should** (G4.2, G4.5, G4.6, G4.8, G4.9, G4.10,
  G4.12, G4.13, G4.14, G4.17, G4.18) · **4 Could** (G4.7, G4.11, G4.15, G4.16).
- Size: **2 S** (G4.7, G4.16) · **13 M** · **3 L** (G4.11, G4.15, G4.17).

Reading: nothing is HAVE because each card needs a control we lack, and none is a model problem.
The three Musts are all auto-label and each is one field plus one surface: an exclusion/synonym list
on the class row, a review-band policy, and a verdict kept instead of a box deleted. The cheap wins
are G4.16 (rejected boxes) and G4.7 (caption to tags); the expensive ones are the agent (G4.17),
the prompt-free sweep (G4.11) and synthetic fill (G4.15).
