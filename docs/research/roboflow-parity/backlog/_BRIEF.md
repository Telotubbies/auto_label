# Backlog authoring contract (read fully before writing any card)

Lane: **planning only**. You may write files under `docs/research/roboflow-parity/backlog/` only.
Never edit application code, tests, configs, `board.md`, or git state. Never run a merge, rebase, push,
delete, or kill a process. You may read and grep anything in the repo.

Repo: `E:/02_Projects/auto_label`, branch `feat/labeldesk-v2` at `fe8ef1a`.
Sources of truth, in order:

1. `docs/research/roboflow-parity/PARITY.md` — the 334 rows, statuses, evidence, sizes.
2. The area file for your area (`01-…` … `07-…`) — the per-feature flow, screens, empty/loading/error
   states, gates and sources. Every UX detail in your cards comes from here, rewritten in LabelDesk words.
3. `design/labeldesk-v3/REDESIGN.md` — the v3 names, IA, routes, tokens and state rules. Use its
   vocabulary (stage names, route shapes, "Empty vs no-match", job tray, permission = dimmed + lock).
4. The code itself. Cite only paths you verified with a read/glob/grep. A file you plan to create is
   marked `(new)`.

Owner directive (2026-11-17): implement **every** MISSING and **every** PARTIAL row down to the last
detail — each click, screen, empty/loading/error state and edge case the area file records. HAVE rows
are protected by the seven guard tasks, not re-planned.

Branding rule: LabelDesk names, copy and icons only. Never copy Roboflow text, feature names as UI
copy, logos, illustrations or screenshots. A Roboflow name may appear once as a source label
(`(RF: *…*)`), never as a label the user reads.

Ponytail rule: the smallest complete change. Extend an existing service/field/component before adding
one. No new dependency for a few lines. No speculative options. Cards must not ask for a refactor that
the gap does not need.

---

## 1. What you deliver

1. **One card per task**: `backlog/T-<nnn>.md`, in your allocated id band, numbered in dependency order.
2. **One part index**: `backlog/.parts/area-<n>.md` (or `wave-e.md`, `guards.md`) in the exact shape of §6.
   The PM merges these into `INDEX.md`; if it is missing or malformed the merge stalls.

A card is **one agent, 1–3 hours**. If a row needs more, split it along a seam a reviewer could accept
or reject separately (schema → service → route → screen → state). Never write a card that hides 6 hours.

Sizing guide: `S` row ≈ 1–2 cards, `M` row ≈ 2–4 cards, `L` row ≈ 4–10 cards. Many S rows bundle two
closely-coupled details into one card when the same file, same test and same reviewer cover both.

Every row you own must appear in the mapping table with at least one task id. A row split across two
cards lists both ids. A row that is genuinely HAVE-only lists `—` and one line saying which guard task
asserts it.

---

## 2. Card template (copy exactly, keep the headings, in this order)

```markdown
# T-<nnn> — <imperative title, ≤ 60 chars>

| Field | Value |
| --- | --- |
| Wave | A / B / C / D / E |
| Parity rows | `3-F3.2`, `3-F3.3` (PARTIAL) |
| Size | S / M / L (source size) → <n> agent-hours |
| Role | R3 backend / R4 frontend / R4+R3 full-stack / R5 port |
| Skills | ponytail, <role skills from pm rules §5> |
| R7 security review | yes / no — <why in ≤ 8 words> |
| Depends on | T-0xx (why) / none |
| Feature flag | `task_<id>` (new line in `services/flags.py`) / none |

## User story
As a <role>, I want <outcome> so that <why>. (One or two sentences, LabelDesk words.)

## UX flow (LabelDesk words)
1. **<Screen name>** — <what the user does>. [empty: …] [loading: …] [error: …]
2. …
Every click, every screen, the states the flow passes through. Name the route
(`/:ws/p/:project/annotate`). Write `[empty]`, `[loading]`, `[error: …]` inline where the user meets them.
Copy that ships in the UI goes in quotes and is new text, never a competitor's wording.

## Backend changes
- Models/schema: <table/column, nullability, default, backfill>. No Alembic in this repo: a new column
  is an `ADD COLUMN` block in `app/schema/<domain>.py` registered in `schema.apply`, a new table is a
  model module registered in `models/__init__.py`.
- Routers: <endpoint, method, path, request/response fields, status codes>.
- Services/jobs: <function signature, job kind, worker path>.
- Permissions + workspace isolation: <which permission, which scope check, what a wrong workspace sees (404)>.
- Secrets/safefetch: <`services/secretbox.py` / `services/safefetch.py` use, or "none">
- OpenAPI: regenerate (`python tools/export_openapi.py`, `npm run gen:api-types`) when a route or
  schema changes — yes/no.

## Frontend changes
- Route: <path, file, redirect from the legacy path>.
- Nav entry: <file in `src/lib/nav/…`, label, visibility rule> or none.
- Components: <file (new), responsibility>.
- API client: <`src/lib/api/<domain>.ts` function signature>.
- Feature flag: <key + where it is read in the UI> or none.

## Files
Exclusive (only this task touches them):
- `exact/path.py` (new) — created
- `exact/path.tsx` — edited
Shared (append-one-line registries; see §5):
- `apps/backend/app/routers/__init__.py` — one router entry
- `apps/backend/openapi.json` — generated

## Tests to write first
pytest — `apps/backend/tests/test_<name>.py`:
- `test_<behaviour>` — <setup → call → asserted result, including the 403/404/422 and the flag-off case>.
node — `apps/frontend/tests/<name>.test.mjs`:
- `test_<behaviour>` — <pure function or rendered-state assertion>, or `none: no frontend surface`.

## Acceptance criteria
- [ ] <observable behaviour, one line each, ≥ 3 and ≤ 7>
- [ ] Empty, loading and error states above all render.
- [ ] Workspace A cannot see or change workspace B's data (404, not 403, for cross-workspace ids).
- [ ] Flag off ⇒ surface absent and the old behaviour unchanged.

## Notes for the implementer
<The one decision the card cannot leave open: exact value, ordering, threshold, copy, or the data
shape. 0–3 lines. Nothing that restates the sections above.>
```

## 3. Wave rules

Canonical assignments from `PARITY.md` §Ranked build plan. **Do not re-litigate these**; rows listed
here belong to that wave:

- **A (trial blockers):** 3-F3.2, 3-F3.3, 3-F3.43, 3-F3.52, 3-F3.46, 3-F3.8, 3-F3.10, 3-F3.16,
  3-F3.18, 1-F4.3, 2-F2.27, 4-F4.13, 4-F4.18, 4-F4.26, 3-F3.27, 3-F3.29, 3-F3.32, 6-F6.1, 6-F6.5,
  6-F6.8, 1-F5.1, 1-F5.2, 7-F7.53, 1-F3.2.
- **B (editor / train / workflow core):** 3-F3.21, 3-F3.54, 5-F5.7, 5-F5.8, 5-F5.40, 5-F5.41,
  5-F5.42, 5-F5.21, 5-F5.22, 5-F5.28, 5-F5.29, 5-F5.31, 4-F4.15, 4-F4.30, 4-F4.33, 4-F4.34, 4-F4.35,
  6-F6.10, 6-F6.23, 6-F6.33, 6-F6.21, 6-F6.24, 6-F6.25, 6-F6.29, 3-F3.45, 3-F3.49, 3-F3.11.
- **C (data and people):** 1-F4.2, 2-F2.25, 2-F2.18, 2-F2.32, 2-F2.35, 2-F2.36, 1-F5.6, 2-F2.45,
  7-F7.43, 1-F5.4, 7-F7.6, 7-F7.8, 7-F7.9, 7-F7.10, 1-F1.5, 7-F7.27, 7-F7.28, 7-F7.38, 7-F7.39,
  7-F7.60, 7-F7.46, 7-F7.47, 7-F7.48, 7-F7.49, 6-F6.18.
- **D (commercial / enterprise):** 7-F7.12, 7-F7.20, 7-F7.21, 7-F7.22, 7-F7.23, 7-F7.24, 7-F7.35,
  7-F7.40, 7-F7.44, 7-F7.45, 7-F7.59, 6-F6.3, 6-F6.4, 6-F6.44, 6-F6.19.
- **E (LabelDesk-native redesign):** 1-F1.4, 3-F3.1 and every visual/copy/icon/mobile/state task.

For a row not in that list, assign the first wave that fits, top down:

- A if a buyer meets it in the first hour and the change is demo-visible and small.
- B if it is editor, training, evaluation or workflow mechanics.
- C if it is dataset, metadata, people, keys, audit or connectors.
- D if it is money, enterprise identity, data protection, fleet/dedicated compute.
- E if the outcome is visual, copy, icons, motion, mobile or a cross-screen state system.

Wave D is **provider-agnostic by order of the owner**: no payment provider, plan price or self-host
licence has been chosen. A wave-D card plans a billing interface plus a mock/test provider, no real
charge, flagged off by default. The three owner decisions are listed in `INDEX.md`, never invented in a
card.

## 4. Cross-area ownership (avoid duplicating work)

These rows are one piece of work. The **owner area** writes the card; the other area maps its row to
that card id and adds no card of its own.

| Work | Owner area | Rows covered by the owner's cards |
| --- | --- | --- |
| Query language (chips, negation, `class:x>=4`, date/size) | 2 | 2-F2.27, 1-F4.3 |
| Workspace asset library | 1 | 1-F4.2, 2-F2.25 |
| Public project page | 1 | 1-F5.2, 7-F7.54 |
| Fork/clone with enumerated errors | 1 | 1-F5.3, 2-F2.20, 7-F7.55 |
| Trash (who/when/days-left, versions+runs+workflows) | 7 | 7-F7.43, 1-F5.6, 2-F2.45 |
| Connector credential store + datasource + mirror + sync guards | 2 | 2-F2.15, 2-F2.16, 2-F2.17, 2-F2.19, 7-F7.46, 7-F7.47, 7-F7.48 |
| Shared class vocabulary / annotation groups | 1 | 1-F2.4, 3-F3.40 |
| Per-image typed metadata | 2 | 2-F2.18, 2-F2.32 |
| Key lifecycle (rename/protect/disable/roll, per-key usage) | 7 | 7-F7.25, 7-F7.26, 7-F7.27, 7-F7.28, 7-F7.29, 1-F1.5, 6-F6.13 |
| Publish licence dialog + PII warning | 1 | 1-F5.1, 7-F7.53 |
| Workspace policy switches (public projects, vendor use) | 7 | 7-F7.60 (+ one line reused by 1-F5.1's kill switch) |
| Split rebalance strategies | 2 | 2-F2.41, 4-F4.12 |
| Health report charts (heat map, histogram, dimensions, nulls) | 2 | 2-F2.37, 4-F4.39, 4-F4.42, 4-F4.43 |
| Train cost in credits (estimator) | 5 | 5-F5.11, 7-F7.18 |
| Model registry: starred/public model, reuse as checkpoint | 5 | 5-F5.3, 5-F5.36, 7-F7.56 |
| Export formats + export dialog + bucket delivery | 4 | 4-F4.34, 4-F4.35, 4-F4.38 |
| Deploy hub, runtimes, self-host, install paths | 6 | 6-F6.1, 6-F6.5, 6-F6.8, 6-F6.45 |
| Active-learning caps and review cadence | 6 | 6-F6.19, 6-F6.32 |
| Audit filters/diff/coverage | 7 | 7-F7.38, 7-F7.39 |
| Webhook + notification sinks | 7 | 7-F7.49, 7-F7.51 |
| Augmentation catalogue + guidance + multiplier estimate | 4 | 4-F4.14, 4-F4.15, 4-F4.30, 4-F4.33 |
| Version wizard preview, resize modes, tag filter | 4 | 4-F4.13, 4-F4.18, 4-F4.26, 4-F4.27 |
| Review speed / bulk review / reject reason | 3 | 3-F3.46, 3-F3.55 (read-only conflict), 3-F3.47 |
| Editor shell + tool rail (v3) | E | 3-F3.1 |
| Tour replay + first-run hints | E | 1-F1.4 |

If you believe another row should also be yours, take it **and** say so in your part index
(`Extra ownership: <row> — <reason>`).

## 5. Shared files (hot registries) — one line per task, merge order matters

Never restructure a shared file. Each task adds the smallest possible line/section, and the card names
it under **Shared**. The hot list:

- `apps/backend/app/routers/__init__.py` — import + `ROUTERS` tuple (route order is the OpenAPI order).
- `apps/backend/app/models/__init__.py` — module import + name re-export + `DOMAIN_MODULES`.
- `apps/backend/app/services/flags.py` — one `FLAGS` line.
- `apps/backend/app/schema/{columns,dataset,identity,streams,training}.py` — append one block at the end;
  `schema.apply` order is the shipped order.
- `apps/backend/app/bootstrap.py` — only for a new index/backfill next to the existing ones.
- `apps/backend/app/main.py` — only if middleware or a startup hook changes (rare).
- `apps/backend/openapi.json` + `apps/frontend/src/lib/api-types.gen.ts` — generated together; never
  hand-edited; regenerated last on the branch.
- `apps/frontend/src/lib/nav/registry.ts`, `lib/nav/project/*.ts`, `lib/nav/workspace/*.ts`,
  `lib/nav/visibility.ts` — nav entries.
- `apps/frontend/src/routes/*.tsx`, `routes/project/*.tsx`, `routes/lazy.ts` — route registration.
- `apps/frontend/src/components/ui.tsx`, `src/index.css`, `src/lib/theme.ts` — shared components/tokens.
- `apps/frontend/src/lib/api.ts`, `src/lib/api/*.ts` — client registry.
- `apps/frontend/src/features/project/ProjectLayout.tsx`, `components/shell/*` — shell.
- `apps/frontend/tests/nav.test.mjs`, `api-types.test.mjs` — registry assertions.

A card that edits a hot file lists it under Shared with the exact line it adds. Two cards may both
append to a registry; the PM serialises them in `INDEX.md`.

## 6. Part index format (exact)

```markdown
# Part <n> — Area <n> <name>

Gap rows: <g> (<p> PARTIAL, <m> MISSING) · Cards: <c> · Hours: <h>

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 1-F1.1 | PARTIAL | T-010 | A | S | 3 |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| apps/backend/app/routers/__init__.py | T-010, T-014 |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-010 | … | A | 3 | R3 | yes | `apps/backend/app/routers/x.py` |

## Judgment calls
- <row> → <wave/card> — <one-line reason>. (Only where the canonical map did not decide.)
```

Hard rules for the part index: every row of your area appears exactly once in Mapping; hours sum to the
header; task ids ascending with no gaps inside your band; no card id outside your band.

## 6b. Amendments (owners' arbiter, 2026-11-17, after lanes 1–4 landed)

- **Card id bands in force:** guards `T-001–T-007`; area 1 `T-010–T-059`; area 2 `T-060–T-119`;
  area 3 `T-120–T-189`; area 4 `T-190–T-249`; area 5 `T-250–T-309`; area 6 `T-310–T-379`;
  area 7 `T-380–T-469`; wave E `T-470–T-519`.
- **Guards are per area, not per theme:** `T-001` = area 1, `T-002` = area 2, … `T-007` = area 7.
  A HAVE row maps to its own area's guard. Do not invent a theme-based guard set; the guard card
  asserts that area's HAVE rows still hold and that the area's existing tests still pass.
- A row owned by another area is cited as `<task ids> (area <n>)`; never write a card in a foreign band.
- `2-F2.37` is HAVE by status but its recorded gap (heat map, histogram) is real and is planned by
  area 2 — a HAVE row may carry cards when its own UX-gap cell names work. Same rule for any row
  whose status cell and gap cell disagree; say so in Judgment calls.

## 7. Self-check before you finish

- [ ] Every PARTIAL and MISSING row of your area appears in Mapping with ≥ 1 card.
- [ ] Every card has all template sections, exact verified paths, pytest **and** node test lines, and
      the flag-off + cross-workspace acceptance criteria.
- [ ] No card exceeds 3 agent-hours; no row's work disappears into a vague card.
- [ ] No two cards in your part touch the same **exclusive** file; anything shared is under Shared.
- [ ] Every wave-D card is provider-agnostic, mock-only, flag-off, and charges nothing.
- [ ] Copy in the cards is new LabelDesk text; no competitor string is presented as UI copy.
- [ ] The part index matches the cards (ids, hours, files).
