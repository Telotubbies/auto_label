# Area 3 — Annotation editor

Method: 30 pages fetched 2026-11-17 — `docs.roboflow.com/llms.txt` (index), then the `.md` variants under `/datasets/annotate/annotate/` (interface overview, tools, shortcuts, keypoints, skeletons, video segments, multimodal, AI labeling hub, Label Assist, Smart Select, Box Prompting, Auto Label, history, comments, show/hide, similarity search), `/datasets/annotate/annotation-groups`, `/datasets/annotate/annotate/{team-collaboration,manage-annotation-workflow,annotation-insights}`, `/datasets/manage/manage-datasets{,/manage-classes,/create-an-annotation-attribute,/manage-batches}`, three changelog entries (brush tool, multi-select, review-mode toggle), `roboflow.com/credits`, `roboflow.com/pricing`. Not opened: blog posts, the `/annotate/` marketing page, dataset-search, add-tags-to-images, Labeling Services. No login, no app screenshots, no scraping.

Screen names below are ours; Roboflow's own label appears only as `(RF: …)`.

## 3.1 Editor layout and entry

### F3.1 Opening the editor and what the shell is made of (RF: Labeling Interface)
- **What the user does:** picks an image from the project's assignment board or the dataset grid; a full-window editor opens on that image.
- **Flow:** 1. Project → *Annotate* board (four columns: unassigned, annotating, review, dataset) or the image grid. 2. Click a card → editor at `/:ws/:project/images/:imageId`. 3. Shell, clockwise: top header bar (back to project, previous/next image, image menu, approve/submit affordances); right-hand vertical **tool rail** (select, box, polygon, brush, smart polygon, empty-marking, AI assists); canvas in the middle; **left drawer** with stacked panels (annotation list, image facts, tags, history, comments); **bottom-left cluster** (zoom stepper + a sun icon opening the display popover). 4. The class picker appears in the right column the moment a shape is drawn or selected.
- **Why it is easy:** everything touched per image sits in two fixed strips, so the canvas never reflows, and the class picker lands where the tool rail already is.
- **Gates:** editor reachable on all plans; the review column needs the paid team add-on.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/manage/manage-datasets/manage-batches.md
- **LabelDesk hook points:** `apps/frontend/src/features/editor/Editor.tsx`, `apps/frontend/src/features/editor/Panels.tsx`

### F3.2 Pan, zoom, and zoom lock
- **What the user does:** zooms with the wheel or stepper, pans by dragging empty canvas, and can pin one zoom level that survives image changes.
- **Flow:** 1. Wheel or `+`/`-` → canvas scales; `0` fits to viewport, `1` jumps to 100%. 2. Drag background (in select mode) → pan; no pan modifier is documented for the drawing tools. 3. Stepper → pick a percentage → click the lock → "zoom lock", so every later image opens at that zoom; unlock to restore fit. 4. `meta`+`+`/`-`/`0` overrides browser zoom for the editor only.
- **Why it is easy:** zoom lock is the difference between inspecting 40 small defects at 400% and re-zooming 40 times.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.3 Image-to-image navigation and what carries over
- **What the user does:** steps through the job with the header arrows or the arrow keys; settings chosen on one image stay applied to the next.
- **Flow:** 1. `left`/`right` arrow or header arrows → previous/next image in the current job (classification projects need `cmd`/`meta` + arrow). 2. `esc` leaves the editor back to the board. 3. Sticky across images: display adjustments, zoom lock, the active segmentation engine, and Label Assist (the chosen model keeps predicting on each newly opened image). 4. Not documented as sticky: tool mode, multi-selection, comment panel state.
- **Why it is easy:** the labeler sets the assist and the contrast once per batch, not once per image.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/model-assisted-labeling.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.4 Display-only image adjustment plus overlay hide (RF: Display Options / Show and Hide Annotations)
- **What the user does:** brightens, adds contrast or gamma to inspect dark or flat images, and can hide every shape to look at the raw pixels — without touching the stored file, labels or exports.
- **Flow:** 1. Sun icon beside the zoom stepper → popover with brightness / contrast / gamma sliders and an "auto" contrast checkbox (auto normalises locally and disables the manual slider). 2. Same popover → show-annotations toggle, or press `h`. 3. While hidden, a notice above the canvas offers a "Show" button. 4. Adjustments persist to the next image; a reset button in the popover restores defaults.
- **Why it is easy:** inspection-only controls remove the fear of corrupting a dataset, persistence removes the setup cost per image, and one key exposes the pixels under a box.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/show-and-hide-annotations.md

### F3.5 Real-world measurement overlay (RF: Measurement Guide)
- **What the user does:** drops two pairs of guide lines over the image and reads width/height in mm, cm, m, in or ft.
- **Flow:** 1. Ruler button next to display options → guide panel. 2. Under "scale", enter pixels per known length + unit (blank = pixels only). 3. Enable the guide, or `shift`+`m` → two dotted line pairs. 4. Drag the tabs outside the image, drag a width/height label to move a pair, or arrow-key a selected tab (10 px with `shift`). 5. Scale is stored in the browser, not in the project.
- **Why it is easy:** defect-size checks on PCB or IC data can be judged in millimetres without an export round trip.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.6 Left drawer: annotation list, tags, image facts
- **What the user does:** reads which classes are present, their colours and layering, without hunting on the canvas.
- **Flow:** 1. Annotation-list panel: per-image shapes in draw order with class colour chips. 2. Tags panel: free-form image tags used later for dataset filtering. 3. Facts panel: dimensions, last-modified time, and the split the image belongs to (train/valid/test).
- **Why it is easy:** the class list answers "did I get all four?" faster than counting boxes.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.7 Look-alike search from inside the editor (RF: Similarity Search)
- **What the user does:** from the open image, finds visually similar unassigned images to label next, or similar approved images to copy a decision from.
- **Flow:** 1. Image menu (three dots in the header) → "find similar unassigned" or "find similar in dataset". 2. A thumbnail strip or grid of neighbours appears. 3. The same menu holds: view source image (eye-with-slash, hides boxes), use as cover photo, remove from project. 4. `[loading]` while neighbours are searched; `[empty]` when nothing passes the threshold (inferred).
- **Why it is easy:** near-duplicate frames are the cheapest labels, and this keeps the labeler moving forward instead of back to a grid.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/similarity-search-and-settings.md

## 3.2 Tools, one by one

Documented tools are exactly: select, box, polygon, brush mask, smart polygon / smart select, empty-marking, keypoint editing inside the box tool, video segments, multimodal prefixes, plus the AI assists. There is **no documentation** for oriented boxes, polyline, ellipse, or a standalone point tool — treat those as absent-for-now (see Title-only).

### F3.8 Select, move, resize (RF: Drag and Select)
- **What the user does:** picks an existing shape, moves or resizes it, changes its class.
- **Flow:** 1. `d` or the hand icon → select mode. 2. Single-click a box → white circular handles on four corners and four edge midpoints. 3. Drag inside to move, drag a handle to resize; the class picker becomes live. 4. Drag background to pan; click background to deselect all. 5. Hold `meta` while in box/polygon mode to borrow the select tool for one click.
- **Why it is easy:** no mode switch is needed to fix a shape that already exists.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.9 Bounding box (RF: Bounding Box tool)
- **What the user does:** drags a rectangle around an object, then labels it.
- **Flow:** 1. `b` or the rectangular icon → crosshairs. 2. Press-drag-release → new box. 3. Class picker opens on the right: text field + filtered class list. 4. Type to filter, `up`/`down` to move the highlight, `enter` to commit. 5. `esc` cancels and deletes a just-drawn box; `backspace` deletes it when the field is empty (in practice twice).
- **Why it is easy:** create→label is one drag plus keystrokes, with no dialog round trip.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md

### F3.10 Polygon (RF: Polygon tool)
- **What the user does:** clicks a vertex chain around an irregular object and closes the ring.
- **Flow:** 1. `p` → crosshairs. 2. Click per vertex. 3. Close by clicking the first vertex again **or** double-clicking the last vertex. 4. Label via the class picker. 5. Select the polygon to edit; corner handles drag to reshape. Vertex add/remove gestures are not documented (inferred as drag-only).
- **Why it is easy:** two closing gestures cover both "I'm back at the start" and "I'm done" mental models.
- **Gates:** segmentation projects require polygon or mask; detection projects convert polygons to boxes automatically.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/annotate/annotate/annotation-tools.md

### F3.11 Brush / pixel mask (RF: Brush tool)
- **What the user does:** paints a pixel-accurate region, toggling between adding and subtracting.
- **Flow:** 1. `u` or the paint-brush icon (instance-segmentation projects). 2. On-canvas brush controls appear: size + add/subtract toggle. 3. Press-drag to paint. 4. Class picker labels the whole region. 5. A bounding box is drawn around each mask by default; a "mask boxes" switch in display options shows only the fill. 6. Convert to box/polygon/mask via the context menu (F3.20).
- **Why it is easy:** one tool covers holes, hair, foliage and transparency where a polygon would need dozens of vertices.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/reference/changelog/changelog/november-2025/annotate-segmentation-masks-with-a-brush.md

### F3.12 One-click mask (RF: Smart Select / Smart Polygon)
- **What the user does:** hovers, clicks once on an object, gets a mask, then refines by clicking.
- **Flow:** 1. Enable in the tool rail (`s`). 2. **Hover** any object → live mask preview before committing. 3. Click → initial mask + polygon. 4. Switch polygon complexity between convex-hull / smooth / complex. 5. Click **outside** the mask to grow it, click **inside** a wrongly included area to shrink it. 6. `enter` accepts. 7. For large objects, press-drag a box instead of clicking to seed. 8. `[loading]` = image being prepared; `[error]` = engine unavailable (inferred copy).
- **Why it is easy:** position-relative clicks replace positive/negative modifier keys, so a trackpad user never hunts for `shift`.
- **Gates:** interactive-AI credits — 1 credit ≈ 100 interactively labelled images vs 1,000 for batch auto-label.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/smart-select.md, https://roboflow.com/credits

### F3.13 Keypoints inside a box (RF: Keypoint tool)
- **What the user does:** places a class's skeleton points on an instance and marks each point's visibility.
- **Flow:** 1. Requires a keypoint project with a saved skeleton (F3.14). 2. Draw the box as usual — the skeleton appears inside at default positions. 3. Drag each point onto its joint. 4. Right-click a point → visible / occluded (rendered with an X) / deleted (not in frame). 5. Right-click the box → "edit keypoint visibility" for a checklist of all points.
- **Why it is easy:** visibility lives on the point, so the annotator never leaves the canvas to say "wrist is behind the crate".
- **Gates:** auto-label for keypoints accepts only a model trained on that dataset.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotate-keypoints.md

### F3.14 Skeleton definition screen (RF: Skeleton Editor)
- **What the user does:** defines points, edges, colours and default layout once per class.
- **Flow:** 1. Project settings → classes → "edit keypoints" on a keypoint-project class. 2. Click the canvas to place the first point, name it. 3. Select a point → create an edge to another point, set colour, or delete. 4. Repeat. 5. Save → the skeleton renders inside every new box of that class.
- **Why it is easy:** one graph definition drives every instance, so labelers cannot invent inconsistent joints.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/edit-keypoint-skeletons.md

### F3.15 Video timeline segments (RF: Video Segments / Action Recognition editor)
- **What the user does:** marks when an action starts and ends, on a per-class timeline row.
- **Flow:** 1. Open a video in an action-recognition project → player + multi-row timeline + class field + save status in the header. 2. Press-drag across the empty row → a segment is drafted. 3. Pick or type the class → a coloured bar lands in that class's row. 4. Autosave; the header must read "saved" before navigating away. 5. Refine: drag either bar edge, or move the playhead to a frame, right-click the segment, "set in" / "set out". 6. Each class gets its own row, so several actions overlap without clutter.
- **Why it is easy:** the row encodes the class, so the timeline answers "what overlaps what" with no dialog.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotate-video-segments.md, https://docs.roboflow.com/datasets/annotate/annotate/annotation-tools.md

### F3.16 Classification-only UI (RF: image-level labels)
- **What the user does:** assigns one tag (single-label) or several (multi-label) with no shapes at all.
- **Flow:** 1. Classification project → the editor shows the class list only; the documented supported annotation is "image-level labels only". 2. Click a chip → applied; multi-label accepts several. 3. Navigate with `cmd`/`meta` + arrow (plain arrows are reserved in this project type). 4. Later, image-grid thumbnails reveal applied labels on hover.
- **Why it is easy:** no drawing surface means one click per image, so the job is a swipe-through.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotation-tools.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md

### F3.17 Multimodal prefixes (RF: Multimodal projects)
- **What the user does:** answers a per-image question, or fills a `<PREFIX>` slot, instead of drawing.
- **Flow:** 1. Sidebar → classes & tags → "add" → enter a prefix, either `<TOTAL>`-style or a question such as "what is the total on this receipt?". 2. Add more with "+", then commit. 3. In the editor each prefix is a question with a per-image answer field.
- **Why it is easy:** the prompt is a first-class row, so VLM/VQA export is mechanical.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotate-multimodal-data.md

### F3.18 Empty vs untouched image (RF: Mark Null)
- **What the user does:** states "there is genuinely nothing here", distinct from "I haven't looked".
- **Flow:** 1. `n` or the null icon → image flagged as a negative sample. 2. `n` again on a null image still in the annotating queue flips it back to unannotated. 3. The same tool clears every annotation from an image.
- **Why it is easy:** background images become training signal instead of being skipped — exactly what a false-positive-prone defect model needs.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md

### F3.19 Undo, redo, repeat previous
- **What the user does:** reverts, re-applies, and clones the previous image's labels onto this one.
- **Flow:** 1. `meta`+`z` undo, `meta`+`shift`+`z` redo, scoped to the current image session. 2. In box / polygon / smart-polygon mode the tool rail exposes undo, redo and **repeat previous**, which re-creates the last image's annotations at identical coordinates.
- **Why it is easy:** on a fixed camera, repeat-previous turns a six-box image into six nudges.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.20 Multi-select and bulk context menu
- **What the user does:** grabs several shapes, then converts, reorders, merges or duplicates them.
- **Flow:** 1. `shift`+click, **or** drag a selection rectangle across the canvas. 2. Right-click a selected shape (or its three-dot menu) → the menu acts on the whole selection. 3. Actions: duplicate (boxes, polygons, keypoint skeletons), convert to box / polygon / mask / smart mask (re-runs segmentation per item), merge masks (union; inherits the primary selection's label and colour; only enabled when all selected shapes are masks), bring to front / forward / send backward / to back.
- **Why it is easy:** merge-masks solves "object split by an occluder" in one action instead of two overlapping polygons.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/reference/changelog/changelog/march-2025/select-multiple-annotations-in-roboflow-annotate.md

## 3.3 AI assistance inside the editor

### F3.21 Box suggestions on every image you open (RF: Label Assist)
- **What the user does:** picks a model once, and every image opened afterwards arrives pre-boxed.
- **Flow:** 1. Wand icon in the tool rail → picker with three tabs: foundation models, "your models", "public models" (a model must be starred in the public library to appear). 2. "Continue" → class step: all model classes ticked by default, uncheck unwanted ones, remap model class names onto project classes. 3. Segmentation projects also choose polygon vs pixel (RLE) output — the choice is remembered. 4. "Select classes" → assist activates on the current image. 5. It keeps running on each newly opened image. 6. Suggestions are editable and deletable like normal shapes; no per-class confidence control is documented here.
- **Why it is easy:** assist is a property of the session, not of each image, so the model runs while the human is still looking at the previous one.
- **Gates:** credits per image; not available on every project type.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/model-assisted-labeling.md, https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling.md

### F3.22 Prompt-on-open with a foundation model, then triage (RF: Label Assist → AI Models tab)
- **What the user does:** types a class plus a short visual description, gets raw suggestions, accepts or discards the lot.
- **Flow:** 1. Wand icon → foundation-model tab. 2. Pick a model (the default differs by plan; models the workspace cannot run are greyed with the reason; with no AI model available the dialog opens on "your models" instead). 3. Tick classes or "+ add class" without leaving the editor; each class gets a description field — the description is the prompt, the class name is what gets saved. 4. "Label with AI" → boxes appear as **suggestions, nothing saved**. 5. Correct: drag to move, drag a corner to resize, change its class, "delete selected box", or arrow through detections one at a time. 6. The primary button counts what is left; clicking saves them, or "discard suggestions" drops all. Existing annotations are untouched.
- **Why it is easy:** the accept control carries the count, so the user always knows the blast radius of one click.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/model-assisted-labeling.md

### F3.23 Text prompt on the open image (RF: Find Objects with AI)
- **What the user does:** asks for one class on the current image by name and description, reviews what is found, saves.
- **Flow:** 1. Tool-rail button → model picker (box-only models vs a mask model; only the mask model exposes a confidence slider, because box models return everything at full confidence). 2. Type class name + description; an empty description searches the class name. 3. "Find objects" → `[loading]` → shapes on canvas. 4. Review, then save or dismiss. 5. The whole button is hidden when class locking is on, since free text could mint a class.
- **Why it is easy:** description-as-prompt ("green umbrella" filed under "umbrella") covers open-vocabulary cases without a second taxonomy.
- **Gates:** credits; disabled when classes are locked.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/manage/manage-datasets/manage-classes.md

### F3.24 Example-box "find all similar" that learns while you work (RF: Box Prompting)
- **What the user does:** boxes one or two examples per class and the tool proposes every other match on the image.
- **Flow:** 1. Draw at least one box. 2. Activate the tool → predictions appear as **dotted** shapes, regenerating on every annotation save or delete. 3. Confidence slider trades recall for precision. 4. Right-click a wrong proposal → "convert to negative" (shaded), which teaches the model; existing annotations can be flipped to negative the same way. 5. Add more positive examples → "predict" refreshes. 6. "Approve predictions" freezes them into annotations, otherwise they are dropped on navigation. 7. The tool menu reports how many images have joined the training set — only human-drawn or human-edited annotations count.
- **Why it is easy:** negative examples kill systematic false positives on a tray of identical parts, and the documented advice is to lower confidence and negate rather than raise the threshold.
- **Gates:** credits; downscales internally and warns above ~2000 px when boxes are under ~5% of the frame.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/box-prompting-ai-labeling.md

### F3.25 Proposal vs committed label is a visible distinction
- **What the user does:** can tell at a glance which shapes are committed and which are still proposals.
- **Flow:** proposals render with dashed outlines (box prompting) or sit behind an accept/discard bar (foundation-model assist, text-prompt search); committed shapes are solid, appear in the annotation drawer, and show confidence only where the model reports it.
- **Why it is easy:** the contract "dashed = not mine yet" prevents half-accepted label sets reaching the dataset.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/box-prompting-ai-labeling.md, https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/model-assisted-labeling.md

## 3.4 Auto-label at dataset scale

### F3.26 Entry, model catalogue, output format (RF: Auto Label)
- **What the user does:** chooses what labels a whole batch.
- **Flow:** 1. After upload the project asks how to label → "auto-label and review" (also reachable from the board). 2. Config screen: a model dropdown mixing foundation models, workspace-trained models and saved workflows; incompatible entries are greyed with a reason. 3. Where a model supports several shapes, a control beside the name picks masks vs polygons; the choice is remembered per project and echoed in the summary modal. 4. Defaults differ by plan and project type.
- **Why it is easy:** one dropdown unifies "zero-shot", "my trained model" and "my pipeline", so users learn one flow instead of three.
- **Gates:** does not work on semantic-segmentation projects; keypoint projects accept only a trained keypoint model.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.27 Classes as prompts with per-class descriptions
- **What the user does:** lists the classes to find and, per class, one line of visual description.
- **Flow:** 1. Class rows in the config panel; description defaults to the class name. 2. The description is what the model searches for; the class name is what gets written. 3. Two classes sharing a description are rejected before preview or job start. 4. Trained models ignore descriptions and use their own classes.
- **Why it is easy:** the prompt is editable where the class lives, so there is no separate prompt file to keep in sync.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.28 Free preview on sample images before spending
- **What the user does:** sees what the model finds on a few images before committing credits.
- **Flow:** 1. A preview runs automatically on a few sample images. 2. "Run again" after changing model or classes. 3. Thumbnail strip → click another sample; "change" → pick different images from the batch. 4. All test results are free and use no credits. 5. `[loading]` per sample.
- **Why it is easy:** the spending decision is made on evidence rather than on a model name.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.29 Per-class confidence threshold that carries into the job
- **What the user does:** tunes how strict each class is, knowing the preview setting becomes the job setting.
- **Flow:** 1. Each class row has a slider; higher = fewer labels. 2. Preview labels show their confidences. 3. The chosen threshold is carried into the batch job, and the UI says so. 4. Models returning everything at full confidence, and similarity-scored classifiers, have no slider; keypoint projects get a second "keypoint threshold" slider (default 60%) after the preview loads.
- **Why it is easy:** one threshold, one screen, no re-preview round trip to make it stick.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.30 Correcting the preview in words (feedback loop)
- **What the user does:** tells the system what the preview got wrong and gets a revised preview.
- **Flow:** 1. Click a preview label → "wrong class" / "shouldn't detect this" / "keep this detection". 2. "Flag missing object" → click the object → optional note → "update preview". 3. The agent adjusts the labelling workflow and re-runs the preview. 4. "Label batch" then runs with the adjusted workflow.
- **Why it is easy:** it turns "this prompt doesn't work" into a fixable request without the user learning workflow blocks.
- **Gates:** needs workflow-management permission and the agent enabled for the workspace.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.31 Saved-workflow source with explicit class mapping
- **What the user does:** runs a saved pipeline as the labeller and maps its output classes onto project classes.
- **Flow:** 1. Pick a workflow from the same dropdown (only type-compatible ones listed). 2. Map each workflow output class → project class, with a per-class confidence. 3. A preview confirms the mapping. 4. Unmapped outputs are silently dropped, and the UI warns to map everything wanted. 5. Or "chat with the Auto Label agent" to build the workflow from your model and classes, iterate on the preview, then "use this workflow". 6. The chat is saved per batch: leave and resume, or start a new chat.
- **Why it is easy:** class mapping is a table rather than an ontology file, and dropped classes are called out before the job, not after.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.32 Cost estimate and existing-annotation policy before the job
- **What the user does:** confirms an itemised cost and decides what happens to labels already present.
- **Flow:** 1. "Label batch" → summary modal. 2. Cost lines: credits per image plus, where applicable, model token usage estimated from recent test results (or the model average when there are none). 3. If the estimate exceeds remaining spend, the job refuses to start. 4. Second, mandatory-for-partial-batches decision: keep existing / merge (adds only predictions that don't overlap an existing same-class annotation at IoU ≥ 0.5) / replace. 5. Confirm → job starts.
- **Why it is easy:** the two questions that ruin a batch — "how much" and "did I just delete work" — are asked in one modal, with merge as the safe default.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.33 Background progress, then ordinary review
- **What the user does:** leaves the job running and comes back to review it as normal annotation work.
- **Flow:** 1. After start the user is dropped on the board, where the job appears as a card beside the others. 2. Runs in the background (a thousand images ≈ a few minutes). 3. Results land in an annotation job assigned to the chosen reviewer, so review-mode rules apply. 4. Afterwards: per-job bulk approve all / reject all, and per-image decisions.
- **Why it is easy:** auto-label output is never "already in the dataset"; it is queued work like a colleague's, which keeps the trust boundary intact.
- **Gates:** reviewer must be a workspace member.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md, https://docs.roboflow.com/datasets/annotate/annotate/team-collaboration.md

### F3.34 Video auto-label with frame sampling
- **What the user does:** auto-marks action segments across a batch of videos.
- **Flow:** 1. Open a video batch → auto label. 2. Select actions and add a one-line description of when each happens. 3. "Sample FPS" 0.5–12, default 8 (higher catches short actions, costs more). 4. Optional: drag a range of up to 30 s on the timeline → "run preview" (costs credits, saves nothing). 5. "Annotate all videos" → confirm cost → start. 6. The job replaces existing segments in those videos; the reviewer approves each segment; videos may be up to 30 minutes.
- **Why it is easy:** the preview range is bounded in time, the unit a video reviewer already thinks in.
- **Gates:** credits per frame seen plus token usage.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

## 3.5 Classes and attributes

### F3.35 Class picker with create-in-place
- **What the user does:** labels a shape, filtering as they type, or mints a class on the spot.
- **Flow:** 1. New or selected shape → right-column picker: text field, save/discard buttons, class list with the active row highlighted, plus a "create class" row when the typed text matches nothing. 2. `up`/`down` move the highlight, `enter` saves, `esc` abandons (deleting a just-drawn shape). 3. Creating a class here adds it project-wide.
- **Why it is easy:** class discovery happens during labelling rather than in a settings detour.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.36 Class administration: rename, merge, delete, lock
- **What the user does:** cleans up the taxonomy across every image at once.
- **Flow:** 1. Project settings → classes tab, checkbox rows. 2. Rename → edit names → "review changes" (old vs new diff) → "confirm changes"; renaming two classes to the same name **is** the merge mechanism. 3. Delete → confirmation list → irreversible, removes every annotation of that class. 4. Lock classes → nobody can add a class; the free-text prompt tool and the class-minting field disappear, while a per-class "prompt with the segmentation model" shortcut stays.
- **Why it is easy:** merge-by-rename with a diff preview is a low-drama fix for duplicate classes ("car" / "vehicle").
- **Gates:** changes apply to every image, not to one dataset version.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/manage-classes.md

### F3.37 Class colour, counts and hotkeys — confirmed vs unknown
- **What the user does:** reads the image by class colour and switches classes by key.
- **Confirmed:** each class has one colour, shown in the class list, the annotation drawer and on-canvas shapes; class names are alphanumeric plus `-`.
- **Not documented:** per-class image counts inside the editor, number-key class selection, and a colour picker. RF's behaviour here is unverified (our build has number-key selection and counts already).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/manage/manage-datasets/manage-classes.md

### F3.38 Per-class annotation attributes (RF: Annotation Attributes, "subclasses")
- **What the user does:** attaches structured extra facts to a shape, e.g. defect severity.
- **Flow:** 1. Classes & tags page → plus icon in that class's attributes column → name it → save. 2. The attribute tag shows next to the class. 3. In the editor, with a shape selected, the attribute field appears in the class picker. 4. Remove later: hover the tag, click the cross, confirm — existing values on annotations are retained.
- **Why it is easy:** attributes ride on the class, so a labeler only sees fields that are valid for that class.
- **Gates:** Enterprise only; exported only in COCO / COCO-segmentation.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/create-an-annotation-attribute.md

### F3.39 Image tags
- **What the user does:** adds free-form tags per image for later filtering.
- **Flow:** 1. Tags panel in the editor drawer, or from the dataset grid. 2. Add/remove tags. 3. Tags drive dataset filters and appear in exports.
- **Why it is easy:** gives triage vocabulary ("blurry", "re-shoot") without polluting the class list.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/manage/manage-datasets.md

### F3.40 Shared class sets and labels across projects (RF: Annotation Groups)
- **What the user does:** lets two projects share one class list and one set of annotations for the same image.
- **Flow:** 1. At project creation, tick "share image annotations with other projects" and pick or type a group name. 2. Images added later that exist in another project of the same group inherit annotations. 3. A chain-link icon appears next to the image in the editor, on asset-library previews and on the project list; hovering lists the projects that share it. 4. Editing an annotation in one project changes it everywhere in the group.
- **Why it is easy:** one image is stored, counted and labelled once even when it feeds two different detectors.
- **Risk:** edits propagate, so the editor must make the shared state loud — which is what the chain-link icon is for.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotation-groups.md

## 3.6 Objects list and layers

### F3.41 Layering through the annotation list and the context menu
- **What the user does:** changes which shape paints on top, and can see the current order.
- **Flow:** 1. Left annotation drawer lists shapes in paint order. 2. Select one or many → right-click → bring to front / forward / backward / to back, applied to the whole selection.
- **Why it is easy:** overlapping defects (a scratch inside a dent) stay readable without moving geometry.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.42 Hiding and removing shapes — what exists and what does not
- **Confirmed:** global overlay hide (`h`), source-image toggle in the image menu, and deleting a shape from the class picker (`backspace` while its text field is empty).
- **Not documented:** per-object hide / lock / occluded toggles inside the annotation drawer (competitors ship these; RF's drawer is described only as classes present, colours and layering). Our build has per-row hide/lock — keep it, but do not claim RF parity there.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/show-and-hide-annotations.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

### F3.43 Duplicating a shape and carrying a set forward
- **What the user does:** copies one shape, or the whole previous image's set.
- **Flow:** 1. Select → context menu → duplicate (boxes, polygons, skeletons). 2. "Repeat previous" re-creates the last image's annotations in place. 3. Copy/paste of an individual shape between two images is **not documented**; repeat-previous is the documented mechanism and is all-or-nothing.
- **Why it is easy:** one button covers the fixed-camera case; everything else is a gap worth beating (see Coverage gaps).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md

## 3.7 Workflow around labelling

### F3.44 The four-column job board
- **What the user does:** sees and moves every batch through the pipeline.
- **Flow:** 1. Project → Annotate: unassigned → annotating → review → dataset. 2. Uploaded images start unassigned; assigning moves a batch to annotating (a partial assignment splits the remainder into a new unassigned batch). 3. Finished work goes to review, or straight to dataset when review is off. 4. Batch card menu: merge batches (the largest selected batch survives and absorbs the others; not across different source videos, not for managed review queues), delete batch (only while unassigned — move it back first).
- **Why it is easy:** the column an image sits in is the single source of truth, so "where is my data?" needs no report.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/manage-batches.md

### F3.45 Assigning work with instructions and notifications
- **What the user does:** hands a batch to one or more people with written instructions; they get told.
- **Flow:** 1. Assign-images tab → pick batch → "add instructions" → edit → "save instructions" (notes typed at upload prefill it). 2. Choose assignees (invite a teammate inline) → "assign images". 3. Assignees get a notification. 4. The jobs board filters by labeler; job detail shows remaining images and allows reassignment mid-job. 5. Inside a job's annotated tab: checkbox / drag / select-all → "send N to unannotated" or "add N to dataset"; a partial add leaves the job running with updated counts.
- **Why it is easy:** instructions travel with the batch, so rules are not in a chat message that scrolls away.
- **Gap:** deadlines and per-labeler quotas are not documented; the only quantity is images-per-job.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/team-collaboration.md

### F3.46 Reviewing: approve / reject per image
- **What the user does:** accepts or sends back each image at keyboard speed.
- **Flow:** 1. Open a batch in the review column → tabs: to do / approved / rejected. 2. In the editor `a` approves, `r` rejects, `u` undoes the last decision. 3. Per-image buttons plus per-job bulk approve all / reject all. 4. Rejected images return to the annotating column. 5. For labelers, `shift`+`a` becomes "submit for review" instead of "add to dataset".
- **Why it is easy:** three single-key decisions turn review into a fast scan rather than a form.
- **Gap:** a structured reject reason is **not documented** — feedback is at best free text.
- **Gates:** team add-on / enterprise; review actions need review permission.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/team-collaboration.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md

### F3.47 Turning review off for solo work
- **What the user does:** removes the review column so finished jobs land straight in the dataset.
- **Flow:** 1. Settings → project settings → switch review mode off. 2. Batches still in review prompt a confirmation, then move back to annotating. 3. Reversible at any time; needs the edit-workspace-settings permission.
- **Why it is easy:** a one-person project should not pay for a review step it never uses.
- **Sources:** https://docs.roboflow.com/reference/changelog/changelog/july-2025/option-to-disable-review-mode.md, https://docs.roboflow.com/datasets/annotate/annotate/team-collaboration.md

### F3.48 Pinned comments on the image
- **What the user does:** leaves a note at a specific spot and replies in a thread.
- **Flow:** 1. Comment button in the sidebar → comment mode. 2. Click the location → a composer opens → type → post. 3. The pin stays at those coordinates; the sidebar lists all threads. 4. Teammates reply; resolved comments can be deleted.
- **Why it is easy:** pointing at pixels beats writing "the third screw from the left".
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/comment-on-an-image.md

### F3.49 Per-image annotation history with revert
- **What the user does:** reads what changed on this image over time and rolls one version back.
- **Flow:** 1. "History" link in the editor sidebar → list of changes. 2. Three dots beside an entry → reveals a revert control → restores that version.
- **Why it is easy:** it answers "who changed this image" without a support ticket.
- **Gates:** premium (labeling history is listed as excluded from the entry plan).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/annotation-history.md, https://roboflow.com/pricing

### F3.50 Per-labeler and per-project label statistics
- **What the user does:** checks throughput and quality per person, not just totals.
- **Flow:** 1. Settings → manage users → annotation insights. 2. Filters: date range, project, labeler(s). 3. Columns: images labeled, unique images labeled, net annotations, added/removed/updated counts, model-assisted, marked-null, and with review enabled: approved, rejected (counts rejection **events**), approval rate (first-pass acceptance). 4. CSV export. 5. Time spent is explicitly not reported.
- **Why it is easy:** first-pass acceptance is the one number that separates "fast" from "good".
- **Gates:** team add-on / enterprise.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotation-insights.md

### F3.51 Keyboard reference, and no remapping
- **What the user does:** learns a fixed key scheme. No user-level remapping or shortcut editor is documented anywhere in the fetched pages (our build already stores per-user bindings).
- **Documented shortcuts as published:**

| Context | Keys | Action |
|---|---|---|
| No selection | `meta` (hold) | Temporarily swap select ↔ box/polygon |
| No selection | `b` / `p` / `d` / `s` / `n` / `u` | Box / polygon / select / smart polygon / mark-empty / brush |
| No selection | `h` | Show or hide all annotations |
| No selection | `+` `-` `0` `1` | Zoom in / out / fit / 100% |
| No selection | `meta`+`+` `meta`+`-` `meta`+`0` | Editor zoom, overriding browser zoom |
| No selection | `←` `→` | Previous / next image (classification: `cmd`+arrow) |
| No selection | `esc` | Exit the editor |
| No selection | `meta`+`z`, `meta`+`shift`+`z` | Undo, redo |
| No selection | `shift`+`a` | Add image to dataset, or open submit-for-review |
| Annotation selected | `↑` `↓` | Previous / next class in the picker |
| Annotation selected | `enter` / `esc` | Commit class / cancel (deletes a just-drawn shape) |
| Annotation selected | `backspace` | Delete the shape when the class text field is empty |
| Multi-select | `shift`+click, or rectangle drag | Select several annotations |
| Review mode | `a` / `r` / `u` | Approve / reject / undo last decision |
| Measurement | `shift`+`m` | Toggle the measurement guide |

- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md, https://docs.roboflow.com/datasets/annotate/annotate/team-collaboration.md
- **LabelDesk hook points:** `apps/frontend/src/features/editor/shortcuts.ts`

## 3.8 Editor states

### F3.52 Saving: silent autosave plus one explicit gate
- **What the user does:** mostly never presses save; two actions are explicit.
- **Flow:** 1. Shape edits persist as they happen — the video editor shows a "saved" status in the header and the docs tell users to wait for it; the image editor's persistence is inferred from the documented flows having no save button. 2. Explicit: `shift`+`a` appends the image to the dataset or opens submit-for-review. 3. Leaving with an unfinished draft annotation is not documented; assume uncommitted shapes vanish and design a dirty indicator.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotate-video-segments.md, https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md
- **LabelDesk hook points:** `apps/frontend/src/features/editor/Editor.tsx` (existing `dirty`/`saving` state)

### F3.53 Slow network, offline, decode failure
- Not documented in any fetched page. What the docs imply: the click-to-mask model runs in the browser, so its first use includes a model download and a per-image "preparing" phase; similarity search is a server round trip. Offline editing, image decode errors and retry behaviour are **unverified** — candidates for our own design.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/smart-select.md

### F3.54 Model unavailable
- **What the user does:** sees a disabled option with a reason instead of a failed run.
- **Flow (three documented instances):** 1. Assist model picker — models the workspace cannot run are greyed with the reason; with no AI model at all the dialog opens on the trained-models tab. 2. Auto label — a model whose blocks are disabled still lists, greyed with the reason, unselectable. 3. Cost estimate above remaining spend → the job does not start.
- **Why it is easy:** every "no" is shown before the click, inside the control that would have said yes.
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/model-assisted-labeling.md, https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label.md

### F3.55 Empty project, read-only image, two editors on one image
- **Empty project:** the board's unassigned column is empty and the editor is unreachable; no empty-state copy is documented.
- **Read-only:** an image opens read-only when its job is unassigned, has left the board, or is not assigned to the viewer; editing needs annotation permission. The state is documented, the visual is not.
- **Two editors:** the documented answer is organisational — assigning jobs to individuals exists so teammates don't "step on each other's work"; reassignment is job-level. No per-annotation lock, presence indicator or conflict UI exists, and annotation history (F3.49) is the only recovery path.
- **Why it matters:** all three states are ours to design; RF has no pattern worth copying beyond "grey it out and say why".
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/team-collaboration.md

## Title-only / unverified

- Oriented/rotated boxes, polyline, ellipse, standalone point tool: no page in the docs index, no mention in any fetched page. Recorded as absent from the **documented** editor, not as impossible.
- Per-class hotkeys, per-class image counts in the editor, class colour customisation: not documented.
- Structured reject reasons, deadlines, per-labeler quotas, review SLAs: not documented.
- Copy/paste of a single annotation between two images: not documented (repeat-previous is).
- Offline mode, decode-error handling, concurrent-edit conflict UI: not documented.
- "Text Prompting" toolbar tool and a per-class "prompt with the segmentation model" icon appear only as names inside the class-locking paragraph; the page that would document them was not found.
- Plan attribution is inconsistent between sources: the pricing comparison lists review mode, labeling analytics and labeling history as excluded from the entry plan, while the team add-on doc sells them as an add-on to it. Treat as approximate.

## Coverage gaps and what to check next

1. Polygon vertex add/remove and mask edge dragging — no page states the gesture; needs an app-side check or a video.
2. Whether the editor-level assist exposes any confidence threshold (auto label does; the assist page does not mention one).
3. The image editor's unsaved-changes story: dirty marker, navigation guard, conflict on leave. Biggest UX unknown, directly relevant to our `dirty`/`saving` handling.
4. Whether reviewers can attach a reason, note or shape to a rejection.
5. How the annotation drawer behaves above a few hundred shapes — virtualisation, class filtering, bulk delete. RF documents the drawer's contents but not its scale behaviour.
6. Latency and failure states of the in-browser segmentation model: first-click spinner, model download, no-GPU fallback.
