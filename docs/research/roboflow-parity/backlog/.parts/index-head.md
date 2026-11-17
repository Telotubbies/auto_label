# LabelDesk v2 — Roboflow-parity build backlog

Planning-lane output, 2026-11-17. Base branch `feat/labeldesk-v2` at `fe8ef1a`. Read-only lane: no
application code, tests or git state were touched; this folder is the only write.

**What this is.** 381 task cards that close every one of the 334 rows in
[`PARITY.md`](../PARITY.md): 262 gap rows (163 PARTIAL + 99 MISSING) plus the 72 HAVE rows, which are
pinned by seven regression-guard cards. Every card is one agent for 1–3 hours, names the exact files it
creates or edits, and specifies the tests that must fail first.

**Sources, in order of authority**
1. [`PARITY.md`](../PARITY.md) — the 334 rows, status, priority, size.
2. `01-workspace-projects.md` … `07-workspace-admin.md` — per-feature flow, screens, empty/loading/error
   states, edge cases.
3. [`design/labeldesk-v3/REDESIGN.md`](../../../../design/labeldesk-v3/REDESIGN.md) — wave E's names, IA,
   routes, tokens and state rules.
4. [`_BRIEF.md`](_BRIEF.md) — the contract every card was written against (template, id bands, wave map,
   cross-area ownership, shared-file rules).
5. The code itself; every path in a card was verified against the repo.

**Owner directive this backlog implements (2026-11-17):** all 334 features, down to each recorded click,
state and edge case, in LabelDesk names, copy and icons only — never Roboflow text, logos or assets.

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
| E | LabelDesk-native redesign (17 frame + 12 finish) | 29 | 76.5 | 4 |
| **Total** | | **381** | **1,076.5** | **334/334 mapped** |

The per-wave row counts exceed 334 because a row can legitimately split across waves (for example
`3-F3.55` has a wave-A save-conflict half and a wave-B state half) and because HAVE rows appear in both
G and a later wave when their own gap cell names real work. The completeness check in §9 asserts the
exact 334-id set, once each, with no unknown id.

**Sizing honesty.** 1,076.5 agent-hours is implementation only. House practice adds review, fix rounds,
rebases and merge gates; budget **1,250–1,350 agent-hours** end to end. The largest concentration is
wave B (419 h), which is also where the product lives, so wave B is the schedule risk, not wave D.

---

## 3. Rules that bind every card

- **Branding.** LabelDesk names, copy and icons only. A competitor name may appear once as a source
  label (`(RF: *…*)`), never as text a user reads. New copy is written in LabelDesk's voice; Thai strings
  are real Thai, not transliterations.
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
  SIEM export, or untrusted uploads/URLs (safefetch). The card says so; 106 cards carry `yes`.

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

---

## 5. What was deliberately not planned

- **A second UI.** `web/` is frozen; all frontend cards target `apps/frontend`.
- **A second annotation engine.** Every editor card extends the existing Konva editor and its JSON
  annotation storage; no card introduces a parallel document model.
- **A second inference server.** Self-hosting links to and documents `apps/inference`; no card rewrites it.
- **Vendor SDKs.** No card adds one. Where a vendor is the only real answer, the card ships an interface
  and a mock, and §4 records the decision.
- **Re-implementing HAVE flows.** The guard cards assert them; they do not rewrite them.
- **A rewrite of the login screen** (see §4.2 #13).

---

## 6. Execution order

Waves are ordered by user value, but three structural facts decide the real schedule.

```
Phase 0  G  T-001…T-007        regression guards, baseline green (19 h)
Phase 1  E  E-frame (17)       tokens, routes /p/, rails, stage frame, top bar, palette  (45.5 h)
Phase 2  A  47 cards           trial blockers                        (132.5 h)
Phase 3  B  149 cards          editor / train / eval / workflow core (419 h)
Phase 4  C  97 cards           data and people                       (278.5 h)
Phase 5  D  52 cards           commercial and enterprise (owner-gated) (151 h)
Phase 6  E  E-finish (12)      polish, mobile, a11y proof, copy deck  (31 h)
```

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
(`T-352`–`T-359`, `T-439`–`T-449`).

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
