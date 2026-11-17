# LabelDesk organisation

Owner request 2026-11-17: run LabelDesk development like a large company, with every role and full
usability testing. The machine runs **at most five opencode lanes at once, plus one PM**. The org is
therefore **roles run as lanes in a cadence**, not headcount: every role below is a card, a skill set and
a definition of done; several roles share one lane over time.

This document extends `docs/OPENCODE_TEAM_FLOW.md` and `docs/OPENCODE_PM_RULES.md`. It changes no
existing rule: R0 merges, the serial gate holds, options-first and TDD hold, R6/R7/R9 still review. The
PM is Claude in the R0 seat and is the **only** merger.

---

## 1. Departments and roles

`Lane` is the load a card puts on the machine: **heavy** = build, review of a large diff, a browser run;
**light** = a read-only pass that can share a slot. One lane runs one card at a time.

| R | Role | Department | Lane | Skills (installed ids) | Definition of done |
| --- | --- | --- | --- | --- | --- |
| R0 | PM / merge captain | Product | light, always on | `ponytail`, `requesting-code-review`, `receiving-code-review`, `dispatching-parallel-agents`, `verification-before-completion` | branch merged one at a time, gate green with numbers, branch and worktree deleted, ledger line |
| R12 | Product analyst | Product | light | `product-lens`, `brainstorming`, `intent-driven-development`, `writing-plans` | card has an outcome, non-goals and testable acceptance; duplicates merged; queue order justified |
| R13 | UX researcher / usability lab | Design · Quality | heavy | `uxui-law`, `webapp-testing`, `e2e-testing`, `agent-self-evaluation` | journey run recorded (steps, time, errors); personas scored; findings carry evidence |
| R14 | UI designer / design system | Design | heavy | `impeccable`, `frontend-design`, `ui-ux-pro-max`, `composition-patterns`, `web-design-guidelines`, `hallmark` | screen obeys the stage frame, glass tokens and type floor; light/dark at 375, 768, 1440; no new token, hex or icon library |
| R15 | Content designer, English and Thai | Design | light | `writing-guidelines`, `humanizer`, `thai-de-ai`, `documentation-writer` | every string is new LabelDesk copy, one word per concept; Thai flagged for a native reviewer |
| R3 | Backend engineer | Engineering | heavy | `test-driven-development`, `systematic-debugging`, `codebase-design`, `error-handling` | RED then GREEN, workspace 404 proved, touched tests pass, ruff 0.17.3 clean, report written |
| R4 | Frontend engineer | Engineering | heavy | `test-driven-development`, `frontend-design`, `react-best-practices`, `composition-patterns`, `webapp-testing` | node tests pass, `npm run build` passes, empty/loading/error states present, screenshots attached |
| R16 | ML engineer | Engineering | heavy | `test-driven-development`, `systematic-debugging`, `eval-harness`, `codebase-design` | adapter and evaluator tests with fakes, metric parity proved, no GPU claim without a run |
| R17 | MCP / integrations engineer | Engineering | heavy | `test-driven-development`, `systematic-debugging`, `error-handling`, `verification-before-completion` | every tool is no more permissive than its route, scopes and limits tested, one audit row per call |
| R18 | Inference hub engineer | Engineering | heavy | `test-driven-development`, `systematic-debugging`, `codebase-design`, `verification-before-completion` | plan and argv revalidated server-side, no network in CI, three locks tested, flag-off state tested |
| R8 | QA engineer | Quality | heavy | `webapp-testing`, `e2e-testing`, `verification-before-completion` | full suites and the feature smoke run on the rebased branch, numbers in the report |
| R19 | Accessibility engineer | Quality | heavy | `web-design-guidelines`, `uxui-law`, `browser-qa`, `impeccable` | axe 0 critical/serious, keyboard-only path proved, contrast pixel-sampled |
| R20 | Performance engineer | Quality | light | `react-best-practices`, `browser-qa`, `verification-before-completion` | budgets measured on a named build and machine, regressions attributed to a commit |
| R10 | Regression fixer | Quality | heavy when red | `systematic-debugging`, `debug-mantra`, `test-driven-development`, `verification-before-completion` | `feat/labeldesk-v2` green again; fix on a `fix/*` branch for R0 |
| R7 | AppSec reviewer and threat modeller | Security | light | `code-review`, `santa-method`, `error-handling` | no Critical or High left; isolation, `secretbox`, `safefetch`, uploads and URLs checked; threat notes updated |
| R21 | Platform/SRE: CI, gate, observability | Platform/SRE | light | `verification-loop`, `setup-pre-commit`, `production-audit`, `git-workflow` | gate reproducible, timings recorded, runbook current, no silent CI red |
| R1 | Release engineer (triage) | Platform/SRE | light | `verification-before-completion`, `git-workflow` | MERGED / SUPERSEDED / UNFINISHED table with git evidence |
| R11 | Docs and ledger keeper | Docs | light | `documentation-writer`, `writing-guidelines`, `living-docs-governance`, `code-tour` | user docs, API docs and runbooks match shipped behaviour; ledger and board current |
| R2 | Tech lead / planner | Engineering | light | `writing-plans`, `codebase-design` | brief splits by file; no two parts share an exclusive file |
| R5 | Port engineer | Engineering | heavy | `codebase-design`, `test-driven-development` | same behaviour and tests on `apps/`, old paths untouched |
| R6 | Code reviewer (never the author) | Quality | light | `requesting-code-review`, `receiving-code-review`, `codebase-design` | verdict APPROVED, or findings with `file:line` and severity; options table checked for over-engineering |
| R9 | UI QA | Quality | light | `impeccable`, `web-design-guidelines`, `uxui-law`, `webapp-testing` | page checked light/dark/375, no console errors, screenshots saved |

**Squads are a view, not a new structure.** Backend, frontend, ML, MCP/integrations and inference-hub
roles own disjoint file families; a wave assigns each family to a build lane. No squad has its own
queue, and no lane edits another family's exclusive file.

**Every role also loads** `ponytail` and `verification-before-completion`; a builder also loads
`test-driven-development`; a reviewer also loads `requesting-code-review` / `receiving-code-review`.

---

## 2. Decision rights (RACI)

`A` = accountable (one), `R` = does the work, `C` = consulted, `I` = informed.

| Decision | A | R | C | I |
| --- | --- | --- | --- | --- |
| Card scope and acceptance | R0 | R12 | R2, R3, R4, R13 | owner |
| Screen design and copy | R14 | R14, R15 | R13, R4, R9 | R0 |
| Merge into `feat/labeldesk-v2` | R0 | R0 | R6, R8 | owner |
| Release of a wave | R0 | R21, R11 | R7, R8, R13, R19, R20 | owner |
| Security sign-off | R7 | R7 | R0, R3, R17, R18 | owner |
| Usability sign-off | R13 | R13, R19, R20 | R14, R15, R8 | R0, owner |
| Push, PR to `main`, deploy | owner | R0 | R21 | — |

A sign-off is **blocking** for its severity class, not for every card: see
`docs/qa/USABILITY-PROGRAM.md` §10.

---

## 3. Cadence

### 3.1 Per card

1. R12 writes or confirms the card's outcome, non-goals and acceptance (the `_BRIEF.md` template).
2. One build lane implements in its own worktree: rebase first, options table at the top of the report
   (2–3 designs, LOC, files, trade-offs; test-only cards skip it), TDD RED then GREEN, touched tests.
3. R6 reviews spec then quality; R7 joins when the card touches auth, RBAC, secrets, uploads, outbound
   URLs, money, OT/PLC or a new execution boundary; R9 joins when the diff changes a screen.
4. R8 runs the feature smoke plus the touched suites on the rebased branch. R0 merges only after.

Findings go back to the same builder with only the findings; max five rounds, R2 re-plans after round 3.

### 3.2 Per merge batch

A batch is one to five reviewed branches. R0 builds `queue/batch-N` on top of feat, runs the **gate**
once, then merges in order; a red batch is bisected one branch at a time.

Gate = serial API suite (about 1,590 tests, 12–15 min measured 2026-11-17), node tests, `npm run build`
(which checks the generated API types), ruff at the CI-pinned version, and the Playwright smoke set
(`npm run e2e`, target under 10 min). Every number is written to the ledger. Post-merge the gate runs
again on feat, as today.

### 3.3 Per wave

A **backlog band** is one wave of `docs/research/roboflow-parity/backlog/INDEX.md` (A, B, C, …). A
**release wave** is a quality cycle Q1–Q4 that closes one or more bands — about 20–40 implementation
cards — and ends with one triage card. At a release wave's close, in this order:

1. R13 runs the usability study: every journey the wave's cards touch, the persona walkthroughs, the
   SUS-style self-score (`docs/qa/USABILITY-PROGRAM.md`).
2. R19 runs axe, keyboard-only and contrast on the wave's screens; R20 runs the performance budgets.
3. R15 runs the English and Thai copy pass and flags Thai for a native reviewer.
4. The wave's triage card (T-1223…T-1226) turns every S1/S2 finding into a fix card and writes the wave's
   release note, `docs/qa/releases/q<N>.md`.
5. R11 records the release note and the ledger line; R0 does not start the next wave while an S1 is open.

### 3.4 Daily

- **Full regression, once a day**: backend serial suite, node tests, web build, e2e smoke. R8 owns the
  run; a red result stops merges until R10 is green. (This is the same gate as §3.2, run on a quiet tree.)
- **Backlog grooming, once a day**: R12 re-reads the next 20 cards, deletes duplicates, confirms
  dependencies still hold against `git log`, and moves stale cards. R0 updates `board.md`.
- **Fifteen-minute stand-up in the ledger**: one line per lane — card, state, blocker, next.

### 3.5 Lanes and interleave

Of the five lanes, **at most four are heavy at once** (the machine limit in `OPENCODE_TEAM_FLOW.md` §3);
S5 and the PM are light. Light roles (R1, R6, R7, R11) can ride an existing slot.

| Slot | Role | Job |
| --- | --- | --- |
| S1 | R3 / R4 / R16 / R17 / R18 | build card A |
| S2 | a different build family | build card B |
| S3 | R6 (+R7) | review A or B; a review is also the second pair of eyes on the other lane's fix |
| S4 | R8 / R13 / R19 / R20 | the **quality slot**: run the journey or audit that covers the last merged quorum |
| S5 | R12 / R14 / R15 / R21 / R11 | design, copy, platform or docs card; a third build lane when no design card is due |
| PM | R0 | queue, merges, gate, ledger — never a build card |

**The interleave rule.** A *quorum* is four implementation cards merged to feat. After each quorum the
next quality slot takes, in order:

1. the next unbuilt card from wave Q (`INDEX.md` §13) whose dependency group is closed — it builds the
   harness, journey or audit and records the baseline; or
2. if all are built, the journey or audit that covers the quorum, as a **re-run**, with the result written
   where that card already writes it (the spec's annotation, or the area audit report).

A quorum may never be skipped to keep a build lane busy. A red journey, a failed budget or an axe
critical/serious is a finding, not a retry: S1 blocks the next merge batch, S2 blocks the affected area's
next implementation card.

---

## 4. Escalation

| Trigger | Who | Action |
| --- | --- | --- |
| A lane has no commit and no report in 40 min | R0 | interrupt, re-dispatch once with the same card |
| Five fix rounds, or round 3 still failing | R0 | stop fixing; R2 re-plans the card |
| Builder and R6 disagree | R0 | ruling in the ledger with cost-if-wrong; no third review round |
| R7 Critical/High | R7 | merge freeze on the touched surface; owner informed; no merge until proved fixed |
| Usability S1 (task impossible, data loss, cross-workspace leak) | R13 | blocks the next merge batch and the wave release |
| WCAG A or AA failure on a core journey | R19 | S2: fix card before the next wave; S1 if it blocks the task |
| Perf budget missed by > 20 % | R20 | finding plus a fix card; the gate keeps the new number, never hides it |
| A new need appears mid-card | R12 | a new card; the running card does not grow |
| Red feat | R10 | all merges pause until green |

### Owner-only decisions

Ask, do not rule, on: push, PR to `main`, deploy, deleting unmerged work; money, pricing, payment
provider or licence; PDPA/legal text, data residency or any public claim; a Thai string signed off as
"native quality"; a release go/no-go after an S1; hardware-dependent claims that need the real GPU box.
Everything else is R0's to decide and record as `Ruling: <decision> — <why> — <cost if wrong>`.

**Owner default when unavailable:** the safer reversible option ships behind a flag off, the question is
recorded in the ledger, and the wave continues. No irreversible or outward-facing action is taken on a
default.

---

## 5. What does not change

- R0–R11 keep their existing meaning; new roles add capacity, they do not replace a reviewer or a gate.
- One merger, one branch at a time, one gate per batch, full suite after each merge.
- Options first (2–3 designs, smallest that satisfies the card); R6 flags over-engineering.
- TDD, workspace-isolation tests, the flag-off case and the failure paths on every card.
- R6 spec and quality review, R7 on security surfaces, R9 on UI moves.
- Worktrees on `B:/02_Projects/ld-worktrees` only; never push; never touch `main`.

The execution order, card ids and file ownership live in
`docs/research/roboflow-parity/backlog/INDEX.md`; the usability method lives in
`docs/qa/USABILITY-PROGRAM.md`.
