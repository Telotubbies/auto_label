# LabelDesk v2 ↔ Roboflow parity matrix

Baseline: `feat/labeldesk-v2` read at `5bdf46f`, re-checked at `fe8ef1a` (2026-11-17). Two merges landed
during the audit (task 31 workflows, task 30 tiling); every status below was re-checked against
`fe8ef1a`, and line numbers may drift by two or three in the files those merges touched. Evidence
base: the seven area files in this folder (Roboflow public docs, blog, changelog and pricing, cited
per feature) against the current code in `apps/backend` and `apps/frontend`.

Status rules:

- **HAVE** — the flow exists end to end and a user can finish it without leaving the product.
- **PARTIAL** — a real implementation exists but a documented part of the flow is missing
  (an option, a state, a permission path or a second surface).
- **MISSING** — no implementation, or only a data field with no flow behind it.

Priority is for a commercial CV labeling SaaS, not for Roboflow's own roadmap:
**Must** = a buyer evaluates the product on it; **Should** = competitive gap buyers notice in a
trial; **Could** = differentiation or long-tail. Size: **S** ≤ 1 day, **M** 2–5 days,
**L** > 1 week of one engineer.

Each area is counted at its end. `parity-report.md` holds the owner summary.

Row IDs are `<area>-<feature id in that area file>`, e.g. `3-F3.46` is `03-annotate.md` §F3.46.
The area file holds the full flow, states and sources for that row.

---

## Area 1 — Workspace, projects, first run

Source: `01-workspace-projects.md` (F1.1–F6.3, 27 features).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 1-F1.1 | One-screen workspace creation with plan choice inline | PARTIAL | `apps/backend/app/routers/auth.py:176` auto-names the workspace from the signup name; `apps/frontend/src/features/settings/Settings.tsx:1109` has a separate "Create a workspace" screen | No plan picker and no slug preview in the flow; the workspace name is derived, not chosen; the plan decision lives pages away in Settings → Plan & Usage | Could | S |
| 1-F1.2 | Three setup questions that seed an assistant | MISSING | No assistant or setup-question surface under `apps/frontend/src/features` | First run asks nothing about the task, so the home screen cannot tailor itself | Could | M |
| 1-F1.3 | Assistant as the post-signup home, with background-task list | MISSING | None; post-signup lands on the project list (`Home.tsx:99`) | A new user meets an empty project list instead of an artifact | Could | L |
| 1-F1.4 | Guided tour as re-runnable coach marks | PARTIAL | `features/workspace/Tour.tsx:8-49` (non-modal card, focus ring, reduced-motion), `dashboardRules.ts:58,75-81` (steps, per-user key) | No replay entry once dismissed, so a user who skips cannot get it back | Should | S |
| 1-F1.5 | API key created once, scoped, listed with usage | HAVE | `routers/workspaces.py:238-282` (scopes, publishable keys, value returned once), `features/settings/Settings.tsx:823` | No roll/rotate action; `last_used` is returned but not surfaced per key | Should | S |
| 1-F2.1 | Type-first creation that lands on upload | HAVE | `features/workspace/Home.tsx:24-72` (name, group, licence, folder, classes, type cards), `:39` navigates to `upload` | No empty-state preview of what each type unlocks beyond two chips | — | — |
| 1-F2.2 | Eight task types with outcome-worded descriptions | PARTIAL | `Home.tsx:14-20` has 5 (detection, instance seg, classification, keypoints, anomaly) | Semantic segmentation, multi-label classification, action/video and multimodal are absent; anomaly is a LabelDesk-only extra | Must | M |
| 1-F2.3 | The type silently drives tools, import, training and export | PARTIAL | `apps/backend/app/adapters/ultralytics_ad.py` task map; `lib/nav/visibility.ts` hides type-specific nav; `models/project.py:31` multilabel flag | The editor does not restrict shape tools per type, and polygon→box conversion rules are not surfaced; no per-type import contract | Must | M |
| 1-F2.4 | Annotation groups share one class vocabulary | PARTIAL | `routers/projects.py:113,133,156-165` stores `annotation_group` | The field is a label only; classes are per project (`models/project.py`), so a second project over the same imagery re-types its vocabulary | Should | M |
| 1-F2.5 | Creation is scriptable with the same shape as the form | PARTIAL | `routers/projects.py:119` REST create; `packages/sdk/labeldesk/client.py:100-135` has upload/export/train/predict only | SDK/CLI cannot create a project, set its type or folder; no agent/MCP surface | Should | S |
| 1-F3.1 | Project "about" page with description and public URL | MISSING | `features/project/ProjectSettings.tsx:12-16,58-68` has name/group/visibility/licence but no description field or public link | Nowhere to write the blurb a visitor or teammate reads, and no URL shown when a project becomes public | Should | S |
| 1-F3.2 | Sidebar is the lifecycle; upload is the landing page | HAVE | `routes/project/index.tsx` + `lib/nav/project/{data,label,models,deploy}.ts`; `Home.tsx:39` | Order is DATA → LABEL → MODELS → STUDIO → DEPLOY; STUDIO sits between train and deploy, which breaks the one-column story | Should | S |
| 1-F3.3 | Four-column annotate board is the labeler's home | HAVE | `features/project/AnnotateBoard.tsx`; `routers/images.py:356-443` board + move | Review column depends on a flag; no batch merge/delete affordances on the board (batch ops live on the dataset grid) | Should | M |
| 1-F3.4 | Counters appear where the decision is made | HAVE | `Home.tsx:156` images/models per card; `routers/projects.py:392` analytics | No per-project recent activity on the card | Could | S |
| 1-F4.1 | Folders above projects, move by drag, delete lifts contents | PARTIAL | `Home.tsx:115-131` folders; `:144-145` move via menu; `routers/workspaces.py:360-390` | Move is a menu pick, not drag; no nesting; no multi-select move | Should | S |
| 1-F4.2 | Workspace-wide media search (asset library) | MISSING | Search is project-scoped only (`features/project/Dataset.tsx`) | A team cannot ask "where is this image used" across projects; no bulk workspace tag/export | Should | L |
| 1-F4.3 | Query language with chips, negation, class counts | PARTIAL | `routers/images.py:190-300` accepts q/split/status/class/tag/batch/annotated/mp/ar/ann; `Dataset.tsx` exposes them as separate controls | No boolean/negation, no `class:x>=4`, no raw-query toggle, no semantic search, no saved views; filter state is not shareable as a URL contract | Must | M |
| 1-F4.4 | Public dataset discovery with image-similarity search | MISSING | No gallery route (`routes/public.routes.tsx` is auth + landing only) | No acquisition loop from public datasets, no similarity search entry point | Should | L |
| 1-F5.1 | Publish is a menu action plus a licence, with a workspace kill switch | PARTIAL | `Home.tsx:65-66,152`; `ProjectSettings.tsx:64-65` | Visibility is chosen in two places with different wording; no workspace-level policy switch, no PII warning at the moment of publishing | Should | S |
| 1-F5.2 | Visitor sees a dataset page whose CTA is "copy into my account" | MISSING | No public project route or viewer | A public project is a flag with no page behind it, so publishing today only changes an icon | Should | M |
| 1-F5.3 | Fork errors enumerated (402/403/404/409/422) | MISSING | No fork/clone endpoint in `routers/projects.py` | Cloning a project or dataset is impossible from any surface | Should | S |
| 1-F5.4 | Three invite routes, role at invite time, visible pending state | PARTIAL | `features/settings/Settings.tsx:759`; `routers/workspaces.py:156-193` (email, role, token link, pending, delete) | No static per-role join link, no same-domain join request, no resend action, no expiry shown | Must | M |
| 1-F5.5 | Per-project ownership transfer | MISSING | Projects have no owner column; only workspace `owner_id` (`models/workspace.py`) | The person who can delete a project is "any admin", not a named colleague | Could | S |
| 1-F5.6 | Soft delete with a 30-day trash, who/when/days left | PARTIAL | `routers/workspaces.py:399-425`; `features/settings/Settings.tsx:1082-1100` | Trash lists projects only; versions, runs and workflows are hard-deleted (`routers/versions.py:95`, `routers/training.py:309`); no deleter, no days-left, no restore selection | Should | S |
| 1-F6.1 | Returning user sees folders then projects, admin tree beside | HAVE | `Home.tsx:97-167`; `lib/nav/workspace/{core,build,govern,footer}.ts` | — | — | — |
| 1-F6.2 | A brand-new workspace has a designed empty state | HAVE | `Home.tsx:162-165` EmptyState; `Dashboard.tsx:52-66` checklist; `Tour.tsx` | Checklist and empty state both compete for the same first screen | Could | S |
| 1-F6.3 | Plan and role gates decide which screens exist | PARTIAL | `lib/nav/audience.ts`; `routers/rbac.py:31-48`; `services/metering.py:91-106` (402 on quota) | Quotas are enforced but product surfaces are not plan-gated: review mode, labeling analytics and labeler seats are free, so plan tiers have nothing to sell | Should | M |

**Area 1 count:** 7 HAVE · 12 PARTIAL · 8 MISSING (27).

---

## Area 2 — Upload and data management

Source: `02-upload-data.md` (F2.1–F2.45, 45 features).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 2-F2.1 | Drop ingest with a duplicate pre-check and a counted summary | HAVE | `features/project/Upload.tsx:66-77` (SHA-256 pre-check), `:98-129` (batched, per-file failures grouped), `routers/images.py:77-81` | Selection list has no thumbnail strip; no "remove this file before upload" per row | — | — |
| 2-F2.2 | Pre-labelled upload with an overwrite switch | PARTIAL | `Upload.tsx:11,34-48` pairs image with label by stem; `routers/images.py:142-152` imports and sets `done`/`review` | No "replace existing annotations" toggle, no per-file orphan-label report; a re-upload of labelled images cannot update labels | Must | S |
| 2-F2.3 | Broad format acceptance with class-name normalisation | PARTIAL | `services/importers.py:4-5,23-35` (COCO, Label Studio, YOLO, VOC, CVAT, OBB inference) | Six families vs roughly forty; no CreateML/TF-record/Darknet-folder/Pascal-Seg import; class sanitising is not documented to the user | Must | M |
| 2-F2.4 | Two-speed archive ingest with background completion | PARTIAL | `Upload.tsx:35-48` sends each zip as its own chunk; `routers/images.py:168` caps 2,000 files/request | No browser-vs-server threshold, no task object to leave and return to; a very large zip is a single blocking request | Should | M |
| 2-F2.5 | Camera capture as an upload source | MISSING | Upload has no camera control; `features/playground/useCamera.ts` is a different surface | Field data must round-trip through the phone's gallery | Should | S |
| 2-F2.6 | Video upload with a frame-extraction dialog | PARTIAL | `routers/videos.py:39-80` (fps / every-N-seconds / scene modes, async job), `features/project/VideoTimeline.tsx` | No trim handles, no manual frame picking, no live frame-count preview before the job starts | Should | M |
| 2-F2.7 | Server-side fetch from a public URL | MISSING | `routers/images.py:164-179` is multipart only | A camera gateway or crawler must fetch and forward bytes itself | Could | S |
| 2-F2.8 | Screening hold with a per-image verdict | MISSING | No screening state on `models/project.py:86-110` | No moderation state, so a blocked image is indistinguishable from a broken upload | Could | L |
| 2-F2.9 | One refusal rule set on every ingest path | HAVE | `routers/images.py:95-98` (size, plan, unreadable), `:168-176` (2,000 files, MB budget), same `ingest()` for web/API/SDK | The 2,000-file cap is per request, so a folder upload succeeds where one big API call fails | Should | S |
| 2-F2.10 | Single-image REST upload with late annotation attach | PARTIAL | `routers/devapi.py:65`; `routers/images.py:533` PUT annotations per image id | No URL/bytes-body variant, no `expectedGroupVersion` concurrency guard, so a second writer silently overwrites | Should | S |
| 2-F2.11 | Archive REST upload via signed URL plus task polling | MISSING | No signed-URL flow; `routers/projects.py:506-530` jobs are internal only | Large imports cannot be resumed, and no task id is handed back to CI | Could | M |
| 2-F2.12 | Video REST upload in the same three steps | PARTIAL | `routers/videos.py:39` single multipart + job; no prepare/status split | A 3 GB video over a flaky link restarts from zero | Could | S |
| 2-F2.13 | SDK bulk upload with workers, retries and project creation | PARTIAL | `packages/sdk/labeldesk/client.py:100-107` one request, no retry/worker knobs | Only ≤2,000 files per call, no exponential retry, cannot create the destination project | Should | S |
| 2-F2.14 | CLI upload with no-wait and JSON output | PARTIAL | `packages/sdk/labeldesk/cli.py:79-93` (`--batch/--split/--tags`, `--json`), `--wait` on export/train | No no-wait task id for upload, no concurrency or retry flags, no zip-download path | Could | S |
| 2-F2.15 | Reusable bucket credentials, separate from the datasource | PARTIAL | `services/connectors.py:1-130` stores credentials inside each connector | Keys are retyped per connector; no credential object, no rotation, no UI (`features/` has no connector screen) | Could | M |
| 2-F2.16 | Datasource connection configuration with a path-style control | PARTIAL | `routers/connectors.py:32-70`; `services/connectors.py:88-117` endpoint/account validation | S3-compatible custom endpoints are refused in multi-tenant mode; no path-style toggle; connection is proven only on first sync | Could | M |
| 2-F2.17 | Mirror configuration: destination, globs, naming, orphans | PARTIAL | `routers/connectors.py:71-100` read-only object listing and sync | No include/exclude globs, no naming strategy, no orphan policy, no destination choice; everything lands in one project | Could | L |
| 2-F2.18 | JSON metadata sidecars with a conflict policy | MISSING | `models/project.py:86-110` has tags but no metadata map | No structured per-image metadata at all, so camera/shift/lot cannot be filtered or carried into exports | Should | M |
| 2-F2.19 | Sync run controls with cooldown, cap and schedule | PARTIAL | `routers/connectors.py:87` manual sync endpoint | Manual only, no schedule, no cooldown, no run history, so a scheduled pipeline cannot lean on it | Could | M |
| 2-F2.20 | Fork a public dataset into the workspace | MISSING | No fork route or source | Cold start always begins at zero images | Should | M |
| 2-F2.21 | Merge projects into a third, union-backed project | MISSING | No merge route in `routers/projects.py` | Consolidating two campaigns means re-uploading or re-labelling | Could | M |
| 2-F2.22 | Grid with hover selection and a contextual bulk bar | HAVE | `features/project/Dataset.tsx:141-171` (selection bar, virtualised rows), `routers/images.py:301-352` (split, tag, status, assign, delete, clear) | Bulk bar has no "export selection" and no "assign to" control, though the API supports both | Should | S |
| 2-F2.23 | Batch board as the dataset pipeline | HAVE | `features/project/AnnotateBoard.tsx`; `routers/images.py:356-443` | Batch merge and batch delete are absent from the board | Should | M |
| 2-F2.24 | Image detail view with attributes and split inside the editor | PARTIAL | `features/editor/Editor.tsx:1031` tags; `features/editor/Panels.tsx` attributes/history | No dimensions/size/split block, no metadata editor, no "find similar" or "use as cover" in the image menu | Should | S |
| 2-F2.25 | Workspace-wide media browser with a sticky action bar | MISSING | No route above project scope (`routes/workspace.routes.tsx`) | Cross-project reuse ("this image is already in project B") is invisible | Should | L |
| 2-F2.26 | Export a single image, a version or a query result | PARTIAL | `routers/versions.py:103` version export; `features/project/Deploy.tsx` no image download | No single-image download, no export of the current filtered selection | Should | S |
| 2-F2.27 | One query language over class, tag, split, size, counts, date | PARTIAL | `routers/images.py:190-195` (16 parameters), `Dataset.tsx:31-41` (URL-synced chips) | No boolean/negation, no `class:x>=4`, no filename wildcard, no date range, no pasteable query string | Must | M |
| 2-F2.28 | Natural-language semantic search over unlabelled content | MISSING | `services/insights_embedding.py` exists but feeds suspect review, not search | Cannot ask "find every forklift I have not labelled"; the index exists and is unused here | Should | M |
| 2-F2.29 | "More like this" from an image already open | PARTIAL | `services/insights_embedding.py`; `routers/insights.py:83-93` | No per-image entry point in the editor or grid, so the ranking is unreachable from the moment of need | Should | S |
| 2-F2.30 | Cross-project search with cursor pagination | MISSING | `routers/images.py:190` is project-scoped | — | Could | M |
| 2-F2.31 | Tag lifecycle: upload, bulk apply, project-wide rename | PARTIAL | `routers/projects.py:351-380` list/rename; `images.py:318-321` add/remove | No tag delete, no merge of near-duplicate tags, no review-before-rename diff | Should | S |
| 2-F2.32 | Typed per-image metadata, bulk update, filterable | MISSING | No metadata field (`models/project.py:86-110`) | Exports lose any capture context the customer already has | Should | M |
| 2-F2.33 | Batch as a first-class, mergeable container | PARTIAL | `routers/projects.py:383-390` list; `images.py` filter by batch | No merge, no delete, no rename, no per-batch progress on the grid | Should | M |
| 2-F2.34 | Folders with inherited permissions | PARTIAL | `routers/workspaces.py:360-390` CRUD; `Home.tsx:120-131` | Folders are visual grouping only; no per-folder access, no nesting | Could | M |
| 2-F2.35 | Exact dedupe that restores a removed image with its labels | PARTIAL | `images.py:79-81` hash check excludes deleted rows; `:118-122` skip | Dedupe is per project and skipped files are only counted in aggregate, not itemised; a removed image returns blank | Should | S |
| 2-F2.36 | Near-duplicate discovery as a ranked search | PARTIAL | `services/versioning.py:59-95` pHash grouping guards splits; `services/health_scan.py` | No cluster list, no threshold control, no "review duplicates" queue — the pHash work is invisible to the user | Should | M |
| 2-F2.37 | Health report whose charts are filters | HAVE | `features/project/HealthCheck.tsx:95-105` bucket buttons, `:153-162` recommendations; `routers/insights.py:61-78` | Annotation heat map and object-count histogram are not in the report | Should | M |
| 2-F2.38 | Cached health report with explicit staleness and regenerate | HAVE | `services/health.py:111-119` (auto_scan guard, running/failed blocks a re-enqueue), `HealthCheck.tsx:198-211` re-run | `generated` timestamp is shown but not explained next to the numbers it qualifies | Could | S |
| 2-F2.39 | Split decided at ingest and stored on the image | HAVE | `images.py:148-149` (`split_of` folder allow-list, else 70/10/20); `Dataset.tsx:167` split badge | Unmatched folder names silently fall to the random split with no warning | Should | S |
| 2-F2.40 | Bulk split change from a selection | HAVE | `Dataset.tsx:144`; `images.py:316-317` | Large selections are applied synchronously in one request | — | — |
| 2-F2.41 | Percentage rebalance with three move policies | PARTIAL | `services/versioning.py:26-59,110-127` stratified split grouped by pHash | One policy only (re-stratify with leakage groups); no "move as few as possible", no per-batch mode, no background progress | Should | M |
| 2-F2.42 | Versions freeze their own split assignment | HAVE | `services/versioning.py:95-185` snapshots images, splits and variants per version | — | — | — |
| 2-F2.43 | Single-image removal | HAVE | `routers/images.py:583-600`; bulk `delete` at `:322-331` | Removal destroys bytes immediately, so there is no undo and no label revival | Should | S |
| 2-F2.44 | Bulk removal with a count-bearing confirm | HAVE | `Dataset.tsx:148` (`Delete N images?`), `images.py:322-331` | Shared-file cases are handled server-side but the dialog does not say what survives | — | — |
| 2-F2.45 | 30-day trash for containers with parent-before-child restore | PARTIAL | `routers/workspaces.py:399-425`; `Settings.tsx:1082-1100` | Projects only; no deleter, no days-left, no selection restore, no versions/trainings/workflows | Should | M |

**Area 2 count:** 11 HAVE · 23 PARTIAL · 11 MISSING (45).

---

## Area 3 — Annotate

Source: `03-annotate.md` (F3.1–F3.55, 55 features).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 3-F3.1 | Editor shell: tool rail, canvas, side panels, header | HAVE | `features/editor/Editor.tsx:815-1230` (tools, panels, header), `routes/project/index.tsx` editor route | Panels are a right drawer, not a persistent left list; no image menu (cover/remove/find similar) | — | — |
| 3-F3.2 | Pan, zoom and zoom lock | PARTIAL | `Editor.tsx:1255-1257` stepper, wheel zoom, pan state `:264-282` | No zoom lock, so inspecting small defects restarts on every image; no keyboard zoom set (`+ - 0 1`) | Should | S |
| 3-F3.3 | Image-to-image navigation with sticky settings | PARTIAL | `Editor.tsx:1267-1269` prev/next, `go()` | Assist and tool reset per image; no `esc` back to the board; display settings are not proven sticky | Should | S |
| 3-F3.4 | Display-only adjustment plus a global overlay hide | PARTIAL | `Editor.tsx:1233-1245` brightness/contrast popover; per-object hide in `ObjectList.tsx:100-104` | No gamma/auto-contrast, no global `h` toggle, so a dark image is inspected through its labels | Should | S |
| 3-F3.5 | Measurement guide in real units | MISSING | Absent from `Editor.tsx` | Defect size must be judged in pixels or after export | Could | S |
| 3-F3.6 | Drawer with annotation list, tags, image facts | PARTIAL | `features/editor/ObjectList.tsx` (list/virtualised), `Editor.tsx:1030-1035` tags | No dimensions, size, uploader or split in the drawer; split lives in the header, tags in a lower panel | Should | S |
| 3-F3.7 | Look-alike search from the open image | MISSING | No similarity action in the editor menu | The cheapest next label (a near-duplicate frame) is unreachable while labelling | Should | S |
| 3-F3.8 | Select, move, resize, reclass | PARTIAL | `Editor.tsx:388` transform path limited to `bbox` | Polygons, OBB and keypoints cannot be dragged/resized on canvas; geometry is edited numerically, which slows correction | Must | M |
| 3-F3.9 | Bounding box tool | HAVE | `Editor.tsx:605-608,1163-1167` draw, class picker with search/hotkeys | — | — | — |
| 3-F3.10 | Polygon tool with two closing gestures | PARTIAL | `Editor.tsx:615,1063` vertex clicks, double-click close | No vertex add/remove gesture on an existing polygon, no edge drag; correcting one corner means redrawing | Must | M |
| 3-F3.11 | Brush / pixel mask | MISSING | `lib/types.ts:64-70` has no mask shape | Fine structures (hair, foliage, transparency) cannot be labelled at all | Should | L |
| 3-F3.12 | One-click object isolation with click-to-grow/shrink | HAVE | `Editor.tsx:478-492` (inside-polygon click = negative, outside = positive), `routers/images.py:712-725` | No hover preview before commit, no engine choice, no convex/smooth/complex control | Should | S |
| 3-F3.13 | Keypoints with per-point visibility | HAVE | `Editor.tsx:152-208` joints panel with state cycling and nudging, `:587` skeleton requirement | States live in a panel, not a right-click menu on the point; no "edit visibility" checklist | — | — |
| 3-F3.14 | Skeleton definition screen | PARTIAL | `features/project/Classes.tsx:41-60` form with names + `0-1` edge text | No canvas placement, no per-edge colour, no symmetry; a 20-joint skeleton is typed blindly | Should | M |
| 3-F3.15 | Video timeline with per-class action segments | MISSING | `VideoTimeline.tsx` annotates extracted frames; no segment/action project type | Action recognition cannot be expressed; video work is frame-by-frame only | Could | L |
| 3-F3.16 | Classification-only, single and multi-label | PARTIAL | `Editor.tsx` class-chip path (`shapes: class`), `models/project.py` `multilabel` column | Multi-label is unreachable from the UI: the create form and settings never expose the flag | Must | S |
| 3-F3.17 | Multimodal prefix questions | MISSING | No prefix model or VQA field | VLM fine-tuning data cannot be authored | Could | L |
| 3-F3.18 | Distinguish "empty" from "not looked at" | MISSING | No null/negative flag on `Image` or the editor | Background-only images cannot become intentional negatives, so false positives stay | Must | S |
| 3-F3.19 | Undo, redo, repeat previous | PARTIAL | `Editor.tsx:330,786` undo/redo stack | No "repeat previous image's labels", the single biggest speed win on fixed cameras | Must | S |
| 3-F3.20 | Multi-select plus convert, merge and order menu | PARTIAL | `ObjectList.tsx:124-153` order actions for one selection | No shift/drag multi-select, no box↔polygon↔mask conversion, no mask union | Should | M |
| 3-F3.21 | Label assist that persists across images | PARTIAL | `Editor.tsx:845` assist with the first ready model; `routers/images.py:735-750` trained models only | Only workspace-trained models (no foundation/public), no class mapping step, assist does not follow to the next image | Must | M |
| 3-F3.22 | Foundation-model prompt on open with counted accept | MISSING | — | No zero-shot pre-labelling at the image level; a new class needs an existing model | Should | L |
| 3-F3.23 | Text prompt over the open image | MISSING | `suggest-class` (`images.py:662`) only names an existing shape | "Find the green umbrella" on this image is impossible | Should | M |
| 3-F3.24 | Example-box prompting with negative examples | MISSING | — | Trays of identical parts need box-by-box drawing | Could | L |
| 3-F3.25 | Proposal vs committed label is visible | HAVE | `panels` source chip with confidence (`Panels.tsx:17-33`), dashed AI outlines in `Editor.tsx` | — | — | — |
| 3-F3.26 | Auto-label entry, model catalogue, output shape | PARTIAL | `AutoLabelDialog.tsx:10-73` (trained / zoo / VLM / SAM 3.1), `training.py:384-413` | No workflow as a source; SAM text prompt is global, not per class; no mask-vs-polygon choice | Must | M |
| 3-F3.27 | Classes as prompts with per-class descriptions | PARTIAL | `AutoLabelDialog.tsx:51` one free-text prompt | One prompt for all classes; no per-class description row, no duplicate-description guard | Must | S |
| 3-F3.28 | Free preview on sample images | HAVE | `AutoLabelDialog.tsx:55,80-97` (3/4/5 samples, re-run) | Preview does not show per-label confidence | — | — |
| 3-F3.29 | Per-class confidence carried into the job | PARTIAL | `AutoLabelDialog.tsx:53` single 40% slider | One threshold per batch; a rare class and a common class cannot differ | Should | M |
| 3-F3.30 | Correct the preview in words | MISSING | — | A bad prompt can only be fixed by guessing a new one | Could | L |
| 3-F3.31 | Saved workflow as labeller with class mapping | MISSING | `AutoLabelDialog.tsx` offers no workflow option | Pipelines built in Workflows cannot label data, so the builder stops at inference | Should | M |
| 3-F3.32 | Cost estimate and existing-annotation policy | PARTIAL | `AutoLabelDialog.tsx:61` `onlyUnannotated` toggle; `training.py:237` counts credits in the job | No estimate before start, no keep/merge/replace with IoU rule; merge is "skip annotated" or overwrite | Must | M |
| 3-F3.33 | Background progress, then ordinary review | HAVE | `training.py:201-246` job + credit metering; result status set to review; `AnnotateBoard.tsx` job card | Job progress is visible in the tray but not as a board card with per-batch counts | Should | S |
| 3-F3.34 | Video auto-label with frame sampling | MISSING | — | — | Could | L |
| 3-F3.35 | Class picker with create-in-place | HAVE | `Editor.tsx:894-925` search, create row, hotkeys | — | — | — |
| 3-F3.36 | Class admin: rename, merge, delete, lock | PARTIAL | `features/project/Classes.tsx`; `routers/projects.py:283-334` merge endpoint | No review-before-rename diff, no class locking (so free-text prompts can mint classes) | Should | M |
| 3-F3.37 | Class colour, counts, hotkeys | HAVE | `Classes.tsx`, `Editor.tsx:894-925`, Okabe-Ito palette in `lib/theme.ts` | — | — | — |
| 3-F3.38 | Per-class annotation attributes | MISSING | `Panels.tsx:21` fixed keys `occluded/truncated/difficult/crowd` | No user-defined per-class fields (severity, colour, part id), and the fixed flags are not exported per class | Should | M |
| 3-F3.39 | Image tags | HAVE | `Editor.tsx:1030-1035`, `routers/images.py:318-321` | — | — | — |
| 3-F3.40 | Shared class sets and labels across projects | MISSING | `annotation_group` is a string only (`models/project.py:31`) | A second project re-types classes and re-labels the same images | Should | L |
| 3-F3.41 | Layering through the list and a context menu | HAVE | `ObjectList.tsx:124-153`, `annotationOrder.ts` | Order actions are buttons in a panel, not a right-click menu, but the outcome matches | — | — |
| 3-F3.42 | Hide a shape; delete a shape | HAVE | `ObjectList.tsx:100-114` hide/lock/delete per row | — | — | — |
| 3-F3.43 | Duplicate a shape, or carry the previous set forward | MISSING | No duplicate/repeat action in `Editor.tsx` | Six identical boxes are drawn six times | Must | S |
| 3-F3.44 | Four-column job board | HAVE | `AnnotateBoard.tsx:15-99`; `routers/images.py:356-443` | Batch merge/delete missing; cards are per batch+assignee, so one batch splits into several cards | Should | M |
| 3-F3.45 | Assign with instructions and notifications | PARTIAL | `AnnotateBoard.tsx:98` assign dialog; `board/move` with assignee | No written instructions field, no notification to the assignee, no reassignment from a job detail | Must | M |
| 3-F3.46 | Approve/reject per image at keyboard speed, with bulk | PARTIAL | `Editor.tsx:726-731,855-857` approve/reject; `:735` submit for review | No `a`/`r`/`u` shortcuts, no bulk approve/reject for a batch, reject carries no reason | Must | M |
| 3-F3.47 | Turn review off for solo work | MISSING | Review is not a project setting (`ProjectSettings.tsx:12-16`) | A one-person project is forced through a review step | Should | S |
| 3-F3.48 | Pinned, threaded comments on the image | PARTIAL | `Panels.tsx:123-160` thread per image, `routers/images.py:620-660` | Comments have no pixel anchor and no resolve state, so "this corner" needs a description | Should | M |
| 3-F3.49 | Per-image annotation history with revert | PARTIAL | `Panels.tsx:176-184` history derived from the local undo stack | History is lost on reload and cannot be reverted; no "who changed this" | Must | M |
| 3-F3.50 | Per-labeler and per-project label statistics | HAVE | `routers/labeling.py:22-27`; `services/labeling_ops.py`; `features/project/qa/Workforce.tsx` | First-pass approval rate needs confirmation against the metric list | Should | S |
| 3-F3.51 | Keyboard reference, and remapping | HAVE | `ShortcutModal.tsx:55-99` remap + clash detection, `shortcuts.ts` | Remapping is per browser, not per account | — | — |
| 3-F3.52 | Silent autosave with one explicit gate | PARTIAL | `Editor.tsx:298-299,370-375` dirty/saving, explicit save; approve is the gate | No navigation guard: leaving with unsaved edits silently drops them | Must | S |
| 3-F3.53 | Slow network, offline, decode failure | MISSING | No retry/offline state in the editor; image load failure is a toast | A dropped connection loses the current edits with no warning | Should | M |
| 3-F3.54 | Model unavailable shown as a disabled option with a reason | PARTIAL | `AutoLabelDialog.tsx:12-23` friendly messages; assist button hidden without a ready model | Assist picker hides the reason instead of grey-listing it, so the user cannot tell "not trained" from "not loaded" | Should | S |
| 3-F3.55 | Empty project, read-only image, two editors on one image | PARTIAL | Server enforces assignment (`images.py` `_assigned`); board empty state exists | Read-only is a 403 toast rather than a visible state; two people can still open one image with last-write-wins | Should | M |

**Area 3 count:** 15 HAVE · 23 PARTIAL · 17 MISSING (55).

---

## Area 4 — Versions, preprocessing, augmentation, export

Source: `04-versions-augmentation.md` (F4.1–F4.46, 46 features).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 4-F4.1 | Frozen point-in-time snapshot | HAVE | `services/versioning.py:95-185` writes a manifest per version; `routers/versions.py:51-72` | — | — | — |
| 4-F4.2 | Sequential number plus human name | HAVE | `versions.py:65-66` (`max+1`, optional name) | Unnamed versions show blank rather than a generated label | — | — |
| 4-F4.3 | Version index with counts, exports, trainings | PARTIAL | `features/project/Versions.tsx` list; `versions.py` export map | No per-row settings summary, so the recipe is invisible until the detail page | Should | S |
| 4-F4.4 | Async generation with progress | PARTIAL | `versions.py:68` enqueues a `version` job; job tray shows % | No per-phase progress (preprocess / augment / write), no completion notice tied to the card | Should | S |
| 4-F4.5 | Delete with consequences and a trash window | PARTIAL | `routers/versions.py:89-101` hard delete after file removal | No name-typed confirm, no trash, no statement that models trained on it stop serving | Should | S |
| 4-F4.6 | Copy a version's recipe onto newer data | MISSING | The wizard always starts at defaults (`Versions.tsx:30-36`) | Retraining after new labels means re-ticking every control and guessing the old values | Should | S |
| 4-F4.7 | Saved recipe locked downstream and shown at train time | PARTIAL | `Train.tsx` picks a version but renders no recipe card | The user cannot see what the model actually trained on from the train screen | Should | S |
| 4-F4.8 | Several trainings per version | HAVE | `routers/training.py:139-161` model list + leaderboard per project/version | — | — | — |
| 4-F4.9 | Five-step wizard, all steps reachable | HAVE | `Versions.tsx:50-56` step strip | — | — | — |
| 4-F4.10 | Step 1 states what enters the version | HAVE | `Versions.tsx:57` approved-image count + rule | No warning when the count is zero beyond the disabled button | Should | S |
| 4-F4.11 | Step 2 split percentages with inline validation | HAVE | `Versions.tsx:58-70` | No "reset to 70/20/10" action | — | — |
| 4-F4.12 | Rebalance with three strategies and class scoping | PARTIAL | `versioning.py:26-59,110-127` stratified, pHash-grouped | One strategy only; no "move as few as possible" vs "shuffle all", no class scope, no background task handle | Should | M |
| 4-F4.13 | Preprocessing picker with per-step preview | PARTIAL | `Versions.tsx:71-97` (resize, grayscale, contrast, filter-null, tiling) | No per-image preview of the transformed result, so label clipping is discovered after generation | Must | M |
| 4-F4.14 | Augmentation added one at a time, ordered | PARTIAL | `Versions.tsx:98-112` flat grid of 10 | No ordering, no preview, no tier labels; a range at 0 is silently off | Should | M |
| 4-F4.15 | Output multiplier with an estimate | PARTIAL | `Versions.tsx:110` 1–5 dropdown | No resulting-count estimate, no note that duplicates are dropped, no plan-driven cap | Should | S |
| 4-F4.16 | Confirm summary and a generated result page | PARTIAL | `Versions.tsx:113-123` summary step; list row after | No dedicated version page: exports, trainings and recipe live in different places | Should | M |
| 4-F4.17 | Auto-orient | HAVE | `services/imaging.py:26-28` EXIF transpose on every ingest | Not surfaced as a switch, which is fine while it is always on | — | — |
| 4-F4.18 | Resize with six modes | PARTIAL | `imaging.py:163-186` (`stretch`, `fit` black edges) | No centre-crop fill, reflect-edge or white-edge padding; an aspect-critical dataset is distorted or starved | Must | M |
| 4-F4.19 | Grayscale preprocessing | HAVE | `Versions.tsx:81`, `imaging.preprocess` | — | — | — |
| 4-F4.20 | Auto-adjust contrast with three algorithms | PARTIAL | `imaging.py:182-183` `autocontrast` only | No histogram equalisation or CLAHE, so low-contrast inspection images stay flat | Should | S |
| 4-F4.21 | Isolate objects into crops | MISSING | — | Detect-then-classify pipelines cannot be built from one dataset | Could | M |
| 4-F4.22 | Static crop by percentage | MISSING | — | Fixed-camera ROI cannot be cropped without an external script | Could | S |
| 4-F4.23 | Tiling: grid, fixed size, fixed aspect | PARTIAL | `Versions.tsx:84-95`; `services/tiling.py` fixed size + overlap | No grid or aspect modes; overlap is a percent slider without a tile-count preview | Should | M |
| 4-F4.24 | Modify classes: omit, rename, merge, regex | MISSING | No class step in the wizard | Version-scoped taxonomy surgery is impossible; it has to happen project-wide and destructively | Should | M |
| 4-F4.25 | Filter null images by percentage | PARTIAL | `Versions.tsx:83` boolean `filter_null` | All-or-nothing and there is no explicit null concept, so "no annotations yet" and "nothing here" are the same | Should | M |
| 4-F4.26 | Filter by tag with require/exclude/allow | MISSING | — | Training on a slice (new camera, new site) needs a separate project | Must | M |
| 4-F4.27 | Pipeline order and conflicts stated | PARTIAL | `Versions.tsx:91` states tiles are cut before resize | Incompatibilities (tiling + filter, classification + tiling) surface as a 400 at create time, not in the form | Should | S |
| 4-F4.28 | Augmentation scope and offline rationale | HAVE | `versioning.py:170-174` train split only, generated offline | Rationale is not shown in the UI | — | — |
| 4-F4.29 | Multiplier semantics and plan cap | PARTIAL | `Versions.tsx:110` 1–5 with hint | Cap is hard-coded rather than plan-derived; no duplicate-drop explanation | Could | S |
| 4-F4.30 | Fourteen basic augmentations with parameters | PARTIAL | `Versions.tsx:13-24` ten options | Missing crop, shear, hue, camera gain, motion blur, 90° direction; maxima are lower than RF's (5 px blur, 10% noise) | Must | M |
| 4-F4.31 | Bounding-box-level augmentation variants | MISSING | `imaging.augment` transforms whole images only | Colour/geometry changes teach background statistics the model should not learn | Should | M |
| 4-F4.32 | Cutout and mosaic | MISSING | — | Occlusion robustness needs an external training-time transform | Could | M |
| 4-F4.33 | Guidance on what and how much to augment | PARTIAL | `Versions.tsx:110` one hint line | No baseline-first guidance, no lighting/focus/occlusion map, so over-augmentation is the default mistake | Should | S |
| 4-F4.34 | Export dialog with format, ZIP and snippet | PARTIAL | `Versions.tsx` export + `versions.py:41-43,103`; signed download | No inline curl/SDK snippet in the export dialog and no "version still generating" state message | Should | S |
| 4-F4.35 | Format catalogue by project type | PARTIAL | `services/exporters.py:21-27,276-280` nine formats filtered by task | Missing clip, darknet, tfrecord, retinanet, yolov5-obb, semantic PNG masks and multi-label multiclass | Must | M |
| 4-F4.36 | Async, cached, repeatable export | HAVE | `exporters.cached_export`, export job dedupe in `versions.py` | — | — | — |
| 4-F4.37 | Round-trip losses documented | PARTIAL | Re-encode on generation; class sanitiser in `ensure_class` | No warning that class names are normalised on import and export | Could | S |
| 4-F4.38 | Export straight to a customer bucket | MISSING | — | Deliverable data must be moved by hand | Could | M |
| 4-F4.39 | Dataset health overview | PARTIAL | `features/project/HealthCheck.tsx`; `services/health.py:97-119` | No null-annotation count, no dimension chart, no heat map | Should | M |
| 4-F4.40 | Class balance per split | HAVE | `services/insights.py:207` distribution; `features/project/insights/DataQuality.tsx` | — | — | — |
| 4-F4.41 | Dimension and aspect-ratio insights | HAVE | `routers/insights.py:61-70` image-stats | — | — | — |
| 4-F4.42 | Annotation heat map with drag-to-filter | MISSING | — | Spatial bias ("everything is centred") cannot be seen | Should | M |
| 4-F4.43 | Objects-per-image histogram with click-through | PARTIAL | `insights.py` geometry stats; `Dataset.tsx` min/max annotation filters | No histogram UI; the filter exists but nothing points at it | Should | S |
| 4-F4.44 | Report caching with an explicit staleness field | HAVE | `services/insights.py:91-105` cache signature; `health.py:111-119` | Timestamp is not shown next to the numbers | Could | S |
| 4-F4.45 | Per-version analytics and version-to-version comparison | HAVE | `routers/insights.py:94-102` version-diff; version-scoped summary/distribution | Beyond Roboflow's documented surface; keep | — | — |
| 4-F4.46 | Pre-train warning about a weak version | PARTIAL | `routers/training.py:229-289` refuses a version that is not ready; `Train.tsx` estimate | No warning for a class missing from valid/test or an empty split | Should | S |

**Area 4 count:** 14 HAVE · 23 PARTIAL · 9 MISSING (46).

---

## Area 5 — Train and models

Source: `05-train-models.md` (F5.1–F5.54, 54 features; F5.40–F5.54 are edge cases).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 5-F5.1 | Project model table with metric, version, licence | HAVE | `features/project/Models.tsx` table + cards; `routers/training.py:139-186` | No filter by task/version, no sort by metric; rows are cards rather than a scannable table | Should | S |
| 5-F5.2 | Many models per version | HAVE | `training.py:139-161`; `Models.tsx` list per project | The version page does not list its trainings; you find them in Models | Should | S |
| 5-F5.3 | Workspace registry with a starred public tab | PARTIAL | `features/workspace/WorkspacePages.tsx:16-18` workspace model list | No starred/public models, no public model page | Could | M |
| 5-F5.4 | Row quick actions: deploy, copy id, evaluation, weights | PARTIAL | `Models.tsx:206-244` (deploy, insights, weights link, stop) | No copy-id affordance and no workflow-template chooser on deploy | Should | S |
| 5-F5.5 | Architecture search engine (NAS) | MISSING | `routers/training.py:189-210` lists fixed families only | No search option, so architecture choice is expert-only | Could | L |
| 5-F5.6 | Train on the live dataset or a frozen version | PARTIAL | `Train.tsx:23` version is required | No "current dataset" path, so a first run needs a version first; no recipe reuse | Should | M |
| 5-F5.7 | Architecture and size picker pre-filtered by task | PARTIAL | `Train.tsx:76-87`; `adapters/catalog.py:33-40` (YOLO26/11/v8 variants) | No RF-DETR family, no SAM 3 fine-tune, no per-size default resolution, no request-access path | Must | M |
| 5-F5.8 | Starting weights: previous, public, public-dataset, random, ImageNet | PARTIAL | `Train.tsx:115-120` resume-from model; COCO weights implicit in the variant | No explicit checkpoint field, no public-dataset or random-init option | Should | S |
| 5-F5.9 | Speed preset plus a full recipe editor | PARTIAL | `Train.tsx:92-114` fast/advanced (epochs, size, batch) | No training-time preprocessing or online augmentation, no hyperparameter set beyond three fields | Should | M |
| 5-F5.10 | Credit cap with the minimum printed | PARTIAL | `Train.tsx:114` max-minutes cap; `training.py:219` | Cap is time, not money, and no floor is printed; a stop does not fund a continuation | Should | S |
| 5-F5.11 | Cost and duration estimate with a long-run confirm | PARTIAL | `Train.tsx:34,126` minutes estimate | Credits are not shown, and an estimate over a day starts without a confirmation step | Should | S |
| 5-F5.12 | Submit with a queued acknowledgement where results will land | HAVE | `Train.tsx:48-70`; `Models.tsx:20-55` stage stepper | The user stays on the form after submit instead of landing on the run | Should | S |
| 5-F5.13 | Instant few-shot model | MISSING | — | A first usable model needs a full training run and a worker | Should | L |
| 5-F5.14 | Search backbone choice by deployment target | MISSING | — | Follows from F5.5 | Could | M |
| 5-F5.15 | Lifecycle states that separate stopped from failed | PARTIAL | `Models.tsx:21-55` stages; job status set | A stop is shown as a cancelled job, not as "stopped early, weights kept" | Should | S |
| 5-F5.16 | Live training graphs and loss curves | HAVE | `Models.tsx:118-134` (mAP50, mAP50-95, precision, recall, loss) | No per-class curves, no search band (no search) | — | — |
| 5-F5.17 | Stop early vs cancel, consequences stated | PARTIAL | `Models.tsx:244` "Stop" after this epoch | No cancel-and-discard action, no refund statement, no consequences table | Should | S |
| 5-F5.18 | Continue training from the last checkpoint | HAVE | `Train.tsx:35-43,115-120` resume-from same-variant model | No checkpoint expiry, no continuation of the same run id | Should | S |
| 5-F5.19 | Spend and logs during a run | PARTIAL | `Client job` progress + `max_minutes`; no credit meter on the run | No live spend, no log pane, so a stuck run is opaque | Should | S |
| 5-F5.20 | Evaluation runs automatically after training | HAVE | `handlers/training.py:160-173` evaluate stage, model kept on eval failure | No "optimizing for inference" step and eval failure is a note, not a retry entry | Should | S |
| 5-F5.21 | Threshold explorer that becomes the served default | PARTIAL | `features/evaluation/EvalPanel.tsx` slider re-derives the matrix; `services/evaluate.py:85` F1-optimal threshold stored | Not proven that the tuned threshold becomes the API default; per-class thresholds absent | Must | M |
| 5-F5.22 | Per-class performance with counts | PARTIAL | `evaluate.py:80-84` per-class AP/AP50; `EvalPanel.tsx` bars | No correct / misclassified / missed / false-positive counts per class | Should | S |
| 5-F5.23 | Confusion matrix with cell drill-down and GT/prediction flip | HAVE | `EvalPanel.tsx:42-165` (threshold re-derive, cell gallery, GT/pred boxes) | — | — | — |
| 5-F5.24 | Improvement recommendations and assistant handoff | PARTIAL | `services/insights_eval.py` slices, calibration, worst images | No written recommendations and no "improve my model" action | Should | M |
| 5-F5.25 | Visual-similarity failure clusters | PARTIAL | `features/project/insights/Embeddings.tsx` + `services/insights_embedding.py` | Clusters are not coloured by per-image score for the evaluated model | Could | M |
| 5-F5.26 | Median latency as a first-class number | MISSING | Training metrics carry no latency | "Fast enough" cannot be compared with "accurate enough" in-product | Should | S |
| 5-F5.27 | Side-by-side comparison on one version (accuracy vs latency) | PARTIAL | `features/insights/CompareTab.tsx:27-80` (PR, per-class AP, Pareto scatter) | Frontier is accuracy-only; no latency axis, no "evaluation needs an update" panel | Should | M |
| 5-F5.28 | Task-appropriate metrics (OKS, mIoU, boundary) | PARTIAL | `evaluate.py:23` COCO 12 keys for detect/segment; classification top-1 | No OKS for keypoints, no mIoU/pixel metrics for semantic masks, no boundary AP | Must | M |
| 5-F5.29 | Evaluation for uploaded weights | MISSING | — | Follows from F5.31 | Should | S |
| 5-F5.30 | Application-level regression evals | MISSING | — | A workflow or model change has no pass/fail gate | Could | L |
| 5-F5.31 | Upload custom weights, versioned or workspace-wide | MISSING | No upload route in `routers/training.py` | Models trained elsewhere cannot be hosted, evaluated or compared | Must | M |
| 5-F5.32 | Train elsewhere and import back | MISSING | Export exists (`training.py:332`), import does not | A customer's own pipeline is a dead end | Could | M |
| 5-F5.33 | Stable, parseable model identity | PARTIAL | `TrainedModel.id` + name; `Models.tsx` shows name | No composite id, no copy affordance, so model references in chat are ambiguous | Should | S |
| 5-F5.34 | Legacy per-version model alias | MISSING | No alias row; `routers/deployments.py:30` aliases exist per project instead | Old-style references cannot resolve, but the deployment alias covers the need | Could | S |
| 5-F5.35 | Explicit production pointer (Roboflow's own gap) | HAVE | `routers/deployments.py:13-45` alias → model, rollback | Better than parity; surface is the Deploy page | — | — |
| 5-F5.36 | Starring search candidates | MISSING | — | Follows from F5.5 | Could | S |
| 5-F5.37 | Delete a run with the serving consequence stated | PARTIAL | `training.py:300-311` hard delete | No trash, no name-typed confirm, no statement about what stops serving | Should | S |
| 5-F5.38 | Licence shown per model and per deploy target | HAVE | `Models.tsx:233-235`; `adapters/catalog.py:12`, licence per family | Deploy page does not repeat the licence next to the endpoint | Should | S |
| 5-F5.39 | Train permission split from read | HAVE | `routes/project/models.routes.tsx` `PermGate`; `rbac.py:31-48` | — | — | — |
| 5-F5.40 | Too few images | PARTIAL | `training.py:231-243` validates version readiness only | A 5-image version starts a doomed run with no warning | Should | S |
| 5-F5.41 | Class imbalance | PARTIAL | `insights_eval.py` slices; `HealthCheck.tsx` class balance | Nothing warns at train time; the evidence exists two pages away | Should | S |
| 5-F5.42 | Small validation or test split | PARTIAL | Version stats carry split counts | No warning before training | Should | S |
| 5-F5.43 | Version not ready or invalid | HAVE | `training.py:237-238` 400 "pick a generated version" | Message names the fix but not which versions are valid | — | — |
| 5-F5.44 | Unsupported task + architecture | HAVE | `training.py:189-210,244-251`; `Train.tsx` family availability + reason | — | — | — |
| 5-F5.45 | Licence restriction on self-hosting | PARTIAL | Licence badge and registry field; no enforcement or advice at export | AGPL obligations are invisible to someone downloading weights | Should | S |
| 5-F5.46 | Time or credit cap reached mid-run | PARTIAL | `max_minutes` honoured by the handler; weights kept | No visible "stopped at cap" state or remainder-funded continuation | Should | S |
| 5-F5.47 | Workspace out of credits | HAVE | `metering.check`/`charge` in train and autolabel paths (`training.py:64,237`) | The 402 message names the plan but not the remedy | Should | S |
| 5-F5.48 | Out of memory or GPU fault | PARTIAL | `safe_error` surfaces the exception; job fails | Raw error text, no "reduce batch or image size" guidance | Should | S |
| 5-F5.49 | Concurrent runs | PARTIAL | No explicit per-project guard in `training.py:231-289` | Two runs can be queued on one GPU and each slows the other | Should | S |
| 5-F5.50 | Ambiguous training reference | HAVE | Every run is addressable by `TrainedModel.id` | — | — | — |
| 5-F5.51 | Long or expensive run needs a confirmation | MISSING | Estimate is informational only (`Train.tsx:126`) | A 12-hour run starts on one click | Should | S |
| 5-F5.52 | Anomaly-project data rules | HAVE | `routers/anomaly.py:82-206`; `features/project/Anomaly.tsx` good-only station | No threshold calibration from a labelled anomaly set | Should | M |
| 5-F5.53 | Evaluation unavailable | PARTIAL | Eval failure leaves `eval_error` on the model and keeps it ready (`handlers/training.py:170-173`) | The model page does not explain that the score is missing and why | Should | S |
| 5-F5.54 | Evaluation stalled | PARTIAL | Job reaper (`services/remote_reaper.py`) fails stranded runs | No separate eval watchdog, so a stuck eval blocks the metric silently | Could | S |

**Area 5 count:** 15 HAVE · 28 PARTIAL · 11 MISSING (54).

---

## Area 6 — Deploy, inference, workflows

Source: `06-deploy-inference.md` (F6.1–F6.46, 46 features; the block catalogue is summarised in F6.33).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 6-F6.1 | One chooser that separates real-time from bulk | MISSING | `features/project/Deploy.tsx` documents one hosted endpoint | No comparison of dedicated, batch, streaming or edge, so a buyer cannot see the delivery options exist | Must | M |
| 6-F6.2 | Per-request endpoint that hides its own cold start | PARTIAL | `routers/training.py:563` predict; `routers/playground.py:93` preflight state | No cold-start or processing-time headers and no documented warmup, so latency surprises arrive in production | Should | S |
| 6-F6.3 | Dedicated private box with dev/prod types and pause | MISSING | — | Customers with data-residency needs have no option | Could | L |
| 6-F6.4 | Batch job over stored images or video | PARTIAL | Autolabel over a dataset (`training.py:432`), workflow batch absent | No generic "run this pipeline over these 4,000 images", no result set artefact | Should | L |
| 6-F6.5 | Self-hosted inference server at no credit cost | PARTIAL | `apps/inference/` (CPU/GPU Dockerfiles, `/predict`, 20 MB cap, `README.md:58-99`) | No route, link or docs page inside the product; the Deploy page still only shows the hosted API | Must | S |
| 6-F6.6 | Cost model printed next to the choice | PARTIAL | Plans and credits in `config.PLANS`, usage page; `charge` per autolabel image | No per-model credit table and no volume bands, so a buyer cannot forecast spend | Should | M |
| 6-F6.7 | Go-live checklist that names what to retry | MISSING | — | Integration failures are debugged from scratch by each customer | Could | S |
| 6-F6.8 | Runtime picker that rewrites the snippets | MISSING | `Deploy.tsx:36-40` snippets are hard-coded to the hosted endpoint | Self-hosted users copy a wrong `api_url` and get a 404 | Should | S |
| 6-F6.9 | Confidence slider with a live preview on the deploy surface | HAVE | `Deploy.tsx:54` slider re-runs predict | — | — | — |
| 6-F6.10 | Request shape follows the workflow's declared inputs | PARTIAL | `routers/workflows.py:96` run; `WorkflowBlocks.tsx` fixed block set | No declared input contract, no per-workflow endpoint, so workflows are not callable from outside | Must | M |
| 6-F6.11 | Immutable model identity with a production pointer | HAVE | `routers/deployments.py:13-45` alias get/put/rollback; model ids | Better than Roboflow: a named production alias exists | — | — |
| 6-F6.12 | Error codes and credit rules written for the caller | PARTIAL | FastAPI codes + `402` metering; not documented in-product | "Did this failure bill me" is unanswerable without reading the code | Should | S |
| 6-F6.13 | Scoped, rotatable keys with a publishable type | PARTIAL | `routers/workspaces.py:238-282` scopes + publishable + revoke | No roll/disable, no per-key usage surface, no rotation reminder | Should | S |
| 6-F6.14 | Monitoring dashboard over production requests | PARTIAL | `features/streams/StreamAnalytics.tsx`, `routers/ops.py:20` drift | Hosted API calls are not recorded per request; only stream events and drift are visible | Should | M |
| 6-F6.15 | Typed production event store | PARTIAL | `routers/streams.py:486-536` events + rules | Events carry no event type or metadata vocabulary, so QA/counting/safety cannot be separated | Should | M |
| 6-F6.16 | Human verdicts on production predictions | PARTIAL | `routers/projects.py:433-450` suspect-label feedback | Feedback exists for suspect labels, not for stream or API events; no correct/incorrect/inconclusive taxonomy | Should | M |
| 6-F6.17 | Review session that routes bad events into training | PARTIAL | `routers/streams.py:536` event → dataset | One-way and one at a time; no session, no single-reviewer lock, no reject/snooze | Should | M |
| 6-F6.18 | Watchdog and digest alerts without visiting a dashboard | PARTIAL | `routers/alerts.py` channels, deliveries, test; `services/alerts.py` | Alerts fire on rules, not on silence; no digest and no camera-offline email | Should | M |
| 6-F6.19 | Active learning as a small rules form | PARTIAL | `ProjectSettings.tsx:69-80` threshold, sample %, include-empty; `routers/ops.py:85-100` | No caps per minute/hour/day, no batch review cadence, no reviewer assignment from this screen | Should | M |
| 6-F6.20 | Retention stated per surface and per plan | PARTIAL | `routers/privacy.py` retention settings + run; DPA page | No `lookbackDays` in responses; trash and event retention are not one readable policy | Should | S |
| 6-F6.21 | Canvas builder with ports, auto-wire and layout modes | PARTIAL | `Workflows.tsx` + `WorkflowBlocks.tsx` linear block list, max 12 blocks | No canvas, no ports, no branching; a pipeline that is not a straight line cannot be expressed | Must | L |
| 6-F6.22 | Block config panel with required ports first | HAVE | `WorkflowBlocks.tsx:75-110` per-type fields | Required fields are not visually separated from optional ones | Should | S |
| 6-F6.23 | Run panel for still, video and live camera | PARTIAL | `Workflows.tsx:14-37` run result panel (detections, texts, events, ms) | Image-only input, no video window, no live preview, so camera pipelines are untestable | Should | M |
| 6-F6.24 | Per-block caching with an explicit uncache | MISSING | — | Every iteration re-runs the expensive model | Could | M |
| 6-F6.25 | Sinks switch that protects test runs | MISSING | — | A test run can write annotations into a real dataset | Should | S |
| 6-F6.26 | Outputs node that is editable and reorderable | PARTIAL | Sink block kinds `response`/`annotations` (`services/workflows.py:20`) | No ordering or selection of output fields | Could | S |
| 6-F6.27 | Save is manual, publish is gated and separate | PARTIAL | `routers/workflows.py:54-95` save + version rows | No draft/live split and no publish gate, so a half-built pipeline is as live as a finished one | Should | M |
| 6-F6.28 | Version history with a Live marker and non-destructive restore | PARTIAL | `WorkflowVersions.tsx`, `routers/workflows.py:80-92` | Restore works, but there is no Live badge, no rename, no "what is production running" | Should | S |
| 6-F6.29 | Disable a node instead of deleting it | MISSING | — | Bisecting a broken pipeline means deleting blocks and losing config | Should | S |
| 6-F6.30 | Nested workflow as a component | MISSING | — | Team templates drift by copy-paste | Could | M |
| 6-F6.31 | Share, fork and folder-scope a workflow | MISSING | — | A pipeline cannot be handed to another project | Could | M |
| 6-F6.32 | Batch run over a workspace image selection | PARTIAL | Autolabel is the only batch path; no selection-scoped run | "Run this on the images I just filtered" is unavailable | Should | M |
| 6-F6.33 | Deploy a workflow to an endpoint or a device | PARTIAL | `routers/workflows.py:96` run only | No deploy chooser, no workflow endpoint URL, no device path | Must | M |
| 6-F6.34 | First-run workflow path: empty canvas → block → test → deploy | PARTIAL | `Workflows.tsx` add/save/run | Starts from a blank list with no template and no sample input, so the first result is far away | Should | S |
| 6-F6.35 | Detect → count → draw examples in the docs | HAVE | `WorkflowBlocks.tsx` model/filter/crop/ocr/rule/sink | Visualisation blocks are absent, so "draw" is not reproducible | Should | M |
| 6-F6.36 | Two-stage detect → crop → classify → write back | PARTIAL | `model` + `crop` + `ocr` blocks; classification model via ref | No detections rewrite step, so per-object classes cannot be attached | Should | M |
| 6-F6.37 | In-process library plus HTTP client | PARTIAL | `packages/sdk/labeldesk/client.py` HTTP client; `apps/inference` server | No in-process model loader, no workflow client method | Should | M |
| 6-F6.38 | Video pipeline object for webcam, file and RTSP | MISSING | — | A customer's own video loop must be written from scratch | Could | M |
| 6-F6.39 | Two CLIs with a stated boundary | PARTIAL | `packages/sdk/labeldesk/cli.py:73-108` one CLI (platform work only) | No inference/benchmark commands, no `--no-wait` | Should | M |
| 6-F6.40 | Key resolution for notebook, container and CI | PARTIAL | CLI `--api-key` / `LABELDESK_API_KEY`; `client.py` | No interactive login cache and no documented precedence | Could | S |
| 6-F6.41 | Source types with different lifetimes in one table | PARTIAL | `Streams.tsx:55-93` RTSP URL + uploaded video; `routers/streams.py:397` | No ONVIF discovery, no webcam/phone QR, no lifetime guidance | Should | M |
| 6-F6.42 | Capture settings only where they can apply | MISSING | Only `sample_fps` (`Streams.tsx:88`) | Resolution/codec advice is absent, so users lower FPS with no effect | Could | S |
| 6-F6.43 | Zones, lines and counters drawn on the frame | HAVE | `features/streams/ZoneEditor.tsx`; `streams/rules.py` count/zone/line | — | — | — |
| 6-F6.44 | Live results, stream state and recovery | PARTIAL | `routers/streams.py:366-397` start/stop, `:449-459` frame/MJPEG, `streamaudit` | No recovery backoff, no "needs attention" taxonomy, no offline email | Should | M |
| 6-F6.45 | Install paths per platform with a one-command default | PARTIAL | `apps/inference/README.md:58-99` Docker CPU/GPU, `deploy/docker-compose.yml` profile | No CLI installer, no Jetson image, and nothing in the product points at it | Should | S |
| 6-F6.46 | Edge fleet management with approval and windows | MISSING | `routers/remote.py` only claims GPU training jobs | No device inventory, config push, or health per device | Could | L |

**Area 6 count:** 5 HAVE · 29 PARTIAL · 12 MISSING (46).

---

## Area 7 — Workspace admin, billing, keys, audit

Source: `07-workspace-admin.md` (F7.1–F7.61, 61 features).

| ID | Roboflow feature | Status | Evidence | UX gap | Pri | Size |
| --- | --- | --- | --- | --- | --- | --- |
| 7-F7.1 | Member roster with seat accounting | PARTIAL | `features/settings/Settings.tsx:738-805` roster + pending; `routers/workspaces.py:137-155` | No seats-used/allowed header, no avatar, no per-row menu (role select + Remove only) | Should | S |
| 7-F7.2 | Bulk email invite with a per-batch role | PARTIAL | `Settings.tsx:749-766` one address at a time; `workspaces.py:156-180` accepts one email | Inviting eight people means eight submissions; no partial-failure report | Should | S |
| 7-F7.3 | Pending invitations with resend and cancel | PARTIAL | `Settings.tsx:798-803` pending rows + Revoke; `workspaces.py:140-148` | No resend, no sent date, no expiry state, so a stale invite is invisible | Should | S |
| 7-F7.4 | Role-locked reusable invite link | MISSING | Only per-invite tokens (`workspaces.py:147`) | Contractors cannot be onboarded by link; the token link is safer but per-person | Could | S |
| 7-F7.5 | Same-domain join request with approval | MISSING | No domain verification or request model | Every join needs an admin to type an address | Could | M |
| 7-F7.6 | Change a member's role, self-change blocked | PARTIAL | `Settings.tsx:781-784` role select; `routers/rbac.py:205-231` | No guard against an admin demoting themselves into lockout | Should | S |
| 7-F7.7 | Remove a member or leave, last-admin guard | HAVE | `Settings.tsx:795`; `workspaces.py:195-235` (owner cannot be removed/renamed) | — | — | — |
| 7-F7.8 | Workspace default role for new joiners | MISSING | Role is chosen per invite | No SSO/join default, which is the safety net once custom roles exist | Should | S |
| 7-F7.9 | Built-in role matrix as a readable table | PARTIAL | `governance/Roles.tsx:39-60` permission grid for custom roles; `ROLE_LABEL` map | The three built-in roles are not shown as a matrix, so "what does a labeler get" needs reverse-engineering | Should | S |
| 7-F7.10 | Custom roles from grouped permissions, copy-from, tooltips | PARTIAL | `Roles.tsx:45-81` workspace/project permission checkboxes, create/edit/delete | No copy-from-existing, no per-permission tooltips, no folder access, and the dialog is a plain modal | Should | M |
| 7-F7.11 | Folder-scoped access and named auth groups | MISSING | Folders have no permission model (`workspaces.py:360-390`) | An outsourced team cannot be limited to one folder | Could | L |
| 7-F7.12 | Billing home for plan, packs and add-ons | MISSING | `Settings.tsx:973-975` "contact your LabelDesk operator" | Plans cannot be changed in-product at all | Must | L |
| 7-F7.13 | Credit burn-down with cumulative/daily toggle | PARTIAL | `Settings.tsx:885-1000` meter cards + daily activity chart | No cumulative-vs-daily toggle, no dollars view, no cycle-range picker | Should | M |
| 7-F7.14 | Attribution by key, folder and member | MISSING | `metering.py` records project/image/kind but no UI filter | "Who or what burned the credits" is unanswerable | Should | M |
| 7-F7.15 | Cycle breakdown plus limits meters | HAVE | `Settings.tsx:973-1000` plan label, credits, gpu/stream/ai/storage meters with quotas | — | — | — |
| 7-F7.16 | Forward projection with saved scenarios | MISSING | — | Forecasting needs a spreadsheet | Could | M |
| 7-F7.17 | Consumption audit log distinct from security audit | PARTIAL | `routers/audit.py` action log; `metering.daily` | Usage rows are aggregated, not a per-charge ledger with minute and feature | Should | M |
| 7-F7.18 | Training cost estimator before spending | PARTIAL | `Train.tsx:34,126` minutes only | No credits, so cost planning is manual arithmetic | Should | S |
| 7-F7.19 | Prepaid credit purchase | MISSING | No purchase path | — | Could | M |
| 7-F7.20 | Flex billing with an explicit spend cap | MISSING | Quota is enforced with 402 only | A team cannot pre-authorise an overage, so work stops mid-project | Could | M |
| 7-F7.21 | Three-stage "you are spending" notices | PARTIAL | `metering.check` raises 402 with plan label (`metering.py:100-106`) | Nothing warns at 80%; the first signal is a failed action | Should | S |
| 7-F7.22 | Cancel a plan with an explicit end state | MISSING | — | — | Could | S |
| 7-F7.23 | Billing portal: card, details, invoices | MISSING | — | Finance has no self-service artefact | Should | M |
| 7-F7.24 | Teams add-on with seat rules | MISSING | Roles are free of charge and not plan-gated (`rbac.py`) | Plan tiers have nothing to sell, so revenue cannot scale with seats | Must | M |
| 7-F7.25 | Key table whose badges carry the state | PARTIAL | `Settings.tsx:823` table; `workspaces.py:238-250` prefix/scopes/publishable/last_used | No masked-with-reveal value, no protect/disable/roll badges, no filter by state | Should | M |
| 7-F7.26 | Create a key with a one-time reveal | HAVE | `workspaces.py:252-271` returns the value once; `Settings.tsx` copy dialog | Naming advice at the moment of typing is missing | — | — |
| 7-F7.27 | Rename, protect, disable, revoke as four strengths | PARTIAL | `workspaces.py:273-284` revoke only | A leaked key has exactly one remedy: destroy it and redeploy every consumer | Should | S |
| 7-F7.28 | Atomic roll with a dependency warning | MISSING | — | Rotation is a manual multi-step outage | Should | M |
| 7-F7.29 | Per-key permission scoping with silent 404s | PARTIAL | `workspaces.py:259-269` scope subset validation; `devapi.py:31-131` `_scopes` | Missing scope returns 403 naming the scope, which discloses the route exists | Should | S |
| 7-F7.30 | Folder-scoped keys | MISSING | Keys are workspace-wide | One site's leak affects everything | Could | M |
| 7-F7.31 | Key metadata and named owners | MISSING | Keys carry only name/scopes | Ownership of a credential is folklore | Could | S |
| 7-F7.32 | Rotation due dates and reminders | MISSING | — | — | Could | S |
| 7-F7.33 | Default key and "in use" fallback made visible | MISSING | Server always resolves the presented key; no default concept | "Which key is the app spending under" is unanswerable | Could | M |
| 7-F7.34 | Public publishable key for browser inference | HAVE | `workspaces.py:252-258` `publishable` forces `["infer"]` | — | — | — |
| 7-F7.35 | Self-serve SSO with DNS proof | MISSING | `oidc.py` validates bearer tokens from an env-configured issuer; no login flow, no domain proof | Enterprise buyers cannot bring their IdP without an operator | Should | L |
| 7-F7.36 | OAuth sign-in for third-party apps | MISSING | — | Integrations must use long-lived workspace keys | Could | L |
| 7-F7.37 | CLI/SDK auth handshake with a default workspace | PARTIAL | `cli.py:68-70` `--api-key`/`--base-url`; no login or default workspace | Every command repeats the key and workspace | Could | S |
| 7-F7.38 | Audit log table with four filters and row detail | PARTIAL | `features/governance/AuditLog.tsx`; `routers/audit.py:30-90` (action/user/since/until, CSV/JSON export) | No actor-type or resource filter, no before/after diff, no infinite scroll | Should | M |
| 7-F7.39 | Audit coverage across admin, data and agent changes | PARTIAL | `audit(db, …)` calls across routers (project, image, key, member, version, training) | Data exports, label approvals and workflow publishes are not a stated, tested category list | Should | M |
| 7-F7.40 | SIEM streaming with a real test event | MISSING | File export only | Enterprise security review fails without it | Could | M |
| 7-F7.41 | Directory-group sync and workspace gating | MISSING | — | — | Could | L |
| 7-F7.42 | Custom branding of login and navigation | MISSING | — | — | Could | M |
| 7-F7.43 | 30-day trash with permanent delete kept in the UI | PARTIAL | `routers/workspaces.py:399-425`; `Settings.tsx:1082-1100` | Projects only, no deleter or days-left, and permanent delete is an API route too | Should | M |
| 7-F7.44 | Private-data licensing opt-out | MISSING | `privacy.py` covers retention and face blur, not licensing | A procurement blocker for PII-sensitive buyers | Should | S |
| 7-F7.45 | Contractual and regional controls | PARTIAL | `routers/privacy.py:270` DPA route + `governance/Dpa.tsx` | No region choice, SLA, HIPAA/BAA position or trust page | Should | M |
| 7-F7.46 | Named credential store for external providers | PARTIAL | `services/connectors.py` credentials live inside each connector | Rotation means editing every connector | Could | M |
| 7-F7.47 | Bucket mirror datasource with a two-tab setup | PARTIAL | `routers/connectors.py` API only; no settings screen | A no-code user cannot connect a bucket at all | Should | M |
| 7-F7.48 | Mirror trigger guards against cost surprises | MISSING | `routers/connectors.py:87` no cooldown or cap | — | Could | S |
| 7-F7.49 | Webhook push from a processing pipeline | PARTIAL | `routers/webhooks.py` deliveries + test; workflow sinks are `response`/`annotations` only | Alerts can fire, but a pipeline cannot post its result anywhere | Should | M |
| 7-F7.50 | Third-party AI billed through the workspace | PARTIAL | `adapters/vlm_ad.py` via `LD_VLM_URL`; no vendor keys or per-token billing | Every VLM vendor needs an operator-run endpoint | Could | M |
| 7-F7.51 | Notification sinks with per-message credit cost | PARTIAL | `routers/alerts.py` channels + deliveries | Channel types are webhook/email only; no Slack/SMS and no cost shown | Should | M |
| 7-F7.52 | Handoff to external training platforms | MISSING | Export only | — | Could | M |
| 7-F7.53 | Publish a project with an explicit licence dialog | PARTIAL | `Home.tsx:65-66`; `ProjectSettings.tsx:64-65` | Set as a field in two places, no pre-publish warning about PII/copyright | Should | S |
| 7-F7.54 | Public project page with sharing statistics and badges | MISSING | No public route | Publishing changes an icon and nothing else | Should | M |
| 7-F7.55 | Fork a public dataset into the workspace | MISSING | No clone route | — | Should | M |
| 7-F7.56 | Star and reuse a public model as a checkpoint | MISSING | — | — | Could | M |
| 7-F7.57 | Create a workspace from a first-run screen | HAVE | `Settings.tsx:1102-1118` FirstRun; `routers/auth.py:47,482` | No plan choice or slug preview | — | — |
| 7-F7.58 | Rename a workspace with a URL-breakage warning | PARTIAL | `routers/workspaces.py:50-71` PATCH name/slug | No warning that endpoints and API references break | Should | S |
| 7-F7.59 | Delete a workspace or the whole account | MISSING | No delete route for workspace or account | A customer cannot leave, and PDPA erasure has no self-serve path | Should | M |
| 7-F7.60 | Workspace policy switches that gate member actions | MISSING | — | An admin cannot forbid public projects or vendor data use | Should | S |
| 7-F7.61 | Cross-workspace rollup for multi-workspace customers | MISSING | `AdminConsole.tsx` is platform-operator only | Agency customers cannot compare their workspaces | Could | L |

**Area 7 count:** 5 HAVE · 25 PARTIAL · 31 MISSING (61).

**All areas:** 72 HAVE · 163 PARTIAL · 99 MISSING (334 features).

---

## Ranked build plan

Ordering rule: first the gaps that make a trial fail or look unfinished, then the parity core a buyer
compares line by line, then workspace/admin depth. Every task is a vertical slice (schema → API → UI)
that one engineer can land alone; the only shared-file edits are named in the row. `S` ≤ 1 day,
`M` 2–5 days, `L` > 1 week.

### Wave A — trial blockers (a buyer's first hour)

| # | Task | Closes | Files | Size |
| --- | --- | --- | --- | --- |
| 1 | Editor safety: unsaved-changes guard, zoom lock, "repeat previous" | 3-F3.2, 3-F3.3, 3-F3.43, 3-F3.52 | `features/editor/Editor.tsx`, `features/editor/shortcuts.ts` | S |
| 2 | Review at keyboard speed: `a`/`r`/`u`, bulk approve/reject on the board, reject reason | 3-F3.46 | `features/editor/Editor.tsx`, `features/project/AnnotateBoard.tsx`, `routers/images.py` | M |
| 3 | Any shape is editable: drag/resize polygons and OBB, vertex add/remove | 3-F3.8, 3-F3.10 | `features/editor/Editor.tsx`, `features/editor/geometry.ts` (new) | M |
| 4 | "Nothing here" flag plus multi-label classification | 3-F3.16, 3-F3.18 | `models/project.py`, `routers/images.py`, `features/editor/Editor.tsx`, `features/workspace/Home.tsx` | M |
| 5 | One query bar: chips, negation, `class:x>=4`, filename/date ranges | 1-F4.3, 2-F2.27 | `features/project/Dataset.tsx`, `routers/images.py` | M |
| 6 | Version wizard: transformed-image preview, six resize modes, tag filter | 4-F4.13, 4-F4.18, 4-F4.26 | `features/project/Versions.tsx`, `services/imaging.py`, `services/versioning.py` | M |
| 7 | Auto-label: per-class prompts, keep/merge/replace policy, credit estimate | 3-F3.27, 3-F3.29, 3-F3.32 | `features/project/AutoLabelDialog.tsx`, `routers/training.py`, `services/refine.py` | M |
| 8 | Deploy becomes a hub: runtime chooser, snippet rewrite, self-hosted entry | 6-F6.1, 6-F6.5, 6-F6.8 | `features/project/Deploy.tsx`, `apps/inference/README.md` (link target only) | M |
| 9 | Public project page, licence dialog at publish, fork CTA | 1-F5.1, 1-F5.2, 7-F7.53 | `routes/public.routes.tsx`, `features/project/PublicProject.tsx` (new), `routers/projects.py` | M |
| 10 | Nav/IA pass: DATA → LABEL → MODELS → DEPLOY, STUDIO folded into Insights tabs | 1-F3.2, redesign | `lib/nav/project/studio.ts`, `lib/nav/registry.ts`, `routes/project/studio.routes.tsx`, `features/project/insights/Insights.tsx` | S |

### Wave B — parity core (editor, train, workflows)

| # | Task | Closes | Files | Size |
| --- | --- | --- | --- | --- |
| 11 | Foundation-model assist: model picker with reasons, class mapping, persists across images | 3-F3.21, 3-F3.54 | `features/editor/Editor.tsx`, `routers/images.py`, `adapters/catalog.py` | M |
| 12 | Train screen: architecture families, checkpoint choice, pre-train warnings | 5-F5.7, 5-F5.8, 5-F5.40–42 | `features/project/Train.tsx`, `routers/training.py`, `adapters/catalog.py` | M |
| 13 | Evaluation: task-appropriate metrics, tuned threshold as the served default, per-class counts | 5-F5.21, 5-F5.22, 5-F5.28 | `services/evaluate.py`, `features/evaluation/EvalPanel.tsx`, `routers/training.py` | M |
| 14 | Custom weight upload with automatic evaluation | 5-F5.29, 5-F5.31 | `routers/training.py`, `features/project/Models.tsx`, `adapters/` | M |
| 15 | Augmentation catalogue: 14 options, guidance, resulting-count estimate | 4-F4.15, 4-F4.30, 4-F4.33 | `features/project/Versions.tsx`, `services/imaging.py` | M |
| 16 | Export: five more formats, in-dialog curl/SDK snippet, generating-state message | 4-F4.34, 4-F4.35 | `services/exporters.py`, `features/project/Versions.tsx` | M |
| 17 | Workflow as an API: declared inputs, callable endpoint, video/camera test input | 6-F6.10, 6-F6.23, 6-F6.33 | `routers/workflows.py`, `features/project/Workflows.tsx`, `services/workflow_runner.py` | M |
| 18 | Workflow canvas with ports and branching (replaces the linear list) | 6-F6.21 | `features/project/Workflows.tsx`, `features/project/WorkflowBlocks.tsx`, `services/workflows.py`, `lib/types.ts` | L |
| 19 | Workflow node controls: disable, sinks switch, cache badge | 6-F6.24, 6-F6.25, 6-F6.29 | `features/project/Workflows.tsx`, `features/project/WorkflowBlocks.tsx`, `services/workflows.py` | M |
| 20 | Assignment that carries instructions and notifies the assignee | 3-F3.45 | `features/project/AnnotateBoard.tsx`, `routers/images.py`, `services/alerts.py` | M |
| 21 | Per-image history that survives reload and can be reverted | 3-F3.49 | `features/editor/Panels.tsx`, `routers/images.py`, `models/project.py` | M |
| 22 | Brush and pixel-mask tool with mask-aware export | 3-F3.11 | `features/editor/Editor.tsx`, `lib/types.ts`, `services/imaging.py`, `services/exporters.py` | L |

### Wave C — workspace data and people

| # | Task | Closes | Files | Size |
| --- | --- | --- | --- | --- |
| 23 | Workspace asset library: cross-project search with a selection-scoped action bar | 1-F4.2, 2-F2.25 | `routes/workspace.routes.tsx`, `features/workspace/AssetLibrary.tsx` (new), `routers/images.py` | L |
| 24 | Typed per-image metadata with sidecar import and filters | 2-F2.18, 2-F2.32 | `models/project.py`, `routers/images.py`, `services/importers.py`, `features/project/Dataset.tsx` | M |
| 25 | Duplicate workbench: near-duplicate clusters and a "re-upload restores labels" rule | 2-F2.35, 2-F2.36 | `routers/images.py`, `features/project/DatasetHealth.tsx`, `services/versioning.py` | M |
| 26 | Trash covers versions, runs and workflows, with who/when/days-left | 1-F5.6, 2-F2.45, 7-F7.43 | `routers/workspaces.py`, `routers/versions.py`, `routers/training.py`, `features/settings/Settings.tsx` | M |
| 27 | Members and roles polish: default role, self-change guard, built-in matrix, copy-a-role | 1-F5.4, 7-F7.6, 7-F7.8–10 | `features/settings/Settings.tsx`, `features/governance/Roles.tsx`, `routers/rbac.py` | M |
| 28 | Key lifecycle: rename, protect, disable, roll with a dependency checklist | 1-F1.5, 7-F7.27, 7-F7.28 | `routers/workspaces.py`, `models/identity.py`, `features/settings/Settings.tsx` | M |
| 29 | Audit that a reviewer can use: actor/resource filters, before/after diff, policy switches | 7-F7.38–39, 7-F7.60 | `routers/audit.py`, `features/governance/AuditLog.tsx`, `routers/privacy.py` | M |
| 30 | Connectors and notifications with a UI: credential store, sync run guards, webhook/pipeline sinks | 7-F7.46–49, 6-F6.18 | `features/settings/Connectors.tsx` (new), `routers/connectors.py`, `routers/webhooks.py`, `routers/alerts.py` | L |

### Wave D — commercial and enterprise (owner decisions needed first)

| # | Task | Closes | Files | Size |
| --- | --- | --- | --- | --- |
| 31 | Self-serve plan change, seats and an add-on, with 80%-of-credits notices | 7-F7.12, 7-F7.20–24 | `features/settings/Settings.tsx`, `routers/workspaces.py`, `services/metering.py`, new billing adapter | L |
| 32 | SSO sign-in with domain proof (not just OIDC bearer validation) | 7-F7.35 | `routers/auth.py`, `oidc.py`, `features/auth/Auth.tsx`, new domain model | L |
| 33 | Data-protection surface: licensing opt-out, region statement, workspace/account deletion, SIEM export | 7-F7.40, 7-F7.44–45, 7-F7.59 | `routers/privacy.py`, `routers/workspaces.py`, `features/governance/Trust.tsx` (new) | M |
| 34 | Batch and dedicated deployment options behind the same snippet contract | 6-F6.3, 6-F6.4 | `routers/deployments.py`, `features/project/Deploy.tsx`, `apps/worker` | L |
| 35 | Stream reliability: recovery states, needs-attention, offline alerts | 6-F6.44 | `apps/backend/app/streams/`, `features/streams/StreamDetail.tsx`, `routers/alerts.py` | M |
| 36 | Active learning with review batches and caps | 6-F6.19 | `features/project/ProjectSettings.tsx`, `routers/ops.py`, `features/project/AnnotateBoard.tsx` | M |

### Wave E — redesign finish

| # | Task | Closes | Files | Size |
| --- | --- | --- | --- | --- |
| 37 | Skeleton, empty and error states across grid, dashboard and deploy | UX gap, 1-F1.4 | `components/ui.tsx`, `index.css`, `features/project/Dataset.tsx`, `features/workspace/Dashboard.tsx` | M |
| 38 | Editor shell visual pass: tool rail, panel tabs, header density, dark/light parity | redesign, 3-F3.1 | `features/editor/Editor.tsx`, `features/editor/Panels.tsx`, `index.css` | M |
| 39 | Own icon, copy and token pass so nothing reads as a competitor's UI | owner goal | `components/shell/icons.ts`, `lib/theme.ts`, `index.css` | M |
| 40 | Mobile: editor and board usable at 375 px | redesign | `features/editor/Editor.tsx`, `components/shell/AppSidebar.tsx`, `features/project/AnnotateBoard.tsx` | M |

### Sequencing notes

- Task 18 rewrites the files of tasks 17 and 19. Land 17 and 19 first, or fold all three into one
  L-sized job with one reviewer.
- Tasks 2, 4, 21, 24 and 26 each add a column or table. They touch `models/project.py` or
  `models/identity.py`; merge them one at a time and run the migration test on an existing database
  as well as an empty one (PM addendum rule).
- Tasks 30, 31, 32 and 33 need owner decisions before code: which billing provider, which plan
  ladder, whether self-hosted weights are sold, and which data region is offered. Without those,
  the UI would encode guesses.
- Every task in Wave A and B is visible in a demo, which is why they outrank the admin depth in
  Wave C even where the admin gap is a Must.

### What not to copy

- Static, unrotatable invite links (7-F7.4): ship per-invite tokens plus a rotatable join link.
- Review gated by a paid add-on (3-F3.46): review is the quality story; keep it in the base plan.
- Model ids frozen to the first training (5-F5.34): the deployment alias already does this better.
- A single-key default with invisible fallback (7-F7.33): if a default key is added, show it as a
  badge from day one.
