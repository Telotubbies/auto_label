DONE

# R10 fix — the Playwright core-loop smoke: breadcrumb project link after the E-frame merges

Lane: R10 regression fixer. Branch `fix/e2e-breadcrumb`, worktree `B:/02_Projects/ld-worktrees/fix-e2e-bc`
from `feat/labeldesk-v2` @ `a213d8e`. Nothing merged, pushed or deleted; no process started or killed.
`TMP`/`TEMP` = `B:/02_Projects/ld-tmp/pytest` for every e2e run.

## Options (owner rule 5c) — smallest design that satisfies the card

| # | Design | LOC (added/removed) | Files | Trade-offs |
| --- | --- | --- | --- | --- |
| **A (chosen)** | One shared match constant in `lib/routes.ts`; the four shell consumers use it; make a crumb a link whenever it has a destination; keep screens that did not move on their old path; build project nav links through `projectPath` | **+42 / −14** | 8 | Restores the user-visible contract at the source: `useMatch` follows the route prefix, and the rail emits canonical `/p/` URLs. No new dependency, no new module. |
| B | Keep the stale `/:ws/:project/*` literals and only patch `TopBar` | ~+2 / −1 | 1 | Passes step 2 only; steps 3 and 6-7 stay broken (old `upload`/`train`/`deploy` links resolve to `null`), and the next route move breaks four files again. |
| C | Revert the T-474 legacy redirect map (`versions` back to identity, etc.) | ~+5 / −5 | 2 | Fights the card's pinned contract (`versions → dataset?tab=versions`) and breaks T-474's own tests. Rejected. |

Why A: the failure has three layers (stale match pattern, crumb renderer, old-shape nav links), and each
layer is one edit in the place that owns it. B leaves the flow red; C contradicts the card that caused
the regression.

## Which merge caused it — bisected

`a5b71d4` is the last good commit. Four merges landed after it, not three:
`f95bc92` (t/474), `d4e2043` (t/472), `b2abfe2` (t/471), `a213d8e` (t/473).

| Commit | Card | e2e core loop |
| --- | --- | --- |
| `a5b71d4` | parent | **1 passed (12.1s)** |
| `f95bc92` | T-474 `/p/` project routes | **failed at step 2** — `getByRole('navigation', {name:'Breadcrumb'}).getByRole('link', {name:'PPE Detection'})` element(s) not found |

**T-474 (`f95bc92`, feature commit `f74b774`) is the cause.** T-471 (`fcd88fb`) only swaps text-size
classes and T-473 (`677468e`) only adds the text utilities and uses one in `Home`, so neither can remove a
link; both sit after the first red commit. T-474's own report predicted this: deviation 4 says "the shell's project detection is deliberately
untouched … `AppLayout`, `TopBar`, `AppSidebar` and `JobTray` still match `/:ws/:project/*`, which now reads
`p` as the project … until the bar's match becomes `/p/:project`. Those four files belong to T-480 and
T-481 … **This is the one known gap**". T-480 was not merged, so the gap shipped.

Three layers of breakage, all from the prefix move:

1. `useMatch('/:ws/:project/*')` in `TopBar`, `AppLayout`, `AppSidebar`, `JobTray` no longer matches
   `/w/p/ppe/...`; the breadcrumb read `p` as the project, `p` is reserved, so the project crumb was never
   built.
2. The breadcrumb rendered every trailing crumb as a `<span>`. The legacy redirect lands `browse` on
   `/p/ppe/dataset`, a path with no nav label (T-474 mounted it as an alias; T-479 owns the stage name),
   so the page crumb vanished and the project crumb became the last crumb — a span, not a link.
3. The project rail (`ProjectPanel`, `ProjectLayout`) still built `/${ws}/${slug}/${to}`. `legacyProjectPath`
   only maps the renamed screens, so `upload`, `train`, `deploy`, `settings` … returned `null` and rendered
   nothing. The e2e reached this at step 3 (`Upload Data` heading never appeared).

The card text of T-474 states the intended contract, so the app is fixed, not the test: "Nav entry: none —
nav entries stay relative (`upload`, `annotate`, …) and render under whichever prefix matched"
(`docs/research/roboflow-parity/backlog/T-474.md` line 33). The test is untouched.

## Fix, in plain words

1. `src/lib/routes.ts` — new `PROJECT_ROUTE_MATCH = '/:ws/p/:project/*'`, one edit point for the prefix.
2. `TopBar`, `AppLayout`, `AppSidebar`, `JobTray` — `useMatch(PROJECT_ROUTE_MATCH)`.
3. `TopBar` — a crumb with a destination is always a `<Link>`; only a crumb without one is the current
   page. The project crumb links to the project root even when the screen has no nav label yet.
4. `src/lib/routes.ts` — `legacyProjectPath` returns the segment unchanged for screens that only gained the
   prefix (the project nav's own `to` values), instead of `null`. Unknown segments still return `null`.
5. `ProjectPanel`, `ProjectLayout` — nav links and the review/train buttons build through `projectPath`.

## Files changed

| File | +/− |
| --- | --- |
| `apps/frontend/src/lib/routes.ts` | +10 / −4 |
| `apps/frontend/src/components/shell/TopBar.tsx` | +4 / −2 |
| `apps/frontend/src/components/shell/AppLayout.tsx` | +2 / −1 |
| `apps/frontend/src/components/shell/AppSidebar.tsx` | +2 / −1 |
| `apps/frontend/src/components/shell/JobTray.tsx` | +2 / −1 |
| `apps/frontend/src/components/shell/ProjectPanel.tsx` | +2 / −1 |
| `apps/frontend/src/features/project/ProjectLayout.tsx` | +4 / −3 |
| `apps/frontend/tests/project-routes.test.mjs` | +17 / −1 |
| **Total** | **+42 / −14** |

## RED

1. New node tests before the fix:

```
$ node --test tests/project-routes.test.mjs
# SyntaxError: The requested module '../src/lib/routes.ts' does not provide an export named 'PROJECT_ROUTE_MATCH'
not ok 1 - tests\project-routes.test.mjs
```

```
$ node --test tests/project-routes.test.mjs
not ok 3 - screens that did not move keep their old URL alive
Expected values to be strictly equal:
  null !== 'upload'
```

2. e2e on `feat/labeldesk-v2` @ `f95bc92`: fails at step 2, breadcrumb link not found (output in the
bisect table above).

## GREEN

```
$ node --test tests/project-routes.test.mjs
# tests 7
# pass 7
# fail 0
```

## Test and build output (foreground, final tree)

```
$ npm test                       (apps/frontend)
# tests 275
# pass 275
# fail 0
# duration_ms 519.7522

$ npm run build                  (gen-api-types --check && tsc -b && vite build)
✓ built in 6.41s
exit=0

$ npm run e2e                    (TMP/TEMP = B:/02_Projects/ld-tmp/pytest/e2e-bc-fix)
Running 1 test using 1 worker
  ok 1 [chromium] › e2e\core-loop.spec.ts:9:1 › core loop: sign in → project → upload → annotate → version → train entry → deploy (7.7s)
  1 passed (23.4s)
```

Bisect runs, same command, are in the table above (`a5b71d4` 1 passed / `f95bc92` 1 failed).

## Open risks

- `legacyProjectPath('versions')` still lands on `dataset?tab=versions`, which today renders the Dataset
  screen without the versions tab (T-479 owns the tabbed stage). The in-app Versions link now goes to
  `/p/ppe/versions` and shows the Versions screen; only an old bookmark takes the tab path. That is
  T-474's pinned contract, not changed here.
- `ProjectPanel` and `ProjectLayout` are shared files; T-475/T-480 rewrite the same area, so expect a
  small rebase conflict there (both sides want `projectPath`).
- The e2e runs desktop 1440 only; the 375 px rail path was not exercised (no layout change in this diff).
