STATUS: DONE

TL;DR
1. Every major tool converges on the same rule: a directory is an *app* if it produces a deployable artifact, a *package* if other code imports it. The names `apps/` and `packages/` are conventions, not requirements, and only Turborepo and Nx docs actually recommend them.
2. Turborepo's official structure (`apps/*` + `packages/*`, root `package.json` + lockfile + `turbo.json`) is the closest thing to a canonical polyglot layout, and Turborepo now has first-class (experimental) support for uv workspaces and for non-JS packages that carry a `package.json` shim.
3. pnpm prescribes no folder split at all — `pnpm-workspace.yaml` just takes a glob list — and as of v12 pnpm can resolve Python deps too, honouring `[tool.uv.workspace]` members.
4. uv's own recommended layout is a root project plus libraries under `packages/`, with `[tool.uv.workspace] members` and `dep = { workspace = true }`; it fits a FastAPI app + worker library cleanly, with one shared lockfile and one shared `requires-python`.
5. All four ecosystems explicitly say the apps/packages split is optional and that flat repos are fine — so a plan that skips or delays the split can cite primary docs, not vibes.

Research date: 2026-11-17. All claims below are from official docs unless marked **[secondary]**.

---

## 1. `apps/` vs `packages/` (or `libs/`): what the tools actually say

**The load-bearing definition comes from Turborepo, and it is about deployability, not folder name.**

- Turborepo: "We recommend starting with splitting your packages into `apps/` for applications and services and `packages/` for everything else, like libraries and tooling." — https://turborepo.com/docs/crafting-your-repository/structuring-a-repository
- An Application Package is "a package in your workspace that will be deployed from your workspace… commonly found in the `./apps` directory", and "It's best practice that your Application Packages are the 'end' of your Package Graph, not being installed into other packages of your repository." — https://turborepo.com/docs/core-concepts/package-types
- A Library Package is "code that you intend to share around your workspace. They aren't independently deployable." — same page.
- Turborepo flags the exception: installing an app into another package "should be the exception", the one listed case being an e2e test package that depends on the app so it is aware of re-deploys. Same page.

**Nx agrees, and is explicit that `libs/` is an accepted alias.**

- "**apps/**: Deployable applications (frontends, backends, CLIs)"; "**packages/**: Shared libraries consumed by apps or other packages"; "You may also see `libs/` used in place of `packages/` in some Nx workspaces. Both work. The `packages/` convention aligns with common pnpm, yarn, and npm workspace conventions." — https://nx.dev/docs/getting-started/tutorials/crafting-your-workspace

**pnpm says nothing about the split.** Its workspace page only shows `packages: - packages/*` as an example glob and never distinguishes apps from libraries — https://pnpm.io/workspaces. The split you see in pnpm repos is imported from Turborepo/Nx docs, not from pnpm.

**The "monorepo handbook" tier of writing does not prescribe folder names either.** monorepo.tools (maintained by Nx) defines a monorepo as "a single repository containing multiple distinct projects, with well-defined relationships" and spends its length on caching/affected/tooling properties, with no apps/packages rule — https://monorepo.tools/. **[secondary]** Treat Turborepo's *Structuring a repository* page as the de facto handbook chapter.

**Practical decision rule (synthesis of the three primary sources above):** if CI/CD has a deploy or release step for the directory → `apps/`. If its only consumer is other code in the repo or the registry → `packages/`. A background worker that ships its own container is an app. A worker *library* that the API also imports is a package.

---

## 2. Turborepo: recommended structure, naming, and Python/other languages

**Minimum anatomy** (root `package.json`, package-manager lockfile, `turbo.json`, and a `package.json` in every package): apps/`docs`, apps/`web`, packages/`ui` — https://turborepo.com/docs/crafting-your-repository/structuring-a-repository

**Globs, and one hard constraint that matters for layout:**

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/*"
  - "packages/*"
```

- "Using this configuration, every directory **with a `package.json`** in the `apps` or `packages` directories will be considered a package."
- "Turborepo does not support nested packages like `apps/**` or `packages/**` due to ambiguous behavior among package managers… If you'd like to group packages by directory, you can do this using globs like `packages/*` and `packages/group/*` and **not** creating a `packages/group/package.json` file."
- Same page. This rules out `apps/web/frontend/`-style nesting.

**Non-JS projects (the general escape hatch):** "Turborepo can run other language toolchains through scripts in `package.json`. Add a package for each independently cacheable project and declare its dependencies so Turborepo can order tasks and invalidate cached results." The worked .NET example puts `apps/api/` and `packages/lib/` side by side with `package.json` files whose `scripts.build` shells out to `dotnet`, and adds `"lib": "workspace:*"` so turbo orders and invalidates correctly — https://turborepo.com/docs/guides/multi-language. Note the explicit caveat: "Turborepo does not read `.csproj` references or manage NuGet dependencies", i.e. the JS dependency edge and the native dependency edge must be kept in sync by hand.

**Native uv support (experimental, 2026):** set `futureFlags.experimentalPythonWorkspaces: true` in `turbo.json`. Then "Turborepo can discover the members of a uv workspace as packages, add their dependency relationships to the Package Graph, and map common Turborepo tasks to uv commands." Requirements: `uv` on PATH, a root `pyproject.toml` with `[tool.uv.workspace]`, "A valid `[tool.turbo].name` for identity in Turborepo's graph", and a root `uv.lock` that Turborepo "never creates or updates". Their example again uses `members = ["packages/*"]`, and the two package types are "Member packages" (real graph nodes) and "The root workspace package" (uses `[tool.turbo] name`, depends on every member). Status warning: "uv support is experimental and can change at any time." — https://turborepo.com/docs/guides/tools/python

**Naming:** packages get unique names, and Turborepo recommends a scope prefix for internal packages (`@repo/...` in docs, `@acme/...` in prose) to avoid collisions with the public registry — https://turborepo.com/docs/crafting-your-repository/structuring-a-repository. There is no official requirement that a directory be called `app` or `workspace`; the task name comes from `package.json#scripts`, and the package name from `package.json#name`.

---

## 3. pnpm workspaces

**Mechanics.** A workspace needs `pnpm-workspace.yaml` at the root; its `packages` field "lists the directories of the workspace's projects" — https://pnpm.io/workspaces. If `packages` is omitted, "only the root package is included in the workspace" — https://pnpm.io/settings#packages.

**Glob syntax** (all from https://pnpm.io/settings#packages):

```yaml
packages:
  - 'my-app'          # a package in a direct subdir of the root
  - 'packages/*'      # all packages in direct subdirs of packages/
  - 'components/**'   # all packages in subdirs of components/
  - '!**/test/**'     # exclude packages inside test directories
```

- "A `*` never matches a name beginning with a dot, so `packages/*` skips `packages/.cache`."
- The root package is always included.
- pnpm reads only `pnpm-workspace.yaml`, not the `workspaces` field of root `package.json` (a non-empty `workspaces` array without a workspace file gets a warning since v12.4.1).

**Does pnpm recommend apps/packages?** No. The docs never mention `apps`. Patterns are arbitrary; `packages/*` is the only example given.

**Local linking and publishing.** `workspace:` "will refuse to resolve to anything other than a local workspace package"; on `pnpm pack`/`pnpm publish`, `workspace:*`/`workspace:^` etc. are rewritten to the concrete version, so a published package's consumers "can use your published workspaces as any other package" — https://pnpm.io/workspaces. That is what makes a published SDK inside the workspace safe.

**Polyglot (v12, experimental).** With `python: enabled: true` in `pnpm-workspace.yaml`, one `pnpm install` resolves both graphs; pnpm reads `pyproject.toml`, writes `pylock.toml`, and gives each Python project a `.venv` — https://pnpm.io/python. "Project discovery honors `[tool.uv.workspace]` members." Members of a uv workspace can share one root `.venv` via `[tool.pnpm.python] shared-environment = true`. Both the feature and "the layout it writes may change" are flagged experimental — so do not make pnpm your Python package manager by default; treat it as optional consolidation.

---

## 4. uv workspaces (Astral)

**Shape.** Add a `tool.uv.workspace` table to a `pyproject.toml`; `members` is required, `exclude` optional, both accept globs. Every matched directory "must contain a `pyproject.toml` file", members "can be *either* applications or libraries", and "Every workspace needs a root, which is *also* a workspace member." — https://docs.astral.sh/uv/concepts/projects/workspaces/

**One lockfile, per-member runs.** "In a workspace, each package defines its own `pyproject.toml`, but the workspace shares a single lockfile"; `uv lock` covers the whole workspace, `uv run --package bird-feeder` runs inside one member — same page.

**Cross-member deps:**

```toml
[tool.uv.sources]
bird-feeder = { workspace = true }
```

"Dependencies between workspace members are editable." Root-level `tool.uv.sources` applies to every member unless a member overrides it. Same page.

**Astral's own recommended layout** is "a root project with a series of accompanying libraries … an explicit root at `albatross`, with two libraries (`bird-feeder` and `seeds`) in the `packages` directory". The framing sentence is directly on point for this repo class: "Think: a FastAPI-based web application, alongside a series of libraries that are versioned and maintained as separate Python packages, all in the same Git repository." Same page.

**Where the API and the worker go, using uv's own vocabulary:** the FastAPI app is an *application* member; a worker that imports shared Python domain code is a *library* member that both the API and the worker entrypoint depend on. uv distinguishes the two at `uv init` time (`--app` vs `--package`, https://docs.astral.sh/uv/concepts/projects/init/), and both are valid members.

**Three constraints to design around, all from the same page:**

1. "uv's workspaces enforce a single `requires-python` for the entire workspace, taking the intersection of all members' `requires-python` values."
2. "As Python does not provide dependency isolation, uv can't ensure that a package uses its declared dependencies and nothing else… uv can't ensure that packages don't import dependencies declared by another workspace member." So import discipline is a review/lint problem, not a tool-enforced one.
3. "Workspaces are *not* suited for cases in which members have conflicting requirements, or desire a separate virtual environment for each member. In this case, path dependencies are often preferable."

**Inference (not a doc claim):** because every glob match must contain a `pyproject.toml`, a polyglot repo should list Python members explicitly (`members = ["apps/api", "apps/worker", "packages/py-core"]`) rather than using `apps/*`, which would also match the TS web app.

---

## 5. Nx: conventions and non-JS stance

- Default convention is `apps/` + `packages/`, with `libs/` accepted as a synonym for `packages/` (quoted in §1) — https://nx.dev/docs/getting-started/tutorials/crafting-your-workspace
- But: "This layout is a suggestion, not a requirement. You can organize projects however you like, including flat structures, nested directories, or patterns specific to your ecosystem. For non-JS workspaces, follow the monorepo conventions in your language (e.g., Gradle multi-project builds, uv workspaces). Nx identifies projects by their `package.json` or `project.json` files, not by folder names." — same page.
- Non-JS: "Any directory with a `project.json` file is an Nx project, and its targets run any command with the same caching and orchestration as a JS task." The worked Python example is literally `packages/py-api/project.json` with `"command": "uv run pytest"`, `"options": { "cwd": "packages/py-api" }`, caching on, `inputs` including `{workspaceRoot}/uv.lock` — https://nx.dev/docs/features/multi-language-support
- Cross-language edges come from the native manifest: for Python, `dependencies = ["shared-utils"]` plus `[tool.uv.sources] shared-utils = { workspace = true }` is read as an Nx graph edge, "so they connect cross-language boundaries too, such as a deploy task that depends on both a JS frontend and a Java backend." Same page.
- "Nx adapts to your project layout rather than imposing one. Use the folder structure and dependency management conventions established by your language's ecosystem." — https://nx.dev/docs/getting-started/tutorials/crafting-your-workspace

Nx and Turborepo therefore agree on the *definition* (deployable vs shared) and disagree only on how much structure they assume. If the repo already runs pnpm + uv, Nx is additive (`nx init`, project.json per non-JS project) and does not need a `libs/` migration.

---

## 6. Where the shared TS SDK lives, and how it should expose itself

**It is a Library Package by Turborepo's definition** — shared, and not independently deployable — so it belongs under `packages/`, not `apps/` (§1). Turborepo's publishing guide is explicitly written around `./packages/math` being promoted from internal to published — https://turborepo.com/docs/guides/publishing-libraries.

**`exports` is the contract.** Node's docs: `"exports"` "provides a modern alternative to `main` allowing multiple entry points to be defined, conditional entry resolution support between environments, and **preventing any other entry points besides those defined in `exports`**"; "For new packages targeting the currently supported versions of Node.js, the `"exports"` field is recommended." Subpath patterns let one package expose a family of entry points:

```json
{ "exports": { ".": "./dist/index.js", "./features/*.js": "./src/features/*.js", "./features/private-internal/*": null } }
```

with `null` used "to exclude private subfolders from patterns", and the `"types"` condition listed as one that "should always be included first". All from https://nodejs.org/api/packages.html (sections *Package entry points*, *Subpath patterns*, *Conditional exports*).

**Turborepo's operational advice on `exports`:** prefer `exports` over `main` because it "is the more modern option", and use subpaths instead of barrel files because barrels "are difficult for compilers and bundlers to handle" — https://turborepo.com/docs/crafting-your-repository/structuring-a-repository.

**Build output shape, from Vite (the tool the frontend already uses):** library mode (`build.lib`) produces `es`+`umd` for a single entry and `es`+`cjs` for multiple entries, and the "Recommended `package.json` for your lib" is:

```json
{ "name": "my-lib", "type": "module", "files": ["dist"],
  "main": "./dist/my-lib.umd.cjs", "module": "./dist/my-lib.js",
  "exports": { ".": { "import": "./dist/my-lib.js", "require": "./dist/my-lib.umd.cjs" } } }
```

— https://vite.dev/guide/build.html#library-mode

**Publishing order** is a task-graph concern: the SDK's `build` must run before the web app's (`"dependsOn": ["^build"]`), and versioning goes through Changesets — https://turborepo.com/docs/guides/publishing-libraries.

**`packages/sdk` vs `packages/client`:** no official source rules on the name, and that is the honest answer. The only sourced constraints are (a) name it under a scope you control (`@org/...`) so it cannot collide on npm, and (b) let `exports` — not the folder name — define the public surface. A defensible convention, consistent with the sources above:

- `packages/sdk` → the published package, name `@org/sdk`, `exports["."]` = typed API client + shared types. This is the thing external consumers install.
- `packages/api-types` (or `sdk/types`) → generated OpenAPI types, if you want the web app to depend on types without pulling the whole client.
- Framework bindings, if any, as a separate `@org/sdk-react`, which is Turborepo's "framework bindings in libraries" pattern (https://turborepo.com/docs/guides/frameworks/framework-bindings).

Avoid naming it `client` if it is also imported server-side or by third parties: "client" describes a consumer (the browser), while the package's job is to be a public contract for many consumers.

---

## 7. The counter-argument: don't split yet

Primary sources, not blog posts, make the case:

- **uv:** "Workspaces are intended to facilitate the development of multiple interconnected packages within a single repository… Workspaces are *not* suited for cases in which members have conflicting requirements, or desire a separate virtual environment for each member. In this case, path dependencies are often preferable." The path-dependency alternative is shown explicitly, with the stated downside being only that `uv run --package` stops working — https://docs.astral.sh/uv/concepts/projects/workspaces/
- **Turborepo:** single-package workspaces are fully supported and keep "local and Remote Caching and task parallelization"; only genuinely package-scoped features like `app#build` stop working — https://turborepo.com/docs/guides/single-package-workspaces
- **Turborepo:** `turbo` "can be incrementally adopted in **any repository, single or multi-package**", and "you don't have to start running *all* your tasks for *all* your packages using `turbo` right away" — https://turborepo.com/docs/getting-started/add-to-existing-repository
- **Nx:** "This layout is a suggestion, not a requirement. You can organize projects however you like, including flat structures" — https://nx.dev/docs/getting-started/tutorials/crafting-your-workspace
- **pnpm:** imposes no split at all; a single root package with no `packages` field is a valid workspace — https://pnpm.io/settings#packages

**Honest cost model for the plan.** Each workspace member costs: one `package.json` or `pyproject.toml`, one entry in the graph (and in `uv.lock`/`pnpm-lock.yaml`), a name that must be unique and scoped, and a CI task. The split pays for itself the moment there are ≥2 deployables plus ≥1 imported package — which is exactly the FastAPI-app + worker + web + SDK shape. Below that threshold, a flat repo with one `package.json` and one `pyproject.toml` is cheaper and the tools still cache. So the defensible position is: adopt the split *because* this repo has four artifacts with different deploy targets, not because a template did.

---

## 8. Recommended tree (synthesis)

```text
repo/
├── apps/                        # deployables only (turbo: Application Packages)
│   ├── api/                     # FastAPI service  → pyproject.toml, Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/api/
│   ├── worker/                  # Python background worker → its own deploy unit
│   │   ├── pyproject.toml
│   │   └── src/worker/
│   └── web/                     # React + Vite (TS) → package.json, vite.config.ts
│       ├── package.json
│       └── src/
├── packages/                    # imported by others, never deployed alone
│   ├── sdk/                     # @org/sdk — published TS SDK (dist/ + exports)
│   ├── py-core/                 # Python domain lib imported by api + worker
│   ├── api-types/               # generated OpenAPI types (optional)
│   └── tsconfig/                # shared tsconfig base (tooling package)
├── deploy/                      # compose files, migrations runner, IaC
│   ├── compose.yaml
│   └── Dockerfile.api
├── docs/
├── package.json                 # private root, scripts → turbo
├── pnpm-workspace.yaml          # packages: apps/*, packages/*
├── turbo.json                   # build/test/lint + (opt-in) experimentalPythonWorkspaces
├── pyproject.toml               # uv workspace root: [tool.uv.workspace] members = [...]
├── uv.lock
└── .python-version
```

Notes that follow from the sources above, not from preference:

- `apps/api`, `apps/worker`, `apps/web` are all deployables, so all three live in `apps/` (§1, §2).
- `packages/py-core` is imported by two apps → a uv *library* member; `apps/api` and `apps/worker` are *application* members (§4).
- List Python members explicitly; do not use `apps/*` as a uv glob, or uv will demand a `pyproject.toml` in `apps/web` (§4).
- Keep `deploy/` outside `apps/` and `packages/` so neither pnpm nor uv treats it as a member — neither tool's globs reach it (§2, §3).
- If Turborepo orchestrates Python, either use the experimental native uv path (`experimentalPythonWorkspaces` + `[tool.turbo] name` + root `uv.lock`) or the stable shim path (a `package.json` per Python project whose scripts call `uv run`), and in the shim case keep the `package.json` dependency edge in sync with the uv dependency edge by hand (§2).

---

## Citations

1. Turborepo — *Structuring a repository* — https://turborepo.com/docs/crafting-your-repository/structuring-a-repository
2. Turborepo — *Package types* — https://turborepo.com/docs/core-concepts/package-types
3. Turborepo — *Multi-language support* — https://turborepo.com/docs/guides/multi-language
4. Turborepo — *Python (Experimental)* — https://turborepo.com/docs/guides/tools/python
5. Turborepo — *Single-package workspaces* — https://turborepo.com/docs/guides/single-package-workspaces
6. Turborepo — *Add to an existing repository* — https://turborepo.com/docs/getting-started/add-to-existing-repository
7. Turborepo — *Publishing libraries* — https://turborepo.com/docs/guides/publishing-libraries
8. Turborepo — *Framework bindings in libraries* — https://turborepo.com/docs/guides/frameworks/framework-bindings
9. pnpm — *Workspace* — https://pnpm.io/workspaces
10. pnpm — *Settings (pnpm-workspace.yaml), § packages* — https://pnpm.io/settings#packages
11. pnpm — *Python dependencies* (v12, experimental) — https://pnpm.io/python
12. uv — *Using workspaces* — https://docs.astral.sh/uv/concepts/projects/workspaces/
13. uv — *Creating projects* (applications vs libraries) — https://docs.astral.sh/uv/concepts/projects/init/
14. Nx — *Crafting Your Nx Workspace* — https://nx.dev/docs/getting-started/tutorials/crafting-your-workspace
15. Nx — *Multi-Language Support* — https://nx.dev/docs/features/multi-language-support
16. Node.js — *Modules: Packages* (entry points, subpath patterns, conditional exports) — https://nodejs.org/api/packages.html
17. Vite — *Building for Production*, Library Mode — https://vite.dev/guide/build.html#library-mode
18. monorepo.tools (Nx-maintained, **[secondary]**) — https://monorepo.tools/
