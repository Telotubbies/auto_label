STATUS: DONE

**TL;DR**
1. Use `github/gitignore`'s Python.gitignore verbatim for the Python side and Node.gitignore for the JS side; both already carry the tool caches (`__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `node_modules/`, `.vite/`, `*.tsbuildinfo`, `.turbo`, `.nx/cache`). Vite's own template `.gitignore` is a subset of Node.gitignore.
2. One root `.gitignore` is the norm for monorepos: Turborepo and pnpm only require root-level config files, and git natively supports nested `.gitignore` files that override the parent. Add a package-level file only when that package needs a different rule.
3. `CODEOWNERS` lives in `.github/`, repo root, or `docs/` (first found, in that order); the **last** matching pattern wins per file; `!`, `[...]` and escaped `#` do **not** work like gitignore.
4. Pin every `pre-commit` `rev` to an immutable tag/SHA — pre-commit explicitly does not support branch names — and run `--all-files` in CI (changed-files only is offered as a faster option, not a recommendation).
5. Never path-filter a **required** check: a skipped workflow leaves the check "Pending" and the PR is unmergeable. Move files in a rename-only commit (git stores no rename metadata; history is reconstructed by `-M` similarity at 50% / `diff.renameLimit` 1000), tag before and after, and revert the move commit as a unit rather than reverting a merge.

---

## 1. `.gitignore`: canonical Python and Node patterns

**Python — `github/gitignore` `Python.gitignore`** (https://github.com/github/gitignore/blob/main/Python.gitignore). Verbatim entries relevant to a mixed repo:

```gitignore
__pycache__/
*.py[codz]
*$py.class
build/
dist/
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.hypothesis/
.pytest_cache/
coverage.xml
*.egg-info/
__pypackages__/
.env
.venv
env/
venv/
.mypy_cache/
.dmypy.json
.pyre/
.pytype/
.ruff_cache/
```

Notes on exact spellings, because agents frequently "improve" them:
- The bytecode pattern in the current file is `*.py[codz]` (the older `*.py[cod]` misses `.pyz`-adjacent caches); it is not `*.pyc` alone. Same URL.
- `.venv` has **no trailing slash** in the upstream file; `env/`, `venv/` do. All three forms ignore a directory of that name at any depth. Same URL.
- `dist/` and `build/` are ignored by the **Python** template too. This matters in a mixed repo: a JS package's `dist/` and a Python package's `dist/` are the same pattern. Same URL.
- `.ruff_cache/` is present under a `# Ruff stuff:` heading. Same URL. `.mypy_cache/` under `# mypy`. Same URL.
- `.env` is ignored but no `!.env.example` exception exists in the Python file (the Node file does have one) — see Section 2 for why that asymmetry bites.

CPython's own docs state a virtual environment is "Not checked into source control systems such as Git", and since 3.13 `venv` even writes a `.gitignore` inside the environment directory by default (https://docs.python.org/3/library/venv.html, https://github.com/python/cpython/blob/main/Doc/library/venv.rst).

**Node — `github/gitignore` `Node.gitignore`** (https://github.com/github/gitignore/blob/main/Node.gitignore):

```gitignore
node_modules/
coverage
*.lcov
.nyc_output
*.tsbuildinfo
.eslintcache
.stylelintcache
dist
.next
.nuxt
.output
.vite/
.pnpm-store
.turbo
.nx/cache
.nx/workspace-data
.nx/migrate-runs
.env
.env.*
!.env.example
```

Exact-spelling notes:
- `coverage` and `dist` appear **without** a trailing slash, so they match a file *or* directory of that name at any level. Writing `coverage/` still works for directories but silently stops matching a stray `coverage` file. Same URL.
- `*.tsbuildinfo` is the TypeScript incremental-build cache — one pattern covers every package in the monorepo. Same URL.
- `.turbo` and `.nx/cache` are already in the canonical Node template, i.e. GitHub's maintainers expect the monorepo caches to be root-ignored. Same URL.

**Vite's own generated `.gitignore`**: `create-vite` ships the file as `_gitignore` in the template directory and renames it on scaffold (`renameFiles: { _gitignore: '.gitignore' }`, https://github.com/vitejs/vite/blob/main/packages/create-vite/src/index.ts). Contents (https://github.com/vitejs/vite/blob/main/packages/create-vite/template-vanilla/_gitignore):

```gitignore
logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*

node_modules
dist
dist-ssr
*.local

.vscode/*
!.vscode/extensions.json
.idea
.DS_Store
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
```

So Vite ignores `node_modules` and `dist` but **not** `.vite/`. That is not an omission: Vite's cache directory defaults to `node_modules/.vite`, already covered by `node_modules` (`build.outDir` defaults to `dist`) — https://vite.dev/config/shared-options#cachedir and https://vite.dev/config/build-options#build-outdir. Add an explicit `.vite/` only if `cacheDir` is configured outside `node_modules`.

## 2. Monorepo-specific ignore rules: one root file or one per workspace?

**What git itself says.** `.gitignore` files are read from "a `.gitignore` file in the same directory as the path, or in any parent directory (up to the top-level of the working tree), with patterns in the higher level files being overridden by those in lower level files down to the directory containing the file", and patterns "match relative to the location of the `.gitignore` file" (https://git-scm.com/docs/gitignore, section DESCRIPTION). Nested files are therefore a first-class feature, not a monorepo workaround.

The critical gotcha for monorepos: "It is not possible to re-include a file if a parent directory of that file is excluded. Git doesn't list excluded directories for performance reasons, so any patterns on contained files have no effect, no matter where they are defined." (https://git-scm.com/docs/gitignore, PATTERN FORMAT). A root `dist/` cannot be partially un-ignored by `packages/web/dist/!keep.txt`; you need to not exclude the directory, or use `!packages/web/dist/` before any `dist/` exclusion.

**What the monorepo tools say.** Neither Turborepo nor pnpm documents per-package `.gitignore` files; both describe root-level, repo-wide configuration:

- Turborepo's "minimum requirements" for a valid workspace are: packages described by the package manager, *a* lockfile, a root `package.json`, a root `turbo.json`, and a `package.json` in each package (https://turborepo.com/docs/crafting-your-repository/structuring-a-repository). No per-package ignore file appears anywhere in that list.
- pnpm: "A workspace must have a `pnpm-workspace.yaml` file in its root", listing `packages:` (https://pnpm.io/workspaces). One workspace definition, one install graph.

Practical rule that follows from the two sources above: keep **one root `.gitignore`** as the single source of truth, and add a package-level `.gitignore` only when a package must ignore something the root must *not* ignore (nested files win, per gitignore(5)), or when a package is meant to be extracted/copied out of the repo intact. Search output stays readable because the root file is the one reviewers see in a diff.

## 3. `CODEOWNERS`

Source: docs.github.com "About code owners" (https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

- **Locations.** "create a new file called `CODEOWNERS` in the `.github/`, root, or `docs/` directory of the repository"; if several exist, GitHub "will search for them in that order and use the first one it finds". Same URL.
- **Branch scoping.** The file applies per branch, and "For code owners to receive review requests, the `CODEOWNERS` file must be on the base branch of the pull request." Fork PRs use the upstream base branch's file. Same URL.
- **Syntax.** A pattern (gitignore-like) followed by one or more `@username` or `@org/team-name`; owners need explicit `write` access; email addresses are also accepted. Multiple owners for the same pattern "must be on the same line" — otherwise "the pattern matches only the last mentioned code owner". Inline `#` comments are allowed. Same URL.
- **Precedence.** "Order is important; the last matching pattern takes the most precedence" (example in the doc: a `*` default owner plus a later `*.js @js-owner` means only `@js-owner` is requested for JS changes). Same URL.
- **Not gitignore.** "Escaping a pattern starting with `#` using `\` … doesn't work", "Using `!` to negate a pattern doesn't work", "Using `[ ]` to define a character range doesn't work". Same URL.
- **Failure modes.** Invalid lines are skipped; unknown or under-permissioned users/teams get no assignment; paths are case sensitive; the file must be under 3 MB or it is not loaded at all. Same URL.
- **Enforcement.** Branch protection option "Require review from Code Owners"; an approval from *any* listed owner satisfies it. Protect the file itself with `/.github/CODEOWNERS @owner` or `/.github/ @owner`. Same URL.

Minimal shape for a polyglot repo:

```text
*                                   @org/maintainers
/.github/                           @org/maintainers
/backend/**                         @org/python-owners
/frontend/**                        @org/ts-owners
*.py                                @org/python-owners
*.{ts,tsx,vue}                      @org/ts-owners
```

(Pattern list is illustrative; `{a,b}` brace expansion is *not* documented on the page above — prefer separate lines for each extension.)

## 4. `pre-commit`

Source: pre-commit.com (https://pre-commit.com/) and the pre-commit-hooks README (https://github.com/pre-commit/pre-commit-hooks).

- **Recommended config shape.** "create a file named `.pre-commit-config.yaml`"; `pre-commit sample-config` generates a basic one; each entry is a `repo:` + `rev:` + `hooks:` mapping (https://pre-commit.com/#quick-start, https://pre-commit.com/#pre-commit-configyaml---repos).
- **Why pin `rev`.** "pre-commit assumes that the value of `rev` is an immutable ref (such as a tag or SHA) and will cache based on that. Using a branch name (or `HEAD`) for the value of `rev` is not supported and will only represent the state of that mutable ref at the time of hook installation (and will NOT update automatically)." The framework deliberately has no "unpinned latest" mode; upgrade with `pre-commit autoupdate` (https://pre-commit.com/#using-the-latest-version-for-a-repository).
- **Standard hooks.**
  - Language-agnostic, from `pre-commit/pre-commit-hooks`: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`. `check-added-large-files` takes "`args: ['--maxkb=123']` (default=500kB)", only checks files "staged for addition", and skips git-lfs files when lfs is installed (https://github.com/pre-commit/pre-commit-hooks#check-added-large-files).
  - Ruff: hook ids are `ruff-check` and `ruff-format` (`ruff` is kept only as a "Legacy alias"); `ruff-format` also formats Python code blocks in Markdown by default (https://github.com/astral-sh/ruff-pre-commit, https://github.com/astral-sh/ruff-pre-commit/blob/main/.pre-commit-hooks.yaml). pre-commit.com lists it as the recommended Python linter/formatter integration (https://pre-commit.com/hooks.html).
  - ESLint: `pre-commit/mirrors-eslint`, `id: eslint`, with the project's plugins declared under `additional_dependencies`; for TypeScript you must widen the file selection, e.g. `files: \.[jt]sx?$` plus `types: [file]` (https://github.com/pre-commit/mirrors-eslint). Repo is actively maintained (last push 2026-11-14).
  - Prettier: `pre-commit/mirrors-prettier` is **archived** ("prettier made some changes that breaks plugins entirely", https://github.com/pre-commit/mirrors-prettier). Safest primary-source-compatible route is a `repo: local` hook that runs the repo's own pinned Prettier binary, so formatter version and plugins match `package.json` (local hooks: https://pre-commit.com/#repository-local-hooks).
- **CI, changed files vs all files.** The docs say both, but the recommendation is all-files: "adding `pre-commit run --all-files` as a CI step will ensure everything stays in tip-top shape. To check only files which have changed, which may be faster, use something like `pre-commit run --from-ref origin/HEAD --to-ref HEAD`" (https://pre-commit.com/#usage-in-continuous-integration). So: `--all-files` is the stated practice, `--from-ref/--to-ref` is an explicitly optional speed-up, not a recommendation. Also cache `~/.cache/pre-commit` keyed on the config hash (same section).

Example skeleton (hook set as documented above):

```yaml
minimum_pre_commit_version: '4.0.0'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1024']
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.5
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: <tag>
    hooks:
      - id: eslint
        files: \.[jt]sx?$
        types: [file]
        additional_dependencies: ['eslint@9']
  - repo: local
    hooks:
      - id: prettier
        name: prettier
        entry: npx --no-install prettier --write
        language: system
        files: \.(ts|tsx|js|jsx|json|css|md)$
```

## 5. CI path filters

Source: docs.github.com workflow syntax (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore).

- `paths` and `paths-ignore` are available on `push` and `pull_request`; "Path filters are not evaluated for pushes of tags." You "cannot use both the `paths` and `paths-ignore` filters for the same event"; for include+exclude use `paths` with `!` entries, and at least one non-negated entry must exist. Order matters: a later `!` excludes, a later positive re-includes. Same URL.
- If both `branches` and `paths` are set, "the workflow will only run when both filters are satisfied". Same URL.
- **Diff semantics.** Pushes use two-dot diffs, pull requests use three-dot diffs ("a comparison between the most recent version of the topic branch and the commit where the topic branch was last synced with the base branch"). "If there are no files changed, the workflow will not run." Same URL (`#git-diff-comparisons`).
- **Hard limits.** A push with more than 1,000 commits always runs the workflow; a timed-out diff always runs it; and if the diff exceeds the file cap (300 in older deployments, 3,000 where the newer limit is enabled) and no match appears in the returned page, the workflow will **not** run. Same URL. A big `git mv`-style migration commit can therefore *skip* a filtered workflow — another reason to keep moves small and path filters coarse.
- **The required-check trap.** "If a workflow is skipped due to path filtering, branch filtering, or a commit message, then checks associated with that workflow will remain in a 'Pending' state. A pull request that requires those checks to be successful will be blocked from merging." (https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs). The reusables behind the syntax page state the same and add: "You should not use path or branch filtering to skip workflow runs if the workflow is required to pass before merging" (https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#example-including-paths — reusable `pull_requests/path-filtering-required-workflows`).
- **Job-level filtering.** Built-in filters operate per *workflow*, "they don't work on a level of individual jobs or steps" (https://github.com/dorny/paths-filter). `dorny/paths-filter` fills that gap: it exposes a `changes` output consumed by `if:`, supports `pull_request`, `push`, `merge_group`, local `HEAD`, uses picomatch with dot-matching enabled, and needs `pull-requests: read` on PR events (same repo README). It is a third-party action — pin it to a major tag or SHA per normal supply-chain practice.

Pattern (PR-safe shape: always-run aggregator job required, filtered work jobs optional):

```yaml
on:
  pull_request:
    paths: ['backend/**', 'frontend/**', '.github/workflows/**', 'pyproject.toml', 'pnpm-lock.yaml']
jobs:
  changes:
    runs-on: ubuntu-latest
    permissions: { pull-requests: read }
    outputs: { backend: '${{ steps.f.outputs.backend }}' }
    steps:
      - uses: actions/checkout@v4
      - id: f
        uses: dorny/paths-filter@v4
        with:
          filters: |
            backend: ['backend/**']
  python-tests:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    ...
```

## 6. Cache and artefact hygiene: what must never be committed

- **Never commit:** virtualenvs (`CPython`: a venv is "Not checked into source control systems such as Git", https://docs.python.org/3/library/venv.html), `node_modules/` and package-manager stores (`.pnpm-store`), build outputs (`dist`, `build`, `.next`, `.turbo`, `.nx/cache` — all in Node.gitignore, https://github.com/github/gitignore/blob/main/Node.gitignore), interpreter caches (`__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/` — https://github.com/github/gitignore/blob/main/Python.gitignore), test/coverage output (`coverage`, `.coverage`, `htmlcov/`), editor state, OS junk (`.DS_Store`), and anything from `.env` (`Node.gitignore` ignores `.env` and `.env.*` but keeps `!.env.example` — mirror that exception explicitly, because the Python template does not provide it).
- **Large binaries.** GitHub warns when you add or update a file larger than **50 MiB**, blocks files larger than **100 MiB**, and caps browser uploads at **25 MiB**; repositories should "remain small, ideally less than 1 GB, and less than 5 GB is strongly recommended" (https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github; the numbers come from that page's `large_files` data: `warning_size: 50 MiB`, `max_github_size: 100 MiB`, `max_github_browser_size: 25 MiB`). Use Git LFS or Releases for anything that must be distributed (same page, "Distributing large binaries").
- **Secrets.** Removing a leaked secret requires rewriting history and coordinating with every clone: "Sensitive data can be removed from the history of a repository _if_ you can carefully coordinate with everyone who has cloned it and you are willing to manage the side effects." (https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). GitHub recommends `git filter-repo` for history rewriting and shows `git rm --cached` + `git commit --amend -CHEAD` for the last unpushed commit (https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github#removing-files-from-a-repositorys-history).
- **History bloat is permanent-ish.** A committed binary stays in the object database and in every clone even after deletion; the only fix is a history rewrite, which is exactly the "side effects" the security page warns about. That is why the pre-commit `check-added-large-files` gate (default 500 kB, configurable via `--maxkb`) is the cheap preventive control (https://github.com/pre-commit/pre-commit-hooks#check-added-large-files).
- **Untracking vs deleting.** `git rm --cached <path>` removes a path from the index while leaving it on disk; `git rm -r --cached` does the same for a directory (https://git-scm.com/docs/git-rm). Use this when adding an ignore rule for an already-tracked artefact — the ignore rule alone does nothing, because "Files already tracked by Git are not affected" (https://git-scm.com/docs/gitignore, DESCRIPTION).

## 7. Practical migration hygiene when moving many files

- **`git mv` vs `mv` + `git add -A`.** `git mv` "Move[s] or rename[s] a file, directory, or symlink… The index is updated after successful completion, but the change must still be committed." (https://git-scm.com/docs/git-mv). Because git records no rename flag in the commit object, both approaches produce the *same* commit content; the difference is only that `git mv` stages the removal and addition for you, while `mv` requires an explicit `git add -A` (or `git add -u`). History is not lost either way — it is *reconstructed* later.
- **Rename detection is a diff-time heuristic.** `-M[<n>]` / `--find-renames[<n>]`: "a threshold on the similarity index… The default similarity index is 50%", with `-M100%` limiting detection to exact renames (https://git-scm.com/docs/diff-options, entry `-M[<n>]`). The exhaustive pairing is capped by `-l<num>`, which "Defaults to `diff.renameLimit`", and `diff.renameLimit` "If not set, the default value is currently 1000" (https://git-scm.com/docs/git-config#Documentation/git-config.txt-diffrenameLimit). Consequences: a move that also rewrites >50% of the file reads as delete+add; a migration larger than 1,000 moved files can silently drop out of exhaustive pairing and show as delete+add unless you raise `-l`/`diff.renameLimit`.
- **`--follow` is single-file-only.** "`--follow`: Continue listing the history of a file beyond renames (works only for a single file)." (https://git-scm.com/docs/git-log). There is no `--follow` for "where did this directory go"; for that you read `git log --summary -M` / `git log --diff-filter=R --name-status` output.
- **Keep rename commits pure.** A commit that only renames is (a) detected at 100% similarity, so `git log --follow`, `git blame -C` and review tools all work, and (b) trivially revertible (Section 9). Mixing content edits into the move commit pushes similarity below the 50% default and destroys both properties. Split as: (1) move-only commit, (2) content/behaviour commit(s). Verify before committing with `git diff --cached -M --summary` (expect `rename old => new (100%)`) or `git show -M --stat`.
- **Practical detection check.** `git diff --find-renames=50% --summary HEAD~1 HEAD` on the migration commit should list `rename` lines, not `delete`/`create` pairs (same option docs).

## 8. Verification checklist (read-only; run from repo root)

Each line names the file/command it checks.

1. `git status --porcelain` → empty, and `git check-ignore -v __pycache__ .pytest_cache .ruff_cache .mypy_cache .venv` → each resolves to a rule in the root `.gitignore`.
2. `git check-ignore -v node_modules dist coverage x.tsbuildinfo .vite .turbo .nx/cache` → all ignored by root `.gitignore` (add `.vite` only if `cacheDir` moved).
3. `.gitignore` contains, unmodified from upstream spellings: `__pycache__/`, `*.py[codz]`, `.venv`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `node_modules/`, `coverage`, `dist`, `*.tsbuildinfo` — `Select-String -Path .gitignore -Pattern '__pycache__/','\*\.py\[codz\]','\.venv','\.pytest_cache/','\.ruff_cache/','\.mypy_cache/','node_modules/','^coverage$','^dist$','\*\.tsbuildinfo'`.
4. `.gitignore` keeps the env exception: `grep -nE '^!\.env\.example$' .gitignore` (the Python template lacks it; add it once, at root).
5. No tracked artefacts: `git ls-files | grep -E '(^|/)(__pycache__|node_modules|dist|build|\.venv|\.pytest_cache|\.ruff_cache|\.mypy_cache|\.turbo|\.nx)/'` → no output.
6. No tracked secrets: `git ls-files | grep -E '(^|/)\.env(\.|$)'` → only `.env.example`; plus `git ls-files -z | xargs -0 -n1 git check-attr --all --` sanity pass if `.gitattributes` exists.
7. No oversized objects in history: `git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>52428800'` → empty (50 MiB = GitHub's warning size).
8. `CODEOWNERS` exists in exactly the intended one of `.github/CODEOWNERS`, `CODEOWNERS`, `docs/CODEOWNERS` (`git ls-files | grep -E '(^|/)CODEOWNERS$'`), every line is `<pattern> <@user|@org/team|email>` (`grep -vE '^\s*(#|$)' .github/CODEOWNERS`), no `!`, no `[...]`, and file size `< 3 MB` (`(Get-Item .github/CODEOWNERS).Length -lt 3MB`).
9. `CODEOWNERS` precedence is deliberate: the last line matching each critical path is the intended team — spot-check `packages/web/**`, `.github/**`, `docs/**` by reading top-to-bottom.
10. `.pre-commit-config.yaml` exists at root and every `rev:` is a tag or 40-hex SHA: `grep -nE '^\s*rev:' .pre-commit-config.yaml` (no `main`, `master`, `HEAD`).
11. Required hook ids present: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `ruff-check`, `ruff-format`, plus `eslint`/`prettier` equivalents: `grep -nE 'id: (trailing-whitespace|end-of-file-fixer|check-yaml|check-added-large-files|ruff-check|ruff-format|eslint|prettier)' .pre-commit-config.yaml`.
12. `check-added-large-files` has an explicit ceiling: `grep -nA2 'id: check-added-large-files' .pre-commit-config.yaml` shows `args: ['--maxkb=...']`.
13. Hooks actually run clean: `pre-commit run --all-files --show-diff-on-failure` → exit 0 (same command CI should use, per pre-commit's CI section).
14. CI path filters do not guard a required job: `grep -nE '^\s+(paths|paths-ignore):' .github/workflows/*.yml` → confirm none sits on a workflow whose check is required in branch protection; filtered work must hang off `if:`/`dorny/paths-filter`, with an always-running aggregator job as the required check.
15. Built-in `paths`/`paths-ignore` not combined on one event, and no bare `**` / `*` unquoted: `grep -nE "^\s+- '?\*\*" .github/workflows/*.yml` (YAML needs quotes for leading `*`, per workflow-syntax docs).
16. Migration commit is rename-pure: `git show --stat -M --summary <move-commit>` lists `rename … (100%)` and no content hunks; `git show --numstat -M <move-commit>` shows `0 0` for every path.
17. Old paths are gone and new paths are tracked: `git ls-files | grep -c '<old-prefix>/'` → `0`; `git ls-tree -r --name-only HEAD -- <new-prefix>` lists the expected files.
18. Large move stayed under the pairing cap: `git diff-tree -r -M -l0 --name-status <move-commit>` (`-l0` = unlimited) shows renames even above 1,000 files.
19. Rollback points exist: `git tag -l 'pre-layout-*' 'post-layout-*'` lists both, and `git tag -v` / `git show --stat <tag>` resolves to the expected commits.
20. Revert rehearsed (no state change): `git revert --no-commit <move-commit> && git revert --abort` → clean; or `git revert -n <move-commit>` then `git reset` if `--abort` is unsupported by your version.

## 9. Branch and rollback safety for a large refactor

- **`git revert` is patch reversal, not "undo".** "Given one or more existing commits, revert the changes that the related patches introduce, and record some new commits that record them. This requires your working tree to be clean"; and "Reverting a commit may result in a merge conflict." (https://git-scm.com/docs/git-revert). Revert of a *pure rename* commit is the easiest case in git: the patch is a delete+create pair with identical content that the merge machinery re-applies in reverse; there is nothing to conflict with unless later commits touched the same paths.
- **Reverting a merge needs `-m`.** "Usually you cannot revert a merge because you do not know which side of the merge should be considered the mainline. This option specifies the parent number (starting from 1) of the mainline" (https://git-scm.com/docs/git-revert, `-m parent-number`). The same entry warns: "Reverting a merge commit declares that you will never want the tree changes brought in by the merge. As a result, later merges will only bring in tree changes introduced by commits that are not ancestors of the previously reverted merge." (See also the "revert a faulty merge" how-to, https://git-scm.com/docs/howto/revert-a-faulty-merge.)
- **Revert a range in one commit.** `git revert -n` / `--no-commit` applies the reversed changes without committing, so a multi-commit migration can be undone as a single reviewable commit (https://git-scm.com/docs/git-revert, `-n`). Order matters when reverting a series: `git rev-list --reverse <base>..<head>` then `git revert -n --no-edit <shas…>`.
- **Safest strategy for a revertible layout migration.**
  1. Annotated tags on both ends: "Annotated tags are meant for release while lightweight tags are meant for private or temporary object labels" (https://git-scm.com/docs/git-tag) — e.g. `git tag -a pre-layout-migration -m …`, `git tag -a post-layout-migration -m …`. Tags give a fixed comparison point (`git diff pre-layout-migration..HEAD`) independent of branch churn.
  2. One move-only commit (or a small number of them, each covering one coherent directory), then content commits on top. This makes "revert the move" a single `git revert` with a clean patch, and keeps `-M` detection at 100%.
  3. Keep the migration on its own branch, merged with `--no-ff`, so the fallback is either `git revert -m 1 <merge>` (whole migration) or reverting the individual move commits (partial). Prefer reverting the individual commits: reverting the merge poisons future re-merges of that branch, per the `-m` warning above.
  4. Branch-protection/CI note: a revert PR must not be blocked by a path-filtered required check (Section 5) — the same trap applies to the rollback path, which is the worst time to discover it.
  5. On a shared branch prefer revert over `reset`: `--hard` "Overwrite[s] all files and directories with the version from _<commit>_, and may overwrite untracked files. Tracked files not in _<commit>_ are removed so that the working tree matches _<commit>_" (https://git-scm.com/docs/git-reset) — that is a good local experiment reset and a bad way to undo a pushed migration.

---

## Citations

**Primary — git**
1. https://git-scm.com/docs/gitignore — gitignore(5): pattern format, nested-file precedence, "cannot re-include inside an excluded directory", tracked files unaffected. (Mirrored source: https://github.com/git/git/blob/master/Documentation/gitignore.adoc)
2. https://git-scm.com/docs/git-mv — git-mv(1): move/rename, index updated, "must still be committed".
3. https://git-scm.com/docs/git-log — git-log(1): `--follow` "works only for a single file".
4. https://git-scm.com/docs/diff-options — `-M[<n>]` / `--find-renames` (default similarity 50%), `-l<num>` pairing cap, `--diff-filter`.
5. https://git-scm.com/docs/git-config — `diff.renameLimit` default 1000, `diff.renames` default true.
6. https://git-scm.com/docs/git-revert — revert semantics, `-m parent-number`, `-n`, merge-conflict and re-merge caveat.
7. https://git-scm.com/docs/git-tag — annotated vs lightweight tags.
8. https://git-scm.com/docs/git-rm — `--cached` untracking.
9. https://git-scm.com/docs/howto/revert-a-faulty-merge — REVERT-A-FAULTY-MERGE HOWTO.

**Primary — github/gitignore & Vite**
10. https://github.com/github/gitignore/blob/main/Python.gitignore — canonical Python patterns.
11. https://github.com/github/gitignore/blob/main/Node.gitignore — canonical Node patterns (incl. `.vite/`, `.turbo`, `.nx/cache`).
12. https://github.com/vitejs/vite/blob/main/packages/create-vite/template-vanilla/_gitignore — Vite's generated ignore file.
13. https://github.com/vitejs/vite/blob/main/packages/create-vite/src/index.ts — `_gitignore` → `.gitignore` rename map.
14. https://vite.dev/config/shared-options#cachedir — `cacheDir` default `node_modules/.vite`.
15. https://vite.dev/config/build-options#build-outdir — `outDir` default `dist`.

**Primary — docs.github.com (source: github/docs)**
16. https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners — "About code owners": locations, order, last-match-wins, syntax limits, 3 MB, base branch.
17. https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax — `on.<push|pull_request>.<paths|paths-ignore>`, git-diff comparisons, limits, filter pattern cheat sheet.
18. https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs — skipped workflows leave checks "Pending" → PR blocked.
19. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github — 50 MiB warning, 100 MiB block, 25 MiB browser, 1 GB/5 GB repo guidance, `git rm --cached` + amend, `filter-repo`.
20. https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository — secrets ⇒ history rewrite + coordination.

**Primary — pre-commit**
21. https://pre-commit.com/ — quick start, config schema, "Usage in continuous integration" (`--all-files`, `--from-ref/--to-ref`), "Using the latest version for a repository" (immutable `rev`).
22. https://pre-commit.com/hooks.html — featured hooks (`astral-sh/ruff-pre-commit`, `pre-commit/pre-commit-hooks`, biome, gitleaks…).
23. https://github.com/pre-commit/pre-commit-hooks — `check-added-large-files` `--maxkb` (default 500 kB), `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`.
24. https://github.com/astral-sh/ruff-pre-commit — hook ids `ruff-check` / `ruff-format`, pinning example; `.pre-commit-hooks.yaml` shows `ruff` as legacy alias.
25. https://github.com/pre-commit/mirrors-eslint — `eslint` hook, `additional_dependencies`, TypeScript file selection.
26. https://github.com/pre-commit/mirrors-prettier — archived (prettier plugin breakage); hence the `repo: local` route.

**Primary — monorepo tooling**
27. https://turborepo.com/docs/crafting-your-repository/structuring-a-repository — workspace "minimum requirements" (root `package.json`, root `turbo.json`, lockfile, package manifests); no per-package ignore requirement.
28. https://pnpm.io/workspaces — `pnpm-workspace.yaml` "must" live at the workspace root.

**Primary — language toolchain**
29. https://docs.python.org/3/library/venv.html — venv "Not checked into source control systems such as Git"; `.gitignore` written into the env by default.

**Secondary**
30. https://github.com/dorny/paths-filter — third-party action README (job/step-level path filtering; "built-in path filters … don't work on a level of individual jobs or steps"). Secondary by definition: not GitHub-owned, but the de-facto reference for job-level filtering.
