# Inference hub: UI QA (T-1021)

The QA pass behind this card: the hub at light, dark and 375 px, every state in PLAN §4.2 that the
fixtures can produce, one screenshot per checkpoint, and the measurements that a screenshot cannot
prove. Findings are filed with `file:line`, severity and the card that owns the fix. No production
code changed: the card's own two node guards are in `apps/frontend/tests/inference-hub.test.mjs`.

| Field | Value |
| --- | --- |
| Run date | 2026-11-18 |
| Base | `feat/labeldesk-v2` at `bc3c4e5` (branch `t/1021`) |
| Flag | `task_inference` on for the demo workspace (`LD_FLAGS_ON=task_inference`) |
| Data | Seeded demo workspace `labeldesk-demo` (`LD_SEED_DEMO=1`), no GPU, no install, no download, no network |
| Stub | `page.route('**/api/ws/*/inference/**')`: hosts, engines, models, segmentation, plans, jobs. `catalog` and `estimate` stayed real, so the calculator's numbers are the endpoint's own |
| Verdict | No Critical findings. 9 Important, 5 Minor |

## 1. Method

The app ran for real: `uvicorn app.main:app` with the demo seed on a free port and the Vite dev
server on another, per `docs/verify/VERIFY.md`. Playwright drove Chromium at 1440 × 900 (light and
dark, `colorScheme` plus `ld:theme`) and 375 × 812 (light; the four tab shots use a 2400 px canvas
so one image holds the whole surface). Inference routes were stubbed from one fixture file built
from the API's own payloads; login, flags, projects and the project registry were the real API.

The uncommitted driver, the fixtures and the raw measurements live in
`B:/02_Projects/ld-tmp/verify/T-1021/` (`qa.mjs`, `fixtures.json`, `qa-evidence.json`); the card's
file list does not include a spec, and T-1020 owns `e2e/inference-hub.spec.ts`.

Observed, not assumed: console errors per combination, both scroll containers at 375 px, the
install button's box in the sheet, focus order with 70 tabs, the dialog's first and last tab stops,
the computed colours behind the log, and the reduced-transparency fallback.

## 2. Coverage

### 2.1 Theme and width, eight checkpoints each

Every cell below is a file in `ui/`: `<theme>-<width>-<nn>-<checkpoint>.png`.

| # | Checkpoint | light-1440 | dark-1440 | light-375 |
| --- | --- | --- | --- | --- |
| 01 | Engines, job card, blocked row, footer | `light-1440-01-engines.png` | `dark-1440-01-engines.png` | `light-375-01-engines.png` |
| 02 | Models, assets panel, filters, table | `light-1440-02-models.png` | `dark-1440-02-models.png` | `light-375-02-models.png` |
| 03 | Calculator, result, assumptions | `light-1440-03-calculator.png` | `dark-1440-03-calculator.png` | `light-375-03-calculator.png` |
| 04 | Segmentation, project picked | `light-1440-04-segmentation.png` | `dark-1440-04-segmentation.png` | `light-375-04-segmentation.png` |
| 05 | Sheet: install plan, acknowledgement unchecked | `light-1440-05-sheet-install.png` | `dark-1440-05-sheet-install.png` | `light-375-05-sheet-install.png` |
| 06 | Sheet: download, disk after | `light-1440-06-sheet-download.png` | `dark-1440-06-sheet-download.png` | `light-375-06-sheet-download.png` |
| 07 | Sheet: install log | `light-1440-07-sheet-log.png` | `dark-1440-07-sheet-log.png` | `light-375-07-sheet-log.png` |
| 08 | Job card on its own | `light-1440-08-job-card.png` | `dark-1440-08-job-card.png` | `light-375-08-job-card.png` |

### 2.2 States, once each

| State | Evidence | What it shows |
| --- | --- | --- |
| Empty | `state-01-empty.png` | `No host has reported` in the picker, "Start a worker, then pick it here." and the worker command |
| Loading | `state-02-loading.png` | Host-picker skeleton and five `aria-busy` engine rows |
| Error | `state-03-error.png` | "Engines did not load for this host." + Retry |
| Offline host | `state-04-offline-host.png` | `train-box (offline)` in the picker, "This host is offline.", plan disabled |
| Blocked engine | `state-05-blocked-engine.png` | TensorRT-LLM: disabled checkbox, lock, "Needs driver 580.65+; host reports 550.54." |
| Gated model | `state-06-gated-model-row.png`, `state-06-gated-model.png` | `Gated` chip; the sheet replaces Download with the `HF_TOKEN` sentence |
| Fails verdict | `state-07-fails-verdict.png` | "Does not fit" + "Does not fit: 129.0 GB short." |
| Low disk | `state-08-low-disk.png`, `state-09-low-disk-sheet.png` | The assets warning; "Needs 6.5 GB, host has 4.0 GB free." and no Download button |
| Calculator error | `state-10-calculator-error.png` | "KV heads (4) must divide by tensor parallel (3)." inline on the field |
| Downloading | `state-11-model-downloading.png` | Row reads `Downloading 43%`; the installed, gated and does-not-fit rows beside it |
| Install failed | `state-12-install-failed.png` | "Install failed: pip exited 1: …" + Copy log |
| Uninstall | `state-13-uninstall-sheet.png` | Engine, version, host, "Shared system packages are not touched." |
| Remove model | `state-14-remove-sheet.png` | Model, variant, host, "This frees 2.3 GB." |

## 3. Measurements

| Check | Result |
| --- | --- |
| Console errors, light-1440 / dark-1440 / light-375 | 0 / 0 / 0. The error state's two 500s are the injected failure, not a defect |
| Document scroll width at 375, all four tabs | 375 = 375 |
| Main scroller at 375, before a result | 375 = 375 on all four tabs |
| Main scroller at 375, after `Show estimate` | **425 vs 375**: 50 px of horizontal scroll (finding 1) |
| Tables at 375 | Engines sticky, catalogue sticky, assets panel **not sticky** (finding 7) |
| Tab bar → select at 375 | Tab buttons hidden, `Inference section` select visible |
| Calculator at 375 | One column, 343 px, form above results behind `Show estimate` |
| Install sheet at 375 | 846 px tall on an 812 px viewport; the acknowledgement sits at y=767 and `Install` at y=817, below the fold (finding 2) |
| Download and log sheets at 375 | Both fit the 812 px viewport with their footer and `Copy log` visible |
| Log text | 12 px, 17.15:1 in light, 12.67:1 in dark on `--card` (AA needs 4.5) |
| Focus ring on glass | 2 px solid `--ring`, `outline-offset: 2px`, measured on a tab inside `.glass` |
| Tabs in the tab order | Host → Engines → Models → Calculator → Segmentation → job card → rows → row menu; a disabled `Review install plan` is correctly skipped |
| Row menu, sheet close, acknowledgement | Reachable: `Actions for Ollama`, `Close`, `I understand this installs software on gpu-demo` |
| Sheet focus | Not moved into the dialog on open (`Review install plan` keeps focus); leaves the dialog after four stops; Escape closes it and focus stays on the page (finding 3) |
| `prefers-reduced-transparency` | `index.css:161` media query and `index.css:165` attribute both swap to `--glass-solid`; measured `background-image: none`, `backdrop-filter: none` |
| New hex, `text-[`, inline font size in `features/inference/**` | 0 hits (node guard) |
| Copy | Sentence case; units on every number ("3.2 GB", "132 tok/s", "1887 ms", "64%"); "estimate" on the decode figure and "Estimate, not a benchmark." in the assumptions panel; no competitor name, logo or tagline |
| Glass placement | `Glass` on the tab bar, the sticky footer bar, the filter bar, the project picker and the three sheets; the engines, models and assets tables, the result card and the log block stay solid on `Card` / `bg-card` |

## 4. Findings

| # | Severity | Finding | File:line | Owner |
| --- | --- | --- | --- | --- |
| 1 | Important | At 375 px the calculator's results table widens the grid track, so the form and the results scroll sideways once an estimate is shown | `features/inference/CalculatorTab.tsx:120`, `:282` | T-1005 |
| 2 | Important | The install sheet is taller than a 375 px viewport: the acknowledgement and `Install` sit below the fold behind a fixed overlay | `features/inference/EngineSheet.tsx:75`, `components/ui.tsx:104` | T-1007 |
| 3 | Important | Sheets do not trap focus and do not restore it to the trigger; PLAN §4.4 requires both | `components/ui.tsx:96-112` | shared `Modal`; file a `fix/*` or fold into T-489 |
| 4 | Important | The tab bar is buttons, not a tablist: no `role="tab"`, no `aria-selected`; the active tab is colour plus a 2 px underline | `components/ui.tsx:53-62`, `features/inference/InferenceHub.tsx:74-85` | T-1000 shell / shared `Tabs` |
| 5 | Important | When `/hosts` fails the picker says "No host has reported" instead of "Hosts did not load." + Retry | `features/inference/InferenceHub.tsx:64` | T-1001 |
| 6 | Important | The low-disk rule reads only the free share, so 28 GB free on a 1.8 TB disk is labelled "Under 10% free"; PLAN §9 alerts on "< 10 GB or < 10%" | `features/inference/assets.ts:40-43` | T-1013 |
| 7 | Important | The assets table is the one table at 375 without a sticky first column, so the model name scrolls away | `features/inference/AssetsPanel.tsx:153`, `:165` | T-1013 |
| 8 | Important | The low-disk remedy names `LD_MODELS_MAX_GB`, which owner decision §12.4 removed from v1 ("No GB cap setting in v1"); the backticks also render literally | `features/inference/assets.ts:18` | T-1013 |
| 9 | Minor | The job card's log tail clips a half line (five lines at `leading-5` in `max-h-24`) | `features/inference/InstallProgress.tsx:135` | T-1009 |
| 10 | Minor | "No engine job is running." renders above the empty and loading states of the Engines tab | `features/inference/InstallProgress.tsx:112`, `EnginesTab.tsx:118` | T-1009 |
| 11 | Minor | The download sheet prints a negative projection as a stat ("Disk after −2.5 GB") | `features/inference/ModelSheet.tsx:110-116` | T-1012 |
| 12 | Minor | Segmentation reasons embed absolute host paths, rendered in the card ("… (B:\02_Projects\ld-worktrees\labeldesk-ml\yolo26_ppe\models\pretrained has none)") | `apps/backend/app/services/inference_segmentation.py:164`, `:176`, `:191`; rendered at `SegmentationTab.tsx:87` | T-1014 |
| 13 | Minor | "Read the setup notes" points at the repository README until the hub's own page ships | `features/inference/segRows.ts:23` | T-1022 |
| 14 | Important | Owner decision §12.5 says any member may open the Calculator; the rail entry is `owner`/`admin` and `/catalog` is admin-only, so a member gets "GPU list unavailable" and no presets | `lib/nav/visibility.ts:22`, `apps/backend/app/routers/inference.py:44-47` (route `:82` has no admin gate, so the split is deliberate but unfinished) | T-1000 + T-1005, PM ruling |

Notes on the fixes, for the owning cards:

- **1** needs `min-w-0` on the two grid children (or `w-full min-w-0` on the results card) so the
  table keeps its own `overflow-x-auto` instead of stretching the track.
- **2** needs the sheet's height arithmetic to subtract the dialog's `my-8` and the title block, or
  the footer pinned inside the dialog instead of pushed by `mt-auto`.
- **3** is one `Modal` fix for the whole app: move focus to the dialog on open, cycle within it,
  restore to the trigger on close.
- **6** should be `free < 10 || free / total < 0.1`, and **8**'s remedy should name what v1 offers:
  remove a model from the panel.
- **12** keeps "Missing checkpoint" and drops the parenthesised path, or shows `LD_SAM_ROOT` only.
- **14** is a decision, not a defect: either the rail gains a Calculator-only entry for members and
  `/catalog` loses its admin gate for the preset list, or §12.5 is amended. `POST /estimate` already
  has no admin gate and the calculator already renders "GPU list unavailable" when `/catalog` 403s,
  so the split exists in code and nothing routes to it.

## 5. What this pass did not observe

- **Permission** (non-admin 404, rail hidden): the access rules are T-1000's and the labeler denial is
  T-1020's spec; this pass kept the admin session. Finding 14 was verified by reading the gate and the
  rail, not by a member session — the demo seed creates the admin only.
- **Real hardware**: no worker inventory came from a real GPU. Every host, engine, model and job in
  the screenshots is a fixture built from the API's own catalogue payloads. Real Ollama, vLLM, a
  download and a checkpoint were never started, per PLAN §12.3.
- **Engine "Install failed" *inside* the sheet** (the plan-endpoint error) and the model's `Verifying`,
  `Checksum failed` and `Stopped` rows: the job-status renderer is the same one `state-12` exercises,
  and the row map is T-1012's own test surface.
- **OS-level reduced transparency**: Chromium cannot emulate the media feature. Both shipped
  mechanisms were verified instead: the media query in `index.css:161` and the app's toggle at
  `index.css:165`, measured through `data-reduce-transparency`.
- **Screen-reader announcement** of the tab change and of the job progress: only the DOM attributes
  were inspected; no screen reader ran.
- **Safari and Firefox**: Chromium only.
