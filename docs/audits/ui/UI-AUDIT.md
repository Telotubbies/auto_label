# LabelDesk UI audit — impeccable pass, 2026-11-17

Independent audit lane. Read-only on code and on `design/labeldesk-v3/`. Everything here was measured on
the running app or read off a frame; nothing was changed to make a finding go away.

**Owner directive.** "impeccable check all design, no AI design, no slop." The visual standard is the
shipped Liquid Glass system (`design/labeldesk-v3/VISUAL-OVERRIDE.md`, `apps/frontend/src/index.css`,
`apps/frontend/src/components/glass.tsx`). The v3 frames decide layout, IA, flow, states and copy, not
the visual style.

**Surfaces audited**
1. The running app at `http://localhost:5173`, signed in as `demo@labeldesk.dev`, workspace
   `labeldesk-demo`, project `ppe-detection` (40 images, 1 model, 1 version).
2. Every PNG in `design/labeldesk-v3/frames/` (116 files).

**How it was measured**
- `docs/audits/ui/tools/shoot.py` drives Playwright over 27 routes × 4 passes (light 1440, dark 1440,
  light 375, dark 375) plus the editor and the signed-out pages: 119 screenshots in `shots/`.
  For each pass it records computed colour/background pairs and WCAG contrast, every text node under
  12 px, heading order, horizontal overflow, small hit targets, marketing vocabulary and emoji.
  Raw data: `docs/audits/ui/data/scan.json`.
- `docs/audits/ui/tools/frames_scan.py` hashes all 116 frames and reports byte-identical duplicates.
- 24 frames were read at full size (the families that carry distinct templates: foundations, home,
  dataset, board, editor, query bar, states, deploy hub, first run, dataset agent, Thai editor, Thai
  station, Thai invoice, mobile editor, mobile station, dark editor). The other 92 were checked for
  duplicates and dimensions only. That limit is stated again in §6.

---

## 1. Scoreboard

| Severity | Count | Meaning |
| --- | --- | --- |
| C — critical | 0 | Nothing blocks a first-hour task or ships a false claim in the app itself. |
| I — important | 25 | A defect a buyer sees in the first hour, or a WCAG AA failure. |
| m — minor | 29 | Polish, consistency, copy, density. |
| **Total** | **54** | 36 app, 18 frames. |

The app is in better shape than the brief feared. There are no gradients invented per screen, no emoji,
no marketing copy inside the tool, no console errors, no horizontal document scroll at 375 px, and only
ten raw-palette classes in the whole frontend. The slop is concentrated in **three shared components**
(`PageHeader`, `Stat`, the tour card) and in **four raw-colour spots**, which is why most of the repair is
already planned by wave E and does not need new cards.

---

## 2. Findings — running app

Rule column names the check that fails: `impeccable` (craft floor), `hallmark` (slop gate), `uxui-law`
(law + production rule), `design-critique` (hierarchy/consistency), `accessibility-review` (WCAG),
`ux-copy` (copy), `design-system` (token coverage).

| # | Surface | Evidence | Rule broken | Sev | Smallest fix | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Every page with a title | `shots/p-dataset-light-1440.png`, `shots/ws-audit-light-1440.png` | impeccable: generic gradient. `PageHeader` is `bg-gradient-to-r from-secondary to-tertiary-container` (`components/ui.tsx:156`), i.e. lavender→pink on every work screen. hallmark gate: gradient wash as decoration | I | Drop the gradient for `bg-card` + `border`; keep the title and one action slot. One line in one component | **T-487** (exists) |
| A2 | Sidebar, project rail, tiles, charts, pills | scan.json `tinyText` on 24 routes; worst: dataset 70 nodes, playground 37 | design-system: type floor. The foundations frame states "metadata never below 12 px"; the app ships 11 px nav headers and 10 px chips (`AppSidebar.tsx:135`, `ProjectPanel.tsx:49,57`, `Dataset.tsx:168`, `Playground.tsx:148`, `ui.tsx:183`) | I | The 13 px floor sweep. Already planned, do not duplicate | **T-471** (exists) |
| A3 | Dataset tiles | `shots/p-dataset-light-1440.png` | design-system: token drift. `SPLIT_TONE = {train:'bg-violet-600', valid:'bg-blue-600', test:'bg-orange-500'}` (`Dataset.tsx:14`); white on orange measures **2.89:1** at 10 px | I | One `splitColor()` helper returning token classes | **T-495** (exists) |
| A4 | Annotate board, Review lane | `shots/p-annotate-light-1440.png`; measured 3.22:1 | accessibility-review 1.4.3. `bg-green-600` with white text (`AnnotateBoard.tsx:103`), and it is a second primary colour beside the blue one | I | Token success surface with `-fg` text, or an outline button | **T-495**, **T-496** (exist) |
| A5 | Playground latency chips, board error banner, auto-label amber note, new-key banner | `shots/ws-playground-dark-1440.png` | accessibility-review 1.4.3 in dark. Four surfaces hard-code light pastels (`bg-green-100`, `bg-red-50`, `bg-amber-50`, `bg-green-50`) that do not follow the theme | I | Route them through the `InlineAlert` primitive | **T-487** (exists) |
| A6 | Chart legends, all four chart screens | scan.json: `mAP50-95` 3.68, `Precision` 2.28, `Recall` 2.80, `mAP50` 2.88 (dark) | accessibility-review 1.4.3 + 1.4.11. 11 px legend text under 4.5:1; series colours are raw hex (`Models.tsx:136`) | I | Legend text `text-xs text-foreground`, series from the theme | **T-523** (new) |
| A7 | Models → Loss, Usage → metered activity | `shots/p-models-light-1440.png`, `shots/ws-usage-light-1440.png` | design-critique: broken state. A chart with axes, gridlines and no series, no "no data" line | I | Render a one-line empty state when the series list is empty | **T-523** (new) |
| A8 | Dataset grid at 375 | `shots/p-dataset-light-375.png` | uxui-law: responsive. `const cols = 5` (`Dataset.tsx:77`) and `grid-cols-5` (`:159`) give 62 px tiles at 375 px; chips inside are unreadable | I | `colsForWidth()` 2/3/5 driving both the slice and the CSS grid | **T-520** (new) |
| A9 | Dataset header | `shots/p-dataset-light-1440.png` vs sidebar count 40 | ux-copy: honesty. `desc` prints the *filtered* count as the total: "24 images in the dataset" while the project has 40 | I | `24 of 40 images match` when a filter is on | **T-520** (new) |
| A10 | `/…/streams`, `/…/qa` (flag off) | `shots/p-streams-flagged-light-1440.png` | design-critique: unclear state. A deep link to a disabled surface lands on Dataset with no explanation (`FlagGate` → `<Navigate to="..">`) | I | A "not available in this workspace" notice with the reason and the way back | **T-521** (new) |
| A11 | Deploy & Test → Hosted API | `shots/p-deploy-light-1440.png` | design-critique: content obscured. The absolutely positioned Copy button sits on top of the first code line (`Deploy.tsx:94-95`) | I | `pr-12` on the `<pre>`; button outside the scroll box | **T-522** (new) |
| A12 | Annotate header at 375 | `shots/p-annotate-light-375.png` | accessibility-review 2.5.8 / layout. The third action ("Upload More") is clipped off the right edge and unreachable | I | One action slot in the header, rest in an overflow menu | **T-487** (exists) |
| A13 | Top bar at 375, every project route | `shots/p-dataset-light-375.png`, `shots/p-annotate-light-375.png` | uxui-law: responsive. "16 awaiting review" wraps and is clipped; "Train Model" and "GPU idle" wrap to two lines in a 44 px bar | I | Chip hidden below `sm`; one control per row | **T-480** (exists) |
| A14 | One screen, three names | breadcrumb "Usage & Billing", `h1` "Settings", tab "Plan & Usage" (`shots/ws-usage-light-1440.png`) | ux-copy: one term per concept | I | One label for the page and its tab | **T-494** (exists) |
| A15 | Status vocabulary | board lane "Dataset", bulk menu "Set status → Dataset", versions tab "Dataset", models "Ready" | ux-copy + uxui-law (Similarity). The same status `done` is shown as "Dataset", "Approved" and "Ready" on three screens | I | One status vocabulary in one module | **T-494** (exists) |
| A16 | Frames' own colour habit, inherited by screens | every `*-1440.png` hero band | impeccable: purple-blue AI palette. `primaryContainer` lavender is the default surface for headers, chips, bulk bars, empty tiles | I | Wave E tokens: chrome is glass, content is `card`; lavender only for selection | **T-470** (exists) |
| A17 | Frames' copy notes shipped as UI | `shots/ws-home-light-1440.png` (green banner clipped) | ux-copy: filler. Internal notes ("Everything is set up. The checklist stays here for reference.") are cut off inside a fixed-height card | I | One sentence that fits, or let the card grow | **T-485** (exists) |
| A18 | Tour card, first load | `shots/ws-home-light-1440.png`, `shots/ws-home-light-375.png` | uxui-law: Golden Rule 7. The fixed card at `bottom-4 right-4` covers the card it explains, and `scrollIntoView({block:'center'})` moves the page under the reader on arrival | m | Anchor the card opposite its target; do not scroll on step 1 | **T-525** (new) |
| A19 | Tour spotlight | `shots/ws-home-dark-1440.png` | design-critique: state confusion. `.tour-target` is `outline: 3px solid var(--ring)` — the same signal as the keyboard focus ring | m | 2 px dashed ring in `--ring` at 60%, plus the card's arrow | **T-525** (new) |
| A20 | Stat tiles | Home / Models / Usage / Versions | design-system: component coverage. Three shapes for one idea: `Stat` with a 4 px accent bar, plain bordered cards, and cards with an inner meter (`ui.tsx:166`, `WorkspacePages.tsx`, `Versions.tsx`) | m | One `Stat` with an optional meter slot | **T-487** (exists) |
| A21 | Playground model list | `shots/ws-playground-light-1440.png` | uxui-copy: redundant content. The same vendor string prints on all ten rows at 10 px | m | Group by family once, or drop the column | **T-524** (new) |
| A22 | Annotate board lanes | `shots/p-annotate-light-1440.png` | ux-copy: empty state. Two lanes say only "Empty" — no what, why or how to start | m | "Nothing waiting. Upload images or move a batch here." | **T-496** (exists) |
| A23 | Annotate board below the fold | `shots/p-annotate-light-1440.png` | design-critique: unfinished. Lanes stop at 300 px, leaving 400 px of empty page on a work screen | m | Lanes fill the viewport height, scroll inside | **T-496** (exists) |
| A24 | Models page actions | `shots/p-models-light-1440.png` | accessibility-review 4.1.2. A bare trash icon sits in the primary action cluster with no visible label and no destructive styling | m | Icon button with `aria-label` and a danger tone, separated from the primary | **T-267** (exists) |
| A25 | Insights nav vs title | `shots/p-insights-light-1440.png` | ux-copy: one term. Nav "Insights", breadcrumb "Insights", `h1` "Insights Studio" | m | `h1` "Insights" | **T-494** (exists) |
| A26 | Workspace sidebar vs settings tabs | `shots/ws-usage-light-1440.png` | design-critique: duplicate navigation. "Plan & Usage" is current in both navs at once | m | Settings tabs are the only nav inside Settings | **T-476** (exists) |
| A27 | Project tab strip at 375 | `shots/p-dataset-light-375.png` | uxui-law: Fitts / affordance. "Classes & Tags" is clipped at the edge with no fade or scroll cue | m | Fade the cut edge and keep the tab strip scrollable | **T-478** (exists) |
| A28 | Home stat strip at 375 | `shots/ws-home-light-375.png` | design-critique: rhythm. Two-up cards give ragged heights; "Annotations 651 / human and model-assisted" wraps to three lines | m | One column below `sm`, or a compact two-line tile | **T-491** (exists) |
| A29 | Editor thumbnails | `shots/editor-light-1440.png` | design-critique: ambiguous affordance. A blue circle-with-check on each thumbnail means "reviewed" but reads as "selected" | m | Check only on reviewed, and use the success role, not primary | **T-498** (exists) |
| A30 | Editor header | `shots/editor-light-1440.png` | design-critique: hierarchy. "Done" chip, "Saved", "Approve" (green fill), "Reject" (red outline), split, assist, panels: six signals in 56 px | m | One review state, one primary, assists at the pointer | **T-498** (exists) |
| A31 | Login aside | `shots/login-light-1440.png` | impeccable: empty decoration. A dashed blue box with dots sits under the three bullets and reads as a missing asset | m | Remove it, or put the session-list preview it implies | none — login is deliberately unplanned (`INDEX.md` §4.2 #13) |
| A32 | Insights charts | `shots/p-insights-light-1440.png` | design-critique: readability. Axis labels rotated 45°, and chart cards are taller than their plots | m | Horizontal labels for ≤6 categories; card height from content | **T-103** (exists) |
| A33 | Sidebar plan meter | `shots/ws-home-light-1440.png` | accessibility-review 4.1.2. The credit bar is a bare `div` with no role or value, and turns red by colour alone at >80% (`AppSidebar.tsx:148`) | m | Reuse `Progress`, which already carries `role`/`aria-valuenow` | **T-471** (exists) |
| A34 | Editor / Deploy code blocks | `shots/editor-light-1440.png`, `shots/p-deploy-light-1440.png` | design-system: monospace at 11 px inside a 13 px floor | m | Same floor sweep | **T-471** (exists) |
| A35 | Upload page | `shots/p-upload-light-1440.png` | ux-copy: empty state. One dropzone, no limits, no "what happens next", no recent uploads | m | Add the accepted formats, the size cap and the duplicate rule under the dropzone | **T-071** (exists) |
| A36 | Versions header | `shots/p-versions-light-1440.png` | design-critique: destructive proximity. A bare trash icon sits beside "Train a model" | m | Danger tone, separated, confirmed by count | **T-219** (exists) |

---

## 3. Findings — frames

The frames are a design lane's file. Nothing here was edited. Each row says who can fix it.

| # | Frame | Rule broken | Sev | Smallest fix |
| --- | --- | --- | --- | --- |
| F1 | `00-foundations.png` / `foundations.png`, `09-models.png` / `09-models-evaluation.png`, `10-deploy.png` / `10-deploy-test.png` | design-system: dead assets. Three byte-identical pairs | m | Delete one of each pair |
| F2 | `e1-editor-thai.png` | ux-copy: Thai is wrong, not just awkward. The S-key tool reads "ยัวจระเข้", which is not a Thai word for any tool; the empty-image note reads "ไม่มีความในภาพ" (should be "ไม่มีวัตถุในภาพ"); the footer reads "ไม่มีปุ่มใดค้างค้าง" | I | Rewrite with a native Thai reviewer; a machine translation will not catch these |
| F3 | `a10-10-station-thai-operator-glove-first.png` | ux-copy: Thai. "โหมดถูกจับ" as the mode chip, "สีเพี้ยนปลอม" as a reason, and a footer sentence about type metrics printed as UI | I | Same reviewer pass |
| F4 | `a1-01-first-run-three-setup-questions.png`, `a6-01-deploy-hub-runtime-chooser-snippets-self-hosted.png` | governance. The frames print prices ($49/mo, $199/mo, $0.60/1k, $189/month, $39/channel) that `INDEX.md` §4.1 says are not decided | I | Print "Pricing not set" until the owner answers |
| F5 | `d3-thai-tax-invoice-promptpay-po-dunning.png` | trust. The PromptPay block is a decorative pattern that scans as nothing, labelled "Scan with any Thai bank app" | I | A real QR from the mock invoice, or a labelled placeholder |
| F6 | `a10-10-station-thai-operator-glove-first.png`, `m-13-station-thai-375.png` | uxui-law §4.7 (ISA-101). Pass is bright green and all three verdicts are equal size; colour means normal, not abnormal, and the most frequent action has no size advantage | I | Pass in the neutral primary, fail in danger, repair in warning; pass gets the larger target |
| F7 | `dark-05-editor.png` | accessibility-review 1.4.3. In dark mode "Approve" becomes light green with white text and "Next image" light blue with white text; both fail AA | I | Dark-mode variants that keep dark text on light fills, or darker fills |
| F8 | `04-annotate-board.png` | data honesty. "To label 0 images" heads a card reading 16/16; "In review 16 images" heads two cards of 16 each | I | Lane counts sum their cards |
| F9 | `s-01-empty-loading-error-and-offline-states.png` | ux-copy: filler. "No dead end: the empty state is the first step." prints under all four empty states and "Nothing you typed is lost." under all four errors | m | Keep the specific sentence, drop the repeated one |
| F10 | `s-01-…` | design-critique: decorative icon. Four different surfaces share one generic document glyph in a lavender tile | m | Use each surface's own icon, or none |
| F11 | `m-13-station-thai-375.png` | ux-copy: language mix. Thai body with English bottom tabs (Projects, Queue, Models, Streams, More) | m | Thai tab labels |
| F12 | `04-annotate-board.png`, `c5-ask-dataset-agent-plan.png`, `d3-…`, `a10-10-…` | ux-copy: notes as UI. Design annotations ("Approve all asks first…", "The agent may propose and trial…", "อักษรไทยสูง 1.6 เท่า…", "7% VAT and a PO number are not edge cases") are set in the interface | m | Move them to the frame's caption, not the screen |
| F13 | `a2-04-images-query-bar-negation-saved-views-share-link.png` | design-critique: inverted hierarchy. "Train model" is an outline while "Export selection" is filled | m | One filled action per screen |
| F14 | `m-01-editor-375.png` vs `05-editor.png` | design-critique: cross-surface drift. Approve is blue on the phone and green on the desktop | m | One review-action colour |
| F15 | `c5-ask-dataset-agent-plan.png` | design-critique: competing primaries. Three filled blue buttons on one screen | m | Keep "Queue for review" filled, the rest outline |
| F16 | `06-dataset.png`, `a2-04-…`, `04-annotate-board.png`, `c5-…` | impeccable: purple-blue AI palette at system scale. Lavender is the default for headers, bulk bars, chips, empty tiles | I | Chrome is glass, content is `card`, lavender only for selection |
| F17 | `m-01-editor-375.png` | design-critique: dead space. The tools sheet ends 150 px above the fixed review bar | m | Sheet meets the bar |
| F18 | `a1-01-…`, `05-editor.png`, `04-annotate-board.png` | ux-copy: two filled primaries in one view ("Create project" + "Start from the demo set", "Approve" + "Next image", "Start labelling" + "Review 16") | m | Secondary actions become outline |

---

## 4. Top 15, in the order a merge captain should take them

1. **A1 PageHeader gradient.** One component, every screen, and it is the single loudest AI tell in the
   product. `T-487`.
2. **A9 + A8 Dataset count and grid.** The count is a false statement about the user's data, and the
   375 px grid is unreadable. `T-520`.
3. **A3 + A4 raw split/approve colours.** Two measured AA failures and the only violet in the app. `T-495`.
4. **A6 + A7 chart legends and blank charts.** Three chart screens show an empty plot or unreadable keys.
   `T-523`.
5. **A10 silent flag-off redirect.** A buyer following a shared link thinks the feature vanished. `T-521`.
6. **A11 Deploy code block.** The Copy button covers the first line of the snippet a developer is meant to
   paste. `T-522`.
7. **A13 + A12 mobile top bar and clipped primary.** At 375 px the primary action is partly off-screen.
   `T-480`, `T-487`.
8. **A2 type floor.** 10 px metadata on 24 routes. `T-471`.
9. **A14 + A15 + A25 naming.** One screen with three names; one status with three words. `T-494`.
10. **A5 dark-mode pastels.** Four light-only status surfaces. `T-487`.
11. **F2 + F3 Thai copy.** Real Thai is a market claim; nonsense Thai breaks it. Design lane + `T-494`.
12. **F4 prices in frames.** The frames contradict the owner's own decision. Design lane.
13. **A18 + A19 tour.** It covers the card it points at and its ring looks like focus. `T-525`.
14. **A20 stat tiles.** Three shapes for one idea. `T-487`.
15. **F8 lane counts.** Numbers that contradict their own cards. Design lane + `T-496`.

---

## 5. What is already good

Worth protecting, because a cleanup wave that flattens these would be a net loss.

- **Token discipline.** Ten raw-palette classes in the whole frontend, and six of the ten are on-canvas
  overlays where a literal colour is correct. Nothing invents a per-screen palette.
- **The glass contract is respected.** Chrome uses `Glass`; the canvas, grids, tables and charts stay
  solid. `prefers-reduced-transparency`, the Settings toggle, `prefers-contrast: more`, `forced-colors`
  and `prefers-reduced-motion` are all handled in `index.css`, and the fallback is solid, not blur.
- **Focus is real.** `:focus-visible` is a 2 px `--ring` at 3:1 with a 2 px offset, and `scroll-padding`
  keeps the focused row clear of the top bar and the job tray.
- **No slop vocabulary.** Zero hits for "Unlock", "Seamless", "Supercharge", "AI-powered", "Elevate",
  "Transform your". Zero emoji. No decorative icon font.
- **No console errors** on any of the 119 captures, and no horizontal document overflow at 375 px.
- **Honest data surfaces.** The Models page says out loud that its metrics come from the original run and
  were not evaluated on this dataset. Train shows unavailable families disabled with the reason
  ("rfdetr not installed") instead of hiding them. Versions states "from 24 source". Upload says
  duplicates are skipped by SHA-256.
- **Error copy in the states frame is the best writing in the project**: "The upload was interrupted at
  240 of 1,280 images", "The endpoint returned 502 three times in a row", "stopped at Detect: model not
  loaded", "The plan stays active for 7 days", each with a specific recovery action and "Nothing you
  typed is lost."
- **The query surface.** Natural language parsed into editable chips, with a "Why this answer" panel that
  names the misreading it avoided. This is the strongest interaction idea in either artefact.
- **The agent plan panel.** Four steps with done / done / below gate / waiting and an explicit
  "Approve plan / Stop". Guardrails shown, not claimed.
- **The foundations frame** documents tokens, roles, components, AA pairs and the type scale with real
  Thai. It is the reason the app's drift is measurable at all.
- **Charts carry their own export.** Every Insights card has CSV and Table next to it.

---

## 6. False positives I checked and dropped

Stated so nobody re-files them.

- **"Object Detection" measured at 1.11:1.** My scanner resolved the label's 70% black scrim as
  transparent and compared white text against the light `bg-muted` behind it. The label is legible. The
  real defect there is the 10 px size (A2).
- **The clipped "Home" title at 375 px.** That is the tour's `scrollIntoView({block:'center'})` moving the
  page, not a layout bug. It is filed once, as A18.
- **The blank landing page in the first capture.** The marketing sections reveal on scroll; after a scroll
  pass the page renders completely. The landing page is not broken.
- **Broken characters in source strings** (`�` seen in a shell grep). Re-read as UTF-8: zero U+FFFD
  bytes in `apps/frontend/src`. That was console encoding, not the file.
- **The tour auto-starting.** It is once per person per workspace by design (`Dashboard.tsx:44`).

## 7. Limits of this audit

- 24 of 116 frames were read at full size. The rest were hashed and dimension-checked only. The frames
  share a small number of templates, so the 18 frame findings are stated as template-level, but a frame I
  did not open may hold a defect this document does not name.
- Contrast was measured on composited solid backgrounds. Text over a photo or over glass was skipped
  (`unknownBg` in `scan.json`), so photo-overlay contrast is unmeasured.
- Screen-reader behaviour and 200% zoom were not exercised. `T-490` owns that proof.
- The app was audited in English only. Thai layout was judged on the frames, because the running app has
  no Thai strings yet.
- Twelve flag-gated routes redirect before rendering, so their screens are not in this audit. Their
  flag-off behaviour is (A10).
