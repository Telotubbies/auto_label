# LabelDesk v2 — Roboflow-parity build backlog

Planning-lane output, 2026-11-17. Base branch `feat/labeldesk-v2` at `fe8ef1a`. Read-only lane: no
application code, tests or git state were touched; this folder is the only write.

**What this is.** 552 task cards in two layers. The first, **waves A–E**, closes every one of the 334 rows in
[`PARITY.md`](../PARITY.md): 262 gap rows (163 PARTIAL + 99 MISSING) plus the 72 HAVE rows, which are
pinned by seven regression-guard cards. The second, **wave F**, turns all 101 features of
[`BEYOND.md`](../../beyond-roboflow/BEYOND.md) — 2 HAVE, 58 PARTIAL, 41 MISSING; 14 Must, 61 Should, 26 Could —
into cards: the layer above parity, where a buyer compares us to CVAT, Encord, Ultralytics, NVIDIA or Edge Impulse,
or to the Thai factory down the road. Every card is one agent for 1–3 hours, names the exact files it
creates or edits, and specifies the tests that must fail first.

**Visual standard (owner, 2026-11-17).** The app's existing Liquid Glass look is binding:
[`VISUAL-OVERRIDE.md`](../../../../design/labeldesk-v3/VISUAL-OVERRIDE.md), `apps/frontend/src/index.css` and
`apps/frontend/src/components/glass.tsx`. The v3 frames decide layout, IA, flow, states and copy — never a second
palette, a second token set or new glass values. §7.4 records every card revised for this rule.

**Sources, in order of authority**
1. [`PARITY.md`](../PARITY.md) — the 334 rows, status, priority, size.
2. `01-workspace-projects.md` … `07-workspace-admin.md` — per-feature flow, screens, empty/loading/error
   states, edge cases.
3. [`design/labeldesk-v3/REDESIGN.md`](../../../../design/labeldesk-v3/REDESIGN.md) — wave E's names, IA,
   routes and state rules, read together with `VISUAL-OVERRIDE.md`: the frames give layout and flow, the running app
   gives the visual system.
4. [`_BRIEF.md`](_BRIEF.md) — the contract every card was written against (template, id bands, wave map,
   cross-area ownership, shared-file rules).
5. [`BEYOND.md`](../../beyond-roboflow/BEYOND.md) and its six group files (`01-…` … `06-…`) — wave F's 101
   features, each with its flow, evidence and recorded gap.
6. The code itself; every path in a card was verified against the repo.

**Owner directive this backlog implements (2026-11-17):** all 334 parity features, down to each recorded click,
state and edge case, in LabelDesk names, copy and icons only — never Roboflow text, logos or assets — plus every
feature of `BEYOND.md` (Must, Should and Could), styled with the glass system the app already ships.

---

## 1. How to use it

**Merge captain, per card**
1. Pick the next card in [§6 Execution order](#6-execution-order). A card is self-contained: read it, its
   parity rows' area-file sections, and `prompts/pm-backlog-quality.md`.
2. Check [§7 File ownership](#7-file-ownership-matrix): if the card's file is shared, merge it in the
   order the matrix gives, rebasing first.
3. Dispatch one implementer with the card, its role and skills, and the paths from §"Sources". The card
   already states the flag key, the migration, the tests and the acceptance criteria.
4. Reviewer runs the tests itself. Every card's acceptance list includes the flag-off state and the
   cross-workspace 404; a card that only tests the happy path is not done.
5. Merge one branch at a time. After a merge, rebase every waiting branch, then re-run its tests before
   its review continues (PM addendum).

**Implementer, before review:** rebase on the current `feat` tip; TDD with RED then GREEN; cover invalid
input, permissions, workspace isolation, flag-off and failure paths; run the touched module tests, the
serial API suite, `npm run build`, node tests, the OpenAPI/types check when routes or schemas changed,
and ruff at the CI-pinned version; stage files by name. `ponytail` still applies: the smallest change
that fully solves the card, no speculative code.

---

## 2. Counts

| Wave | Meaning | Cards | Agent-hours | PARITY rows touched |
| --- | --- | --- | --- | --- |
| G | Regression guards for the 72 HAVE rows | 7 | 19 | 72 (all HAVE) |
| A | Trial blockers — a buyer's first hour | 47 | 132.5 | 52 |
| B | Editor, train, evaluation and workflow core | 149 | 419 | 124 |
| C | Data and people — dataset depth, members, keys, audit, connectors | 97 | 278.5 | 88 |
| D | Commercial and enterprise (owner-gated; provider-agnostic) | 52 | 151 | 27 |
| E | LabelDesk-native redesign (17 frame + 12 finish) | 29 | 75 | 4 |
| **F** | **BEYOND — the capability layer above parity (owner-gated where legal)** | **171** | **488** | **101 BEYOND features** |
| **Total** | | **552** | **1,563** | **334/334 parity + 101/101 BEYOND mapped** |

Wave F's 171 cards are 1.7 per BEYOND feature: the same density this backlog already carries for parity (1.3
cards per row), with two or three cards only where a feature crosses schema → service → screen. Each is ≤ 3
agent-hours; none hides a six-hour job. Native Thai (G5.22) is four cards at the head of the wave because every
later band adds strings to the catalogue it creates.

The per-wave row counts exceed 334 because a row can legitimately split across waves (for example
`3-F3.55` has a wave-A save-conflict half and a wave-B state half) and because HAVE rows appear in both
G and a later wave when their own gap cell names real work. The completeness check in §9 asserts the
exact 334-id set, once each, with no unknown id.

**Sizing honesty.** 1,563 agent-hours is implementation only: 1,075 for parity and 488 for BEYOND. House practice
adds review, fix rounds, rebases and merge gates, so budget **1,850–1,950 agent-hours** end to end
(parity 1,250–1,350 plus wave F 600–650). The largest single concentration is wave B (419 h), which is also where
the product lives, so wave B is the schedule risk, not wave D. Wave F's 488 h are spread over seven bands that share
almost no exclusive file, so it parallelises better than B even though it is larger. Wave E dropped 1.5 h in the
owner's visual revision (T-470, T-472), which is why the wave-E row reads 75.

---

## 3. Rules that bind every card

- **Branding.** LabelDesk names, copy and icons only. A competitor name may appear once as a source
  label (`(RF: *…*)`), never as text a user reads. New copy is written in LabelDesk's voice; Thai strings
  are real Thai, not transliterations.
- **Glass is the visual standard.** Chrome (top bar, rails, floating toolbars, sheets, popovers, overlay) uses `Glass`
  from `components/glass.tsx`; content (canvas, dense tables, charts, cards) stays solid on `Card`. Tones come from the
  shipped roles — `bg-success/15 text-success`, `--primary`, `--muted-foreground` — through `chipTone` /
  `statusTone` / `classColor`. No card adds a CSS variable, a palette, a hex literal, an arbitrary font size or an
  icon library. Type is `text-sm` / `text-xs`. This binds every wave, not only E and F.
- **Provider-agnostic commercial wave.** No payment provider, plan price or self-host licence has been
  chosen (see §4). Every wave-D money card ships a `BillingProvider` interface plus a deterministic
  `MockProvider`, flags the surface off by default (`task_billing`), charges nothing, and renders
  "Pricing not set" where a price would be. The same rule applies to any vendor-shaped gap: dedicated
  compute, edge fleet, NAS, SMS, foundation-model assist and directory sync are planned as an interface,
  a catalogue row, a mock driver and an explicit "not available in this deployment" state.
- **Ponytail.** Extend an existing service, column or component before adding one. No new dependency for
  a few lines. Every card that adds a surface must state whether it needs a `services/flags.py` key.
- **No Alembic.** A new column is an `ADD COLUMN` block in `app/schema/<domain>.py`, registered in
  `schema.apply`; a new table is a model module registered in `models/__init__.py`. Migration-bearing
  branches merge one at a time and are tested on an existing database as well as an empty one.
- **OpenAPI is generated.** A route or schema change runs `python tools/export_openapi.py` and
  `npm run gen:api-types`; `openapi.json` and `api-types.gen.ts` are never hand-edited and are
  regenerated after a rebase that moved the contract.
- **Workspace isolation is a test, not a claim.** Every card's acceptance list has a cross-workspace id
  case that must return 404 and change nothing.
- **R7 security review** is required where a card touches auth, SSO/OAuth, RBAC, keys or secrets,
  billing money or webhooks, unauthenticated routes, folder-scoped access, destructive account actions,
  SIEM export, or untrusted uploads/URLs (safefetch). The card says so; 106 parity cards carry `yes`, and 62 of
  wave F's 171 do.
- **Wave F is owner-gated where law or money decides.** A card that touches Thai VAT invoicing, PDPA/DSAR personal
  data, a retention floor or legal hold, breach notification, an SLA credit, a licence or a public trust claim plans
  an interface plus a mock or dry run, ships flag-off, prints `Pricing not set` / `not certified` / `no measured
  history yet` where a fact would go, and **charges nothing**. Its Notes open with the decision the owner (or a Thai
  lawyer and accountant) must make first.

---

## 4. Decisions only the owner can make

### 4.1 Blocking wave D (three questions, in order)

1. **Payment provider.** Which provider processes subscriptions and one-off credit purchases (for
   example a global card processor, a merchant-of-record, or a Thai local gateway)? Until answered,
   `services/billing.py` defines the interface and a mock provider, and no card names a vendor.
2. **Plan ladder and prices.** What are the tiers, seats per tier, monthly credit allowance, credit-pack
   price, overage policy and trial length? Until answered, `app/pricing.py` holds `None`s and every
   screen renders "Pricing not set" — the UI shape ships, the numbers do not.
3. **Self-host licence.** Do we sell or license self-hosted inference and/or weights, under what terms,
   and which model families are permitted for commercial self-hosting given their upstream licences
   (the catalogue already badges AGPL/Ultralytics families)? Until answered, self-hosted inference is
   documented and free of credit charge, but no licence text or entitlement exists.

### 4.2 Secondary decisions (a default ships until the owner rules)

| # | Decision | Default the cards ship meanwhile | Cards affected |
| --- | --- | --- | --- |
| 4 | Assistant model provider for setup questions and the first-run artifact | Deterministic templates plus a create-project action; no LLM call | T-012–T-016 |
| 5 | HEIC/HEIF ingest | Refused with a remedy sentence and a documented reason | T-030, T-031 |
| 6 | Publishing models beyond the workspace | Workspace-shared checkpoints only; no internet-public model page | T-257, T-258 |
| 7 | Dedicated GPU boxes and edge fleet hardware | Interface, catalogue row, mock driver, "not available in this deployment" | T-352, T-358 |
| 8 | SMS notification vendor | Webhook and email channels; SMS listed as unavailable | T-439, T-440 |
| 9 | Semantic-segmentation project type and trainable keypoints | Pixel metrics computed over instance masks; keypoints show a visible "cannot train yet" state; OKS never faked from box AP | T-277–T-279 |
| 10 | Architecture search and few-shot models | Local catalogue search; a fixed Ultralytics quick recipe; no external model | T-269–T-276 |
| 11 | Directory sync protocol and OAuth app model | Interface plus mock directory; no SCIM claim in copy | T-427–T-434 |
| 12 | Data region, SLA and HIPAA/BAA position | Region statement and DPA page describe what exists; no unverified claim | T-404, T-409 |
| 13 | Login screen redesign (REDESIGN audit finding 1) | Deliberately unplanned: no parity row, REDESIGN §8 does not schedule it, and the SSO entry belongs to area 7's T-424/T-426 | — |

Nothing in this backlog blocks on a secondary decision; the three blocking ones gate only the money
surfaces, which are flagged off.

### 4.3 Decisions wave F needs (owner or a Thai professional)

Wave F ships without all of them — each card plans the mechanism, a mock and a flag-off state — but nothing in it
may claim a legal or commercial fact until these are answered.

| # | Decision | Default a card ships meanwhile | Cards |
| --- | --- | --- | --- |
| 14 | **Thai tax and e-invoicing.** Does the company issue a 7% VAT tax invoice itself, through a Revenue-Department-approved e-tax service, or through a merchant of record? What are the document series, withholding rules, and does the accountant accept a PromptPay QR on the invoice? | Invoice *shape* only: company/tax-id fields, VAT as its own line, a dry-run number, `Pricing not set`, no filing | T-755–T-758 |
| 15 | **PDPA position.** Who is controller and who is processor for each camera deployment; what is the DSAR deadline the product counts (30 days is the plan); which retention floors are contractual? Needs a Thai lawyer before any of it is asserted in copy | Case object, countdown, draft register, dry-run erasure and a certificate template labelled draft | T-747, T-750–T-754, T-760–T-761 |
| 16 | **Notification channels.** Which LINE Official Account sends alerts, who owns it, and what the acknowledgement ladder escalates to | One channel row, a token in `secretbox`, mock delivery in tests | T-714, T-720 |
| 17 | **Offline licence and partner model.** Is an air-gapped install sold, leased or free; does a partner resell child workspaces and at what margin | A signed licence-file verifier (offline, no phone-home by default) and a partner console with `ยังไม่กำหนดราคา` | T-732, T-733 |
| 18 | **Who writes the Thai copy.** In-house, agency, or the implementing agent? Whether the workspace default is Thai or browser-derived | The card authors real Thai for every string they add; browser-derived default; the switch ships | T-600–T-603 and every card's `lib/i18n.ts` keys |
| 19 | **The line's fail-safe.** When the model is down or the PLC link drops, does the line reject by default or stop by default? A missed NG part is a liability, not a bug | `stop` by default, both modes configurable, no silent pass, the policy shown on the station screen | T-688, T-689 |

---

## 5. What was deliberately not planned

- **A second UI.** `web/` is frozen; all frontend cards target `apps/frontend`.
- **A second annotation engine.** Every editor card extends the existing Konva editor and its JSON
  annotation storage; no card introduces a parallel document model.
- **A second inference server.** Self-hosting links to and documents `apps/inference`; no card rewrites it.
- **Vendor SDKs.** No card adds one. Where a vendor is the only real answer, the card ships an interface
  and a mock, and §4 records the decision.
- **Re-implementing HAVE flows.** The guard cards assert them; they do not rewrite them. The two BEYOND features
  that are HAVE (`G1.1` consensus, `G2.10` suspect labels) get cards only for the part their own gap cell names.
- **A rewrite of the login screen** (see §4.2 #13).
- **Six BEYOND features its own §4 names as non-goals** — planogram (`G6.10`), fruit grading (`G6.12`),
  parameter sweeps (`G2.1`), the plugin marketplace (`G1.12`, `G2.17`) and on-camera analytics (`G3.18`). The owner
  directive plans every row, so all six still have cards; each card's Notes open with `Owner-hold:` and each ships
  behind its flag, so nothing is scheduled by accident. (`G1.14` 3D/LiDAR and `G1.15` DICOM were dropped from the
  BEYOND matrix before it reached this lane, and have no card.)
- **A second locale.** `G5.23` (an i18n framework with RTL) folds into `G5.22`: Thai first, one catalogue and one
  switch, no framework for markets we do not sell to.

---

## 6. Execution order

Waves are ordered by user value, but three structural facts decide the real schedule.

```
Phase 0  G  T-001…T-007        regression guards, baseline green (19 h)
Phase 0b G2 T-520…T-525        UI clean-up from the design audit          (12 h)
Phase 0c G3 T-050…T-059        code clean-up: lint gate, dead code, duplicates (22 h)
Phase 1  E  E-frame (17)       tokens, routes /p/, rails, stage frame, top bar, palette  (43 h)
Phase 1b X  10 cards           MCP server for AI agents: 16 tools, 2 transports (27.5 h)
Phase 2  A  47 cards           trial blockers                        (132.5 h)
Phase 3  B  149 cards          editor / train / eval / workflow core (419 h)
Phase 4  C  97 cards           data and people                       (278.5 h)
Phase 5  F  171 cards          BEYOND capability layer (Thai first)  (488 h)
Phase 6  D  52 cards           commercial and enterprise (owner-gated) (151 h)
Phase 7  E  E-finish (12)      polish, mobile, a11y proof, copy deck  (32 h)
```

**Why F runs before D.** Both sit after wave C and before E-finish, but wave D is inert until the owner answers §4.1
(provider, prices, licence) while wave F's Musts are product: Thai UI, the label-quality loop, the line-side loop,
defensible auto-label and the vertical packs. F also has no dependency on a vendor, so it can start the day C merges.
If the owner answers §4.1 early, D and F may run in parallel — they touch different files, and §7's matrix names the
few shared registries.

**E-frame, before wave A.** Routes, rails and tokens are the ground every later screen stands on:
`T-470` tokens, `T-471` type floor, `T-472` glass, `T-473` Thai truncation, `T-474` `/p/` routes,
`T-475` link helper, `T-476` workspace rail, `T-477` stage manifest, `T-478` project rail, `T-479` stage
tabs, `T-480` top bar, `T-481` job tray, `T-482` command palette, `T-483` project overview, `T-484`
overview header, `T-493` icons, `T-495` colour source. E-finish runs last: `T-485`–`T-492`, `T-494`,
`T-496`–`T-498`.

**Wave B is four parallel families**, not one queue. Split lanes by file family so no two lanes share a
hot file: editor (`T-120`–`T-174`), versions (`T-190`–`T-232`), train/eval/models (`T-250`–`T-296`),
workflow/deploy (`T-310`–`T-359`). Each lane merges through the same captain; a lane never edits another
lane's exclusive file.

**Wave C families:** dataset and query (`T-060`–`T-104`), metadata/connectors (`T-070`–`T-086`), people
and keys (`T-174`, `T-380`–`T-403`), audit/policy (`T-400`–`T-411`). Wave D families: billing
(`T-412`–`T-426`), identity and data protection (`T-427`–`T-449`), enterprise surfaces
(`T-352`–`T-359`, `T-439`–`T-449`). **Wave F families:** Thai (`T-600`–`T-603`), label quality
(`T-610`–`T-633`), auto-label (`T-640`–`T-665`), industrial (`T-670`–`T-697`), Thai market (`T-710`–`T-733`),
enterprise (`T-740`–`T-779`), training depth (`T-780`–`T-805`). Every F band owns its own new modules, so the seven
can run concurrently once Thai's catalogue has landed; they meet only in the registries §7 lists.

**Serialisation rules**
1. **Migrations.** One migration-bearing branch merges at a time. If a card's Files include
   `app/models/*.py` plus an `app/schema/*.py` block, it is migration-bearing; run the existing-database
   test before merge.
2. **Registries.** Append one line per card: `routers/__init__.py`, `models/__init__.py`,
   `services/flags.py`, nav registries, route tables. Merge ascending card id within a wave.
3. **Generated files.** `openapi.json` and `api-types.gen.ts` are regenerated after every merge that
   changed the contract; a conflict there is resolved by re-running the two commands, never by hand.
4. **Rewrites before polish.** Cards that rewrite a file (`Editor.tsx`, `Dataset.tsx`, `Versions.tsx`,
   `Train.tsx`, `Models.tsx`, `Deploy.tsx`, `Home.tsx`, `ProjectPanel.tsx`, `TopBar.tsx`) land before any
   polish card touches the same file; the matrix gives the order.

---

## 6a. Wave tables

Every PARITY row appears exactly once per wave it touches, with the cards that close it. A row split
across waves appears in each wave with the cards for that wave.

### Wave G — regression guards (HAVE rows)

Test-only cards. Land them first: they pin the 72 HAVE flows so the 260+ later cards cannot regress them silently. Each guard extends existing tests where possible; no application code changes.

**7 cards · 19 agent-hours · 72 PARITY rows listed.**

#### G.1 Rows and the cards that close them

| Parity row | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| `1-F1.5` | API key created once, scoped, listed with usage | HAVE | G | T-001 |
| `1-F2.1` | Type-first creation that lands on upload | HAVE | G | T-001 |
| `1-F3.2` | Sidebar is the lifecycle; upload is the landing page | HAVE | E/G | T-001, T-477, T-478 |
| `1-F3.3` | Four-column annotate board is the labeler's home | HAVE | G | T-001 |
| `1-F3.4` | Counters appear where the decision is made | HAVE | G | T-001 |
| `1-F6.1` | Returning user sees folders then projects, admin tree beside | HAVE | G | T-001 |
| `1-F6.2` | A brand-new workspace has a designed empty state | HAVE | E/G | T-001, T-485 |
| `2-F2.1` | Drop ingest with a duplicate pre-check and a counted summary | HAVE | G | T-002 |
| `2-F2.9` | One refusal rule set on every ingest path | HAVE | G | T-002 |
| `2-F2.22` | Grid with hover selection and a contextual bulk bar | HAVE | G | T-002 |
| `2-F2.23` | Batch board as the dataset pipeline | HAVE | G | T-002 |
| `2-F2.37` | Health report whose charts are filters | HAVE | C/G | T-002, T-102, T-103 |
| `2-F2.38` | Cached health report with explicit staleness and regenerate | HAVE | A/G | T-002, T-104 |
| `2-F2.39` | Split decided at ingest and stored on the image | HAVE | A/G | T-002, T-104 |
| `2-F2.40` | Bulk split change from a selection | HAVE | G | T-002 |
| `2-F2.42` | Versions freeze their own split assignment | HAVE | G | T-002 |
| `2-F2.43` | Single-image removal | HAVE | G | T-002 |
| `2-F2.44` | Bulk removal with a count-bearing confirm | HAVE | A/G | T-002, T-104 |
| `3-F3.1` | Editor shell: tool rail, canvas, side panels, header | HAVE | E/G | T-003, T-497, T-498 |
| `3-F3.9` | Bounding box tool | HAVE | G | T-003 |
| `3-F3.12` | One-click object isolation with click-to-grow/shrink | HAVE | B/G | T-003, T-172 |
| `3-F3.13` | Keypoints with per-point visibility | HAVE | G | T-003 |
| `3-F3.25` | Proposal vs committed label is visible | HAVE | B/G | T-003, T-151 |
| `3-F3.28` | Free preview on sample images | HAVE | B/G | T-003, T-173 |
| `3-F3.33` | Background progress, then ordinary review | HAVE | B/G | T-003, T-173 |
| `3-F3.35` | Class picker with create-in-place | HAVE | G | T-003 |
| `3-F3.37` | Class colour, counts, hotkeys | HAVE | G | T-003 |
| `3-F3.39` | Image tags | HAVE | G | T-003 |
| `3-F3.41` | Layering through the list and a context menu | HAVE | G | T-003 |
| `3-F3.42` | Hide a shape; delete a shape | HAVE | G | T-003 |
| `3-F3.44` | Four-column job board | HAVE | G | T-003 |
| `3-F3.50` | Per-labeler and per-project label statistics | HAVE | G | T-003 |
| `3-F3.51` | Keyboard reference, and remapping | HAVE | C/G | T-003, T-174 |
| `4-F4.1` | Frozen point-in-time snapshot | HAVE | G | T-004 |
| `4-F4.2` | Sequential number plus human name | HAVE | B/G | T-004, T-232 |
| `4-F4.8` | Several trainings per version | HAVE | G | T-004 |
| `4-F4.9` | Five-step wizard, all steps reachable | HAVE | A/G | T-004, T-194 |
| `4-F4.10` | Step 1 states what enters the version | HAVE | A/B/G | T-004, T-196, T-232 |
| `4-F4.11` | Step 2 split percentages with inline validation | HAVE | G | T-004 |
| `4-F4.17` | Auto-orient | HAVE | G | T-004 |
| `4-F4.19` | Grayscale preprocessing | HAVE | G | T-004 |
| `4-F4.28` | Augmentation scope and offline rationale | HAVE | G | T-004 |
| `4-F4.36` | Async, cached, repeatable export | HAVE | G | T-004 |
| `4-F4.40` | Class balance per split | HAVE | G | T-004 |
| `4-F4.41` | Dimension and aspect-ratio insights | HAVE | G | T-004 |
| `4-F4.44` | Report caching with an explicit staleness field | HAVE | A/G | T-004, T-104 |
| `4-F4.45` | Per-version analytics and version-to-version comparison | HAVE | G | T-004 |
| `5-F5.1` | Project model table with metric, version, licence | HAVE | B/G | T-005, T-263 |
| `5-F5.2` | Many models per version | HAVE | G | T-005 |
| `5-F5.12` | Submit with a queued acknowledgement where results will land | HAVE | G | T-005 |
| `5-F5.16` | Live training graphs and loss curves | HAVE | B/G | T-005, T-272 |
| `5-F5.18` | Continue training from the last checkpoint | HAVE | G | T-005 |
| `5-F5.20` | Evaluation runs automatically after training | HAVE | G | T-005 |
| `5-F5.23` | Confusion matrix with cell drill-down and GT/prediction flip | HAVE | G | T-005 |
| `5-F5.35` | Explicit production pointer (Roboflow's own gap) | HAVE | G | T-005 |
| `5-F5.38` | Licence shown per model and per deploy target | HAVE | G | T-005 |
| `5-F5.39` | Train permission split from read | HAVE | G | T-005 |
| `5-F5.43` | Version not ready or invalid | HAVE | G | T-005 |
| `5-F5.44` | Unsupported task + architecture | HAVE | G | T-005 |
| `5-F5.47` | Workspace out of credits | HAVE | G | T-005 |
| `5-F5.50` | Ambiguous training reference | HAVE | G | T-005 |
| `5-F5.52` | Anomaly-project data rules | HAVE | B/G | T-005, T-296 |
| `6-F6.9` | Confidence slider with a live preview on the deploy surface | HAVE | G | T-006 |
| `6-F6.11` | Immutable model identity with a production pointer | HAVE | G | T-006 |
| `6-F6.22` | Block config panel with required ports first | HAVE | G | T-006 |
| `6-F6.35` | Detect → count → draw examples in the docs | HAVE | G | T-006 |
| `6-F6.43` | Zones, lines and counters drawn on the frame | HAVE | G | T-006 |
| `7-F7.7` | Remove a member or leave, last-admin guard | HAVE | G | T-007 |
| `7-F7.15` | Cycle breakdown plus limits meters | HAVE | G | T-007 |
| `7-F7.26` | Create a key with a one-time reveal | HAVE | G | T-007 |
| `7-F7.34` | Public publishable key for browser inference | HAVE | G | T-007 |
| `7-F7.57` | Create a workspace from a first-run screen | HAVE | G | T-007 |

#### G.2 Cards

| Task | Title | Parity rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-001](T-001.md) | Guard area 1: workspace, projects, first run | `1-F1.5`, `1-F2.1`, `1-F3.2`, `1-F3.3`, `1-F3.4`, `1-F6.1`, `1-F6.2` | 2.5 | no | none (must land before the first area-1 card merges) |
| [T-002](T-002.md) | Guard area 2: upload, dataset grid, splits, deletion, health | `2-F2.1`, `2-F2.9`, `2-F2.22`, `2-F2.23`, `2-F2.37`, `2-F2.38`, `2-F2.39`, `2-F2.40`, `2-F2.42`, `2-F2.43`, `2-F2.44` | 3 | no | none (land before the first area-2 card); T-002 owns all eleven area-2 HAVE rows per `_BRIEF.md` §6b |
| [T-003](T-003.md) | Guard area 3: editor shell, tools, proposals, board, keyboard | `3-F3.1`, `3-F3.9`, `3-F3.12`, `3-F3.13`, `3-F3.25`, `3-F3.28`, `3-F3.33`, `3-F3.35`, `3-F3.37`, `3-F3.39`, `3-F3.41`, `3-F3.42`, `3-F3.44`, `3-F3.50`, `3-F3.51` | 3 | no | none (land before the first area-3 card) |
| [T-004](T-004.md) | Guard area 4: version snapshot, wizard, preprocessing, export | `4-F4.1`, `4-F4.2`, `4-F4.8`, `4-F4.9`, `4-F4.10`, `4-F4.11`, `4-F4.17`, `4-F4.19`, `4-F4.28`, `4-F4.36`, `4-F4.40`, `4-F4.41`, `4-F4.44`, `4-F4.45` | 3 | no | none (land before the first area-4 card) |
| [T-005](T-005.md) | Guard area 5: model table, train entry, evaluation, alias | `5-F5.1`, `5-F5.2`, `5-F5.12`, `5-F5.16`, `5-F5.18`, `5-F5.20`, `5-F5.23`, `5-F5.35`, `5-F5.38`, `5-F5.39`, `5-F5.43`, `5-F5.44`, `5-F5.47`, `5-F5.50`, `5-F5.52` | 3 | no | none (land before the first area-5 card) |
| [T-006](T-006.md) | Guard area 6: deploy threshold, workflow blocks, zones | `6-F6.9`, `6-F6.11`, `6-F6.22`, `6-F6.35`, `6-F6.43` | 2.5 | no | none (land before the first area-6 card) |
| [T-007](T-007.md) | Guard area 7: membership removal, usage limits, keys, first run | `7-F7.7`, `7-F7.15`, `7-F7.26`, `7-F7.34`, `7-F7.57` | 2 | no | none (land before the first area-7 card) |

### Wave G2 — UI clean-up (design audit)

Six cards from the independent design audit of 2026-11-17 ([`docs/audits/ui/UI-AUDIT.md`](../../../audits/ui/UI-AUDIT.md)).
The audit found 54 defects; 26 of the 36 app defects already have an owner among the cards below, and those
are mapped in the audit rather than re-planned here. These six close nine of the remaining ten. They land
after the guards and before E-frame, so E rebases onto a smaller diff.

**6 cards · 12 agent-hours · 0 PARITY rows (defects, not gaps).** Part index: [`.parts/wave-g2.md`](.parts/wave-g2.md).

| Audit | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| A8, A9 | Dataset grid at 375 and a count that names the total | defect | G2 | T-520 |
| A10 | A flag-gated surface says it is off instead of redirecting | defect | G2 | T-521 |
| A11 | Deploy snippet: the Copy button stops covering the first line | defect | G2 | T-522 |
| A6, A7 | Chart legends at AA, and an empty series says so | defect | G2 | T-523 |
| A21 | Playground: the vendor appears once per group | defect | G2 | T-524 |
| A18, A19 | The tour stops covering the card it points at | defect | G2 | T-525 |

| Task | Title | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- |
| [T-520](T-520.md) | Dataset grid reflows at 375, and the count tells the truth | 3 | no | none |
| [T-521](T-521.md) | A surface that is off says so, instead of bouncing to the dataset | 2.5 | no | none |
| [T-522](T-522.md) | Deploy snippet: the Copy button stops covering the first line | 1 | no | none |
| [T-523](T-523.md) | A chart with no series says so, and every legend reads at AA | 2.5 | no | none |
| [T-524](T-524.md) | Playground: the vendor appears once, not ten times | 1 | no | none |
| [T-525](T-525.md) | The tour stops covering what it points at | 2 | no | none |

### Wave G3 — code clean-up (independent code audit)

Ten cards from the independent code audit of 2026-11-17 ([`docs/audits/code/CODE-AUDIT.md`](../../../audits/code/CODE-AUDIT.md)).
The audit measured the tree with the tools CI already pins (ruff 0.17.3, vulture, radon, tsc) and found no dead
files, no unused backend dependency and average backend complexity 4.95 (A) — but **no lint gate over app code
at all** (825 ruff findings, with two tests asserting the gate stays off), 1,510 lines of orphan QA scripts,
63 modules that each log in by hand and three files over 1,000 lines. These ten cards remove an estimated
1,940 lines and one dependency, and land after G2 and before E-frame so E rebases onto a smaller diff.

**10 cards · 22 agent-hours · 0 PARITY rows (clean-up, not gaps).** Part index: [`.parts/g3.md`](.parts/g3.md).

| Audit | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| Lint gate (94 pyflakes findings, 0 gate) | `ruff check apps/backend` in CI and pre-commit; delete the four assertions that pin the gap open | defect | G3 | T-050 |
| Four identical box-IoU bodies | one `services/boxes.py` helper | dead duplication | G3 | T-051 |
| Seven verified dead backend symbols, one dead probe | delete them | dead code | G3 | T-052 |
| Seven double-encoded strings, one written to the DB | repair the literals and guard the repo | defect | G3 | T-053 |
| Two dead exports, four never-passed props, one orphan CSS class | delete them; one permission query reuses the shared hook | dead code | G3 | T-054 |
| 9 `pct`, 3 `fmtInt`, 3 `fmtBytes`, 2 `fmtTime` in two units | one `lib/format.ts` | duplication | G3 | T-055 |
| 63 modules with their own login helper, 12 `_schema` fixtures | one helper in `conftest.py` | duplication | G3 | T-056 |
| Empty root `tests/`, 10 orphan scripts, stale gate docs | delete; drop the redundant `playwright` pin | dead weight | G3 | T-057 |
| `Settings.tsx` 1,168 lines, 12 pages | split the 541-line account/security block out | file size | G3 | T-058 |
| Two chart toolkits sharing four concepts | one theme reader and colour normaliser | duplication | G3 | T-059 |

| Task | Title | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- |
| [T-050](T-050.md) | Gate app code on pyflakes and clear the 94 findings | 3 | no | none (lands first; every G3 card rebases on it) |
| [T-051](T-051.md) | One box-IoU helper instead of four | 1.5 | no | none |
| [T-052](T-052.md) | Delete the dead backend surface the audit proved | 2.5 | yes | T-050 (`adapters/base.py`) |
| [T-053](T-053.md) | Repair the seven double-encoded strings in images | 1 | no | none |
| [T-054](T-054.md) | Delete dead frontend exports, props and CSS | 1.5 | no | T-525 (`index.css`) |
| [T-055](T-055.md) | One format module for numbers, bytes, percentages, clocks | 2.5 | no | T-523 (`Models.tsx`) |
| [T-056](T-056.md) | One login helper and one schema fixture for the backend tests | 3 | no | T-050 (nine shared test modules) |
| [T-057](T-057.md) | Remove the empty tests tree, orphan scripts and stale gate docs | 3 | no | T-050 (`ci.yml`) |
| [T-058](T-058.md) | Split Settings.tsx into its twelve pages' three files | 2 | no | none |
| [T-059](T-059.md) | Point project insights at the shared chart helpers | 2 | no | none |

The 18 frame defects in the audit (F1–F18) are the design lane's: Thai copy that is not Thai, prices the
owner has not set, a QR that scans as nothing, and a dark-mode Approve that fails AA. No code card closes
them.

### Wave A — trial blockers

A buyer's first hour. Editor safety, review speed, editable geometry, "nothing here", the query bar, the version preview, auto-label policy, the deploy hub, the public page and the nav order. Every card here is demo-visible.

**47 cards · 132.5 agent-hours · 52 PARITY rows listed.**

#### A.1 Rows and the cards that close them

| Parity row | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| `1-F1.1` | One-screen workspace creation with plan choice inline | PARTIAL | A/D | T-010, T-011 |
| `1-F2.2` | Eight task types with outcome-worded descriptions | PARTIAL | A | T-017 |
| `1-F3.1` | Project "about" page with description and public URL | MISSING | A | T-023 |
| `1-F4.3` | Query language with chips, negation, class counts | PARTIAL | A | T-060 |
| `1-F5.1` | Publish is a menu action plus a licence, with a workspace kill switch | PARTIAL | A | T-033, T-034 |
| `1-F5.2` | Visitor sees a dataset page whose CTA is "copy into my account" | MISSING | A | T-035, T-036 |
| `1-F5.3` | Fork errors enumerated (402/403/404/409/422) | MISSING | A | T-032, T-037 |
| `2-F2.2` | Pre-labelled upload with an overwrite switch | PARTIAL | A/C | T-063, T-068 |
| `2-F2.20` | Fork a public dataset into the workspace | MISSING | A | T-032, T-037 |
| `2-F2.27` | One query language over class, tag, split, size, counts, date | PARTIAL | A | T-060, T-061, T-062 |
| `2-F2.35` | Exact dedupe that restores a removed image with its labels | PARTIAL | A | T-097 |
| `2-F2.38` | Cached health report with explicit staleness and regenerate | HAVE | A/G | T-002, T-104 |
| `2-F2.39` | Split decided at ingest and stored on the image | HAVE | A/G | T-002, T-104 |
| `2-F2.44` | Bulk removal with a count-bearing confirm | HAVE | A/G | T-002, T-104 |
| `3-F3.2` | Pan, zoom and zoom lock | PARTIAL | A | T-120 |
| `3-F3.3` | Image-to-image navigation with sticky settings | PARTIAL | A | T-120 |
| `3-F3.8` | Select, move, resize, reclass | PARTIAL | A | T-123, T-124 |
| `3-F3.10` | Polygon tool with two closing gestures | PARTIAL | A | T-125 |
| `3-F3.16` | Classification-only, single and multi-label | PARTIAL | A | T-126 |
| `3-F3.18` | Distinguish "empty" from "not looked at" | MISSING | A | T-127 |
| `3-F3.19` | Undo, redo, repeat previous | PARTIAL | A | T-122 |
| `3-F3.27` | Classes as prompts with per-class descriptions | PARTIAL | A | T-130 |
| `3-F3.29` | Per-class confidence carried into the job | PARTIAL | A | T-130 |
| `3-F3.32` | Cost estimate and existing-annotation policy | PARTIAL | A | T-131, T-132 |
| `3-F3.43` | Duplicate a shape, or carry the previous set forward | MISSING | A | T-122 |
| `3-F3.46` | Approve/reject per image at keyboard speed, with bulk | PARTIAL | A | T-128, T-129 |
| `3-F3.52` | Silent autosave with one explicit gate | PARTIAL | A | T-121 |
| `3-F3.54` | Model unavailable shown as a disabled option with a reason | PARTIAL | A/B | T-131, T-140, T-141 |
| `3-F3.55` | Empty project, read-only image, two editors on one image | PARTIAL | A/B | T-121, T-164 |
| `4-F4.9` | Five-step wizard, all steps reachable | HAVE | A/G | T-004, T-194 |
| `4-F4.10` | Step 1 states what enters the version | HAVE | A/B/G | T-004, T-196, T-232 |
| `4-F4.13` | Preprocessing picker with per-step preview | PARTIAL | A | T-192, T-198, T-199 |
| `4-F4.15` | Output multiplier with an estimate | PARTIAL | A/B | T-191, T-192, T-214 |
| `4-F4.16` | Confirm summary and a generated result page | PARTIAL | A/B | T-194, T-219, T-220, T-221 |
| `4-F4.18` | Resize with six modes | PARTIAL | A | T-197, T-198 |
| `4-F4.21` | Isolate objects into crops | MISSING | A/B | T-198, T-202 |
| `4-F4.23` | Tiling: grid, fixed size, fixed aspect | PARTIAL | A/B | T-192, T-198, T-204, T-205 |
| `4-F4.26` | Filter by tag with require/exclude/allow | MISSING | A | T-192, T-195, T-196 |
| `4-F4.27` | Pipeline order and conflicts stated | PARTIAL | A/B | T-190, T-191, T-193, T-198, T-205 |
| `4-F4.29` | Multiplier semantics and plan cap | PARTIAL | A/B | T-190, T-214 |
| `4-F4.44` | Report caching with an explicit staleness field | HAVE | A/G | T-004, T-104 |
| `6-F6.1` | One chooser that separates real-time from bulk | MISSING | A | T-310, T-311 |
| `6-F6.2` | Per-request endpoint that hides its own cold start | PARTIAL | A | T-317 |
| `6-F6.5` | Self-hosted inference server at no credit cost | PARTIAL | A | T-312 |
| `6-F6.7` | Go-live checklist that names what to retry | MISSING | A | T-318 |
| `6-F6.8` | Runtime picker that rewrites the snippets | MISSING | A | T-313, T-314 |
| `6-F6.10` | Request shape follows the workflow's declared inputs | PARTIAL | A | T-315, T-316 |
| `6-F6.12` | Error codes and credit rules written for the caller | PARTIAL | A | T-318 |
| `6-F6.45` | Install paths per platform with a one-command default | PARTIAL | A | T-312 |
| `7-F7.53` | Publish a project with an explicit licence dialog | PARTIAL | A | T-033, T-034 |
| `7-F7.54` | Public project page with sharing statistics and badges | MISSING | A | T-035, T-036 |
| `7-F7.55` | Fork a public dataset into the workspace | MISSING | A | T-032, T-037 |

#### A.2 Cards

| Task | Title | Parity rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-010](T-010.md) | Name the workspace and show its address before submit | `1-F1.1` | 3 | yes | none |
| [T-017](T-017.md) | Eight project types with outcome wording, plus "ask for another" | `1-F2.2` | 3 | no | none |
| [T-023](T-023.md) | Project description and its public link, written where the author is | `1-F3.1` | 3 | yes | T-017 (project payload shape is settled) |
| [T-032](T-032.md) | Clone or fork a project with enumerated failure codes | `1-F5.3`, `2-F2.20`, `7-F7.55` | 3 | yes | T-017 (type ids on the copy) |
| [T-033](T-033.md) | Publish a project: licence choice and an explicit content check | `1-F5.1`, `7-F7.53` | 2 | yes | T-023 (description is what a visitor reads) |
| [T-034](T-034.md) | Make public / make private dialog with the content warning | `1-F5.1`, `7-F7.53` | 3 | yes | T-033 (publish endpoint), T-023 (description + public path) |
| [T-035](T-035.md) | Public dataset payload: description, classes, licence, sample images | `1-F5.2`, `7-F7.54` | 3 | yes | T-033 (publishing sets visibility and path), T-023 (description) |
| [T-036](T-036.md) | Public dataset page a visitor can read and copy from | `1-F5.2`, `7-F7.54` | 3 | no | T-035 (the payload), T-032 (the copy endpoint behind the CTA) |
| [T-037](T-037.md) | Copy dialog: progress, five precise failures, land on versions | `1-F5.3`, `2-F2.20`, `7-F7.55` | 3 | no | T-036 (the page that hosts the dialog), T-032 (the endpoint and its codes) |
| [T-060](T-060.md) | Query grammar and compiler for the dataset grid | `2-F2.27`, `1-F4.3` | 3 | no | none |
| [T-061](T-061.md) | Serve the query language from the images route | `2-F2.27` | 3 | no | T-060 (compiler) |
| [T-062](T-062.md) | One filter bar, a filters popover and saved-view chips | `2-F2.27` | 3 | no | T-061 (query parameter, count header) |
| [T-063](T-063.md) | Replace-annotations switch and orphan-label report | `2-F2.2` | 2.5 | no | none |
| [T-097](T-097.md) | Itemise duplicates and revive a removed image with its labels | `2-F2.35` | 2.5 | no | T-063 (the upload result fields this extends) |
| [T-104](T-104.md) | Data honesty: explain freshness, name the split fallback, say what delete keeps | `2-F2.38`, `2-F2.39`, `2-F2.44`, `4-F4.44` | 2.5 | no | none |
| [T-120](T-120.md) | Zoom, zoom lock, and a sticky editor session | `3-F3.2`, `3-F3.3` | 3 | no | none |
| [T-121](T-121.md) | Honest saving: flush before leaving, refuse a stale write | `3-F3.52`, `3-F3.55` | 3 | no | none |
| [T-122](T-122.md) | Duplicate a shape, or repeat the previous image's labels | `3-F3.43`, `3-F3.19` | 2.5 | no | none |
| [T-123](T-123.md) | Geometry module for moving polygons, rotated boxes and keypoints | `3-F3.8` | 3 | no | none |
| [T-124](T-124.md) | Canvas handles: drag a polygon, a rotated box, a joint | `3-F3.8` | 3 | no | T-123 (geometry module it calls) |
| [T-125](T-125.md) | Add, remove and drag polygon vertices | `3-F3.10` | 3 | no | T-124 (the handle layer it extends) |
| [T-126](T-126.md) | Classification single- vs multi-label is reachable | `3-F3.16` | 2 | no | none |
| [T-127](T-127.md) | Mark an image empty (a real negative sample) | `3-F3.18` | 3 | no | none |
| [T-128](T-128.md) | Review at keyboard speed: a, r, u | `3-F3.46` | 2.5 | no | T-127 (empty images are the only zero-label approvals) |
| [T-129](T-129.md) | Bulk review asks first: count, classes, reason | `3-F3.46` | 3 | no | T-128 (the same decision rules, applied in bulk) |
| [T-130](T-130.md) | One prompt and one threshold per class | `3-F3.27`, `3-F3.29` | 3 | no | none |
| [T-131](T-131.md) | Estimate the spend, and choose what happens to existing labels | `3-F3.32`, `3-F3.54` | 3 | yes | none |
| [T-132](T-132.md) | The auto-label summary sheet | `3-F3.32` | 2.5 | no | T-131 (the estimate and policy it displays) |
| [T-190](T-190.md) | Recipe contract, pipeline order and plan caps | `4-F4.27`, `4-F4.29` | 3 | no | none |
| [T-191](T-191.md) | Validate version create and expose plan limits | `4-F4.27`, `4-F4.15` | 2 | no | T-190 (recipe contract) |
| [T-192](T-192.md) | Version preview endpoint: counts, conflicts, sample, tiles | `4-F4.13`, `4-F4.23`, `4-F4.15`, `4-F4.26` | 3 | yes | T-190 (normalize/validate), T-191 (router shape) |
| [T-193](T-193.md) | Frontend recipe mirror with node-side copy | `4-F4.27` | 2.5 | no | T-190 (codes), T-191 (limits shape) |
| [T-194](T-194.md) | Split the version screens and build the wizard shell | `4-F4.16`, `4-F4.9` | 3 | no | T-191 (limits), T-193 (conflict copy) |
| [T-195](T-195.md) | Tag rules select the version's source pool | `4-F4.26` | 3 | no | T-190 (recipe normalize/validate) |
| [T-196](T-196.md) | Source step: pool counts and the tag-rule matrix | `4-F4.26`, `4-F4.10` | 2.5 | no | T-192 (preview counts), T-194 (shell), T-195 (rules + helper) |
| [T-197](T-197.md) | Six resize modes with label-correct geometry | `4-F4.18` | 3 | no | T-190 (mode validation) |
| [T-198](T-198.md) | Preprocessing step: an ordered, add-and-remove pipeline | `4-F4.13`, `4-F4.18`, `4-F4.21`, `4-F4.23`, `4-F4.27` | 3 | no | T-192 (preview), T-193 (conflicts), T-194 (shell), T-197 (modes) |
| [T-199](T-199.md) | Preview panel with labels drawn on the transformed image | `4-F4.13` | 2 | no | T-192 (preview payload), T-198 (host step) |
| [T-310](T-310.md) | One runtime catalogue, one response contract | `6-F6.1` | 3 | no | none |
| [T-311](T-311.md) | A chooser that separates real-time from bulk | `6-F6.1` | 3 | no | T-310 (the catalogue it renders) |
| [T-312](T-312.md) | Self-hosting you can start from inside the product | `6-F6.5`, `6-F6.45` | 3 | no | T-311 (the row that opens it) |
| [T-313](T-313.md) | Snippets and an endpoint card that follow the runtime | `6-F6.8` | 3 | yes | T-310 (runtime ids), T-312 (the self-hosted host) |
| [T-314](T-314.md) | Deploy and test: prove it works, then ship it | `6-F6.8` | 3 | no | T-313 (endpoint card), T-310 (catalogue) |
| [T-315](T-315.md) | A workflow declares the inputs it will accept | `6-F6.10` | 3 | no | none (extends `services/workflows.py`) |
| [T-316](T-316.md) | Call a published workflow from outside | `6-F6.10` | 3 | yes | T-315 (the contract), T-310 (the envelope) |
| [T-317](T-317.md) | Say when a request paid the cold start | `6-F6.2` | 2.5 | no | T-310 (the envelope fields) |
| [T-318](T-318.md) | What went wrong, and whether it cost anything | `6-F6.12`, `6-F6.7` | 3 | no | T-310 (status codes it documents) |

### Wave B — editor, train and workflow core

The product core. Editor tools, assist, history, masks; versions and augmentation; training, evaluation and models; workflows and deploy. Run as four families (editor / versions / train-eval / workflow-deploy) with disjoint exclusive files.

**149 cards · 419 agent-hours · 124 PARITY rows listed.**

#### B.1 Rows and the cards that close them

| Parity row | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| `1-F1.2` | Three setup questions that seed an assistant | MISSING | B | T-012 |
| `1-F1.3` | Assistant as the post-signup home, with background-task list | MISSING | B | T-013, T-014, T-015, T-016 |
| `1-F2.3` | The type silently drives tools, import, training and export | PARTIAL | B | T-018, T-019 |
| `2-F2.6` | Video upload with a frame-extraction dialog | PARTIAL | B | T-071, T-072 |
| `2-F2.24` | Image detail view with attributes and split inside the editor | PARTIAL | B | T-087 |
| `2-F2.26` | Export a single image, a version or a query result | PARTIAL | B/C | T-087, T-089 |
| `2-F2.29` | "More like this" from an image already open | PARTIAL | B | T-088 |
| `2-F2.41` | Percentage rebalance with three move policies | PARTIAL | B | T-100, T-101 |
| `3-F3.4` | Display-only adjustment plus a global overlay hide | PARTIAL | B | T-138 |
| `3-F3.5` | Measurement guide in real units | MISSING | B | T-161 |
| `3-F3.6` | Drawer with annotation list, tags, image facts | PARTIAL | B | T-161 |
| `3-F3.7` | Look-alike search from the open image | MISSING | B | T-162 |
| `3-F3.11` | Brush / pixel mask | MISSING | B | T-133, T-134, T-135 |
| `3-F3.12` | One-click object isolation with click-to-grow/shrink | HAVE | B/G | T-003, T-172 |
| `3-F3.14` | Skeleton definition screen | PARTIAL | B | T-149 |
| `3-F3.15` | Video timeline with per-class action segments | MISSING | B | T-146, T-147, T-148 |
| `3-F3.20` | Multi-select plus convert, merge and order menu | PARTIAL | B | T-136, T-137 |
| `3-F3.21` | Label assist that persists across images | PARTIAL | B | T-139, T-140 |
| `3-F3.22` | Foundation-model prompt on open with counted accept | MISSING | B | T-150, T-151, T-152 |
| `3-F3.23` | Text prompt over the open image | MISSING | B | T-153 |
| `3-F3.24` | Example-box prompting with negative examples | MISSING | B | T-154, T-155 |
| `3-F3.25` | Proposal vs committed label is visible | HAVE | B/G | T-003, T-151 |
| `3-F3.26` | Auto-label entry, model catalogue, output shape | PARTIAL | B | T-141 |
| `3-F3.28` | Free preview on sample images | HAVE | B/G | T-003, T-173 |
| `3-F3.30` | Correct the preview in words | MISSING | B | T-156, T-157 |
| `3-F3.31` | Saved workflow as labeller with class mapping | MISSING | B | T-158 |
| `3-F3.33` | Background progress, then ordinary review | HAVE | B/G | T-003, T-173 |
| `3-F3.34` | Video auto-label with frame sampling | MISSING | B | T-159, T-160 |
| `3-F3.45` | Assign with instructions and notifications | PARTIAL | B | T-142, T-143 |
| `3-F3.47` | Turn review off for solo work | MISSING | B | T-165 |
| `3-F3.49` | Per-image annotation history with revert | PARTIAL | B | T-144, T-145 |
| `3-F3.53` | Slow network, offline, decode failure | MISSING | B | T-163 |
| `3-F3.54` | Model unavailable shown as a disabled option with a reason | PARTIAL | A/B | T-131, T-140, T-141 |
| `3-F3.55` | Empty project, read-only image, two editors on one image | PARTIAL | A/B | T-121, T-164 |
| `4-F4.2` | Sequential number plus human name | HAVE | B/G | T-004, T-232 |
| `4-F4.3` | Version index with counts, exports, trainings | PARTIAL | B | T-217 |
| `4-F4.4` | Async generation with progress | PARTIAL | B | T-217, T-218 |
| `4-F4.5` | Delete with consequences and a trash window | PARTIAL | B | T-219 |
| `4-F4.6` | Copy a version's recipe onto newer data | MISSING | B | T-222 |
| `4-F4.7` | Saved recipe locked downstream and shown at train time | PARTIAL | B | T-222, T-256, T-261 |
| `4-F4.10` | Step 1 states what enters the version | HAVE | A/B/G | T-004, T-196, T-232 |
| `4-F4.12` | Rebalance with three strategies and class scoping | PARTIAL | B | T-100 |
| `4-F4.14` | Augmentation added one at a time, ordered | PARTIAL | B | T-208, T-215, T-216 |
| `4-F4.15` | Output multiplier with an estimate | PARTIAL | A/B | T-191, T-192, T-214 |
| `4-F4.16` | Confirm summary and a generated result page | PARTIAL | A/B | T-194, T-219, T-220, T-221 |
| `4-F4.20` | Auto-adjust contrast with three algorithms | PARTIAL | B | T-200 |
| `4-F4.21` | Isolate objects into crops | MISSING | A/B | T-198, T-202 |
| `4-F4.22` | Static crop by percentage | MISSING | B | T-201 |
| `4-F4.23` | Tiling: grid, fixed size, fixed aspect | PARTIAL | A/B | T-192, T-198, T-204, T-205 |
| `4-F4.24` | Modify classes: omit, rename, merge, regex | MISSING | B | T-206, T-207 |
| `4-F4.25` | Filter null images by percentage | PARTIAL | B | T-203 |
| `4-F4.27` | Pipeline order and conflicts stated | PARTIAL | A/B | T-190, T-191, T-193, T-198, T-205 |
| `4-F4.29` | Multiplier semantics and plan cap | PARTIAL | A/B | T-190, T-214 |
| `4-F4.30` | Fourteen basic augmentations with parameters | PARTIAL | B | T-208, T-209, T-210, T-215 |
| `4-F4.31` | Bounding-box-level augmentation variants | MISSING | B | T-211, T-215 |
| `4-F4.32` | Cutout and mosaic | MISSING | B | T-212, T-213, T-215 |
| `4-F4.33` | Guidance on what and how much to augment | PARTIAL | B | T-216 |
| `4-F4.34` | Export dialog with format, ZIP and snippet | PARTIAL | B | T-224, T-225 |
| `4-F4.35` | Format catalogue by project type | PARTIAL | B | T-226, T-227, T-228, T-229 |
| `4-F4.37` | Round-trip losses documented | PARTIAL | B | T-225 |
| `4-F4.46` | Pre-train warning about a weak version | PARTIAL | B | T-223, T-261 |
| `5-F5.1` | Project model table with metric, version, licence | HAVE | B/G | T-005, T-263 |
| `5-F5.4` | Row quick actions: deploy, copy id, evaluation, weights | PARTIAL | B | T-268 |
| `5-F5.5` | Architecture search engine (NAS) | MISSING | B | T-269, T-270, T-271, T-272 |
| `5-F5.6` | Train on the live dataset or a frozen version | PARTIAL | B | T-260, T-261 |
| `5-F5.7` | Architecture and size picker pre-filtered by task | PARTIAL | B | T-250, T-251, T-255 |
| `5-F5.8` | Starting weights: previous, public, public-dataset, random, ImageNet | PARTIAL | B | T-259 |
| `5-F5.9` | Speed preset plus a full recipe editor | PARTIAL | B | T-255, T-256 |
| `5-F5.10` | Credit cap with the minimum printed | PARTIAL | B | T-253, T-254 |
| `5-F5.11` | Cost and duration estimate with a long-run confirm | PARTIAL | B | T-252, T-254 |
| `5-F5.13` | Instant few-shot model | MISSING | B | T-274, T-275, T-276 |
| `5-F5.14` | Search backbone choice by deployment target | MISSING | B | T-273 |
| `5-F5.15` | Lifecycle states that separate stopped from failed | PARTIAL | B | T-263 |
| `5-F5.16` | Live training graphs and loss curves | HAVE | B/G | T-005, T-272 |
| `5-F5.17` | Stop early vs cancel, consequences stated | PARTIAL | B | T-264 |
| `5-F5.19` | Spend and logs during a run | PARTIAL | B | T-266 |
| `5-F5.21` | Threshold explorer that becomes the served default | PARTIAL | B | T-277 |
| `5-F5.22` | Per-class performance with counts | PARTIAL | B | T-278 |
| `5-F5.24` | Improvement recommendations and assistant handoff | PARTIAL | B | T-279, T-280 |
| `5-F5.25` | Visual-similarity failure clusters | PARTIAL | B | T-281, T-282 |
| `5-F5.26` | Median latency as a first-class number | MISSING | B | T-263 |
| `5-F5.27` | Side-by-side comparison on one version (accuracy vs latency) | PARTIAL | B | T-283, T-284 |
| `5-F5.28` | Task-appropriate metrics (OKS, mIoU, boundary) | PARTIAL | B | T-285, T-286 |
| `5-F5.29` | Evaluation for uploaded weights | MISSING | B | T-290 |
| `5-F5.30` | Application-level regression evals | MISSING | B | T-292, T-293, T-294, T-295 |
| `5-F5.31` | Upload custom weights, versioned or workspace-wide | MISSING | B | T-288, T-289 |
| `5-F5.33` | Stable, parseable model identity | PARTIAL | B | T-268 |
| `5-F5.34` | Legacy per-version model alias | MISSING | B | T-268 |
| `5-F5.36` | Starring search candidates | MISSING | B/C | T-257, T-271, T-272 |
| `5-F5.37` | Delete a run with the serving consequence stated | PARTIAL | B | T-267 |
| `5-F5.40` | Too few images | PARTIAL | B | T-261, T-262 |
| `5-F5.41` | Class imbalance | PARTIAL | B | T-261, T-262 |
| `5-F5.42` | Small validation or test split | PARTIAL | B | T-261, T-262 |
| `5-F5.45` | Licence restriction on self-hosting | PARTIAL | B | T-268 |
| `5-F5.46` | Time or credit cap reached mid-run | PARTIAL | B | T-265 |
| `5-F5.48` | Out of memory or GPU fault | PARTIAL | B | T-263 |
| `5-F5.49` | Concurrent runs | PARTIAL | B | T-262 |
| `5-F5.51` | Long or expensive run needs a confirmation | MISSING | B | T-254 |
| `5-F5.52` | Anomaly-project data rules | HAVE | B/G | T-005, T-296 |
| `5-F5.53` | Evaluation unavailable | PARTIAL | B | T-284, T-287 |
| `5-F5.54` | Evaluation stalled | PARTIAL | B | T-287 |
| `6-F6.14` | Monitoring dashboard over production requests | PARTIAL | B | T-335, T-336 |
| `6-F6.15` | Typed production event store | PARTIAL | B | T-337, T-338 |
| `6-F6.16` | Human verdicts on production predictions | PARTIAL | B | T-339 |
| `6-F6.17` | Review session that routes bad events into training | PARTIAL | B | T-340, T-341 |
| `6-F6.20` | Retention stated per surface and per plan | PARTIAL | B | T-338 |
| `6-F6.21` | Canvas builder with ports, auto-wire and layout modes | PARTIAL | B | T-320, T-321, T-322, T-323 |
| `6-F6.23` | Run panel for still, video and live camera | PARTIAL | B | T-324 |
| `6-F6.24` | Per-block caching with an explicit uncache | MISSING | B | T-325 |
| `6-F6.25` | Sinks switch that protects test runs | MISSING | B | T-326 |
| `6-F6.26` | Outputs node that is editable and reorderable | PARTIAL | B | T-327 |
| `6-F6.27` | Save is manual, publish is gated and separate | PARTIAL | B | T-328, T-329 |
| `6-F6.28` | Version history with a Live marker and non-destructive restore | PARTIAL | B | T-330 |
| `6-F6.29` | Disable a node instead of deleting it | MISSING | B | T-326 |
| `6-F6.30` | Nested workflow as a component | MISSING | B | T-331 |
| `6-F6.32` | Batch run over a workspace image selection | PARTIAL | B | T-334 |
| `6-F6.33` | Deploy a workflow to an endpoint or a device | PARTIAL | B | T-319 |
| `6-F6.34` | First-run workflow path: empty canvas → block → test → deploy | PARTIAL | B | T-333 |
| `6-F6.36` | Two-stage detect → crop → classify → write back | PARTIAL | B | T-332 |
| `6-F6.37` | In-process library plus HTTP client | PARTIAL | B | T-342 |
| `6-F6.38` | Video pipeline object for webcam, file and RTSP | MISSING | B | T-343 |
| `6-F6.39` | Two CLIs with a stated boundary | PARTIAL | B | T-344 |
| `7-F7.18` | Training cost estimator before spending | PARTIAL | B | T-252, T-254 |
| `7-F7.43` | 30-day trash with permanent delete kept in the UI | PARTIAL | B/C | T-267, T-405, T-406, T-407 |

#### B.2 Cards

| Task | Title | Parity rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-012](T-012.md) | Ask three setup questions on first run and keep the answers | `1-F1.2` | 3 | yes | T-010 (the workspace exists and lands somewhere) |
| [T-013](T-013.md) | Deterministic assistant planner: brief in, project plan out | `1-F1.3` | 3 | no | T-012 (the setup answers are the first brief) |
| [T-014](T-014.md) | Assistant thread endpoints and the create-project action | `1-F1.3` | 3 | yes | T-013 (planner output), T-012 (setup answers seed the thread) |
| [T-015](T-015.md) | Assistant surface: composer, proposal row, attach menu | `1-F1.3` | 3 | no | T-014 (thread + action endpoints) |
| [T-016](T-016.md) | Sign up lands on the assistant, with a background-task panel | `1-F1.3` | 3 | no | T-015 (the surface this lands on) |
| [T-018](T-018.md) | One type contract: what each type may store, import, train and export | `1-F2.3` | 3 | no | T-017 (the type ids exist) |
| [T-019](T-019.md) | The editor shows only the tools the project type can learn from | `1-F2.3` | 2 | no | T-018 (the contract the UI mirrors) |
| [T-071](T-071.md) | Predict and trim video frame extraction before the job | `2-F2.6` | 2.5 | no | none |
| [T-072](T-072.md) | Frame-extraction dialog with trim and hand-picked frames | `2-F2.6` | 3 | no | T-071 (trim/pick fields, plan route) |
| [T-087](T-087.md) | Editor image menu, attributes block, cover and download | `2-F2.24`, `2-F2.26` | 3 | no | none |
| [T-088](T-088.md) | "Find similar" from the image in front of me | `2-F2.29` | 2.5 | no | T-087 (the menu that opens it) |
| [T-100](T-100.md) | Rebalance splits with three move policies | `2-F2.41`, `4-F4.12` | 3 | no | none |
| [T-101](T-101.md) | Rebalance step in the version wizard, with progress | `2-F2.41` | 2.5 | no | T-100 (rebalance route + job) |
| [T-133](T-133.md) | A mask is a first-class shape: storage and validation | `3-F3.11` | 3 | yes | none |
| [T-134](T-134.md) | Masks survive versions, training data and export | `3-F3.11` | 3 | no | T-133 (the mask shape it converts) |
| [T-135](T-135.md) | The brush: paint, subtract, and see the mask | `3-F3.11` | 3 | no | T-133 (the mask shape it writes) |
| [T-136](T-136.md) | Select several shapes: shift-click and a marquee | `3-F3.20` | 2.5 | no | none |
| [T-137](T-137.md) | Convert, merge and re-order a whole selection | `3-F3.20` | 3 | no | T-133 (mask shape), T-136 (the selection set) |
| [T-138](T-138.md) | Display-only adjustment and hide-all annotations | `3-F3.4` | 2 | no | T-120 (the session bag it reads and writes) |
| [T-139](T-139.md) | An assist session that follows you to the next image | `3-F3.21` | 3 | yes | none |
| [T-140](T-140.md) | Assist picker: three sources, a class mapping step | `3-F3.21`, `3-F3.54` | 3 | no | T-139 (the session it writes) |
| [T-141](T-141.md) | One model dropdown, one output shape | `3-F3.26`, `3-F3.54` | 3 | no | T-133 (the mask output target) |
| [T-142](T-142.md) | Instructions ride with the batch; assignment splits across people | `3-F3.45` | 2.5 | yes | none |
| [T-143](T-143.md) | The assign sheet, and managing a batch mid-flight | `3-F3.45` | 3 | no | T-142 (instructions and multi-assignee dealing) |
| [T-144](T-144.md) | Every save leaves a revision you can roll back | `3-F3.49` | 3 | yes | none |
| [T-145](T-145.md) | The History panel reads real revisions and restores one | `3-F3.49` | 2.5 | no | T-144 (the revisions and revert routes) |
| [T-146](T-146.md) | Action segments become data, not a drawing | `3-F3.15` | 3 | yes | none |
| [T-147](T-147.md) | A timeline with one row per class | `3-F3.15` | 3 | no | T-146 (the segment routes) |
| [T-148](T-148.md) | Review action segments, then export them | `3-F3.15` | 2.5 | no | T-146 (segment routes), T-147 (the Actions view) |
| [T-149](T-149.md) | Place a skeleton on a canvas, not in a textarea | `3-F3.14` | 3 | no | none |
| [T-150](T-150.md) | Ask a foundation model for boxes on this image | `3-F3.22` | 3 | yes | T-130 (per-class prompts the request mirrors) |
| [T-151](T-151.md) | Proposals are dashed, counted, and never silently saved | `3-F3.22`, `3-F3.25` | 3 | no | none |
| [T-152](T-152.md) | The foundation-prompt dialog on the open image | `3-F3.22` | 3 | no | T-150 (the route), T-151 (the proposal layer), T-130 (the class prompt rows) |
| [T-153](T-153.md) | "Find the green umbrella" on this image | `3-F3.23` | 3 | yes | T-150 (the prompt service and its metering), T-151 (proposals) |
| [T-154](T-154.md) | Box prompting: example boxes propose the rest | `3-F3.24` | 3 | yes | T-151 (proposal layer, client side) |
| [T-155](T-155.md) | The box-prompting controls: negatives, refresh, approve | `3-F3.24` | 3 | no | T-154 (the route), T-151 (proposal layer) |
| [T-156](T-156.md) | Feedback the preview can act on | `3-F3.30` | 3 | yes | T-130 (per-class prompts a revision rewrites) |
| [T-157](T-157.md) | Correct the preview in words, then see the new preview | `3-F3.30` | 3 | no | T-156 (the records and revise route) |
| [T-158](T-158.md) | A saved workflow as the labeller, with an explicit class map | `3-F3.31` | 3 | yes | T-130 (per-class thresholds), T-157 (the preview thread the chat half uses) |
| [T-159](T-159.md) | Video auto-label: the job and its bounded preview | `3-F3.34` | 3 | yes | T-146 (segments it writes), T-150 (the prompt service it reuses) |
| [T-160](T-160.md) | Configure a video auto-label run, preview a range, then queue it | `3-F3.34` | 3 | no | T-159 (the job and preview routes), T-147 (the timeline geometry it reuses), T-148 (where results are reviewed) |
| [T-161](T-161.md) | Measure in millimetres; read the image's facts | `3-F3.5`, `3-F3.6` | 3 | no | none |
| [T-162](T-162.md) | The similar-images strip inside the editor | `3-F3.7` | 2.5 | no | T-088 (area 2's similar-image ranking and route), T-087 (the editor menu that opens it) |
| [T-163](T-163.md) | A dropped connection keeps the work on this device | `3-F3.53` | 3 | yes | T-121 (the save state machine and stale guard it extends) |
| [T-164](T-164.md) | A read-only image says why; an empty project says what next | `3-F3.55` | 2.5 | yes | none |
| [T-165](T-165.md) | Turn review off for a one-person project | `3-F3.47` | 2.5 | yes | T-128 (the review rules it relaxes) |
| [T-172](T-172.md) | Isolation assist: preview before commit, engine and smoothing under the user's control | `3-F3.12` | 3 | no | none |
| [T-173](T-173.md) | Auto-label: per-label confidence in the preview, and a job card that counts | `3-F3.28`, `3-F3.33` | 2.5 | no | none |
| [T-200](T-200.md) | Contrast: stretch, equalise and adaptive equalisation | `4-F4.20` | 2.5 | no | T-197 (imaging owner), T-198 (step registry) |
| [T-201](T-201.md) | Static crop by percentage with an overlay | `4-F4.22` | 3 | no | T-197 (imaging owner), T-198 (step registry), T-199 (preview) |
| [T-202](T-202.md) | Isolate objects: one crop per box, detection becomes classification | `4-F4.21` | 3 | no | T-195 (versioning owner), T-197 (imaging owner) |
| [T-203](T-203.md) | Null images: keep a percentage, and say what null means | `4-F4.25` | 3 | no | T-195 (versioning owner), T-198 (step registry) |
| [T-204](T-204.md) | Tiling: grid and fixed-aspect modes beside fixed size | `4-F4.23` | 3 | no | T-190 (validation), T-197 (imaging owner) |
| [T-205](T-205.md) | Tiling card: mode, overlap, padding and the tile count | `4-F4.23`, `4-F4.27` | 2.5 | no | T-198 (step registry), T-204 (modes + preview count) |
| [T-206](T-206.md) | Class surgery: omit, rename and merge inside the version | `4-F4.24` | 3 | no | T-195 (versioning owner), T-190 (codes) |
| [T-207](T-207.md) | Class surgery panel with a regex preview | `4-F4.24` | 3 | no | T-198 (step registry), T-206 (backend map) |
| [T-208](T-208.md) | Ordered augmentation list, tiers and the parameter table | `4-F4.14`, `4-F4.30` | 3 | no | T-190 (recipe contract), T-197 (imaging owner) |
| [T-209](T-209.md) | Geometric augmentations: crop, shear and 90° direction | `4-F4.30` | 3 | no | T-208 (op table + dispatch) |
| [T-210](T-210.md) | Photometric augmentations: hue, camera gain and motion blur | `4-F4.30` | 3 | no | T-208 (op table + dispatch) |
| [T-211](T-211.md) | Box-level augmentation: change the object, not the background | `4-F4.31` | 3 | no | T-208 (dispatch + scope), T-210 (photometric ops to reuse) |
| [T-212](T-212.md) | Cutout: painted occlusion with labels kept | `4-F4.32` | 2 | no | T-208 (dispatch + premium tier) |
| [T-213](T-213.md) | Mosaic: pack 3–9 images into one tile | `4-F4.32` | 3 | no | T-208 (dispatch + tier), T-195 (pool selection) |
| [T-214](T-214.md) | Output step: multiplier, plan cap and the estimate | `4-F4.15`, `4-F4.29` | 2 | no | T-191 (limits endpoint), T-192 (estimate), T-194 (shell) |
| [T-215](T-215.md) | Augmentation catalogue: add one, configure it, read its tier | `4-F4.14`, `4-F4.30`, `4-F4.31`, `4-F4.32` | 3 | no | T-208 (op table), T-209/T-210 (forms of the ops that exist) |
| [T-216](T-216.md) | Augmentation step: ordered cards and the baseline guidance | `4-F4.14`, `4-F4.33` | 3 | no | T-215 (catalogue), T-214 (output step) |
| [T-217](T-217.md) | Version index rows with a delta chip and live states | `4-F4.3`, `4-F4.4` | 3 | no | T-194 (VersionList extraction) |
| [T-218](T-218.md) | Version job phases: preprocess, augment, write | `4-F4.4` | 2.5 | no | T-195 (versioning owner) |
| [T-219](T-219.md) | Version detail: split bar, class counts, one primary, guarded delete | `4-F4.16`, `4-F4.5` | 3 | no | T-194 (VersionDetail extraction), T-217 (flag) |
| [T-220](T-220.md) | "What changed": diff against the previous version | `4-F4.16` | 2 | no | T-219 (detail host), T-217 (flag) |
| [T-221](T-221.md) | Trainings and exports on the version page | `4-F4.16` | 2 | no | T-219 (detail host), T-217 (flag) |
| [T-222](T-222.md) | Recipe summary, the "baked in" lock and recipe reuse | `4-F4.7`, `4-F4.6` | 3 | no | T-219 (detail host), T-193 (recipe normalise), T-217 (flag) |
| [T-223](T-223.md) | Version readiness: what would block or weaken a run | `4-F4.46` | 2.5 | no | T-219 (detail host), T-217 (flag) |
| [T-224](T-224.md) | Export dialog: format chips, download, progress and states | `4-F4.34` | 2.5 | no | T-219 (detail host, secondary menu) |
| [T-225](T-225.md) | "Use from code" and the round-trip loss notes | `4-F4.34`, `4-F4.37` | 2 | yes | T-224 (dialog) |
| [T-226](T-226.md) | Format registry, task filtering, multi-label and CLIP | `4-F4.35` | 3 | no | T-192 (chip list consumed by the dialog's parent), T-206 (class map) |
| [T-227](T-227.md) | Darknet and RetinaNet writers | `4-F4.35` | 3 | no | T-226 (registry owner) |
| [T-228](T-228.md) | TFRecord writer | `4-F4.35` | 3 | no | T-226 (registry owner) |
| [T-229](T-229.md) | Semantic PNG mask writer | `4-F4.35` | 3 | no | T-226 (registry owner) |
| [T-232](T-232.md) | Version numbers that read, and a wizard that refuses an empty version | `4-F4.2`, `4-F4.10` | 2 | no | none |
| [T-250](T-250.md) | Train catalogue: task × family × size with default resolution | `5-F5.7` | 3 | no | none (first training card) |
| [T-251](T-251.md) | Access requests for gated model families | `5-F5.7` | 2.5 | no | T-250 (`request_access` flag on a family) |
| [T-252](T-252.md) | Training quote: minutes, credits, GPU and the smallest run | `5-F5.11`, `7-F7.18` | 3 | no | T-250 (variant + default resolution) |
| [T-253](T-253.md) | Credit cap: a money ceiling with the printed floor | `5-F5.10` | 2.5 | no | T-252 (credits ↔ seconds constant) |
| [T-254](T-254.md) | Sticky training summary, cap field, long-run confirmation | `5-F5.11`, `5-F5.10`, `5-F5.51`, `7-F7.18` | 3 | no | T-252 (quote route), T-253 (cap rule), T-255 (the screen that mounts it) |
| [T-255](T-255.md) | Train screen: three blocks, three presets, variants behind Advanced | `5-F5.7`, `5-F5.9` | 3 | no | T-250 (catalogue shape), T-252 (quote), T-254 (summary mount) |
| [T-256](T-256.md) | Training-time recipe: validated options, locked dataset rows | `5-F5.9`, `4-F4.7` | 3 | no | T-250 (family rows), T-255 (the Advanced panel host) |
| [T-259](T-259.md) | Starting weights: previous, COCO, shared, ImageNet, random | `5-F5.8` | 3 | no | T-258 (`checkpointOptions`, shared kind), T-250 (variant resolution) |
| [T-260](T-260.md) | Train on the live dataset (implicit version) | `5-F5.6` | 3 | no | T-250 (task), T-252 (quote must include the implicit version) |
| [T-261](T-261.md) | Dataset block: current-or-version, health chip, frozen rows | `5-F5.6`, `4-F4.7`, `4-F4.46`, `5-F5.40`, `5-F5.41`, `5-F5.42` | 3 | no | T-260 (current mode), T-262 (the readiness payload), T-256 (`RecipeLockRows`) |
| [T-262](T-262.md) | Start guards: pre-flight warnings and one active run | `5-F5.40`, `5-F5.41`, `5-F5.42`, `5-F5.49` | 3 | no | T-260 (current-dataset counts), area 4's `services/versions_ready.py` (T-223) |
| [T-263](T-263.md) | Run list: stopped vs failed, median latency, a remedy per failure | `5-F5.15`, `5-F5.26`, `5-F5.48`, `5-F5.1` | 3 | no | T-262 (the remedy codes), T-255 (Models surface flag) |
| [T-264](T-264.md) | Stop early vs cancel, with the consequences on screen | `5-F5.17` | 3 | no | T-263 (the run list that hosts the dialog), T-253 (the credit constant) |
| [T-265](T-265.md) | Cap-reached stop, spend shown, and a funded continuation | `5-F5.46` | 3 | no | T-253 (cap), T-263 (run list state), T-264 (stop semantics) |
| [T-266](T-266.md) | Spend meter and a log tail for a running job | `5-F5.19` | 2.5 | yes | T-265 (credits used), T-264 (the run states) |
| [T-267](T-267.md) | Delete a run: typed name and the serving consequence | `5-F5.37`, `7-F7.43` | 3 | no | T-268 (the binding that would move), area 7's trash model (T-380s) |
| [T-268](T-268.md) | Immutable model references, the legacy alias, and licence at download | `5-F5.33`, `5-F5.34`, `5-F5.4`, `5-F5.45` | 3 | no | T-267 (delete clears aliases), T-250 (variant naming) |
| [T-269](T-269.md) | Architecture search: the space, the caps and the plan | `5-F5.5` | 3 | no | T-250 (catalogue), T-252 (quote), T-262 (`small_valid_split`) |
| [T-270](T-270.md) | The search job: candidate fan-out inside one run | `5-F5.5` | 3 | no | T-269 (the plan), T-262 (guards), T-263 (run states) |
| [T-271](T-271.md) | Keep a search candidate as a real model | `5-F5.5`, `5-F5.36` | 2.5 | no | T-270 (candidate rows and their weights) |
| [T-272](T-272.md) | Search results on screen: band, scatter, keep | `5-F5.5`, `5-F5.36`, `5-F5.16` | 3 | no | T-270 (candidate rows), T-271 (keep action), T-263 (run list host) |
| [T-273](T-273.md) | Search backbone step: name the deployment target | `5-F5.14` | 2.5 | no | T-269 (bands and the 15-image rule), T-272 (results screen) |
| [T-274](T-274.md) | Quick model engine: a usable detector minutes after the first batch | `5-F5.13` | 3 | no | T-250 (catalogue), T-252 (quote), T-262 (guards) |
| [T-275](T-275.md) | Offer a quick model automatically after the first approved batch | `5-F5.13` | 2 | no | T-274 (the engine and its limits) |
| [T-276](T-276.md) | Quick model entry, states and the confidence hint | `5-F5.13` | 2.5 | no | T-274 (route and limits), T-275 (the note), T-263 (run list) |
| [T-277](T-277.md) | The tuned threshold becomes the served default | `5-F5.21` | 3 | no | T-263 (the model detail host), T-250 (variant) |
| [T-278](T-278.md) | Per-class counts: correct, misclassified, missed, false positive | `5-F5.22` | 2.5 | no | T-277 (the panel host), `insights_eval.match` (existing) |
| [T-279](T-279.md) | Recommendations derived from one evaluation | `5-F5.24` | 3 | no | T-278 (counts), T-263 (the detail host), `insights_eval.slices` (existing) |
| [T-280](T-280.md) | Recommendations card with working links | `5-F5.24` | 2.5 | no | T-279 (the payload), T-277 (`EvalPanel` host), T-263 (the run list) |
| [T-281](T-281.md) | Per-image scores joined onto the embedding map | `5-F5.25` | 3 | no | T-278 (counts helpers), `services/insights_eval.image_meta` (existing) |
| [T-282](T-282.md) | Colour the map by model score, open the worst first | `5-F5.25` | 2.5 | no | T-281 (the joined scores), `features/project/insights/Embeddings.tsx` (existing) |
| [T-283](T-283.md) | Compare by task metric, with stale evaluations named and re-runnable | `5-F5.27` | 3 | no | T-278 (counts), T-281 (score join), T-271 (the `eval_model` kind this card defines) |
| [T-284](T-284.md) | Compare screen: metric selector, update panel, next steps | `5-F5.27`, `5-F5.53` | 3 | no | T-283 (metric + staleness payload), `features/insights/CompareTab.tsx` (existing) |
| [T-285](T-285.md) | Pixel metrics and boundary AP for mask models | `5-F5.28` | 3 | no | T-283 (`metric_version`), `services/evaluate.py` (existing) |
| [T-286](T-286.md) | Mask quality card, task metric set, unsupported-task states | `5-F5.28` | 2.5 | no | T-285 (pixel + boundary payload), T-277 (`EvalPanel` host), T-283 (`metric_version`) |
| [T-287](T-287.md) | Evaluation lifecycle: unavailable, sampled and timed out | `5-F5.53`, `5-F5.54` | 3 | no | T-283 (`eval_model` re-run), T-263 (the run list host) |
| [T-288](T-288.md) | Upload external weights: format, magic and a worker-side proof | `5-F5.31` | 3 | no | T-268 (`ref`), T-270 (`eval_model` kind), T-257 (`shared` for the workspace mode) |
| [T-289](T-289.md) | Upload dialog with a validation state per file | `5-F5.31` | 2.5 | no | T-288 (the route and its statuses), T-263 (the run list host) |
| [T-290](T-290.md) | Uploaded models get the same evaluation and the same compare chart | `5-F5.29` | 2 | no | T-288 (validated upload), T-283 (`eval_model`), T-284 (compare UI) |
| [T-292](T-292.md) | Regression eval suites: the table and the check grammar | `5-F5.30` | 3 | no | T-250, T-257 (workspace scoping), `services/workflows` (existing) |
| [T-293](T-293.md) | Running a regression suite as one job | `5-F5.30` | 3 | no | T-292 (suites and checks), `services/workflows` runner (existing) |
| [T-294](T-294.md) | Regression tab: create a suite and run it | `5-F5.30` | 3 | no | T-292 (suites), T-293 (runs), T-263 (the Models container) |
| [T-295](T-295.md) | Regression results and the deploy gate | `5-F5.30` | 2.5 | no | T-294 (the tab), T-293 (runs), `services/deployments` (existing) |
| [T-296](T-296.md) | Calibrate an anomaly station against a labelled anomaly set | `5-F5.52` | 3 | no | none |
| [T-319](T-319.md) | Every place a workflow can run, from one button | `6-F6.33` | 3 | no | T-316 (the invoke URL), T-315 (the contract the destinations read) |
| [T-320](T-320.md) | A workflow becomes a graph with named ports | `6-F6.21` | 3 | no | T-315 (the port contract it extends) |
| [T-321](T-321.md) | Old linear workflows keep running | `6-F6.21` | 3 | no | T-320 (the graph and its ports) |
| [T-322](T-322.md) | The canvas: nodes, ports and a palette | `6-F6.21` | 3 | no | T-320 (graph shape), T-321 (compile) |
| [T-323](T-323.md) | Wiring help in three strengths, and one arrange button | `6-F6.21` | 3 | no | T-322 (the canvas), T-320 (port rules) |
| [T-324](T-324.md) | Test a draft on a still, a clip or a camera | `6-F6.23` | 3 | no | T-322 (the editor), T-321 (the plan) |
| [T-325](T-325.md) | Block cache, with an honest uncache | `6-F6.24` | 2.5 | no | T-324 (the run panel) |
| [T-326](T-326.md) | Mute the side effects, and mute one node | `6-F6.25`, `6-F6.29` | 2.5 | no | T-324 (the run panel), T-320 (`disabled` on a node) |
| [T-327](T-327.md) | The Outputs node is a list you can order | `6-F6.26` | 2.5 | no | T-320 (ports), T-315 (the contract) |
| [T-328](T-328.md) | Save is a draft; publish is a gate | `6-F6.27` | 3 | no | T-320 (a graph to check), T-316 (the endpoint that must serve the published version) |
| [T-329](T-329.md) | The publish panel, and auto-publish | `6-F6.27` | 2.5 | no | T-328 (the gate endpoint) |
| [T-330](T-330.md) | Version history that says what production runs | `6-F6.28` | 2 | no | T-328 (the live pointer), T-322 (the editor it restores into) |
| [T-331](T-331.md) | A workflow inside a workflow | `6-F6.30` | 3 | no | T-320 (ports), T-321 (compile) |
| [T-332](T-332.md) | Per-object classes: detect, crop, classify, write back | `6-F6.36` | 3 | no | T-320 (block types), T-321 (compile) |
| [T-333](T-333.md) | A first workflow that produces a result in five actions | `6-F6.34` | 2.5 | no | T-322 (the canvas), T-332 (the recipe module) |
| [T-334](T-334.md) | Run a model over the images I just picked | `6-F6.32` | 3 | no | none (extends the shipped `batch_inference` job) |
| [T-335](T-335.md) | Record every hosted request, without keeping the image | `6-F6.14` | 3 | yes | T-310 (the envelope's `request_id`) |
| [T-336](T-336.md) | A monitoring page that says what it does not keep | `6-F6.14` | 3 | no | T-335 (the rows it aggregates) |
| [T-337](T-337.md) | Production events get a type and a vocabulary | `6-F6.15` | 3 | no | none (extends `StreamEvent`) |
| [T-338](T-338.md) | Filter events, and say how far back the data goes | `6-F6.15`, `6-F6.20` | 3 | no | T-337 (the type and the metadata) |
| [T-339](T-339.md) | A human verdict on a production event | `6-F6.16` | 3 | no | T-337 (the event shape), T-338 (the list it appears in) |
| [T-340](T-340.md) | One reviewer at a time, and the lock releases itself | `6-F6.17` | 3 | no | T-339 (a veredict to review against) |
| [T-341](T-341.md) | The review session screen | `6-F6.17` | 2.5 | no | T-340 (the session routes) |
| [T-342](T-342.md) | Run a workflow and load a model from Python | `6-F6.37` | 3 | no | T-316 (the invoke route), T-312 (the weights the loader reads) |
| [T-343](T-343.md) | A video source object for a file, a webcam or a camera URL | `6-F6.38` | 3 | no | T-342 (the SDK surface it joins) |
| [T-344](T-344.md) | Two command sets, one stated boundary | `6-F6.39` | 3 | no | T-342 (client methods), T-334 (the batch it drives) |

### Wave C — data and people

Depth behind the demo. Dataset metadata and duplicates, the asset library, trash, members and roles, key lifecycle, audit, connectors, CLI/account preferences. Mostly additive screens and columns.

**97 cards · 278.5 agent-hours · 88 PARITY rows listed.**

#### C.1 Rows and the cards that close them

| Parity row | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| `1-F2.4` | Annotation groups share one class vocabulary | PARTIAL | C | T-020, T-021 |
| `1-F2.5` | Creation is scriptable with the same shape as the form | PARTIAL | C | T-022 |
| `1-F4.1` | Folders above projects, move by drag, delete lifts contents | PARTIAL | C | T-024, T-025 |
| `1-F4.2` | Workspace-wide media search (asset library) | MISSING | C | T-026, T-027, T-028, T-029 |
| `1-F4.4` | Public dataset discovery with image-similarity search | MISSING | C | T-030, T-031, T-044 |
| `1-F5.4` | Three invite routes, role at invite time, visible pending state | PARTIAL | C | T-038, T-039, T-040 |
| `1-F5.5` | Per-project ownership transfer | MISSING | C | T-041 |
| `1-F5.6` | Soft delete with a 30-day trash, who/when/days left | PARTIAL | C | T-405, T-406, T-407 |
| `2-F2.2` | Pre-labelled upload with an overwrite switch | PARTIAL | A/C | T-063, T-068 |
| `2-F2.3` | Broad format acceptance with class-name normalisation | PARTIAL | C | T-064, T-065 |
| `2-F2.4` | Two-speed archive ingest with background completion | PARTIAL | C | T-066, T-068 |
| `2-F2.5` | Camera capture as an upload source | MISSING | C | T-067 |
| `2-F2.7` | Server-side fetch from a public URL | MISSING | C | T-066, T-068 |
| `2-F2.8` | Screening hold with a per-image verdict | MISSING | C | T-069, T-070 |
| `2-F2.10` | Single-image REST upload with late annotation attach | PARTIAL | C | T-073 |
| `2-F2.11` | Archive REST upload via signed URL plus task polling | MISSING | C | T-074 |
| `2-F2.12` | Video REST upload in the same three steps | PARTIAL | C | T-074 |
| `2-F2.13` | SDK bulk upload with workers, retries and project creation | PARTIAL | C | T-075 |
| `2-F2.14` | CLI upload with no-wait and JSON output | PARTIAL | C | T-075 |
| `2-F2.15` | Reusable bucket credentials, separate from the datasource | PARTIAL | C | T-076, T-080 |
| `2-F2.16` | Datasource connection configuration with a path-style control | PARTIAL | C | T-077, T-080 |
| `2-F2.17` | Mirror configuration: destination, globs, naming, orphans | PARTIAL | C | T-078, T-081 |
| `2-F2.18` | JSON metadata sidecars with a conflict policy | MISSING | C | T-083 |
| `2-F2.19` | Sync run controls with cooldown, cap and schedule | PARTIAL | C | T-079, T-081 |
| `2-F2.21` | Merge projects into a third, union-backed project | MISSING | C | T-085, T-086 |
| `2-F2.25` | Workspace-wide media browser with a sticky action bar | MISSING | C | T-026 |
| `2-F2.26` | Export a single image, a version or a query result | PARTIAL | B/C | T-087, T-089 |
| `2-F2.28` | Natural-language semantic search over unlabelled content | MISSING | C | T-090 |
| `2-F2.30` | Cross-project search with cursor pagination | MISSING | C | T-091 |
| `2-F2.31` | Tag lifecycle: upload, bulk apply, project-wide rename | PARTIAL | C | T-092 |
| `2-F2.32` | Typed per-image metadata, bulk update, filterable | MISSING | C | T-082, T-084 |
| `2-F2.33` | Batch as a first-class, mergeable container | PARTIAL | C | T-093 |
| `2-F2.34` | Folders with inherited permissions | PARTIAL | C | T-094, T-095, T-096 |
| `2-F2.36` | Near-duplicate discovery as a ranked search | PARTIAL | C | T-098, T-099 |
| `2-F2.37` | Health report whose charts are filters | HAVE | C/G | T-002, T-102, T-103 |
| `2-F2.45` | 30-day trash for containers with parent-before-child restore | PARTIAL | C | T-405, T-406, T-407 |
| `3-F3.17` | Multimodal prefix questions | MISSING | C | T-166, T-167, T-168 |
| `3-F3.36` | Class admin: rename, merge, delete, lock | PARTIAL | C | T-169 |
| `3-F3.38` | Per-class annotation attributes | MISSING | C | T-170 |
| `3-F3.40` | Shared class sets and labels across projects | MISSING | C | T-020 |
| `3-F3.48` | Pinned, threaded comments on the image | PARTIAL | C | T-171 |
| `3-F3.51` | Keyboard reference, and remapping | HAVE | C/G | T-003, T-174 |
| `4-F4.38` | Export straight to a customer bucket | MISSING | C | T-230, T-231 |
| `4-F4.39` | Dataset health overview | PARTIAL | C | T-103 |
| `4-F4.42` | Annotation heat map with drag-to-filter | MISSING | C | T-103 |
| `4-F4.43` | Objects-per-image histogram with click-through | PARTIAL | C | T-103 |
| `5-F5.3` | Workspace registry with a starred public tab | PARTIAL | C | T-257, T-258 |
| `5-F5.32` | Train elsewhere and import back | MISSING | C | T-291 |
| `5-F5.36` | Starring search candidates | MISSING | B/C | T-257, T-271, T-272 |
| `6-F6.13` | Scoped, rotatable keys with a publishable type | PARTIAL | C | T-391 |
| `6-F6.18` | Watchdog and digest alerts without visiting a dashboard | PARTIAL | C | T-439 |
| `6-F6.31` | Share, fork and folder-scope a workflow | MISSING | C | T-345 |
| `6-F6.40` | Key resolution for notebook, container and CI | PARTIAL | C | T-348 |
| `6-F6.41` | Source types with different lifetimes in one table | PARTIAL | C | T-346 |
| `6-F6.42` | Capture settings only where they can apply | MISSING | C | T-347 |
| `7-F7.1` | Member roster with seat accounting | PARTIAL | C | T-380 |
| `7-F7.2` | Bulk email invite with a per-batch role | PARTIAL | C | T-039 |
| `7-F7.3` | Pending invitations with resend and cancel | PARTIAL | C | T-039 |
| `7-F7.4` | Role-locked reusable invite link | MISSING | C | T-038 |
| `7-F7.5` | Same-domain join request with approval | MISSING | C | T-040 |
| `7-F7.6` | Change a member's role, self-change blocked | PARTIAL | C | T-381 |
| `7-F7.8` | Workspace default role for new joiners | MISSING | C | T-382 |
| `7-F7.9` | Built-in role matrix as a readable table | PARTIAL | C | T-382 |
| `7-F7.10` | Custom roles from grouped permissions, copy-from, tooltips | PARTIAL | C | T-383 |
| `7-F7.13` | Credit burn-down with cumulative/daily toggle | PARTIAL | C | T-409 |
| `7-F7.14` | Attribution by key, folder and member | MISSING | C | T-410 |
| `7-F7.16` | Forward projection with saved scenarios | MISSING | C | T-411 |
| `7-F7.17` | Consumption audit log distinct from security audit | PARTIAL | C | T-408 |
| `7-F7.25` | Key table whose badges carry the state | PARTIAL | C | T-388, T-389 |
| `7-F7.27` | Rename, protect, disable, revoke as four strengths | PARTIAL | C | T-390, T-391 |
| `7-F7.28` | Atomic roll with a dependency warning | MISSING | C | T-392, T-393 |
| `7-F7.29` | Per-key permission scoping with silent 404s | PARTIAL | C | T-394 |
| `7-F7.31` | Key metadata and named owners | MISSING | C | T-396 |
| `7-F7.32` | Rotation due dates and reminders | MISSING | C | T-397 |
| `7-F7.33` | Default key and "in use" fallback made visible | MISSING | C | T-398 |
| `7-F7.37` | CLI/SDK auth handshake with a default workspace | PARTIAL | C | T-441 |
| `7-F7.38` | Audit log table with four filters and row detail | PARTIAL | C | T-399, T-400 |
| `7-F7.39` | Audit coverage across admin, data and agent changes | PARTIAL | C | T-401 |
| `7-F7.43` | 30-day trash with permanent delete kept in the UI | PARTIAL | B/C | T-267, T-405, T-406, T-407 |
| `7-F7.46` | Named credential store for external providers | PARTIAL | C | T-076 |
| `7-F7.47` | Bucket mirror datasource with a two-tab setup | PARTIAL | C | T-080 |
| `7-F7.48` | Mirror trigger guards against cost surprises | MISSING | C | T-079 |
| `7-F7.49` | Webhook push from a processing pipeline | PARTIAL | C | T-435 |
| `7-F7.51` | Notification sinks with per-message credit cost | PARTIAL | C | T-438 |
| `7-F7.52` | Handoff to external training platforms | MISSING | C | T-440 |
| `7-F7.56` | Star and reuse a public model as a checkpoint | MISSING | C | T-257, T-258 |
| `7-F7.58` | Rename a workspace with a URL-breakage warning | PARTIAL | C | T-442 |
| `7-F7.60` | Workspace policy switches that gate member actions | MISSING | C | T-402, T-403 |

#### C.2 Cards

| Task | Title | Parity rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-020](T-020.md) | Shared class vocabulary: group table, project link, propagation rules | `1-F2.4`, `3-F3.40` | 3 | yes | none |
| [T-021](T-021.md) | Group picker on the create form and a shared-vocabulary panel | `1-F2.4` | 3 | no | T-020 (groups and the conflict rules exist) |
| [T-022](T-022.md) | Create a project from the SDK and the CLI, same shape as the form | `1-F2.5` | 3 | yes | T-017 (the type ids and their shaping rules) |
| [T-024](T-024.md) | Move projects and folders by drag, including a multi-selection | `1-F4.1` | 3 | no | none |
| [T-025](T-025.md) | Folders inside folders, with a cycle rule and a breadcrumb | `1-F4.1` | 3 | no | T-024 (the drag UI this nests into) |
| [T-026](T-026.md) | Workspace asset search: one query across every project | `1-F4.2`, `2-F2.25` | 3 | yes | none |
| [T-027](T-027.md) | Asset library page: one filter bar, a grid, a saved sort | `1-F4.2` | 3 | no | T-026 (the search endpoint) |
| [T-028](T-028.md) | Cross-project bulk actions on a selection | `1-F4.2` | 3 | yes | T-026 (selection comes from the asset query), T-027 (the grid) |
| [T-029](T-029.md) | Select all matches and export the workspace as one job | `1-F4.2` | 3 | yes | T-026 (the query), T-028 (the selection bar) |
| [T-030](T-030.md) | Public dataset listing with type, size and model filters | `1-F4.4` | 3 | yes | none |
| [T-031](T-031.md) | Discovery gallery page a visitor can browse signed out | `1-F4.4` | 3 | no | T-030 (the listing endpoint) |
| [T-038](T-038.md) | Per-role join links, invite expiry and resend | `1-F5.4`, `7-F7.4` | 3 | yes | none |
| [T-039](T-039.md) | Members panel: join links, pending invites with expiry and resend | `1-F5.4`, `7-F7.2`, `7-F7.3` | 3 | no | T-038 (join links, expiry, resend) |
| [T-040](T-040.md) | Same-domain join requests an admin accepts | `1-F5.4`, `7-F7.5` | 3 | yes | T-039 (the Members page that hosts the queue) |
| [T-041](T-041.md) | Hand a project to a named colleague | `1-F5.5` | 3 | yes | none |
| [T-044](T-044.md) | Drop one photo and reorder public datasets by visual similarity | `1-F4.4` | 3 | yes | T-030 (the listing to reorder), T-031 (the gallery that hosts the dropzone) |
| [T-064](T-064.md) | Detect the import format and normalise class names | `2-F2.3` | 3 | no | none |
| [T-065](T-065.md) | Read CreateML, Darknet-folder and Pascal-Seg uploads | `2-F2.3` | 3 | no | T-064 (dispatch hook and `Bundle.format`) |
| [T-066](T-066.md) | Archive imports as a job, and ingest from a URL | `2-F2.4`, `2-F2.7` | 3 | yes | none |
| [T-067](T-067.md) | Capture training frames from the camera | `2-F2.5` | 2.5 | no | none |
| [T-068](T-068.md) | Upload page: pre-flight, archive branch, URL row, result sheet | `2-F2.4`, `2-F2.7`, `2-F2.2` | 3 | no | T-063 (overwrite field), T-064 (format/renames/orphans), T-066 (archive + URL routes), T-067 (camera sheet) |
| [T-069](T-069.md) | Screening state on every ingested image | `2-F2.8` | 3 | no | none |
| [T-070](T-070.md) | The awaiting-screening queue on the dataset | `2-F2.8` | 2.5 | no | T-069 (state, verdict route) |
| [T-073](T-073.md) | Attach labels to a stored image, with a stale-write guard | `2-F2.10` | 2.5 | yes | T-066 (the reviewed URL fetch pattern) |
| [T-074](T-074.md) | Resumable upload sessions for archives and video | `2-F2.11`, `2-F2.12` | 3 | yes | T-066 (archive job, `ingest` reuse, routers/uploads.py) |
| [T-075](T-075.md) | SDK and CLI upload: workers, retries, no-wait and JSON | `2-F2.13`, `2-F2.14` | 3 | no | T-074 (session endpoints for `--no-wait` and `--zip-upload`) |
| [T-076](T-076.md) | A reusable credential store for bucket access | `2-F2.15`, `7-F7.46` | 3 | yes | none |
| [T-077](T-077.md) | Prove a bucket connection and get path-style right | `2-F2.16` | 3 | yes | T-076 (credentials are what a test exercises) |
| [T-078](T-078.md) | Mirror a bucket into a project: globs, naming, orphans | `2-F2.17` | 3 | yes | T-077 (validated connection, path-style) |
| [T-079](T-079.md) | Sync run controls, history and a daily schedule | `2-F2.19`, `7-F7.48` | 2.5 | no | T-078 (mirror run to control) |
| [T-080](T-080.md) | Connectors screen: credentials and a proven connection | `2-F2.15`, `2-F2.16`, `7-F7.47` | 3 | no | T-076 (credentials API), T-077 (test + PATCH) |
| [T-081](T-081.md) | Datasource screen: mirror rules, run controls and history | `2-F2.17`, `2-F2.19` | 3 | no | T-078 (mirror config + run result), T-079 (guards, history, schedule), T-080 (datasource form shell) |
| [T-082](T-082.md) | Typed per-image metadata with bulk update | `2-F2.32` | 3 | no | T-061 (the `metadata:` selector is compiled by the query route) |
| [T-083](T-083.md) | JSON sidecars and the metadata conflict policy | `2-F2.18` | 3 | no | T-082 (`Image.meta` and the typing rules) |
| [T-084](T-084.md) | Metadata editor and bulk metadata dialog | `2-F2.32` | 3 | no | T-082 (API), T-083 (human-owned keys) |
| [T-085](T-085.md) | Merge projects into a third one, without re-uploading | `2-F2.21` | 3 | no | none |
| [T-086](T-086.md) | Merge dialog with a union preview | `2-F2.21` | 2 | no | T-085 (preview + merge routes) |
| [T-089](T-089.md) | Export the images matching the current query | `2-F2.26` | 3 | no | T-061 (`query` compile + selection scope) |
| [T-090](T-090.md) | Search unlabelled content by description | `2-F2.28` | 3 | no | T-060 (the query grammar marks free text as filename), T-088 (feature cache reader) |
| [T-091](T-091.md) | Workspace-wide image search with cursor pages | `2-F2.30` | 3 | no | T-060 (query grammar), T-061 (per-project compile) |
| [T-092](T-092.md) | Rename, merge and delete tags with a reviewable diff | `2-F2.31` | 3 | no | none |
| [T-093](T-093.md) | Rename, merge and delete batches from the board | `2-F2.33` | 3 | no | none |
| [T-094](T-094.md) | Nest folders and move projects in bulk | `2-F2.34` | 3 | no | none |
| [T-095](T-095.md) | Folder access that the server enforces | `2-F2.34` | 3 | yes | T-094 (nesting), T-091 (search must respect it) |
| [T-096](T-096.md) | Folder tree, drag-move and the access dialog | `2-F2.34` | 3 | no | T-094 (nesting + bulk move), T-095 (access) |
| [T-098](T-098.md) | Near-duplicate clusters with an adjustable threshold | `2-F2.36` | 3 | no | none |
| [T-099](T-099.md) | Duplicate review: side-by-side, tag or remove | `2-F2.36` | 3 | no | T-098 (cluster route) |
| [T-102](T-102.md) | Heat-map region selection for the health report | `2-F2.37` | 2 | no | none |
| [T-103](T-103.md) | Health charts that are filters, not decoration | `2-F2.37`, `4-F4.39`, `4-F4.42`, `4-F4.43` | 3 | no | T-102 (heat region → selection token) |
| [T-166](T-166.md) | Prompt slots and per-image answers | `3-F3.17` | 3 | yes | none |
| [T-167](T-167.md) | Answer the project's questions in the editor | `3-F3.17` | 2.5 | no | T-166 (the prompts and answers) |
| [T-168](T-168.md) | Author the prompts, then export VQA rows | `3-F3.17` | 2.5 | no | T-166 (the prompt routes) |
| [T-169](T-169.md) | Rename with a diff, and lock the taxonomy | `3-F3.36` | 3 | yes | none |
| [T-170](T-170.md) | Per-class attribute fields on a shape | `3-F3.38` | 3 | yes | none |
| [T-171](T-171.md) | Comments pinned to a spot, with replies and resolve | `3-F3.48` | 3 | yes | none |
| [T-174](T-174.md) | Shortcuts belong to the account, not the browser | `3-F3.51` | 2 | no | none |
| [T-230](T-230.md) | Bucket delivery: upload an export to a workspace connector | `4-F4.38` | 3 | yes | T-226 (artefact + registry); the dialog half of the same row lands in the next card |
| [T-231](T-231.md) | Export destination wiring and the storage menu | `4-F4.38` | 2.5 | yes | T-230 (uploader), T-224 (dialog slot) |
| [T-257](T-257.md) | Star and share models, with a workspace registry tab | `5-F5.3`, `5-F5.36`, `7-F7.56` | 3 | no | T-250 (model rows carry a family/size) |
| [T-258](T-258.md) | Shared checkpoint catalogue and reuse from another project | `7-F7.56`, `5-F5.3` | 3 | yes | T-257 (`shared` flag), T-252 (quote so the reuse shows a price) |
| [T-291](T-291.md) | Train elsewhere: a dataset bundle and the way back | `5-F5.32` | 2.5 | yes | T-288 (the import half), area 4's `exporters.cached_export` (existing) |
| [T-345](T-345.md) | Hand a workflow to another project | `6-F6.31` | 3 | yes | T-320 (the graph a copy carries), T-328 (versions a fork copies) |
| [T-346](T-346.md) | Say what each camera source can and cannot become | `6-F6.41` | 3 | yes | none (extends the shipped stream create path) |
| [T-347](T-347.md) | Capture settings, and where they do nothing | `6-F6.42` | 2 | no | T-346 (the source kinds it differentiates) |
| [T-348](T-348.md) | One key, three sources, one documented order | `6-F6.40` | 2.5 | yes | T-344 (the CLI it extends) |
| [T-380](T-380.md) | Member roster with seats, avatars and a row menu | `7-F7.1` | 3 | no | none |
| [T-381](T-381.md) | Membership guards: no self-demotion, no last admin | `7-F7.6` | 2.5 | yes | T-380 (the row menu that calls these routes) |
| [T-382](T-382.md) | Roles tab: the built-in matrix and the default joiner role | `7-F7.9`, `7-F7.8` | 3 | yes | T-381 (the same page's role dialog) |
| [T-383](T-383.md) | Custom-role editor: copy, groups, tooltips, safe delete | `7-F7.10` | 3 | yes | T-382 (same page, shared labels) |
| [T-388](T-388.md) | Key schema and the key list payload | `7-F7.25` | 3 | yes | none |
| [T-389](T-389.md) | Key table with state badges and a masked value | `7-F7.25` | 3 | no | T-388 (payload) |
| [T-390](T-390.md) | Rename, protect, disable and revoke | `7-F7.27` | 3 | yes | T-388 (columns and payload) |
| [T-391](T-391.md) | Key row menu with four strengths | `7-F7.27`, `6-F6.13` | 2.5 | no | T-390 (the actions) |
| [T-392](T-392.md) | Roll a key with a dependency probe | `7-F7.28` | 3 | yes | T-390 (protect/disable state the roll must preserve) |
| [T-393](T-393.md) | Roll dialog with the blast radius | `7-F7.28` | 2.5 | no | T-392 (probe and roll) |
| [T-394](T-394.md) | A missing key scope answers 404, and the picker that sets it | `7-F7.29` | 3 | yes | T-388 (payload) |
| [T-396](T-396.md) | Key metadata and named owners | `7-F7.31` | 2.5 | no | T-388 (payload and columns) |
| [T-397](T-397.md) | Rotation due date, one reminder and the due ladder | `7-F7.32` | 3 | no | T-388 (payload), T-396 (owners receive the mail) |
| [T-398](T-398.md) | Default key and the in-use badge | `7-F7.33` | 3 | no | T-388 (payload), T-397 (the due ladder reuses the same badges) |
| [T-399](T-399.md) | Audit filters, actor types and the row detail payload | `7-F7.38` | 3 | yes | none |
| [T-400](T-400.md) | Audit table: four filter slots, row expand, endless scroll | `7-F7.38` | 3 | no | T-399 (filters, cursor, detail payload) |
| [T-401](T-401.md) | Audit coverage catalogue and the missing emissions | `7-F7.39` | 3 | yes | T-399 (the log that renders these actions) |
| [T-402](T-402.md) | Workspace policy store and the policy API | `7-F7.60` | 3 | yes | none |
| [T-403](T-403.md) | Project settings policy screen | `7-F7.60` | 2.5 | no | T-402 (store and routes) |
| [T-405](T-405.md) | Trash rows for projects, versions, runs and workflows | `7-F7.43`, `1-F5.6`, `2-F2.45` | 3 | yes | none |
| [T-406](T-406.md) | Restore order, permanent purge and the 30-day window | `7-F7.43`, `1-F5.6`, `2-F2.45` | 3 | yes | T-405 (the stamps) |
| [T-407](T-407.md) | Trash screen with who, when and days left | `7-F7.43`, `1-F5.6`, `2-F2.45` | 3 | no | T-406 (the routes) |
| [T-408](T-408.md) | Consumption ledger for the billing surface | `7-F7.17` | 3 | no | none |
| [T-409](T-409.md) | Burn-down with cumulative/daily and credits/dollars | `7-F7.13` | 3 | no | T-408 (the ledger supplies the per-kind split) |
| [T-410](T-410.md) | Attribution by key, folder and member | `7-F7.14` | 3 | no | T-408 (ledger), T-409 (the same range controls) |
| [T-411](T-411.md) | Usage projection with saved scenarios | `7-F7.16` | 3 | yes | T-409 (the series the projection extrapolates) |
| [T-435](T-435.md) | Webhook sink block in a workflow | `7-F7.49` | 3 | yes | none |
| [T-438](T-438.md) | Notification cost metering and display | `7-F7.51` | 3 | no | T-408 (the ledger), T-410 (attribution) |
| [T-439](T-439.md) | Alert on silence and on camera offline | `6-F6.18` | 3 | no | T-438 (the channel that carries the alert and its cost) |
| [T-440](T-440.md) | External training handoff | `7-F7.52` | 3 | yes | T-435 (the outbound transport it reuses) |
| [T-441](T-441.md) | CLI login and a default workspace | `7-F7.37` | 2 | yes | none |
| [T-442](T-442.md) | Rename a workspace with a URL-breakage warning | `7-F7.58` | 2.5 | yes | none |

### Wave D — commercial and enterprise

Commercial and enterprise. Money is provider-agnostic and flagged off; identity, data protection, dedicated/batch delivery and stream reliability are interface-first with mock drivers. Do not start the money cards before the three owner answers in §4.1.

**52 cards · 151 agent-hours · 27 PARITY rows listed.**

#### D.1 Rows and the cards that close them

| Parity row | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| `1-F1.1` | One-screen workspace creation with plan choice inline | PARTIAL | A/D | T-010, T-011 |
| `1-F6.3` | Plan and role gates decide which screens exist | PARTIAL | D | T-042, T-043 |
| `6-F6.3` | Dedicated private box with dev/prod types and pause | MISSING | D | T-352, T-353 |
| `6-F6.4` | Batch job over stored images or video | PARTIAL | D | T-354, T-355 |
| `6-F6.6` | Cost model printed next to the choice | PARTIAL | D | T-349 |
| `6-F6.19` | Active learning as a small rules form | PARTIAL | D | T-350, T-351 |
| `6-F6.44` | Live results, stream state and recovery | PARTIAL | D | T-356, T-357 |
| `6-F6.46` | Edge fleet management with approval and windows | MISSING | D | T-358, T-359 |
| `7-F7.11` | Folder-scoped access and named auth groups | MISSING | D | T-384, T-385, T-386, T-387 |
| `7-F7.12` | Billing home for plan, packs and add-ons | MISSING | D | T-412, T-413, T-414 |
| `7-F7.19` | Prepaid credit purchase | MISSING | D | T-417 |
| `7-F7.20` | Flex billing with an explicit spend cap | MISSING | D | T-418 |
| `7-F7.21` | Three-stage "you are spending" notices | PARTIAL | D | T-419 |
| `7-F7.22` | Cancel a plan with an explicit end state | MISSING | D | T-416 |
| `7-F7.23` | Billing portal: card, details, invoices | MISSING | D | T-415 |
| `7-F7.24` | Teams add-on with seat rules | MISSING | D | T-420 |
| `7-F7.30` | Folder-scoped keys | MISSING | D | T-395 |
| `7-F7.35` | Self-serve SSO with DNS proof | MISSING | D | T-423, T-424, T-425, T-426 |
| `7-F7.36` | OAuth sign-in for third-party apps | MISSING | D | T-427, T-428, T-429 |
| `7-F7.40` | SIEM streaming with a real test event | MISSING | D | T-421, T-422 |
| `7-F7.41` | Directory-group sync and workspace gating | MISSING | D | T-430, T-431, T-432 |
| `7-F7.42` | Custom branding of login and navigation | MISSING | D | T-433, T-434 |
| `7-F7.44` | Private-data licensing opt-out | MISSING | D | T-404 |
| `7-F7.45` | Contractual and regional controls | PARTIAL | D | T-446 |
| `7-F7.50` | Third-party AI billed through the workspace | PARTIAL | D | T-436, T-437 |
| `7-F7.59` | Delete a workspace or the whole account | MISSING | D | T-443, T-444, T-445 |
| `7-F7.61` | Cross-workspace rollup for multi-workspace customers | MISSING | D | T-447, T-448, T-449 |

#### D.2 Cards

| Task | Title | Parity rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-011](T-011.md) | Offer the plan on the same screen, mock and off by default | `1-F1.1` | 2 | yes | T-010 (the form the picker sits in) |
| [T-042](T-042.md) | Entitlements: one map of what a plan unlocks | `1-F6.3` | 3 | yes | none |
| [T-043](T-043.md) | Gate the review column, labeling analytics and non-admin seats | `1-F6.3` | 3 | yes | T-042 (the entitlement map and dependency) |
| [T-349](T-349.md) | The rate table, next to the choice | `6-F6.6` | 3 | no | T-311 (the chooser it sits beside) |
| [T-350](T-350.md) | Collection limits: caps, cadence and what is kept | `6-F6.19` | 3 | no | none (extends `services/active_learning.py`) |
| [T-351](T-351.md) | The active-learning form, and who reviews the batch | `6-F6.19` | 2.5 | no | T-350 (the caps and cadence endpoints) |
| [T-352](T-352.md) | A private box: interface, mock driver, honest default | `6-F6.3` | 3 | no | T-310 (the catalogue that must stop saying "not configured") |
| [T-353](T-353.md) | The private-box panel, its usage and its logs | `6-F6.3` | 2.5 | no | T-352 (the lifecycle routes) |
| [T-354](T-354.md) | Batch over stored files: run a workflow, keep a result set | `6-F6.4` | 3 | yes | T-315 (the input contract a batch must match), T-321 (the compiled plan) |
| [T-355](T-355.md) | The batch screen: source, progress, result | `6-F6.4` | 3 | no | T-354 (the workflow source and the `results` artefact), T-334 (the selection source) |
| [T-356](T-356.md) | Camera state and job state are two different words | `6-F6.44` | 3 | no | none (extends `app/streams/manager.py`) |
| [T-357](T-357.md) | Restart one camera or all of them, and read what happened | `6-F6.44` | 2.5 | no | T-356 (the state vocabulary and the attention reason) |
| [T-358](T-358.md) | Devices that check in, and say how they are | `6-F6.46` | 3 | yes | T-310 (the edge row that must stop saying "not configured"), T-356 (the state words it reports) |
| [T-359](T-359.md) | A config change that cannot reach 200 boxes unreviewed | `6-F6.46` | 3 | yes | T-358 (the devices it addresses) |
| [T-384](T-384.md) | Folder permission and auth-group tables | `7-F7.11` | 2.5 | yes | none |
| [T-385](T-385.md) | Folder scope enforcement with silent 404s | `7-F7.11` | 3 | yes | T-384 (tables and the access service) |
| [T-386](T-386.md) | Folder access and auth-group API | `7-F7.11` | 3 | yes | T-385 (enforcement reads these grants) |
| [T-387](T-387.md) | Folder permissions panel and the auth-groups screen | `7-F7.11` | 3 | no | T-386 (both APIs) |
| [T-395](T-395.md) | Folder keys scoped to one folder | `7-F7.30` | 3 | yes | T-386 (folder grants), T-388 (key schema) |
| [T-404](T-404.md) | Private-data licensing opt-out | `7-F7.44` | 2.5 | yes | T-403 (the switch row it extends) |
| [T-412](T-412.md) | BillingProvider, MockProvider and the plan catalogue | `7-F7.12` | 3 | yes | none |
| [T-413](T-413.md) | Billing API and webhook verification | `7-F7.12` | 3 | yes | T-412 (protocol, mock, catalogue) |
| [T-414](T-414.md) | Billing screen: plan, packs and add-ons | `7-F7.12` | 3 | no | T-413 (state, checkout, cancel) |
| [T-415](T-415.md) | Billing portal, billing details and invoices | `7-F7.23` | 3 | yes | T-413 (provider invoices), T-414 (the screen it sits on) |
| [T-416](T-416.md) | Cancel plan with an explicit end state | `7-F7.22` | 3 | yes | T-413 (cancel endpoint), T-414 (the screen) |
| [T-417](T-417.md) | Prepaid credits with the volume price | `7-F7.19` | 3 | yes | T-413 (checkout), T-416 (the plan page it sits next to) |
| [T-418](T-418.md) | Flex billing with a monthly spend cap | `7-F7.20` | 3 | yes | T-412 (provider and account), T-417 (spend order) |
| [T-419](T-419.md) | Three-stage spend notices | `7-F7.21` | 3 | no | T-418 (flex headroom), T-413 (the options it links to) |
| [T-420](T-420.md) | Teams add-on: seat rules and the expiry state | `7-F7.24` | 3 | yes | T-412 (catalogue), T-413 (checkout) |
| [T-421](T-421.md) | SIEM config, OTLP sender and a real test event | `7-F7.40` | 3 | yes | T-401 (the action catalogue it streams) |
| [T-422](T-422.md) | SIEM integration tab with named failure causes | `7-F7.40` | 2.5 | no | T-421 (routes) |
| [T-423](T-423.md) | SSO domains, config and the verification state machine | `7-F7.35` | 3 | yes | none |
| [T-424](T-424.md) | DNS verification, SSO setup API | `7-F7.35` | 3 | yes | T-423 (models and state machine) |
| [T-425](T-425.md) | Single sign-on tab | `7-F7.35` | 3 | no | T-424 (routes) |
| [T-426](T-426.md) | Continue with SSO on the sign-in screen | `7-F7.35` | 3 | yes | T-424 (verified issuer and client id), T-425 (the tab that enables it) |
| [T-427](T-427.md) | OAuth apps and the authorize endpoint | `7-F7.36` | 3 | yes | none |
| [T-428](T-428.md) | Token endpoint, spend attribution and OAuth audit events | `7-F7.36` | 3 | yes | T-427 (clients and codes) |
| [T-429](T-429.md) | Consent screen and authorized apps | `7-F7.36` | 3 | no | T-428 (token endpoint and client registration) |
| [T-430](T-430.md) | Directory groups and workspace gating columns | `7-F7.41` | 3 | yes | T-423 (auth groups from folder access, SSO config) |
| [T-431](T-431.md) | Sign-in group sync with role reconciliation | `7-F7.41` | 3 | yes | T-430 (gating, group map) |
| [T-432](T-432.md) | Required groups, auto-join and the four-row behaviour table | `7-F7.41` | 3 | no | T-431 (the sync it configures) |
| [T-433](T-433.md) | Branding config and asset rules | `7-F7.42` | 3 | yes | none |
| [T-434](T-434.md) | Branding screen with save and discard | `7-F7.42` | 2.5 | no | T-433 (service and routes) |
| [T-436](T-436.md) | Vendor AI keys and routing | `7-F7.50` | 3 | yes | none |
| [T-437](T-437.md) | Vendor credit rates and metering | `7-F7.50` | 2.5 | no | T-436 (the connection it bills), T-408 (the ledger it writes) |
| [T-443](T-443.md) | Delete a workspace | `7-F7.59` | 3 | yes | T-406 (the purge path this reuses) |
| [T-444](T-444.md) | Delete an account and its data | `7-F7.59` | 3 | yes | T-443 (the workspace purge it composes) |
| [T-445](T-445.md) | Danger zone screen | `7-F7.59` | 3 | no | T-443 (workspace delete), T-444 (account delete) |
| [T-446](T-446.md) | Trust, contractual and regional page | `7-F7.45` | 3 | no | none |
| [T-447](T-447.md) | Organization model for multi-workspace customers | `7-F7.61` | 3 | yes | none |
| [T-448](T-448.md) | Cross-workspace rollup API | `7-F7.61` | 3 | yes | T-447 (organizations), T-408 (the ledger it aggregates) |
| [T-449](T-449.md) | Organization dashboard | `7-F7.61` | 3 | no | T-448 (rollup API) |

### Wave E — LabelDesk-native redesign

LabelDesk-native redesign. 17 frame cards run in phase 1 (before wave A) because every later screen assumes /p/ routes, stage rails and v3 tokens; 12 finish cards run last.

**29 cards · 75 agent-hours · 4 PARITY rows listed.**

#### E.1 Rows and the cards that close them

| Parity row | Feature | Status | Wave | Task ids |
| --- | --- | --- | --- | --- |
| `1-F1.4` | Guided tour as re-runnable coach marks | PARTIAL | E | T-486 |
| `1-F3.2` | Sidebar is the lifecycle; upload is the landing page | HAVE | E/G | T-001, T-477, T-478 |
| `1-F6.2` | A brand-new workspace has a designed empty state | HAVE | E/G | T-001, T-485 |
| `3-F3.1` | Editor shell: tool rail, canvas, side panels, header | HAVE | E/G | T-003, T-497, T-498 |

#### E.2 Cards

| Task | Title | Parity rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-470](T-470.md) | Token contract: reuse the shipped glass roles, add none | — | 2 | no | none |
| [T-471](T-471.md) | Enforce a 13 px text floor and freeze stray values | — | 2.5 | no | T-470 (the mapping says which shipped role each label reads) |
| [T-472](T-472.md) | Glass: pin the shipped look and widen the fallback | — | 1.5 | no | T-470 (the mapping names `--glass-tint` / `--glass-solid` as the glass roles) |
| [T-473](T-473.md) | Thai-safe truncation: two lines, then an explicit more | — | 2.5 | no | T-470 (the mapping names the roles a label reads) |
| [T-474](T-474.md) | `/p/` project routes, with legacy URLs redirected | — | 3 | no | T-473 (independently mergeable; listed for merge order inside the E frame) |
| [T-475](T-475.md) | Every internal link through one path helper | — | 2.5 | no | T-474 (`projectPath` and the route tree must exist) |
| [T-476](T-476.md) | Workspace rail: six destinations, governance in Settings | — | 3 | no | T-474 (`/p/` routes must exist before the rail links change shape); T-400 (it owns the Settings → Audit log tab and the `/audit` redirect — this card must not add them) |
| [T-477](T-477.md) | Stage manifest: five steps, their state and their count | `1-F3.2` | 2.5 | no | T-474 (stage paths come from `projectPath`) |
| [T-478](T-478.md) | Project rail: numbered StageItem with dot, count and lock | `1-F3.2` | 3 | no | T-477 (the manifest), T-476 (one rail model per level) |
| [T-479](T-479.md) | Stage tabs: Images · Versions · Health inside one stage | — | 2.5 | no | T-474 (routes), T-478 (the rail links to a stage, not a tab) |
| [T-480](T-480.md) | One 56 px top bar; the global Train button is gone | — | 3 | no | T-472 (glass), T-476 (rail no longer carries the switcher) |
| [T-481](T-481.md) | The job tray becomes a workspace panel behind its icon | — | 2.5 | no | T-480 (the bar owns the trigger button) |
| [T-482](T-482.md) | A real command palette on ⌘K | — | 3 | no | T-476 (nav registry as the page source), T-480 (the trigger lives in the bar) |
| [T-483](T-483.md) | Project overview: the pipeline board a project never had | — | 3 | no | T-477 (stage facts), T-478 (StageItem), T-474 (the `/p/` index route) |
| [T-484](T-484.md) | Overview header: one dynamic primary and a truthful aside | — | 2.5 | no | T-483 (the page and the column exist), T-477 (`primaryLabel`) |
| [T-485](T-485.md) | Home: the queue first, then five-count project cards | `1-F6.2` | 3 | no | T-477 (stage counts), T-483 (the same stage vocabulary on the overview), T-475 (links) |
| [T-486](T-486.md) | First-run hint in the first project card, replayable | `1-F1.4` | 2 | no | T-485 (the first project card exists as a component) |
| [T-487](T-487.md) | Page header, chip, empty state and error sheet primitives | — | 2.5 | no | T-470 (tokens), T-471 (type scale) |
| [T-488](T-488.md) | Skeletons that match the geometry they replace | — | 2 | no | T-487 (the primitives file), T-485 (Home's sections) |
| [T-489](T-489.md) | Focus order, 44 px hit areas and labelled stage dots | — | 2.5 | no | T-478 (the stage rows exist), T-487 (the primitives) |
| [T-490](T-490.md) | axe and keyboard proof, with contrast measured on the real tokens | — | 3 | no | T-489 (labels and hit areas), T-487 (primitives), T-472 (the glass fill the pairs are measured on) |
| [T-491](T-491.md) | 375 px: bottom tabs, a stacked overview, no sideways scroll | — | 3 | no | T-480 (the bar), T-483 (the overview board) |
| [T-492](T-492.md) | Phone editor: a read-only preview with a desktop handoff | — | 2.5 | no | T-491 (the mobile shell), T-498 (the editor header) |
| [T-493](T-493.md) | One icon registration for every rail, stage and screen | — | 2 | no | T-478 (stage rows take an icon from the registry), T-476 (the rail's final list) |
| [T-494](T-494.md) | LabelDesk copy deck for the ten screens, in real Thai | — | 2.5 | no | T-487 (the primitives that render the copy), T-485 (Home's empty states), T-600 (the catalogue and `t()` this card fills) |
| [T-495](T-495.md) | One colour source for status, split and class chips | — | 2 | no | T-470 (tokens), T-487 (`chipTone`), T-062 (it owns `Dataset.tsx`), T-314 (it rebuilds `Deploy.tsx` and moves the class-colour mapping) |
| [T-496](T-496.md) | Annotate board: three lanes of batch rows, one way in | — | 3 | no | T-129 (bulk review confirm sheet), T-164 (read-only and empty states), T-479 (stage tabs), T-495 (colour source) |
| [T-497](T-497.md) | Editor rail: two tabs, and an inspector for the rest | `3-F3.1` | 3 | no | T-489 (44 px targets), T-471 (type floor for the rail labels) |
| [T-498](T-498.md) | Editor header: next image, review state, assists at the pointer | `3-F3.1` | 3 | no | T-497 (the rail), T-489 (hit areas), T-490 (the keyboard harness proves the path) |


### Wave X — MCP server for AI agents (appended 2026-11-17)

Owner request: *"make an MCP server so AI agents can connect to LabelDesk and use it."* One thin server over
the existing `/api/v1` developer surface: 16 tools, 3 resources and 2 prompts, over stdio and Streamable
HTTP. Every tool runs under the caller's own workspace key, so RBAC, workspace isolation, metering, rate
limits and audit stay in the one place they already live — no second permission model, no second database.
Design note: [`../../mcp/MCP-PLAN.md`](../../mcp/MCP-PLAN.md).

**10 cards · 27.5 agent-hours · ids `T-990`–`T-999`.** Eight of the ten carry R7 review (the key surface, the
credential seam, the write tools, the exposed endpoint, the audit trail and the isolation suite). Backend
work is deliberately small: six new key-authenticated routes over the browser routes that already exist for the browser
session, one `write` scope, one `whoami` field that carries the workspace switch, and one audit row per tool
call. The server itself lives in `apps/mcp/` and is deployed as its own small container on the API's origin
(`https://<domain>/mcp`), because the API image cannot share code with a `pip install`-able client without
moving its build context.

| # | Card | Hours | R7 |
| --- | --- | --- | --- |
| 1 | [T-990](T-990.md) — Key surface: read a project, search images, read and write labels | 3 | yes |
| 2 | [T-991](T-991.md) — Key surface: auto-label, create a version, list deployments, infer by image | 3 | yes |
| 3 | [T-992](T-992.md) — MCP app: skeleton, per-request key, scope-filtered tool list | 3 | yes |
| 4 | [T-993](T-993.md) — The eight read tools, with paging caps | 3 | no |
| 5 | [T-994](T-994.md) — Six write and spend tools behind one confirm gate | 3 | yes |
| 6 | [T-995](T-995.md) — Resources and prompts: read before you write | 2 | no |
| 7 | [T-996](T-996.md) — Streamable HTTP transport, per-request key, origin guard | 3 | yes |
| 8 | [T-997](T-997.md) — Audit every tool call, prove the limits | 2.5 | yes |
| 9 | [T-998](T-998.md) — Isolation and adversarial suite for the whole server | 2.5 | yes |
| 10 | [T-999](T-999.md) — Ship it: sidecar, Caddy route, client setup, R7 sign-off | 2.5 | yes |

**Rules that bind this wave beyond §3.** A tool is never more permissive than the route behind it: it calls
`/api/v1` with the caller's key and nothing else. Every spend or overwrite tool takes `confirm: true` or
answers a dry run with its cost. `tools/list` is filtered by the key's scopes (the spec allows list results
to vary by the request's authorization). No delete, deploy, key or billing tool exists. Two independent
switches: `task_992` per workspace, and the compose `profiles: ["mcp"]` per deployment.

**Merge order.** `T-990` → `T-991` (the `write` scope, then the routes that use it) → `T-992` → `T-993`,
`T-994`, `T-995` (each appends one `register(...)` line to `server.py`) → `T-996` → `T-997` → `T-998` →
`T-999` last, because it changes the deployment. Shared registries are listed in
[`.parts/wave-x.md`](.parts/wave-x.md).


### Wave F — BEYOND: the capability layer above parity

Where parity ends and a buyer starts comparing us to somebody else. Thai-first (G5.22) heads the wave because every
later screen adds strings to the catalogue it creates; then label quality, defensible auto-label, the line-side loop,
Thai vertical packs, enterprise trust, and training depth. Thirty-three cards are owner-gated or owner-held (legal,
tax, money, a licence, or a BEYOND §4 non-goal) and ship flag-off with a mock or a dry run; the line's fail-safe
policy (§4.3 #19) is the one further owner decision, and its card states it in place of a test.

**171 cards · 488 agent-hours · 101 BEYOND features listed (2 HAVE, 58 PARTIAL, 41 MISSING).**
The per-card table with role, R7 flag and dependencies is in [`.parts/wave-f.md`](.parts/wave-f.md), which is also the
part index the PM merges.

#### F.1 Bands, in merge order


| Band | First | Last | Cards | Hours |
| --- | --- | --- | --- | --- |
| Thai-first foundation — G5.22 | T-600 | T-603 | 4 | 10.5 |
| A · label quality loop — G1.x | T-610 | T-633 | 24 | 67.5 |
| D · auto-label you can defend — G4.x | T-640 | T-665 | 26 | 73 |
| C · line-side loop — G3.x | T-670 | T-697 | 28 | 80.5 |
| F · Thai market and verticals — G6.x | T-710 | T-733 | 24 | 69 |
| E · data protection and money — G5.3…G5.16 | T-740 | T-758 | 19 | 55.5 |
| E · platform trust and adoption — G5.7…G5.24 | T-760 | T-779 | 20 | 58 |
| B · training and MLOps depth — G2.x | T-780 | T-805 | 26 | 74 |
| **Total** | | | **171** | **488** |

#### F.2 Features and the cards that close them


| BEYOND id | Feature | Status | Pri | Size | Task ids | Hours |
| --- | --- | --- | --- | --- | --- | --- |
| G1.1 | Duplicate passes merged by majority, with a reviewer override | HAVE | Should | S | T-611 | 3 |
| G1.2 | Answer-key rows seeded into the live queue at a rate | PARTIAL | Should | M | T-612, T-613 | 5.5 |
| G1.3 | Score at submit, with capped retries and hints | MISSING | Could | M | T-614, T-615 | 5.5 |
| G1.4 | Quality dashboard down to class and confusion pairs | PARTIAL | Must | M | T-616, T-617 | 5.5 |
| G1.5 | Work queue with priority, stage scope and a cap per labeler | MISSING | Must | M | T-618, T-619 | 5.5 |
| G1.6 | Labeling stage graph (human, model, consensus) | MISSING | Should | L | T-620, T-621, T-622 | 8.5 |
| G1.9 | Object tracks with keyframes, an out-of-frame state, split and merge | PARTIAL | Should | M | T-623, T-624 | 5.5 |
| G1.10 | Review screen with side-by-side answer key and a mismatch list | PARTIAL | Should | M | T-625, T-626 | 5.5 |
| G1.11 | Trial project that scores a labeler before real work | MISSING | Could | M | T-627, T-628 | 5.5 |
| G1.12 | Event-triggered extension runtime on label events | PARTIAL | Could | L | T-629, T-630 | 5.5 |
| G1.13 | Label form defined as a document, not a task type | MISSING | Could | L | T-631, T-632 | 6 |
| G1.16 | Time-in-stage and labelling speed accounting | PARTIAL | Should | S | T-633 | 3 |
| G1.17 | Quality metric chosen per field, with thresholds | PARTIAL | Could | S | T-610 | 3 |
| G2.1 | Sweep a version across a parameter space | MISSING | Could | L | T-802, T-803 | 6 |
| G2.2 | The run keeps its exact configuration, exportable and re-importable | PARTIAL | Should | S | T-780 | 3 |
| G2.3 | One ledger row per run with configuration as sortable columns | PARTIAL | Should | M | T-781 | 3 |
| G2.4 | Promotion is a request naming an approver | PARTIAL | Should | M | T-782, T-783 | 5 |
| G2.5 | Lineage carries its inputs and can re-run from any node | PARTIAL | Should | M | T-784 | 3 |
| G2.6 | A model card ships with the weights | MISSING | Should | M | T-789, T-790 | 5.5 |
| G2.7 | A slice of the score opens into the images that caused it | PARTIAL | Should | M | T-785, T-786 | 5.5 |
| G2.8 | The hold-out score is audited for leakage | PARTIAL | Should | M | T-787, T-788 | 5.5 |
| G2.9 | Coverage report for the conditions the model will meet | PARTIAL | Could | L | T-792 | 3 |
| G2.10 | Suspect labels ranked by model confidence | HAVE | Could | S | T-793 | 2 |
| G2.11 | Benchmark sheet: latency and throughput per export format and device | MISSING | Should | M | T-791 | 3 |
| G2.12 | Queues with priorities, pools and quotas instead of one worker | PARTIAL | Should | L | T-798, T-799 | 6 |
| G2.13 | Bring your own GPU, and watch it in our dashboard | PARTIAL | Could | M | T-800, T-801 | 5.5 |
| G2.14 | A failed run explains itself and retries with the same arguments | PARTIAL | Should | M | T-795 | 3 |
| G2.15 | Per-run host telemetry, not just loss curves | PARTIAL | Could | S | T-794 | 3 |
| G2.16 | A published run report a non-engineer can read | PARTIAL | Should | M | T-796, T-797 | 6 |
| G2.17 | An extension point for our own and the customer's analysis | MISSING | Could | L | T-804, T-805 | 6 |
| G3.1 | Camera onboarding: discovery, profile choice, credential pre-test | PARTIAL | Should | M | T-672 | 3 |
| G3.2 | Site → line → station → camera hierarchy | PARTIAL | Must | M | T-670, T-671 | 6 |
| G3.3 | Operator verdict with reason codes and a piece id | PARTIAL | Should | M | T-675, T-676 | 5.5 |
| G3.4 | Rules that follow a schedule instead of always being on | MISSING | Should | S | T-677 | 3 |
| G3.5 | Alarm ownership, snooze, cross-camera grouping and a queue | PARTIAL | Should | M | T-678, T-679 | 6 |
| G3.6 | Evidence clip with pre/post-roll and a hold | MISSING | Should | M | T-680, T-681 | 5.5 |
| G3.7 | Store-and-forward while the edge or the server is offline | MISSING | Should | L | T-673, T-674 | 6 |
| G3.8 | Device-bound engine registry with a golden replay | PARTIAL | Should | M | T-682, T-683 | 5.5 |
| G3.9 | Training that knows its deployment target | MISSING | Should | L | T-684, T-685 | 5.5 |
| G3.10 | Prune / INT8 / QAT with an accuracy delta | PARTIAL | Should | M | T-686, T-687 | 6 |
| G3.11 | Reject signal to the machine over Modbus / OPC-UA / MQTT | MISSING | Must | M | T-688, T-689 | 5.5 |
| G3.12 | Barcode / QR / lot-code decoding | MISSING | Should | M | T-690 | 3 |
| G3.13 | OCR / OCV verification against an expected value | PARTIAL | Should | S | T-691 | 2.5 |
| G3.14 | Measurement in real units with calibration and a tolerance verdict | MISSING | Should | M | T-692 | 3 |
| G3.15 | Shift calendar, first-pass yield and reason breakdown | PARTIAL | Should | M | T-693 | 3 |
| G3.16 | Camera quality guard: readiness probe plus a per-camera baseline | PARTIAL | Should | S | T-694 | 2.5 |
| G3.17 | Event envelope contract, broker transport, dead-letter and replay | PARTIAL | Should | M | T-695, T-696 | 6 |
| G3.18 | On-camera analytics partitioning (metadata in, not pixels) | MISSING | Could | L | T-697 | 3 |
| G4.1 | A per-class prompt pack (synonyms, exclusions) that can seed the class list | PARTIAL | Must | M | T-640, T-641 | 6 |
| G4.3 | Confidence bands with an escalation threshold and per-band counts | PARTIAL | Must | M | T-642, T-643 | 5.5 |
| G4.4 | A VLM second pass that flags a box instead of deleting it | PARTIAL | Must | M | T-644 | 3 |
| G4.5 | A judge rubric returning a verdict, a reason and a score per label | MISSING | Should | M | T-645, T-646 | 5.5 |
| G4.6 | A question checklist that answers into per-image attributes | MISSING | Should | M | T-647, T-648 | 5.5 |
| G4.7 | Caption and keyword extraction written back as tags | PARTIAL | Could | S | T-649 | 2.5 |
| G4.8 | Named clusters on the embedding map, with lasso-to-label | PARTIAL | Should | M | T-650 | 3 |
| G4.9 | A per-class coverage and gap report with targets | PARTIAL | Should | M | T-651 | 3 |
| G4.10 | Active learning with margin sampling, a quota and a stated budget | PARTIAL | Should | M | T-652, T-653 | 5.5 |
| G4.11 | A discovery sweep that names classes nobody asked for | MISSING | Could | L | T-654, T-655 | 5.5 |
| G4.12 | Track a concept from one text prompt across a video with stable IDs | PARTIAL | Should | M | T-656, T-657 | 5.5 |
| G4.13 | A disagreement queue between two auto-label models | MISSING | Should | M | T-658 | 3 |
| G4.14 | A teacher → student loop with an agreement gate | PARTIAL | Should | M | T-659 | 3 |
| G4.15 | Synthetic and composited fills for a rare class, with provenance | MISSING | Could | L | T-660, T-661 | 5.5 |
| G4.16 | Harvest the boxes the checker rejected as hard negatives | MISSING | Could | S | T-662 | 2.5 |
| G4.17 | A labelling job the agent plans, trials, then escalates | MISSING | Should | L | T-663, T-664 | 5.5 |
| G4.18 | Ask the dataset a structural question in words | MISSING | Should | M | T-665 | 3 |
| G5.3 | Sign-in policy: session life, step-up, MFA, network rules | PARTIAL | Should | M | T-740, T-741, T-742, T-743 | 11.5 |
| G5.4 | Ownership transfer and an offboarding sweep | MISSING | Must | M | T-744, T-745 | 6 |
| G5.5 | Tamper-evident audit trail with a retention floor | PARTIAL | Should | M | T-746, T-747 | 6 |
| G5.6 | Object-scoped activity history | PARTIAL | Should | M | T-748, T-749 | 6 |
| G5.7 | Retention policy builder with dry-run and legal hold | PARTIAL | Should | M | T-760, T-761 | 6 |
| G5.8 | Sandbox and production separation | MISSING | Could | M | T-762, T-763 | 6 |
| G5.9 | DSAR workbench: find, export and erase one person | PARTIAL | Must | M | T-750, T-751, T-752 | 8.5 |
| G5.10 | Processing register: purpose, lawful basis, consent, transfers | PARTIAL | Should | M | T-753, T-754 | 6 |
| G5.11 | Sub-processor register with change notice and an objection window | MISSING | Should | S | T-764 | 3 |
| G5.12 | Trust centre | PARTIAL | Should | M | T-765 | 3 |
| G5.13 | Breach notification runbook with a 72-hour clock | PARTIAL | Should | M | T-766, T-767 | 6 |
| G5.15 | Customer-owned bucket and customer-managed keys | MISSING | Could | L | T-768, T-769 | 6 |
| G5.16 | Thai invoiced billing: PromptPay, bank transfer, VAT tax invoice, PO, dunning | MISSING | Must | M | T-755, T-756, T-757, T-758 | 11.5 |
| G5.17 | Per-project budget with a pre-flight estimate and pause | PARTIAL | Should | M | T-770, T-771 | 5.5 |
| G5.18 | Public status page with incident history | PARTIAL | Should | M | T-772, T-773 | 5.5 |
| G5.19 | SLA with measured uptime and a self-serve credit claim | MISSING | Could | M | T-774, T-775 | 5.5 |
| G5.20 | In-product help: what's new, docs search, feedback | MISSING | Should | S | T-776 | 3 |
| G5.21 | Guided onboarding and admin adoption analytics | PARTIAL | Could | M | T-777, T-778 | 5.5 |
| G5.22 | Thai locale end to end, including generated documents | PARTIAL | Must | L | T-600, T-601, T-602, T-603 | 10.5 |
| G5.24 | WCAG 2.2 AA with an automated gate | PARTIAL | Could | M | T-779 | 3 |
| G6.1 | Lot-bound inspection record with an OK / NG / rework disposition | PARTIAL | Must | M | T-710, T-711 | 5.5 |
| G6.2 | First-pass yield and defect Pareto per lot, line and shift | MISSING | Must | M | T-712, T-713 | 6 |
| G6.4 | Shift handover brief at the end of a shift | MISSING | Should | S | T-719 | 3 |
| G6.5 | Glove-first Thai operator screen at the station | MISSING | Should | L | T-715, T-716 | 6 |
| G6.6 | Vertical starter packs (PPE safety, IC/PCB defect) installed in one step | PARTIAL | Must | M | T-717, T-718 | 5.5 |
| G6.7 | LINE alert with evidence and an acknowledgement ladder | PARTIAL | Should | M | T-714, T-720 | 5.5 |
| G6.8 | Daily safety summary PDF for an inspector | MISSING | Should | M | T-721, T-722 | 5.5 |
| G6.10 | Shelf-gap and planogram slot compliance | MISSING | Could | L | T-723 | 3 |
| G6.11 | Price-tag read-back against a price master | PARTIAL | Could | M | T-724 | 3 |
| G6.12 | Fruit grading station by size and defect | MISSING | Could | L | T-725 | 3 |
| G6.13 | Exporter lot report with grade mix and photographs | MISSING | Could | M | T-726 | 3 |
| G6.14 | Offline field capture with deferred sync and geotag | MISSING | Should | M | T-727 | 3 |
| G6.15 | Evidence package for police or insurer | PARTIAL | Should | M | T-729, T-730 | 5.5 |
| G6.16 | Redaction of faces and plates across capture, live view and export | PARTIAL | Should | M | T-728, T-731 | 5.5 |
| G6.20 | Air-gapped on-premises install with an offline licence | PARTIAL | Should | L | T-732 | 3 |
| G6.22 | Partner console for an SI: child workspaces, licence pool, statement | MISSING | Could | L | T-733 | 3 |

#### F.3 Cards


| Task | Title | BEYOND rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-600](T-600.md) | One message catalogue and a real language switch | G5.22 | 3 | no | none (it lands before every other wave-F screen, which needs its plumbing) |
| [T-601](T-601.md) | Thai dates, numbers and the count formatters every screen uses | G5.22 | 2.5 | no | T-600 (the locale preference and `localeTag()`) |
| [T-602](T-602.md) | Exports and documents speak the same language as the screen | G5.22 | 2.5 | no | T-600 (catalogue), T-601 (formatters) |
| [T-603](T-603.md) | Thai typography under real strings: no stretch, no mid-word cut | G5.22 | 2.5 | no | T-600 (catalogue), T-601 (formatters), T-473 (`.clamp-2`, `lib/text.ts`) |
| [T-610](T-610.md) | Choose a quality metric and threshold per class | G1.17 | 3 | no | T-600 (the message catalogue every new string is keyed into) |
| [T-611](T-611.md) | Let a reviewer overrule a consensus majority | G1.1 | 3 | no | none (extends the shipped `task_23` surface) |
| [T-612](T-612.md) | Seed the answer key into a batch at a rate | G1.2 | 3 | no | T-610 (the per-class threshold the score uses) |
| [T-613](T-613.md) | Show the answer-key pool and every attempt | G1.2 | 2.5 | no | T-612 (the pool routes and the attempt history), T-600 (the message catalogue) |
| [T-614](T-614.md) | Score a submission with three attempts and hints | G1.3 | 3 | no | T-610 (per-class thresholds), T-612 (the attempt log the cap counts) |
| [T-615](T-615.md) | Ask for the score before an image goes to review | G1.3 | 2.5 | no | T-614 (the score route), T-600 (the message catalogue) |
| [T-616](T-616.md) | Measure agreement per class and swapped pairs | G1.4 | 3 | no | T-610 (the per-class threshold the report scores at) |
| [T-617](T-617.md) | Put agreement, swaps and reviewers on one screen | G1.4 | 2.5 | no | T-616 (the report route), T-600 (the message catalogue) |
| [T-618](T-618.md) | Give every image a priority, a stage and a cap | G1.5 | 3 | no | none (the queue is the base the stage graph in T-620 builds on) |
| [T-619](T-619.md) | Open a queue instead of hunting board cards | G1.5 | 2.5 | no | T-618 (the queue API), T-600 (the message catalogue) |
| [T-620](T-620.md) | Define the label path as named stages | G1.6 | 2.5 | no | T-618 (`Image.stage` and the queue read the same field), T-610 (the shared threshold vocabulary) |
| [T-621](T-621.md) | Move an image along the stage path | G1.6 | 3 | no | T-620 (the graph), T-618 (the queue rows it moves) |
| [T-622](T-622.md) | Draw the label path and publish it | G1.6 | 3 | no | T-620 (the graph), T-621 (move and reroute), T-600 (the message catalogue) |
| [T-623](T-623.md) | Give a tracked object an identity and an exit | G1.9 | 3 | no | none (extends `task_22` and `services/video.py`) |
| [T-624](T-624.md) | List the tracks beside the video timeline | G1.9 | 2.5 | no | T-623 (the track routes), T-600 (the message catalogue) |
| [T-625](T-625.md) | Show what disagrees with the answer key | G1.10 | 2.5 | yes | T-610 (per-class thresholds), T-614 (the matcher this extends) |
| [T-626](T-626.md) | Review an image against the answer key | G1.10 | 3 | no | T-625 (the conflicts route), T-600 (the message catalogue) |
| [T-627](T-627.md) | Score a labeler on a trial set before live work | G1.11 | 3 | yes | T-612 (the approved answer-key pool), T-614 (the matcher and attempt log), T-625 (per-class conflict rows) |
| [T-628](T-628.md) | Read a trial scorecard before hiring | G1.11 | 2.5 | no | T-627 (the trial routes), T-600 (the message catalogue) |
| [T-629](T-629.md) | Run a customer's checker when a label is saved | G1.12 · owner-gated | 3 | yes | T-611 (a label event exists to trigger on), T-610 (the class vocabulary the payload uses) |
| [T-630](T-630.md) | Install and watch an extension package | G1.12 · owner-gated | 2.5 | no | T-629 (the extension routes), T-600 (the message catalogue) |
| [T-631](T-631.md) | Store the label form as a document | G1.13 | 3 | no | none (annotations are already free JSON on `Image`) |
| [T-632](T-632.md) | Build the form and render it in the editor | G1.13 | 3 | no | T-631 (the form document and its validation), T-600 (the message catalogue) |
| [T-633](T-633.md) | Account for hours per stage and objects per hour | G1.16 | 3 | no | T-618 (`Image.stage`, the field time is attributed to), T-620 (the stage vocabulary), T-600 (the message catalogue) |
| [T-640](T-640.md) | Store a prompt pack on the class, apply its exclusions | G4.1 | 3 | yes | none (it lands the egress consent seam every later VLM card reads) |
| [T-641](T-641.md) | Edit the class pack, and build classes from a list | G4.1 | 3 | no | T-640 (the pack column, validation and collision rule) |
| [T-642](T-642.md) | Confidence bands, the escalation threshold, per-band counts | G4.3 | 3 | no | none (independent of the prompt pack; land after T-640 so `handlers/training.py` stays linear) |
| [T-643](T-643.md) | The review policy panel and two queues on the board | G4.3 | 2.5 | no | T-642 (the bands, the preview totals, the `bucket=review` tag) |
| [T-644](T-644.md) | Keep a doubted box, flag it, store the crop | G4.4 | 3 | yes | T-640 (the egress gate) and T-642 (the image outcome this verdict rides on) |
| [T-645](T-645.md) | Judge rubric: verdict, reason and score per label | G4.5 | 3 | yes | T-640 (the egress gate), T-644 (the verdict shape a judge row sits beside) |
| [T-646](T-646.md) | A Judge tab with a rubric picker and a results table | G4.5 | 2.5 | no | T-645 (the rubric engine, the runs and their scope shapes) |
| [T-647](T-647.md) | Question sets that answer into per-image attributes | G4.6 | 3 | yes | T-645 (the egress gate and the adapter call pattern) |
| [T-648](T-648.md) | Question set editor, answer columns and the filter chip | G4.6 | 2.5 | no | T-647 (the question store, the answer job and the `attr` filter) |
| [T-649](T-649.md) | Describe a batch: caption and keywords become tags | G4.7 | 2.5 | yes | T-645 (the egress gate) |
| [T-650](T-650.md) | Named clusters on the map, with lasso-to-label | G4.8 | 3 | no | none (reads the feature cache `services/insights_embedding.py` already writes) |
| [T-651](T-651.md) | Per-class coverage and gap report with targets | G4.9 | 3 | no | T-650 (cluster membership, for "missing from N clusters") |
| [T-652](T-652.md) | Margin sampling, a per-class floor and a stated budget | G4.10 | 3 | no | none (the engine, the cap and the pick batch already ship) |
| [T-653](T-653.md) | The active-learning card: reasons, cap and budget | G4.10 | 2.5 | no | T-652 (reasons, floor, exploration and the budget line) |
| [T-654](T-654.md) | A discovery sweep that names classes nobody asked for | G4.11 | 3 | yes | T-645 (the egress gate and the constrained-answer pattern) |
| [T-655](T-655.md) | The Discover objects panel: rank, inspect, promote | G4.11 | 2.5 | no | T-654 (the sweep, its crops and the ignore list) |
| [T-656](T-656.md) | Track a concept from one phrase, with stable ids | G4.12 | 3 | no | none (reuses `services/track.py` and the `task_22` video surface) |
| [T-657](T-657.md) | The track list: review a track as a unit | G4.12 | 2.5 | no | T-656 (the track routes, the ids and the delete action) |
| [T-658](T-658.md) | A disagreement queue between two auto-label models | G4.13 | 3 | yes | none (reuses `resolve()` and the image rows the batch already scopes) |
| [T-659](T-659.md) | Teacher → student: agreement table and a promotion gate | G4.14 | 3 | no | T-644 (the source and verdict stamps on a teacher label) |
| [T-660](T-660.md) | Synthetic fills for a thin class, with provenance | G4.15 | 3 | no | T-651 (the thin-class entry point and its target) |
| [T-661](T-661.md) | The Add examples dialog: method, preview, provenance | G4.15 | 2.5 | no | T-660 (the build job, the recipes and the tags) |
| [T-662](T-662.md) | Harvest rejected boxes as hard negatives | G4.16 | 2.5 | no | T-644 (the `box_checks` rows and their crops) |
| [T-663](T-663.md) | A labelling job the agent plans, trials, then runs | G4.17 | 3 | yes | T-645 (the egress gate), T-642 (the review bands the plan escalates with) |
| [T-664](T-664.md) | The new-job sheet: write, trial, approve, report | G4.17 | 2.5 | no | T-663 (the plan, trial, approve and report endpoints) |
| [T-665](T-665.md) | Ask the dataset a structural question in words | G4.18 | 3 | yes | T-645 (the egress gate and the constrained-answer pattern) |
| [T-670](T-670.md) | Give a plant sites, lines and stations | G3.2 | 3 | no | none (every later station card attaches here) |
| [T-671](T-671.md) | A station page that owns its cameras and model | G3.2 | 3 | no | T-670 (sites, lines, stations, camera attachment and the station counts) |
| [T-672](T-672.md) | Discover cameras and prove the password first | G3.1 | 3 | yes | none (it extends the existing stream create dialog; `Streams.tsx` is its only screen) |
| [T-673](T-673.md) | Spool events to disk before the quota drops them | G3.7 | 3 | no | T-670 (a spooled event names its station, so the drained row is attributable) |
| [T-674](T-674.md) | Drain the spool and show what is buffered | G3.7 | 3 | no | T-673 (the spool table, the writer and the ceiling policy) |
| [T-675](T-675.md) | Record a verdict with a reason code and a piece id | G3.3 | 3 | no | T-670 (a verdict names its station and takes the station's reason codes) |
| [T-676](T-676.md) | An operator screen for one gesture per piece | G3.3 | 2.5 | no | T-675 (the verdict route and the reason list), T-674 (`SpoolBadge` for the local-only notice) |
| [T-677](T-677.md) | Let a rule follow a production schedule | G3.4 | 3 | no | T-670 (the optional shift template is stored on the station) |
| [T-678](T-678.md) | Group alarms across cameras with an owner and a snooze | G3.5 | 3 | no | T-670 (a group names its station, so four cameras on one cell collapse and four lines do not) |
| [T-679](T-679.md) | A queue screen that acks, assigns and snoozes | G3.5 | 3 | no | T-678 (grouping, ack, assign and snooze), T-670 (the station a group names) |
| [T-680](T-680.md) | Assemble an evidence clip with pre- and post-roll | G3.6 | 3 | no | T-670 (a clip names its station in the event payload), T-675 (a verdict travels with the clip) |
| [T-681](T-681.md) | Hold a clip as evidence past retention | G3.6 | 2.5 | no | T-680 (the clip file and its 409 shortfall contract) |
| [T-682](T-682.md) | Pin a model build to the device it was built for | G3.8 | 2.5 | no | T-670 (a device serves a station, and the station page links the pairing) |
| [T-683](T-683.md) | Replay a golden set before a build may serve | G3.8 | 3 | no | T-682 (the builds, their profiles and the device pairing) |
| [T-684](T-684.md) | Give a training run a deployment target and a budget | G3.9 | 2.5 | no | T-682 (the device families and their TRT/CUDA bands are the same vocabulary) |
| [T-685](T-685.md) | Pick a configuration from measured accuracy and latency | G3.9 | 3 | no | T-684 (the target profile and the budget on a run) |
| [T-686](T-686.md) | Prune and quantise a model with a measured delta | G3.10 | 3 | no | T-682 (the build path and its profile), T-684 (the target the result is judged against) |
| [T-687](T-687.md) | Read the optimisation report and compare with production | G3.10 | 3 | no | T-686 (the optimise job and its report), T-682 (the build profile it names) |
| [T-688](T-688.md) | Decide what the line does when the model is down | G3.11 | 3 | yes | T-670 (a station owns the outputs), T-673 (a spooled event still counts as "the model was working") |
| [T-689](T-689.md) | Show and test the fault policy for a station | G3.11 | 2.5 | yes | T-688 (the policy routes, the watchdog and the fault rows), T-671 (the station page that reads the banner) |
| [T-690](T-690.md) | Decode a barcode or QR into a checked lot code | G3.12 | 3 | no | T-670 (a code rule belongs to a station's camera), T-675 (a verdict names the piece the code read) |
| [T-691](T-691.md) | Verify printed text against an expected value | G3.13 | 2.5 | no | T-670 (a check is registered per station and field) |
| [T-692](T-692.md) | Measure in millimetres against a tolerance band | G3.14 | 3 | no | T-671 (the station page and its calibration section), T-670 (the station the scale belongs to) |
| [T-693](T-693.md) | Read first-pass yield per shift and station | G3.15 | 3 | no | T-670 (station and shift windows), T-675 (the verdicts that make a yield) |
| [T-694](T-694.md) | Guard a camera against a drifted scene | G3.16 | 2.5 | no | T-670 (a drift belongs to a station's camera), T-680 (the clamp-and-cooldown pattern this reuses) |
| [T-695](T-695.md) | A versioned event envelope with a dead-letter queue | G3.17 | 3 | yes | T-670 (site/line/station in the envelope), T-675 (verdict and reason in the envelope) |
| [T-696](T-696.md) | Publish events to a plant broker with a delivery log | G3.17 | 3 | yes | T-695 (the envelope, the sink model, the dead-letter and the replay) |
| [T-697](T-697.md) | Pair a device that sends metadata instead of pixels | G3.18 · owner-gated | 3 | yes | T-695 (the envelope shape a device reuses), T-670 (a device serves a station) |
| [T-710](T-710.md) | Bind every disposition to a lot that survives the audit | G6.1 | 3 | no | T-670 (a unit is inspected at a station), T-675 (the verdict vocabulary this record extends) |
| [T-711](T-711.md) | The lot bar: OK, NG or rework on the station screen | G6.1 | 2.5 | no | T-710 (the lot routes), T-600 (the message catalogue), T-601 (date and count formatters) |
| [T-712](T-712.md) | First-pass yield and the defect Pareto by lot and shift | G6.2 | 3 | no | T-710 (the dispositions), T-670 (line and station), T-693 (the shift windows and their yield definition) |
| [T-713](T-713.md) | A yield board with a Pareto and a lot drill-down | G6.2 | 3 | no | T-712 (the yield routes), T-600 (catalogue), T-601 (date, count and percent formatters) |
| [T-714](T-714.md) | LINE evidence with an acknowledgement ladder | G6.7 | 3 | yes | T-670 (who is on shift for tier two); the LINE channel it extends ships in `task_33` |
| [T-715](T-715.md) | Pair a panel to a station and boot it in Thai | G6.5 | 3 | yes | T-670 (the station and its line), T-710 (the lot the panel is inspecting), T-690 (the lot code it scans) |
| [T-716](T-716.md) | The glove-first kiosk: one instruction, two targets | G6.5 | 3 | no | T-715 (pairing and the boot payload), T-711 (the disposition vocabulary it presents) |
| [T-717](T-717.md) | One step installs a vertical pack's classes and station | G6.6 | 3 | no | T-640 (the class prompt field the pack writes), T-670 (the station it creates), T-250 (the model family the station names) |
| [T-718](T-718.md) | The pack gallery: what it installs, item by item | G6.6 | 2.5 | no | T-717 (the catalogue and install route), T-600 (catalogue copy) |
| [T-719](T-719.md) | A shift handover brief the outgoing shift can send | G6.4 | 3 | yes | T-712 (yield so far), T-710 (open NG and rework), T-714 (the acknowledgement state it counts) |
| [T-720](T-720.md) | Acknowledge an incident and edit the ladder | G6.7 | 2.5 | no | T-714 (the ack state and the escalation policy), T-600 (catalogue), T-601 (dates) |
| [T-721](T-721.md) | One document sheet engine and the safety summary | G6.8 | 3 | no | T-601 (dates and counts), T-602 (the locale of a generated document), T-675 (the verdict vocabulary the incident table prints) |
| [T-722](T-722.md) | Preview the daily safety sheet and sign it | G6.8 | 2.5 | no | T-721 (the sheet route and its supervisor gate), T-600 (catalogue), T-601 (dates) |
| [T-723](T-723.md) | Planogram slots and a shelf-gap exception list | G6.10 · owner-gated | 3 | no | T-670 (the station the bay belongs to), T-711 (the disposition vocabulary a gap is not) |
| [T-724](T-724.md) | Read tags against a price master and list mismatches | G6.11 | 3 | no | T-602 (the CSV writer conventions), `task_32` (the OCR payload this card reads) |
| [T-725](T-725.md) | A grading station that measures size and assigns a grade | G6.12 · owner-gated | 3 | no | T-710 (the lot unit the grade is stored on), T-670 (the station), T-602 (document locale conventions) |
| [T-726](T-726.md) | An exporter lot report with grade mix and photographs | G6.13 | 3 | no | T-721 (the one document engine), T-710 (the lot and its units), T-725 (the grades the mix counts) |
| [T-727](T-727.md) | Field capture that queues offline and syncs later | G6.14 | 3 | no | none (it extends the shipped upload and hash-check path in `routers/images.py`; no station, lot or new transport) |
| [T-728](T-728.md) | Plate blur, static masks and a fail-closed policy | G6.16 | 3 | yes | T-680 (the clip the export policy governs), T-690 (a plate read is the same optional-driver shape) |
| [T-729](T-729.md) | An evidence package with a hash manifest and a cover | G6.15 | 3 | yes | T-728 (the redaction policy the package honours), T-680 (the clip), T-681 (the hold), T-721 (the cover sheet) |
| [T-730](T-730.md) | The evidence dialog: window, items and redaction | G6.15 | 2.5 | no | T-729 (the package routes), T-728 (the export policy it offers), T-721 (the cover sheet it previews) |
| [T-731](T-731.md) | Camera privacy controls and the export choice | G6.16 | 2.5 | no | T-728 (the policy fields and the preview route), T-730 (the export choice in the evidence dialog), T-600 (catalogue) |
| [T-732](T-732.md) | An offline licence file that verifies on the box | G6.20 · owner-gated | 3 | yes | none (a deployment-wide state; `apps/inference` and `deploy/` are the install surfaces it documents) |
| [T-733](T-733.md) | A partner console: children, a pool and a statement | G6.22 · owner-gated | 3 | yes | T-430 (the tenancy model it must not fork), T-670 (the camera count a licence is measured in) |
| [T-740](T-740.md) | Session policy store enforced at refresh and reuse | G5.3 | 3 | yes | none (the screen is T-743; step-up is T-741) |
| [T-741](T-741.md) | Step-up re-authentication before destructive actions | G5.3 | 3 | yes | T-740 (the same sign-in policy store; a step-up ticket is bounded by it) |
| [T-742](T-742.md) | Office and VPN address rules with a named refusal | G5.3 | 2.5 | yes | T-740 (the same policy surface and admin gate) |
| [T-743](T-743.md) | Sign-in policy screen with live consequence lines | G5.3 | 3 | yes | T-740 (policy + member-session routes), T-741 (the step-up sheet it reuses), T-742 (the range rules) |
| [T-744](T-744.md) | Ownership transfer with two confirmations and one audit row | G5.4 | 3 | yes | T-741 (the step-up sheet gates the hand-over) |
| [T-745](T-745.md) | Offboarding sweep: everything that depends on a member | G5.4 | 3 | yes | T-744 (both edit `routers/workspaces.py`; the sweep is the second half of the same flow) |
| [T-746](T-746.md) | Hash chain over the audit rows and a verify route | G5.5 | 3 | yes | none (T-747 renders it and adds the floor) |
| [T-747](T-747.md) | Retention floor no one can lower, and the Integrity tab | G5.5 · owner-gated | 3 | yes | T-746 (the chain and its verify route) |
| [T-748](T-748.md) | Per-image revisions and an object-scoped history route | G5.6 | 3 | no | none (T-749 renders it) |
| [T-749](T-749.md) | History rail: field deltas and restore as a new revision | G5.6 | 3 | no | T-748 (the revisions and the two routes) |
| [T-750](T-750.md) | DSAR case object with a 30-day statutory clock | G5.9 · owner-gated | 2.5 | yes | T-744 (the `models/compliance.py` module it appends to) |
| [T-751](T-751.md) | Find and export one person: scoped search and bundle | G5.9 · owner-gated | 3 | yes | T-750 (the case object and the router it appends to) |
| [T-752](T-752.md) | Erase one person and print a signed certificate | G5.9 · owner-gated | 3 | yes | T-751 (find and export), T-750 (the case), T-744 (the `Members` sheet patterns it reuses) |
| [T-753](T-753.md) | Processing register rows, transfers and consent records | G5.10 · owner-gated | 3 | yes | T-750 (the compliance router), T-752 (the Compliance page's first tab) |
| [T-754](T-754.md) | Register screen and the export an auditor takes away | G5.10 · owner-gated | 3 | yes | T-753 (the routes), T-752 (the Compliance page shell) |
| [T-755](T-755.md) | Thai invoice object: VAT lines and dry-run numbering | G5.16 · owner-gated | 3 | yes | T-412 (the `BillingInvoice` row and `pricing.py` the plan prices live in) |
| [T-756](T-756.md) | The tax-invoice document, print-first and draft-marked | G5.16 · owner-gated | 3 | yes | T-755 (the invoice row and its satang totals), T-754 (the print stylesheet block) |
| [T-757](T-757.md) | PromptPay and transfer instructions under a mock provider | G5.16 · owner-gated | 2.5 | yes | T-755 (the invoice row and `due_at`), T-412 (the mock provider boundary) |
| [T-758](T-758.md) | Invoice request, dunning clock and credit notes in one list | G5.16 · owner-gated | 3 | yes | T-755 (the invoice rows), T-756 (the document), T-757 (the payment instructions and reminders) |
| [T-760](T-760.md) | Retention rules a customer writes, one per data class | G5.7 · owner-gated | 3 | yes | none (it is the base T-761 previews and freezes) |
| [T-761](T-761.md) | Preview a sweep, then freeze a project under hold | G5.7 · owner-gated | 3 | yes | T-760 (the rules the preview evaluates) |
| [T-762](T-762.md) | A sandbox that is a mode, behind a driver seam | G5.8 | 3 | yes | none (it defines the seam T-763 fills) |
| [T-763](T-763.md) | Test keys, a refused attach, a signed promotion | G5.8 | 3 | yes | T-762 (the environment column and the driver) |
| [T-764](T-764.md) | A sub-processor register with an objection window | G5.11 · owner-gated | 3 | yes | none (the trust page T-765 links to it) |
| [T-765](T-765.md) | A trust page that says what is not certified | G5.12 · owner-gated | 3 | yes | T-764 (the register it links to), the DPA route that already ships |
| [T-766](T-766.md) | An incident with a 72-hour clock and a scope count | G5.13 · owner-gated | 3 | yes | none (T-767 drafts and sends from it) |
| [T-767](T-767.md) | Draft the controller notice, send it, keep the evidence | G5.13 · owner-gated | 3 | yes | T-766 (the incident, its clock and its scope count) |
| [T-768](T-768.md) | A storage driver seam and an honest "not available" | G5.15 · owner-gated | 3 | yes | none (T-769 fills the form behind it) |
| [T-769](T-769.md) | Connect a bucket, prove a write, and hold a key reference | G5.15 · owner-gated | 3 | yes | T-768 (the driver seam, the columns and the mode route) |
| [T-770](T-770.md) | A per-project budget that refuses before it spends | G5.17 | 3 | no | none (T-771 renders it) |
| [T-771](T-771.md) | Show the cost before the click, and who can raise the cap | G5.17 | 2.5 | no | T-770 (the budget routes and the estimate) |
| [T-772](T-772.md) | A public status page fed by probes we already compute | G5.18 · owner-gated | 3 | yes | T-766 (the incident model its banner reads) |
| [T-773](T-773.md) | Incident history, subscribers and the postmortem | G5.18 · owner-gated | 2.5 | yes | T-766 (the incident record), T-772 (the page and the sampler) |
| [T-774](T-774.md) | Measure uptime, and say when there is not enough | G5.19 · owner-gated | 3 | yes | T-772 (the samples), T-765 (the trust page section) |
| [T-775](T-775.md) | A credit claim that exists only once a schedule does | G5.19 · owner-gated | 2.5 | yes | T-774 (the measured month), T-765 (the page it sits on) |
| [T-776](T-776.md) | One help panel: what's new, docs, a report | G5.20 | 3 | yes | none (it opens beside every screen) |
| [T-777](T-777.md) | A checklist that advances only on real work | G5.21 | 3 | no | none (T-778 reads the same state) |
| [T-778](T-778.md) | Who actually labels, and who never logged in | G5.21 | 2.5 | yes | T-777 (the same workspace state and the counts helper) |
| [T-779](T-779.md) | Keyboard resize, a skip link, and a failing gate | G5.24 | 3 | no | T-490 (the scan harness), T-765 (the trust page that carries the statement), T-762 (it edits the same layout file) |
| [T-780](T-780.md) | One run keeps its whole configuration | G2.2 | 3 | no | none (it is the base every other G2 card reads) |
| [T-781](T-781.md) | Every run as one sortable ledger row | G2.3 | 3 | no | T-780 (the configuration columns come from the stored snapshot) |
| [T-782](T-782.md) | Promotion becomes a request with an approver | G2.4 | 2.5 | no | none (the alias pointer and event table already exist) |
| [T-783](T-783.md) | The promotion queue a second person answers | G2.4 | 2.5 | no | T-782 (the request contract and its routes) |
| [T-784](T-784.md) | A run node that says what went in and can be re-run | G2.5 | 3 | no | T-780 (the configuration and the `?fromModel=` seeding it exposes) |
| [T-785](T-785.md) | A slice keeps its file list, saved and re-runnable | G2.7 | 3 | no | none (evaluation detections and the manifest already exist) |
| [T-786](T-786.md) | Click a slice and land on the images to relabel | G2.7 | 2.5 | no | T-785 (the slice, saved-slice and batch routes) |
| [T-787](T-787.md) | Score the hold-out with the duplicates removed | G2.8 | 3 | no | none (pHash grouping and evaluation already ship) |
| [T-788](T-788.md) | The leak chip and the two numbers side by side | G2.8 | 2.5 | no | T-787 (the audit route and the cleaned-split setting) |
| [T-789](T-789.md) | A model card that ships beside the weights | G2.6 | 3 | no | T-785 (slice numbers), T-787 (the audited hold-out) for the auto-filled facts only |
| [T-790](T-790.md) | Write the card on the model page | G2.6 | 2.5 | no | T-789 (the card contract, its publish rule and the bundle route) |
| [T-791](T-791.md) | Answer "how fast on our box" with a per-format table | G2.11 | 3 | no | T-780 (benchmark rows sit beside the run's configuration) |
| [T-792](T-792.md) | Coverage: the conditions this data cannot separate | G2.9 | 3 | no | none (the embedding job and its 2-D projection already ship) |
| [T-793](T-793.md) | Work the suspect queue in batches, and reach Train from it | G2.10 | 2 | no | none (queue, ranking, verdicts and precision all ship behind `task_28`) |
| [T-794](T-794.md) | Per-run host telemetry, not just loss curves | G2.15 | 3 | no | none (the GPU ledger already samples used VRAM and the holder) |
| [T-795](T-795.md) | A failed run explains itself and retries unchanged | G2.14 | 3 | no | T-780 (`?fromModel=` restores the arguments the retry needs) |
| [T-796](T-796.md) | A report block document with a public link | G2.16 | 3 | yes | T-781 (the runs block reads the ledger), T-785 (the slice block) |
| [T-797](T-797.md) | Build the report, print it as a PDF | G2.16 | 3 | yes | T-796 (the report contract, publish and the public route) |
| [T-798](T-798.md) | Pools, priorities and a quota the scheduler enforces | G2.12 | 3 | no | none (the queue, the worker claim and the GPU ledger already ship) |
| [T-799](T-799.md) | The queue page and the pool picker | G2.12 | 3 | no | T-798 (pools, ordering, quota and interrupt routes) |
| [T-800](T-800.md) | Mint a one-run command for the customer's own GPU | G2.13 | 3 | yes | T-798 (the pool a remote runner advertises and claims from) |
| [T-801](T-801.md) | Run on my hardware, and see it in the dashboard | G2.13 | 2.5 | no | T-800 (the mint route, the run token and the state route) |
| [T-802](T-802.md) | A parameter space becomes a set of trial runs | G2.1 · owner-gated | 3 | no | T-780 (each trial stores its own configuration), T-781 (the trial rows are ledger rows) |
| [T-803](T-803.md) | The sweep panel and the trial rows | G2.1 · owner-gated | 3 | no | T-802 (the sweep routes, the estimate and pruning) |
| [T-804](T-804.md) | A narrow extension point for our analysis and theirs | G2.17 · owner-gated | 3 | yes | T-781 (an extension reads ledger fields), T-789 (the card can cite an extension's metric) |
| [T-805](T-805.md) | The Extensions list and the panel slot it fills | G2.17 · owner-gated | 3 | no | T-804 (the registry, validator and run route) |

---

## 7. File ownership matrix

**The rule that prevents merge failures:** a card owns a file **exclusively** only when no other card
lists it. Everything else is shared, and shared means: smallest possible edit, one line or one block,
merge in the order below, rebase before your review continues.

The matrix below was computed from all 552 cards — 381 parity plus 171 wave F — and not from their labels. Where a
card called a file exclusive that another card also edits, the label was corrected in the card and the file appears
here as shared. **If a file is in this table, it is shared, whatever a card says.**

- **Generated artefacts** (`openapi.json`, `api-types.gen.ts`): never hand-edited; regenerate after the
  merge that changed the contract. A conflict here is resolved by re-running
  `python tools/export_openapi.py` and `npm run gen:api-types`.
- **Registries over 30 cards** (`services/flags.py`, `lib/types.ts`, …): append one line per card, merge
  ascending id. A conflict is resolved by keeping both lines, never by reordering.
- The exhaustive list — all shared files with all their cards — is in
  [`_FILE-OWNERSHIP.md`](_FILE-OWNERSHIP.md). The table here is the top of that list, where conflicts
  actually happen.

| File | Cards (merge order) |
| --- | --- |
| `apps/backend/app/routers/__init__.py` | T-014, T-026, T-030, T-032, T-033, T-035, T-038, T-066, T-076, T-091, T-146, T-166, T-174, T-292, T-310, T-316, T-317, T-335, T-340, T-345, T-358, T-386, T-413, T-421, T-424, T-427, T-436, T-440, T-444, T-448 |
| `apps/frontend/src/features/settings/Settings.tsx` | T-010, T-027, T-039, T-040, T-043, T-080, T-081, T-380, T-387, T-389, T-400, T-403, T-407, T-408, T-409, T-410, T-411, T-414, T-425, T-429, T-432, T-434, T-436, T-442, T-445, T-446 |
| `apps/frontend/src/lib/api/models.ts` | T-173, T-251, T-252, T-254, T-257, T-258, T-260, T-261, T-264, T-265, T-266, T-267, T-271, T-274, T-277, T-278, T-279, T-283, T-284, T-288, T-291, T-292, T-293, T-294, T-296 |
| `apps/backend/app/routers/projects.py` | T-014, T-017, T-018, T-020, T-023, T-024, T-041, T-083, T-085, T-087, T-092, T-093, T-095, T-098, T-126, T-149, T-165, T-169, T-170, T-264, T-385, T-405 |
| `apps/frontend/src/lib/api/core.ts` | T-010, T-011, T-012, T-017, T-021, T-025, T-042, T-085, T-091, T-094, T-095, T-174, T-380, T-381, T-402, T-403, T-404, T-426, T-442, T-443, T-444, T-481 |
| `apps/frontend/src/lib/api.ts` | T-015, T-026, T-030, T-032, T-033, T-035, T-038, T-310, T-386, T-389, T-406, T-408, T-413, T-421, T-424, T-427, T-432, T-433, T-436, T-440, T-447 |
| `apps/backend/app/models/project.py` | T-020, T-023, T-025, T-032, T-041, T-069, T-078, T-082, T-087, T-094, T-095, T-127, T-142, T-170, T-171, T-320, T-328, T-345, T-405 |
| `apps/backend/app/schema/dataset.py` | T-020, T-023, T-025, T-032, T-041, T-069, T-078, T-082, T-087, T-094, T-095, T-127, T-142, T-170, T-171, T-320, T-328, T-345, T-405 |
| `apps/frontend/src/lib/recipe.ts` | T-193, T-196, T-197, T-198, T-200, T-201, T-202, T-203, T-205, T-207, T-208, T-209, T-210, T-211, T-212, T-213, T-214, T-215, T-222 |
| `apps/backend/app/handlers/training.py` | T-131, T-144, T-173, T-253, T-256, T-258, T-259, T-260, T-263, T-264, T-265, T-266, T-268, T-270, T-283, T-287, T-288, T-290 |
| `apps/backend/app/config.py` | T-029, T-032, T-042, T-066, T-085, T-089, T-100, T-159, T-190, T-274, T-283, T-287, T-288, T-293, T-350, T-437, T-438 |
| `apps/frontend/src/features/workspace/Home.tsx` | T-017, T-021, T-023, T-024, T-025, T-034, T-041, T-086, T-096, T-126, T-385, T-475, T-485, T-486, T-488, T-494 |
| `apps/backend/app/models/training.py` | T-251, T-253, T-257, T-265, T-268, T-270, T-271, T-274, T-277, T-288, T-292, T-293, T-296, T-405, T-440 |
| `apps/backend/app/models/identity.py` | T-038, T-040, T-174, T-382, T-388, T-392, T-402, T-430, T-431, T-433, T-436, T-443, T-444, T-447 |
| `apps/frontend/src/lib/nav/registry.ts` | T-015, T-027, T-345, T-387, T-400, T-414, T-425, T-432, T-434, T-436, T-446, T-474, T-476, T-477 |
| `apps/backend/app/schema/identity.py` | T-012, T-038, T-040, T-174, T-382, T-388, T-392, T-402, T-430, T-431, T-443, T-444, T-447 |
| `apps/frontend/src/features/editor/shortcuts.ts` | T-019, T-120, T-122, T-124, T-127, T-128, T-135, T-136, T-138, T-147, T-151, T-174, T-498 |
| `apps/frontend/tests/nav.test.mjs` | T-015, T-027, T-322, T-474, T-476, T-477, T-478, T-479, T-480, T-481, T-482, T-483, T-496 |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | T-043, T-093, T-129, T-132, T-142, T-143, T-164, T-165, T-173, T-475, T-495, T-496 |
| `apps/backend/app/deps.py` | T-095, T-264, T-385, T-408, T-417, T-418, T-421, T-428, T-443, T-444 |
| `apps/backend/app/schema/training.py` | T-253, T-257, T-265, T-268, T-271, T-274, T-277, T-288, T-296, T-405 |
| `apps/backend/app/services/imaging.py` | T-197, T-200, T-201, T-202, T-208, T-209, T-210, T-211, T-212, T-213 |
| `apps/frontend/src/features/project/Dataset.tsx` | T-062, T-070, T-084, T-089, T-104, T-126, T-127, T-334, T-475, T-495 |
| `apps/backend/app/routers/workflows.py` | T-319, T-320, T-321, T-324, T-326, T-327, T-328, T-330, T-401 |
| `apps/backend/app/services/billing.py` | T-412, T-413, T-414, T-415, T-416, T-417, T-418, T-419, T-420 |
| `apps/backend/app/services/recipe.py` | T-190, T-192, T-195, T-197, T-204, T-206, T-208, T-209, T-211 |
| `apps/backend/app/services/versioning.py` | T-134, T-195, T-201, T-202, T-203, T-206, T-213, T-218, T-232 |
| `apps/frontend/src/features/project/models/RunList.tsx` | T-263, T-264, T-265, T-266, T-267, T-276, T-280, T-287, T-289 |
| `apps/frontend/src/features/project/ProjectSettings.tsx` | T-018, T-023, T-034, T-041, T-069, T-126, T-165, T-337, T-351 |
| `apps/frontend/src/lib/api/deploy.ts` | T-310, T-317, T-335, T-336, T-349, T-352, T-353, T-358, T-359 |
| `apps/backend/app/routers/auth.py` | T-010, T-011, T-038, T-040, T-174, T-426, T-431, T-442 |
| `apps/backend/app/routers/versions.py` | T-100, T-191, T-192, T-199, T-216, T-223, T-230, T-232 |
| `apps/backend/app/services/keys.py` | T-388, T-390, T-392, T-394, T-395, T-396, T-397, T-398 |
| `apps/frontend/src/features/project/Models.tsx` | T-263, T-268, T-272, T-276, T-286, T-289, T-291, T-294 |
| `apps/frontend/src/features/project/versions/steps/PreprocessStep.tsx` | T-198, T-199, T-200, T-201, T-202, T-203, T-205, T-207 |
| `apps/frontend/src/lib/api/governance.ts` | T-076, T-077, T-079, T-382, T-383, T-399, T-401, T-446 |
| `apps/frontend/src/lib/api/keys.ts` | T-389, T-390, T-392, T-394, T-395, T-396, T-397, T-398 |
| `apps/backend/app/routers/streams.py` | T-337, T-338, T-339, T-346, T-347, T-356, T-357 |
| `apps/backend/app/schema/__init__.py` | T-025, T-038, T-094, T-142, T-171, T-320, T-405 |
| `apps/backend/app/services/workflows.py` | T-315, T-320, T-321, T-330, T-331, T-332, T-435 |

| Registry / generated file | Cards | Rule |
| --- | --- | --- |
| `apps/backend/openapi.json` | 204 | generated — regenerate after merge |
| `apps/frontend/src/lib/api-types.gen.ts` | 202 | generated — regenerate after merge |
| `apps/frontend/src/lib/types.ts` | 130 | append one line per card, ascending id |
| `apps/backend/app/services/flags.py` | 118 | append one line per card, ascending id |
| `apps/frontend/src/lib/api/dataset.ts` | 52 | append one line per card, ascending id |
| `apps/backend/app/routers/images.py` | 37 | append one line per card, ascending id |
| `apps/frontend/src/features/editor/Editor.tsx` | 37 | append one line per card, ascending id |
| `apps/backend/app/routers/training.py` | 36 | append one line per card, ascending id |
| `apps/backend/app/routers/workspaces.py` | 36 | append one line per card, ascending id |
| `apps/backend/app/models/__init__.py` | 35 | append one line per card, ascending id |


### Wave F additions

171 cards, 98 new flag keys, and the first shared **catalogue**. Two rules keep this band mergeable:

| Registry / generated file | Wave-F cards | Rule |
| --- | --- | --- |
| `apps/frontend/src/lib/i18n.ts` (T-600 creates it) | 106 | one key block per card, appended ascending; no card creates a second dictionary |
| `apps/backend/app/services/flags.py` | 106 | one `FLAGS` line per new key, ascending |
| `apps/backend/openapi.json` | 125 | generated — regenerate after each contract merge |
| `apps/frontend/src/lib/api-types.gen.ts` | 134 | generated with the above, never hand-edited |
| `apps/frontend/src/lib/types.ts` | 96 | one interface block per card, ascending |
| `apps/backend/app/routers/__init__.py` | 63 | one import and one `ROUTERS` entry |
| `apps/backend/app/models/__init__.py` | 43 | one import, one re-export, one `DOMAIN_MODULES` entry |
| `apps/frontend/src/lib/api.ts` | 53 | one `...xApi` spread |

| Human-edited hot file | Wave-F cards (merge order) |
| --- | --- |
| `apps/frontend/src/features/settings/Settings.tsx` | T-600, T-601, T-645, T-732, T-741, T-743, T-744, T-745, T-758, T-762, T-763, T-768, T-771, T-775, T-778, T-799, T-805 |
| `apps/backend/app/config.py` | T-645, T-647, T-649, T-654, T-656, T-658, T-659, T-660, T-663, T-683, T-685, T-686, T-751, T-752, T-757, T-791 |
| `apps/frontend/src/lib/api/models.ts` | T-624, T-659, T-780, T-783, T-786, T-788, T-790, T-791, T-794, T-795, T-799, T-801, T-803 |
| `apps/frontend/src/lib/api/dataset.ts` | T-602, T-641, T-648, T-649, T-653, T-655, T-657, T-658, T-661, T-662, T-664, T-793 |
| `apps/frontend/src/features/project/Models.tsx` | T-659, T-683, T-687, T-780, T-783, T-790, T-791, T-794, T-795, T-801, T-805 |
| `apps/backend/app/schema/streams.py` | T-670, T-675, T-678, T-680, T-688, T-690, T-694, T-714, T-723, T-728 |
| `apps/backend/app/schema/dataset.py` | T-611, T-618, T-633, T-640, T-647, T-649, T-725, T-727, T-761 |
| `apps/backend/app/schema/identity.py` | T-618, T-640, T-733, T-740, T-742, T-747, T-762, T-768, T-777 |
| `apps/backend/app/routers/images.py` | T-614, T-631, T-647, T-649, T-660, T-662, T-692, T-727, T-728 |
| `apps/backend/app/routers/training.py` | T-642, T-658, T-659, T-770, T-780, T-798, T-800, T-802 |
| `apps/backend/app/worker.py` | T-674, T-714, T-757, T-772, T-795, T-798 |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | T-643, T-644, T-653, T-658, T-664 |
| `apps/frontend/src/features/editor/Editor.tsx` | T-615, T-626, T-632, T-644, T-648, T-692, T-749 |

The full file → cards map for this wave, including every new module that a second card appends to, is in
[`.parts/wave-f.md`](.parts/wave-f.md) §"Shared-file users". Twelve exclusive-file collisions were found between
bands and resolved in the cards (§7.1a).

### 7.1 Exclusive-file collisions found and resolved

Eight files were declared exclusive by two cards each. The resolution is recorded in the cards:

| File | Cards | Resolution |
| --- | --- | --- |
| `packages/sdk/labeldesk/client.py` | T-022, T-075 (+T-344) | Shared; T-342 creates the methods, T-022/T-075 append, T-344 appends `batch/jobs/workflows` |
| `packages/sdk/labeldesk/cli.py` | T-022, T-075, T-344 | T-344 owns the parser and exit codes; the other two register subcommands |
| `apps/backend/tests/test_sdk_cli.py` | T-022, T-075, T-344 | Append-only sections, in that order |
| `apps/backend/tests/test_folders.py` | T-024, T-094 | T-024 creates, T-094 appends |
| `apps/frontend/src/features/workspace/FolderTree.tsx` | T-025, T-096 | T-025 creates and owns, T-096 adds drag-move and the access dialog |
| `apps/frontend/tests/folder-tree.test.mjs` | T-025, T-096 | T-025 creates, T-096 appends |
| `apps/backend/app/services/folder_access.py` | T-095, T-384 | T-095 creates the enforcement; T-384 adds the grant table |
| `packages/sdk/labeldesk/config.py` | T-348, T-441 | T-348 creates the credential file module; T-441 stores the default workspace |


#### 7.1a Wave F collisions found and resolved

Six bands were authored in parallel, so twelve files were claimed exclusively by two cards. Each resolution was
written into the later card: it lists the file under **Shared** with the merge order, and the earlier card keeps it.

| File | Cards | Resolution |
| --- | --- | --- |
| `apps/backend/app/config.py` | T-629, T-791 | T-791 appends one `LD_LOCAL_JOBS` entry after T-629 |
| `apps/backend/app/models/extensions.py`, `services/extensions.py`, `routers/extensions.py`, `tests/test_extensions.py` | T-629, T-804 | T-629 creates the module; T-804 appends one class, function, route and test section |
| `apps/backend/app/routers/queue.py` | T-618, T-798 | T-618 creates the labeling queue router; T-798 appends the run-pool routes |
| `apps/backend/app/routers/training.py` | T-684, T-770 | T-770 appends the budget checks after T-684's target fields |
| `apps/backend/app/services/evidence.py` | T-681, T-729 | T-681 creates the clip hold; T-729 appends the package builder |
| `apps/backend/app/services/retention.py` | T-681, T-761 | T-761 appends the legal-hold guard after T-681's clip hold |
| `apps/backend/app/worker.py` | T-629, T-674, T-772 | ascending: extensions dispatch, then spool drain, then status sample |
| `apps/backend/tests/test_coverage.py` | T-651, T-792 | T-651 creates; T-792 appends its section |
| `apps/frontend/src/lib/api/extensions.ts` | T-630, T-805 | T-630 creates; T-805 appends two calls |

### 7.2 Cross-area rows (one piece of work, one owner)

The rows below are one piece of work that two areas both list. The owning card declares the foreign row,
so the mapping is complete from either direction:

| Row | Owning card | Area that maps it |
| --- | --- | --- |
| `3-F3.40` | T-020 (shared class vocabulary) | 3 |
| `4-F4.12` | T-100 (rebalance strategies) | 4 |
| `6-F6.13` | T-391 (key disable/rotate) | 6 |
| `7-F7.2`, `7-F7.3` | T-039 (members panel) | 7 |
| `7-F7.4` | T-038 (join links) | 7 |
| `7-F7.5` | T-040 (same-domain join) | 7 |
| `7-F7.46` | T-076 (credential store) | 7 |
| `7-F7.47` | T-080 (connectors screen) | 7 |
| `7-F7.48` | T-079 (sync guards) | 7 |
| `1-F4.3` | T-060 (query language) | 1 |
| `1-F5.6`, `2-F2.45` | area 7 trash cards | 1, 2 |
| `2-F2.25` | T-026–T-029 (asset library) | 2 |
| `2-F2.20`, `7-F7.55` | T-032, T-037 (fork) | 2, 7 |
| `7-F7.54` | T-035, T-036 (public project page) | 7 |
| `7-F7.18`, `7-F7.56` | T-252/T-254, T-257/T-258 | 7 |
| `7-F7.53` | T-033/T-034 (publish licence) | 7 |

### 7.3 Labels corrected during assembly

- **Guards are per area.** `.parts/area-2.md`, `area-3.md`, `area-4.md` and `area-5.md` numbered guards
  by theme before §6b of the brief fixed the convention. `INDEX` uses `T-001` = area 1 … `T-007` = area
  7 for every HAVE row; no card body depends on the old numbering.
- **HAVE rows with real gap cells got top-up cards.** `2-F2.38`, `2-F2.39`, `2-F2.44`, `4-F4.44`
  (T-104), `3-F3.12` (T-172), `3-F3.28`, `3-F3.33` (T-173), `3-F3.51` (T-174), `4-F4.2`, `4-F4.10`
  (T-232), `5-F5.52` (T-296). They stay mapped to their guard as well.
- **Area 1's part-index header miscounts statuses** (says 14 PARTIAL / 6 MISSING; `PARITY.md` and the
  rows themselves give 12 / 8). All 27 rows are mapped; the header line is the only error.

---

## 7.4 Wave E arbitration — where REDESIGN and the running app disagree

The redesign lane resolved these in its cards; the owner or the merge captain can overrule any of them.
They are listed so nobody "fixes" a card back to the old behaviour by accident.

**Owner revision pass, 2026-11-17.** The owner's `VISUAL-OVERRIDE.md` makes the running app's Liquid Glass the
visual standard: the frames keep layout, IA, flow, states and copy, and lose every claim over colour, surface,
blur, radius and type. Rows 1, 3, 6 and 8–15 are the cards revised for that rule; nothing in them changes a route,
a screen's purpose or its flow.

| # | Conflict | Resolution in the cards |
| --- | --- | --- |
| 1 | REDESIGN §6.1 lists literal hex tokens and a new seed (`#5B4BE0`); the app derives every role from HCT at runtime (seed `#3b6cf6`) | **Revised (was: move the seed).** T-470 now adds no variable and changes no seed: it writes one mapping from the frame vocabulary (`surface-container`, `outline`, `text-muted`, `glass-fill`, `glass-blur`) onto the shipped roles, and its test forbids a parallel token family. The hex table stays a design reference, not a palette |
| 2 | REDESIGN §3.2 draws seven rail labels and calls them "six items" | T-476 ships five destinations plus Admin, with governance as Settings tabs; the count is asserted in `nav.test.mjs` |
| 3 | Glass numbers differ (redesign 24 px / 62–66 % / 96 % fallback vs app 16–20 px / 58–62 % / 92 %) | **Revised (was: adopt the redesign values).** T-472 now keeps 16/20 px, 58/62 %, 80/84 % and 92 %, pins them in `glass.test.mjs`, and only widens the reduced-transparency fallback to every glass class. T-490 measures contrast on the tokens the browser actually paints |
| 4 | The global "Train Model" button is injected through a `#topbar-actions` portal in `ProjectLayout` | T-480 deletes the portal rather than hiding it; the stage owns its primary |
| 5 | Area 7 cards say "the rail already points at this tab" | Their tabs survive; T-476 drops the rail entry. The sentence is corrected at merge, not re-planned |
| 6 | 179 sub-12 px text occurrences in 30 files | **Revised.** T-471 adds no `--text-*` token: metadata moves to `text-sm` (14/20) and only chips and table headers may use `text-xs` (12/16), so no arbitrary size exists. The frozen map still only shrinks, and each owning card clears its own file |
| 7 | Dataset Health lives inside the Insights studio, but §3.3 puts Health in the Dataset stage | T-479 mounts the existing component under the stage tab; T-103 owns the chart work and the eventual single home |
| 8 | REDESIGN §6.4 asks for status/split/class chip tokens beyond the app's roles | **Revised.** T-487's `chipTone` returns the shipped idiom (`bg-success/15 text-success`, `bg-warning/15`, `bg-info/15`, `bg-destructive/15`, `bg-secondary`); no `--*-bg` variable is added, and the page title uses the shipped `text-2xl` instead of a new 28/34 size |
| 9 | REDESIGN §10.2 turns twelve hex pairs into a contrast table | **Revised.** T-490 reads `index.css`'s `oklch()` fallbacks for the static half and the browser's computed colours for the HCT-derived half; the v3 hex literals are not asserted, because they describe nothing that ships |
| 10 | The v3 mobile frame wants a `--mobile-tabbar` token | **Revised.** T-491 uses `h-14` plus `pb-[env(safe-area-inset-bottom)]`; no mobile-only custom property enters the token block |
| 11 | Two cards would each own a "colour source" | **Revised.** T-495 stays the single source (`classColor`, `splitColor`, `statusTone`) and every wave-F card renders a chip through one of them; a new colour constant is a test failure |
| 12 | T-494 (E-finish) planned `lib/copy.ts`, but wave F's Thai card needs the catalogue earlier | **Revised.** T-600 creates `lib/i18n.ts` and the language switch at the head of wave F; T-494 now depends on it and fills the ten screens' keys instead of creating a second deck |
| 13 | A tenant's branding could become a second palette | **Revised.** T-434's eleven swatches write the existing role variables through `applyTheme()`'s role map; the preview renders the same glass system with a different seed |
| 14 | Twenty-two E cards build a surface and said nothing about which primitive it uses | **Verified, one line added.** T-476, T-478–T-486, T-488, T-492, T-496–T-498 now carry a `Glass:` bullet naming `Glass` / `Card` and the token each surface uses; T-474, T-475, T-477 and T-479–T-482 are routes, nav or composition and need none |
| 15 | T-473 and T-498 still referred to the removed `text-micro` / `text-small` utilities | **Revised.** Both now name `text-sm` / `text-xs`; T-473 depends on T-470's mapping rather than on a type-scale token |

### 7.5 Ordering exceptions (merge order ≠ id order)

Four train-screen cards build child components that a lower id imports. Merge them in this order, not
ascending id:

```
T-262 (PreflightList) → T-261 (DataBlock) → T-256 (RecipePanel) → T-255 (Train container) → T-251 (FamilyGrid access)
```

Every other family merges ascending within its wave. Two path notes for the captain: `features/project/train/`
and `features/project/versions/steps/` are new directories created by their first card, and `apps/sdk` files
are shared by id order T-022 → T-075 → T-344 → T-348 → T-441.

---

## 8. Risks the merge captain should watch

| # | Risk | Why it bites | Mitigation in this plan |
| --- | --- | --- | --- |
| 1 | `Editor.tsx` is touched by 37 cards | It is the product's core file; a bad merge is a lost week | Wave B's editor lane is serialised; behaviour cards land before E-finish's shell cards; the matrix orders them |
| 2 | `openapi.json` + `api-types.gen.ts` conflicts | 204 cards change the contract | Regenerate, never hand-merge; run the contract test after every merge |
| 3 | Migration ordering | This repo has no Alembic; `schema.apply` is ordinal | One migration-bearing branch at a time; existing-database test per merge |
| 4 | Flags nobody turns on | 100+ new keys can hide unfinished work forever | Every card's flag-off acceptance and one flag per surface; `task_470` (`ui_v3`) is the only cross-screen switch |
| 5 | Wave D encodes a guess | Provider, prices and licence are undecided | Mock provider, `None` prices, "Pricing not set", flag off |
| 6 | Numbers disagree across screens (uploaded / annotated / approved) | REDESIGN §9 risk R3 | `T-104` and `T-479` pull counts from one API vocabulary; the guard asserts today's counts |
| 7 | 13 px type floor and glass fallback regress | Token fixes are easy to undo in a later card | `T-471`, `T-472`, `T-490` assert them mechanically |
| 8 | Wave B's 419 h | It is half the programme | Four parallel families with disjoint exclusive files; E-frame already landed |
| 9 | Wave F encodes a legal or commercial guess | 33 cards touch tax, PDPA, retention, SLA, licensing or a B2B claim | Every one is owner-gated in §4.3, ships flag-off with a mock or dry run, and asserts no fact: `Pricing not set`, `not certified`, `no measured history yet` |
| 10 | 98 new flag keys on top of parity's 118 | A flag nobody turns on hides finished work forever | One key per surface, named in the card, with a flag-off acceptance line; wave F reuses eight keys across related cards rather than minting one per card |
| 11 | Thai strings that are literal translations | Half-translated Thai is worse than English on a factory floor | T-600's catalogue is the only dictionary, T-603's 30 % stress run proves the layout, and every card authors real Thai in the same commit as the English |
| 12 | Wave F's four owner-held non-goals get scheduled by accident | BEYOND §4 rules them out; the owner asked for every row anyway | Each card's Notes open with `Owner-hold:` and each ships behind its flag; §5 names them |
| 13 | Two waves touching the same registry (`flags.py`, `i18n.ts`, `openapi.json`) | F runs after C and before E-finish, so a rebase is inevitable | §7's wave-F block gives the merge order per file; generated artefacts are regenerated, never merged |

---

## 9. Completeness verification

Computed mechanically from `PARITY.md`, `BEYOND.md` and the 552 card headers at assembly time:

- PARITY rows parsed: **334** — 72 HAVE, 163 PARTIAL, 99 MISSING (matches `PARITY.md:437`).
- Gap rows with at least one card: **262 / 262**.
- HAVE rows with a guard: **72 / 72**.
- Card ids: **381**, unique, `T-001`–`T-498` with no duplicate; every card declares ≥ 1 parity row or is
  a wave-E redesign card (23 such cards, listed with `—` in the wave-E table).
- Unknown parity ids referenced by cards: **0**.
- Cards exceeding 3 agent-hours: **0**.
- Files claimed exclusively by two cards: **0** (after §7.1).
- BEYOND rows parsed: **101** — 2 HAVE, 58 PARTIAL, 41 MISSING (matches `BEYOND.md` §6).
- BEYOND rows with at least one card: **101 / 101**; the four rows BEYOND §1 assigns to parity (`G5.1`, `G5.2`,
  `G5.14`) and folds into `G5.22` (`G5.23`) have no card here, by design.
- Wave F cards: **171**, `T-600`–`T-805`, unique, contiguous inside each band, every one ≤ 3 agent-hours
  (mean 2.85), every one carrying a `Glass:` line, a flag-off acceptance line and a cross-workspace 404 line.
- Wave F total: **488 agent-hours**; R7 `yes` on **62** cards; **33** owner-gated or owner-held, plus the line's
  fail-safe decision recorded on T-688/T-689 (§4.3 #19).

Re-run the check any time with the assembly script logic: read every `T-*.md`, extract the
`| Parity rows |` cell, and diff the set against `PARITY.md`'s and `BEYOND.md`'s id columns.

---

## 10. Definition of done

The programme is done when:

- [ ] `pytest` is green serially, `npm run build` is green, node tests are green, ruff is clean at the
      CI-pinned version, and the OpenAPI contract test passes.
- [ ] The 262 gap rows each have a card whose acceptance criteria are demonstrably met, and the card's
      flag-off state is tested.
- [ ] The seven guards pass on the final tip, so no HAVE flow regressed on the way.
- [ ] Every shared file was merged in the matrix order, and no branch carried a hand-edited generated
      artefact into a merge.
- [ ] Wave D remains inert without the three owner decisions: no charge, no vendor name, no price.
- [ ] Wave F's 101 features each have a card whose acceptance criteria are demonstrably met, and the card's
      flag-off state is tested.
- [ ] Wave F remains inert without §4.3's answers: no legal claim, no tax number, no price, no certification,
      no SLA figure, and no `Owner-hold` card scheduled.
- [ ] Thai is real on the labeler and operator surfaces: the catalogue has no untranslated key on a converted
      screen, and T-603's stress run is green.
- [ ] One design system: no new CSS variable, hex literal, arbitrary font size or second palette exists anywhere
      in `src`, and the glass tokens are the ones T-472 pins.
- [ ] A demo pass of waves A–C needs no explanation of a missing state: empty, loading, error and
      permission states all render as the cards describe.

Programme ledger for the owner: [`parity-backlog-report.md`](../../../../.superpowers/sdd/2026-10-31-labeldesk-v2/parity-backlog-report.md).

---

## 11. Wave M — MLflow parity (appended 2026-11-17)

Owner directive: "copy Roboflow and MLflow entirely". This wave closes the MLflow half, the way waves A–F
close Roboflow and BEYOND. Source of truth:
[`docs/research/mlflow-parity/MLFLOW-PARITY.md`](../../mlflow-parity/MLFLOW-PARITY.md) — **92 rows** (5 HAVE,
48 PARTIAL, 39 MISSING, one by design), backed by five area files that carry the click-by-click flow,
states, code evidence and a docs URL per claim.

**82 cards · 211.5 agent-hours · ids `T-900`–`T-987`.** Every card follows `_BRIEF.md` §2 with the wave-M
deviations: `| Wave | M |`, MLflow row ids in `| Parity rows |`, and an `Overlap:` first line in Notes
naming the Roboflow card it sits beside. Flags follow house convention — one `task_<id>` key per card, 43
in total; three of them carry most of the wave (`task_mlruns` 21 cards, `task_mltraces` 6, `task_mlgenai`
6) and the rest are per-screen keys so a single surface can ship alone. Budget **250–270 agent-hours** end
to end with review.

| Lane | Cards | Hours | Depends on |
| --- | --- | --- | --- |
| M1a Runs and tracking | T-900–T-916 | 44 | wave B train lane `T-250`–`T-296` |
| M1b Registry, versions and contract | T-918–T-931 | 37.5 | wave B `T-257`/`T-268`; independent of M1a |
| M2 Models and deployment | T-932–T-942 | 27 | M1b (`ML2-T2.7` contract) |
| M3 Evaluation, traces and prompts | T-946–T-965 | 53 | wave B `T-283`/`T-284`, M1a run table |
| M4 Platform, experiments and wire API | T-968–T-987 | 50 | M1a + M1b tables; the wire routes last |

**Order.** Wave M starts after wave B's train and evaluation lane merges: eleven cards extend files that
lane rewrites (`TrainedModel`, the model detail screen, `T-283`/`T-284` comparison) and the run table the
wire API reads belongs to M1a. M1a and M1b run in parallel — different files, different surfaces. M2
follows M1b. M3 follows M1a and `T-283`. M4 is last: `T-983`/`T-984` (the `/api/2.0/mlflow/*` subset) open a
new request surface onto customer run data and both carry R7 review.

**Deduplication.** 19 rows point at an existing card; 13 of them need no new card at all. The `Overlap:`
line on every card names that card, so no merge captain schedules the same work twice.

### M1a Runs and tracking

**17 cards · 44.0 hours.**

| Task | Title | Hours | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- |
| T-900 | Guard area 1: the training run record stays honest | 2.5 | no | `none` | `apps/backend/tests/test_mlruns_guard.py` |
| T-901 | Run settings block: the parameters a run used | 2.0 | yes | `task_mlruns` | `apps/backend/app/services/run_view.py` |
| T-902 | Every metric point gets a time, not just an epoch | 2.5 | no | `none` | `apps/backend/tests/test_run_metric_times.py` |
| T-903 | Curves keep drawing while a run is still training | 2.0 | no | `none` | `apps/frontend/src/features/insights/runLive.ts` |
| T-904 | Parallel coordinates: 1–6 runs across every metric at once | 2.5 | no | `none` | `apps/frontend/src/features/insights/parallelRuns.ts` |
| T-905 | Continued runs: a parent link, not two unrelated rows | 2.0 | no | `none` | `apps/frontend/src/features/project/models/runLineage.ts` |
| T-906 | Run tags and a run note | 2.5 | yes | `none` | `apps/frontend/src/features/project/models/RunTags.tsx` |
| T-907 | A filter grammar for the run list | 3.0 | yes | `none` | `apps/backend/app/services/run_filter.py` |
| T-908 | The filter bar on the run list | 2.5 | no | `none` | `apps/frontend/src/features/project/models/runQuery.ts` |
| T-909 | Saved run views you can hand to a teammate | 2.5 | no | `none` | `apps/frontend/src/features/project/models/runViews.ts` |
| T-910 | Host metrics sampled during a run | 3.0 | no | `none` | `apps/backend/app/services/system_metrics.py` |
| T-911 | Artifacts and checkpoints of a run, listed | 3.0 | yes | `none` | `apps/backend/app/services/run_artifacts.py` |
| T-912 | The artifacts panel on the run page | 2.5 | no | `none` | `apps/frontend/src/features/project/models/RunArtifacts.tsx` |
| T-913 | Which dataset a run actually consumed | 2.5 | no | `none` | `apps/frontend/src/features/project/models/RunDataset.tsx` |
| T-914 | A notebook can create and log into a run | 3.0 | yes | `task_mlruns_wire` | `apps/backend/app/models/mlruns.py` |
| T-915 | Search, metric history, restore and artifacts on the wire | 3.0 | yes | `none` | `apps/backend/tests/test_mlrun_wire_search.py` |
| T-916 | Prove the wire API with the real client, and document it | 3.0 | no | `none` | `apps/backend/requirements-mlflow.txt` |

### M1b Registry, versions and contract

**14 cards · 37.5 hours.**

| Task | Title | Hours | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- |
| T-918 | Give every model row a registered name and a version number | 3.0 | no | `task_918` | `apps/backend/app/services/model_registry.py` |
| T-919 | Group the Models rail by registered name, with search | 3.0 | no | `task_919` | `apps/frontend/src/features/project/models/RegistryRail.tsx` |
| T-920 | Keep deleted versions as tombstones so numbers are never reused | 2.0 | yes | `task_920` | `apps/backend/tests/test_model_tombstones.py` |
| T-921 | Free-form aliases on a version, with production reserved | 3.0 | no | `task_921` | `apps/frontend/src/features/project/models/AliasChips.tsx` |
| T-922 | Key-value tags on a model version, filterable | 2.0 | no | `task_922` | `apps/backend/app/services/model_tags.py` |
| T-923 | Tag chips, an editor and a tag filter on the model page | 3.0 | no | `task_923` | `apps/frontend/src/features/project/models/TagEditor.tsx` |
| T-924 | Deprecate a version with a reason, without deleting it | 2.5 | no | `task_924` | `apps/backend/app/services/model_lifecycle.py` |
| T-925 | A "produced by" panel on the model page | 2.5 | no | `task_925` | `apps/backend/app/services/model_provenance.py` |
| T-926 | A declared contract on every version: input, output, parameters | 3.0 | no | `task_926` | `apps/backend/app/services/model_contract.py` |
| T-927 | A written description on the model and on each version | 2.0 | no | `task_927` | `apps/backend/app/services/model_text.py` |
| T-928 | Show a real example input on the model page | 2.5 | no | `task_928` | `apps/backend/app/services/model_example.py` |
| T-929 | Restrict one model to managers or admins | 3.0 | yes | `task_929` | `apps/backend/app/services/model_access.py` |
| T-930 | Emit model-registry events on the existing webhook channel | 3.0 | yes | `task_930` | `apps/backend/app/services/registry_events.py` |
| T-931 | A Webhooks screen under workspace settings | 3.0 | yes | `task_931` | `apps/frontend/src/features/settings/Webhooks.tsx` |

### M2 Models and deployment

**11 cards · 27.0 hours.**

| Task | Title | Hours | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- |
| T-932 | A family says what it can do | 2.5 | no | `none` | `apps/backend/app/adapters/base.py` |
| T-933 | The artefact explains itself | 3.0 | yes | `task_mlartefact` | `apps/backend/app/services/artefacts.py` |
| T-934 | A refused request costs nothing | 2.0 | no | `task_mlcontract` | `apps/backend/app/services/contract_guard.py` |
| T-935 | The environment travels with the weights | 2.5 | no | `none` | `apps/backend/app/services/model_env.py` |
| T-936 | How big is this model, really | 2.0 | no | `none` | `apps/backend/app/services/model_size.py` |
| T-937 | A deployed model you can probe | 2.0 | yes | `none` | `apps/backend/app/routers/model_health.py` |
| T-938 | Container files for one model | 3.0 | yes | `task_mlcontainer` | `apps/backend/app/services/container.py` |
| T-939 | Drop in a new model family | 2.5 | yes | `none` | `apps/backend/app/adapters/plugins.py` |
| T-940 | A deployment records whether it answers | 2.5 | no | `none` | `apps/backend/app/services/deploy_health.py` |
| T-941 | Register a target you run yourself | 3.0 | yes | `task_mltarget` | `apps/backend/app/models/targets.py` |
| T-942 | Ask a vision model your own question | 2.0 | yes | `task_mlprompt` | `apps/backend/app/routers/predict_vlm.py` |

### M3 Evaluation, traces and prompts

**20 cards · 53.0 hours.**

| Task | Title | Hours | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- |
| T-946 | Pin an evaluation set: table, digest and create route | 3.0 | no | `task_mlruns` | `apps/backend/app/models/evaluation.py` |
| T-947 | Score any model on a pinned set, from its panel | 2.5 | no | `task_mlruns` | `apps/frontend/src/features/evaluation/EvaluateMenu.tsx` |
| T-948 | Release rules: store a metric threshold and judge a model | 3.0 | no | `task_mlruns` | `apps/backend/app/routers/release_rules.py` |
| T-949 | The gate answers in the deploy dialog | 2.5 | yes | `task_mlruns` | `apps/frontend/src/features/project/deploy/GateGate.tsx` |
| T-950 | Classification gets its own evaluation preset | 3.0 | no | `task_mlruns` | `apps/backend/tests/test_evaluate_classify.py` |
| T-951 | A customer's own metric, declared not coded | 3.0 | yes | `task_mlruns` | `apps/backend/app/routers/custom_metrics.py` |
| T-952 | Score a prediction file someone handed you | 2.5 | yes | `task_mlruns` | `apps/backend/app/services/external_results.py` |
| T-953 | Is the difference real? Paired deltas with an interval | 3.0 | no | `task_mlruns` | `apps/backend/app/services/compare_stats.py` |
| T-954 | One trace per request: table, emit call, read route | 3.0 | yes | `task_mltraces` | `apps/backend/app/services/tracing.py` |
| T-955 | The trace list, its filters and the span waterfall | 3.0 | no | `task_mltraces` | `apps/backend/app/services/trace_query.py` |
| T-956 | Every adapter call traced without editing the adapter | 3.0 | no | `task_mltraces` | `apps/frontend/src/features/project/settings/Tracing.tsx` |
| T-957 | Mark any function as a step, by hand | 2.0 | no | `task_mltraces` | `apps/backend/tests/test_manual_tracing.py` |
| T-958 | Accept OpenTelemetry traces from a customer's own service | 2.5 | yes | `task_mltraces` | `apps/backend/app/routers/otel.py` |
| T-959 | What each call cost in time and tokens | 2.5 | no | `task_mltraces` | `apps/backend/app/services/model_cost.py` |
| T-960 | Score a VLM answer on the axes that matter | 3.0 | yes | `task_mlgenai` | `apps/backend/app/services/judges.py` |
| T-961 | A judge written as criteria, versioned like a prompt | 2.0 | yes | `task_mlgenai` | `apps/frontend/src/features/project/settings/CustomJudges.tsx` |
| T-962 | Does the judge agree with your reviewers? | 2.5 | no | `task_mlgenai` | `apps/backend/app/services/judge_agreement.py` |
| T-963 | Store the answer a human would accept | 2.0 | no | `task_mlgenai` | `apps/frontend/src/features/evaluation/Expectations.tsx` |
| T-964 | Prompts with immutable versions and an alias | 3.0 | yes | `task_mlgenai` | `apps/backend/app/models/prompts.py` |
| T-965 | The Playground keeps what you tried | 2.0 | no | `task_mlgenai` | `apps/frontend/src/features/playground/runs.ts` |

### M4 Platform, experiments and wire API

**20 cards · 50.0 hours.**

| Task | Title | Hours | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- |
| T-968 | A run spec committed next to the code | 3.0 | yes | `task_968` | `apps/backend/app/services/run_spec.py` |
| T-969 | Typed parameters and the resolved plan | 2.5 | no | `task_969` | `apps/backend/tests/test_train_params.py` |
| T-970 | Check before you spend | 2.0 | no | `task_970` | `apps/backend/app/services/train_preflight.py` |
| T-971 | Record the environment a run happened in | 2.5 | no | `task_971` | `apps/backend/app/services/env_fingerprint.py` |
| T-972 | Choose where a run executes, and see who claimed it | 3.0 | yes | `task_972` | `apps/backend/app/services/workers.py` |
| T-973 | A pipeline file becomes a workflow | 3.0 | yes | `task_973` | `apps/backend/app/services/pipeline_file.py` |
| T-974 | Profiles: one pipeline, three settings | 2.5 | no | `task_974` | `apps/backend/tests/test_pipeline_profiles.py` |
| T-975 | Run a pipeline from the terminal | 2.5 | no | `task_975` | `apps/backend/tests/test_pipeline_cli.py` |
| T-976 | "Why can this person do this?" | 2.5 | yes | `task_976` | `apps/backend/tests/test_rbac_explain.py` |
| T-977 | Refuse a request that arrived under the wrong host name | 2.0 | yes | `task_977` | `apps/backend/app/services/runtime_state.py` |
| T-978 | Experiments exist as a container for runs | 3.0 | no | `task_978` | `apps/backend/app/services/experiments.py` |
| T-979 | Tag, note and restore an experiment | 2.5 | no | `task_979` | `apps/backend/tests/test_experiment_meta.py` |
| T-980 | Experiments in the sidebar, with an empty state worth reading | 2.5 | no | `task_980` | `apps/frontend/src/routes/project/experiments.routes.tsx` |
| T-981 | One endpoint that says what this server speaks | 2.0 | no | `task_981` | `apps/backend/app/routers/version.py` |
| T-982 | Cursors and one error shape on the public API | 3.0 | no | `task_982` | `apps/backend/app/services/page.py` |
| T-983 | The experiments wire endpoints, on area 1's router | 3.0 | yes | `task_983` | `apps/backend/app/services/mlflow_shapes.py` |
| T-984 | The single-verb aliases and the artifact listing on the wire | 2.0 | yes | `task_984` | `apps/backend/tests/test_wire_single_verbs.py` |
| T-985 | Prove a third-party client can log here | 2.0 | no | `task_985` | `apps/backend/tests/test_wire_client_smoke.py` |
| T-986 | `labeldesk doctor` | 2.5 | yes | `task_986` | `packages/sdk/labeldesk/doctor.py` |
| T-987 | A JavaScript client from the same OpenAPI file | 2.0 | yes | `task_987` | `packages/sdk-js/package.json` |

### Wave M file ownership

Generated from the cards' Files sections at assembly time; ids ascending.

| Shared file | Cards that touch it |
| --- | --- |
| `apps/backend/app/services/flags.py` | T-901, T-914, T-918, T-919, T-920, T-921, T-922, T-923, T-924, T-925, T-926, T-927, T-928, T-929, T-930, T-931, T-933, T-934, T-936, T-938, T-941, T-942, T-946, T-954, T-968, T-969, T-970, T-971, T-972, T-973, T-974, T-975, T-976, T-977, T-978, T-979, T-980, T-981, T-982, T-983, T-984, T-985, T-986, T-987 |
| `apps/backend/app/routers/__init__.py` | T-914, T-933, T-937, T-939, T-941, T-942, T-946, T-948, T-951, T-952, T-954, T-955, T-958, T-960, T-962, T-964, T-978, T-981 |
| `apps/backend/app/models/__init__.py` | T-914, T-941, T-946, T-948, T-951, T-952, T-954, T-956, T-959, T-960, T-961, T-963, T-964, T-965, T-972, T-978 |
| `apps/backend/app/schema/training.py` | T-906, T-918, T-920, T-922, T-924, T-927, T-929, T-935, T-940, T-941, T-971 |
| `apps/backend/app/schema/dataset.py` | T-968, T-974 |
| `apps/backend/app/schema/__init__.py` | T-974 |
| `apps/frontend/src/lib/api/models.ts` | T-906, T-908, T-913, T-918, T-919, T-921, T-922, T-923, T-924, T-925, T-926, T-927, T-928, T-929, T-933, T-935, T-937, T-938, T-939, T-941, T-942, T-947, T-949, T-953, T-959, T-968, T-969, T-970, T-971, T-972, T-978, T-979, T-983 |
| `apps/frontend/src/lib/types.ts` | T-901, T-905, T-906, T-913, T-918, T-921, T-922, T-924, T-925, T-926, T-927, T-928, T-929, T-931, T-932, T-933, T-935, T-936, T-947, T-949, T-953 |
| `apps/frontend/src/lib/nav/project/models.ts` | T-946, T-955, T-980 |
| `apps/frontend/src/features/project/Models.tsx` | T-901, T-905, T-906, T-908, T-909, T-912, T-913, T-919, T-921, T-923, T-924, T-925, T-926, T-927, T-928, T-929, T-932, T-933, T-935, T-936, T-938, T-942, T-971 |
| `apps/backend/openapi.json` | T-901, T-905, T-906, T-907, T-911, T-913, T-914, T-915, T-918, T-919, T-920, T-921, T-922, T-924, T-925, T-926, T-927, T-928, T-929, T-932, T-933, T-934, T-935, T-936, T-937, T-938, T-939, T-940, T-941, T-942, T-946, T-947, T-948, T-949, T-951, T-952, T-953, T-954, T-955, T-956, T-958, T-959, T-960, T-961, T-962, T-963, T-964, T-965, T-968, T-969, T-970, T-971, T-972, T-973, T-974, T-975, T-976, T-977, T-978, T-979, T-981, T-982, T-983, T-986 |
| `apps/frontend/src/lib/api-types.gen.ts` | T-901, T-905, T-906, T-907, T-911, T-913, T-914, T-915, T-918, T-919, T-920, T-921, T-922, T-924, T-925, T-926, T-927, T-928, T-929, T-932, T-933, T-934, T-935, T-936, T-937, T-938, T-939, T-940, T-941, T-942, T-946, T-947, T-948, T-949, T-951, T-952, T-953, T-954, T-955, T-956, T-958, T-959, T-960, T-961, T-962, T-963, T-964, T-965, T-968, T-969, T-970, T-971, T-972, T-973, T-974, T-975, T-976, T-977, T-978, T-979, T-981, T-982, T-983, T-986 |

No two cards claim the same exclusive file (checked mechanically). A test file that two cards touch is
listed under Shared by the card that does not own the module.

### Wave M completeness

- MLflow rows: **92** — 5 HAVE, 48 PARTIAL, 39 MISSING (one, `ML2-T2.15`, by design).
- Gap rows with a card or a cited existing card: **87 / 87**.
- Cards: **82**, ids `T-900`–`T-987`, unique, contiguous inside each lane, mean 2.58 h, max 3 h.
- R7 `yes` on **33** cards (the wire API, per-model permission, registry webhooks, artifact download,
  trace ingest and every route that reaches customer run data).
- Docs pages covered: each area file lists every page read, including the redirects the site's `ml/`
  re-cut introduced.
- Integrate-vs-build: **81 Build · 4 Wire · 2 Integrate · 3 Integrate + build · 2 none**; licensing and
  trademark rules in `MLFLOW-PARITY.md` §1, and no card uses the MLflow name or logo as UI copy.

---

## 12. Wave I — Inference Hub (appended 2026-11-17)

Owner directive: a LabelDesk "Inference Hub" with four surfaces — engine installs, a model catalogue,
a VRAM/throughput calculator, and a segmentation catalogue wired to auto-label. Plan:
[`docs/research/inference-hub/PLAN.md`](../../inference-hub/PLAN.md); decision:
[`docs/adr/0005-inference-hub.md`](../../../adr/0005-inference-hub.md).

**23 cards · 62.5 agent-hours · ids `T-1000`–`T-1022`.** Every card is 1–3 hours, names its exclusive
files, and specifies the tests that must fail first. Wave I carries no PARITY or BEYOND row: it is a
new surface, so the `Parity rows` field reads `— (owner request 2026-11-17)` and the closest BEYOND
rows are cited in the plan, not claimed.

**The three locks.** `task_inference` (workspace flag, off by default) gates routes and the rail entry;
`LD_INFERENCE_WORKSPACE` bounds the hub to one workspace on a multi-tenant deployment;
`LD_ALLOW_ENGINE_INSTALL=1` is required on a worker before any install job may execute. All three are
tested, and the flag-off state is in every card's acceptance list.

**Hard rules for this wave.**
1. **Nothing executes in the API process.** `engine_apply` and `model_pull` live in
   `REMOTE_JOB_KINDS` and the `labeldesk-worker` handler map; they are never added to
   `LOCAL_JOB_KINDS`, and a test proves the embedded worker leaves them queued.
2. **No user string becomes a command, a path or a URL.** The client sends catalogue ids and enums; the
   server builds `argv`; the worker re-validates the plan and runs `shell=False` with an allowlist.
3. **No real download in CI.** Fake `uv`/`python`/`docker` and a local hub fixture; a socket guard
   fails the suite on `huggingface.co`, `pypi.org` or a registry.
4. **Never Ollama.** No card installs, downloads, invokes or documents Ollama, in this wave or later.
5. **No new design system.** Glass from `components/glass.tsx` on chrome only; dense tables, results and
   logs stay solid; no new token, hex, font size or icon library.

### I1 Shell, estimate, host truth

**6 cards · 16.0 hours.**

| Task | Title | Hours | Role | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- | --- |
| T-1000 | Inference Hub shell: flag, route, rail entry, admin gate | 2.0 | R4+R3 | yes | `task_inference` | `apps/frontend/src/features/inference/InferenceHub.tsx` |
| T-1001 | Host inventory: the worker reports its own hardware | 3.0 | R3 | yes | `task_inference` | `apps/backend/app/services/host_inventory.py` |
| T-1002 | Engine and GPU catalogue: one source of pins and presets | 3.0 | R3 | yes | `task_inference` | `apps/backend/app/services/inference_catalog.py` |
| T-1003 | Engine compatibility: say blocked before the button exists | 2.0 | R3 | no | `task_inference` | `apps/backend/app/services/inference_compat.py` |
| T-1004 | VRAM and throughput estimator: one module, one answer | 3.0 | R3 | no | `task_inference` | `apps/backend/app/services/inference_estimate.py` |
| T-1005 | Calculator screen: inputs, per-GPU result, visible assumptions | 3.0 | R4 | no | `task_inference` | `apps/frontend/src/features/inference/CalculatorTab.tsx` |

### I2 Engines: plan, install, follow, uninstall

**4 cards · 12.0 hours.**

| Task | Title | Hours | Role | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- | --- |
| T-1006 | Install plan and enqueue: a dry run, then one job | 3.0 | R3 | yes | `task_inference` | `apps/backend/app/services/inference_plan.py` |
| T-1007 | Engines tab: select, compare, review the plan, confirm | 3.0 | R4 | yes | `task_inference` | `apps/frontend/src/features/inference/EnginesTab.tsx` |
| T-1008 | Worker engine job: run the plan, keep the log, cancel cleanly | 3.0 | R3 | yes | `task_inference` | `apps/worker/labeldesk_worker/engines.py` |
| T-1009 | Job card: progress, log sheet, cancel and uninstall | 3.0 | R4+R3 | no | `task_inference` | `apps/frontend/src/features/inference/InstallProgress.tsx` |

### I3 Models: catalogue, download, disk

**4 cards · 10.5 hours.**

| Task | Title | Hours | Role | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- | --- |
| T-1010 | Model catalogue: pins, quant variants, licence and gate | 3.0 | R3 | yes | `task_inference` | `apps/backend/app/services/inference_models.py` |
| T-1011 | Worker model download: resume, verify, never fill the disk | 3.0 | R3 | yes | `task_inference` | `apps/worker/labeldesk_worker/model_pull.py` |
| T-1012 | Models tab: filter, compare, download with a disk check | 3.0 | R4 | yes | `task_inference` | `apps/frontend/src/features/inference/ModelsTab.tsx` |
| T-1013 | Host assets: what is installed, how much disk, reclaim it | 2.5 | R4 | no | `task_inference` | `apps/frontend/src/features/inference/AssetsPanel.tsx` |

### I4 Segmentation and auto-label

**3 cards · 7.5 hours.**

| Task | Title | Hours | Role | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- | --- |
| T-1014 | Segmentation catalogue: models, VRAM, licence, provisioned state | 2.5 | R3 | no | `task_inference` | `apps/backend/app/services/inference_segmentation.py` |
| T-1015 | Segmentation tab: cards, provisioned state, use for auto-label | 3.0 | R4 | no | `task_inference` | `apps/frontend/src/features/inference/SegmentationTab.tsx` |
| T-1016 | Auto-label accepts a preselected model from a link | 2.0 | R4 | no | `task_inference` | `apps/frontend/tests/autolabel-prefill.test.mjs` |

### I5 Hardening, QA and release

**6 cards · 16.5 hours.**

| Task | Title | Hours | Role | R7 | Flag | First exclusive file |
| --- | --- | --- | --- | --- | --- | --- |
| T-1017 | Access, audit and limits: three locks on one action | 2.5 | R3 | yes | `task_inference` | `apps/backend/tests/test_inference_access.py` |
| T-1018 | Adversarial suite: prove the boundary, not just the happy path | 3.0 | R3 | yes | `task_inference` | `apps/backend/tests/test_inference_isolation.py` |
| T-1019 | Mocked installer harness: CI never downloads a weight | 3.0 | R3+R8 | yes | `task_inference` | `apps/worker/tests/conftest.py` |
| T-1020 | E2E smoke: the four surfaces on a mocked worker | 2.5 | R8 | no | `task_inference` | `apps/frontend/e2e/inference-hub.spec.ts` |
| T-1021 | UI QA: light, dark and 375 px across the four surfaces | 2.0 | R9 | no | `task_inference` | `docs/research/inference-hub/ui-qa.md` |
| T-1022 | Ship it: operator runbook, user docs, rollout and rollback | 2.5 | R11+R3 | yes | `task_inference` | `docs/INFERENCE-HUB.md` |

### Order and dependencies

Merge order is the id order with these hard predecessors:

| Card | Needs before it can be reviewed |
| --- | --- |
| T-1001 | T-1000 (flag) |
| T-1003 | T-1001 (inventory), T-1002 (catalogue) |
| T-1004 | T-1002 (GPU presets) |
| T-1005 | T-1000, T-1002, T-1004 |
| T-1006 | T-1002, T-1003 |
| T-1007 | T-1006 (plan/install routes really exist) |
| T-1008 | T-1006 (payload/enqueue), T-1001 (inventory) |
| T-1009 | T-1008 (job), T-1007 (tab) |
| T-1010 | T-1002 (engine ids), T-1004 (fit helper) |
| T-1011 | T-1010, T-1008 |
| T-1012 | T-1010, T-1011, T-1009, T-1005 |
| T-1013 | T-1011, T-1012 |
| T-1014 | T-1001 |
| T-1015 | T-1014, T-1016 |
| T-1016 | none (inert until T-1015 links to it) |
| T-1017 | T-1006, T-1008, T-1011 |
| T-1018 | T-1006, T-1008, T-1011, T-1017 |
| T-1019 | T-1008, T-1011 |
| T-1020 | T-1007, T-1009, T-1012, T-1013, T-1015, T-1016 |
| T-1021 | T-1007, T-1009, T-1012, T-1013, T-1015 |
| T-1022 | T-1017–T-1021 |

Phase gates: P0 and P1 have no side effects and ship first; P2 ships only with
`LD_ALLOW_ENGINE_INSTALL=1` on a lab host; P3 after one clean install and one clean download; P4 after
P1; P5 closes the wave. Each phase merges with the flag off and is demoable before the next starts.

### Wave I file ownership

Generated from the cards' Files sections; ids ascending. Only shared files are listed; every other
path is exclusive to one card and checked mechanically.

| Shared file | Cards that touch it, in merge order |
| --- | --- |
| `apps/backend/app/services/flags.py` | T-1000 |
| `apps/backend/app/routers/__init__.py` | T-1001 |
| `apps/backend/app/routers/inference.py` | T-1001, T-1002, T-1003, T-1004, T-1006, T-1009, T-1010, T-1011, T-1014, T-1017 |
| `apps/backend/app/routers/remote.py` | T-1001, T-1008 |
| `apps/backend/app/models/insights.py` | T-1001 |
| `apps/backend/app/schema/insights.py` + `schema/__init__.py` | T-1001 |
| `apps/backend/app/config.py` | T-1008 |
| `apps/backend/app/services/inference_access.py` | T-1001, T-1017 |
| `apps/backend/app/services/inference_jobs.py` | T-1006, T-1011, T-1017 |
| `apps/backend/tests/test_flags.py` | T-1000 |
| `apps/worker/labeldesk_worker/cli.py` | T-1001, T-1008, T-1011 |
| `apps/worker/pyproject.toml` | T-1011 |
| `apps/frontend/src/routes/workspace.routes.tsx` | T-1000 |
| `apps/frontend/src/lib/nav/types.ts`, `visibility.ts`, `workspace/core.ts`, `registry.ts`, `components/shell/AppSidebar.tsx` | T-1000 |
| `apps/frontend/src/features/inference/InferenceHub.tsx` | T-1000, T-1005, T-1007, T-1012, T-1015 |
| `apps/frontend/src/lib/api/inference.ts` | T-1001, T-1002, T-1006, T-1009, T-1010, T-1012, T-1013, T-1014 |
| `apps/frontend/src/lib/types.ts` | T-1001, T-1002, T-1003, T-1004, T-1006, T-1009, T-1010, T-1012, T-1014 |
| `apps/frontend/tests/inference-hub.test.mjs` | T-1000, T-1005, T-1007, T-1012, T-1015 |
| `apps/backend/openapi.json` + `apps/frontend/src/lib/api-types.gen.ts` | every card with a route; generated together and never hand-merged |

Hot-file rules from §4c apply: on a rebase that touches the router or the generated pair, take feat's
copy and regenerate; registries keep both sides' entries.

### Wave I completeness

- Cards: **23**, ids `T-1000`–`T-1022`, unique and contiguous, mean **2.72 h**, max **3 h**.
- R7 `yes`: **13** cards (T-1000, T-1001, T-1002, T-1006, T-1007, T-1008, T-1010, T-1011, T-1012,
  T-1017, T-1018, T-1019, T-1022).
- Every card has a User story, UX flow, Backend changes, Frontend changes, Files, Tests to write
  first, and Acceptance criteria with the flag-off and cross-workspace cases (or an explicit
  "no frontend surface" / "no new route" line where the card genuinely has none).
- No card adds a dependency outside the worker's optional `inference` extra; the API gains none.
- No card names a price, a vendor reseller, a certification or a benchmark it has not measured.
- **Ollama appears nowhere except the exclusion statements** in the plan and the ADR.
