DONE

# T-495 — One colour source for status, split and class chips

Worktree `B:\02_Projects\ld-worktrees\t-495`, branch `t/495` from `feat/labeldesk-v2` @ `a213d8e`.
Commits: `0e8570d` (test/RED), `389171a` (implementation).

## Options first (owner rule)

| # | Design | Prod LOC | Files touched | Trade-off |
| --- | --- | --- | --- | --- |
| A | Two pure helpers in `lib/theme.ts` returning shipped role class strings; Dataset swaps its constant; AnnotateBoard swaps one class; one node test file | ~30 | `theme.ts`, `Dataset.tsx`, `AnnotateBoard.tsx`, `tests/colour-source.test.mjs` | Smallest complete change; keeps the file ownership the card gives other lanes; Deploy waits for T-314 as the card says |
| B | New `lib/colours.ts` module and refactor `StatusPill`, `Deploy.tsx`, insights split colours to consume it | ~90 | + `ui.tsx`, `Deploy.tsx`, 4 insights files, new module | Violates ownership (`ui.tsx` is T-487, `Deploy.tsx` is T-314, insights files belong to other cards); bigger diff and merge risk |
| C | Add `--*-bg` CSS variables plus a helper | ~20 | `index.css`, `theme.ts` | Introduces a second token family; refused by VISUAL-OVERRIDE and T-470's `test_no_parallel_token_family` |

**Chosen: A.** It is the only design that fully satisfies the card inside its file list, and it adds no
token, palette or dependency.

## What I did, in plain words

1. `apps/frontend/src/lib/theme.ts` now exports `splitColor(split)` and `statusTone(status)` beside
   `classColor`. Both return shipped role class strings, not hex or raw Tailwind hues:
   - splits: `train` = `bg-secondary text-secondary-foreground`, `valid` = `bg-info/15 text-info`,
     `test` = `bg-warning/15 text-warning`; an unknown split keeps the neutral tone.
   - statuses: `done` = success, `running` = info, `queued` = warning, `failed` = destructive,
     each as `bg-<role>/15 text-<role>`; an unknown status returns
     `{ label: <raw word>, className: 'bg-secondary text-secondary-foreground' }`, so it can never
     render as an empty chip.
2. `Dataset.tsx` lost the local `SPLIT_TONE` map and its three raw hues, imports `splitColor`, and the
   split chip now prints the split word in the shared tone. The chip moved from `text-[10px]` to the
   shipped `text-xs` at the same time, because the tinted role needs its matching text role and T-471
   forbids sub-12 px text.
3. `AnnotateBoard.tsx`: the approve button's `bg-green-600 hover:bg-green-700` became the success role
   `bg-success text-background hover:bg-success/90`, the same pattern `Editor.tsx`'s Approve already uses.
4. `Deploy.tsx` was not touched, as the card requires. Its local eight-colour array is still pinned by
   the new test, which skips with a named reason until T-314 lands `deploy/TestPane.tsx`.
5. The new test also freezes the raw-hue count per file under `src/features/**`; it may only shrink.

## Files changed (vs `a213d8e`)

| File | + | − |
| --- | --- | --- |
| `apps/frontend/src/lib/theme.ts` | 26 | 0 |
| `apps/frontend/src/features/project/Dataset.tsx` | 2 | 3 |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | 1 | 1 |
| `apps/frontend/tests/colour-source.test.mjs` (new) | 95 | 0 |
| **Total** | **124** | **4** |

## TDD — RED

Before the helpers existed (`node --test tests/colour-source.test.mjs`):

```
not ok 1 - test_split_colours_are_three_distinct_tones
  error: 'undefined is not a function'
not ok 2 - test_unknown_status_is_neutral_but_labelled
  error: 'statusTone is not a function'
not ok 3 - test_the_four_status_roles_print_their_word
  error: 'statusTone is not a function'
not ok 4 - test_dataset_uses_split_color
  error: 'Dataset.tsx keeps no local split palette'
not ok 5 - test_deploy_has_one_colour_source # SKIP T-314 has not landed: Deploy.tsx still owns the local eight-colour array
not ok 6 - test_no_new_raw_palette_classes
  error: 'features/project/AnnotateBoard.tsx adds a raw Tailwind hue; a chip resolves through splitColor, statusTone or classColor'
# tests 6
# pass 0
# fail 5
# skipped 1
```

## TDD — GREEN

After the implementation:

```
ok 1 - test_split_colours_are_three_distinct_tones
ok 2 - test_unknown_status_is_neutral_but_labelled
ok 3 - test_the_four_status_roles_print_their_word
ok 4 - test_dataset_uses_split_color
ok 5 - test_deploy_has_one_colour_source # SKIP T-314 has not landed: Deploy.tsx still owns the local eight-colour array
ok 6 - test_no_new_raw_palette_classes
# tests 6
# pass 5
# fail 0
# skipped 1
```

## Touched tests and full suite

`apps/frontend` → `npm test` (`node --test "tests/*.test.mjs"`), all files including the new one:

```
1..279
# tests 279
# pass 278
# fail 0
# skipped 1
# duration_ms 524.9311
```

The single skip is the card's prescribed T-314 wait. No backend test was touched or run: the card has no
backend surface and the OpenAPI contract did not change, so no regeneration was needed.

## Build

`npm run build` (runs `gen-api-types --check`, `tsc -b`, `vite build`):

```
> node scripts/gen-api-types.mjs --check && tsc -b && vite build
dist/index.html                               0.41 kB │ gzip:   0.27 kB
✓ built in 7.40s
exit=0
```

The only build note is the pre-existing Vite chunk-size warning (charts/index > 500 kB), unrelated to
this diff.

## Deviations from the card

1. **One extra test** — `test_the_four_status_roles_print_their_word` beyond the five listed. It exists
   only to prove the card's acceptance line that `done`, `running`, `queued` and `failed` map to the
   four semantic roles and print their word.
2. **Chip type** — the Dataset split chip also went from `text-[10px]` to `text-xs` in the same line.
   Keeping `text-white` on a tinted role would have lost contrast; leaving 10 px would have reintroduced
   a size T-471 bans. The swap is still the one chip line the card asks for.
3. **Return shape** — `statusTone` returns `{ label, className }`, matching T-487's `chipTone` idiom, so
   a caller cannot render the colour without the word. The card names the label and the neutral class,
   not the exact object shape.
4. **`text-[10px]` was not touched elsewhere**; the remaining raw hue in `AnnotateBoard.tsx`
   (`bg-red-50`) and the other three files are frozen, not rewritten, because they are outside this card.
5. `Deploy.tsx`, `deploy/TestPane.tsx` and the versions/insights surfaces were deliberately left alone;
   T-314 and the surfaces' owning cards consume `classColor`/`splitColor`.

## Risks the merge captain should know

- `node_modules` in the worktree is a junction to the main checkout's `apps/frontend/node_modules`
  (untracked, gitignored). Remove the junction or the worktree when the branch is merged.
- Until T-314 lands, `Deploy.tsx` still draws with its own eight-colour array; that is the card's
  explicit hand-off, and the guard test will start enforcing it the moment `deploy/TestPane.tsx` exists.
