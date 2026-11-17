# Area 2 — Upload & Data Management

Method: fetched 16 Roboflow pages on 2026-11-17 — the docs index (`llms.txt`), adding-data, datasources, upload-a-dataset, manage-images, manage-datasets, dataset-search, manage-batches, add-tags-to-images, image-metadata, dataset-health-check, create-a-dataset-version, fork-a-universe-dataset, merge-datasets, delete-an-image, trash, asset-library, project-folders(+permissions), similarity-search-and-settings, annotate-an-image, plus roboflow.com/pricing, /credits, /ai/image-deduplication. Not opened: `docs.roboflow.com/reference/**` OpenAPI YAML bodies, changelog pages, blog.roboflow.com posts, Universe browse pages, `help.roboflow.com` upload-error articles, image-preprocessing page (covered by the data-layer note).

Screen names used below are Roboflow's own screen locations described as neutral steps, not copied UI copy. Anything marked `[inferred]` is my reconstruction, not documented.

## A. Web upload paths

### F2.1 Drag-and-drop ingest with a pre-upload duplicate preview (RF: Upload Data page)
- **What the user does:** drops files, folders or an archive onto one target, sees what will be new vs skipped, names the batch, picks split + tags + (optionally) "add straight to dataset", then confirms.
- **Flow:** 1. Project sidebar → **Upload Data** [empty: a single drop target plus a camera shortcut]. 2. Drop files → client enumerates them, hashes, and asks the server which are already present [loading: per-file rows resolve in place]. 3. Summary badges: "N new", "M duplicates skipped" [error: unsupported extension → the file is dropped from the count and named in the summary]. 4. Fill batch name / split / tags. 5. Confirm → progress per file → toast: uploaded count, skipped count, failed count with a link to the failure list. 6. Files appear as one batch on the **Annotate** board.
- **Why it is easy:** duplicate rejection happens before bytes leave the browser, so a 900-image re-drop costs one hash request and produces a count the user can check against what they dragged.
- **Gates:** images ≤30 MB, ≤16,384 px per side, ≤178,956,970 px total (all methods); 40+ annotation formats, available set depends on project type; web app "recommended for fewer than 1,000 images".
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md, https://docs.roboflow.com/datasets/manage/manage-images.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Upload.tsx`, `apps/backend/app/routers/images.py`

### F2.2 Pre-annotated web upload with an annotation-overwrite switch (RF: upload annotations with images)
- **What the user does:** drops a folder/zip that contains images plus their label files; if the images already exist, chooses whether the incoming labels replace the stored ones.
- **Flow:** 1. Upload Data → drop. 2. Confirmation dialog: checkbox "replace annotations on images already in this project" (off by default; classification projects always replace). 3. Upload → images with labels go to the **Dataset** or to a **Review** queue if review mode is on; the archive's labels form a new annotation job credited to the uploader, even on re-upload. 4. Images without labels go to a batch for labelling.
- **Why it is easy:** one toggle decides a destructive question ("do my old labels survive?") at the moment the user still remembers what is in the zip.
- **Gates:** annotation formats per project type; review-mode approval required before labels count.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md, https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Upload.tsx`

### F2.3 Format acceptance and class-name normalisation (RF: 40+ annotation formats)
- **What the user does:** drops whatever format their previous tool exported; no conversion step before upload.
- **Flow:** 1. Upload Data → drop. 2. Server detects format from the file set (COCO JSON + images, VOC XML beside images, YOLO txt + `data.yaml`, CreateML, etc.); directory names `train|training|valid|validation|val|test|testing` set the split, nothing else does (a folder `train2017` sets no split, `test_image.jpg` is not a test item) [error: file whose name does not match an image → orphan label, reported per file]. 3. Class names are rewritten on the way in: trim, collapse all whitespace to one space, replace `/.[]#~*` with `-`, drop `|'"`.
- **Why it is easy:** the import contract is "folder layout means split, file names pair images to labels", so users can fix a broken import by renaming folders rather than editing JSON.
- **Gates:** split folder names are an exact allow-list; case-insensitive.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md, https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

### F2.4 Two-speed zip ingest (RF: browser extract vs server-side archive)
- **What the user does:** drops one archive instead of thousands of files; does not care whether it is unpacked locally or remotely.
- **Flow:** 1. Drop `.zip`. 2. ≤300 files → expands in the browser and takes the normal folder-upload path, nested folders preserved. 3. Larger (≤8 GB) → uploaded whole, processed server-side; the progress bar finishes, then the user can leave the page and watch **Activity Center**. 4. Result lands as one batch on **Annotate**; a re-upload of the same zip still creates a new annotation job.
- **Why it is easy:** the 300-file threshold is invisible except as a change in where the progress bar comes from, and the async path frees the tab.
- **Gates:** >8 GB must go through the CLI; SDK zip path is 8 GB / 100,000 files and refuses prediction-type uploads.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md, https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Upload.tsx`

### F2.5 Camera capture as an upload source (RF: Use Camera)
- **What the user does:** captures training data without leaving the upload page — single frames, timed frames, or a short clip.
- **Flow:** 1. Upload Data → **Use Camera** → pick device [error: no permission / no device → the button reports the failure; `[inferred]`]. 2. Mode: Photo (one frame per shot) · Interval (1 frame every 0.2–60 s, up to 1,000 images) · Video (MP4, ≤300 s). 3. Review the clip → "Keep Video" → "Add N to Upload" / "Add Video to Upload". 4. In image projects a clip then opens the frame-extraction dialog (F2.6).
- **Why it is easy:** the capture mode (interval vs clip) is chosen before capture and the resulting frame count is shown before commit, so a 1,000-frame accident is visible.
- **Gates:** interval ≤1,000 images; clip ≤300 s; video mode hidden in browsers that cannot record MP4 (e.g. Firefox).
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

### F2.6 Video upload with a frame-extraction dialog (RF: Upload Video)
- **What the user does:** uploads MOV/MP4 and chooses which frames become images, either by sampling interval or by hand.
- **Flow:** 1. Upload Data → drop video(s). 2. Extraction dialog per video: interval slider from 60 fps down to 1 frame per 60 s → the count updates live [loading: filmstrip thumbnails stream in]. 3. Trim handles on the filmstrip exclude a head/tail range. 4. "Manual selection" → `M` adds the current frame, `,`/`.` step one frame, `Shift+←`/`→` jump between picks; sampled + picked frames merge without duplicates. 5. Queue several videos → apply one interval to all; each video with manual picks opens its own dialog. 6. Frames land in the batch. Action-recognition projects instead keep the video whole and label time segments; a folder of videos + `_annotations.coco.json` (`info.format = roboflow-video-coco`) imports segments, and re-importing replaces segments unless frame annotations exist.
- **Why it is easy:** the sampling decision is shown as "here are the exact frames", with trim and manual override in the same dialog, so the cost of a 30-minute video is visible before ingest.
- **Gates:** browser decodes the file, so the format list follows the browser; HEVC/H.265 commonly fails with an "unsupported video" error (only Safari decodes it) — the documented remedy is re-encode to H.264 MP4. API path: ≤3 GB. CLI cannot upload video at all.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

### F2.7 Server-side fetch upload from a public URL (RF: `image` query parameter)
- **What the user does:** hands the API a URL instead of bytes; the platform pulls the image itself.
- **Flow:** 1. Call the image upload endpoint with `image=<public URL>`. 2. Server fetches → returns an image ID. 3. Image appears on **Annotate** in the named batch or in "Uploaded via API". 4. `[inferred]` failures are a fetch error in the response, not a queued retry; nothing in the docs describes a retry or timeout policy.
- **Why it is easy:** one parameter turns any crawler or camera gateway into an uploader with no client-side file handling.
- **Gates:** same 30 MB / 16,384 px / 179 MP caps; no documented SSRF allow-list or per-URL rate limit.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-images.md

### F2.8 Screening hold on ingest (RF: image upload screening)
- **What the user does:** nothing extra — but every upload can come back with an image ID marked "held", and the user must read a verdict before treating it as usable.
- **Flow:** 1. Upload returns an image with a screening state. 2. Client reads `/{workspace}/images/{imageId}/screening`: pending (still held) · passed | redacted (may become available later) · rejected | failed (never enters the project). 3. Only after the verdict does the client report the image as available; the docs warn a verdict alone does not confirm dataset readiness. 4. Batch counts report held images separately from ready ones; a zip task's `result.screening` is folded into `result.uploaded` with no per-image verdicts.
- **Why it is easy:** it converts an invisible moderation queue into a countable third state ("uploaded, awaiting verdict") instead of an image that silently never appears.
- **Gates:** `[inferred]` applied to all workspaces; docs do not state which content classes trigger it.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md, https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md

### F2.9 Refusal rules that apply to every ingest path (RF: image size limits)
- **What the user does:** never learns a per-path limit — one set of caps holds everywhere.
- **Flow:** 1. Any path (web, API, zip, datasource) checks size/dimensions. 2. Oversize → that file is refused, the rest of the batch proceeds. 3. Already-stored images uploaded before the caps were introduced stay in the project. 4. `[inferred]` the failure reason surfaces as a per-file row in the upload summary or as an HTTP error; no docs page lists the exact message text.
- **Why it is easy:** one rule set to remember, and oversize files never poison the batch.
- **Gates:** 30 MB · 16,384 px per side · 178,956,970 px total.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

## B. Programmatic ingestion

### F2.10 Single-image REST upload with a late-annotation attach (RF: Manage Images API)
- **What the user does:** pushes one image (stream, camera, crawler), gets an ID back, then attaches labels to that ID afterwards.
- **Flow:** 1. POST the image as multipart, base64 body, or URL parameter → returns image ID. 2. Image appears on **Annotate** in the Unassigned column. 3. POST the annotation file against the image ID — labels must reference the stored file name. By default this also moves the image into the **Dataset**, removing it from batch/job/review flow; `addToDataset=false` keeps the workflow state. 4. Optional concurrency guard: read `annotationGroupVersion`, send it as `expectedGroupVersion`, and a stale write fails with 409 instead of overwriting a colleague.
- **Why it is easy:** the two-step ID handshake means a slow labeller or a second service can add labels without re-sending pixels, and the version token makes that safe.
- **Gates:** docs elsewhere say annotations cannot be added to already-imported images — this API page contradicts that; treat the UI-only rule as the reliable one.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-images.md, https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

### F2.11 Dataset-zip REST upload with signed URL and task polling (RF: `upload/zip`)
- **What the user does:** uploads a whole labelled dataset in three calls instead of N.
- **Flow:** 1. POST → `{signedUrl, taskId}`. 2. PUT the zip to the signed URL with `Content-Type: application/zip` and **without** the API key (it is a storage host, not the API). 3. Poll `GET /{workspace}/upload/zip/{taskId}` until `completed` or `failed`. 4. `annotationOverwrite=true` replaces labels on existing images; unlabelled images enter a labelling batch; PDFs and videos inside the zip are skipped with a warning (videos accepted only in action-recognition projects).
- **Why it is easy:** the long part is a resumable object upload with a poll-able task, so a dropped connection is not a lost import.
- **Gates:** signed URL expires (docs give 60 minutes for the video path; the zip page states no expiry); 8 GB / 100,000 files.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md

### F2.12 Video REST upload with the same three steps (RF: `upload/video`)
- **What the user does:** ingests large video outside the browser.
- **Flow:** 1. Prepare → `videoId`, `signedUrl`, `requiredHeaders`. 2. PUT the file with every required header (URL valid 60 min). 3. Read status until `uploaded` or `failed`. 4. Optional `batch` / `tag` / `metadata` / `split`; re-uploading the same video reuses the record, keeps its batch, and applies the new tags/metadata/split. 5. Find it later with `mediaTypes: ["video"]` in search.
- **Why it is easy:** re-upload is idempotent and additive (batch kept, new tags merged) rather than a duplicate.
- **Gates:** MP4/MOV ≤3 GB.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

### F2.13 Python SDK bulk upload with prediction flag and retries (RF: `upload_dataset`)
- **What the user does:** one call from a notebook or ETL job to push a directory into a project that may not exist yet.
- **Flow:** 1. `workspace.upload_dataset(path, project_name, num_workers=10, project_type=…, project_license=…, batch_name=…, num_retries=0, is_prediction=False)`. 2. Project is created if missing. 3. Progress printed per worker; failures retried N times. 4. `is_prediction=True` marks labels as model output → the image moves into a review job, unless it is already assigned to a job.
- **Why it is easy:** project creation, split detection from folder names, batching and retries are one signature; `num_workers` (recommend ≤25) is the only perf knob.
- **Gates:** zip path rejects `is_prediction`; SHA-256 dedupe from `roboflow` 1.3.6 (original bytes, not re-encoded) so a re-push costs no storage.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md, https://docs.roboflow.com/datasets/manage/manage-images.md

### F2.14 CLI upload with wait/no-wait and machine-readable output (RF: `roboflow image upload|import`)
- **What the user does:** uploads a directory or zip from a shell, optionally fire-and-forget, optionally as JSON for a pipeline.
- **Flow:** 1. `roboflow image upload <path> -p <project>` (alias `roboflow upload`). 2. Auto-detects file / directory / zip. 3. Flags: `-c` concurrency (default 10), `-b` batch, `-s` split override, `-t` tags, `-r` retries, `--zip-upload`, `--no-wait` → prints a task id to poll with `roboflow asynctasks get`. 4. `--json` prints `{status, path, project}` for scripting.
- **Why it is easy:** the same command accepts the three common shapes (file, folder, zip), and `--no-wait` + task id makes it safe inside CI.
- **Gates:** images only — video must be split into frames first.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md, https://docs.roboflow.com/datasets/create-and-upload/adding-data.md

### F2.15 Reusable bucket credentials, separate from the datasource (RF: Datasource Credentials)
- **What the user does:** stores bucket access once, then reuses it across datasources without re-typing keys.
- **Flow:** 1. Workspace **Settings → Credentials → Add Credential** (provider-specific: S3 keys, Azure, GCS). 2. Name it, save [error: `[inferred]` a failed validation is reported when the datasource lists files, not at credential save]. 3. In a datasource form the "Credential" dropdown lists saved ones; a `+` adds one inline without losing the form. 4. Access is stored encrypted; least-privilege policy examples are published separately.
- **Why it is easy:** credentials are a named object with one owner page, so rotating a key is one edit rather than N datasource edits.
- **Gates:** Enterprise-ish governance is not stated here; available on the plans that expose datasources.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F2.16 Datasource mirror configuration (connection half) (RF: Bucket Mirror)
- **What the user does:** points a datasource at a bucket and proves the connection.
- **Flow:** 1. **Settings → Datasources → Create** → **Connection** tab: name, provider, bucket, region, credential. 2. Bucket field accepts a name only (`my-bucket` or `s3://my-bucket`); a path suffix is rejected. 3. S3-compatible providers: enter a custom `endpoint`, region `auto` or provider-specific, and a "use path-style addressing" checkbox that pre-selects itself and keeps the choice [error: connecting with the wrong addressing mode fails on first file listing with a message telling the user to switch]. 4. `[inferred]` the connection is validated by listing the bucket, so a bad key fails here rather than silently at first sync.
- **Why it is easy:** the failure that usually eats an afternoon (path-style vs virtual-hosted, private-network endpoint) is a checkbox with a self-correcting error.
- **Gates:** endpoint must be internet-reachable; localhost, private, link-local and hostnames resolving to them are rejected.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F2.17 Mirror behaviour: destination, globs, naming, orphans, updates (RF: Mirror Configuration)
- **What the user does:** decides which files come in, where they land, how they are named, and what happens when the bucket changes.
- **Flow:** 1. **Mirror Configuration → Import Destination**: Workspace (Asset Library, optionally also a project) or Folder (folder-scoped, needs folder permissions). One destination per datasource; add another datasource for another target. 2. File filters: glob patterns (`*` one level, `**` recursive, quotes to escape `*`), a `.txt` in the bucket, or an explicit whitelist. 3. `namingStrategy`: fullPath (default) · fileName · eTag · metadata key. 4. `updateImageWhenNewer` (default on) + `updateImageStrategy: overwrite`. 5. Orphan removal **off by default** — files deleted from the bucket stay; enabling it deletes them unless another project or datasource references them, and deleting a datasource with orphan removal on warns and requires acknowledgement.
- **Why it is easy:** the destructive options are the ones that default to off, and the delete-datasource dialog names the blast radius before it runs.
- **Gates:** supported images JPEG/PNG/BMP/WebP/AVIF; videos MP4/MOV ≤3 GB mirrored to the Asset Library only (no frames extracted, not added to a project); glob is case-sensitive (`harvest**` does not match `Harvest`).
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F2.18 Metadata sidecars and conflict policy on sync (RF: JSON sidecar sync)
- **What the user does:** writes one `.json` next to each image in the bucket; the platform merges it into per-image metadata on every sync.
- **Flow:** 1. Put `photo_001.jpg` + `photo_001.json` in the bucket. 2. JSON keys import as-is; nested objects flatten with dots (`capture.temperature`). 3. On later edits, `updateMetadataWhenNewer` (default on) re-syncs, and the chosen strategy decides conflicts: mergeBucketWins (default) · mergeUserWins · overwrite · untilFirstChange (stop syncing a key once a human edits it) · append (new keys only).
- **Why it is easy:** `untilFirstChange` gives a human's manual correction permanent precedence without a per-key rule editor.
- **Gates:** sidecar ≤256 KB, must be valid JSON, `null`/`undefined` dropped.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md, https://docs.roboflow.com/datasets/create-and-upload/adding-data/image-metadata.md

### F2.19 Mirror run controls with cooldown, cap and schedule (RF: trigger a sync)
- **What the user does:** presses play to re-sync, or turns on a daily schedule and forgets it.
- **Flow:** 1. **Settings → Datasources** row → play button. 2. Blocked while a run is in progress. 3. After a run, re-trigger blocked 15 min; the tooltip counts down. Cooldown is skipped if the run found nothing (zero enqueued or all failed), if config changed, or if the last run errored. 4. Hard cap 10 runs per rolling hour, regardless of cooldown skips; cron runs bypass both. 5. "Run automatically on a daily schedule" (off by default) → every 24 h. 6. Eye icon per row opens the **Asset Library** pre-filtered to that datasource, disabled until one sync has completed; a bottom link shows all mirrored assets once any datasource has run.
- **Why it is easy:** the throttle explains itself in the tooltip and exempts retries-after-failure, so the common "my bucket changed, sync now" case still works.
- **Gates:** 10 runs/hour; 15-min cooldown; one destination per datasource.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/datasources.md

### F2.20 Fork a public dataset into the workspace (RF: Fork a Universe dataset)
- **What the user does:** starts from a public dataset instead of an empty project, then customises it.
- **Flow:** 1. Public dataset page → **Use this Dataset** → **Fork Project** [error: not signed in → login first]. 2. Async copy into the workspace. 3. Land on the fork's **Generate New Version** page. 4. Fork starts with fresh versions and export settings; source project is untouched and requires `project:create`.
- **Why it is easy:** the copy ends on the version wizard, so the next click is "train", not "now re-upload".
- **Gates:** 402 not enough credits/image quota · 403 source not public · 404 not found / wrong scope · 409 workspace already owns it · 422 missing params. Agent path can copy a subset ("50 images of X") across several sources and rename classes project-wide.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/fork-a-universe-dataset.md

### F2.21 Merge projects into a third, free because duplicate-backed (RF: Merge Datasets)
- **What the user does:** combines two projects' unique images into a new training project.
- **Flow:** 1. Workspace project list → row menu → **Merge Datasets**. 2. Check the projects to merge. 3. Name the new dataset and its annotation group → Merge. 4. New project holds the union of images and annotations *as of the merge*; the two sources stay. 5. No storage charge, because the images are already counted.
- **Why it is easy:** it answers "consolidate without doubling my storage bill" directly, and leaves the sources intact so nothing is lost by trying.
- **Gates:** same workspace only; snapshot semantics, not a live link.
- **Sources:** https://docs.roboflow.com/datasets/manage/merge-datasets.md

## C. Dataset browser

### F2.22 Image grid with hover-select and a bulk action bar (RF: Dataset page)
- **What the user does:** scans thumbnails, ticks the ones they want, then applies one action to all of them.
- **Flow:** 1. Project → **Dataset** → images tab [loading: skeletons `[inferred]`; empty: a prompt to upload, plus the "Upload images" primary action]. 2. Hover a tile → checkbox appears top-right; click more tiles to extend the selection. 3. A selection bar appears with count + actions: apply tags, change split, remove from project, download/export `[inferred: exact set on this page; the documented actions are tag-apply, split-change and remove]`. 4. Destructive actions open a confirm dialog stating the count; confirm → the tiles disappear and a toast reports the count.
- **Why it is easy:** selection is per-tile on hover (no mode switch) and the action bar only exists when something is selected, so the grid stays a grid.
- **Gates:** bulk split change on a large selection runs as a background job; search "Select all matching" then bulk-apply is the documented pattern for acting beyond one page.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/delete-an-image.md, https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Dataset.tsx`

### F2.23 Batch board as the dataset pipeline (RF: Annotate page columns)
- **What the user does:** moves groups of images, not images, through upload → labelling → review → dataset.
- **Flow:** 1. **Annotate** page shows four columns: Unassigned · Annotating · Review (only where review exists) · Dataset. 2. Every upload becomes one batch card in Unassigned. 3. Assign a batch (or a selection inside it) to a person → card moves to Annotating; unassigned leftovers are split into a new batch in Unassigned. 4. Annotated → Review, or straight to Dataset without review. 5. Approved → Dataset; rejected → back to Annotating. 6. Row menu: merge batches, delete batch (Unassigned only — otherwise "move to unassigned" first).
- **Why it is easy:** the state of 10,000 images is one moving card per ingest, and the column position *is* the status.
- **Gates:** review column absent for plans without review mode; a batch must be in Unassigned to be deleted; merge requires compatible batches (not from different source videos, not managed review queues).
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/manage-batches.md

### F2.24 Image detail view inside the editor (RF: Annots drawer, Image Attributes, metadata editor)
- **What the user does:** opens one image and sees everything about it without leaving the labelling surface.
- **Flow:** 1. Click a tile → editor. 2. Right toolbar: drawing tools + class selector. 3. **Annots** drawer: classes present/absent, colours, layering, tags. 4. **Image Attributes**: dimensions, last-modified, and which split (train/valid/test) the image is in. 5. Metadata section: two inputs (key, value) → Enter or **Add**; a second edit/remove path `[inferred: value chips with delete]`. 6. Header navigation: previous/next image, view-source-image toggle, options menu (find similar, use as cover, remove from project).
- **Why it is easy:** split membership, tags and metadata are visible on the same screen as the boxes, so "why is this image in test?" is answerable without a second tab.
- **Gates:** split shown is the project-level split; versions freeze their own copy (F2.41).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate.md, https://docs.roboflow.com/datasets/create-and-upload/adding-data/image-metadata.md
- **LabelDesk hook points:** `apps/backend/app/routers/images.py`

### F2.25 Workspace-wide media browser with a sticky action bar (RF: Asset Library)
- **What the user does:** works across projects: find images from any project, then tag, copy into a project, run a workflow, export or delete them.
- **Flow:** 1. Workspace sidebar → **Asset Library**. 2. Filter bar: free text = semantic search; `like-image:<id>`; dataset filters; `metadata:` comparisons; "Filters" for the form view, "Raw" for the whole RoboQL string. 3. **Type** dropdown filters by source project type (appears only when the workspace has >1 type). 4. Select tiles, or **Select All** for the entire query. 5. Sticky bottom bar: tags/metadata · create project · add to project · run workflow · export · delete. 6. Workflow modal: pick workflow (must have exactly one `image` input), CPU/GPU (auto-selected when required), Start → background job tracked in **Activity Center** and **Deployments → Batch Processing**; work can write tags/attributes back so results become searchable.
- **Why it is easy:** "Select All" is scoped to the query, not the page, and the bar states that scope — the classic bulk-action trap is closed.
- **Gates:** export requires "Export Workspace Images" permission (owners by default); export is disabled until Select All is used so the download matches the selection; jobs consume credits.
- **Sources:** https://docs.roboflow.com/platform/workspaces/asset-library.md

### F2.26 Export a single image, a version, or a query result (RF: download and search export)
- **What the user does:** takes data out in the format their trainer wants, either one image or everything matching a search.
- **Flow:** 1. Single image → download (raw, preprocessed or augmented variant). 2. Search → `--export -f coco|yolov8|voc -l <dir>` from the CLI, or `Workspace.search_export(query, format, location)` from the SDK. 3. Whole version → export page with format + link.
- **Why it is easy:** the same query language that filters the grid also produces the export, so "the images I was looking at" is a durable selection.
- **Gates:** folder-restricted members cannot download versions inside folders (zip, links and tokens are all blocked).
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md, https://docs.roboflow.com/datasets/manage/project-folders/project-folder-permissions.md

## D. Search and filters

### F2.27 One query language over classes, tags, splits, size, counts, date and batch (RF: Query Syntax / RoboQL)
- **What the user does:** types a compact query instead of hunting through filter dropdowns.
- **Flow:** 1. Dataset page search box. 2. Available selectors: `tag:` `split:` `class:` `filename:` (`*` for partial) `job:` `min/max-width` `min/max-height` `min/max-annotations` `date:` (immutable upload date, supports `>=` `<` ranges) `like-image:` `metadata:key="v"` with `= > ≥ < ≤`. 3. Combine with `AND OR NOT` and parentheses; prefix `-` to invert; `class:helmet=3`, `class:vest>=4` for counts. 4. Results update in the grid; "Select all matching" extends a bulk action to the full result set.
- **Why it is easy:** the operators are the same words users already think in (`tag`, `split`, `class`), and a query is shareable/pasteable, unlike a dropdown state.
- **Gates:** workspace search adds `project:` / `dataset:` and accepts any filter repeated to require both; empty query returns everything.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md

### F2.28 Natural-language semantic search for unlabelled content (RF: semantic search)
- **What the user does:** describes the image instead of naming a class, and finds images whose objects are not labelled yet.
- **Flow:** 1. Type free text with no filter selector (e.g. `person -class:helmet`). 2. Free text is treated as a CLIP-embedding query and returns nearest images, then the `-class:` filter removes the ones already labelled. 3. Combine with any other filter.
- **Why it is easy:** it turns "find what I forgot to label" into one sentence plus one negation, with no class taxonomy beforehand.
- **Gates:** embedding search needs an index that already covers the images; no documented score threshold or result cap in the UI.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md, https://roboflow.com/ai/image-deduplication

### F2.29 "More like this" from an existing image (RF: `like-image` / Similarity Search)
- **What the user does:** points at one image and asks for look-alikes, either among unlabelled images or inside the dataset.
- **Flow:** 1. Open an image in the editor → options menu. 2. **Find similar unassigned images** (to label next) or **Find similar images in dataset** (to spot repeats). 3. Results open as a visual result grid. 4. Same capability from code: `like-image:<id>` selector, `like_image=` in the SDK/API, and the Asset Library search bar.
- **Why it is easy:** the two scopes answer the two real questions — "what should I label next" and "is this already in here" — from the image the user is already looking at.
- **Gates:** similarity ranking only; no automatic duplicate flag or merge action (see F2.35).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/similarity-search-and-settings.md

### F2.30 Workspace search across projects with cursor pagination (RF: `search/v1`)
- **What the user does:** searches every project at once and pages through results.
- **Flow:** 1. POST a query to the workspace search endpoint. 2. Response rows carry the source project. 3. Page with `continuationToken` from the previous response. 4. CLI: `roboflow search "<query>" --limit --cursor --fields --json`.
- **Why it is easy:** the same syntax works at two scopes, so a per-project query is a workspace query with `project:` added.
- **Gates:** `project:foo` / `dataset:foo` selectors; per-page `limit` (CLI default 50).
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md

## E. Tags, metadata, batches, folders

### F2.31 Tag lifecycle: at upload, in bulk, then renamed or deleted project-wide (RF: image tags)
- **What the user does:** labels sets of images with plain words, then curates the vocabulary later.
- **Flow:** 1. At upload: tag field in the upload form (web), `tag_names=[...]` (SDK), `--tag` (CLI). 2. On existing images: select tiles → **Images Selected** → **Apply tags** → type arbitrary tags. 3. Vocabulary cleanup: project **Settings → Tags** → tick rows → **Rename** (enter new names → **Review Changes** → **Confirm Changes**) or **Delete** (review list → confirm). 4. Filter by tag in the image grid / assign view. 5. Use tags as a version filter (require/exclude) to train on a slice.
- **Why it is easy:** the rename path is a review-then-confirm diff, so a typo fix across 40k images is inspectable before it lands.
- **Gates:** none stated; tags are free text, so case/plural drift is on the user.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/add-tags-to-images.md

### F2.32 Typed custom metadata fields, per image, bulk-updatable (RF: Image Metadata)
- **What the user does:** attaches structured attributes (camera id, shift, score) and then filters on them.
- **Flow:** 1. Open an image → metadata section → key input + value input → Enter/Add; values auto-typed (`95`→number, `true`→boolean, else string). 2. Bulk: select images → apply, or API batch (≤1,000 IDs) → task URL → poll; the result counts successes and lists failures. 3. Search: `metadata:camera_id="cam001"`, `metadata:quality_score>80`, ranges via two bounds; Asset Library autocompletes keys and values from what exists. 4. Sidecar sync keeps them current (F2.18).
- **Why it is easy:** no schema to define up front — first use of a key creates it, and typing is inferred from what was typed.
- **Gates:** key charset `[A-Za-z0-9_.]`, first char letter/digit/underscore, no `/`; batch cap 1,000 images/request.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data/image-metadata.md

### F2.33 Batch as a first-class, nameable, mergeable container (RF: Dataset Batches)
- **What the user does:** names ingests so a later conversation ("the April batch") maps to a filter, and merges fragments back together.
- **Flow:** 1. Batch name at upload (default `Uploaded on <timestamp>` in the web UI; "Uploaded via API" for API pushes). 2. Filters: `job:<id>`, batch selector in search, batch card on the Annotate board. 3. Merge: row menu → **Merge Batches** → search + select ≥2 → merge; the largest batch survives and absorbs the rest, emptied cards disappear. 4. Delete: Unassigned only.
- **Why it is easy:** merging is defined by a deterministic rule ("largest survives") instead of asking the user to pick a target.
- **Gates:** cannot merge batches from different source videos or managed review queues; batch deletion is permanent and unrecoverable.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/manage-batches.md

### F2.34 Project folders with inherited permissions (RF: Project Folders)
- **What the user does:** groups projects, optionally hiding a group from most of the workspace.
- **Flow:** 1. Workspace → **+ New Folder** → name → Save (projects created inside are auto-added). 2. Move projects: row menu → **Move Project** → pick folder, or drag a project/folder card onto a folder (multi-select drag moves all). 3. Permissions: folder row menu → **Set Permissions** → **Anyone** (default) or **Restricted** → search members, assign a role per member → Save. 4. Deleting a folder never deletes contents — projects/Workflows/subfolders move up one level.
- **Why it is easy:** access is inherited down the tree with the subfolder override winning, so one restriction at the top covers a whole branch.
- **Gates:** Enterprise; access to a folder implies access to subfolders unless set otherwise; a member with access only to a deep subfolder sees it at top level with ancestor names hidden from list, breadcrumbs and search; API keys scoped to a folder inherit the creating member's visibility; moves require write on both folders; lockout prevention blocks a state where the actor loses access.
- **Sources:** https://docs.roboflow.com/datasets/manage/project-folders.md, https://docs.roboflow.com/datasets/manage/project-folders/project-folder-permissions.md

## F. Duplicates and dataset health

### F2.35 Exact-duplicate skip that preserves removed images' labels (RF: duplicate handling)
- **What the user does:** re-drops files without thinking; repeated content never doubles storage or splits.
- **Flow:** 1. Upload → duplicates skipped per image per project. 2. Merge two datasets → the union is free because the images are duplicate-backed. 3. Remove an image, upload it again → it rejoins with its **annotations and annotation status intact**, so a labelled image never returns as unlabelled. 4. Storage is charged once even across projects in a workspace.
- **Why it is easy:** the resurrection rule removes the fear of deleting: re-adding is non-destructive.
- **Gates:** matching is content hash (SHA-256 as of SDK 1.3.6); dedupe is per project, not per workspace, for the skip decision. Known failure mode: users report "uploaded 936, only 120 saved" when dedupe is not itemised in the result — see F2.1's per-file summary requirement.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md, https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md, https://roboflow.com/ai/image-deduplication

### F2.36 Near-duplicate discovery is a search, not a check (RF: like-image ranking)
- **What the user does:** sorts the dataset by visual similarity to a chosen image, then judges and removes/tags the look-alikes by hand.
- **Flow:** 1. Pick a frame (or use `like-image:<id>` / `like_image=`). 2. Grid sorted by CLIP similarity, near-identical frames adjacent. 3. User selects the ones to drop, tags them `dup`, or narrows a version with a tag filter. 4. `[inferred]` nothing in the docs shows a "these 14 are near-duplicates" cluster list, a similarity threshold control in the app, or a cross-split leakage check.
- **Why it is easy:** ranking instead of thresholding means the user's eye is the decision-maker, which is honest about CLIP's false positives.
- **Gates:** one anchor image at a time in the app; batch/cluster views must be built in code (Workflows cosine-similarity block + a threshold).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/use-roboflow-annotate/similarity-search-and-settings.md, https://roboflow.com/ai/image-deduplication

### F2.37 Health report whose charts are filters (RF: Dataset Health Check)
- **What the user does:** opens one tab, reads four numbers, then clicks a chart to jump to the images behind the number.
- **Flow:** 1. Project → **Dataset** → **Health Check** tab [loading: first computation can take minutes on large datasets; `[inferred]` progress or a spinner rather than partial charts]. 2. Header stats: image count, annotation count, average image size, median aspect ratio, missing annotations, null annotations [empty: no images → an upload prompt `[inferred]`]. 3. Class balance per split (train/valid/test). 4. Dimension insights: raw sizes and aspect ratios, with a note that resizing happens in versions, not here. 5. Annotation heat map: drag a region to see the images annotated there. 6. Object-count histogram: click a bar to see images with that many objects. 7. Interpretation text explains the failure each chart detects (concentration in one frame area; no null images; no 1-vs-many instances).
- **Why it is easy:** every chart is a doorway into the grid rather than a dead picture, so the report ends in a fixable list instead of a dashboard to admire.
- **Gates:** guidance is advisory (resize is "strongly recommended"); no automatic action.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-health-check.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/HealthCheck.tsx`

### F2.38 Cached health report with an explicit staleness flag (RF: `GET /health`, `regenerate`)
- **What the user does:** reads the API report, or asks for a fresh one when a decision depends on it.
- **Flow:** 1. GET the health endpoint → counts, class balance, object histogram (no heat map, no dimensions). 2. Read `generated`; the stored report may predate recent edits. 3. Pass `regenerate=true` → recompute during the request (minutes on large datasets).
- **Why it is easy:** the cached-vs-fresh decision is a parameter plus a timestamp, not a mystery about why numbers disagree with the grid.
- **Gates:** API surface is a subset of the UI; callers must not assume parity.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-health-check.md

## G. Splits

### F2.39 Split is decided at ingest and stored on the image (RF: split from folder / default split)
- **What the user does:** either relies on folder names from their old export or picks one split for the whole upload.
- **Flow:** 1. Upload with `train/`, `valid/`, `test/` folders → each image takes that folder's split. 2. No matching folder → the request's `split` value (zip default `train`). 3. Unmatched folder names (`train2017`) silently set no split → falls back to the default; `[inferred]` this is the most common "why is everything train?" cause. 4. Split shown as a badge on the tile and in the image attributes panel.
- **Why it is easy:** the folder layout carries the intent, so a standard COCO/YOLO export needs no mapping step.
- **Gates:** allow-list only: `train training valid validation val test testing`, case-insensitive.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/upload-a-dataset.md

### F2.40 Bulk split change from a selection (RF: "Change Dataset Split")
- **What the user does:** moves a hand-picked set into another split without touching the rest.
- **Flow:** 1. Select images (optionally after "Select all matching" on a query). 2. Bulk menu → **Change Dataset Split** → train/valid/test. 3. Large selections run in the background.
- **Why it is easy:** it is the same selection mechanism as tagging, so "these 40 hard negatives go to valid" is two clicks.
- **Gates:** none stated beyond role permissions.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md

### F2.41 Percentage rebalance with three move policies (RF: Step 2 Train/Test Split → Rebalance)
- **What the user does:** sets 70/20/10 (or anything) once and lets the system decide which images move.
- **Flow:** 1. **Versions** → **Generate New Version** → **Step 2: Train/Test Split** → **Rebalance**. 2. Set train/valid/test percentages; **Reset** returns to 70/20/10. 3. Choose policy: **move as few as possible** (keep current splits, move only enough) · **random shuffle** (reassign everything) · **random shuffle per upload batch or annotation job** (each batch independently hits the ratios). 4. Optional class scope: only images whose classes are all in the chosen set move (forces the "move as few" policy). 5. Large rebalances run as a background task with per-phase progress; the dialog can be dismissed and progress followed in **Activity Center**. 6. API equivalent: `POST /{ws}/{project}/splits/rebalance` → `202` + task id, with `mode`, `grouping`, `classes`; requires `project:update`.
- **Why it is easy:** the three policies name the actual trade-off (stability vs purity vs per-ingest balance) instead of exposing a bare percentage.
- **Gates:** rebalance changes the project, so it affects the *next* version; augmentation multiplier still capped (5x on Core, 20,000 version images per credit).
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version.md

### F2.42 Versions freeze their own split assignment (RF: version snapshots)
- **What the user does:** keeps training versions reproducible even after the project's splits change.
- **Flow:** 1. Generate version → the split at generation time is baked in. 2. Later edits to images, labels or splits leave existing versions untouched. 3. Rebalancing the project affects only versions generated afterwards.
- **Why it is easy:** "the numbers changed and I don't know why" is answered by "this version predates the rebalance".
- **Gates:** a version cannot be restored while its parent project is in Trash.
- **Sources:** https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version.md, https://docs.roboflow.com/platform/workspaces/trash.md

## H. Deletion and retention

### F2.43 Single-image removal: permanent, no trash (RF: Remove From Project)
- **What the user does:** removes one bad image from a project.
- **Flow:** 1. Open the image in the editor. 2. Three-dot menu → **Remove From Project** → **Confirm**. 3. Image and its annotations are gone permanently. 4. Re-uploading the same file restores the record with its annotations and status.
- **Why it is easy:** the confirmation is a single explicit step, and the "re-upload restores labels" rule is the real undo — but the user has to know it.
- **Gates:** permanent; images are NOT covered by the workspace Trash (which covers projects, versions, trainings, workflows only).
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/delete-an-image.md, https://docs.roboflow.com/platform/workspaces/trash.md

### F2.44 Bulk removal with a count-bearing confirm (RF: dataset multi-delete)
- **What the user does:** removes a set of bad frames after a health-check review.
- **Flow:** 1. **Dataset** page → hover tiles → tick checkboxes. 2. **Actions** dropdown → **Remove from Project**. 3. Confirm dialog names the selection; **Delete** proceeds. 4. Irrevocable; an image no other project uses is deleted for good, one shared elsewhere survives.
- **Why it is easy:** the confirm is the last gate and it sits immediately after the selection, so the count is still on screen.
- **Gates:** shared images survive project-level deletion; workspace-level delete (API/SDK) removes regardless of references and is flagged "use with care".
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/delete-an-image.md, https://docs.roboflow.com/datasets/manage/manage-images.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Dataset.tsx`

### F2.45 30-day Trash for containers, with parent-before-child restore (RF: Trash)
- **What the user does:** deletes a project/version/training/workflow by mistake and gets it back.
- **Flow:** 1. Delete → item leaves all listings, in-flight training for it is cancelled so credits stop. 2. **Settings → Trash** lists items grouped by type with who/when/days-left. 3. **Restore** per row or by checkbox; **Restore All**; the item returns to its original location. 4. Versions need their project out of Trash first; trainings need both. 5. **Delete Permanently** / **Empty Trash** exist only in the web app, behind a confirmation dialog. 6. Storage still bills during the 30 days. 7. A project deleted with "also delete images from Asset Library" shows an amber marker; images shared with other projects are always kept.
- **Why it is easy:** irreversibility is scoped by surface — scripts can only soft-delete, humans must click a button to destroy.
- **Gates:** RBAC permissions per action (`view_trash`, `trash_dataset`, `restore_version`, …); API/SDK/CLI expose no permanent delete; image-level deletion has no trash at all.
- **Sources:** https://docs.roboflow.com/platform/workspaces/trash.md

## Title-only / unverified

Pages whose titles I saw in `llms.txt` but did not open, so nothing above relies on them: `datasource-credentials/{aws-s3,gcs,azure}`, `datasource-policy-examples`, `upload-data-from-aws-gcp-and-azure/*`, `download-a-dataset`, `download-an-image`, `create-an-annotation-attribute`, `manage-classes`, `annotation-groups`, `rename-a-project`, `create-a-project`, `universe-search`, `download-a-universe-dataset`, `explore-images-in-a-universe-dataset`, `dataset-versions/exporting-data`, `image-preprocessing`, `image-augmentation`.

Claims I could not verify:
- **Upload failure taxonomy.** No docs page lists the actual error strings, per-file reason codes, or the retry policy. All per-file error copy above is `[inferred]`.
- **Grid vs list view, thumbnail size control, keyboard navigation in the browser, infinite scroll vs pagination.** Nothing in the fetched pages describes these. Pagination is documented only as API `offset`/`limit` and `continuationToken`; `[inferred]` the web grid pages and virtualises.
- **Saved views / named filter sets.** Mentioned nowhere. LabelDesk's filter-as-URL-params is already the stronger pattern.
- **Filter chips in the dataset grid.** Not documented (the Asset Library has a Filters/Raw toggle and metadata autocomplete; chips are implied by "remove filter" behaviour at most).
- **Health-check recommendation list.** The earlier repo note (`data-layer.md`) claims built-in recommendations (add nulls, fix missing, cover other regions, include 0/1/many, use resize). The health-check page I fetched this session presents those as prose guidance inside each chart section, not as a scored recommendation list. Treat "recommendation cards" as unconfirmed.
- **Blur / exposure / class-balance "checks" with thresholds.** Roboflow's health check has class balance and dimensions only; there is no blur/brightness metric on the page (Encord has those). Do not claim RF parity there.
- **Image detail panel completeness** (exact fields, whether tags and metadata are one panel or two). The editor page describes an Annots drawer + Attributes sidebar + a metadata editor; the exact layout is inferred.
- **Annotation-to-existing-image rule conflict.** `adding-data.md` says annotations can only arrive with their images; `manage-images.md` documents attaching an annotation to an existing image ID. The API page is the newer, more specific source; the UI rule stands.
- **Credit cost of an upload vs storage vs version** is per-credit rate only (10,000 uploads, 5,000 stored, 20,000 version images per credit) — no per-image price.

## Coverage gaps and what to check next

1. **Upload error copy** — open `help.roboflow.com` upload-error articles and 2-3 `discuss.roboflow.com` threads ("only N of M images saved", "unsupported video") to pin the loud-vs-silent failure list. This is the single most useful thing still missing for the redesign.
2. **Grid mechanics** — one screenshot-free way in: the `browse` query parameters used in Universe fork examples (`queryText`, `pageSize`, `startingIndex`) hint at the grid's paging contract; check `docs.roboflow.com/reference` for a browse/search pagination schema.
3. **Saved views** — check the changelog index for "saved search" / "views"; if absent, LabelDesk should treat saved views as a differentiator, not parity.
4. **Screening policy** — which content triggers a hold, and whether the held state is visible in the web grid (not just the API). Affects whether LabelDesk needs a third upload state at all.
5. **Datasource quota/plan gating** — pricing lists only "Dataset Size Limit: Uncapped; On-demand" and folder permissions as Enterprise. Which plan opens Datasources is unconfirmed; check `billing-and-plans.md`.
6. **Bulk-action ceiling** — the docs say "large selections process in the background" without a number; find the async-task limits page before designing LabelDesk's threshold.
