# Part 6 — Area 6 Deploy, inference, workflows

Gap rows: 41 (29 PARTIAL, 12 MISSING) · Cards: 50 · Hours: 142.5

Hours are attributed once, to the card's primary row; a row that only rides another row's card shows `0 (bundled with …)` and that card's hours appear on its primary row. The 5 HAVE rows are protected by this area's guard `T-006` and carry no card.

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 6-F6.1 | MISSING | T-310, T-311 | A | M | 6 |
| 6-F6.2 | PARTIAL | T-317 | A | S | 2.5 |
| 6-F6.3 | MISSING | T-352, T-353 | D | L | 5.5 |
| 6-F6.4 | PARTIAL | T-354, T-355 | D | L | 6 |
| 6-F6.5 | PARTIAL | T-312 | A | S | 3 |
| 6-F6.6 | PARTIAL | T-349 | D | M | 3 |
| 6-F6.7 | MISSING | T-318 | A | S | 3 |
| 6-F6.8 | MISSING | T-313, T-314 | A | S | 6 |
| 6-F6.9 | HAVE | — · guard T-006 | — | — | — |
| 6-F6.10 | PARTIAL | T-315, T-316 | A | M | 6 |
| 6-F6.11 | HAVE | — · guard T-006 | — | — | — |
| 6-F6.12 | PARTIAL | T-318 | A | S | 0 (bundled with 6-F6.7) |
| 6-F6.13 | PARTIAL | area 7 band (T-380–T-469) | C | S | — |
| 6-F6.14 | PARTIAL | T-335, T-336 | B | M | 6 |
| 6-F6.15 | PARTIAL | T-337, T-338 | B | M | 6 |
| 6-F6.16 | PARTIAL | T-339 | B | M | 3 |
| 6-F6.17 | PARTIAL | T-340, T-341 | B | M | 5.5 |
| 6-F6.18 | PARTIAL | area 7 band (T-380–T-469) | C | M | — |
| 6-F6.19 | PARTIAL | T-350, T-351 | D | M | 5.5 |
| 6-F6.20 | PARTIAL | T-338 | B | S | 0 (bundled with 6-F6.15) |
| 6-F6.21 | PARTIAL | T-320, T-321, T-322, T-323 | B | L | 12 |
| 6-F6.22 | HAVE | — · guard T-006 | — | — | — |
| 6-F6.23 | PARTIAL | T-324 | B | M | 3 |
| 6-F6.24 | MISSING | T-325 | B | M | 2.5 |
| 6-F6.25 | MISSING | T-326 | B | S | 2.5 |
| 6-F6.26 | PARTIAL | T-327 | B | S | 2.5 |
| 6-F6.27 | PARTIAL | T-328, T-329 | B | M | 5.5 |
| 6-F6.28 | PARTIAL | T-330 | B | S | 2 |
| 6-F6.29 | MISSING | T-326 | B | S | 0 (bundled with 6-F6.25) |
| 6-F6.30 | MISSING | T-331 | B | M | 3 |
| 6-F6.31 | MISSING | T-345 | C | M | 3 |
| 6-F6.32 | PARTIAL | T-334 | B | M | 3 |
| 6-F6.33 | PARTIAL | T-319 | B | M | 3 |
| 6-F6.34 | PARTIAL | T-333 | B | S | 2.5 |
| 6-F6.35 | HAVE | — · guard T-006 | — | — | — |
| 6-F6.36 | PARTIAL | T-332 | B | M | 3 |
| 6-F6.37 | PARTIAL | T-342 | B | M | 3 |
| 6-F6.38 | MISSING | T-343 | B | M | 3 |
| 6-F6.39 | PARTIAL | T-344 | B | M | 3 |
| 6-F6.40 | PARTIAL | T-348 | C | S | 2.5 |
| 6-F6.41 | PARTIAL | T-346 | C | M | 3 |
| 6-F6.42 | MISSING | T-347 | C | S | 2 |
| 6-F6.43 | HAVE | — · guard T-006 | — | — | — |
| 6-F6.44 | PARTIAL | T-356, T-357 | D | M | 5.5 |
| 6-F6.45 | PARTIAL | T-312 | A | S | 0 (bundled with 6-F6.5) |
| 6-F6.46 | MISSING | T-358, T-359 | D | L | 6 |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/routers/__init__.py` | T-310, T-316, T-317, T-335, T-340, T-345, T-358 |
| `apps/backend/app/models/__init__.py` | T-335, T-340, T-345, T-352, T-358 |
| `apps/backend/app/services/flags.py` | T-311 (`task_311`), T-314 (`task_314`), T-316 (`task_316`), T-322 (`task_322`), T-324 (`task_324`), T-328 (`task_328`), T-330 (`task_330`), T-334 (`task_334`), T-335 (`task_335`), T-337 (`task_337`), T-339 (`task_339`), T-340 (`task_340`), T-345 (`task_345`), T-346 (`task_346`), T-349 (`task_349`), T-350 (`task_350`), T-352 (`task_352`), T-358 (`task_358`) |
| `apps/backend/app/schema/dataset.py` | T-320 (creates the `WORKFLOWS` block), T-328, T-345 |
| `apps/backend/app/schema/streams.py` | T-337, T-339, T-346, T-356 |
| `apps/backend/app/models/project.py` | T-320, T-328, T-345 |
| `apps/backend/app/models/streams.py` | T-337, T-339, T-346, T-356 |
| `apps/backend/app/services/workflows.py` | T-315, T-320, T-321, T-331, T-332 |
| `apps/backend/app/services/workflow_graph.py` (owner T-320) | T-320, T-331, T-332 |
| `apps/backend/app/services/workflow_compile.py` (owner T-321) | T-321, T-331 |
| `apps/backend/app/services/workflow_runner.py` | T-326, T-332 |
| `apps/backend/app/services/workflow_invoke.py` (owner T-316) | T-316, T-328 |
| `apps/backend/app/services/batch_inference.py` | T-334, T-354 |
| `apps/backend/app/streams/manager.py` | T-337, T-356 |
| `apps/backend/app/routers/workflows.py` | T-315, T-320, T-324, T-326, T-327, T-328, T-330 |
| `apps/backend/app/routers/streams.py` | T-337, T-338, T-339, T-346, T-347, T-356, T-357 |
| `apps/backend/app/routers/batch_inference.py` | T-334, T-354 |
| `apps/backend/app/routers/runtimes.py` (owner T-310) | T-310, T-349, T-352, T-353 |
| `apps/backend/app/routers/training.py` | T-317, T-335 |
| `apps/backend/app/routers/edge.py` (owner T-358) | T-358, T-359 |
| `apps/backend/app/jobs.py` | T-340, T-350, T-359 |
| `apps/backend/app/config.py` | T-350 |
| `packages/sdk/labeldesk/client.py` | T-342, T-343, T-344, T-348 |
| `packages/sdk/labeldesk/cli.py` (owner T-344) | T-344, T-348 |
| `apps/frontend/src/features/project/Deploy.tsx` (owner T-314) | T-314, T-311, T-318, T-349 |
| `apps/frontend/src/features/project/Workflows.tsx` (owner T-322) | T-322, T-329, T-333, T-345 |
| `apps/frontend/src/features/project/WorkflowBlocks.tsx` | T-331, T-332 |
| `apps/frontend/src/features/workflow/WorkflowEditor.tsx` (owner T-322) | T-322, T-324, T-329 |
| `apps/frontend/src/features/workflow/WorkflowCanvas.tsx` (owner T-322) | T-322, T-323, T-326, T-327 |
| `apps/frontend/src/features/workflow/RunPanel.tsx` (owner T-324) | T-324, T-321, T-325, T-326 |
| `apps/frontend/src/features/workflow/graph.ts` (owner T-322) | T-322, T-323, T-331 |
| `apps/frontend/src/features/workflow/templates.ts` (owner T-332) | T-332, T-333 |
| `apps/frontend/src/features/deploy/EndpointCard.tsx` (owner T-313) | T-313, T-317, T-318 |
| `apps/frontend/src/features/deploy/Chooser.tsx` (owner T-311) | T-311, T-312, T-353 |
| `apps/frontend/src/features/streams/Streams.tsx` | T-346, T-356, T-357 |
| `apps/frontend/src/features/streams/StreamDetail.tsx` | T-337, T-338, T-339, T-341, T-347, T-357 |
| `apps/frontend/src/features/workspace/WorkspacePages.tsx` | T-336, T-355, T-358 |
| `apps/frontend/src/features/project/ProjectSettings.tsx` | T-337, T-351 |
| `apps/frontend/src/features/project/Dataset.tsx` | T-334 (area 2's T-062 owns this file; rebase its one button onto that split) |
| `apps/frontend/src/lib/api/deploy.ts` (owner T-310) | T-310, T-317, T-335, T-336, T-349, T-352, T-353, T-358, T-359 |
| `apps/frontend/src/lib/api/workflows.ts` | T-316, T-319, T-320, T-324, T-326, T-328, T-329, T-330, T-345 |
| `apps/frontend/src/lib/api/streams.ts` | T-337, T-338, T-339, T-340, T-346, T-347, T-357 |
| `apps/frontend/src/lib/api/dataset.ts` | T-334, T-350, T-355 |
| `apps/frontend/src/lib/types.ts` | every card that adds a field: T-310, T-315, T-316, T-317, T-319–T-321, T-324, T-326–T-328, T-330, T-334–T-340, T-345–T-347, T-349, T-352–T-359 |
| `apps/backend/openapi.json` + `apps/frontend/src/lib/api-types.gen.ts` | every route card: T-310, T-315–T-317, T-319, T-320, T-324, T-326–T-328, T-330, T-334–T-340, T-345–T-358 — regenerate once, last, in card order |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-310 | One runtime catalogue, one response contract | A | 3 | R3 | no | `services/runtimes.py`, `routers/runtimes.py`, `tests/test_runtimes.py`, `lib/api/deploy.ts` |
| T-311 | A chooser that separates real-time from bulk | A | 3 | R4 | no | `features/deploy/Chooser.tsx`, `deploy/choice.ts`, `tests/deploy-choice.test.mjs` |
| T-312 | Self-hosting you can start from inside the product | A | 3 | R4 | no | `features/deploy/SelfHost.tsx`, `deploy/selfHostSnippets.ts`, `tests/deploy-selfhost.test.mjs` |
| T-313 | Snippets and an endpoint card that follow the runtime | A | 3 | R4 | yes | `features/deploy/snippets.ts`, `deploy/EndpointCard.tsx`, `tests/deploy-snippets.test.mjs` |
| T-314 | Deploy and test: prove it works, then ship it | A | 3 | R4 | no | `features/project/Deploy.tsx`, `features/deploy/TestPane.tsx` |
| T-315 | A workflow declares the inputs it will accept | A | 3 | R3 | no | `services/workflow_contract.py`, `tests/test_workflow_contract.py` |
| T-316 | Call a published workflow from outside | A | 3 | R4+R3 | yes | `routers/workflow_api.py`, `services/workflow_invoke.py`, `tests/test_workflow_invoke.py`, `features/workflow/InvokeSnippet.tsx` |
| T-317 | Say when a request paid the cold start | A | 2.5 | R3 | no | `routers/warmup.py`, `services/warmup.py`, `tests/test_infer_headers.py` |
| T-318 | What went wrong, and whether it cost anything | A | 3 | R4 | no | `features/deploy/CallerReference.tsx`, `deploy/errorCopy.ts`, `tests/deploy-errors.test.mjs` |
| T-319 | Every place a workflow can run, from one button | B | 3 | R4+R3 | no | `services/workflow_destinations.py`, `tests/test_workflow_destinations.py`, `features/deploy/Destinations.tsx`, `deploy/destinations.ts` |
| T-320 | A workflow becomes a graph with named ports | B | 3 | R3 | no | `services/workflow_graph.py`, `tests/test_workflow_graph.py` |
| T-321 | Old linear workflows keep running | B | 3 | R3 | no | `services/workflow_compile.py`, `tests/test_workflow_compile.py` |
| T-322 | The canvas: nodes, ports and a palette | B | 3 | R4 | no | `features/workflow/WorkflowCanvas.tsx`, `WorkflowEditor.tsx`, `workflow/graph.ts`, `features/project/Workflows.tsx`, `tests/workflow-graph.test.mjs` |
| T-323 | Wiring help in three strengths, and one arrange button | B | 3 | R4 | no | `features/workflow/wiring.ts`, `tests/workflow-wiring.test.mjs` |
| T-324 | Test a draft on a still, a clip or a camera | B | 3 | R4 | no | `features/workflow/RunPanel.tsx`, `workflow/media.ts`, `tests/workflow-media.test.mjs` |
| T-325 | Block cache, with an honest uncache | B | 2.5 | R4 | no | `features/workflow/blockCache.ts`, `tests/workflow-cache.test.mjs` |
| T-326 | Mute the side effects, and mute one node | B | 2.5 | R4 | no | `features/workflow/runGuards.ts`, `tests/workflow-guards.test.mjs` |
| T-327 | The Outputs node is a list you can order | B | 2.5 | R4+R3 | no | `services/workflow_outputs.py`, `features/workflow/OutputsNode.tsx`, `workflow/outputs.ts`, two test files |
| T-328 | Save is a draft; publish is a gate | B | 3 | R3 | no | `services/workflow_publish.py`, `tests/test_workflow_publish.py` |
| T-329 | The publish panel, and auto-publish | B | 2.5 | R4 | no | `features/workflow/PublishGate.tsx`, `workflow/publishView.ts`, `tests/workflow-publish.test.mjs` |
| T-330 | Version history that says what production runs | B | 2 | R4 | no | `features/project/WorkflowVersions.tsx` |
| T-331 | A workflow inside a workflow | B | 3 | R3 | no | `services/workflow_inner.py`, `tests/test_workflow_inner.py`, `workflow/blocks/InnerWorkflowFields.tsx` |
| T-332 | Per-object classes: detect, crop, classify, write back | B | 3 | R3 | no | `services/workflow_replace.py`, `tests/test_workflow_replace.py`, `workflow/blocks/ReplaceFields.tsx`, `workflow/templates.ts` |
| T-333 | A first workflow that produces a result in five actions | B | 2.5 | R4 | no | `features/workflow/FirstRun.tsx`, `tests/workflow-first-run.test.mjs` |
| T-334 | Run a model over the images I just picked | B | 3 | R3 | no | `tests/test_batch_selection.py`, `project/batch/RunOnSelectionDialog.tsx`, `batch/selectionRun.ts`, `tests/batch-selection.test.mjs` |
| T-335 | Record every hosted request, without keeping the image | B | 3 | R3 | yes | `models/requests.py`, `services/request_log.py`, `routers/monitor.py`, `tests/test_request_log.py` |
| T-336 | A monitoring page that says what it does not keep | B | 3 | R4 | no | `features/deploy/Monitor.tsx`, `deploy/monitorView.ts`, `services/request_stats.py`, `tests/monitor-view.test.mjs` |
| T-337 | Production events get a type and a vocabulary | B | 3 | R3 | no | `streams/event_types.py`, `models/streams.py`, `tests/test_event_types.py`, `project/EventVocabulary.tsx`, `streams/EventTypeChip.tsx` |
| T-338 | Filter events, and say how far back the data goes | B | 3 | R4+R3 | no | `streams/event_query.py`, `tests/test_event_query.py`, `streams/EventFilters.tsx`, `streams/eventFilter.ts` |
| T-339 | A human verdict on a production event | B | 3 | R3 | no | `services/event_feedback.py`, `tests/test_event_feedback.py`, `streams/EventVerdict.tsx`, `tests/event-verdict.test.mjs` |
| T-340 | One reviewer at a time, and the lock releases itself | B | 3 | R3 | no | `models/review.py`, `services/review_session.py`, `routers/review.py`, `tests/test_review_session.py` |
| T-341 | The review session screen | B | 2.5 | R4 | no | `streams/ReviewSession.tsx`, `streams/reviewKeys.ts`, `tests/review-session.test.mjs` |
| T-342 | Run a workflow and load a model from Python | B | 3 | R5 | no | `packages/sdk/labeldesk/loader.py`, `tests/test_sdk_workflow.py`, `packages/sdk/README.md` |
| T-343 | A video source object for a file, a webcam or a camera URL | B | 3 | R5 | no | `packages/sdk/labeldesk/pipeline.py`, `tests/test_sdk_pipeline.py` |
| T-344 | Two command sets, one stated boundary | B | 3 | R5 | no | `packages/sdk/labeldesk/cli.py` |
| T-345 | Hand a workflow to another project | C | 3 | R4+R3 | yes | `models/sharing.py`, `services/workflow_share.py`, `routers/workflow_sharing.py`, `workflow/ShareWorkflow.tsx`, `SharedWorkflow.tsx`, `FolderPicker.tsx` |
| T-346 | Say what each camera source can and cannot become | C | 3 | R4+R3 | yes | `streams/discovery.py`, `tests/test_stream_discovery.py`, `streams/NewSourceDialog.tsx`, `streams/sources.ts` |
| T-347 | Capture settings, and where they do nothing | C | 2 | R4 | no | `streams/capture.py`, `tests/test_stream_capture.py`, `streams/CaptureSettings.tsx`, `streams/capture.ts` |
| T-348 | One key, three sources, one documented order | C | 2.5 | R5 | yes | `packages/sdk/labeldesk/config.py`, `tests/test_sdk_keys.py` |
| T-349 | The rate table, next to the choice | D | 3 | R4+R3 | no | `services/credit_rates.py`, `tests/test_credit_rates.py`, `deploy/CostTable.tsx`, `deploy/costView.ts` |
| T-350 | Collection limits: caps, cadence and what is kept | D | 3 | R3 | no | `tests/test_active_learning_caps.py` |
| T-351 | The active-learning form, and who reviews the batch | D | 2.5 | R4 | no | `project/ActiveLearningForm.tsx`, `project/activeLearningView.ts`, `tests/active-learning-form.test.mjs` |
| T-352 | A private box: interface, mock driver, honest default | D | 3 | R3 | no | `models/dedicated.py`, `services/dedicated.py`, `tests/test_dedicated.py` |
| T-353 | The private-box panel, its usage and its logs | D | 2.5 | R4 | no | `deploy/DedicatedPanel.tsx`, `deploy/dedicatedView.ts`, `tests/dedicated-panel.test.mjs` |
| T-354 | Batch over stored files: run a workflow, keep a result set | D | 3 | R3 | yes | `tests/test_batch_workflow.py` |
| T-355 | The batch screen: source, progress, result | D | 3 | R4 | no | `deploy/BatchJobs.tsx`, `deploy/batchView.ts`, `tests/batch-view.test.mjs` |
| T-356 | Camera state and job state are two different words | D | 3 | R3 | no | `streams/state.py`, `tests/test_stream_state.py`, `streams/statusMeta.ts` |
| T-357 | Restart one camera or all of them, and read what happened | D | 2.5 | R4+R3 | no | `services/stream_activity.py`, `tests/test_stream_activity.py`, `streams/StreamActions.tsx`, `StreamActivity.tsx` |
| T-358 | Devices that check in, and say how they are | D | 3 | R3 | yes | `models/edge.py`, `services/edge_fleet.py`, `routers/edge.py`, `tests/test_edge_fleet.py`, `deploy/EdgeDevices.tsx` |
| T-359 | A config change that cannot reach 200 boxes unreviewed | D | 3 | R3 | yes | `services/edge_config.py`, `tests/test_edge_config.py`, `deploy/EdgeConfig.tsx`, `deploy/edgeConfigView.ts` |

## Judgment calls
- Guards are per area: the five HAVE rows (`6-F6.9`, `6-F6.11`, `6-F6.22`, `6-F6.35`, `6-F6.43`) map to this area's guard `T-006`. Two of them (`6-F6.22` published-ports separation, `6-F6.35` visualisation blocks) have a gap cell that names real work; that work ships inside T-322 (required fields first in the config panel) and T-327/T-333 (the visualisation and next-step path) rather than as cards of their own, so the rows stay `—` and the guard asserts the existing behaviour still holds.
- `6-F6.13` (key lifecycle) and `6-F6.18` (alert channels) → area 7 band (T-380–T-469) per brief §4. No card here; T-318 links to the keys page and T-357 links to the alert channels instead of building either.
- `6-F6.25` (sinks switch) — claimed here after checking that `.parts/area-7.md` had not landed at authoring time. **Risk:** if area 7 planned the switch as part of its webhook sinks, T-326 is the duplicate to drop, because it is the same control.
- `6-F6.20` (retention per surface) — only the lookback half is planned, in T-338 (`lookback_days` in every event response plus the clamped-range sentence). The trash-window half is area 7's `7-F7.43`; T-338 does not touch the trash model.
- `6-F6.44` — recovery, the state vocabulary and the activity feed are T-356/T-357. Its offline-email half is `6-F6.18`'s (area 7): T-356 only produces the `attention` reason a notice would quote.
- `6-F6.6` is wave D even though no charge is added: the outcome is the money story, and a wave-D card stays provider-agnostic — T-349 prints the rates the product already meters and contains no price, currency or checkout.
- `6-F6.32` is wave B, not D: it runs on the shipped `batch_inference` job with a new `selection` source, so it does not wait for `6-F6.4`'s workflow batch (wave D). The two share `services/batch_inference.py` and are ordered T-334 → T-354.
- `6-F6.37`–`6-F6.40` (SDK/CLI) are not named in §3; they are placed by the first rule that fits — `6-F6.37`/`38`/`39` in B (inference mechanics, beside the deploy surface) and `6-F6.40` in C (a credential file, so R7 applies).
- `6-F6.41` is C, not B: ONVIF discovery and camera credentials are the connector-shaped part of the row. `6-F6.42` rides the same surface in C.
- `6-F6.31` is C: sharing, forking and folders are people/permission work. Folder-scoped read/edit permissions are deliberately **not** planned — this repo's `folders` table carries no permission rows, and a second ACL beside the project roles would give two sources of truth.
- `6-F6.3` and `6-F6.46` are wave D and provider-agnostic by order of the owner: T-352/T-353 plan a driver interface, a catalogue row, a mock driver, a flag off by default and an honest "not available in this deployment" state, with no vendor, no price and no credential; T-358/T-359 do the same for a device check-in contract (`LD_EDGE_FLEET`), with approval and a maintenance window as the only write path. Neither card invents hardware the owner has not chosen.
- `6-F6.4` and `6-F6.27` touch the same execution path: T-354 reuses the compile + runner pair from T-321, and T-328 makes the invoke path read the published blocks. Neither teaches `workflow_runner.py` a second execution model — that is the one decision these cards must not leave open.
- Cross-area consumers, mapped not duplicated: `3-F3.31` (area 3's `T-158`, workflow as the labeller) consumes T-315's contract and T-319's destinations; area 4's export and import cards own the artefact formats T-354/355 reuse; area 5's evaluation surface is the future `CHECKS` entry in T-328. This area adds no labeler, no exporter and no evaluation metric.
- S10 of the redesign is delivered by T-311 (chooser), T-313 (endpoint card), T-314 (test-first panes) and T-336 (requests). The workspace-rail "Deployments" entry is unchanged; T-336/T-355/T-358 add tabs to it rather than new rail items.
