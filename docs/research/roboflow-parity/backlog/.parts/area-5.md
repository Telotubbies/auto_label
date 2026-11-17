# Part 5 — Area 5 Train and models

Gap rows: 39 (28 PARTIAL, 11 MISSING) · Cards: 46 · Hours: 129.5

Hours are attributed once, to the card's primary row; a row that only shares another row's card shows `—` and that card's hours appear on its primary row. The 15 HAVE rows are protected by the area guard (`T-006`) and carry no card.

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 5-F5.1 | HAVE | — (guard T-006; filter/sort gap cell lands in T-263) | — | — | — |
| 5-F5.2 | HAVE | — (guard T-006; version-page trainings are area 4's T-221) | — | — | — |
| 5-F5.3 | PARTIAL | T-257, T-258 | C | M | 6 |
| 5-F5.4 | PARTIAL | T-268 (+ area 6 deploy hub for the template chooser) | B | S | — |
| 5-F5.5 | MISSING | T-269, T-270, T-271, T-272 | B | L | 11.5 |
| 5-F5.6 | PARTIAL | T-260, T-261 | B | M | 6 |
| 5-F5.7 | PARTIAL | T-250, T-251 | B | M | 5.5 |
| 5-F5.8 | PARTIAL | T-259 | B | S | 3 |
| 5-F5.9 | PARTIAL | T-255, T-256 | B | M | 6 |
| 5-F5.10 | PARTIAL | T-253 | B | S | 2.5 |
| 5-F5.11 | PARTIAL | T-252, T-254 | B | S | 6 |
| 5-F5.12 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.13 | MISSING | T-274, T-275, T-276 | B | L | 7.5 |
| 5-F5.14 | MISSING | T-273 | B | M | 2.5 |
| 5-F5.15 | PARTIAL | T-263 | B | S | 3 |
| 5-F5.16 | HAVE | — (guard T-006; the search-band gap cell lands in T-272) | — | — | — |
| 5-F5.17 | PARTIAL | T-264 | B | S | 3 |
| 5-F5.18 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.19 | PARTIAL | T-266 | B | S | 2.5 |
| 5-F5.20 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.21 | PARTIAL | T-277 | B | M | 3 |
| 5-F5.22 | PARTIAL | T-278 | B | S | 2.5 |
| 5-F5.23 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.24 | PARTIAL | T-279, T-280 | B | M | 5.5 |
| 5-F5.25 | PARTIAL | T-281, T-282 | B | M | 5.5 |
| 5-F5.26 | MISSING | T-263 | B | S | — |
| 5-F5.27 | PARTIAL | T-283, T-284 | B | M | 6 |
| 5-F5.28 | PARTIAL | T-285, T-286 | B | M | 5.5 |
| 5-F5.29 | MISSING | T-290 | B | S | 2 |
| 5-F5.30 | MISSING | T-292, T-293, T-294, T-295 | B | L | 11.5 |
| 5-F5.31 | MISSING | T-288, T-289 | B | M | 5.5 |
| 5-F5.32 | MISSING | T-291 | C | M | 2.5 |
| 5-F5.33 | PARTIAL | T-268 | B | S | 3 |
| 5-F5.34 | MISSING | T-268 | B | S | — |
| 5-F5.35 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.36 | MISSING | T-271, T-272, T-257 | B | S | — |
| 5-F5.37 | PARTIAL | T-267 | B | S | 3 |
| 5-F5.38 | HAVE | — (guard T-006; deploy-page repeat is area 6) | — | — | — |
| 5-F5.39 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.40 | PARTIAL | T-262 | B | S | 3 |
| 5-F5.41 | PARTIAL | T-262 | B | S | — |
| 5-F5.42 | PARTIAL | T-262 | B | S | — |
| 5-F5.43 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.44 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.45 | PARTIAL | T-268 | B | S | — |
| 5-F5.46 | PARTIAL | T-265 | B | S | 3 |
| 5-F5.47 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.48 | PARTIAL | T-263 | B | S | — |
| 5-F5.49 | PARTIAL | T-262 | B | S | — |
| 5-F5.50 | HAVE | — (guard T-006) | — | — | — |
| 5-F5.51 | MISSING | T-254 | B | S | — |
| 5-F5.52 | HAVE | — (guard T-006; its gap cell is not planned — see Judgment calls) | — | — | — |
| 5-F5.53 | PARTIAL | T-287 | B | S | 3 |
| 5-F5.54 | PARTIAL | T-287 | B | S | — |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/routers/training.py` (owner T-250) | T-250, T-251, T-252, T-253, T-256, T-257, T-259, T-260, T-262, T-263, T-265, T-266, T-268, T-270, T-271, T-277, T-279, T-288, T-291 |
| `apps/backend/app/handlers/training.py` (owner T-260) | T-253, T-256, T-258, T-259, T-260, T-263, T-264, T-265, T-266, T-268, T-270, T-287, T-288, T-290 |
| `apps/backend/app/models/training.py` (owner T-251) | T-251, T-253, T-257, T-265, T-268, T-270, T-277, T-288, T-292, T-293 |
| `apps/backend/app/schema/training.py` | T-253, T-257, T-265, T-268, T-271, T-277, T-288 |
| `apps/backend/app/models/__init__.py` | T-251, T-268, T-270, T-292, T-293 |
| `apps/backend/app/routers/__init__.py` | T-292 |
| `apps/backend/app/handlers/__init__.py` | T-293 |
| `apps/backend/app/config.py` | T-274, T-283, T-287, T-288, T-293 |
| `apps/backend/app/worker.py` | T-275 |
| `apps/backend/app/services/train_quote.py` (owner T-252) | T-252, T-260, T-265, T-269 |
| `apps/backend/app/services/train_catalog.py` (owner T-250) | T-250, T-252, T-269 |
| `apps/backend/app/services/train_preflight.py` (owner T-262) | T-262, T-269, T-273 |
| `apps/backend/app/services/train_recipe.py` (owner T-256) | T-256, T-259 |
| `apps/backend/app/services/architecture_search.py` (owner T-269) | T-269, T-270 |
| `apps/backend/app/services/quick_model.py` (owner T-274) | T-274, T-275 |
| `apps/backend/app/services/model_refs.py` (owner T-268) | T-268, T-271 |
| `apps/backend/app/services/weight_upload.py` (owner T-288) | T-288, T-290 |
| `apps/backend/app/services/evaluate.py` | T-263, T-283, T-285, T-287 |
| `apps/backend/app/services/insights.py` | T-278, T-281, T-283 |
| `apps/backend/app/services/insights_eval.py` | T-278, T-279, T-281 |
| `apps/backend/app/services/deployments.py` (owner T-267) | T-267, T-295 |
| `apps/backend/app/services/eval_checks.py` (owner T-292) | T-292, T-295 |
| `apps/backend/app/services/train_failure.py` (owner T-263) | T-263, T-266 |
| `apps/backend/app/adapters/catalog.py` | T-277 |
| `apps/backend/app/adapters/base.py` | T-277 |
| `apps/backend/app/adapters/ultralytics_ad.py` | T-256, T-259 |
| `apps/backend/app/routers/workspaces.py` | T-257, T-258 |
| `apps/backend/app/routers/projects.py` | T-264 |
| `apps/backend/app/routers/insights.py` | T-281 |
| `apps/backend/app/routers/insights_models.py` (owner T-283) | T-278, T-283 |
| `apps/backend/app/routers/deployments.py` | T-295 |
| `apps/backend/app/routers/regression_evals.py` (owner T-292) | T-292, T-295 |
| `apps/frontend/src/features/project/Train.tsx` (owner T-255) | T-254, T-256, T-259, T-261, T-286 |
| `apps/frontend/src/features/project/Models.tsx` (owner T-263) | T-265, T-267, T-268, T-272, T-273, T-276, T-280, T-286, T-289, T-291, T-294 |
| `apps/frontend/src/features/project/models/RunList.tsx` (owner T-263) | T-264, T-265, T-266, T-267, T-276, T-280, T-287, T-289 |
| `apps/frontend/src/features/evaluation/EvalPanel.tsx` (owner T-277) | T-278, T-280, T-286 |
| `apps/frontend/src/features/insights/CompareTab.tsx` (owner T-284) | T-284 |
| `apps/frontend/src/features/insights/Insights.tsx` | T-284 |
| `apps/frontend/src/features/project/insights/Embeddings.tsx` | T-282 |
| `apps/frontend/src/features/workspace/ModelRegistry.tsx` (owner T-257) | T-258 |
| `apps/frontend/src/features/workspace/WorkspacePages.tsx` | T-257 |
| `apps/frontend/src/features/project/models/RegressionTab.tsx` (owner T-294) | T-295 |
| `apps/frontend/src/lib/api/models.ts` (owner T-251) | T-251, T-252, T-257, T-258, T-259, T-261, T-262, T-264, T-265, T-266, T-267, T-271, T-273, T-274, T-276, T-277, T-278, T-279, T-283, T-284, T-288, T-289, T-291, T-292, T-293, T-294 |
| `apps/frontend/src/lib/api/insights.ts` | T-281 |
| `apps/frontend/src/lib/types.ts` | T-250–T-295 (one block per card) |
| `apps/backend/tests/test_train_stages.py` | T-263 (state derivation), T-264 (cancel body) |
| `apps/backend/openapi.json` + `apps/frontend/src/lib/api-types.gen.ts` | T-250, T-251, T-252, T-253, T-256, T-257, T-258, T-259, T-260, T-262, T-263, T-264, T-265, T-266, T-267, T-268, T-269, T-270, T-271, T-277, T-278, T-279, T-281, T-283, T-285, T-287, T-288, T-291, T-292, T-293, T-295 (regenerate last on the branch) |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-250 | Train catalogue: task × family × size with default resolution | B | 3 | R3 | no | `services/train_catalog.py`, `routers/training.py` |
| T-251 | Access requests for gated model families | B | 2.5 | R3+R4 | no | `train/AccessRequestDialog.tsx` |
| T-252 | Training quote: minutes, credits, GPU and the smallest run | B | 3 | R3 | no | `services/train_quote.py` |
| T-253 | Credit cap: a money ceiling with the printed floor | B | 2.5 | R3 | no | `test_train_cap.py` |
| T-254 | Sticky training summary, cap field, long-run confirmation | B | 3 | R4 | no | `train/TrainSummary.tsx`, `train/LongRunDialog.tsx`, `train/summary.ts` |
| T-255 | Train screen: three blocks, three presets, variants behind Advanced | B | 3 | R4 | no | `Train.tsx`, `train/FamilyGrid.tsx`, `train/PresetControl.tsx`, `train/presets.ts` |
| T-256 | Training-time recipe: validated options, locked dataset rows | B | 3 | R4+R3 | no | `services/train_recipe.py`, `train/RecipePanel.tsx`, `train/RecipeLockRows.tsx`, `lib/trainRecipe.ts` |
| T-257 | Star and share models, with a workspace registry tab | C | 3 | R3+R4 | no | `workspace/ModelRegistry.tsx`, `workspace/modelTabs.ts` |
| T-258 | Shared checkpoint catalogue and reuse from another project | C | 3 | R3+R4 | yes | `workspace/SharedCheckpoints.tsx`, `train/checkpoints.ts` |
| T-259 | Starting weights: previous, COCO, shared, ImageNet, random | B | 3 | R3+R4 | no | `train/CheckpointCard.tsx` |
| T-260 | Train on the live dataset (implicit version) | B | 3 | R3 | no | `test_train_current_dataset.py` |
| T-261 | Dataset block: current-or-version, health chip, frozen rows | B | 3 | R4 | no | `train/DataBlock.tsx`, `lib/datasetHealth.ts` |
| T-262 | Start guards: pre-flight warnings and one active run | B | 3 | R3 | no | `services/train_preflight.py`, `train/PreflightList.tsx` |
| T-263 | Run list: stopped vs failed, median latency, a remedy per failure | B | 3 | R3+R4 | no | `services/train_failure.py`, `models/RunList.tsx`, `models/runState.ts`, `Models.tsx` |
| T-264 | Stop early vs cancel, with the consequences on screen | B | 3 | R3+R4 | no | `models/EndRunDialog.tsx`, `models/endRun.ts` |
| T-265 | Cap-reached stop, spend shown, and a funded continuation | B | 3 | R3+R4 | no | `models/CapBanner.tsx`, `models/continuation.ts` |
| T-266 | Spend meter and a log tail for a running job | B | 2.5 | R3+R4 | yes | `models/SpendLogPanel.tsx`, `models/logTail.ts` |
| T-267 | Delete a run: typed name and the serving consequence | B | 3 | R3+R4 | no | `services/deployments.py`, `models/DeleteRunDialog.tsx`, `models/deleteCopy.ts` |
| T-268 | Immutable model references, the legacy alias, licence at download | B | 3 | R3+R4 | no | `services/model_refs.py`, `models/RunActions.tsx`, `lib/modelRef.ts` |
| T-269 | Architecture search: the space, the caps and the plan | B | 3 | R3 | no | `services/architecture_search.py` |
| T-270 | The search job: candidate fan-out inside one run | B | 3 | R3 | no | `test_search_run.py` |
| T-271 | Keep a search candidate as a real model | B | 2.5 | R3 | no | `test_search_candidate_keep.py` |
| T-272 | Search results on screen: band, scatter, keep | B | 3 | R4 | no | `models/SearchResults.tsx`, `models/searchChart.ts` |
| T-273 | Search backbone step: name the deployment target | B | 2.5 | R4+R3 | no | `train/BackboneStep.tsx`, `train/bands.ts` |
| T-274 | Quick model engine: a usable detector minutes after the first batch | B | 3 | R3 | no | `services/quick_model.py` |
| T-275 | Offer a quick model automatically after the first approved batch | B | 2 | R3 | no | `models/QuickModelNote.tsx` |
| T-276 | Quick model entry, states and the confidence hint | B | 2.5 | R4 | no | `models/QuickModelDialog.tsx`, `models/quickModel.ts` |
| T-277 | The tuned threshold becomes the served default | B | 3 | R3+R4 | no | `evaluation/ThresholdDefault.tsx`, `evaluation/threshold.ts`, `evaluation/EvalPanel.tsx` |
| T-278 | Per-class counts: correct, misclassified, missed, false positive | B | 2.5 | R3+R4 | no | `evaluation/PerClassCounts.tsx`, `evaluation/counts.ts` |
| T-279 | Recommendations derived from one evaluation | B | 3 | R3 | no | `services/recommendations.py` |
| T-280 | Recommendations card with working links | B | 2.5 | R4 | no | `models/RecommendationsCard.tsx`, `models/recommendationLink.ts` |
| T-281 | Per-image scores joined onto the embedding map | B | 3 | R3 | no | `test_eval_clusters.py` |
| T-282 | Colour the map by model score, open the worst first | B | 2.5 | R4 | no | `insights/ModelScoreLayer.tsx`, `insights/scoreColour.ts` |
| T-283 | Compare by task metric, with stale evaluations named and re-runnable | B | 3 | R3 | no | `services/compare_metrics.py` |
| T-284 | Compare screen: metric selector, update panel, next steps | B | 3 | R4 | no | `insights/CompareTab.tsx`, `insights/CompareMetricSelect.tsx`, `insights/EvaluationUpdatePanel.tsx`, `insights/compareMetric.ts` |
| T-285 | Pixel metrics and boundary AP for mask models | B | 3 | R3 | no | `test_eval_pixel.py` |
| T-286 | Mask quality card, task metric set, unsupported-task states | B | 2.5 | R4 | no | `evaluation/MaskQualityCard.tsx`, `evaluation/metricSet.ts` |
| T-287 | Evaluation lifecycle: unavailable, sampled and timed out | B | 3 | R3+R4 | no | `models/EvalStateNote.tsx`, `models/evalState.ts` |
| T-288 | Upload external weights: format, magic and a worker-side proof | B | 3 | R3 | **yes** | `services/weight_upload.py` |
| T-289 | Upload dialog with a validation state per file | B | 2.5 | R4 | no | `models/UploadWeightsDialog.tsx`, `models/uploadForm.ts` |
| T-290 | Uploaded models get the same evaluation and the same compare chart | B | 2 | R3 | no | `test_uploaded_eval.py` |
| T-291 | Train elsewhere: a dataset bundle and the way back | C | 2.5 | R3+R4 | yes | `services/train_kit.py`, `models/TrainElsewhereDialog.tsx`, `models/trainKit.ts` |
| T-292 | Regression eval suites: the table and the check grammar | B | 3 | R3 | no | `services/eval_checks.py`, `routers/regression_evals.py` |
| T-293 | Running a regression suite as one job | B | 3 | R3 | no | `handlers/evals.py` |
| T-294 | Regression tab: create a suite and run it | B | 3 | R4 | no | `models/RegressionTab.tsx`, `models/SuiteDialog.tsx`, `models/suiteForm.ts` |
| T-295 | Regression results and the deploy gate | B | 2.5 | R4+R3 | no | `models/EvalRunResults.tsx`, `models/evalRunView.ts` |

## Judgment calls
- **HAVE rows → guard T-006, no cards.** Per the authoring instruction, the 15 HAVE rows (`5-F5.1`, `5-F5.2`, `5-F5.12`, `5-F5.16`, `5-F5.18`, `5-F5.20`, `5-F5.23`, `5-F5.35`, `5-F5.38`, `5-F5.39`, `5-F5.43`, `5-F5.44`, `5-F5.47`, `5-F5.50`, `5-F5.52`) map to `—` + `T-006`. Where §6b would allow a card because the gap cell names work, that work lands inside an adjacent card: F5.1's filter/sort in `T-263`, F5.2's version-page trainings in area 4's `T-221`, F5.16's search charts in `T-272`, F5.38's licence repetition at deploy in area 6, and F5.52's threshold calibration is **not planned** — that is the one owner decision this part leaves open (see below).
- **5-F5.52 → unplanned on purpose.** The gap cell names "threshold calibration from a labelled anomaly set", which changes the anomaly approval workflow owned by area 5's `routers/anomaly.py`… but it is a HAVE row and the planner instruction is explicit. PM: if the owner wants it, it is one card in this band and needs a labelled-anomaly decision first.
- **7-F7.18 (train cost estimator) → `T-252`, `T-254`** — the same cards as `5-F5.11`; the estimator is one service and one summary card.
- **7-F7.56 (star and reuse a public model) → `T-257`, `T-258`** — deliberately **workspace-shared**, not internet-public. Publishing weights to a public page needs a licence/IP decision the owner has not made, and the public *project* page is area 1's `1-F5.2`. The row is satisfied for the "reuse as a checkpoint" half; say so at review rather than inventing a publication policy.
- **5-F5.4** — copy-reference, evaluation, weights and licence ship in `T-268`; the *deploy workflow-template chooser* is the deploy hub's (area 6). Do not duplicate it here.
- **4-F4.7** — area 4 owns the version-side half (`T-222`); area 5 ships the train-side locked rows in `T-256` and the chip in `T-261`. **4-F4.46** — area 4 owns the rules and the version list (`T-223`); `T-261` renders the S8 chip. **4-F4.6** was claimed by area 4 (`T-222`), so this part adds nothing for it.
- **5-F5.5 / 5-F5.13 with no vendor.** Search is built from the local catalogue (`T-269`–`T-272`), not an external NAS service; the "quick model" is a fixed ultralytics recipe (`T-274`–`T-276`), not a vendor few-shot model. F5.13 therefore gets three cards, not four to six: there is no external model to integrate, so a fourth card would be padding.
- **5-F5.28** — this repo has no semantic-segmentation project type and no trainable keypoint family. Pixel metrics are computed over **instance-segmentation masks** (`T-285`) and the keypoint case ships as a visible "cannot train yet" state (`T-286`). OKS is deferred with a reason on screen, not faked from bbox AP.
- **5-F5.26** — the median latency backend rides `T-263` (one card) because the same payload change also feeds the run list.
- **5-F5.45** — licence advice at the weights download in `T-268`; repeating it beside the endpoint is area 6's deploy page.
- **Waves.** Everything is B except `T-257`, `T-258` (registry/publication → C) and `T-291` (data leaving the platform → C).
- **Flags — seven new keys only:** `task_250` (train & run surfaces), `task_257` (workspace registry + shared checkpoints), `task_269` (architecture search), `task_274` (quick model), `task_277` (served threshold), `task_288` (weight upload), `task_292` (regression evals). Every other card states which of these seven hides it; no card invents its own key.
- **Foreign-band merges into area-5 files:** area 6's deploy hub edits `routers/deployments.py` (shared with `T-295`'s one gate call) and area 4's `T-223` owns `services/versions_ready.py`, which `T-262` only imports. Neither is an exclusive collision.
- **`routers/training.py` is the hottest file in this part (19 cards).** PM: serialise in the order listed under Shared-file users; T-250 first because it removes the `FAMILIES` block every later route reads from.
