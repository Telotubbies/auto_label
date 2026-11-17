# Part 2 — Area 2 Upload and data management

Gap rows: 34 (23 PARTIAL, 11 MISSING) · Cards: 44 · Hours: 125.5

Card hours sum to 125.5. Row hours below list a shared card in full (e.g. T-068 serves `2-F2.2`, `2-F2.4`
and `2-F2.7`), so the Hours column overlaps and is not expected to add up to the header.

## Mapping

| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 2-F2.1 | HAVE | — (guard T-001) | — | — | — |
| 2-F2.2 | PARTIAL | T-063, T-068 | A | S | 5.5 |
| 2-F2.3 | PARTIAL | T-064, T-065 | C | M | 6 |
| 2-F2.4 | PARTIAL | T-066, T-068 | C | M | 6 |
| 2-F2.5 | MISSING | T-067 | C | S | 2.5 |
| 2-F2.6 | PARTIAL | T-071, T-072 | B | M | 5.5 |
| 2-F2.7 | MISSING | T-066, T-068 | C | S | 6 |
| 2-F2.8 | MISSING | T-069, T-070 | C | L | 5.5 |
| 2-F2.9 | HAVE | — (guard T-001) | — | — | — |
| 2-F2.10 | PARTIAL | T-073 | C | S | 2.5 |
| 2-F2.11 | MISSING | T-074 | C | M | 3 |
| 2-F2.12 | PARTIAL | T-074 | C | S | 3 |
| 2-F2.13 | PARTIAL | T-075 | C | S | 3 |
| 2-F2.14 | PARTIAL | T-075 | C | S | 3 |
| 2-F2.15 | PARTIAL | T-076, T-080 | C | M | 6 |
| 2-F2.16 | PARTIAL | T-077, T-080 | C | M | 6 |
| 2-F2.17 | PARTIAL | T-078, T-081 | C | L | 6 |
| 2-F2.18 | MISSING | T-083 | C | M | 3 |
| 2-F2.19 | PARTIAL | T-079, T-081 | C | M | 5.5 |
| 2-F2.20 | MISSING | — (area 1: fork, band T-010–T-059) | — | M | — |
| 2-F2.21 | MISSING | T-085, T-086 | C | M | 5 |
| 2-F2.22 | HAVE | — (guard T-002) | — | — | — |
| 2-F2.23 | HAVE | — (guard T-003) | — | — | — |
| 2-F2.24 | PARTIAL | T-087 | B | S | 3 |
| 2-F2.25 | MISSING | — (area 1: asset library, band T-010–T-059) | — | L | — |
| 2-F2.26 | PARTIAL | T-087, T-089 | C | S | 6 |
| 2-F2.27 | PARTIAL | T-060, T-061, T-062 | A | M | 9 |
| 2-F2.28 | MISSING | T-090 | C | M | 3 |
| 2-F2.29 | PARTIAL | T-088 | B | S | 2.5 |
| 2-F2.30 | MISSING | T-091 | C | M | 3 |
| 2-F2.31 | PARTIAL | T-092 | C | S | 3 |
| 2-F2.32 | MISSING | T-082, T-084 | C | M | 6 |
| 2-F2.33 | PARTIAL | T-093 | C | M | 3 |
| 2-F2.34 | PARTIAL | T-094, T-095, T-096 | C | M | 9 |
| 2-F2.35 | PARTIAL | T-097 | A | S | 2.5 |
| 2-F2.36 | PARTIAL | T-098, T-099 | C | M | 6 |
| 2-F2.37 | HAVE | T-102, T-103 (planned: heat map + histogram gap, brief §4) | C | M | 5 |
| 2-F2.38 | HAVE | — (guard T-004) | — | — | — |
| 2-F2.39 | HAVE | — (guard T-005) | — | — | — |
| 2-F2.40 | HAVE | — (guard T-002) | — | — | — |
| 2-F2.41 | PARTIAL | T-100, T-101 | B | M | 5.5 |
| 2-F2.42 | HAVE | — (guard T-005) | — | — | — |
| 2-F2.43 | HAVE | — (guard T-006; label revival covered by T-097) | — | — | — |
| 2-F2.44 | HAVE | — (guard T-006) | — | — | — |
| 2-F2.45 | PARTIAL | — (area 7: trash, band T-380–T-469) | — | M | — |

## Shared-file users (suggested merge order)

| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/services/flags.py` | T-060, T-063, T-064, T-066, T-069, T-073, T-074, T-076, T-082, T-083, T-085, T-088, T-089, T-090, T-091, T-092, T-093, T-094, T-097, T-098, T-100, T-102 |
| `apps/backend/app/routers/images.py` | T-061 (exclusive), T-063, T-069, T-070, T-073, T-078, T-082, T-083, T-084, T-087, T-088, T-089, T-090, T-097 |
| `apps/backend/app/models/project.py` | T-069 (exclusive), T-078, T-082, T-087, T-094, T-095 |
| `apps/backend/app/schema/dataset.py` | T-069, T-078, T-082, T-087, T-094, T-095 |
| `apps/backend/app/schema/__init__.py` | T-094 |
| `apps/backend/app/routers/projects.py` | T-085 (exclusive), T-083, T-087, T-092, T-093, T-095, T-098 |
| `apps/backend/app/routers/uploads.py` | T-066 (exclusive), T-074 |
| `apps/backend/app/services/importers.py` | T-064 (exclusive), T-065, T-083 |
| `apps/backend/app/services/connectors.py` | T-077 (exclusive), T-076, T-078, T-079, T-083 |
| `apps/backend/app/routers/connectors.py` | T-077 (exclusive), T-078, T-079 |
| `apps/backend/app/models/storage.py` | T-076 (exclusive), T-079 |
| `apps/backend/app/routers/workspaces.py` | T-094, T-095 |
| `apps/backend/app/routers/__init__.py` | T-066, T-076, T-091 |
| `apps/backend/app/models/__init__.py` | T-076, T-079, T-095 |
| `apps/backend/app/handlers/__init__.py` | T-066 |
| `apps/backend/app/handlers/versioning.py` | T-089, T-100 |
| `apps/backend/app/handlers/ops.py` | T-085 |
| `apps/backend/app/config.py` | T-066, T-085, T-089, T-100 |
| `apps/backend/app/bootstrap.py` | T-076 |
| `apps/backend/app/services/secretbox.py` | T-076 |
| `apps/backend/app/apikeys.py` | T-095 |
| `apps/backend/app/deps.py` | T-095 |
| `apps/backend/app/worker.py` | T-079 |
| `apps/backend/app/services/query.py` | T-060 (exclusive), T-082 |
| `apps/frontend/src/lib/api/dataset.ts` | T-061, T-063, T-066, T-070, T-071, T-073, T-082, T-084, T-087, T-088, T-089, T-090, T-092, T-093, T-098, T-099, T-100, T-101, T-102 |
| `apps/frontend/src/lib/api/core.ts` | T-085, T-086, T-091, T-094, T-095, T-096 |
| `apps/frontend/src/lib/api/governance.ts` | T-076, T-077, T-078, T-079 |
| `apps/frontend/src/features/project/Dataset.tsx` | T-062 (exclusive), T-070, T-084, T-089 |
| `apps/frontend/src/features/project/FilterBar.tsx` | T-062 (exclusive), T-084, T-090 |
| `apps/frontend/src/features/settings/Settings.tsx` | T-080, T-081 |
| `apps/frontend/src/features/workspace/Home.tsx` | T-086, T-096 |
| `apps/frontend/src/features/editor/Editor.tsx` | T-073, T-087 |
| `apps/frontend/src/features/editor/Panels.tsx` | T-084, T-087 |
| `apps/frontend/src/features/editor/ImageMenu.tsx` | T-087 (exclusive), T-088 |
| `apps/frontend/src/features/project/HealthCheck.tsx` | T-099, T-103 |
| `apps/backend/openapi.json`, `apps/frontend/src/lib/api-types.gen.ts` | every card marked "OpenAPI: yes" — regenerate once, last, in card order T-061 … T-102 |

## Cards

| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-060 | Query grammar and compiler for the dataset grid | A | 3 | R3 | no | `services/query.py`, `tests/test_dataset_query.py` |
| T-061 | Serve the query language from the images route | A | 3 | R3 | no | `routers/images.py`, `tests/test_images_query.py` |
| T-062 | One filter bar, a filters popover and saved-view chips | A | 3 | R4 | no | `features/project/FilterBar.tsx`, `lib/query.ts`, `features/project/Dataset.tsx`, `tests/query-chips.test.mjs` |
| T-063 | Replace-annotations switch and orphan-label report | A | 2.5 | R3 | no | `tests/test_upload_overwrite.py` |
| T-064 | Detect the import format and normalise class names | C | 3 | R3 | no | `services/importers.py`, `services/import_normalize.py`, `tests/test_import_normalize.py` |
| T-065 | Read CreateML, Darknet-folder and Pascal-Seg uploads | C | 3 | R3 | no | `services/import_extra.py`, `tests/test_import_extra.py` |
| T-066 | Archive imports as a job, and ingest from a URL | C | 3 | R3 | yes | `routers/uploads.py`, `handlers/intake.py`, `tests/test_upload_paths.py` |
| T-067 | Capture training frames from the camera | C | 2.5 | R4 | no | `features/project/CameraCapture.tsx`, `lib/capture.ts`, `tests/camera-capture.test.mjs` |
| T-068 | Upload page: pre-flight, archive branch, URL row, result sheet | C | 3 | R4+R3 | no | `features/project/Upload.tsx`, `lib/uploadSummary.ts`, `tests/upload-summary.test.mjs` |
| T-069 | Screening state on every ingested image | C | 3 | R3 | no | `models/project.py`, `services/screening.py`, `tests/test_screening.py` |
| T-070 | The awaiting-screening queue on the dataset | C | 2.5 | R4+R3 | no | `features/project/ScreeningQueue.tsx`, `tests/screening-queue.test.mjs`, `tests/test_screening_bulk.py` |
| T-071 | Predict and trim video frame extraction before the job | B | 2.5 | R3 | no | `routers/videos.py`, `services/video.py`, `handlers/streams.py`, `tests/test_video_plan.py` |
| T-072 | Frame-extraction dialog with trim and hand-picked frames | B | 3 | R4 | no | `features/project/VideoExtractDialog.tsx`, `lib/extractPlan.ts`, `tests/video-extract.test.mjs` |
| T-073 | Attach labels to a stored image, with a stale-write guard | C | 2.5 | R3 | yes | `routers/devapi.py`, `tests/test_api_attach.py` |
| T-074 | Resumable upload sessions for archives and video | C | 3 | R3 | yes | `services/upload_sessions.py`, `tests/test_upload_sessions.py` |
| T-075 | SDK and CLI upload: workers, retries, no-wait and JSON | C | 3 | R3 | no | `packages/sdk/labeldesk/client.py`, `packages/sdk/labeldesk/cli.py`, `tests/test_sdk_cli.py` |
| T-076 | A reusable credential store for bucket access | C | 3 | R3 | yes | `models/storage.py`, `services/credentials.py`, `routers/credentials.py`, `tests/test_credentials.py` |
| T-077 | Prove a bucket connection and get path-style right | C | 3 | R3 | yes | `services/connectors.py`, `routers/connectors.py`, `tests/test_connector_setup.py` |
| T-078 | Mirror a bucket into a project: globs, naming, orphans | C | 3 | R3 | yes | `services/mirror.py`, `tests/test_mirror.py` |
| T-079 | Sync run controls, history and a daily schedule | C | 2.5 | R3 | no | `services/mirror_runs.py`, `tests/test_mirror_runs.py` |
| T-080 | Connectors screen: credentials and a proven connection | C | 3 | R4 | no | `features/settings/Connectors.tsx`, `lib/connectorForm.ts`, `tests/connector-form.test.mjs` |
| T-081 | Datasource screen: mirror rules, run controls and history | C | 3 | R4 | no | `features/settings/Datasources.tsx`, `lib/mirrorForm.ts`, `tests/mirror-form.test.mjs` |
| T-082 | Typed per-image metadata with bulk update | C | 3 | R3 | no | `services/metadata.py`, `tests/test_metadata.py` |
| T-083 | JSON sidecars and the metadata conflict policy | C | 3 | R3 | no | `services/sidecars.py`, `tests/test_sidecars.py` |
| T-084 | Metadata editor and bulk metadata dialog | C | 3 | R4 | no | `features/editor/MetadataEditor.tsx`, `features/project/BulkMetadataDialog.tsx`, `lib/metadataForm.ts`, `tests/metadata-form.test.mjs`, `tests/test_meta_keys.py` |
| T-085 | Merge projects into a third one, without re-uploading | C | 3 | R3 | no | `services/merge.py`, `routers/projects.py`, `tests/test_project_merge.py` |
| T-086 | Merge dialog with a union preview | C | 2 | R4 | no | `features/workspace/MergeProjects.tsx`, `lib/mergePreview.ts`, `tests/merge-preview.test.mjs` |
| T-087 | Editor image menu, attributes block, cover and download | B | 3 | R4+R3 | no | `features/editor/ImageMenu.tsx`, `features/editor/AttributesBlock.tsx`, `tests/image-menu.test.mjs`, `tests/test_image_menu.py` |
| T-088 | "Find similar" from the image in front of me | B | 2.5 | R3 | no | `services/similar.py`, `lib/similar.ts`, `tests/test_similar.py`, `tests/similar.test.mjs` |
| T-089 | Export the images matching the current query | C | 3 | R3 | no | `services/selection_export.py`, `features/project/ExportSelectionDialog.tsx`, `lib/exportEstimate.ts`, `tests/test_selection_export.py`, `tests/export-estimate.test.mjs` |
| T-090 | Search unlabelled content by description | C | 3 | R3 | no | `services/semantic.py`, `features/project/SemanticSearch.tsx`, `lib/semantic.ts`, `tests/test_semantic.py`, `tests/semantic.test.mjs` |
| T-091 | Workspace-wide image search with cursor pages | C | 3 | R4+R3 | no | `routers/search.py`, `services/search.py`, `features/workspace/Search.tsx`, `lib/search.ts`, `tests/test_search.py`, `tests/search.test.mjs` |
| T-092 | Rename, merge and delete tags with a reviewable diff | C | 3 | R4+R3 | no | `features/project/TagManager.tsx`, `lib/tagDiff.ts`, `tests/test_tags.py`, `tests/tag-diff.test.mjs` |
| T-093 | Rename, merge and delete batches from the board | C | 3 | R4+R3 | no | `features/project/BatchMenu.tsx`, `lib/batchActions.ts`, `tests/test_batches.py`, `tests/batch-actions.test.mjs` |
| T-094 | Nest folders and move projects in bulk | C | 3 | R3 | no | `services/folders.py`, `tests/test_folders.py` |
| T-095 | Folder access that the server enforces | C | 3 | R3 | yes | `services/folder_access.py`, `tests/test_folder_access.py` |
| T-096 | Folder tree, drag-move and the access dialog | C | 3 | R4 | no | `features/workspace/FolderTree.tsx`, `lib/folderTree.ts`, `tests/folder-tree.test.mjs` |
| T-097 | Itemise duplicates and revive a removed image with its labels | A | 2.5 | R3 | no | `services/dedupe.py`, `tests/test_upload_dedupe.py` |
| T-098 | Near-duplicate clusters with an adjustable threshold | C | 3 | R3 | no | `services/duplicates.py`, `tests/test_duplicates.py` |
| T-099 | Duplicate review: side-by-side, tag or remove | C | 3 | R4 | no | `features/project/Duplicates.tsx`, `lib/duplicates.ts`, `tests/duplicates.test.mjs` |
| T-100 | Rebalance splits with three move policies | B | 3 | R3 | no | `services/rebalance.py`, `tests/test_rebalance.py` |
| T-101 | Rebalance step in the version wizard, with progress | B | 2.5 | R4 | no | `features/project/RebalanceDialog.tsx`, `lib/rebalanceForm.ts`, `tests/rebalance-form.test.mjs` |
| T-102 | Heat-map region selection for the health report | C | 2 | R3 | no | `tests/test_heat_selection.py` |
| T-103 | Health charts that are filters, not decoration | C | 3 | R4 | no | `features/project/HealthCharts.tsx`, `lib/healthCharts.ts`, `tests/health-charts.test.mjs` |

## Judgment calls

- **2-F2.37 (HAVE) is planned, not guarded** — the report exists, but the record's own gap is "annotation heat map
  and object-count histogram are missing" and brief §4 assigns health-report charts to area 2. T-102/T-103 build
  only that gap; the existing cards stay under guard T-004.
- **2-F2.20 → area 1** (fork/clone) and **2-F2.25 → area 1** (asset library) per brief §4; **2-F2.45 → area 7**
  (trash). Their rows carry no card here and the mapping names the owning band.
- **2-F2.6 boundary** — video upload, trim, sampling and hand-picked frames are planned here (T-071/T-072); the
  action-segment timeline for recognition projects stays with area 3.
- **2-F2.12 folded into T-074** — video and archive share one signed-grant service; only the `kind` differs, so two
  cards would duplicate the token, replay guard and status endpoint.
- **2-F2.4 browser-side zip expansion deliberately not planned** — no zip library is installed and
  `DecompressionStream` would mean an ~80-line central-directory reader for no visible gain. The server splits at
  300 entries, so the user still sees one fast path and one background job.
- **2-F2.8 has no moderation vendor** — LabelDesk ships a manual hold/verdict gate with the same five states
  (`pending/passed/rejected/failed`), a project-level "hold uploads" switch and a release/discard queue. `failed`
  stays reserved and is never set by this plan.
- **2-F2.3 TFRecord/COCO-Camera-Trap are excluded** — they need `protobuf`/`av`, and the area forbids a new
  dependency; the answer for those exports is "export COCO from that tool".
- **Wave assignment for rows outside the canonical list** follows brief §3 top-down: `2-F2.2`, `2-F2.27`, `2-F2.35`
  are A (first-hour upload, query, re-drop); `2-F2.6`, `2-F2.24`, `2-F2.29`, `2-F2.41` are B (editor and version
  mechanics); the rest are C (dataset, metadata, connectors). No D row belongs to this area, and pure visual passes
  (REDESIGN S3/S6) stay with the E lane — this area ships their functional states (pre-flight line, result sheet,
  job tray, uploaded/approved vocabulary) inside T-062 and T-068.
- **Guard ids for HAVE rows are assigned by theme** (`T-001` ingest/refusal, `T-002` grid and bulk, `T-003` board,
  `T-004` health report, `T-005` splits/versions, `T-006` deletion) because `backlog/guards.md` was not in the tree
  while this part was written. The PM should re-point them if the guard card set differs; no card here plans a
  HAVE row's behaviour.
- **Cross-workspace ids on image routes keep `image_ctx`'s existing refusal.** Every project-scoped route in this
  part answers 404 for a foreign project (contract met). Image-scoped routes reuse `deps.image_ctx`, which today
  answers 403 for a non-member and 404 for a deleted image; changing that helper is a guard-protected path, so the
  cards state "no new path that reveals another workspace's data" instead of forcing a 404 rewrite.
- **One exclusive owner per hot file, shared edits listed by line.** `models/project.py` (T-069),
  `routers/images.py` (T-061), `routers/projects.py` (T-085), `routers/connectors.py` + `services/connectors.py`
  (T-077), `services/importers.py` (T-064), `routers/uploads.py` (T-066), `models/storage.py` (T-076),
  `services/query.py` (T-060), `Dataset.tsx` (T-062), `FilterBar.tsx` (T-062), `Upload.tsx` (T-068). Later cards
  name their exact one-line addition under Shared; the PM serialises that order.
- **Foreign rows covered by this part's cards (do not duplicate them):** `1-F4.3` → T-060/T-061/T-062;
  `4-F4.12` → T-100/T-101; `4-F4.39`, `4-F4.42`, `4-F4.43` → T-102/T-103; `7-F7.46`, `7-F7.47`, `7-F7.48` →
  T-076…T-081.
