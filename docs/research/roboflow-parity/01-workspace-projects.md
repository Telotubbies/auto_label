# Area 1 — Workspace, projects, and the first-run path

Method: fetched `docs.roboflow.com/llms.txt` (full index, 893 entries) plus 15 docs pages and
`roboflow.com/pricing` on 2026-11-17. Pages read in full: workspace creation, key concepts, project
creation, upload, annotation tools, annotation batches, dataset search, project folders,
make-public, project description, fork-a-universe, universe intro, universe search,
invite-a-member, change-owner, asset library, trash, API keys, Teams add-on, Agent, docs home.
Screens are login-walled, so every "what the screen looks like" claim is either a docs sentence or
marked **inferred**. Lowercase strings in quotes are Roboflow labels quoted as evidence of their
flow; none of them is proposed as LabelDesk copy.

Not opened: `/quick-start` (now redirects to the docs home), changelog entries cited by title only,
RBAC and SSO pages, billing pages beyond the Teams add-on, the app itself.

---

## 1.1 Sign-up and first run

### F1.1 One-screen workspace creation with plan choice inline (RF: *Create a Workspace*)

- **What the user does:** signs in, then names their first workspace and picks a plan on the same
  screen before seeing any product surface.
- **Flow:** 1. Sign-in page (email or Google) → 2. Workspace switcher in the left rail: click the
  workspace name, then the `+` control → 3. **New workspace** screen: one name field plus a plan
  picker (Free / paid / Enterprise), then "Continue" → 4. The name is turned into the workspace
  slug immediately, so the URL and API workspace ID exist before any project does → 5. hand-off to
  the assistant surface (F1.3). [error: name already taken — inferred, docs only say the name
  becomes the ID].
- **Why it is easy:** there is no separate "billing settings" detour; the plan decision and the
  identity decision are one form, and the free tier needs no card (pricing FAQ).
- **Gates:** Free = $0, 10 credits/month, 20 projects, unlimited admin seats. Paid credit packs
  from $39/mo. No card required to start.
- **Sources:** https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md ,
  https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/auth/` (dir),
  `apps/frontend/src/features/workspace/Home.tsx`

### F1.2 Three setup questions that seed the assistant (RF: *Workspace Setup Questions*)

- **What the user does:** answers three free-text questions — what they want to build, what should
  happen with the result, what data they already have — or skips them.
- **Flow:** 1. **Setup questions** screen, one question at a time → 2. each field has a "use an
  example" control that fills editable sample text → 3. "Back" / "Skip" per question → 4. answers
  are prepended as the first message of a new assistant conversation → 5. the assistant surface
  opens and proposes a starting point. Skipping everything opens an empty conversation
  (documented). Workspaces created later skip this step entirely.
- **Why it is easy:** the user never restates the brief to the assistant, and no answer is a hard
  gate, so a user who wants to poke around is not blocked.
- **Gates:** none; first workspace only.
- **Sources:** https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx`

### F1.3 The assistant is the post-signup home, not a blank project list (RF: *Roboflow Agent*)

- **Flow:** 1. **Assistant** screen: chat box centred, a `+` menu (create asset / attach files / use
  camera), left rail with the assistant selected → 2. type, or pick a starter action → 3. long jobs
  surface as a counter above the chat box and in a **Background tasks** panel (`[loading]` running
  pill with count; `[empty]` nothing running; a finished task links to the page it created) → 4. a
  project created in a tab turns that tab into the project view. First-message `[error: ...]` is
  **inferred**; docs describe none.
- **Why it is easy:** the first screen already produces an artifact (project, copied dataset,
  generated images) before the user learns the navigation; image generation is the documented
  cold-start path when there are no photos yet (1–10 images, billed only for images kept).
- **Gates:** assistant runs on credits; image generation per saved image; bring-your-own LLM key is
  a workspace toggle Roboflow must enable, and is unavailable in the EU region.
- **Sources:** https://docs.roboflow.com/agents/roboflow-agent.md ,
  https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx`,
  `apps/frontend/src/features/workspace/Tour.tsx`

### F1.4 Guided tour as a re-runnable coach mark, not a modal wall

- **What the user does:** steps through a short tour that highlights one region of the home screen
  at a time; can end it at any point and replay it later.
- **Flow:** 1. first visit to the workspace home shows a floating card ("step 2 of 6") anchored
  bottom-right → 2. the target element is scrolled into view, ringed, and receives focus → 3.
  Next / Back / close; the last step's primary button reads as a finish action → 4. the card is a
  non-blocking region, so the page stays usable behind it. Replay entry point is not documented for
  Roboflow (**inferred** that one exists, since the assistant page is described as the ongoing home).
  `[empty]` state: no tour once dismissed. `prefers-reduced-motion` behaviour is **inferred** as
  required.
- **Why it is easy:** a floating non-modal card costs nothing if ignored, which matters because
  checklist completion benchmarks are low (19.2% average, per the earlier repo note).
- **Gates:** none documented.
- **Sources:** https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md (setup ends on
  the assistant page); tour mechanics are from LabelDesk's own `Tour.tsx` pattern, cited here as a
  design comparator, not as a Roboflow claim.
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Tour.tsx`,
  `apps/frontend/src/features/workspace/dashboardRules.ts` (dir listing only)

### F1.5 API key is one click from the docs, and shown once on creation (RF: *API Keys*)

- **What the user does:** creates a key and copies it, or reveals an existing one.
- **Flow:** 1. Docs home keeps a standing pointer to the key page → 2. **Settings → API Keys**
  lists keys as rows: name, badges, creator and date, masked value with reveal and copy, row menu
  (edit, protect, roll, disable, revoke) → 3. "Generate new key" → name → **Key created** dialog
  shows the value once → 4. afterwards the API and CLI never return it again. `[empty]` first-run
  state: no keys yet, table empty, generate button still available — **inferred** because every
  workspace action needs a key and the app auto-creates one when it needs one.
- **Why it is easy:** the value is revealed exactly where it is needed and the list tells you which
  key the app itself is using ("default" vs "in use" badges), so a user does not have to guess which
  of five keys is live.
- **Gates:** viewing keys needs a permission that admins hold by default; scoped/folder keys and
  choosing a default are paid/enterprise features (pricing: scoped keys not in Core).
- **Sources:** https://docs.roboflow.com/reference/authentication/authentication/manage-api-keys-in-the-dashboard.md ,
  https://docs.roboflow.com/readme.md , https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/settings/` (dir)

## 1.2 Project types and creation

### F2.1 Type-first creation form, launched from the workspace home (RF: *Create a Project*)

- **What the user does:** fills name + annotation group + type, and submits.
- **Flow:** 1. Workspace home → "create new project" → 2. **New project** screen: project type,
  2. project name, 3. annotation group (a noun for the thing being labelled, e.g. "vehicles"), then
  submit → 3. the project is created empty and the user is taken to the **upload** screen, which is
  also the first thing the project shows. The same form opens inside an assistant tab ("create a
  new asset" → new model), and the tab becomes the project view afterwards.
- **Why it is easy:** three fields, all of them things a user already knows; the noun for the
  annotation group is reused as the wording inside the labeling prompts, so a first-time labeler
  sees "draw a box around each vehicle" instead of a generic instruction.
- **Gates:** 20 projects on the free/Core tier (pricing), custom on Enterprise.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/create-a-project.md ,
  https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx` (already renders a
  5-card type picker with icon, one-line description and 2 capability chips; licence, folder,
  annotation group and initial classes are in the same modal), `apps/backend/app/routers/projects.py`

### F2.2 Eight task types, one line of description each, and a "request another type" escape

- **What the user does:** picks the task type from the creation form.
- **Flow:** 1. type selector → 2. the list is: find objects with boxes; assign one label to a whole
  image; assign several labels to a whole image; find objects to the pixel with separate instances;
  find objects to the pixel with one mask per class; find named points and link them into a
  skeleton; mark when an action starts and ends in a video; multimodal (image + text pairs for VLM
  work) → 3. a dropdown entry lets the user register interest in a type that is not listed → 4. the
  type is fixed at creation and drives everything downstream (F2.3).
- **Why it is easy:** the descriptions are phrased as outcomes ("assign several labels") rather than
  as model families, so the choice does not require knowing what YOLO is.
- **Gates:** all listed types appear on the free tier; there is no documented per-type gate.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/create-a-project.md (7 types),
  https://docs.roboflow.com/platform/workspaces/key-concepts.md (adds multimodal),
  https://docs.roboflow.com/datasets/universe/universe/find-a-dataset-on-universe.md (filter list)
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx` (`TYPES` array: object
  detection, instance segmentation, classification, keypoints, anomaly detection behind a flag —
  no semantic segmentation, no multi-label, no video/action, no multimodal; anomaly detection is a
  LabelDesk-only addition)

### F2.3 The type is the schema: what it silently changes

- **What the user does:** nothing extra — the type decides which tools appear, what can be
  imported, what can be trained, and what can be exported.
- **Flow (documented consequences):**
  | Type | Annotation tools offered | Notes from docs |
  |---|---|---|
  | Object detection | boxes, polygons, masks (polygon/mask auto-converted to boxes) | most permissive importer |
  | Instance segmentation | polygons, masks | one shape per object |
  | Semantic segmentation | polygons, masks | all objects of a class are one entity |
  | Keypoint detection | keypoints on a defined skeleton; skeleton editor (points, edges, symmetry) | skeleton definition is a separate settings surface |
  | Classification (single / multi) | none — image-level labels only | zip re-upload always replaces the label |
  | Action recognition | video segment start/end on a timeline | videos stay whole instead of being split into frames |
  | Multimodal | prefix-based text/region pairing for VLM fine-tuning | separate save path in the editor |
  Model architectures and export formats are limited by the type ("formats you can use depend on
  the project type"); uploading a video into an image-based project opens a frame-extraction dialog
  (interval from 60 fps down to 1 frame / 60 s, trim handles, manual selection with `M` / `,` / `.`),
  while an action-recognition project keeps the video intact.
- **Why it is easy:** the user never chooses an annotation format or an export layout up front; the
  editor only shows shapes the target model can learn from.
- **Gates:** none documented per type; per-format export gates exist on the formats page (not read).
- **Sources:** https://docs.roboflow.com/datasets/annotate/annotate/annotation-tools.md ,
  https://docs.roboflow.com/datasets/create-and-upload/adding-data.md ,
  https://docs.roboflow.com/platform/workspaces/key-concepts.md
- **LabelDesk hook points:** `apps/backend/app/adapters/ultralytics_ad.py` (`TASK[project_type]`),
  `apps/backend/app/adapters/refine.py` (shape logic branches on instance vs box),
  `apps/frontend/src/lib/nav/visibility.ts` (`projectType` already reaches nav visibility)

### F2.4 Annotation groups share classes and labels across projects (RF: *Annotation Groups*)

- **What the user does:** reuses a group noun when creating a second project, or creates a new one.
- **Flow:** 1. creation form field 3 (annotation group), default is the project name when created
  from the CLI → 2. projects in the same group share the class list and the annotations → 3. this
  makes a second project over the same imagery cheap (different split, different preprocessing).
  `[error: ...]`: docs do not describe a conflict when two projects in one group disagree on a class
  (**inferred** risk, see gaps).
- **Why it is easy:** a team labelling "defects" across five product lines keeps one vocabulary, so
  classes can be compared and merged later instead of reconciled by hand.
- **Gates:** none documented.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/create-a-project.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx` (`annotation_group`
  field already posts to the API), `apps/backend/app/routers/projects.py`

### F2.5 Creation is scriptable and agent-callable, with the same shape as the form

- **What the user does:** creates the same project from Python, the CLI, or an assistant instead of
  the form.
- **Flow:** 1. `create_project(name, type, licence, annotation_group)` / `roboflow project create
  <name> --type <type>` / `POST /{workspace}/projects` / MCP `projects_create` → 2. JSON response
  echoes status, project, type, workspace → 3. `--json` variants exist for every read command → 4.
  a folder can be passed at creation so the project never appears at the top level.
- **Why it is easy:** automation is not a second-class path; the licence field doubles as the
  privacy switch (`"Private"` vs `"MIT"` / `"CC BY 4.0"`).
- **Gates:** API creation needs the `project:create` scope on Enterprise-scoped keys (scoped keys are
  not in Core).
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/create-a-project.md ,
  https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/backend/app/routers/projects.py`

## 1.3 Project home and project navigation

### F3.1 The project's own "about" page carries description, public URL and settings entry (RF: *Project Overview*)

- **What the user does:** edits the blurb that becomes the public dataset page, and finds the
  public link once the project is public.
- **Flow:** 1. inside a project, open the three-dot menu next to the project name in the project
  sidebar → 2. "project overview" → 3. **Overview** screen with an "edit" affordance on the
  description → 4. editor → "save description" → 5. back on Overview, a URL row appears at the
  bottom when the project is public; copy it to see the visitor page.
- **Why it is easy:** the description is written where the author already is, and the public URL is
  shown to them at the moment it starts existing — no hunt through settings after publishing.
- **Gates:** public projects are unavailable when a workspace blocks them (F5.1); the description
  itself is not gated.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/set-a-project-description.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/ProjectLayout.tsx` (no overview or
  "about" surface in the current project nav), `apps/frontend/src/features/project/ProjectSettings.tsx`

### F3.2 Project sidebar is the lifecycle, and upload is the landing page

- **What the user does:** moves top to bottom through one column: get data in, label, snapshot,
  train, ship.
- **Flow:** 1. after creation, the **upload** screen with a drag-and-drop target (also reachable as
  "upload data" from the sidebar) → 2. sidebar items named in docs: upload data, annotate, dataset,
  versions, models, deploy; plus health check, overview and project settings reached from the
  sidebar / three-dot menu → 3. `[loading]` — a zip over 300 files processes server-side and reports
  progress in an **activity centre** while the user keeps working → 4. `[error: ...]` an undecodable
  video surfaces an explicit "unsupported video" message that names the codec (HEVC/H.265) and the
  remedy (convert to MP4/H.264) → 5. images land in a batch on the annotate board.
- **Why it is easy:** the first screen of a new project is an action (drop files), not a stats page
  with zeros; the error message tells the user the fix rather than the failure.
- **Gates:** image limits are enforced identically on web, API and zip path (30 MB, 16,384 px per
  side, ~179 MP total); images above it are refused rather than silently downscaled.
- **Sources:** https://docs.roboflow.com/datasets/create-and-upload/adding-data.md ,
  https://docs.roboflow.com/platform/workspaces/key-concepts.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Upload.tsx`,
  `apps/frontend/src/features/project/ProjectLayout.tsx`

### F3.3 The annotate board is the project's real home for labelers (RF: *Annotate page*)

- **What the user does:** works a four-column board of batches instead of a list of images.
- **Flow:** 1. **Annotate** screen, four columns: unassigned → annotating → review → dataset, each
  holding batch cards with progress → 2. assign a whole batch or a subset; any unassigned remainder
  is split into a new batch automatically → 3. open a card to jump into the editor at that batch's
  first image → 4. batch menu: merge (only compatible ones — not across source videos, not managed
  review queues; the largest batch survives) or delete (only from unassigned; otherwise "move to
  unassigned" first) → 5. approved batches enter dataset, rejected ones return to annotating.
  `[empty]` unassigned column on a fresh project — the real first-run state (**inferred** copy).
  `[error: ...]` batch deletion is irreversible and the docs say it cannot be recovered, unlike
  projects, which go to Trash.
- **Why it is easy:** the board answers "where is my work" in one glance for the person who manages
  labelers, and the same screen is the queue for the labeler, so no separate task list exists.
- **Gates:** the review column is not available to free/public-tier users (the docs caption says it
  is absent for public users); review mode, labeling analytics and labeler/reviewer roles sit in the
  Teams add-on (up to 10 non-admin members).
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/manage-batches.md ,
  https://docs.roboflow.com/platform/billing-and-plans/teams-add-on.md , https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/AnnotateBoard.tsx` (same four
  columns already: unassigned / annotating / review / dataset)

### F3.4 Project-level counters exist, but not on the overview page

- **What the user does:** reads counts where they occur rather than from a dashboard.
- **Flow:** the project list row and API show type, image count, versions; the CLI `project get`
  prints images, versions and per-class counts; the versions tab lists versions newest-first with
  the model trained on each. Dataset-level health (class balance, dimensions, annotation heat map,
  object-count histogram, summary stats) is a separate **health check** page, covered in Area 2.
  There is no documented single "project home" tile set with stats + recent activity (**inferred**
  absence; see gaps).
- **Why it is easy:** numbers appear next to the decision they support (a version before you train
  it, a class count before you start labelling) rather than in one abstract dashboard.
- **Gates:** dataset analytics included on Core per pricing.
- **Sources:** https://docs.roboflow.com/platform/workspaces/list-workspaces-and-projects.md ,
  https://docs.roboflow.com/datasets/universe/universe/set-a-project-description.md
- **LabelDesk hook points:** `apps/backend/app/routers/projects.py` (`/{project}/analytics`)

## 1.4 Workspace-level search and navigation

### F4.1 Folders sit above projects on the workspace home, and projects are movable by drag

- **What the user does:** organises projects into a shallow tree that is the first thing on the
  workspace page.
- **Flow:** 1. **Workspace home**: folder cards at the top, then ungrouped projects → 2. "new folder"
  top-right → name → save → you land inside the folder, and any project created from there is added
  to it → 3. project three-dot menu → "move project" → pick destination (workspace name = out of the
  folder) → 4. drag a project card onto a folder card; select several folders and drag one to move
  them all → 5. renaming and deleting folders; deleting a folder keeps its contents and lifts them
  one level (or to workspace level). `[empty]` — no folders yet: only the new-folder button
  (**inferred**).
- **Why it is easy:** moving is a drag, and deleting a folder is non-destructive by design, so
  tidying cannot lose work.
- **Gates:** folder permissions and the folders API are Enterprise; nested folders appear in the API
  (`parent_id`) but nesting is not described in the web flow.
- **Sources:** https://docs.roboflow.com/datasets/manage/project-folders.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx` (folder select in the
  create modal, folder list on home)

### F4.2 Workspace-wide media search is a first-class sidebar destination (RF: *Asset Library*)

- **What the user does:** searches images and videos across every project from one bar.
- **Flow:** 1. **Asset library** item in the workspace sidebar → 2. search bar takes free text
  (semantic), `like-image:<id>`, filter syntax (`class:`, `tag:`, `metadata:key>value`) and a "type"
  dropdown that appears only when the workspace holds more than one project type → 3. a "raw" toggle
  swaps the chip UI for the query string → 4. select images, or "select all" to span every match; a
  sticky action bar then offers tag, metadata, create project, add to project, run a workflow,
  export, delete → 5. export stays disabled until "select all", so the download always matches the
  query. `[loading]` jobs appear in the activity centre and a batch-processing tab.
- **Why it is easy:** the same query language serves one project and the whole workspace, and the
  destructive/expensive actions only unlock after an explicit "select all", which prevents
  accidental workspace-wide deletes.
- **Gates:** exporting workspace images needs a permission owners hold by default; running a
  workflow costs credits; video indexing included on Core.
- **Sources:** https://docs.roboflow.com/platform/workspaces/asset-library.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Dataset.tsx` (project-scoped only)

### F4.3 Query language with chips, negation and numeric class counts

- **What the user does:** finds the images that are wrong, not just the images that match a word.
- **Flow:** 1. **Dataset** screen search field → 2. plain words = semantic search; any `filter:` =
  structured → 3. documented filters: `tag`, `filename` (with `*` wildcards), `split`, `job`,
  `min/max-width`, `min/max-height`, `min/max-annotations`, `class`, `date`, `like-image` → 4.
  boolean `AND/OR/NOT` with parentheses, leading `-` to invert, `class:helmet>=4` for counts → 5.
  select results → bulk actions (e.g. move to another split), large selections process in the
  background. `[empty]` — zero matches: docs do not describe the empty state (**inferred**: needs a
  "no images match, clear N filters" affordance).
- **Why it is easy:** "images with a helmet but no vest" is one line, and the same string runs on the
  API, so an audit someone does by hand can be re-run as a job later.
- **Gates:** dataset search included on Core.
- **Sources:** https://docs.roboflow.com/datasets/manage/manage-datasets/dataset-search.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Dataset.tsx`,
  `apps/backend/app/routers/images.py`

### F4.4 Public dataset discovery with image-similarity search (RF: *Universe search*)

- **What the user does:** searches public datasets by text, by keyword, or by dropping in one of
  their own images.
- **Flow:** 1. Public gallery home, search bar → 2. results ranked semantically by default; a
  "search by" toggle switches to keyword/metadata matching → 3. left filter panel: has-a-model,
  project type, trained model family, plus advanced filters (image count, stars); an image dropzone
  reorders results by visual similarity and can be combined with text and filters → 4. dataset page
  shows class list, licence and a citation block → 5. "use this dataset" → fork (F5.3). `[loading]`
  — image search accepts JPEG/PNG/HEIC/GIF ≤ 20 MB, GIF searches on the first frame; `[error: ...]`
  for oversized files is not documented (**inferred**).
- **Why it is easy:** dropping one photo of the user's own scene is a faster way to find relevant
  public data than describing it in words.
- **Gates:** public datasets are free to browse; forking consumes the target workspace's image
  quota/credits.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/find-a-dataset-on-universe.md ,
  https://docs.roboflow.com/datasets/universe/universe/what-is-roboflow-universe.md
- **LabelDesk hook points:** `apps/frontend/src/features/landing/` (dir)

## 1.5 Sharing, publishing and collaboration

### F5.1 Publishing a project is a menu action plus a licence choice, with a workspace-wide kill switch

- **What the user does:** flips one project from private to public and picks its licence.
- **Flow:** 1. **Workspace home**, project card three-dot menu → 2. "make public" → 3. licence
  picker dialog → 4. the project appears publicly; the same menu offers "make private" to reverse
  it. There is a standing warning that private data, PII or NSFW content should not be published.
- **Why it is easy:** one project, one toggle, one licence — no separate publishing pipeline, and
  the reverse action is in the same place.
- **Gates:** a workspace settings switch ("public projects") can forbid new public projects; when it
  is off, existing public projects stay public; Enterprise has it off by default and a plan,
  compliance policy, or the EU region can lock the switch (support must change it).
- **Sources:** https://docs.roboflow.com/datasets/manage/make-a-project-public.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx` (visibility is chosen in
  the create modal, not as a post-hoc toggle), `apps/frontend/src/features/project/ProjectSettings.tsx`

### F5.2 The visitor sees a dataset page, not an app screen, and the primary CTA is "copy this into my account"

- **What the user does:** lands on a public dataset page from a search result or shared link, inspects
  classes and licence, then forks it.
- **Flow:** 1. public dataset page: description (authored by the owner, F3.1), class list, licence
  and citation block, dataset images → 2. "use this dataset" → 3. "fork project" (requires being
  signed in) → 4. **version-create** screen in the visitor's own workspace, ready to snapshot the
  copied data → 5. from there the visitor can label, generate versions or train.
- **Why it is easy:** the fork lands the visitor on the next meaningful step (make a version) instead
  of a generic project home; the empty-state problem of a new account is solved by someone else's
  data.
- **Gates:** forking needs a signed-in account, `project:create` scope on API, and enough image quota
  or credits in the target workspace.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/find-a-dataset-on-universe.md ,
  https://docs.roboflow.com/datasets/universe/universe/fork-a-universe-dataset.md
- **LabelDesk hook points:** `apps/frontend/src/features/landing/` (dir)

### F5.3 Fork errors are enumerated, not generic

- **What the user does:** hits a fork and either gets a copy or a precise reason.
- **Flow:** 1. fork request → 2. async task ID + polling URL returned → 3. `[loading]` polling; the
  web path shows a copy-in-progress state (**inferred** placement) → 4. `[error: 402]` not enough
  credits/quota; `[error: 403]` source not public; `[error: 404]` not found / wrong key / key belongs
  to another workspace; `[error: 409]` workspace already owns it; `[error: 422]` missing parameter or
  URL without a project slug → 5. on success, a new project with fresh versions and export settings
  (no inherited preprocessing).
- **Why it is easy:** "you already own this" and "you are out of quota" are different messages, so the
  user knows whether to retry, upgrade or look elsewhere.
- **Gates:** as F5.3 errors imply.
- **Sources:** https://docs.roboflow.com/datasets/universe/universe/fork-a-universe-dataset.md
- **LabelDesk hook points:** `apps/backend/app/routers/projects.py`

### F5.4 Three invite routes, all role-bearing, with visible pending state

- **What the user does:** adds teammates by email, by link, or by letting same-domain colleagues ask
  to join.
- **Flow:** 1. **Settings → Members** → 2. email route: paste comma-separated emails, pick a role,
  "send invites"; pending invites listed below with cancel / resend → 3. link route: copy a static
  per-role join URL (docs warn it can never be changed) → 4. domain route: a switch lets people from
  the workspace's verified domain see it in a "workspaces you can join" list and request access; the
  admin accepts from **Members** or from **Notifications** → 5. confirmation email to the admin when
  someone joins; verification = the person appears in the member list. `[empty]` — no invites yet,
  list empty (**inferred**). `[error]` — email invites expire after 3 days (resend or re-invite);
  seat limit reached blocks sending, resolved by upgrading or removing a member.
- **Why it is easy:** the role is chosen at invite time rather than after, and pending invites show up
  as rows so an admin can see who has not accepted.
- **Gates:** admin seats unlimited; non-admin members (labeler / reviewer / custom roles) need the
  Teams add-on (up to 10) or Enterprise; a pending invite still consumes a seat.
- **Sources:** https://docs.roboflow.com/platform/workspaces/team-members/invite-a-team-member.md ,
  https://docs.roboflow.com/platform/billing-and-plans/teams-add-on.md
- **LabelDesk hook points:** `apps/frontend/src/features/settings/` (dir),
  `apps/backend/app/routers/workspaces.py`

### F5.5 Ownership is per project, and Projects move by folder, not by workspace

- **What the user does:** hands a project to a colleague, or reorganises it within the workspace.
- **Flow:** 1. **Workspace home** → project tile three-dot → "change owner" → 2. dialog lists
  workspace members → 3. confirm → ownership transfers immediately; the new owner gains
  owner-only rights (including delete) and the old owner loses them. Moving between workspaces is
  not a documented operation — the only cross-project operations are folder moves and a merge that
  requires both projects to be in the same workspace. Workspace ownership itself cannot be
  transferred: the creator role is a non-removable signatory, so a successor must be promoted to
  admin instead.
- **Why it is easy:** the destructive right follows a named person, and both actions sit on the same
  tile menu where the project is visible.
- **Gates:** change-owner is limited to the current owner (or admin, **inferred**); merge and folders
  are workspace/Enterprise bounded.
- **Sources:** https://docs.roboflow.com/datasets/manage/change-project-owner.md ,
  https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md ,
  https://docs.roboflow.com/datasets/manage/project-folders.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx`

### F5.6 Deleting is soft by default; only the UI can make it permanent

- **What the user does:** deletes a project, version, training or workflow; or restores one.
- **Flow:** 1. delete from the item's menu → confirm → 2. the item leaves the workspace and every API
  listing; in-flight training is cancelled so credits stop → 3. **Settings → Trash** lists deleted
  items by type with who deleted it, when, and days left (30-day window) → 4. restore one row, a
  selection, or everything; items return to where they were deleted from → 5. permanent delete and
  empty-trash exist only in the web UI, deliberately absent from API/SDK/CLI. Parent-first rules:
  versions and trainings cannot return before their project. `[empty]` empty trash list; an amber
  marker warns when a project's own images will be removed too (shared images are always kept).
- **Why it is easy:** the destructive action is one click but reversible for 30 days, and automation
  cannot destroy data at all.
- **Gates:** trash actions are permission-scoped (`view_trash`, `trash_*`, `restore_*`) for custom
  roles; storage keeps counting against the plan during the 30 days.
- **Sources:** https://docs.roboflow.com/platform/workspaces/trash.md
- **LabelDesk hook points:** `apps/frontend/src/features/settings/` (dir),
  `apps/backend/app/routers/projects.py` (hard delete today)

## 1.6 Workspace home for a returning user

### F6.1 The returning user's entry point is the project list, with the assistant as a peer destination

- **What the user does:** opens the workspace and sees folders, then projects, then goes in.
- **Flow:** 1. sign-in → 2. left rail: assistant / asset library / settings / trash / members as
  documented destinations; projects with folders at the top of the home → 3. project tile → project
  (landing on upload for a new project, or wherever the user left off — **inferred**, docs do not
  state whether a project restores the last screen) → 4. workspace-level settings groups: plan and
  billing, usage (members, projects, source images, generated images, inference — all-time and by
  month), members, API keys, third-party keys, rename, delete, ownership note.
- **Why it is easy:** everything an admin needs for the workspace is one settings tree, and usage is
  expressed as the same units the billing page uses, so the two can be read together.
- **Gates:** usage dashboard on all plans; billing folders and organisation-level comparison are
  Enterprise.
- **Sources:** https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md ,
  https://docs.roboflow.com/datasets/manage/project-folders.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx`,
  `apps/frontend/src/features/workspace/Dashboard.tsx`

### F6.2 Empty states in a brand-new workspace are undocumented; the design has to be inferred

- **What the user does:** sees a workspace with nothing in it.
- **Flow:** 1. first workspace → setup questions (F1.2) → 2. assistant page (F1.3), which is the
  substitute for an empty project list → 3. if the user navigates to the project area anyway:
  folders row absent, project area empty, one create action. The docs never describe this screen,
  so the specific copy, illustration and whether a sample dataset is offered are **inferred /
  unknown**. What is documented: a new account's first workspace is the only one that asks setup
  questions, so returning users never see that path again.
- **Why it is easy:** routing the first screen to the assistant sidesteps the empty-table problem
  entirely; there is no separate "demo project" documented anywhere in the docs index.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/platform/workspaces/roboflow-workspaces.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/Home.tsx` (has `EmptyState` and a
  tour; no assistant surface)

### F6.3 Plan and role gates that change what the first-run user can actually do

- **What the user does:** nothing — the gates decide which screens exist for them.
- **Flow (observed/documented gates):**
  | Capability | Free | Core | Enterprise / add-on |
  |---|---|---|---|
  | Projects | 20 | 20 | custom |
  | Admin seats | unlimited | unlimited | custom |
  | Labeler / reviewer roles, review column, labeling analytics, label history | — | Teams add-on (≤10 non-admin) | included |
  | Review mode | — | Teams add-on | included |
  | SSO, RBAC, custom roles, scoped keys, folder permissions | — | — | included |
  | Public projects | allowed unless blocked | allowed unless blocked | off + lockable |
  | Vision-events retention | 14 days (Core baseline) | 14 days | custom |
- **Why it is easy:** the labeler role and the review column ship together in one add-on, so a team
  that invites a labeler knows what it is buying.
- **Gates:** as tabled; the EU region additionally blocks the Teams add-on and can lock the
  public-project switch.
- **Sources:** https://roboflow.com/pricing ,
  https://docs.roboflow.com/platform/billing-and-plans/teams-add-on.md ,
  https://docs.roboflow.com/datasets/manage/make-a-project-public.md
- **LabelDesk hook points:** `apps/frontend/src/lib/nav/visibility.ts`

---

## Title-only / unverified

Listed from the docs index but not opened, so detail is not confirmed: image comments for review
(`comment-on-an-image`), project rename and its effect on project URL and model API
(`rename-a-project`), project merge within a workspace (`merge-datasets`), folder-level access for
SSO (`project-folder-permissions`), organisation dashboards comparing workspaces, premium trial
state, public-project analytics (stars, views, downloads), workspace announcements banner, SDK
Universe search, `dataset-batches` API paging, and the "download a Universe dataset" path that is
not the fork path.

## Coverage gaps and what to check next

- **No screenshots of any logged-in screen.** The project sidebar order (upload / annotate / dataset
  / versions / models / deploy / health / overview / settings) is assembled from sentences across
  four pages, not from a single nav listing. Verify against a real account before treating it as the
  IA.
- **Guided tour, sample project, and demo data** are not documented anywhere in the docs index. The
  only first-run artefacts confirmed are: setup questions, the assistant landing page, and public
  dataset forking. Treat "Roboflow ships a demo project" as unproven.
- **Command palette / global project search:** nothing in the index or in any fetched page mentions
  one. The workspace-wide search that does exist is media search (Asset Library). Absence of a
  project-name search is an inference from silence, not a documented gap.
- **Type coverage vs docs:** the creation page lists 7 types, key concepts lists 8 (adds multimodal),
  and the API/SDK enum lists only 6 (no action recognition, no multimodal). Oriented/bounded-ellipse
  boxes are not a project type anywhere in the index — if LabelDesk wants rotated boxes, no sibling
  flow exists to copy.
- **What the first screen of a project shows for a returning user** — the docs describe the entry
  point after creation (upload) but not the resume behaviour.
- **Onboarding email verification, duplicate-name errors, and invite-link abuse** are not described;
  the invite-link warning ("static, cannot be changed") is the only hint of that risk.
- Next: read `reference/changelog/` entries for the last two quarters for onboarding or workspace-home
  redesigns, and `platform/enterprise-features/role-based-access-control.md` for the exact role names
  that the matrix will need.
