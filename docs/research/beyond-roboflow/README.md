# Beyond Roboflow — shared brief (2026-11-17)

Owner directive: LabelDesk v2 already has a Roboflow parity plan
(`docs/research/roboflow-parity/PARITY.md`, 334 features). Do **not** re-research those.
This folder looks for the features that parity with Roboflow will *not* give us: what
CVAT, Labelbox, Encord, Ultralytics, Landing AI, NVIDIA, Edge Impulse, FiftyOne,
enterprise buyers and the Thai market expect in 2025–2026.

Read-only lane: no application code, no git writes, no branch or file outside this
folder and `.superpowers/sdd/2026-10-31-labeldesk-v2/`. Never kill a process you did
not start.

## Sources (one file per group)

| File | Group |
| --- | --- |
| `01-annotation-platforms.md` | CVAT, Label Studio, Labelbox, SuperAnnotate, V7 Darwin, Encord, Dataloop, Kili |
| `02-training-mlops.md` | Ultralytics HUB, Landing AI / LandingLens, HF AutoTrain, W&B, ClearML, FiftyOne |
| `03-edge-industrial.md` | NVIDIA Metropolis / DeepStream / TAO, Edge Impulse, Viso.ai, Cognex / Keyence-style inspection, Axis / Milestone video analytics |
| `04-vlm-foundation.md` | open-vocabulary detection, SAM 3 family, VLM QA / auto-label, agentic labeling, synthetic data, active learning, embedding curation (2025–2026) |
| `05-enterprise-table-stakes.md` | SSO/SCIM, audit, data residency, BYO storage, PDPA/GDPR, usage billing, status page, onboarding/help centre, i18n (Thai first) |
| `06-repo-research-thai-market.md` | this repo's `reports/` and `research/notes/`, plus Thai use cases (factories, PPE, retail, agriculture) |

## Hard rules

1. **Own words only.** Never copy a competitor's sentence, UI label, logo, illustration
   or icon. A competitor name appears only as a source label, e.g. "text-prompted
   masking (OF: *Magic Mask*)" — and our own name for the feature is the heading.
2. **No invented sources.** Every feature cites at least one URL you actually fetched
   in this session. If you only saw a title in a sitemap or a search result, put it in
   `## Title-only / unverified` and never present it as confirmed detail.
3. **Feature IDs are stable.** `<G>.<n>` where `<G>` is `1`–`6` for the file, e.g. `G4.7`.
   Never renumber after writing.
4. **Say how the user works, not that the feature exists.** What they do, click by
   click, which screen each step happens on, and the `[empty]` / `[loading]` /
   `[error: ...]` states that flow passes through.
5. No marketing adjectives. "Why it is easy" is one or two concrete sentences.
6. **Dedupe against parity first.** `PARITY.md` (334 rows) already owns upload,
   folders, the editor, versions/augmentation, training, deploy/inference, workflows,
   workspace admin, billing, API keys, audit log screens, tagging, splits, health check,
   dedupe/clustering, query filters, export formats. If your candidate is already one of
   those, either drop it or put it in `## Already covered by PARITY.md` with the row ID
   (`e.g. 1-F4.3`) and **no** feature card. A feature only counts if it adds a capability,
   a surface or a control parity does not describe.

## Feature card shape (required)

```markdown
### G<file>.<n> <Our name for the feature> (<source>)
- **What the user does:** one or two sentences, concrete.
- **Who uses it:** role + situation, not a persona essay.
- **Flow:** 1. … 2. … (name the screen at each step; `[empty]`, `[loading]`,
  `[error: …]` inline where the user meets them)
- **Why it is easy:** concrete, no adjectives.
- **Products with it:** names + the URL that proves it.
- **Why it matters for LabelDesk:** one or two sentences tied to our buyer or our risk.
- **LabelDesk code evidence:** repo paths + line numbers you actually opened, or
  `none found (searched <patterns>)`. This field is mandatory.
- **Suggested status:** HAVE | PARTIAL | MISSING, one clause of justification.
- **Suggested priority / size:** Must | Should | Could, and S | M | L.
```

Status and priority definitions are PARITY.md's, reused verbatim in meaning:
HAVE = flow works end to end today; PARTIAL = real code but a documented piece is
missing; MISSING = no implementation. Must = a buyer evaluates the product on it;
Should = a gap buyers notice in a trial; Could = differentiator or long tail.
S ≤ 1 day, M 2–5 days, L > 1 week of one engineer.

## Where the code is (`feat/labeldesk-v2`, `fe8ef1a`)

- Backend routers: `apps/backend/app/routers/` (admin, alerts, anomaly, audit, auth,
  connectors, dashboards, deployments, devapi, flags, images, insights, insights_lineage,
  insights_models, labeling, ocr, ops, playground, privacy, projects, rbac, registry,
  remote, streams, training, versions, videos, webhooks, workflows, workspaces).
- Backend services: `apps/backend/app/services/` — note `active_learning.py`,
  `embeddings.py`, `insights_embedding.py`, `drift.py`, `faceblur.py`, `retention.py`,
  `erasure.py`, `track.py`, `tiling.py`, `quality.py`, `labeler_stats.py`,
  `workflows.py`, `workflow_runner.py`.
- Adapters: `apps/backend/app/adapters/` — `sam3_ad.py`, `vlm_ad.py`, `hf_ad.py`,
  `rfdetr_ad.py`, `ultralytics_ad.py`, `tensorrt_ad.py`, `refine.py`, `catalog.py`.
- Top-level `app/`: `oidc.py`, `totp.py`, `apikeys.py`, `rbac.py`, `ratelimit.py`,
  `superadmin.py`, `gpu.py`, `jobs.py`.
- Frontend: `apps/frontend/src/features/{editor,project,workspace,settings,streams,
  governance,insights,lineage,evaluation,playground,auth,landing,dashboards}`,
  `src/lib/{api,nav}`, `src/routes/`. There is no i18n layer and no Thai string in the UI.
- Standalone experiment: `sam3_auto_label/` (untracked) is a working SAM 3.1
  text-prompt PPE pipeline with checkpoint/resume and 11 export formats — not wired
  into the app. Treat it as evidence of capability, not as a shipped feature.

Ignore `apps/api/` and `apps/web/` (stale pre-rename copies) and never index
`sam3_auto_label/sam3_venv/` (a 70k-file virtualenv that will blow up your context).

## Output budget

250–450 lines per file, dense bullets. Thai text is not needed in these files; the
owner summary and `BEYOND.md` are written by the lead.
