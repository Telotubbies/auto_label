# Part 3 — Area 3 Annotate

Gap rows: 40 (23 PARTIAL, 17 MISSING) · Cards: 52 · Hours: 148

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 3-F3.1 | HAVE | wave E band (T-470–T-509); guard T-001 | E | — | — |
| 3-F3.2 | PARTIAL | T-120 | A | S | 3 |
| 3-F3.3 | PARTIAL | T-120 | A | S | 0 (bundled with 3-F3.2) |
| 3-F3.4 | PARTIAL | T-138 | B | S | 2 |
| 3-F3.5 | MISSING | T-161 | B | S | 3 |
| 3-F3.6 | PARTIAL | T-161 | B | S | 0 (bundled with 3-F3.5) |
| 3-F3.7 | MISSING | T-162 (on area 2's T-088) | B | S | 2.5 |
| 3-F3.8 | PARTIAL | T-123, T-124 | A | M | 6 |
| 3-F3.9 | HAVE | — · guard T-002 | — | — | — |
| 3-F3.10 | PARTIAL | T-125 | A | M | 3 |
| 3-F3.11 | MISSING | T-133, T-134, T-135 | B | L | 9 |
| 3-F3.12 | HAVE | — · guard T-002 | — | — | — |
| 3-F3.13 | HAVE | — · guard T-002 | — | — | — |
| 3-F3.14 | PARTIAL | T-149 | B | M | 3 |
| 3-F3.15 | MISSING | T-146, T-147, T-148 | B | L | 8.5 |
| 3-F3.16 | PARTIAL | T-126 | A | S | 2 |
| 3-F3.17 | MISSING | T-166, T-167, T-168 | C | L | 8 |
| 3-F3.18 | MISSING | T-127 | A | S | 3 |
| 3-F3.19 | PARTIAL | T-122 | A | S | 0 (bundled with 3-F3.43) |
| 3-F3.20 | PARTIAL | T-136, T-137 | B | M | 5.5 |
| 3-F3.21 | PARTIAL | T-139, T-140 | B | M | 6 |
| 3-F3.22 | MISSING | T-150, T-151, T-152 | B | L | 9 |
| 3-F3.23 | MISSING | T-153 | B | M | 3 |
| 3-F3.24 | MISSING | T-154, T-155 | B | L | 6 |
| 3-F3.25 | HAVE | — · guard T-003 | — | — | — |
| 3-F3.26 | PARTIAL | T-141 | B | M | 3 |
| 3-F3.27 | PARTIAL | T-130 | A | S | 3 |
| 3-F3.28 | HAVE | — · guard T-007 | — | — | — |
| 3-F3.29 | PARTIAL | T-130 | A | M | 0 (bundled with 3-F3.27) |
| 3-F3.30 | MISSING | T-156, T-157 | B | L | 6 |
| 3-F3.31 | MISSING | T-158 | B | M | 3 |
| 3-F3.32 | PARTIAL | T-131, T-132 | A | M | 5.5 |
| 3-F3.33 | HAVE | — · guard T-004 | — | — | — |
| 3-F3.34 | MISSING | T-159, T-160 | B | L | 6 |
| 3-F3.35 | HAVE | — · guard T-005 | — | — | — |
| 3-F3.36 | PARTIAL | T-169 | C | M | 3 |
| 3-F3.37 | HAVE | — · guard T-005 | — | — | — |
| 3-F3.38 | MISSING | T-170 | C | M | 3 |
| 3-F3.39 | HAVE | — · guard T-006 | — | — | — |
| 3-F3.40 | MISSING | area 1 band (T-010–T-059) | C | L | — |
| 3-F3.41 | HAVE | — · guard T-006 | — | — | — |
| 3-F3.42 | HAVE | — · guard T-006 | — | — | — |
| 3-F3.43 | MISSING | T-122 | A | S | 2.5 |
| 3-F3.44 | HAVE | — · guard T-004 | — | — | — |
| 3-F3.45 | PARTIAL | T-142, T-143 | B | M | 5.5 |
| 3-F3.46 | PARTIAL | T-128, T-129 | A | M | 5.5 |
| 3-F3.47 | MISSING | T-165 | B | S | 2.5 |
| 3-F3.48 | PARTIAL | T-171 | C | M | 3 |
| 3-F3.49 | PARTIAL | T-144, T-145 | B | M | 5.5 |
| 3-F3.50 | HAVE | — · guard T-007 | — | — | — |
| 3-F3.51 | HAVE | — · guard T-006 | — | — | — |
| 3-F3.52 | PARTIAL | T-121 | A | S | 3 |
| 3-F3.53 | MISSING | T-163 | B | M | 3 |
| 3-F3.54 | PARTIAL | T-131, T-140, T-141 | B | S | 0 (folded into three cards) |
| 3-F3.55 | PARTIAL | T-164 + T-121 | B / A | M | 2.5 |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/frontend/src/features/editor/Editor.tsx` | T-120, T-121, T-122, T-124, T-125, T-126, T-127, T-128, T-135, T-136, T-137, T-138, T-139, T-140, T-145, T-149, T-151, T-152, T-153, T-155, T-157, T-161, T-162, T-163, T-164, T-165, T-167, T-169, T-170, T-171 |
| `apps/frontend/src/lib/api/dataset.ts` | T-121, T-126, T-127, T-128, T-129, T-130, T-131, T-137, T-139, T-140, T-142, T-143, T-144, T-146, T-148, T-150, T-153, T-154, T-155, T-156, T-158, T-159, T-162, T-164, T-165, T-166, T-168, T-169, T-171 |
| `apps/frontend/src/lib/types.ts` | T-121, T-126, T-127, T-128, T-129, T-130, T-133, T-139, T-140, T-142, T-143, T-144, T-146, T-149, T-150, T-151, T-153, T-154, T-156, T-157, T-158, T-159, T-161, T-162, T-164, T-166, T-167, T-170, T-171 |
| `apps/frontend/src/features/editor/shortcuts.ts` | T-120, T-122, T-124, T-126, T-128, T-135, T-136, T-138, T-151 |
| `apps/frontend/src/features/project/AutoLabelDialog.tsx` | T-130, T-131, T-132, T-141, T-157, T-158 |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | T-129, T-132, T-142, T-143, T-164, T-165 |
| `apps/frontend/src/features/project/Classes.tsx` | T-149, T-168, T-169, T-170 |
| `apps/frontend/src/features/project/VideoTimeline.tsx` | T-147, T-148, T-160 |
| `apps/frontend/src/features/project/ProjectSettings.tsx` | T-126, T-165 |
| `apps/backend/app/routers/images.py` | T-121, T-127, T-128, T-129, T-133, T-137, T-150, T-153, T-154, T-161, T-162, T-164, T-166, T-170, T-171 |
| `apps/backend/app/routers/training.py` | T-130, T-131, T-139, T-141, T-156, T-158 |
| `apps/backend/app/routers/projects.py` | T-149, T-165, T-169, T-170 |
| `apps/backend/app/routers/segments.py` | T-146 (created), T-148, T-159 |
| `apps/backend/app/routers/prompts.py` | T-166 (created), T-168 |
| `apps/backend/app/services/flags.py` | T-133, T-139, T-146, T-150, T-154, T-156, T-159, T-162, T-165, T-166, T-169, T-170 |
| `apps/backend/app/services/refine.py` | T-130, T-141, T-158 |
| `apps/backend/app/services/exporters.py` | T-134, T-170 |
| `apps/backend/app/services/versioning.py` | T-134 |
| `apps/backend/app/models/__init__.py` | T-139, T-144, T-146, T-166 |
| `apps/backend/app/routers/__init__.py` | T-146, T-166 |
| `apps/backend/app/handlers/__init__.py` | T-159 |
| `apps/backend/app/schema/dataset.py` | T-127, T-142, T-170, T-171 |
| `apps/backend/app/schema/__init__.py` | T-142, T-171 |
| `apps/backend/app/services/labeling_ops.py` | T-144, T-164 |
| `apps/backend/app/openapi.json`, `apps/frontend/src/lib/api-types.gen.ts` | every card that changes a route or a schema — regenerate last on the branch |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-120 | Zoom, zoom lock, and a sticky editor session | A | 3 | R4 | no | `viewport.ts`, `editorSession.ts` |
| T-121 | Honest saving: flush before leaving, refuse a stale write | A | 3 | R4+R3 | no | `saveGuard.ts` |
| T-122 | Duplicate a shape, or repeat the previous image's labels | A | 2.5 | R4 | no | `repeat.ts` |
| T-123 | Geometry module for moving polygons, rotated boxes and keypoints | A | 3 | R4 | no | `geometry.ts` |
| T-124 | Canvas handles: drag a polygon, a rotated box, a joint | A | 3 | R4 | no | `ShapeTransformLayer.tsx` |
| T-125 | Add, remove and drag polygon vertices | A | 3 | R4 | no | `polygonEdit.ts` |
| T-126 | Classification single- vs multi-label is reachable | A | 2 | R4+R3 | no | `NewProjectForm.tsx`, `newProjectModel.ts` |
| T-127 | Mark an image empty (a real negative sample) | A | 3 | R4+R3 | no | `nullMark.ts` |
| T-128 | Review at keyboard speed: a, r, u | A | 2.5 | R4+R3 | no | `reviewKeys.ts` |
| T-129 | Bulk review asks first: count, classes, reason | A | 3 | R4+R3 | no | `BulkReviewSheet.tsx` |
| T-130 | One prompt and one threshold per class | A | 3 | R4+R3 | no | `ClassPromptRows.tsx` |
| T-131 | Estimate the spend, and choose what happens to existing labels | A | 3 | R3 | yes | `autolabel_plan.py` |
| T-132 | The auto-label summary sheet | A | 2.5 | R4 | no | `AutoLabelSummary.tsx` |
| T-133 | A mask is a first-class shape: storage and validation | B | 3 | R3 | yes | `masks.py`, `maskDecode.ts` |
| T-134 | Masks survive versions, training data and export | B | 3 | R3 | no | `mask_export.py` |
| T-135 | The brush: paint, subtract, and see the mask | B | 3 | R4 | no | `brush.ts` |
| T-136 | Select several shapes: shift-click and a marquee | B | 2.5 | R4 | no | `selection.ts` |
| T-137 | Convert, merge and re-order a whole selection | B | 3 | R4+R3 | no | `shape_convert.py`, `bulkOps.ts`, `ShapeContextMenu.tsx` |
| T-138 | Display-only adjustment and hide-all annotations | B | 2 | R4 | no | `display.ts` |
| T-139 | An assist session that follows you to the next image | B | 3 | R3 | yes | `models/assist.py`, `assist_session.py` |
| T-140 | Assist picker: three sources, a class mapping step | B | 3 | R4 | no | `AssistPicker.tsx` |
| T-141 | One model dropdown, one output shape | B | 3 | R4+R3 | no | `AutoLabelModelField.tsx` |
| T-142 | Instructions ride with the batch; assignment splits across people | B | 2.5 | R3 | yes | `assignments.py` |
| T-143 | The assign sheet, and managing a batch mid-flight | B | 3 | R4 | no | `AssignSheet.tsx` |
| T-144 | Every save leaves a revision you can roll back | B | 3 | R3 | yes | `models/revisions.py`, `revisions.py` |
| T-145 | The History panel reads real revisions and restores one | B | 2.5 | R4 | no | `HistoryRevisions.tsx` |
| T-146 | Action segments become data, not a drawing | B | 3 | R3 | yes | `models/segments.py`, `routers/segments.py`, `services/segments.py` |
| T-147 | A timeline with one row per class | B | 3 | R4 | no | `ActionTimeline.tsx`, `segmentMath.ts` |
| T-148 | Review action segments, then export them | B | 2.5 | R4+R3 | no | `segment_export.py`, `SegmentReview.tsx` |
| T-149 | Place a skeleton on a canvas, not in a textarea | B | 3 | R4+R3 | no | `skeletons.py`, `SkeletonEditor.tsx`, `skeletonDraft.ts` |
| T-150 | Ask a foundation model for boxes on this image | B | 3 | R3 | yes | `prompt_detect.py` |
| T-151 | Proposals are dashed, counted, and never silently saved | B | 3 | R4 | no | `proposals.ts`, `ProposalBar.tsx` |
| T-152 | The foundation-prompt dialog on the open image | B | 3 | R4 | no | `PromptDetectDialog.tsx` |
| T-153 | "Find the green umbrella" on this image | B | 3 | R4+R3 | yes | `FindObjectsPanel.tsx` |
| T-154 | Box prompting: example boxes propose the rest | B | 3 | R3 | yes | `box_prompt.py` |
| T-155 | The box-prompting controls: negatives, refresh, approve | B | 3 | R4 | no | `BoxPromptControls.tsx` |
| T-156 | Feedback the preview can act on | B | 3 | R3 | yes | `models/preview.py`, `preview_feedback.py` |
| T-157 | Correct the preview in words, then see the new preview | B | 3 | R4 | no | `PreviewFeedbackPanel.tsx` |
| T-158 | A saved workflow as the labeller, with an explicit class map | B | 3 | R4+R3 | yes | `WorkflowClassMap.tsx` |
| T-159 | Video auto-label: the job and its bounded preview | B | 3 | R3 | yes | `video_autolabel.py` (service and handler) |
| T-160 | Configure a video auto-label run, preview a range, then queue it | B | 3 | R4 | no | `VideoAutoLabelDialog.tsx`, `videoAutoLabelModel.ts` |
| T-161 | Measure in millimetres; read the image's facts | B | 3 | R4+R3 | no | `measure.ts`, `ImageFacts.tsx` |
| T-162 | The similar-images strip inside the editor | B | 2.5 | R4 | no | `SimilarStrip.tsx` |
| T-163 | A dropped connection keeps the work on this device | B | 3 | R4 | yes | `offlineQueue.ts` |
| T-164 | A read-only image says why; an empty project says what next | B | 2.5 | R4+R3 | yes | `ReadOnlyNotice.tsx` |
| T-165 | Turn review off for a one-person project | B | 2.5 | R4+R3 | yes | `review_mode.py`, `ReviewModeCard.tsx` |
| T-166 | Prompt slots and per-image answers | C | 3 | R3 | yes | `models/prompts.py`, `routers/prompts.py`, `services/prompts.py` |
| T-167 | Answer the project's questions in the editor | C | 2.5 | R4 | no | `AnswerPanel.tsx` |
| T-168 | Author the prompts, then export VQA rows | C | 2.5 | R4+R3 | no | `vqa_export.py`, `PromptAdmin.tsx` |
| T-169 | Rename with a diff, and lock the taxonomy | C | 3 | R4+R3 | yes | `class_admin.py`, `ClassEditSheet.tsx` |
| T-170 | Per-class attribute fields on a shape | C | 3 | R4+R3 | yes | `class_attrs.py`, `ClassAttributeFields.tsx` |
| T-171 | Comments pinned to a spot, with replies and resolve | C | 3 | R4+R3 | yes | `CommentPins.tsx` |

## Judgment calls
- `3-F3.54` → no card of its own: its three documented instances live in T-131 (cost refusal), T-140 (assist picker reasons) and T-141 (auto-label catalogue reasons). A fourth card would restate them.
- `3-F3.19` → T-122: undo/redo already exist and reset per image; repeat-previous is the only missing half, so it rides the duplicate card.
- `3-F3.55` → split across T-164 (read-only state, empty project; wave B) and T-121 (stale-write conflict; wave A, so data safety lands in the trial wave). The row is listed once, in B, with the A half named.
- `3-F3.2`/`3-F3.3` bundled into T-120 — both are session-scoped viewport/preference rules on one file and one test file, and the brief allows a tight A-wave bundle.
- `3-F3.5`/`3-F3.6` bundled into T-161 — two S details that both extend the editor's bottom bar and drawer and share one node test file.
- `3-F3.15`/`3-F3.34` → no new project type: segments attach to a video, so the work does not collide with area 1's project-type band; a type gate would duplicate that ownership.
- `3-F3.40` → area 1 band (T-010–T-059), per brief §4. No card here.
- `3-F3.1` → wave E band (T-470–T-509), per brief §4; guard T-001 asserts the shell.
- `3-F3.45` notification delivery → 7-F7.49 (area 7's sink). T-142 publishes one `board.assign` event and T-143 never claims a delivery channel.
- `3-F3.38` COCO `attributes` line touches `services/exporters.py`, which area 4 owns for formats — one appended key, flagged here so the merge reviewer sees the overlap.
- `3-F3.47` wave B (workflow/permission mechanics), not E: the outcome is who may approve, not a visual change.
- `3-F3.26` semantic-segmentation gate → no code: `PROJECT_TYPES` has no such type (`models/common.py:10`); T-141 pins the absence with a test.
- `3-F3.7` → T-162 is a **consumer** of area 2's work: `2-F2.29`'s T-088/T-087 own `services/similar.py`, the route and the menu; T-162 only adds the editor strip, so the ranking is not implemented twice.
- `3-F3.11` → mask geometry is vectorised when a version is built (T-134) and the bitmap stays on the image row; the shortcut is stated in the card rather than pretending bitmaps survive augmentation.
- Guard ids T-001…T-007 are this part's reading of the PM's guards band: T-001 editor shell/canvas, T-002 tools + geometry, T-003 proposal vs committed rendering, T-004 board/batches, T-005 class picker/ontology, T-006 objects drawer + keyboard/rebind, T-007 preview + labeling statistics.
