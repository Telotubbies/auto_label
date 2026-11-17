# LabelDesk engineering and design standards

Binding for every contributor and agent. Reviewers check each item; a violation is a review finding.

## 1. General

- Read the code around you first and match its naming, comment density and idiom.
- One responsibility per file. Files that grow past ~400 lines get split along a real seam.
- The layout rule: deployable code in `apps/`, importable code in `packages/`, the offline ML pipeline in `ml/` ([ADR 0003](adr/0003-repository-layout-v2.md)).
- YAGNI: build what the brief asks, nothing speculative.
- No secrets, tokens or absolute machine paths in code or tests.
- Every change ships with tests; the full suite stays green; test output stays free of new warnings.

## 2. Python (apps/backend, apps/worker)

- Python 3.11, type hints on every public function; `from __future__` not required.
- Format and lint: `ruff format` + `ruff check` (rules: E, F, I, B, UP, SIM). Line length 120.
- FastAPI: routers stay thin — validation in Pydantic models, logic in `services/` or `adapters/`.
- Every workspace-scoped query filters by `workspace_id`; trained models resolve via `resolve(ref, db, workspace_id=...)`.
- Errors shown to users: our own `ValueError`/`HTTPException` messages only; internals go to `log.exception`.
- GPU work goes through `app.gpu.scheduler`; never load a model outside a lease.
- DB schema: `create_all` + `ensure_columns`; never drop columns.
- Tests: pytest, one module per feature, env set before importing `app`, fakes for GPU/network, `@pytest.mark.gpu` / `slow` for real hardware.

## 3. TypeScript / React (apps/frontend)

- TS `strict`; no `any` except at untyped library edges with a comment.
- Format and lint: Biome (`biome check`), 2-space indent, single quotes.
- Data fetching with TanStack Query; API calls only through `src/lib/api.ts`; types in `src/lib/types.ts`.
- Components: function components, composition over boolean props, colocate feature code in `src/features/<area>/`.
- No hard-coded colours, sizes or fonts in components — use Tailwind classes backed by tokens.
- `npm run build` must pass with no new TS errors.

## 4. API conventions

- REST under `/api/ws/{ws}/projects/{project}/…`; nouns plural; JSON snake_case on the wire for new endpoints, existing camelCase payloads keep their shape.
- 400 validation, 401 auth, 403 role, 404 missing or other tenant, 409 state conflict, 402 credits, 503 GPU busy / model unavailable.
- Long work runs as a job (`jobs` table) with progress; endpoints return quickly.

## 5. Design system

- Colour: Material dynamic colour from a seed (HCT) → CSS variables; brand colour never doubles as a class colour; class colours from Okabe-Ito → Glasbey; heatmaps viridis.
- Liquid Glass only on chrome (nav, top bar, floating toolbars, dialogs, command palette, job tray, overlay chips). Content surfaces (canvas, tables, charts, video) stay solid.
- Solid fallback under `prefers-reduced-transparency`, the in-app "Reduce transparency" setting, and when `backdrop-filter` is unsupported.
- Type: IBM Plex Sans + Anuphan (Thai), Thai line-height 1.6, never truncate Thai with `slice()`.
- Motion: opacity/transform only, 150–600 ms, never animate blur, disabled under `prefers-reduced-motion`.
- Empty, loading (skeleton for page loads), error and long-job (job tray with progress) states for every screen.

## 6. Accessibility (WCAG 2.2 AA)

- Text contrast ≥ 4.5:1, large text and controls/focus ≥ 3:1 — verified with axe; `color-contrast` "incomplete" counts as fail until pixel-sampled.
- Keyboard operable everywhere; visible focus never hidden by sticky UI; targets ≥ 24×24 px; click alternative for every drag.
- Semantic landmarks and heading order; charts have a table view.

## 7. Process

- Work in your own worktree/branch; never edit the main checkout or shared branch.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).
- UI tasks load the `impeccable` skill and attach light/dark/375 px screenshots.
