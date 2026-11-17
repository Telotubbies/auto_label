# Roboflow parity research — shared brief

Owner goal: LabelDesk v2 must reach **feature and UX parity** with Roboflow, presented
in LabelDesk's own design language, names, copy and icons. This folder holds the
evidence base; `PARITY.md` (written by the lead) turns it into a HAVE/PARTIAL/MISSING
matrix and a build plan.

Research date: 2026-11-17. Read-only lane: no application code, no git writes,
`board.md` untouched.

## Hard rules for every area file

1. **Own words only.** Never copy Roboflow sentences, feature names used as UI copy,
   logos, illustrations or icons. Name a Roboflow feature only as a parenthetical
   source label, e.g. "one-click object isolation (RF: *Smart Select*)". Every screen
   name, button label and microcopy you propose must be new.
2. **One feature = one ID.** `<area>.<n>` (e.g. `F3.4`). IDs are stable; the parity
   matrix cites them.
3. **Every feature says how it works for the user**, not just that it exists:
   what they do, the click-by-click flow with the screen each step happens on, and
   the empty / loading / error states that flow passes through.
4. **Every feature cites at least one URL** you actually fetched. Items known only
   from a docs sitemap title go in a "Title-only" section and are never presented as
   confirmed detail.
5. No marketing adjectives. "Why it is easy" is one or two concrete sentences.

## Required shape of an area file

```markdown
# Area <n> — <name>

Method: <what you fetched, how many pages, date>. Not opened: <list>.

## <Feature group>

### F<n>.<k> <Feature name in our words> (RF: <label>)
- **What the user does:** ...
- **Flow:** 1. ... 2. ... (name the screen at each step; write `[empty]`, `[loading]`,
  `[error: ...]` inline where the user would meet them)
- **Why it is easy:** ...
- **Gates:** plan/role/credit limits, if any
- **Sources:** URL, URL
- **LabelDesk hook points:** at most 3 repo paths you actually opened (no verdicts)

## Title-only / unverified
...

## Coverage gaps and what to check next
...
```

Target 250–450 lines per file, dense bullets over prose. Thai text is not needed in
area files; the owner summary is Thai and lives in the parity report.

## Where LabelDesk lives today (branch `feat/labeldesk-v2`)

Backend: `apps/backend/app/{routers,services,models,schema,handlers,adapters,streams}`.
Frontend: `apps/frontend/src/{features,routes,components,lib}`.
`apps/api/` and `apps/web/` are stale untracked copies from before the rename — ignore them.

Project navigation: `upload`, `browse`, `videos`, `versions`, `insights`, `suspects`,
`model-insights`, `classes`, `annotate`, `qa`, `train`, `anomaly`, `models`, `deploy`,
`streams`, `lineage`, `dashboards`, `stream-analytics`, `settings`.
Editor: `/:ws/:project/images/:imageId`.
Workspace navigation: home, `models`, `deployments`, `activity`, `audit`, `admin`,
`playground`, `settings/*`.
Backend routers: admin, alerts, anomaly, audit, auth, connectors, dashboards,
deployments, flags, images, insights(+lineage, models), labeling, ocr, ops,
playground, privacy, projects, rbac, registry, remote, streams, training, versions,
videos, webhooks, workspaces.

## Reusable prior research in this repo

- `research_notes/ฟีเจอร์ที่ยังขาดเทียบคู่แข่ง/roboflow_features.md` — cited RF checklist
- `research_notes/ฟีเจอร์ที่ยังขาดเทียบคู่แข่ง/competitor_features.md`
- `research_notes/UX UI และฟีเจอร์ SaaS Computer Vision/annotation_editor_ux.md`
- `research_notes/UX UI และฟีเจอร์ SaaS Computer Vision/platform_ux_dashboards.md`
- `research_notes/ฟีเจอร์ SaaS ด้าน Computer Vision/*.md` (data, training, inference, annotation)
- `reports/*.md` — synthesized tiers (M/S/D) for the same topics
- `.superpowers/sdd/2026-10-31-labeldesk-v2/gap-audit.md` — earlier code-vs-report diff

## Fetching Roboflow

- `https://docs.roboflow.com/llms.txt` for the page index; append `.md` to any docs
  URL for the markdown version.
- Also useful: `https://blog.roboflow.com/`, `https://roboflow.com/pricing`,
  `https://roboflow.com/credits`, changelog under `docs.roboflow.com/reference/changelog/`.
- Public pages only. No login, no scraping of the app UI, no screenshots.
