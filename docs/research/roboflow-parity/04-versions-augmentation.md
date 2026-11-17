# Area 4 — Versions, preprocessing, augmentation, export, version analytics

Method: 21 pages fetched 2026-11-17, `.md` variants: `llms.txt` (index);
`/datasets/versions/dataset-versions` + `/create-a-dataset-version` + `/delete-a-version` +
`/image-preprocessing` + `/image-augmentation` + `/image-augmentation/add-augmentations-to-images`
+ `/augmentation-types` + 14 `/augmentation-types/*` pages (flip, rotate, crop, rotation,
shear, grayscale, hue, saturation, brightness, exposure, blur, noise, camera gain, motion
blur, cutout, mosaic); `/exporting-data`; `/datasets/versions/dataset-health-check`;
`/models/train/train-a-model`; `roboflow.com/pricing`. Not opened: Trash, 90°-rotate,
grayscale and remap detail pages, credits, `download-a-dataset`, `dataset-search`,
`list-workspaces-and-projects`.

Wizard step labels marked **[inferred]** are reconstructed from the documented step numbers
(2 = split, 4 = augmentation, 5 = output size) plus flow text; steps 1 and 3 are not
described page by page.

## Version as a snapshot

### F4.1 Frozen point-in-time snapshot (RF: *Dataset Version*)
- **User:** freezes the current images, labels, splits, preprocessing and augmentation into one numbered, named object that training and export consume. Later project edits — new images, deleted images, edited boxes — never reach an existing version.
- **Flow:** 1. Project → Versions. 2. `[empty]` first visit shows a create prompt. 3. Version card → version page (splits, images, settings, exports, trainings). 4. Train or export there.
- **Why easy:** one object answers "which data plus which transforms produced this model", so comparisons are attributable instead of reconstructive.
- **Gates:** training needs a version; generation costs credits and an edit-capable role.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions.md, https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version.md
- **LD:** `apps/frontend/src/features/project/Versions.tsx`, `apps/backend/app/routers/versions.py`

### F4.2 Sequential number plus human name
- **User:** types an optional name; the system also assigns a project-scoped integer that never repeats and never changes.
- **Flow:** 1. Name field on the final wizard step. 2. `[empty]` unnamed → list shows a generated fallback label. 3. Rows show name + id; API and URLs use the number.
- **Why easy:** the number is the stable handle for scripts and support; the name is free text for humans (`augmented-640`) and can be edited later.
- **Sources:** dataset-versions.md (list payload, CLI list output); create-a-dataset-version.md.
- **LD:** `routers/versions.py` — `number` = max+1, fallback `name or f"v{n}"`.

### F4.3 Version index
- **User:** scans every version of the project to choose one to train, export, inspect or delete.
- **Flow:** each row shows id, name, image count, creation date, settings summary, existing exports and trainings. `[loading]` skeleton rows; `[error: request failed]` with retry.
- **Why easy:** all downstream artefacts (models, exports) are reachable from the version that produced them, so the list is the project history.
- **Gates:** listing is read-only; download links are withheld from roles without export rights.
- **Sources:** dataset-versions.md, delete-a-version.md.
- **LD:** `Versions.tsx`; `routers/versions.py` (`exports` map, signed URL gated on `project.export`).

### F4.4 Generation is an async job with progress
- **User:** starts generation and leaves the wizard; the version appears generating, then ready.
- **Flow:** 1. Generate → wizard closes, card in generating state. 2. `[loading]` progress on the card/page. 3. `[error: generation failed]` keeps a failed card so the request stays inspectable. 4. On success counts populate. 5. Long jobs survive closing the dialog (documented for split rebalancing: per-phase progress, dismissable, tracked in an activity centre).
- **Why easy:** generation is visibly background work, not a frozen request, and the outcome is reported even if the user navigates away.
- **Gates:** credits charged at creation; plan multiplier cap checked before the job starts.
- **Sources:** create-a-dataset-version.md, image-preprocessing.md.
- **Unverified:** the exact progress widget and any completion notification for **version** generation (email notification is documented for training only).

### F4.5 Delete with consequences stated up front (RF: *Trash*)
- **User:** opens a version, deletes it, types the version name to confirm, and moves it to trash.
- **Flow:** 1. Version page → edit → delete. 2. Confirm dialog requires typing the name. 3. Toast: moved to trash. 4. Restore any time within 30 days; permanent delete can be forced earlier from trash.
- **Why easy:** the destructive click is name-gated, and the consequences are listed before the click — in-flight training for that version is cancelled, every model trained from it stops serving until restore, and generated-image quota is **not** freed until permanent deletion.
- **Gates:** delete role; the parent project must be active to restore.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions/delete-a-version.md
- **LD:** `routers/versions.py` deletes bytes first then the row, 409 if files remain, no trash window.

### F4.6 Copy a version's recipe onto newer data (RF: *Reuse Preprocessing and Augmentations*)
- **User:** lifts preprocessing, augmentations, class remapping and tag filters from an old version onto the current dataset, then edits before generating.
- **Flow:** 1. Train screen → saved-version card → reuse. 2. Settings prefill the editable current-dataset path. 3. Generate.
- **Why easy:** retraining after new labels should not mean re-ticking twenty controls; the recipe travels, the data does not.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md

### F4.7 Saved-version settings are locked downstream
- **User:** trains on a saved version and finds the recipe's preprocessing and augmentation rows disabled, with a pointer to the version page.
- **Flow:** 1. Train → pick saved version. 2. Rows render locked with explanatory text. 3. The version page's training-recipe card shows what the model actually used.
- **Why easy:** it prevents the silent lie of "I changed augmentation at train time" when the pixels were already baked.
- **Sources:** train-a-model.md.

### F4.8 Several trainings per version
- **User:** runs different architectures and sizes against identical frozen data and compares them; the version page lists every run.
- **Flow:** version page → train → repeat with another architecture → switch between results.
- **Why easy:** comparisons are honest because the data cannot drift between runs.
- **Gates:** one concurrent training job by default on the consumer plan.
- **Sources:** train-a-model.md; roboflow.com/pricing.

## The creation wizard

### F4.9 Wizard shell: five numbered steps, all reachable
- **User:** configures a recipe across five steps in one surface; each step is a section, never a page that hides earlier choices.
- **Flow:** 1. Versions → new version. 2. Step strip: 1 source [inferred], 2 split, 3 preprocessing [inferred], 4 augmentation, 5 output size/confirm. 3. Generate. 4. Cancel closes without creating anything.
- **Why easy:** the recipe reads as a checklist, which shows at a glance that augmentation is optional and preprocessing is not.
- **Gates:** only the output-size step filters its options by plan.
- **Sources:** create-a-dataset-version.md, add-augmentations-to-images.md (steps 4 and 5), image-preprocessing.md (step 2).
- **LD:** `Versions.tsx` already uses the same five-step shape with tabs.

### F4.10 Step 1 — what enters the version
- **User:** confirms the pool before splitting. **[inferred]** the step states the count of labeled/approved images that will be frozen; subsetting happens through tag filters, filter-null and class omission rather than a dedicated image picker (all three are documented, none is tied to step 1).
- **Flow:** 1. Step 1 shows counts. 2. `[empty: nothing annotated yet]` blocks next with a path back to labeling. 3. Continue.
- **Why easy:** one number prevents "I thought I had 900 images" after a long generation.
- **Sources:** create-a-dataset-version.md, image-preprocessing.md.
- **LD:** `Versions.tsx` step 0 prints the approved-image count and explains the dataset-column rule.

### F4.11 Step 2 — split percentages and rebalance entry
- **User:** reads the current split, edits train/valid/test percentages, optionally rebalances.
- **Flow:** 1. Split step shows current counts. 2. Three percent fields; 70/20/10 is recommended and can be reset in one click. 3. `[error: percentages must total 100]` inline and blocking. 4. Rebalance opens F4.12.
- **Why easy:** a defensible default plus a reset button means users who do not care can skip the step safely.
- **Sources:** create-a-dataset-version.md.
- **LD:** `Versions.tsx` step 1 — switch, three inputs, inline total check.

### F4.12 Rebalance dialog: three strategies plus class scoping
- **User:** chooses how images move to reach the targets.
- **Flow:** 1. Rebalance → dialog with three modes. 2. Pick mode, optionally scope to classes, confirm. 3. Large datasets run as a background task with per-phase progress; the dialog can be dismissed and the task followed in the activity centre. `[error]` surfaces from the task.
- **Why easy:** each mode answers a different fear — don't churn my splits (move as few as possible); give me a clean random split (shuffle all); keep every upload batch represented in every split (shuffle per batch or annotation job).
- **Data effect:** writes to the **project**, so the next version inherits it; existing versions keep their splits. Class scoping silently switches the method back to minimal-move and only moves images containing only those classes.
- **Gates:** project-update permission; API returns 202 + task id to poll.
- **Sources:** create-a-dataset-version.md.
- **LD:** `Versions.tsx` has a rebalance switch and three inputs, no mode choice, no async task.

### F4.13 Step 3 — preprocessing picker (all splits)
- **User:** adds zero or more preprocessing steps, which apply to train, valid **and** test.
- **Flow:** 1. Step 3 lists transforms (F4.17–F4.27). 2. Add step → config → apply. 3. Steps stack; remove to undo. 4. Preview draws labels on the transformed output. `[empty]` = none, allowed. `[loading]` per-image preview. `[error: step incompatible]` for fixed-size tiling with isolate-objects or dynamic crop.
- **Why easy:** the scope difference (all splits vs train only) is printed next to the step, and that is the one thing users get wrong.
- **Gates:** two tiling modes are workspace-gated in the app while the API accepts them for all.
- **Sources:** image-preprocessing.md.
- **LD:** `Versions.tsx` step 2 — resize (two of six modes), grayscale, contrast, filter-null.

### F4.14 Step 4 — augmentation picker, one addition at a time
- **User:** adds augmentations individually; each is a card in an ordered list.
- **Flow:** 1. Add augmentation step → catalogue. 2. Configure → apply → back to the list. 3. Repeat. 4. Remove a card to drop it. `[empty]` = no augmentation, which the docs actively recommend as a baseline. `[error: premium feature]` when an enhanced or bbox-level option is unavailable on the plan.
- **Why easy:** add-one-then-configure matches how people reason about augmentation; sixteen toggles on one screen would invite over-augmentation.
- **Gates:** enhanced and bbox-level options are premium.
- **Sources:** add-augmentations-to-images.md, image-augmentation.md.
- **LD:** `Versions.tsx` step 3 — flat list of 10 toggles/ranges, no tiers, no preview, no ordering.

### F4.15 Step 5 — output size multiplier with an estimate
- **User:** picks how many images per source training image the version should contain.
- **Flow:** 1. Options limited to the plan's maximum. 2. Estimate shown: 100 images at 70/20/10 with 3× ≈ 210/20/10. 3. Note that the realised count can be lower — duplicate outputs are dropped and filters can remove images.
- **Why easy:** "copies per training image" is a ratio users can reason about, and the split is shown as numbers so nobody expects valid and test to grow.
- **Gates:** Core up to 5×, Enterprise custom; web app only offers allowed values, and API/SDK generation **fails** above the cap instead of clamping silently.
- **Sources:** image-augmentation.md, roboflow.com/pricing, create-a-dataset-version.md.
- **LD:** `Versions.tsx` defaults `outputs: 3`, no cap and no estimate.

### F4.16 Confirm and the generated result page
- **User:** names the version, confirms, and lands on a page describing exactly what was built.
- **Flow:** 1. Confirm summarises split, preprocessing, augmentation, multiplier and estimated count **[inferred placement]**. 2. Generate → F4.4. 3. Result page: per-split counts, total images, applied settings, export panel, train entry, training list.
- **Why easy:** the generated page is the single launchpad for export, train and delete, and it records the recipe rather than asking the user to remember it.
- **Sources:** dataset-versions.md (version payload fields), create-a-dataset-version.md.

## Preprocessing (train + valid + test)

### F4.17 Auto-orient (RF: *Auto-Orient*)
- **User:** leaves one toggle on.
- **Effect:** applies the EXIF orientation and strips EXIF so stored pixels match the display; labels rotate with the pixels, no other coordinate change.
- **When:** always, per the docs' recommendation, especially when inference images come from the same capture pipeline.
- **UI:** boolean, on by default, with a note to check how inference images arrive.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions/image-preprocessing.md

### F4.18 Resize and its six modes
- **User:** sets width, height, and one mode; downsize only.
- **UI:** two number fields + mode dropdown + per-image preview.

| Mode | Pixels | Labels |
|---|---|---|
| Stretch to exact | distorted to W×H, nothing dropped | scaled proportionally |
| Fill (centre crop) | centre crop to W×H, edges dropped | clipped to new frame, not scaled |
| Fit within | longest side = target, not square | scaled proportionally |
| Fit, reflect edges | padded by mirroring | boxes mirrored into padding by default |
| Fit, black edges | black padding | unchanged; padding holds no objects |
| Fit, white edges | white padding | as black |

- **Why easy:** each mode states what is traded — distortion, lost pixels, or padding — so the choice is a trade-off, not a guess.
- **Sources:** image-preprocessing.md. **LD:** only stretch and black-edge fit exist.

### F4.19 Grayscale (RF: *Grayscale*)
- **User:** toggles it. **Effect:** RGB → one channel via 0.2125 R + 0.7154 G + 0.0721 B; labels unchanged.
- **When:** colour is irrelevant or misleading (material, thermal, print); saves memory.
- **UI:** boolean.
- **Sources:** image-preprocessing.md.

### F4.20 Auto-adjust contrast, three algorithms (RF: *Auto-Adjust Contrast*)
- **User:** picks one algorithm or none.
- **Effect:** contrast stretching rescales to the 2nd–98th percentile; histogram equalization flattens the global intensity distribution; adaptive equalization (CLAHE) equalises over local tiles so dark and bright regions both gain detail. Labels unchanged.
- **When:** low-contrast capture (haze, backlight, microscopy). Global equalization can amplify noise; CLAHE is the local-detail option.
- **UI:** select with three entries + off, live preview.
- **Sources:** image-preprocessing.md.

### F4.21 Isolate objects (RF: *Isolate Objects*)
- **User:** turns every box into its own image, converting a detection dataset into a classification dataset.
- **Effect:** pixels cropped per box; the box class becomes the image class and all other boxes in that source image are discarded.
- **When:** second stage of a detect-then-classify pipeline, or when classes are visually close and a crop classifier is cheaper than a bigger detector.
- **UI:** boolean; incompatible with fixed-size and fixed-aspect tiling.
- **Sources:** image-preprocessing.md.

### F4.22 Static crop
- **User:** defines a fixed percentage region applied to every image.
- **UI:** four percentage fields (x/y min and max) with an overlay preview.
- **Effect:** same relative region of every frame; boxes fully outside are dropped, partial boxes are clipped to the new frame.
- **When:** fixed camera with a known region of interest.
- **Sources:** image-preprocessing.md, create-a-dataset-version.md (`static-crop` keys).

### F4.23 Tiling, three modes (RF: *Tile*)
- **User:** cuts images into tiles so small objects occupy more pixels.
- **Modes:** grid (rows × columns, default 2×2, tile size follows image size); fixed size (exact tile W×H, overlap %, padding black/white); fixed aspect ratio (ratio, span width/height, overlap %, padding).
- **Effect:** pixels are re-cut, not resampled, in fixed-size mode; labels are clipped per tile and boxes entirely outside a tile are dropped; padding fills the right/bottom remainder so every tile is full size.
- **Rules surfaced:** tiles ≥ 224 px per side; images too small stay whole in aspect mode; tiling runs **before** resize; fixed-size/aspect cannot combine with isolate-objects or dynamic crop; no size estimate is offered for fixed modes because tile count depends on each image's dimensions.
- **When:** aerial, microscopy, PCB/defect inspection, wide-angle CCTV.
- **Gates:** fixed-size and fixed-aspect are enabled in-app for selected workspaces only; the API accepts all three for any workspace.
- **Sources:** image-preprocessing.md.
- **Title-only:** "Dynamic Crop" is named in the incompatibility note but has no index page — its options are unverified.

### F4.24 Modify classes: omit, rename, merge, regex (RF: *Modify Classes*)
- **User:** edits the version's class list without touching the project's.
- **Flow:** 1. Step 3 → modify classes. 2. Per class: keep, omit, or rename to a target (two names → one target merges them). 3. Optional find/replace by regular expression with a preview and an apply button. 4. Reset restores every class.
- **Label effect:** omitted classes lose their boxes; images left with nothing become unannotated and are then eligible for filter-null; regex edits many names at once.
- **Why easy:** destructive class surgery lives in a version-scoped, resettable place.
- **Gates:** regex controls appear above three classes in the version builder, for any count in training setup.
- **Sources:** image-preprocessing.md. **LD:** absent from `Versions.tsx`.

### F4.25 Filter null images
- **User:** sets how much unannotated data to keep, or removes it.
- **Effect:** only images explicitly marked null (including images emptied by class omission) are eligible; missing/unlabeled images are a different problem and are not touched.
- **When:** background frames drown the signal. The UI warns to annotate everything and mark nulls properly first.
- **UI:** percentage control plus a warning block.
- **Sources:** image-preprocessing.md.

### F4.26 Filter by tag: require / exclude / allow
- **User:** assigns each tag one of three roles.
- **Semantics:** require — only images with that tag pass; exclude — images with it are dropped; allow — images with it pass unless another rule excludes them.
- **Flow:** 1. Tag list with three radio columns. 2. Click a column header to set the whole list. 3. Apply. 4. Reset. `[empty: no tags on the project]` makes the step inert.
- **When:** train on a subset (new camera, new site) or hold out an unwanted batch. It is the closest thing to an image picker in the wizard.
- **Sources:** image-preprocessing.md.

### F4.27 Pipeline order and conflicts are stated, not silent
- **User:** stacks steps and meets the constraints.
- **Rules:** tiling before resize; fixed tiling incompatible with per-image cropping; 224 px floor; no estimate for fixed tiling; some steps change labels (crop) and others only pixels.
- **Why easy:** the order is fixed and documented instead of a graph the user can wire wrongly.
- **Sources:** image-preprocessing.md.

## Augmentation (train split only, applied offline at generation)

### F4.28 Scope and the offline rationale
- **User:** enables augmentation on a version and accepts that valid and test are untouched.
- **Flow:** step 4 additions → step 5 multiplier → copies land only in train.
- **Why easy:** the product states the reason in user terms — a stored copy of each augmented image makes runs reproducible, and CPU work happens once instead of every epoch, so rented GPU time is not spent waiting on augmentation.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions/image-augmentation.md

### F4.29 Multiplier semantics and plan cap
- **User:** picks N×, where N counts the preprocessed original plus N−1 augmented copies.
- **Effect:** 100 images at 70/20/10 with 3× ≈ 210/20/10; duplicate outputs are dropped, so the realised count can be lower.
- **Gates:** Core up to 5×, Enterprise custom; above the cap the API fails.
- **Sources:** image-augmentation.md, roboflow.com/pricing.

### F4.30 Basic image-level augmentations, with parameters
- **User:** adds any subset; each card carries the controls below and is randomised per generated image within the configured bound.

| Option | Controls (documented) | Documented range | bbox twin | Tier |
|---|---|---|---|---|
| Flip | horizontal, vertical | — | `bbflip` | Basic |
| 90° rotate | clockwise, counter-clockwise, upside-down | 90/180/270 | `bbninety` | Basic |
| Crop | percent of area to drop | min/max | `bbcrop` | Basic |
| Rotation | max degrees, both directions | degrees | `bbrotate` | Basic |
| Shear | horizontal, vertical | degrees | `bbshear` | Basic |
| Grayscale | percent of images converted | percent | none | Basic |
| Hue | max rotation around the wheel | degrees | none | Basic |
| Saturation | percent up or down | percent | none | Basic |
| Brightness | brighten and/or darken + percent | percent | `bbbrightness` | Basic |
| Exposure | percent up to 100 (100 = white/black) | percent | `bbexposure` | Basic |
| Blur | kernel/radius in pixels | max 25 px, odd kernels | `bbblur` | Basic |
| Noise | percent of pixels, salt and pepper | max 25% | `bbnoise` | Basic |
| Camera gain | variance multiplier | — | yes, listed | Basic |
| Motion blur | length px, angle deg, frames per blur length | — | yes, listed | Basic |

- **Label effects:** geometric options transform boxes and polygons with the pixels. Crop is the only one that loses labels: fully out-of-frame boxes are dropped, partial ones are clipped, and there is **no** minimum-retained-area control yet (stated as planned).
- **Why easy:** every option is one bounded number or a direction pair, so the user never authors a distribution, and API keys (`hue.degrees`, `noise.percent`) mirror the on-screen labels.
- **Sources:** image-augmentation.md, create-a-dataset-version.md (keys and ranges), the 14 per-option pages.
- **LD:** `Versions.tsx` ships 10 of these with stricter hard-coded maxima (45°, 50%, 80%, 5 px, 10%, 50%).

### F4.31 Bounding-box-level variants (premium)
- **User:** picks the box-level twin of an option; only the content inside each box is altered.
- **Effect:** background statistics stay clean while the object's appearance varies; boxes and polygons follow the same geometry.
- **When:** small datasets where whole-image colour or geometry changes would teach the wrong background.
- **Gates:** premium; available for flip, 90° rotate, crop, rotation, shear, brightness, exposure, blur, noise, camera gain, motion blur — not for grayscale, hue, saturation, cutout, mosaic.
- **Sources:** image-augmentation.md, create-a-dataset-version.md (`bb*` keys).

### F4.32 Enhanced augmentations: cutout and mosaic (premium)
- **User:** adds occlusion or composite mixing.
- **Cutout:** count (boxes per image) + percent (each box as % of the image); black rectangles are painted over, labels underneath are kept.
- **Mosaic:** packs 3–9 images into one tile, shrinking them; labels are re-projected into the composite.
- **Warning shown:** many modern models already apply these online, so doubling them can hurt; the docs advise against using them with the first-party model and with YOLOv8.
- **Gates:** premium, image-level only.
- **Sources:** image-augmentation.md, cutout and mosaic pages.

### F4.33 How a user decides what and how much
- **Guidance given:** start with **no** augmentation to establish a baseline; only add after a clean run, otherwise a regression has no reference. If the baseline is bad, the problem is class balance, representation or dataset size.
- **Map the catalogue implies:** lighting → brightness/exposure; focus → blur/motion blur; sensor quality → noise/camera gain; mounting angle → rotation/shear/flip/90°; colour-irrelevant material → grayscale/hue/saturation; occlusion → cutout; many small objects → mosaic.
- **Magnitude:** bounds are absolute and visible (25 px blur, 25% noise, 100% exposure), and output count is a separate dial from transform strength, so "more images" and "more extreme images" are not the same decision. Example values on the option pages (20% crop, 0.3% noise, 2.5 px blur, ±15° hue, ±30% saturation, 10% cutout × 10, 100 px motion blur at 90°) are illustrative, not defaults.
- **Sources:** image-augmentation.md and the per-option pages.

## Export

### F4.34 Export dialog
- **User:** exports a version in the format their trainer expects, as a ZIP or as a copy-paste snippet.
- **Flow:** 1. Version card → export. 2. Format select, filtered to the project type. 3. Download `.zip` or show download code. 4. `[loading]` export progress, link appears when ready. 5. `[error: format unavailable for this project type]`, `[error: version still generating]`. 6. Key warning: the curl/Python snippet contains a private API key and must not be shared.
- **Why easy:** one dialog serves a human (ZIP) and a script (curl/SDK), and the key warning sits exactly where the key is revealed.
- **Gates:** export permission; the download link is a grant, so read-only roles must not get one.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions/exporting-data.md
- **LD:** `routers/versions.py` — `GET /formats` filtered by project type, export job dedupe, `sign_path` gated on `project.export`.

### F4.35 Format catalogue by project type
| Project type | Formats |
|---|---|
| Object detection | clip, coco, createml, darknet, multiclass, tensorflow, tfrecord, voc, yolokeras, yolov5pytorch, yolov7pytorch, mt-yolov6, retinanet, benchmarker |
| Single-label classification | folder, clip |
| Multi-label classification | multiclass, folder, clip |
| Instance segmentation | coco-segmentation, clip, coco, createml, darknet, multiclass, tensorflow, tfrecord, voc, yolokeras, yolov4pytorch, yolov4scaled, yolov5-obb, yolov5pytorch, yolov7pytorch, mt-yolov6, retinanet, benchmarker |
| Semantic segmentation | coco-segmentation, png-mask-semantic |
| Keypoint detection | coco, yolov5pytorch |

- **Why easy:** the list is filtered by project type, so a classification user never sees a detection format.
- **Sources:** exporting-data.md.

### F4.36 Export is async, cached and repeatable
- **User:** exports once, then re-downloads the same artefact later.
- **Flow:** 1. Request starts a job. 2. The API returns 202 with progress until ready, then a payload with the download link. 3. Repeat requests return the existing artefact instead of rebuilding. 4. CLI and SDK expose the same operation.
- **Why easy:** a large export is never a blocking browser download, and asking twice is free.
- **Sources:** exporting-data.md, dataset-versions.md.

### F4.37 What does not survive a round trip
- **Images:** exports are re-compressed for training speed; original bytes need the per-image original URL or a separate whole-dataset export that rebuilds from source files and keeps the original extension.
- **Class names:** ASCII-sanitised on upload **and** export — accented characters are anglicised where possible, otherwise replaced with a dash. A round trip can rename classes.
- **Segmentation geometry:** choosing a detection format for a segmentation project drops masks (polygons become boxes) — implied by the separate mask formats in F4.35.
- **Attributes and metadata:** not covered by the documented formats; assume loss until verified.
- **Search-driven subsets:** the original-quality export rejects semantic search; only field filters (`class:`, `tag:`, `split:`, `filename:`) work.
- **Sources:** exporting-data.md.

### F4.38 Export straight to a customer bucket — not documented
- Only browser ZIP, curl link and SDK/CLI download to local disk are documented. No S3/GCS/Azure destination write appears on the export page. Treat bucket delivery as unverified.

## Version and dataset analytics

### F4.39 Health check overview
- **User:** opens the dataset health tab to judge whether the project is trainable at all.
- **Contents:** image count, annotation count, average image size, median aspect ratio, missing annotations, null annotations, image-dimension distribution, object-count histogram, annotation heat map.
- **Flow:** dataset page → health tab. `[loading]` first computation can take minutes on large datasets. `[error]` a report may be stale; the API takes an explicit regenerate flag.
- **Why easy:** the two numbers that most often block training — missing vs null annotations — sit on the same screen as size and class context, with the difference explained.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-health-check.md
- **LD:** `apps/frontend/src/features/project/HealthCheck.tsx` — label issues (tiny/out-of-bounds/zero-area/duplicate) and quality classes (blurry/dark/ok) already exist; thresholds mirrored from the backend service and shown in the card.

### F4.40 Class balance per split
- **User:** reads a per-class breakdown for train, valid and test side by side.
- **Why it matters:** catches a class present only in train, or a rare class with two test instances, before those become a meaningless per-class mAP.
- **Sources:** dataset-health-check.md.

### F4.41 Dimension insights
- **User:** inspects the raw image size and aspect-ratio distribution.
- **Why it matters:** it justifies the resize mode and target size from F4.18; the page notes that resizing a version never changes the raw images, so the chart always describes source data.
- **Sources:** dataset-health-check.md.

### F4.42 Annotation heat map with drag-to-filter
- **User:** drags a rectangle over a spatial heat map of annotation positions to list every image whose boxes fall in that region.
- **Why easy:** "our boxes are all in the middle" becomes a clickable image list, which is the fix path rather than just a chart.
- **Sources:** dataset-health-check.md.

### F4.43 Objects-per-image histogram with click-through
- **User:** clicks a bar (say, three objects) to see those images.
- **Why it matters:** multi-instance images are where detection recall breaks, and the histogram is the fastest way to notice that nearly every image holds exactly one box.
- **Sources:** dataset-health-check.md.

### F4.44 Report caching and staleness
- **User:** sees counts that may predate the latest labels.
- **Behaviour:** the first report and any regenerate request are computed during the call (slow); later calls return the stored report, which carries a generated timestamp.
- **Why it is risky:** staleness is a field rather than a lie, but a user who never reads the timestamp can decide on stale numbers.
- **Sources:** dataset-health-check.md (HTTP API).

### F4.45 Per-version analytics and version-to-version comparison — not documented
- Health check is **project-level**. The version payload carries `images`, `splits`, class names and its trainings — no per-version class histogram, no version diff, no per-version health report in any page read. Treat snapshot-level analytics and comparison as an inferred gap, not a parity item.

### F4.46 Warning before training on a bad version — only partly documented
- Documented: training refuses a version that is not ready, returning a 400 with a `remedy` field naming the fix; plan limits apply; the health page advises on missing and null annotations.
- Not documented: any pre-flight that blocks or warns on "zero test images for class X" or "no null annotations" at train time. That warning is a LabelDesk opportunity, not parity.
- **Sources:** train-a-model.md, dataset-health-check.md.

## Title-only / unverified
- **Dynamic Crop** — named only in a tiling incompatibility note, no index page.
- **90° rotate, grayscale augmentation, remap detail pages** — parameter names taken from the settings JSON only.
- **Per-plan version count cap** — pricing lists 20 projects, a 5× multiplier and uncapped/on-demand dataset size; no per-project version cap found.
- **Generated-image quota** — referenced by the delete page, never quantified.
- **Version-generation notification** — email is documented for training completion only.
- **Export to cloud destination** — no page found.
- **Per-version analytics/comparison** — no page found (F4.45).
- **Renaming or duplicating a version object** (beyond reusing its settings) — not documented.

## Coverage gaps and what to check next
- Reconstruct step 1 and step 3 from the app or a recording; docs number only steps 2, 4, 5.
- Does a transform card preview one sample or a grid, and do stacked previews apply cumulatively?
- Can preprocessing steps be reordered, or only added and removed?
- Minimum images per version and per split — not stated anywhere read.
- Trash page copy, and exactly when quota is reclaimed.
- Verify segmentation-format behaviour (F4.37) against a real export before promising round-trip fidelity in LabelDesk.
