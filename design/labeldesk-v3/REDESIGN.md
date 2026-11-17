# LabelDesk v3 — Redesign specification

Status: design lane output, 16 Nov 2026. Evidence from a Playwright walkthrough of the running app
(`http://localhost:5173`, `demo@labeldesk.dev`) at 1440×900, plus a 375×812 pass; screenshots in
`design/labeldesk-v3/audit/`. Sources read: `docs/STANDARDS.md`, `research/reports/UX UI และฟีเจอร์ SaaS Computer
Vision.md`, `research/reports/Information architecture แพลตฟอร์ม ML.md`, and the current
`apps/frontend/src` shell, nav, project and editor code.

This document is the blueprint for the FigCraft file `design/labeldesk-v3/labeldesk-v3.figcraft`
(pages **Foundations** and **Screens**). It changes layout, hierarchy and copy. It does not change the
backend, the annotation engine or the licensing model.

---

## 1. What the audit found

The current UI is a competent admin console. It fails the owner's test — "does not fit real use" —
because it is organised by **feature**, while the work is organised by **steps of a pipeline**. Every
screen is reachable, nothing tells a person what to do next, and the one action that is always offered
("Train Model") is wrong on almost every screen.

Measured path, cold start: sign in → Home → project row → project opens on **Dataset** → Annotate →
Review card → editor. Five interactions before a box can be drawn, and the first two hide the goal.
The same loop in Roboflow is: project → Annotate → image.

### Screen-by-screen friction

| # | Screen (audit file) | Observed friction | Principle violated |
|---|---|---|---|
| 1 | Login `01-login.png` | Marketing panel ("Access stays with you") occupies 45% of a task screen; one field pair; no SSO, no "demo workspace" shortcut. | Nielsen #8 aesthetic-and-minimalist design; Gulf of execution (Norman) |
| 2 | Home `02-home.png` | Five KPI cards come first, the actual queue ("Work waiting for you", 16 items) is third; "At a glance" and "Your workspace at a glance" are two different things with the same name; "Replay tour" sits above real work; 11 nav destinations, two of them ("Members", "API Keys") are also inside Settings. | Hick's law; Law of proximity; Von Restorff (the wrong thing is loudest) |
| 3 | Project entry `12-project-overview.png` | A project has **no overview**. Clicking a project drops you on the Dataset grid. Nothing states which of the five workflow stages is done, blocked or next. | Gulf of evaluation (Norman); recognition over recall (Nielsen #6) |
| 4 | Project rail (all project screens) | Eleven flat links in five ALL-CAPS groups. "Dataset", "Versions", "Insights", "Model insights" are jargon to a shift supervisor; "Models" exists twice (workspace and project) with different meanings. | Miller's 7±2; Jakob's law (CV tools order by lifecycle); Nielsen #2 match to the real world |
| 5 | Global top bar (all project screens) | "Train Model" is the primary button on Upload, Annotate, Dataset, Versions, Models and Deploy. On Annotate it invites you to skip labelling. "16 awaiting review" is styled like a status badge but is a link. | Nielsen #4 consistency; Fitts's law used against the step |
| 6 | Upload `13-upload.png` | Two equal-weight buttons ("Select Files", "Select Folder"), no batch naming before upload, no statement of dedupe or split behaviour, and the page never says what happens next. | Nielsen #5 error prevention; Gulf of execution |
| 7 | Annotate board `15-annotate.png` | Batch kanban with four columns; the image is never the unit. A labeler must find their batch, press "Annotate", then wait for an image to load. "Approve all" is a solid green button beside "Reject all" — a bulk irreversible-looking action with no count. | Error prevention; Doherty threshold (no perceived progress); Nielsen #5 |
| 8 | Editor `25-editor.png`, `26-editor-drawn.png` | The strongest screen: solid canvas, class rail, object list, review mode. Weak points: 8 left tabs (Labels, Attributes, Comments, History, Raw) compete with the class list; "Smart Polygon" is the loudest control in the rail; no "next image" affordance in the top bar; 11 px metadata. | Fitts's law (primary targets); hierarchy; WCAG 1.4.4 (small text at 11 px) |
| 9 | Dataset `14b-browse-full.png` | Eight filters in two rows before any image (search, status, split, class, tag, batch, annotations, quality, sort); grid metadata at 11 px with colour dots instead of class names; header says "24 images" while Home says 40 — uploaded vs approved is never distinguished. | Hick's law; Nielsen #2; WCAG 1.4.3 |
| 10 | Versions `16-versions.png` | "Generate New Version" (top right) and "Train a model" (card) are two primaries on one screen; split counts shown after the fact; no diff between versions; download leads with a Python snippet rather than the file. | Nielsen #4; progressive disclosure |
| 11 | Train `19b-train-full.png` | Fifteen variant chips, five family cards with licence badges, then a Fast/Advanced toggle that appears *after* the choice; cost ("3 credits") in 11 px grey at the very bottom; no time or VRAM estimate before starting. | Cognitive load; Nielsen #8; trust (선행 정보 없음) |
| 12 | Models `21-models.png` | Four metric cards and two charts, no interpretation and no next action; "Train new model" repeats the global button; the evaluation note explains a caveat instead of offering the fix. | Gulf of evaluation; Nielsen #10 help and documentation |
| 13 | Deploy `22-deploy.png` | Three code snippets stacked; the cURL line is clipped at the card edge (`.../e6b6a0faf`); threshold slider has no preview until an image is uploaded; empty drop zone with no sample. | WCAG 1.4.4 / overflow; error prevention; recognition over recall |
| 14 | Playground `04-playground.png` | Separate destination from Deploy & Test, same job. Two "test my model" entry points. | Nielsen #4; IA duplication |
| 15 | Mobile `28-mobile-home.png`, `29-mobile-project.png` | Desktop layout stacked: 2-column KPI grid, hamburger-only nav, project sections in a horizontal scroller, 11 px text. No bottom navigation, no thumb-reach primary action. | Mobile ergonomics; WCAG 2.5.5 target size |
| 16 | Settings / Governance | Seven settings tabs; the workspace rail repeats "Members", "Plan & Usage", "API Keys" as top-level items that land inside Settings. | IA duplication; Hick's law |

Cross-cutting: colour and glass already follow the standard (HCT tokens, `Glass` on chrome only).
The problem is **structure, priority and language**, not the palette. That is why the redesign keeps
the annotation canvas, the dense tables and the charts solid, and spends its boldness on navigation,
hierarchy and the project home.

---

## 2. Target users and the five jobs

| User | Context | What they need in the first 3 seconds |
|---|---|---|
| **Annotator / labeler** (shift worker, Thai-first) | 6–8 h at a desk, keyboard-heavy, paid per approved image | The next image to label, how many are left, the classes with hotkeys |
| **Reviewer / QA lead** | Owns label quality; approves batches, checks class balance | What is waiting for approval, what the model disagrees with, one action to accept |
| **ML engineer** | Trains, compares, exports, watches metrics | Which dataset version is clean, what to train, whether the last run beat the last |
| **Project manager / operations** | Owns delivery, cost and the customer | Pipeline status at a glance, blockers, cost per run, who is behind |
| **Workspace owner / admin** | Billing, members, compliance | Usage and governance without entering a project |

Top five jobs, in the order the product must serve them:

1. **Get images in and labelled.** Upload → assign → label with hotkeys → submit. Success = approved images per hour.
2. **Review and fix labels.** See disagreements and low-confidence items first, accept or correct, never approve blind.
3. **Freeze a dataset version and train a model.** One default recipe, a cost/time estimate, a run that can be watched.
4. **Understand whether the model is good enough.** Metrics tied to images and slices, with a recommendation that links back to the fix.
5. **Test and ship.** Drop an image or point a camera, see boxes, copy an endpoint, monitor drift.

Everything else (asset library, workflows, universe, audit) is secondary and must not share the
primary rail.

---

## 3. The new information architecture

Two levels, each with a single job. The **workspace** answers "which project?"; the **project**
answers "where am I in the pipeline?".

### 3.1 Chrome

```
┌ Top bar (glass) ────────────────────────────────────────────────────────────────┐
│ [WS switcher ▾]  breadcrumb: Projects / PPE Detection     [⌘K Search]  [Jobs 2]  [◐]  [DS] │
└────────────────────────────────────────────────────────────────────────────────┘
```

- One top bar for both levels. Height 56. The workspace switcher is the only place workspaces change.
- Search is a real command palette (projects, images, versions, runs, pages) — `⌘K`, not a dead input.
- The job tray is an icon with a count, opening a glass panel; long jobs never need a page.
- The theme toggle and the account menu live here, not in the rail.

### 3.2 Workspace rail (only outside a project)

```
Projects                ← home: project cards + "your next step" queue
Models                  ← registry across projects
Deployments             ← live endpoints + streams
Activity
─────────────
Members                 ← governance lives in Settings, one entry
Usage & billing
Settings
```

Six items, no ALL-CAPS group labels, no "Universe", no "Asset library". Anything removed from here is
still reachable from **Settings** and from the command palette, so nothing is lost.

### 3.3 Project rail (the Roboflow pattern, without Roboflow's look)

```
[ PPE Detection ▾ ]                 ← project switcher, shows type icon
Object detection · 24 approved

① Upload                  40   ●   ← done, shows what it holds
② Annotate                16   →   ← active step, live count
③ Dataset  › Versions      1        ← one stage with two tabs, not two links
④ Train                    1        ← last run status
⑤ Deploy                   —        ← not yet

─────────────
Insights                        ← dataset + model analytics
Classes & tags                  ← ontology
Streams                         ← cameras
Project settings
```

Rules:

- **Numbered steps 1–5 follow the work**, in this order and no other. A stage shows its own state
  (done / needs you / blocked / not started) with a dot, a count and one line of text.
- Sub-surfaces of a stage are **tabs inside the stage**, never sibling links: Dataset contains
  *Images · Versions · Health*; Train contains *Runs · Compare*; Deploy contains *Test · API · Streams*.
  This removes "Dataset vs Versions vs Model insights" from the rail.
- The rail shows **only stages the role can act on**, and shows the rest dimmed with a lock and a
  "Request access" tooltip (progressive disclosure, not permanent hiding). A labeler sees
  Upload (read), Annotate, Dataset (read) and Help.
- The current stage owns the primary button in the page header. There is no global "Train Model".

### 3.4 Routes

| New route | Replaces | Notes |
|---|---|---|
| `/:ws` | same | Projects + queue |
| `/:ws/p/:project` | `/:ws/:project/browse` redirect | **Project overview** (new) |
| `/:ws/p/:project/upload` | `/:ws/:project/upload` | |
| `/:ws/p/:project/annotate` | same | board, plus `?image=` deep link |
| `/:ws/p/:project/annotate/:imageId` | `.../images/:id` | editor keeps `status`/`batch`/`review` query |
| `/:ws/p/:project/dataset` + `?tab=versions\|health` | `browse`, `versions`, `insights?tab=health` | legacy URLs redirect |
| `/:ws/p/:project/train` + `?tab=runs\|compare` | `train`, `model-insights` | |
| `/:ws/p/:project/models` | same | |
| `/:ws/p/:project/deploy` + `?tab=api\|streams` | `deploy`, `streams` | Playground folds in as *Test* |
| `/:ws/models`, `/:ws/deployments`, … | same | workspace level unchanged |

Route change is additive: keep the old paths as `<Navigate replace>` so bookmarks and tests survive.
`apps/frontend/tests/nav.test.mjs` and the reserved-segment list need the `/p/` prefix.

---

## 4. Liquid Glass + Material 3 Expressive, without hurting legibility

Rules, in order of precedence:

1. **Content is solid.** Canvas, image grids, tables, charts, code blocks and forms sit on
   `--surface` / `--surface-container`. No blur, no translucency, no gradient behind data.
2. **Chrome is glass.** Top bar, project rail, floating toolbars, dialogs, command palette, job tray,
   toasts, overlay chips. Blur 24 px, saturate 180%, fill 62% light / 66% dark, 1 px inner highlight.
3. **Glass never carries text below 4.5:1.** Every glass surface pairs its tint with a solid text
   colour token; the glass is decoration, the contrast comes from the fill.
4. **Fallback is first-class.** `prefers-reduced-transparency`, the in-app setting, or no
   `backdrop-filter` ⇒ 96% opaque surface, same geometry, same borders. `prefers-reduced-motion` ⇒
   opacity only, ≤120 ms.
5. **One expressive moment per screen.** A tinted hero band, a progress ring, or a gradient edge on the
   active stage — not three. Material 3 Expressive gives colour and shape, not noise.

---

## 5. The ten key screens

Each entry: purpose → layout → what changes and why. Frames are 1440 wide in the FigCraft file.

### S1 · Workspace home
**Purpose:** "what needs me now, in any project".
**Layout:** 64 px page title with one primary action (*New project*); a **Needs you** queue (max 4 rows,
each with project, stage, count and the action); project cards with pipeline progress (5 dots and
numbers: `40 · 16 · 1 · 1 · —`); a slim usage strip; recent activity below the fold.
**Changes:** kills the five KPI cards as the first thing; one "at a glance" instead of two; the queue
uses the shared `TaskRow` component; the tour becomes a dismissible 3-step inline hint inside the
first project card, not a floating modal over real work.
**Why:** action before statistics; one name per concept; the first screen answers a question.

### S2 · Project overview (new)
**Purpose:** the project's cockpit and the entry point every role shares.
**Layout:** header = project name, type, *Open next task* primary button (label is dynamic:
"Label 16 images", "Review 16 labels", "Train on v2", "Test the model"). Below, the **pipeline board**:
five numbered cards left to right (Upload, Annotate, Dataset, Train, Deploy), each with a state chip, a
count, a one-line explanation and a single action. Right column (360): dataset health ring, latest run
with mAP and delta, "blocked by" list, recent activity.
**Changes:** the missing overview; the same five stages as the rail, so the model of the product is
learned once; each card is a shortcut with a reason.
**Why:** Gulf of evaluation closed; the next action is a sentence, not a guess.

### S3 · Upload
**Purpose:** get images in, correctly, once.
**Layout:** one large drop zone (keyboard + browse + folder + camera) with a **batch name** field that
defaults to `YYYY-MM-DD · shift`, split policy as two radio chips (Auto 80/10/10 · Manual later), and a
pre-flight line: "40 images · 3 duplicates will be skipped · 0 too small". After upload: a result sheet
"Added 37 · duplicates 3 · failed 0" with per-file reasons, and one primary *Send to Annotate*.
**Changes:** one primary, explicit dedupe and split, a result you can act on; the empty state explains
the 3 accepted formats and shows the demo dataset button.
**Why:** silent skipping is the #1 support thread in this category; the user must be able to predict
the outcome before spending upload time.

### S4 · Annotate — the queue board
**Purpose:** a labeler starts working in one click; a reviewer sees what is pending.
**Layout:** header with role-aware primary (*Start labelling* / *Review 16*). Three lanes — **To label**,
**In review**, **Approved** — as lists of batch rows (name, images, assignee, age, progress bar) instead
of kanban cards; each row's primary opens the **first image of that batch** in the editor. A right rail
shows "Your throughput today" and the hotkey cheat-sheet link. The board itself is solid surface.
**Changes:** images become the unit inside a batch; "Approve all" requires a confirm sheet that names
the count and the classes involved; bulk approve moves into a selection action bar, not a green button
next to the primary.
**Why:** one click to work; destructive bulk actions lose their prominence.

### S5 · Editor (kept, refined)
**Purpose:** draw, correct, review at speed.
**Layout:** unchanged three-zone frame — left 264 rail (Classes / Objects tabs only; Attributes,
Comments, History, Raw move to a right inspector sheet opened by a button), canvas solid `#0F1115`
behind the image, right 200 thumbnail strip collapsible. Top bar: filename, split chip, review state,
**Next image (→)** and **Approve / Reject**; the assistant actions (Smart Polygon, Label Assist) sit in
a floating glass toolbar bottom-centre, next to zoom. Keyboard legend in the palette, not on screen.
**Changes:** removes four competing tabs; gives the review loop an explicit "next"; moves AI assists
to where the pointer already is; 12 px minimum for metadata.
**Why:** this is the product; every other screen exists to fill it. Protect the canvas, cut the chrome.

### S6 · Dataset (Images · Versions · Health)
**Purpose:** find, filter, fix, freeze.
**Layout:** tab row inside the stage. Images tab: one filter bar (search, status, split, class, quality
as a single *Filters* popover with a count badge), a saved-view chip row ("Needs review", "Missing
negatives", "Test set"), selection bar on demand (n selected → Assign / Auto-label / Export / Delete),
then the grid at 2 columns per 240 px with 13 px captions and class names on hover. Header states
"40 uploaded · 24 approved".
**Changes:** 8 visible controls → 1 + popover; explicit uploaded/approved distinction; bulk actions
appear only with a selection; empty and no-match states differ.
**Why:** Hick's law and error prevention; the grid is the work, not the filter form.

### S7 · Versions
**Purpose:** freeze a reproducible dataset and hand it to training.
**Layout:** left list of versions (name, date, images, approved, delta chip `+6 / −2` vs previous);
right detail: split bar, class counts, recipe summary, "What changed" diff list, and one primary
*Train on this version*. Export moves to a secondary menu with format chips and a direct download.
**Changes:** one primary; diff before download; no Python snippet in the default path (it lives under
"Use from code").
**Why:** a version exists to be trained and audited; the diff is the reason to make a new one.

### S8 · Train
**Purpose:** start a run you can predict.
**Layout:** three numbered blocks in one column (max 720): 1 Version (select with a health chip),
2 Recipe (Fast / Balanced / Accurate segmented control, one line each: epochs, image size, ETA, credits;
Advanced collapses into a details panel with the family/variant grid), 3 Output (name, base weights,
max minutes). A sticky summary card right: "~18 min · 3 credits · RTX 4090" and the primary *Start
training*. After start, the page becomes a run view with live loss curve and a job tray entry.
**Changes:** variants move behind Advanced; ETA, VRAM and cost are visible before the commitment;
licence badges become a single "Licences" link in the summary.
**Why:** people cannot choose between 15 variants; they can choose between three promises.

### S9 · Models & evaluation
**Purpose:** know if it is good enough, and what to fix.
**Layout:** run list left (name, version, mAP, status), detail right: metric tiles (mAP50, mAP50-95,
precision, recall) with delta vs previous run; confusion matrix with a confidence slider that
recomputes live and opens the worst images on click; a **Recommendations** card ("127 images have no
negatives — add 50", "harness recall 41% — 22 images to label") where each line links to a filtered
dataset view. Deploy is the primary; Export and Compare are secondary.
**Changes:** interpretation and next step; matrix becomes interactive; caveats become actions.
**Why:** this is where trust is won or lost; a number without a next step is decoration.

### S10 · Deploy & test
**Purpose:** prove it works on a new image, then ship it.
**Layout:** two panes. Left (fluid): drop zone that accepts drag, paste, camera or "use a sample"; image
with boxes, confidence slider, per-class toggles, latency readout. Right (400): endpoint card with the
full URL wrapped (never clipped) and a copy button, language tabs (cURL / Python / JS), auth note,
"Manage keys" link; below, a Streams mini-list with live status.
**Changes:** test first, API second (the current page leads with code); Playground merges here; the curl
block wraps; sample images remove the cold empty state.
**Why:** the job is "does it see my object", not "read my API".

### Mobile (375) — Home, Project overview, Annotate
- Bottom tab bar (glass): **Projects · Work · Models · More**; 48 px targets, safe-area padding.
- Home: title, the single next task as a full-width card, then project cards stacked.
- Project overview: vertical stepper — five rows, each with state dot, count, one action; the pipeline
  board does not become five horizontal cards.
- Annotate: batch list as full-width rows; editor is explicitly "desktop recommended" with a read-only
  preview and an "Open on desktop" link — a phone cannot draw boxes at 375 px.

---

## 6. Component and token system

### 6.1 Colour

HCT seed **#5B4BE0** ("pigment violet") → Material 3 tones. Roles, not values, in code.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--primary` | #5B4BE0 | #C4BCFF | primary action, active stage |
| `--primary-container` | #E5E0FF | #3A2E9E | tinted hero, selected row |
| `--secondary` | #00696B | #4FD8DA | progress, "in review" |
| `--tertiary` | #8F4A00 | #FFB786 | warnings that are not errors |
| `--success` | #146C43 | #5BD69A | approved, healthy |
| `--danger` | #B3261E | #FFB4AB | destructive, failed |
| `--surface` | #FCFBFF | #131218 | page |
| `--surface-container` | #F4F2FA | #1D1B23 | cards, tables |
| `--outline` | #7A7688 | #918D9E | dividers, inputs |
| `--text` / `--text-muted` | #1B1A21 / #5A5766 | #EDEAF4 / #A9A5B8 | 15.8:1 / 6.4:1 |

Class colours stay **Okabe-Ito** in fixed order, generated beyond 8 with Glasbey, never derived from the
brand seed (`docs/STANDARDS.md` §5). Charts use the same palette plus viridis for heatmaps. Every class
chip carries its name, not only a dot.

Contrast: body 4.5:1 verified per token pair; 3:1 for ≥24 px and for control outlines; glass fills are
tested with the text colour they carry (target ≥7:1 on chrome to survive backdrop variation).

### 6.2 Type — IBM Plex Sans + Anuphan (as standard)

| Role | Size / line | Weight | Notes |
|---|---|---|---|
| Display | 40 / 46 | 600 | only on Home and project overview |
| H1 page | 28 / 34 | 600 | one per screen |
| H2 section | 20 / 26 | 600 | |
| H3 card | 16 / 22 | 600 | |
| Body | 14 / 22 | 400 | UI default |
| Body Thai | 14 / 22.4 | 400 | line-height 1.6 |
| Small | 13 / 18 | 400 | metadata, captions (never 11) |
| Micro | 12 / 16 | 500 | chips, table headers, uppercase tracking 0.02em |
| Mono | 13 / 20 | 400 | code, ids (JetBrains Mono or system mono) |

Numbers use tabular figures in tables and metrics. Thai strings are never truncated with `slice()`; two
lines max, then an explicit "more".

### 6.3 Space, radius, elevation

- Space scale 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64. Page gutter 32 desktop, 16 mobile.
- Radius: 8 chips, 12 inputs and buttons, 16 cards and rows, 24 dialogs and glass bars, 999 pills.
- Elevation is **chromatic, not black**: `0 1px 0 rgba(255,255,255,.7) inset, 0 8px 24px -12px rgba(27,26,33,.24)`.
  No drop shadows on flat cards; only floating chrome and modals get depth.
- Grid: 12 columns, 24 gutter; content max 1440, reading max 720.

### 6.4 Core components (drawn on the Foundations page)

1. `Button` — primary (filled), secondary (tonal), ghost, danger; 36/32/28 heights; icon 16; focus ring 2 px
   offset 2; loading state keeps width.
2. `StageItem` — the numbered rail item: number, label, count, state dot, optional lock.
3. `TaskRow` — project · stage · count · one action; the unit of "needs you".
4. `StageCard` — pipeline card on the overview: number, title, state chip, metric line, action.
5. `Chip` — class, split, status, saved view; 12 px; colour never the only signal.
6. `Field` — label above, hint below, error replaces hint, 36 px; select and combobox share geometry.
7. `FilterBar` — search + one Filters button with active-count badge + saved views.
8. `DataTable` — 40 px header, 44 px rows, sticky header, zebra off, hover `surface-container-high`,
   numeric right-aligned, row action on hover + always in keyboard.
9. `EmptyState` — illustration-free icon, one sentence, one primary, one "why" link.
10. `JobTrayItem` — job name, progress, ETA, cancel; persists across routes.
11. `GlassShell` — top bar/rail/dialog wrappers with the fallback baked in.
12. `Toast` / `InlineAlert` — error, warning, success; never a bare red background.

### 6.5 Motion

Opacity and transform only, 150–300 ms, ease-out for enter, ease-in for exit. The stage dot pulses once
when a count changes. No animation under `prefers-reduced-motion`. Blur never animates.

---

## 7. Empty, loading, error, and long-job states

| State | Rule | Example |
|---|---|---|
| Empty (new project) | Say what this step is for, one primary, one shortcut (demo data) | Dataset: "No images yet — Upload 20 images or start from the 40-image demo set." |
| Empty (filtered) | Distinguish from empty: "No images match these 3 filters" + Clear filters | Dataset filters |
| Loading | Skeleton matching final geometry; no spinner on a page load | Grid: 12 tile skeletons |
| Error | What failed, what survived, retry, and the reference id | Upload: "Added 37, failed 3 — see reasons" |
| Long job | Job tray with % and ETA; the page may continue; never block the route | Training, auto-label, export |
| Permission | Dimmed rail item + lock + "Request access"; never a silent redirect | Train for a labeler |
| Offline / API down | Banner in the top bar, actions disabled with a reason | Global |

---

## 8. Implementation plan

Small tasks, each shippable, ordered by user value. Files are the real ones in this repo.

| # | Task | Files | Done when |
|---|---|---|---|
| T1 | **Tokens v3**: add surface-container, outline, glass roles, type scale, spacing; keep HCT runtime | `apps/frontend/src/index.css`, `apps/frontend/src/lib/theme.ts` | Tokens appear in devtools; no hard-coded hex in components (grep) |
| T2 | **Shell**: single 56 px top bar, workspace switcher, palette trigger, job tray; delete global "Train Model" injection | `components/shell/TopBar.tsx`, `AppLayout.tsx`, `ProjectLayout.tsx` | No `Train Model` outside Train; top bar height constant across routes |
| T3 | **Workspace rail** reduced to 6 items; governance moves under Settings | `lib/nav/workspace/*.ts`, `components/shell/AppSidebar.tsx`, `tests/nav.test.mjs` | Nav test passes with the 6 items; every removed route reachable from Settings |
| T4 | **Project rail** as numbered stages with counts and state; sub-surfaces become tabs | `lib/nav/project/*.ts`, `components/shell/ProjectPanel.tsx`, `lib/nav/registry.ts` | `manifest` of 5 stages + 4 secondary; legacy links redirect |
| T5 | **Project overview** page (S2) with pipeline board and dynamic primary | new `features/project/Overview.tsx`, `routes/project/index.tsx` | `/p/:project` renders; primary label changes by state |
| T6 | **Routes** `/p/` prefix + legacy redirects; update tests | `routes/*.tsx`, `lib/nav/registry.ts`, `tests/nav.test.mjs` | Old URLs land on the new screens; no 404 |
| T7 | **Home** (S1): Needs-you queue first, project cards with stage counts | `features/workspace/Home.tsx`, `Dashboard.tsx` | Queue above KPIs; one "at a glance" |
| T8 | **Upload** (S3): pre-flight estimate, dedupe summary, single primary | `features/project/Upload.tsx`, `features/project/Upload2.tsx` (web/ parity) | Upload 10 files shows 10/dupes/failed; result has next step |
| T9 | **Annotate board** (S4): lanes of batch rows, open first image, bulk confirm | `features/project/AnnotateBoard.tsx` | One click from board to a drawable image; approve-all needs confirm |
| T10 | **Editor** (S5): 2 rail tabs, next-image, assist toolbar, 12 px floor | `features/editor/Editor.tsx`, `Panels.tsx`, `ObjectList.tsx` | Keyboard-only path: open → box → next → approve |
| T11 | **Dataset** (S6): one filter bar + popover, saved views, selection bar, uploaded vs approved | `features/project/Dataset.tsx`, `features/project/HealthCheck.tsx` | Filter bar ≤1 row at 1440; counts consistent with Home |
| T12 | **Versions** (S7): diff, single primary, export menu | `features/project/Versions.tsx` | Diff list renders; Train is the only primary |
| T13 | **Train** (S8): three blocks, presets, ETA/VRAM/credits summary | `features/project/Train.tsx` | Default path is 3 choices; advanced holds families |
| T14 | **Models** (S9): deltas, interactive matrix, recommendations | `features/project/Models.tsx`, `features/insights/EvaluationTab.tsx` | Matrix cell click opens filtered images; every recommendation links |
| T15 | **Deploy** (S10): test-first layout, wrapped endpoint, sample image; fold Playground in | `features/project/Deploy.tsx`, `features/playground/Playground.tsx`, `routes/workspace.routes.tsx` | No clipped URL at 1440; sample works without upload |
| T16 | **Mobile**: bottom tabs, stacked overview, read-only editor notice | `components/shell/AppLayout.tsx`, `features/project/ProjectLayout.tsx`, `index.css` | 375 px: no horizontal scroll on Home/Overview/Annotate |
| T17 | **States + a11y pass**: skeletons, empty/no-match, error sheet, axe zero critical, focus order | `components/ui.tsx`, all above | axe: 0 critical/serious; keyboard path documented |

Order of delivery: T1–T4 (frame), T5–T7 (first value), T9–T10 (core loop), T8/T11–T13 (pipeline),
T14–T15 (trust and ship), T16–T17 (hardening).

Out of scope for v3: new features (connectors, semantic search), backend changes, the `.fig` handoff
back into React.

---

## 9. Risks and non-goals

- **Two UIs in the repo.** `web/` (v2 mock, Vite 5173 in this audit is `apps/frontend`, but `web/`
  still exists with its own shell). The redesign must land in one app; the other is deleted or frozen.
  Confirm with the PM before T2.
- **Role matrix is security-relevant.** The rail hides, the server enforces. No visual-only gating.
- **Numbers must agree across screens.** Uploaded vs approved vs annotated is currently three different
  counts; define one vocabulary in the API types before T11.
- **Glass is a regression risk** on low-contrast projectors and in bright rooms. The fallback is not
  optional; test it with the in-app toggle, not only the OS setting.
- **No Roboflow copy.** Layout patterns (stage rail, version→train handoff, test-first deploy) are
  patterns; text, icons, illustrations, screenshots and brand colours are not reused.

---

## 10. Review of the built frames

Reviewed against `frames/*.png` at 100%: 00 Foundations, 01 Workspace home, 02 Project overview,
03 Upload, 04 Annotate board, 05 Editor, 06 Dataset, 07 Versions, 08 Train, 09 Models, 10 Deploy,
M1/M2/M3 at 375.

### 10.1 Design critique

**Overall impression.** The set now reads as one product with one job: the rail says where you are
in the pipeline, the page header says what to do next, and only one element per screen is loud.
The weakest frame is 09 Models, where the right column still asks the reader to interpret a matrix
before it offers the fix.

| Frame | Finding | Severity | Fix applied / still open |
|---|---|---|---|
| 01 Home | Three "Needs you" actions used three stage colours, so colour no longer meant one thing | 🟡 | Applied: all three are tonal violet; the stage is carried by the row's left bar and the label |
| 01 Home | Rail labels sat at a 48 px indent with no icons, reading as a broken list | 🟢 | Applied: labels align at 28 px; the active row keeps its pill |
| 02 Overview | "What needs you" rows opened with empty 40 px grey squares (icon holes) | 🔴 | Applied: squares removed, rows start on the text |
| 06 Dataset | "Delete / Clear" sat outside the selection bar and the right page edge | 🟡 | Applied: moved inside the bar, Delete before Clear |
| 07 Versions | Split legend overlapped itself ("18% valid 86 imgs22% test") | 🔴 | Applied: one legend line, `train · 60% · 276 imgs` |
| 07 Versions | Lower-left quarter was empty | 🟢 | Applied: "Runs trained on these versions" table, which also answers "what used v1?" |
| 08 Train | The status chip and "Change" sat inside the select field, reading as placeholder text | 🟡 | Applied: chip inside, "Change ▾" outside the field |
| 08 Train | The sparkline fell left to right, so a good run looked like a declining one | 🟡 | Applied: bars ascend; caption stays `epoch 1 → 40` |
| 08 Train | "Last run" bars are epoch indices, not a real loss curve | 🟢 open | Replace with the run's real loss curve once the API exposes it; do not fake a curve |
| 09 Models | Matrix cells above 50 use the primary fill, so the diagonal is loud but the off-diagonal misses are quiet | 🟡 open | Colour the *errors* (off-diagonal) by magnitude instead; the diagonal should be neutral |
| 10 Deploy | Code block lost its indentation and the URL ran into "Copy" | 🟡 | Applied: host-path URL, Copy pinned right; indentation is a code-block style rule for T15 |
| 04 Annotate | Lanes were 660 px tall with two cards, so the board looked empty | 🟡 | Applied: 384 px lanes plus a throughput + shortcuts strip |
| M1/M2/M3 | State chips overlapped the row chevron; "Fix ›" collided with the health sentence | 🔴 | Applied: chips right-aligned at `344 − width`, chevron pinned, text shortened |
| M3 Annotate | "Copy desktop link" overflowed its card | 🟡 | Applied: card height and button move inside |

**What works and should survive refactoring.** The stage rail with numbers and counts (02/05–10);
the dynamic primary button label (02); the "one primary per screen" rule holding across all ten
frames; the editor's three-zone frame with a solid canvas; the explicit upload pre-flight
("40 images · 3 duplicates · 2 under 320 px"); and the test-first Deploy pane.

### 10.2 Accessibility review (WCAG 2.2 AA, from the mock)

Contrast computed with the WCAG formula from the token values; text below 4.5:1 fails.

| Element | Foreground | Background | Ratio | Required | Result |
|---|---|---|---|---|---|
| Body / headings | `#1B1A21` | `#FCFBFF` | 15.9:1 | 4.5 | pass |
| Secondary text | `#5A5766` | `#FCFBFF` | 6.9:1 | 4.5 | pass |
| Micro labels, table headers | `#5A5766` | `#F4F2FA` | 6.4:1 | 4.5 | pass |
| Active stage, chip text | `#3A2E9E` | `#E5E0FF` | 8.6:1 | 4.5 | pass |
| Primary button label | `#FFFFFF` | `#5B4BE0` | 5.4:1 | 4.5 | pass |
| Approved chip | `#146C43` | `#C8F2DC` | 5.2:1 | 4.5 | pass |
| Warning chip | `#8F4A00` | `#FFE2C4` | 5.8:1 | 4.5 | pass |
| Blocked chip | `#B3261E` | `#FFD9D5` | 5.6:1 | 4.5 | pass |
| Canvas chrome on dark | `#A9A5B8` | `#1B1A21` | 6.6:1 | 4.5 | pass |
| Input outline | `#7A7688` | `#FFFFFF` | 4.1:1 | 3.0 (1.4.11) | pass |
| Focus ring | `#5B4BE0` | `#FCFBFF` | 5.9:1 | 3.0 (2.4.11) | pass |

Findings carried into implementation:

| # | Issue | Criterion | Severity | Action |
|---|---|---|---|---|
| 1 | All 11 px `#7A7688` labels were 3.9:1 on `#F4F2FA` | 1.4.3 | 🔴 | Fixed in the file (77 nodes) to `#5A5766`; enforce a 13 px floor and the darker token in T1 |
| 2 | Controls in the mock are 32–36 px tall | 2.5.5 / 2.5.8 | 🟡 | Keep 32 px visual height but a 44 px hit area (`::before` inset) on table row actions and rail items |
| 3 | Status is colour + text in most places, but the stage dot alone encodes state in the rail | 1.4.1 | 🟡 | The dot must ship with the count and the state word in `aria-label`, never alone |
| 4 | Glass chrome has no fallback in the mock | 1.4.3 / contrast over backdrop | 🔴 | `prefers-reduced-transparency`, the in-app toggle and no-`backdrop-filter` all resolve to a 96% surface; text sits on the solid fill, never on the blur |
| 5 | Charts (10 Deploy, 08 Train) rely on height only | 1.4.1 | 🟢 | Bars get an accessible name and a summary sentence; no colour-only series |
| 6 | Matrix cells are colour + number | 1.4.1 | 🟢 | Pass, but the numbers must be in the DOM as a table, not drawn text |
| 7 | Keyboard path is drawn (B / Enter / A) but unverified in code | 2.1.1 | 🟡 | T10 acceptance: open → draw → next → approve with no pointer |

Not verifiable in FigCraft: real focus order, screen-reader names, zoom to 200%, `forced-colors`.
Those belong to T17 and must be tested in the app, not inferred from the mock.

### 10.3 Design handoff notes

**Tokens.** Use the REDESIGN §6 table as the source. Suggested names in `index.css`:
`--surface`, `--surface-container`, `--surface-container-high`, `--outline`, `--text`, `--text-muted`,
`--primary`, `--on-primary`, `--primary-container`, `--on-primary-container`, `--success`, `--warning`,
`--danger` plus `-bg` variants, `--glass-fill` (62% / 66%), `--glass-blur` (24 px), `--radius-{8,12,16,24}`,
`--space-{4…64}`. Class colours stay Okabe-Ito in fixed order and always ship with the class name.

**Geometry.** Top bar 56; workspace rail 232; project rail 232; content gutter 32 (16 at ≤768);
page title 28/34 with a 124 px header block; cards radius 16, inputs 12, chips 999; card padding 20;
list row 62–68.

**Components.** `Button` (primary / tonal / ghost / danger; 36·32·28; loading keeps width),
`StageItem` (number, label, count, state, optional lock), `StageCard`, `TaskRow`, `Chip`, `Field`,
`FilterBar`, `DataTable` (40 header / 44 rows, numeric right), `EmptyState`, `JobTrayItem`, `GlassShell`,
`Toast` / `InlineAlert`. Every one ships all eight states; the mock shows default, selected, loading and
disabled only.

**States and edge cases.** Empty vs no-match must differ in copy and in the action offered.
Long job = job tray + non-blocking route. Error sheet names what survived and what did not.
Permission = dimmed rail item with a lock and "Request access", never a silent redirect.
Numbers: uploaded, approved, annotated, in review must come from one API vocabulary (risk R3).

**Responsive.** 1440 is the design width. At 1024 the right column of 02/09 drops below; at 768 the
rail collapses to icons plus a slide-over; at 375 the bottom tabs replace the rail and the editor
becomes read-only with a "Copy desktop link" handoff, exactly as M3 draws it.

**Motion.** 150–300 ms, opacity and transform only, ease-out in and ease-in out. The stage dot pulses
once when a count changes. Nothing moves under `prefers-reduced-motion`; blur never animates.

**What is deliberately not in the mock.** Live blur, real icon glyphs, Thai strings (the canvas cannot
shape Thai script), and the loss curve. Those are code concerns; do not read the mock as a pixel
contract for them.

---

## 11. v3b extension — parity coverage (17 Nov 2026)

Second design-lane pass. It fixes the PM review of `frames/05-editor.png` and extends the system to the Must and
Should gaps in `docs/research/roboflow-parity/PARITY.md`. The file now has eight pages: **Foundations**,
**Screens** (ten core screens plus three 375 variants) and one page per PARITY area — 1 Workspace & projects,
2 Upload & data, 3 Annotate, 4 Versions & export, 5 Train & models, 6 Deploy & workflows, 7 Admin & billing,
8 States & 375. Every frame is exported to `frames/<slug>.png` at 1440 × 900 (or 375 × 812).

### 11.1 The editor fix (05-editor)

| PM finding | What changed | PARITY |
|---|---|---|
| Boxes sat outside the photo | The image is 1477 × 1108 (4:3), so a 828-wide frame letterboxed it to 621 px. The image layer now matches the photo box exactly (621 × 466 at x 440) and all six boxes, plus a second person, are re-anchored on the objects. The meta line reads `1477 × 1108`, not `1280 × 720`. | 3-F3.9, 3-F3.13 |
| No tool palette | Floating 48 px glass rail on the canvas: select `V`, box `B`, polygon `P`, smart polygon `S`, brush `M`, keypoint `K`. The active tool gets a primary-container chip and every button carries its shortcut letter, so none is icon-only. | 3-F3.8–3-F3.11, 3-F3.13 |
| No undo/redo | Two 30 px ghost buttons in the header, left of the status chip; redo looks disabled when the stack is empty. | 3-F3.19 |
| No class-attribute control | `ATTRIBUTES` block in the rail: occluded / truncated / difficult / crowd toggles plus `+ Add`; the per-class definitions live on the Classes page (A3-04). | 3-F3.38 |
| No negative-image control | `THIS IMAGE → Nothing here` switch with the rule printed under it: it counts as an intentional negative and exports an empty label file. | 3-F3.18 |

Checked for the same class of error elsewhere: image fills now sit inside their frames, no label chip is drawn
off-canvas, and factual copy (dimensions, counts, credit maths) matches the asset or the seeded data.

### 11.2 Frame index → PARITY ids

| Page | Frame (PNG slug) | Covers |
|---|---|---|
| Screens | `01-workspace-home` … `10-deploy-test`, `m1`–`m3` | 1-F6.1, 2-F2.1, 3-F3.1, 4-F4.1, 5-F5.1, 6-F6.9, 6-F6.11 |
| 1 | `a1-01-first-run-three-setup-questions` | 1-F1.1, 1-F1.2, 1-F1.3, 1-F6.2, 1-F6.3 |
| 1 | `a1-02-projects-folders-drag-multi-select` | 1-F4.1, 1-F3.4, 1-F2.4 |
| 1 | `a1-03-project-about-publish-licence-and-pii-gate` | 1-F3.1, 1-F5.1, 7-F7.53 |
| 1 | `a1-04-public-dataset-page-visitor-fork-errors` | 1-F5.2, 1-F5.3, 2-F2.20, 7-F7.54, 7-F7.55 |
| 1 | `a1-05-assistant-tasks-re-runnable-tour` | 1-F1.3, 1-F1.4 |
| 2 | `a2-01-upload-files-camera-url-pre-labelled-batch` | 2-F2.2, 2-F2.4, 2-F2.5, 2-F2.6, 2-F2.7 |
| 2 | `a2-02-import-labels-formats-class-mapping-metadata-sidecars` | 2-F2.3, 2-F2.18, 2-F2.32, 4-F4.37 |
| 2 | `a2-03-asset-library-cross-project-search-and-reuse` | 1-F4.2, 2-F2.25, 2-F2.28, 2-F2.29, 2-F2.30 |
| 2 | `a2-04-images-query-bar-negation-saved-views-share-link` | 1-F4.3, 2-F2.26, 2-F2.27 |
| 2 | `a2-05-duplicates-dataset-health-phash-clusters-heat-map` | 2-F2.35, 2-F2.36, 2-F2.37, 4-F4.39, 4-F4.42, 4-F4.43 |
| 3 | `05-editor` (rebuilt in place) | 3-F3.8–3-F3.11, 3-F3.18, 3-F3.19, 3-F3.38 |
| 3 | `a3-01-editor-polygon-vertices-brush-mask-convert-merge` | 3-F3.2, 3-F3.8, 3-F3.10, 3-F3.11, 3-F3.20 |
| 3 | `a3-02-auto-label-per-class-prompts-policy-cost-estimate` | 3-F3.26–3-F3.32, 3-F3.54 |
| 3 | `a3-03-review-reject-reasons-batch-approve-assignment-history` | 3-F3.45, 3-F3.46, 3-F3.49, 3-F3.52 |
| 3 | `a3-04-skeleton-keypoints-per-class-attributes` | 3-F3.13, 3-F3.14, 3-F3.36, 3-F3.38, 3-F3.40 |
| 4 | `a4-01-versions-index-recipe-summary-copy-a-recipe` | 4-F4.3–4-F4.7, 4-F4.16, 4-F4.45, 4-F4.46 |
| 4 | `a4-02-version-wizard-preview-resize-modes-tag-filter-class-remap` | 4-F4.13, 4-F4.18, 4-F4.20, 4-F4.23, 4-F4.24, 4-F4.26, 4-F4.30, 4-F4.33 |
| 4 | `a4-03-export-every-format-snippet-bucket-target` | 4-F4.34–4-F4.38 |
| 5 | `a5-01-train-families-checkpoint-warnings-cost` | 5-F5.6–5-F5.11, 5-F5.17, 5-F5.19, 5-F5.40–5-F5.42, 5-F5.46, 5-F5.51 |
| 5 | `a5-02-models-evaluation-weights-upload-per-task-metrics-latency` | 5-F5.1, 5-F5.4, 5-F5.21, 5-F5.22, 5-F5.26, 5-F5.28, 5-F5.29, 5-F5.31, 5-F5.33, 5-F5.53 |
| 6 | `a6-01-deploy-hub-runtime-chooser-snippets-self-hosted` | 6-F6.1, 6-F6.2, 6-F6.5, 6-F6.6, 6-F6.8, 6-F6.12, 6-F6.13 |
| 6 | `a6-02-workflow-canvas-ports-branch-disabled-node-cache` | 6-F6.21, 6-F6.22, 6-F6.24, 6-F6.25, 6-F6.29, 6-F6.30 |
| 6 | `a6-03-workflow-test-still-video-camera-publish-and-endpoint` | 6-F6.10, 6-F6.23, 6-F6.26–6-F6.28, 6-F6.32, 6-F6.33 |
| 7 | `a7-01-billing-plans-seats-add-ons-80-notices` | 7-F7.12, 7-F7.13, 7-F7.18, 7-F7.20–7-F7.24 |
| 7 | `a7-02-members-roles-invites-sso` | 1-F5.4, 7-F7.1–7-F7.10, 7-F7.35, 7-F7.60 |
| 7 | `a7-03-api-keys-four-strengths-roll-with-dependency-check` | 1-F1.5, 6-F6.13, 7-F7.25–7-F7.33 |
| 7 | `a7-04-data-protection-licensing-region-deletion-trash` | 1-F5.6, 2-F2.45, 4-F4.5, 5-F5.37, 7-F7.43–7-F7.45, 7-F7.59 |
| 8 | `s-01-empty-loading-error-and-offline-states` | 1-F6.2, 3-F3.53, 3-F3.55 |
| 8 | `m-01-editor-375`, `m-02-review-375`, `m-03-deploy-375` | 3-F3.1, 3-F3.46, 6-F6.1 |

### 11.3 Handoff notes per new screen

Tokens are the Foundations page's: primary `#5B4BE0`, primary container `#E5E0FF`, secondary `#00696B`,
tertiary `#8F4A00`, success `#146C43`, danger `#B3261E`, surface `#FCFBFF`, container `#F4F2FA`, high
`#ECE9F5`, hairline `#E7E2F1`, text `#1B1A21`, muted `#5A5766`. Class colours stay Okabe-Ito. Chrome is the
only glass surface (`#FFFFFFF0` at 66–95%); canvas, tables and charts stay solid.

| Screen | Components | States shown | Copy rule |
|---|---|---|---|
| A1-01 First run | Plan radio cards, chip rows, inline slug preview, demo-set card | plan selected, 3 answered questions, disabled create until Q1 | Questions are outcome-worded ("What will you label?"), not field labels |
| A1-02 Projects | Folder cards, drop target, table with multi-select, floating bulk bar, drag pill | 2 selected, active drop target, 7 rows | Next step is a verb + count ("Review 16") |
| A1-03 Project about | Description textarea, segmented visibility, licence select, checklist, modal with PII banner | modal open, unchecked consent, 12 flagged images | Irreversible consequence is named before the button |
| A1-04 Public dataset | Hero band, badge chips, class chips, split bar, version row, fork card with error legend | 402 state (quota), fork error codes 402/403/404/409/422 | "Copy to my workspace", never "Fork" |
| A1-05 Assistant | Coach mark with progress dots, task cards with progress, ask box, replay link | tour step 1 of 4, 2 running tasks | Assistant answers cite the screen they used |
| A2-01 Upload | Drop zone, source buttons, pre-labelled switch, conflict checkbox, recent-upload table | duplicate skip, orphan-label warning, running 68% | Refusals are itemised, not counted |
| A2-02 Import | Format grid, class-mapping rows, sidecar table, dry-run | 12 formats, 4 renames, 1 merge | "Nothing is renamed until you press Import" |
| A2-03 Asset library | Query field, saved views, filter rail, selection grid, sticky bar | 3 selected across 2 projects | "Search once, copy into the project you are in" |
| A2-04 Images | Chip query bar with negation and counts, saved-view popover, share URL | 128 of 1,284 match, selection survives paging | URL is the query |
| A2-05 Health | Decision cards, split bars, heat-map grid, histogram | 36 duplicate pairs, 12 unlabelled, thin test class | Every chart is a filter |
| A3-01 Editor (polygon/mask) | Tool rail, vertex handles, brush bar with size + feather, convert/merge actions | 2 objects selected, 1 polygon + 1 mask, autosaved | Tools carry letters, not icons alone |
| A3-02 Auto-label | Source radios with readiness, per-class prompt rows, confidence per class, cost block, policy radios, preview strip | 2 classes without prompts, over-quota warning | Estimate and policy sit next to the Run button |
| A3-03 Review | Shortcut bar, queue rows with diff chips, reject reasons, assignment with instructions, history | 3 selected, low-confidence flag, revertable entries | Reject always asks why |
| A3-04 Classes | Skeleton canvas with joints and edges, keypoint-state legend, class table with locks, attribute table | locked classes, 3 keypoint states | Attributes are per class and become export columns |
| A4-01 Versions | Version rows with recipe line, copy-recipe action, diff card, warning | latest marked, 3 classes missing from test | Recipe is visible before training |
| A4-02 Wizard | Step strip, preprocessing rows, resize-mode chips, before/after preview, tag require/exclude, class remap, augmentation grid, estimate | fit-pad selected, 2 tags, 1 rename | Show the transformed image before generating |
| A4-03 Export | Format grid with unavailability reasons, snippet tabs, bucket form, round-trip warnings | COCO selected, 4 formats disabled, bucket transfer | Unavailable formats say why |
| A5-01 Train | Family cards, size chips, checkpoint select, pre-train warnings, cost/time card, live log, stop/cancel note | 3 empty test classes, cap 60 min, queued behind 1 run | Cost is credits and minutes, both |
| A5-02 Models | Model table with latency, metric grid per task, threshold with "save as default", upload card, edge-state list | production alias, uploaded model, eval failed | Threshold saves to the served default |
| A6-01 Deploy | Runtime cards (5), runtime tabs, snippet block, test image with threshold, self-host block, error-code list | hosted selected, 402/413/429 documented | One chooser separates real-time from batch |
| A6-02 Canvas | Typed ports, branch, disabled node, cache badge, config panel with required first, sinks warning | draft, 1 disabled block, sinks off | A test cannot write to the dataset |
| A6-03 Workflow test | Input tabs (still/video/camera), outputs list, publish card, version history | draft vs live v4, sinks writing 0 | Publish is separate from save |
| A7-01 Billing | Plan cards, seat list, add-on toggles, invoice rows, cancel note | 100% credits, upgrade path | Spend warnings at 80% and 100% |
| A7-02 Members | Roster with seats, bulk invite, role matrix, SSO card with DNS proof, policy switches | pending invite, SSO verified, 4 policies | Default role is named, not implied |
| A7-03 Keys | Key table with state badges, four-strength actions, roll with dependency checklist, scopes | active/disabled/publishable, rotation due | Revoke is the only irreversible action |
| A7-04 Data protection | Licensing radios, retention, danger zone with type-to-confirm, trash table | type-to-confirm, 4 trash rows with days left | Deletion states what survives and for how long |
| S-01 States | 12 cells: empty / loading / error per surface | skeleton, spinner, error with recovery | Same voice in all four states |
| M-01–M-03 | 375 layouts: editor with bottom tool sheet, review list with batch bar, deploy with runtime list | thumb-reach primary, 44 px targets | One primary action per screen |

**Known gaps in this pass.** No frame for Area 2 datasource connectors/mirror sync (2-F2.15–2-F2.19, 2-F2.31,
2-F2.33, 2-F2.41); no usage/attribution or audit-log frame (7-F7.14, 7-F7.16, 7-F7.17, 7-F7.38, 7-F7.39);
no streams/monitoring or edge-fleet frame (6-F6.14, 6-F6.16–6-F6.18, 6-F6.41, 6-F6.44, 6-F6.46); no video
timeline or multimodal frame (3-F3.15, 3-F3.17); mobile covers three flows, not all. `docs/research/beyond-roboflow/BEYOND.md`
does not exist in the tree, so nothing from it is designed. The Areas 4–7 frames were laid out from code
geometry and spot-checked as PNGs; the ones checked by eye are A1-01…A1-05, A2-01…A2-05, A3-01…A3-04,
A4-01/A4-02, A5-01 (text only), A6-01, A6-02 (after fix), A7-01, S-01 and M-01.

## 12. v3c extension — contrast, the remaining PARITY areas, BEYOND.md, Thai and mobile (17 Nov 2026)

Third pass. It closes the gaps the v3b report named, fixes the contrast token system-wide, and designs the
Must and Should cards in `docs/research/beyond-roboflow/BEYOND.md`. The file now has **18 pages**: Foundations,
Screens, one page per PARITY area (1–12), and six new pages — **13 Train ops & model governance**,
**14 Foundation-model labeling**, **15 Trust, privacy & Thai billing**, **16 Thai operator screens**,
**17 Mobile 375 — every flow**, **18 States for the new surfaces**. Every frame is exported to
`frames/<slug>.png` at 1440 × 900, or 375 × 812 for mobile. There are **106 PNGs**.

### 12.1 The contrast fix

`#7A7688` at 11–12 px was 4.3 : 1 on `#FCFBFF`, below WCAG AA. The token is now **`#5A5766`** (6.8 : 1 on the
surface, 6.4 : 1 on `#F4F2FA`), and it is the only muted-text token on every page: 2,566 text layers carry it.
The last two `#7A7688` fills (a Foundations swatch and a status dot) were repainted, so the old value no longer
exists in the document.

While sweeping, three other sets failed for the same reason and were fixed: `#8C8798` placeholder and count text
(3.4 : 1), `#A9A5B8` autosave and zoom text (2.3 : 1), `#B3AEC0` icon glyphs (2.1 : 1) — 57 layers, all now
`#5A5766`. The documented *disabled* sample on Foundations stays light on purpose: disabled text is exempt
(WCAG 1.4.3) and it must look disabled. Code blocks keep their tinted-on-dark pairs; those were verified as
pairs, not as text on the page background.

Rule for handoff: `--color-text-muted: #5A5766`. No 11–12 px text may be lighter than that on a light surface.
Status colours keep their own `-fg` tokens (`#146C43`, `#8A5A00`, `#B3261E`) rather than borrowing the muted one.

### 12.2 Thai typography

Thai text is set in **Noto Sans Thai** (present in the app); Latin and digits stay in Inter. An earlier frame
set Thai in Inter, which has no Thai glyphs: the fallback broke vowel placement and rendered `ล็อต` as `ลองต์`
and `กะ` as `n`. The rule: any string containing U+0E00–U+0E7F uses `Noto Sans Thai`, line-height 1.6 for 12–13 px
(Thai stacks above and below the baseline), and is never truncated to fit — labels widen or wrap.

### 12.3 Frame index → PARITY and BEYOND ids

**Area 9 — data sources and audit** (`9 · Data sources & audit`)

| Frame (PNG slug) | Covers |
|---|---|
| `a9-01-datasources-credential-endpoint-path-style` | 2-F2.15, 2-F2.16, 2-F2.17, 7-F7.25 |
| `a9-02-mirror-destination-globs-orphan-policy-runs` | 2-F2.18, 2-F2.19, 2-F2.31, 2-F2.33 |
| `a9-03-tags-batches-metadata-merge-sidecars-rebalance` | 2-F2.32, 2-F2.34, 2-F2.41 |
| `a9-04-usage-attribution-ledger-forecast` | 7-F7.14, 7-F7.16, 7-F7.17, G5.17 |
| `a9-05-audit-log-filters-before-after-diff` | 7-F7.38, 7-F7.39, G5.5, G5.6 |

**Area 10 — streams, edge and line** (`10 · Streams, edge & line`)

| Frame | Covers |
|---|---|
| `a10-01-plant-line-station-camera-hierarchy` | 6-F6.14, G3.2 |
| `a10-02-add-camera-onvif-discovery-readiness` | 6-F6.16, G3.1, G3.16 |
| `a10-03-stream-detail-live-recovery-store-forward` | 6-F6.17, G3.6, G3.7 |
| `a10-04-alert-rules-schedule-owner-snooze-digest` | 6-F6.41, G3.4, G3.5 |
| `a10-05-line-alerts-evidence-acknowledgement` | 6-F6.44, G6.7 |
| `a10-06-station-inspection-lot-verdict-reason-codes` | G3.3, G3.12, G3.14, G6.1 |
| `a10-07-plc-reject-signal-edge-fleet` | 6-F6.46, G3.11, G3.17 |
| `a10-08-first-pass-yield-defect-pareto-handover` | G3.15, G6.2, G6.4 |
| `a10-09-production-review-verdict-taxonomy-evidence` | 6-F6.41, G3.17 |
| `a10-10-station-thai-operator-glove-first` | G5.22, G6.5 |

**Area 11 — video and multimodal** (`11 · Video & multimodal`)

| Frame | Covers |
|---|---|
| `a11-01-video-timeline-tracks-keyframes-split-merge` | 3-F3.15, 3-F3.17, G1.9 |
| `a11-02-video-autolabel-multimodal-prefix-tags` | 3-F3.34, G4.6, G4.7, G4.12 |

**Area 12 — label operations and quality** (`12 · Label ops & quality`)

| Frame | Covers |
|---|---|
| `a12-01-labeling-queue-priority-cap-speed` | G1.5, G1.16 |
| `a12-02-label-quality-agreement-confusion-thresholds` | G1.1, G1.4, G1.17 |
| `a12-03-review-answer-key-score-capped-retries` | G1.2, G1.3, G1.10 |

**Area 13 — training ops and model governance** (`13 · Train ops & model governance`)

| Frame | Covers |
|---|---|
| `b1-run-ledger-config-columns-sweep` | G2.1, G2.2, G2.3 |
| `b2-lineage-model-card` | G2.5, G2.6 |
| `b3-evaluation-slices-leakage-coverage` | G2.7, G2.8, G2.9 |
| `b4-promotion-benchmark-retry` | G2.4, G2.11, G2.14, G3.10 |
| `b5-training-queue-hosts-report` | G2.12, G2.13, G2.15, G2.16 |

**Area 14 — foundation-model labeling** (`14 · Foundation-model labeling`)

| Frame | Covers |
|---|---|
| `c1-autolabel-confidence-bands-prompt-pack` | G4.1, G4.3 |
| `c2-vlm-second-pass-flag-judge-rubric` | G4.4, G4.5, G4.16 |
| `c3-image-map-clusters-coverage-active-learning` | G4.8, G4.9, G4.10 |
| `c4-disagreement-queue-student-gate` | G4.13, G4.14 |
| `c5-ask-dataset-agent-plan` | G4.17, G4.18 |

**Area 15 — trust, privacy and Thai billing** (`15 · Trust, privacy & Thai billing`)

| Frame | Covers |
|---|---|
| `d1-ownership-transfer-offboarding` | G5.4 |
| `d2-dsar-workbench-processing-register` | G5.9, G5.10, G5.11 |
| `d3-thai-tax-invoice-promptpay-po-dunning` | G5.16, G5.22 |
| `d4-retention-legal-hold-breach-clock` | G5.7, G5.13 |
| `d5-trust-centre-status-sla` | G5.12, G5.18, G5.19 |
| `d6-access-policy-help` | G5.3, G5.20 |
| `d7-vertical-starter-packs` | G6.6 |
| `d8-offline-capture-evidence-redaction` | G6.14, G6.15, G6.16 |
| `d9-air-gapped-install-offline-licence` | G6.20 |

**Area 16 — Thai operator screens** (`16 · Thai operator screens`)

| Frame | Covers |
|---|---|
| `e1-editor-thai` | G5.22, 3-F3.8, 3-F3.18, 3-F3.38 |
| `e2-labeling-queue-thai` | G5.22, G1.5, G1.16 |
| `e3-line-alerts-thai` | G5.22, G6.7 |

**Area 17 — mobile, every flow** (`17 · Mobile 375 — every flow`)

| Frame | Flow |
|---|---|
| `m-04-home-375` | Workspace home — continue labeling, three counts, project list |
| `m-05-projects-375` | Projects and folders |
| `m-06-upload-375` | Upload — files, camera, queue with a held file |
| `m-07-images-375` | Images — query bar, filter chips, grid, multi-select bar |
| `m-08-queue-375` | Labeling queue — stages, priority, cap |
| `m-09-versions-export-375` | Versions and export |
| `m-10-train-375` | Train — family, parameters, thin-class warning, cost |
| `m-11-models-375` | Models and the promotion gate |
| `m-12-streams-plant-375` | Streams — plant → line → camera, offline camera |
| `m-13-station-thai-375` | Station (Thai, glove-first) — three 60 px verdict buttons |
| `m-14-alerts-ack-375` | Alerts — P1 with acknowledge and assign |
| `m-15-billing-375` | Usage and the Thai invoice |
| `m-16-audit-375` | Audit log — filters, four event rows |

These join the earlier `m-01-editor-375`, `m-02-review-375`, `m-03-deploy-375`: 16 flows at 375 px.

**Area 18 — states** (`18 · States for the new surfaces`)

| Frame | Screens × 3 states |
|---|---|
| `s-02-states-data-mirror-audit` | Data sources, mirror, audit log |
| `s-03-states-streams-station-alerts` | Streams, station, alerts |
| `s-04-states-queue-quality-review` | Labeling queue, label quality, review |
| `s-05-states-runs-map-video` | Training runs, image map, video |

Each cell names the state, what happened, and the one action that recovers. Loading cells use skeleton rows,
never a spinner, and error cells are never red-only: the chip, the border and the copy all say "error".

### 12.4 Handoff notes per new screen

Tokens are the Foundations page's, unchanged: primary `#5B4BE0`, primary container `#E5E0FF`, secondary
`#00696B`, tertiary `#8F4A00`, success `#146C43`, danger `#B3261E`, surface `#FCFBFF`, container `#F4F2FA`,
hairline `#E7E2F1`, text `#1B1A21`, **muted `#5A5766`**. Radius: cards 14, inputs and buttons 10, chips 999.
Glass stays on chrome only; tables, charts and canvases are solid.

| Screen | Components | States shown | Copy rule |
|---|---|---|---|
| A9-01 Data sources | Credential cards, connector table with state chips, connection test with a 200/403 result | healthy, 403 · key, draft, paused | A red row names what failed and the one action |
| A9-02 Mirror | Destination form, glob editor with match count, orphan policy radios, run log | running, skipped by glob, orphan kept | "Mirror copies, it never deletes the source" |
| A9-03 Tags & batches | Batch merge, sidecar mapping, rebalance policy | 3 merges, 1 conflict | Conflicts are listed, not counted |
| A9-04 Usage | Attribution by key, ledger table, forecast band | 80% of quota, one key over | Credits and money, both |
| A9-05 Audit | Filter bar, saved view, before/after diff, tamper-evident card | diff open, export, hash chain intact | The diff is the row, not a second page |
| A10-01 Hierarchy | Tree (plant → line → station → camera), status dots, counts | 3 lines, 1 station empty | Mirror the physical layout |
| A10-02 Add camera | ONVIF discovery list, profile choice, readiness probe | discovered, probing, low light | A camera is ready only after a probe |
| A10-03 Stream detail | Live tile, recovery ladder, store-and-forward spool | live, reconnecting, spooled 42 | Offline is a state, not an error |
| A10-04 Alert rules | Schedule window, owner picker, snooze, digest, silence | in-window, snoozed, silenced | A rule names an owner before it can fire |
| A10-05 LINE alerts | LINE message preview, acknowledgement ladder, delivery log | ack in 41 s, escalated at 15 min, 1 delivery failed | The ladder names a person at each rung |
| A10-06 Station | Lot card, three verdict buttons, reason chips, barcode, measurement band | pass, fail, rework, no barcode | One press per verdict; reason only on fail |
| A10-07 PLC reject | Signal profile, approval gate, edge fleet table | approved, dry-run, 3 edges online | A machine signal needs a named approver |
| A10-08 Yield | FPY stat + sparkline, Pareto bars, shift table, handover log | 96.2% vs target 95, 2 escaped | Every chart is a filter |
| A10-09 Production review | Verdict taxonomy, reviewer lock, event envelope, evidence | locked by 1 reviewer, envelope valid | Taxonomy before free text |
| A10-10 Thai station | Thai chrome, big verdict buttons, reason chips | idle, scanned, measuring | Glove-first: 60 px targets, no hover |
| B1 Run ledger | Sortable table with config columns, sweep panel, retry | done, failed, sweep best | Configuration is a column |
| B2 Lineage | Node chain, selected node, re-run, model card | 5 nodes, 1 selected | Re-run rebuilds the snapshot |
| B3 Evaluation | Slice table, image strip, leakage audit, coverage bars | slice open, 0.4% overlap, 2 gaps | A slice opens its images |
| B4 Promotion | Request form, approver rows, checklist, benchmark table, failed run | waiting on benchmark, OOM retry | Two approvers, one alias |
| B5 Queue & hosts | Queue table, pool cards, host telemetry, run report | running, queued, held | Telemetry is per run |
| C1 Auto-label policy | Band bar, thresholds, per-class prompt table, cost summary | 7% accept, 1 class without a prompt | A prompt is a definition, not a paragraph |
| C2 Second pass | Photo with a flagged box, rubric table, weighted score, accept/keep | flag, weak, fail, accepted | Flag, never delete |
| C3 Image map | Cluster cards, dots, lasso, AL budget, coverage targets | 5 clusters, 84 selected, 3 gaps | Targets have numbers and ticks |
| C4 Disagreement | Pair table with vote chips, student gate, vote rules | tie, escalate, 0.93 vs 0.95 | A tie goes to a human |
| C5 Ask the dataset | Query field, parsed chips, result grid, answer card, agent plan | 84 results, plan trialled, below gate | The answer never replaces the filter |
| D1 Ownership | Transfer form, consent check, offboarding checklist, history | requested, cool-off 5 days | A handover with a witness |
| D2 DSAR | Case card with deadline, data map, register, sub-processors | 19 days left, 14 rows to erase | Erase is a count and a certificate |
| D3 Thai invoice | Invoice preview, PromptPay QR, payment methods, PO, dunning | unpaid, PO net 30 | 7% VAT and a PO are the invoice |
| D4 Retention | Policy table with dry-run counts, legal hold, breach clock | dry run 21,246, hold active, 52 h left | Deleted is a number, a date, a signatory |
| D5 Trust centre | Public page preview, status components, SLA credit | 99.94%, 1 degraded, no claim | Every incident links |
| D6 Access policy | Policy rows, help search, what's new, sign-in summary | MFA enforced, 2 ranges | Policy is visible at sign-in |
| D7 Starter packs | Three pack cards with class chips and state, install diff | installed, installable, needs calibration | A pack is a starting point with a name |
| D8 Field capture | Offline session, storage meter, redaction list, evidence builder | offline 38 min, 42 queued | The device is a buffer |
| D9 Air-gapped | Install steps with verification, licence file, update channel | 5 steps, licence valid to 2027 | No outbound call |
| E1 Thai editor | Thai chrome, canvas, tool rail with letters, class and attribute rail | 3 boxes, 1 selected, autosaved | Tools carry letters, not icons alone |
| E2 Thai queue | Stage tabs, priority list, cap card, queue table, labeler row | 96 of 120, 1 capped | A queue without a cap burns people |
| E3 Thai LINE | LINE card, ack buttons, ladder, delivery log, escalation | acked in 41 s, escalated at 15 min | Every ack has a name and a time |
| M-04…M-16 | One 375 layout per flow: header, content, bottom tab bar, one primary action | selected, offline, capped, P1 | 44 px targets, one action per screen |
| S-02…S-05 | 3 × 3 state cells per group: empty, loading, error | skeleton, recovery action | Error says what happened and what to press |

### 12.5 What is still not designed

Named honestly, all Should/Could except where noted:

- G1.6 labeling stage graph (Should, L): the queue shows stages, but there is no node editor for human → model → consensus.
- G3.8 device-bound engine registry with golden replay (Should): B4 benchmarks a device, but no registry of TRT/CUDA profiles per edge.
- G3.9 training that knows its deployment target (Should): B4 shows the target at promotion, not at train time.
- G6.8 daily safety summary PDF (Should): the yield page exports a shift report, not the inspector's daily pack.
- G3.13 OCR/OCV comparison against an expected value (Should): A10-06 reads a barcode and measures in mm, but no
  frame compares read text with a master value and lists exceptions.
- Could cards with no frame: G1.11, G1.12, G1.13, G2.10 (HAVE), G2.17, G3.18, G4.11, G4.15, G5.8, G5.21, G5.24, G6.10, G6.11, G6.12, G6.13, G6.22.

PARITY rows: every row the v3b report listed as an open design gap now has a frame. The rest of the 334 rows are
HAVE rows that already ship, or API/SDK/backend depth with no design delta; they are not counted as covered.
