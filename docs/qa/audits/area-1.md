# Area 1 audit — entry, workspace home, project overview

T-1214, wave Q, first pass. Owner request 2026-11-17: usability program, audit area 1.

| Field | Value |
| --- | --- |
| Build audited | `bc3c4e5` (`feat/labeldesk-v2`), plus this card's spec only — no product file changed |
| Flag | `task_470` (`ui_v3`) on for every workspace read; the public routes carry no flag |
| Method | `docs/qa/USABILITY-PROGRAM.md` §3–§10: axe, keyboard, 375/768/1440, forced states, Nielsen 1–5, laws, personas |
| Spec | `apps/frontend/e2e/audit-area-1.spec.ts` (`@nightly`) |
| Evidence | `B:/02_Projects/ld-tmp/evidence/T-1214/` (57 screenshots, 19 axe JSON files, 4 state files) |
| Run log | `B:/02_Projects/ld-tmp/evidence/T-1214-record.log` |
| Result | 2 of 4 spec tests green; **3 S2**, 5 S3, 1 S4 open. No S1. |

**What a buyer meets before a project**: the landing, the five auth screens, the first run on a new
workspace, the workspace home and the project overview. Every screen is reachable, the copy is the
shipped copy, and the glass system is the one the app already ships. The problems are in what the
screens do, not in what they look like: two accessible names do not contain their visible text, one
loading state announces itself illegally, the overview board is 93 px wide at 1440, and the first run
offers the same "create" three ways while the empty queue offers nothing.

The spec encodes the target, not today's defects. The three red assertions are the regression tests
for the fix cards below; they stay red until the product changes (`USABILITY-PROGRAM.md` §10).

---

## 1. Evidence index

Every screenshot is `area1-<screen>-<width>-<theme>.png`.

| Screen | Routes | Captures |
| --- | --- | --- |
| Landing | `/` | 375 / 768 / 1440 × light, dark |
| Sign in | `/login` | same |
| Create account | `/signup` | same |
| Reset request | `/forgot` | same |
| Reset form | `/reset/:token` (an invalid token) | same |
| Verify result | `/verify/:token` (an invalid token → the error state) | same |
| Workspace home | `/labeldesk-demo` | same |
| Project overview | `/labeldesk-demo/p/ppe-detection` | same |
| First run | a brand-new workspace's `/:ws` | same |
| Home · no match | `/:ws` with a filter that matches nothing | 1440 light |
| Home · loading | `/:ws`, `/api/ws/*/home` delayed 1,200 ms | 1440 light |
| Home · error | `/:ws`, two 503s then a working retry | 1440 light |

54 route captures (9 routes × 3 widths × 2 themes) + 3 state captures = **57 files**; `screenshots.json`
lists them. Axe output: `axe-<screen>-<width>-<theme>.json` (raw) and `axe-summary.json` (counts).
States: `empty-state-copy.json`, `empty-state-actions.json`, `overview-board-widths.json`,
`responsive-1440.json`.

The app shell scrolls inside a `div`, so an app screenshot is one viewport tall; the landing is a
document and its shots are full-page.

---

## 2. Accessibility — axe-core 4.14, 19 passes

Eighteen route passes (9 screens × light/dark at 1440) plus the loading state.

| Screen | Light | Dark |
| --- | --- | --- |
| Landing | 0 / 0 | 0 / 0 |
| Sign in | 0 / 0 | 0 / 0 |
| Create account | 0 / 0 | 0 / 0 |
| Reset request | 0 / 0 | 0 / 0 |
| Reset form | 0 / 0 | 0 / 0 |
| Verify result | 0 / 0 | 0 / 0 |
| Workspace home | 0 / 0 | **0 / 1** |
| Project overview | **0 / 1** | **0 / 1** |
| First run | 0 / 0 | 0 / 0 |
| Home · loading | **0 / 1** | not run (same markup) |

`critical / serious`. **Moderate: 0. Minor: 0** on every pass — there is no moderate or minor list to
carry.

| Pass | Rule | Impact | Nodes | Element |
| --- | --- | --- | --- | --- |
| Overview, light and dark | `label-content-name-mismatch` (WCAG 2.5.3) | serious | 7 | Project rail links: `aria-label="Upload, 40, done"` (visible text `1 Upload done 40`), `"Annotate, 16, needs you"`, `"Dataset, 1, done"`, `"Classes & Tags"` (visible `Classes & Tags —`), `"Train, 0, not started"`, `"Models"`, `"Deploy, no count yet"` |
| Home, dark | `label-content-name-mismatch` (WCAG 2.5.3) | serious | 1 | Jobs trigger: `aria-label="Jobs, 1 active"`, visible text `Jobs 1` |
| Home, loading | `aria-prohibited-attr` (WCAG 4.1.2) | serious | 1 | `<div aria-busy="true" aria-label="Loading workspace dashboard">` — `aria-label` on a roleless `div` |

The rail rule fails because the name reorders the visible text and omits the pipeline number; the
trailing "—" the secondary rows print is not in the name. The Jobs trigger fails on the comma between
"Jobs" and its count. Both are fixable without a new token or component.

`color-contrast` returned no violation on these passes. The harness helper returns `violations` only,
so axe's `incomplete` bucket was not measured — see §13.

---

## 3. Keyboard only — passes

`area 1 keyboard: landing → sign up → home → overview` walks the first hour with Tab, Enter and typed
text; no pointer event is used. Every stop painted a `:focus-visible` ring (2 px, non-zero outline)
and the order was reading order.

| Step | Assertion | Result |
| --- | --- | --- |
| 1 Landing | the first eight stops are Skip to content → LabelDesk → Product → Models → Pricing → Docs → Log in → Start free | pass |
| 2 Sign up | the name field is focused on arrival; Tab reaches Work email → Password → Workspace name → Create account, in that order | pass |
| 3 First run | five tour steps, each advanced with Tab + Enter; the card never overlaps the section it rings; step 1 leaves `scrollY` at 0 | pass (A18/A19 re-checked) |
| 4 Empty workspace | "0 of 6 done" and "No projects yet."; Tab reaches the checklist's Create, Enter opens the dialog | pass |
| 5 Create + overview | the name is typed, Tab reaches Create Project, Enter creates and lands on `/upload`; Tab reaches the project switcher, Enter opens the overview; one primary visible and inside the viewport | pass |

The landing's skip link is the first stop and works. The auth shell's brand link precedes the form;
the form autofocuses the name field, so the first Tab starts at Work email.

---

## 4. Responsive — 375, 768, 1440 — passes

54 checks (9 screens × 3 widths × 2 themes): no horizontal document scroll, and the screen's primary
sits fully inside the viewport. The 1440 legs are recorded in `responsive-1440.json`; the rest are
also captured as screenshots.

| Screen | 375 | 768 | 1440 |
| --- | --- | --- | --- |
| Landing, five auth screens | pass | pass | pass |
| Workspace home, first run | pass | pass | pass |
| Project overview | pass (no document scroll) | pass | pass |

Two things the check cannot see, and the screenshots show: at 375 the project section strip is a
horizontal scroller whose rows run off the right edge, the breadcrumb truncates to `Label… › PP…`, and
the GPU chip wraps onto two lines inside its pill. The document does not scroll sideways and the
primary is reachable, so the assertion passes; the clipping is **Q1-A1-05**.

At 1440 the workspace rail (232) and the project rail (232) plus the 360 px aside leave **512 px** for
the five pipeline cards — **93 px each** (`overview-board-widths.json`). The cards are readable as
labels, not as sentences: "40 / images / uploaded" and "Train / on v1" wrap one word per line. That is
**Q1-A1-04**.

---

## 5. States — forced, not hoped for

| State | How forced | What renders | Actions offered |
| --- | --- | --- | --- |
| Empty (new) | a new account's workspace | tour, "At a glance" with five zeros, "You're all caught up." for the queue, "0 of 6 done", "No projects yet." | `Create` (checklist) **and** `Create your first project` |
| Empty (no match) | the projects search set to `zzz no project matches this` | "No projects match." + the projects hint | `Create your first project` (no clear-filters) |
| Loading | `/api/ws/*/home` delayed 1,200 ms | three grey slabs with `aria-busy`, no page spinner | — |
| Error | two 503s on `/api/ws/*/home` | one alert: "Could not load the workspace dashboard: audit: forced failure" + Try again; the Projects grid and the rail stay usable | `Try again` → real data |
| Permission | not forced here — the demo account is a workspace admin; the role matrix is audit area 7 | — | — |
| Offline | not forced here — the shell's banner belongs to area 7's shell work | — | — |

`empty-state-copy.json` holds the three sentences; they are genuinely different:

- first run: `No projects yet. Projects hold images, annotations, versions and models. Create your first project`
- empty queue: `You're all caught up. New assignments, reviews and unassigned batches appear here.`
- no match: `No projects match. Projects hold images, annotations, versions and models. Create your first project`

`empty-state-actions.json`: first run `["Create", "Create your first project"]`, queue `[]`, no match
`["Create your first project"]`. The acceptance line "each has one action" is **not met** — Q1-A1-06.

The loading skeleton is three slabs (96 px, then two 224 px blocks) against a final page of five stat
cards, a queue, an activity list and a checklist; it is not the final geometry. The error card prints
the API's own message and no reference id — Q1-A1-03 and Q1-A1-08.

---

## 6. First-run tour — passes A18/A19

Measured at 1440 on a brand-new workspace, all five steps, keyboard only:

- Step 1 (`home-stats`) does not scroll the page: `scrollY` was 0 before and after.
- No step's card box intersects the box of the section it rings (5/5), including the tall
  `home-projects` section at the bottom of the page.
- Each step is announced "Step N of 5"; Next/Done and End tour are reachable by Tab and work with Enter.
- Done writes the seen key for that person in that workspace (`dashboardRules.tourKey`); the rule is
  pinned by T-525's node test, and this run did not re-visit the workspace to observe it.

At 375 the tour is a bottom sheet over the lower part of the page; the ringed section stays visible
above it. This closes the A18/A19 re-check the card asks for.

---

## 7. Nielsen heuristics — 1–5 per screen

Scale: 1 blocks the task, 3 works but costs a detour, 5 no friction. Evidence is a screenshot, a spec
assertion or a measured number.

### Landing (`/`) — mean 4.1, min 3 → A

| H | Score | Evidence |
| --- | --- | --- |
| H1 system status | 5 | static page, nothing to report; the CTA is visible at first paint |
| H2 real world | 4 | "Label, train and deploy vision models — in one place"; no model jargon above the fold |
| H3 control and freedom | 4 | section anchors; no modal, no trap |
| H4 consistency | 4 | one CTA verb, "Start free", in nav, hero and closing band |
| H5 error prevention | 5 | no form, no destructive action |
| H6 recognition | 3 | nav labels "Product / Models" do not say what the sections hold; the four hero cards are `aria-hidden` |
| H7 flexibility | 4 | 8 stops, all anchors, reading order (spec step 1) |
| H8 minimalism | 4 | one loud band per section; a single primary per band |
| H9 error recovery | 5 | n/a — no error surface |
| H10 help | 3 | "Docs" scrolls to the footer's link list, not to documentation |

### Sign in (`/login`) — mean 4.0 → A

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | busy submit keeps its width; inline alert |
| H2 | 4 | Email / Password, plain words |
| H3 | 4 | wrong password keeps the email; Forgot password is one link |
| H4 | 4 | same shell and field geometry as Create account |
| H5 | 4 | inline error names the problem; rate-limit sentence |
| H6 | 4 | Forgot password beside the field it belongs to |
| H7 | 4 | autofocus on email, Enter submits |
| H8 | 5 | one primary; the marketing rail is hidden at 375 |
| H9 | 4 | inline alert + hint "Check the email and password" |
| H10 | 3 | no help entry; Forgot password is the only escape |

### Create account (`/signup`) — mean 3.8 → B

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | `aria-busy` on the submit, box unchanged |
| H2 | 4 | Full name / Work email / Password / Workspace name |
| H3 | 4 | "Already have an account? Sign in" |
| H4 | 4 | same card as sign in |
| H5 | 4 | duplicate email is named inline; the typed address survives |
| H6 | 4 | password and workspace hints sit under their fields |
| H7 | 3 | four fields and a long rail; Tab order is correct but there is no shortcut |
| H8 | 3 | the marketing rail takes ~45 % of a task screen at 1440 (accepted: INDEX §4.2 #13) |
| H9 | 4 | inline alert plus "Sign in instead, or use a different address" |
| H10 | 4 | hints answer why, not only what |

### Reset request (`/forgot`) — mean 4.1 → A

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | "Check your email" repeats the address; "Use a different email" |
| H2 | 4 | "Enter the email on your account" |
| H3 | 4 | Back to sign in; use a different email |
| H4 | 4 | same shell |
| H5 | 4 | never says whether the account exists |
| H6 | 4 | single field, autofocus |
| H7 | 4 | Enter submits |
| H8 | 5 | one field, one primary |
| H9 | 4 | rate-limit hint: 15 minutes |
| H10 | 4 | spam advice and the dev inbox note |

### Reset form (`/reset/:token`) — mean 4.1 → A

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | "The link works once"; the expired case is stated |
| H2 | 4 | "Choose a new password" |
| H3 | 4 | "Request another" link |
| H4 | 4 | same shell and field geometry |
| H5 | 4 | confirm field + 8-character minimum, both checked before the request |
| H6 | 4 | hint under the first field |
| H7 | 4 | Enter submits; both fields autofocus in order |
| H8 | 5 | two fields, one primary |
| H9 | 4 | "invalid or expired" with a link to a new link |
| H10 | 4 | explains the 30-minute rule |

### Verify result (`/verify/:token`) — mean 4.1 → A

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | checking → verified / invalid, each with its own heading |
| H2 | 4 | "This link won't work" and why |
| H3 | 4 | one action back to sign in |
| H4 | 4 | same shell |
| H5 | 5 | n/a |
| H6 | 4 | the reason is on the screen, not in a help page |
| H7 | 4 | single action, Enter works |
| H8 | 5 | one card, one action |
| H9 | 4 | explains used/expired and what to do |
| H10 | 3 | the "request a new link" step lives behind sign-in |

### Workspace home (`/:ws`) — mean 3.2 → C

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 3 | counts are live, but the loading state is three grey slabs and the error prints the server's message (Q1-A1-03, 08) |
| H2 | 3 | "Datasets" counts projects, "Models" counts training runs (Q1-A1-09) |
| H3 | 3 | clearing the search is the only way out of "No projects match."; the state offers create instead (Q1-A1-06) |
| H4 | 3 | "Create Project" (dialog), "New Project" (toolbar), "Create" (checklist) for one action |
| H5 | 4 | delete names the project and asks first |
| H6 | 3 | the queue row names the project and counts, never the stage |
| H7 | 3 | no keyboard path to the queue; the first Tab path crosses the top bar, the rail and five stat cards |
| H8 | 3 | five stat cards lead; "Invite Team" in the header and "New Project" in the toolbar compete (Q1-A1-07) |
| H9 | 3 | one line + Try again, no reference id, raw server detail (Q1-A1-08) |
| H10 | 4 | the getting-started checklist is real help |

### First run (empty workspace) — mean 3.9 → B

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | "0 of 6 done" and five zero counts; the tour states where you are |
| H2 | 4 | checklist in work words: Create a project, Upload images, Label… |
| H3 | 4 | tour is dismissible and replayable; Escape ends it |
| H4 | 3 | two create actions for one outcome (Q1-A1-06) |
| H5 | 4 | nothing destructive |
| H6 | 4 | each undone step carries its own sentence |
| H7 | 3 | two paths to the first project, no single one |
| H8 | 3 | checklist Create and empty-state "Create your first project" both look actionable (Q1-A1-06) |
| H9 | 5 | n/a |
| H10 | 5 | the checklist is the what-next |

### Project overview (`/:ws/p/:project`) — mean 3.7, min 2 → C

| H | Score | Evidence |
| --- | --- | --- |
| H1 | 4 | five stage states, counts, health ring, "Blocked by" |
| H2 | 4 | Upload / Annotate / Dataset / Train / Deploy |
| H3 | 4 | every card links; the header primary is the next task |
| H4 | 4 | one state vocabulary, the same as the rail |
| H5 | 4 | no destructive action on this screen |
| H6 | 4 | each card carries its count and one action |
| H7 | 4 | the header primary follows the earliest open step (`overviewFacts.primary`) |
| H8 | **2** | at 1440 the five cards are 93 px wide and their sentences wrap one word per line (Q1-A1-04); at 375 the breadcrumb and GPU chip clip (Q1-A1-05) |
| H9 | 4 | a failed count shows "—" and a Retry, never a zero |
| H10 | 3 | "Blocked by" names the fix; no help link |

**Acceptance check "no score < 3": not met** — the overview's H8 is 2. That screen cannot ship in a
wave without its fix card (program §4), and Q1-A1-04 is that card.

---

## 8. Laws (`uxui-law`) — pass / fail where they apply

| Law | Result | Evidence |
| --- | --- | --- |
| Fitts — target size | pass | rail rows 32 px with a 44 px `::before` hit area; header primary 36 px; card links `min-h-6` |
| Hick — control count | **fail** | home: five stat cards + queue + checklist + three filters + two create entries before the one task (Q1-A1-07) |
| Miller — grouping | pass | three rail groups, six checklist steps, at most three blockers |
| Jakob — familiar patterns | pass | numbered pipeline, standard email/password forms, a Forgot link beside the field |
| Doherty — feedback < 400 ms | not measured | no trace in this card; T-1221 owns the budgets |
| Goal-Gradient — progress | pass | "4 of 6 done" with a progress bar; stage counts |
| Zeigarnik — unfinished work | pass | "16 items" badge, "needs you" chips, undone checklist rows |
| Von Restorff — one loud thing | **fail** | first run shows two create actions; the five-card stat row is louder than the queue (Q1-A1-06, 07) |
| Tesler — the system absorbs complexity | pass | batch-name and split defaults, counts, state words, slug suggestions |
| Postel — tolerant input | pass | email trimmed; project search case-insensitive; a taken address suggests a free one |
| Occam — one path | **fail** | two paths to the first project on first run (Q1-A1-06) |
| Prägnanz — grouping reads as one thing | **fail** | five 93 px columns read as a striped block (Q1-A1-04) |
| Aesthetic-Usability — first impression | **fail** | the overview's first look at 1440 is a squeezed board (Q1-A1-04) |

Every failure names the law and the finding that owns it.

---

## 9. Personas P1, P3, P4 — walkthroughs and SUS-8

One evaluator plays each persona (program §12). "Notice" and "connect" are the walkthrough's Q2 and
Q3; "feedback" is Q4.

| Persona | Walk | Notice | Connect | Feedback | Dead end |
| --- | --- | --- | --- | --- | --- |
| **P1 new labeler** (375 and 1440) | landing → sign up → home → queue → annotate | yes | yes ("16 to review") | yes (badge, then the board) | none |
| **P3 QA lead** (1440, then 375) | sign in → home → the review queue → overview | yes at 1440; **no at 375** — the queue sits below five stat cards | yes | yes | none |
| **P4 admin** (1440) | sign in → home → overview → back to home | yes | yes ("Blocked by", stage states) | yes on home; **no on the overview** — the board does not read | none |

SUS-8 (program §5 formula; odd items subtract 4, even items are 20 minus the sum):

| Persona | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | **75** |
| P3 | 4 | 2 | 3 | 2 | 4 | 2 | 4 | 2 | **72** |
| P4 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | **75** |

All three clear the 68 floor; P1 and P4 sit exactly on the 75 release target and P3 is 3 below it. The
drag on P3 is the queue's position below the stats at 375 and the overview board at 1440 — Q1-A1-07
and Q1-A1-04. No persona is below 68, so the SUS adds no S2 of its own.

---

## 10. Copy — shipped strings only

There is no `lib/i18n.ts` yet (T-600 has not landed), so the catalogue is the JSX literals. Every string
on the twelve screens was read against the claims the system can back.

| Claim on an area-1 screen | Backed by |
| --- | --- |
| "Free plan · 3 projects · 10,000 images" / "3 projects, 10,000 images, 3 seats" | `app/config.py` `PLANS["free"]`: 3 / 10 000 / 3 / 30 credits |
| "SAM 3.1 and a VLM can draft and check masks **when an operator connects them**" | conditional sentence; no unconditional capability claim |
| "YOLO, RT-DETR, D-FINE — trains on your data" | `adapters/catalog.py` ships D-FINE nano/small/medium/large alongside the YOLO and RT-DETR rows |
| "A reset link expires after 30 minutes and stops working the moment a new password is set" | `routers/auth.py:31` `RESET_TTL = 30 * 60`; one-time token |
| "plus eight single-use codes for a lost phone" | `totp.py` `new_recovery_codes(n=8)` |
| "Every device is listed with its IP and last activity" | **not exercised in this audit** — the session list exists, the sentence was not proven here |
| No price, certification, data-residency or SLA claim | none appears on any area-1 screen |

Vocabulary drift (**Q1-A1-09**, S4): "Datasets" for projects, "Models" for training runs, "ready to
serve" for deployments; "Create Project" (dialog) vs "New Project" (toolbar) vs "Create" (checklist)
vs "Create your first project" (empty state). One word per concept is the program's §8 rule.

Thai is not applicable yet: no Thai string ships on these screens.

---

## 11. Findings

Format: id · severity · persona · spec · route · build, then expected / actual / rule / measure /
evidence / fix card. Ids stay `Q1-A1-nn` for T-1223.

```text
Q1-A1-01 · S2 · P1 P3 P4 · audit-area-1 (axe) · /:ws/p/:project · build bc3c4e5
Expected: every project-rail link's accessible name contains the text the eye reads, in order.
Actual: the name reorders the row and drops the pipeline number — aria-label "Upload, 40, done" over
        a row that reads "1 Upload done 40"; also Annotate, Dataset, Classes & Tags, Train, Models,
        Deploy. 7 nodes.
Rule: WCAG 2.5.3 Label in Name; H4 consistency.
Measure: axe 4.14 label-content-name-mismatch, serious, 7 nodes, light and dark at 1440.
Evidence: axe-overview-1440-light.json, axe-overview-1440-dark.json, area1-overview-1440-light.png.
Fix card: "The rail says what the eye reads" — StageItem.tsx (name from content, not aria-label).
```

```text
Q1-A1-02 · S3 · P1 P4 · audit-area-1 (axe) · /:ws and /:ws/p/:project · build bc3c4e5
Expected: the Jobs trigger's name contains its visible text ("Jobs 1").
Actual: aria-label "Jobs, 1 active" — the comma breaks the contiguous match; same rule as 01, second
        component. Only observable while a job is active (3 of 5 runs).
Rule: WCAG 2.5.3; H4.
Measure: axe label-content-name-mismatch, serious, 1 node (home dark, overview dark).
Evidence: axe-home-1440-dark.json; JobButton.tsx:37-41; T-1214-record.log.
Fix card: same card as Q1-A1-01, JobButton.tsx added to its files.
```

```text
Q1-A1-03 · S2 · all · audit-area-1 (states) · /:ws (loading) · build bc3c4e5
Expected: the loading state is a named region or status (WCAG 4.1.2) whose blocks match the final
          geometry (program §9).
Actual: <div aria-busy="true" aria-label="Loading workspace dashboard"> — aria-label on a roleless
        div is prohibited; the three slabs (100/224/224 px) do not match the five stat cards, the
        queue, the activity list and the checklist that replace them.
Rule: WCAG 4.1.2; program §9 loading rule.
Measure: axe aria-prohibited-attr, serious, 1 node.
Evidence: axe-home-loading-1440-light.json, area1-home-loading-1440-light.png.
Fix card: "The dashboard skeleton is a named region and the page's shape".
```

```text
Q1-A1-04 · S2 · P2 P3 P4 · audit-area-1 (screenshots, measured) · /:ws/p/:project · build bc3c4e5
Expected: at 1440 the five pipeline cards read as five cards with a sentence and one action.
Actual: two 232 px rails plus the 360 px aside leave 512 px; each card is 93 px wide, so "40 images
        uploaded" and "Train on v1" wrap one word per line and "Review 16" wraps into the count row.
Rule: H8 aesthetic and minimalist design; Prägnanz; Aesthetic-Usability.
Measure: available 512 px, cards 93 px, 5 columns; screenshot at 1440 light and dark.
Evidence: overview-board-widths.json, area1-overview-1440-light.png, area1-overview-1440-dark.png.
Fix card: "The overview board gets a readable width at 1440".
```

```text
Q1-A1-05 · S3 · P1 P4 · audit-area-1 (screenshots) · /:ws/p/:project at 375 · build bc3c4e5
Expected: no clipped tab or chip at 375 (program §6); the top bar stays one line.
Actual: the breadcrumb truncates to "Label… › PP…", the GPU chip wraps "GPU idle" onto two lines
        inside its pill and the section strip's rows run off the right edge.
Rule: program §6 breakpoints; Fitts; H4.
Measure: 375 × 812, light and dark; the document does not scroll sideways, so only the screenshot
        shows it.
Evidence: area1-overview-375-light.png, area1-overview-375-dark.png.
Fix card: "The 375 top bar keeps its breadcrumb and its chips on one line".
```

```text
Q1-A1-06 · S3 · P1 P4 · audit-area-1 (states) · /:ws (first run, empty queue, no match) · build bc3c4e5
Expected: each empty state has one action, and the action fixes that state.
Actual: first run offers "Create" (checklist) and "Create your first project" (projects); the empty
        queue says "You're all caught up." and offers nothing; a no-match search offers "Create your
        first project" instead of clearing the filter.
Rule: H8 one primary; Von Restorff; Occam; program §9 "each with a way out"; H9/H10.
Measure: first run 2 actions, queue 0, no match 1 (wrong one).
Evidence: empty-state-actions.json, empty-state-copy.json, area1-home-no-match-1440-light.png,
          area1-first-run-375-light.png.
Fix card: "Three empty states, three honest actions".
```

```text
Q1-A1-07 · S3 · P3 P4 · audit-area-1 (screenshots) · /:ws · build bc3c4e5
Expected (REDESIGN §S1): the "needs you" queue first, then project cards; one primary on the screen.
Actual: "At a glance" and five stat cards lead at every width; at 375 the queue is below the fold. The
        header's only button is "Invite Team" while "New Project" sits in the projects toolbar, so the
        screen has no single primary.
Rule: H1/H8; Von Restorff; Hick.
Measure: five stat cards above the queue at 1440 and 375; two candidate primaries.
Evidence: area1-home-1440-light.png, area1-home-375-light.png, area1-first-run-375-light.png.
Fix card: "Home leads with what needs you".
```

```text
Q1-A1-08 · S3 · P4 · audit-area-1 (states) · /:ws (error) · build bc3c4e5
Expected: an error says what failed, what survived, how to retry and a reference id (program §9).
Actual: "Could not load the workspace dashboard: <raw API message>" and Try again; no reference id, and
        the server's own detail is printed to the user. The Projects grid and the rail do survive.
Rule: H9 error recovery; program §9; PM rule "no internals in user-facing errors".
Measure: 503 ×2 → one alert, 0 reference ids, 1 raw server string.
Evidence: area1-home-error-1440-light.png.
Fix card: "The dashboard error names a reference, not the server".
```

```text
Q1-A1-09 · S4 · all · audit-area-1 (read) · /:ws · build bc3c4e5
Expected: one word per concept (program §8).
Actual: "Datasets" for projects, "Models" for training runs, "ready to serve" for deployments;
        "Create Project" / "New Project" / "Create" / "Create your first project" for one action.
Rule: H4 consistency; program §8.
Measure: 4 names for two concepts; 4 action labels for one action.
Evidence: area1-home-1440-light.png; Dashboard.tsx:106-110; Home.tsx:140; Dashboard.tsx:174.
Fix card: the copy/design pass (S4, batched — no dedicated card).
```

No S1: every screen is reachable, no data is lost or exposed in this area, and no public claim on a
landing or auth screen was found false.

---

## 12. Proposed fix cards

Titles only; T-1223 numbers and writes the stubs. Every one is ≤ 3 agent-hours and names this spec as
its regression test.

| For | Proposed title | Files | Hours |
| --- | --- | --- | --- |
| 01 + 02 | The rail and the Jobs trigger say what the eye reads | `components/shell/StageItem.tsx`, `components/shell/JobButton.tsx`, `tests/nav.test.mjs` (append) | 1.5 |
| 03 + 08 | The dashboard skeleton is a named region, and its error names a reference | `features/workspace/Dashboard.tsx` | 2 |
| 04 | The overview board gets a readable width at 1440 | `features/project/Overview.tsx`, `features/project/StageCard.tsx` | 2.5 |
| 05 | The 375 top bar keeps its breadcrumb and its chips on one line | `components/shell/TopBar.tsx` | 2 |
| 06 + 07 | Three empty states, three honest actions — and Home leads with what needs you | `features/workspace/Dashboard.tsx`, `features/workspace/Home.tsx` | 3 |
| 09 | Copy pass: one word per concept (S4, batched with the design pass) | `docs/qa/audits/copy-th.md` owner (T-1222) | — |

Cards 03+08 and 06+07 both touch `Dashboard.tsx`, so they merge in that order; 04 and 05 touch files no
other card in this list touches.

**Release rule.** 01, 03 and 04 are S2, so they block the next merge batch until fixed or the owner
records an exception. 02, 05, 06, 07, 08 are S3: fixed in the next wave or accepted in writing. 09 is
batched into the copy pass.

---

## 13. Limits and what was not verified

- **axe `incomplete` is not measured.** The T-1200 helper returns `violations` only; `color-contrast`
  produced no violation, but axe's `incomplete` bucket (which the program treats as a failure until
  pixel-sampled) is not exposed. R19 must sample contrast on the glass surfaces separately.
- **No screen reader, no 200 % zoom.** Recorded as manual, not measured, exactly as the program says.
- **No performance numbers.** Loading was forced at 1,200 ms for the state, not timed; T-1221 owns the
  budgets.
- **One evaluator.** The persona walkthroughs and SUS-8 are a proxy, not user data.
- **The demo seed only.** Workspace isolation was not re-tested here (the card excludes it); no
  cross-workspace request was made.
- **Flag-off frame.** The public routes carry no flag. With `task_470` off the project index redirects
  to `browse` (the v2 dataset grid) and the top bar shows the v2 "Train Model" button; observed once on
  the keyboard test's first attempt, recorded in `T-1214-keyboard.log` and not part of the v3 scores.
- **The Jobs-trigger finding is timing-dependent** (only while a job is active); it reproduced in 3 of
  5 runs, and the rail finding is stable in both themes.
- **Screenshots of app screens are one viewport tall** because the shell scrolls inside a `div`; the
  landing's are full-page.
- **No hardware, no model call.** Nothing in this area touches a GPU, vLLM, SAM or Ollama.

---

## 14. Re-running it

```powershell
$env:TMP = 'B:\02_Projects\ld-tmp\pytest'; $env:TEMP = $env:TMP
$env:PATH = "<worktree>\apps\backend\.venv\Scripts;$env:PATH"
$env:LD_AUDIT_EVIDENCE = 'B:\02_Projects\ld-tmp\evidence\T-1214'
cd <worktree>/apps/frontend
npx playwright test e2e/audit-area-1.spec.ts --reporter=list
```

Later waves re-run this spec and append to `docs/qa/audits/area-1.md`; they do not rewrite it.
