# Part F — Wave F (BEYOND): the capability layer above parity

Gap rows: 101 (2 HAVE, 58 PARTIAL, 41 MISSING) · Cards: 171 · Hours: 488

Sources: `docs/research/beyond-roboflow/BEYOND.md` (matrix, §3, §4) and its six group files. Every card cites a verified repo path; every one is ≤ 3 agent-hours and carries the flag-off, cross-workspace and empty/loading/error acceptance lines.

## Bands (execution order = id order)

| Band | First | Last | Cards | Hours |
| --- | --- | --- | --- | --- |
| Thai-first foundation — G5.22 | T-600 | T-603 | 4 | 10.5 |
| A · label quality loop — G1.x | T-610 | T-633 | 24 | 67.5 |
| D · auto-label you can defend — G4.x | T-640 | T-665 | 26 | 73 |
| C · line-side loop — G3.x | T-670 | T-697 | 28 | 80.5 |
| F · Thai market and verticals — G6.x | T-710 | T-733 | 24 | 69 |
| E · data protection and money — G5.3…G5.16 | T-740 | T-758 | 19 | 55.5 |
| E · platform trust and adoption — G5.7…G5.24 | T-760 | T-779 | 20 | 58 |
| B · training and MLOps depth — G2.x | T-780 | T-805 | 26 | 74 |
| **Total** | | | **171** | **488** |

## Mapping

| BEYOND id | Feature | Status | Pri | Size | Task ids | Hours |
| --- | --- | --- | --- | --- | --- | --- |
| G1.1 | Duplicate passes merged by majority, with a reviewer override | HAVE | Should | S | T-611 | 3 |
| G1.2 | Answer-key rows seeded into the live queue at a rate | PARTIAL | Should | M | T-612, T-613 | 5.5 |
| G1.3 | Score at submit, with capped retries and hints | MISSING | Could | M | T-614, T-615 | 5.5 |
| G1.4 | Quality dashboard down to class and confusion pairs | PARTIAL | Must | M | T-616, T-617 | 5.5 |
| G1.5 | Work queue with priority, stage scope and a cap per labeler | MISSING | Must | M | T-618, T-619 | 5.5 |
| G1.6 | Labeling stage graph (human, model, consensus) | MISSING | Should | L | T-620, T-621, T-622 | 8.5 |
| G1.9 | Object tracks with keyframes, an out-of-frame state, split and merge | PARTIAL | Should | M | T-623, T-624 | 5.5 |
| G1.10 | Review screen with side-by-side answer key and a mismatch list | PARTIAL | Should | M | T-625, T-626 | 5.5 |
| G1.11 | Trial project that scores a labeler before real work | MISSING | Could | M | T-627, T-628 | 5.5 |
| G1.12 | Event-triggered extension runtime on label events | PARTIAL | Could | L | T-629, T-630 | 5.5 |
| G1.13 | Label form defined as a document, not a task type | MISSING | Could | L | T-631, T-632 | 6 |
| G1.16 | Time-in-stage and labelling speed accounting | PARTIAL | Should | S | T-633 | 3 |
| G1.17 | Quality metric chosen per field, with thresholds | PARTIAL | Could | S | T-610 | 3 |
| G2.1 | Sweep a version across a parameter space | MISSING | Could | L | T-802, T-803 | 6 |
| G2.2 | The run keeps its exact configuration, exportable and re-importable | PARTIAL | Should | S | T-780 | 3 |
| G2.3 | One ledger row per run with configuration as sortable columns | PARTIAL | Should | M | T-781 | 3 |
| G2.4 | Promotion is a request naming an approver | PARTIAL | Should | M | T-782, T-783 | 5 |
| G2.5 | Lineage carries its inputs and can re-run from any node | PARTIAL | Should | M | T-784 | 3 |
| G2.6 | A model card ships with the weights | MISSING | Should | M | T-789, T-790 | 5.5 |
| G2.7 | A slice of the score opens into the images that caused it | PARTIAL | Should | M | T-785, T-786 | 5.5 |
| G2.8 | The hold-out score is audited for leakage | PARTIAL | Should | M | T-787, T-788 | 5.5 |
| G2.9 | Coverage report for the conditions the model will meet | PARTIAL | Could | L | T-792 | 3 |
| G2.10 | Suspect labels ranked by model confidence | HAVE | Could | S | T-793 | 2 |
| G2.11 | Benchmark sheet: latency and throughput per export format and device | MISSING | Should | M | T-791 | 3 |
| G2.12 | Queues with priorities, pools and quotas instead of one worker | PARTIAL | Should | L | T-798, T-799 | 6 |
| G2.13 | Bring your own GPU, and watch it in our dashboard | PARTIAL | Could | M | T-800, T-801 | 5.5 |
| G2.14 | A failed run explains itself and retries with the same arguments | PARTIAL | Should | M | T-795 | 3 |
| G2.15 | Per-run host telemetry, not just loss curves | PARTIAL | Could | S | T-794 | 3 |
| G2.16 | A published run report a non-engineer can read | PARTIAL | Should | M | T-796, T-797 | 6 |
| G2.17 | An extension point for our own and the customer's analysis | MISSING | Could | L | T-804, T-805 | 6 |
| G3.1 | Camera onboarding: discovery, profile choice, credential pre-test | PARTIAL | Should | M | T-672 | 3 |
| G3.2 | Site → line → station → camera hierarchy | PARTIAL | Must | M | T-670, T-671 | 6 |
| G3.3 | Operator verdict with reason codes and a piece id | PARTIAL | Should | M | T-675, T-676 | 5.5 |
| G3.4 | Rules that follow a schedule instead of always being on | MISSING | Should | S | T-677 | 3 |
| G3.5 | Alarm ownership, snooze, cross-camera grouping and a queue | PARTIAL | Should | M | T-678, T-679 | 6 |
| G3.6 | Evidence clip with pre/post-roll and a hold | MISSING | Should | M | T-680, T-681 | 5.5 |
| G3.7 | Store-and-forward while the edge or the server is offline | MISSING | Should | L | T-673, T-674 | 6 |
| G3.8 | Device-bound engine registry with a golden replay | PARTIAL | Should | M | T-682, T-683 | 5.5 |
| G3.9 | Training that knows its deployment target | MISSING | Should | L | T-684, T-685 | 5.5 |
| G3.10 | Prune / INT8 / QAT with an accuracy delta | PARTIAL | Should | M | T-686, T-687 | 6 |
| G3.11 | Reject signal to the machine over Modbus / OPC-UA / MQTT | MISSING | Must | M | T-688, T-689 | 5.5 |
| G3.12 | Barcode / QR / lot-code decoding | MISSING | Should | M | T-690 | 3 |
| G3.13 | OCR / OCV verification against an expected value | PARTIAL | Should | S | T-691 | 2.5 |
| G3.14 | Measurement in real units with calibration and a tolerance verdict | MISSING | Should | M | T-692 | 3 |
| G3.15 | Shift calendar, first-pass yield and reason breakdown | PARTIAL | Should | M | T-693 | 3 |
| G3.16 | Camera quality guard: readiness probe plus a per-camera baseline | PARTIAL | Should | S | T-694 | 2.5 |
| G3.17 | Event envelope contract, broker transport, dead-letter and replay | PARTIAL | Should | M | T-695, T-696 | 6 |
| G3.18 | On-camera analytics partitioning (metadata in, not pixels) | MISSING | Could | L | T-697 | 3 |
| G4.1 | A per-class prompt pack (synonyms, exclusions) that can seed the class list | PARTIAL | Must | M | T-640, T-641 | 6 |
| G4.3 | Confidence bands with an escalation threshold and per-band counts | PARTIAL | Must | M | T-642, T-643 | 5.5 |
| G4.4 | A VLM second pass that flags a box instead of deleting it | PARTIAL | Must | M | T-644 | 3 |
| G4.5 | A judge rubric returning a verdict, a reason and a score per label | MISSING | Should | M | T-645, T-646 | 5.5 |
| G4.6 | A question checklist that answers into per-image attributes | MISSING | Should | M | T-647, T-648 | 5.5 |
| G4.7 | Caption and keyword extraction written back as tags | PARTIAL | Could | S | T-649 | 2.5 |
| G4.8 | Named clusters on the embedding map, with lasso-to-label | PARTIAL | Should | M | T-650 | 3 |
| G4.9 | A per-class coverage and gap report with targets | PARTIAL | Should | M | T-651 | 3 |
| G4.10 | Active learning with margin sampling, a quota and a stated budget | PARTIAL | Should | M | T-652, T-653 | 5.5 |
| G4.11 | A discovery sweep that names classes nobody asked for | MISSING | Could | L | T-654, T-655 | 5.5 |
| G4.12 | Track a concept from one text prompt across a video with stable IDs | PARTIAL | Should | M | T-656, T-657 | 5.5 |
| G4.13 | A disagreement queue between two auto-label models | MISSING | Should | M | T-658 | 3 |
| G4.14 | A teacher → student loop with an agreement gate | PARTIAL | Should | M | T-659 | 3 |
| G4.15 | Synthetic and composited fills for a rare class, with provenance | MISSING | Could | L | T-660, T-661 | 5.5 |
| G4.16 | Harvest the boxes the checker rejected as hard negatives | MISSING | Could | S | T-662 | 2.5 |
| G4.17 | A labelling job the agent plans, trials, then escalates | MISSING | Should | L | T-663, T-664 | 5.5 |
| G4.18 | Ask the dataset a structural question in words | MISSING | Should | M | T-665 | 3 |
| G5.3 | Sign-in policy: session life, step-up, MFA, network rules | PARTIAL | Should | M | T-740, T-741, T-742, T-743 | 11.5 |
| G5.4 | Ownership transfer and an offboarding sweep | MISSING | Must | M | T-744, T-745 | 6 |
| G5.5 | Tamper-evident audit trail with a retention floor | PARTIAL | Should | M | T-746, T-747 | 6 |
| G5.6 | Object-scoped activity history | PARTIAL | Should | M | T-748, T-749 | 6 |
| G5.7 | Retention policy builder with dry-run and legal hold | PARTIAL | Should | M | T-760, T-761 | 6 |
| G5.8 | Sandbox and production separation | MISSING | Could | M | T-762, T-763 | 6 |
| G5.9 | DSAR workbench: find, export and erase one person | PARTIAL | Must | M | T-750, T-751, T-752 | 8.5 |
| G5.10 | Processing register: purpose, lawful basis, consent, transfers | PARTIAL | Should | M | T-753, T-754 | 6 |
| G5.11 | Sub-processor register with change notice and an objection window | MISSING | Should | S | T-764 | 3 |
| G5.12 | Trust centre | PARTIAL | Should | M | T-765 | 3 |
| G5.13 | Breach notification runbook with a 72-hour clock | PARTIAL | Should | M | T-766, T-767 | 6 |
| G5.15 | Customer-owned bucket and customer-managed keys | MISSING | Could | L | T-768, T-769 | 6 |
| G5.16 | Thai invoiced billing: PromptPay, bank transfer, VAT tax invoice, PO, dunning | MISSING | Must | M | T-755, T-756, T-757, T-758 | 11.5 |
| G5.17 | Per-project budget with a pre-flight estimate and pause | PARTIAL | Should | M | T-770, T-771 | 5.5 |
| G5.18 | Public status page with incident history | PARTIAL | Should | M | T-772, T-773 | 5.5 |
| G5.19 | SLA with measured uptime and a self-serve credit claim | MISSING | Could | M | T-774, T-775 | 5.5 |
| G5.20 | In-product help: what's new, docs search, feedback | MISSING | Should | S | T-776 | 3 |
| G5.21 | Guided onboarding and admin adoption analytics | PARTIAL | Could | M | T-777, T-778 | 5.5 |
| G5.22 | Thai locale end to end, including generated documents | PARTIAL | Must | L | T-600, T-601, T-602, T-603 | 10.5 |
| G5.24 | WCAG 2.2 AA with an automated gate | PARTIAL | Could | M | T-779 | 3 |
| G6.1 | Lot-bound inspection record with an OK / NG / rework disposition | PARTIAL | Must | M | T-710, T-711 | 5.5 |
| G6.2 | First-pass yield and defect Pareto per lot, line and shift | MISSING | Must | M | T-712, T-713 | 6 |
| G6.4 | Shift handover brief at the end of a shift | MISSING | Should | S | T-719 | 3 |
| G6.5 | Glove-first Thai operator screen at the station | MISSING | Should | L | T-715, T-716 | 6 |
| G6.6 | Vertical starter packs (PPE safety, IC/PCB defect) installed in one step | PARTIAL | Must | M | T-717, T-718 | 5.5 |
| G6.7 | LINE alert with evidence and an acknowledgement ladder | PARTIAL | Should | M | T-714, T-720 | 5.5 |
| G6.8 | Daily safety summary PDF for an inspector | MISSING | Should | M | T-721, T-722 | 5.5 |
| G6.10 | Shelf-gap and planogram slot compliance | MISSING | Could | L | T-723 | 3 |
| G6.11 | Price-tag read-back against a price master | PARTIAL | Could | M | T-724 | 3 |
| G6.12 | Fruit grading station by size and defect | MISSING | Could | L | T-725 | 3 |
| G6.13 | Exporter lot report with grade mix and photographs | MISSING | Could | M | T-726 | 3 |
| G6.14 | Offline field capture with deferred sync and geotag | MISSING | Should | M | T-727 | 3 |
| G6.15 | Evidence package for police or insurer | PARTIAL | Should | M | T-729, T-730 | 5.5 |
| G6.16 | Redaction of faces and plates across capture, live view and export | PARTIAL | Should | M | T-728, T-731 | 5.5 |
| G6.20 | Air-gapped on-premises install with an offline licence | PARTIAL | Should | L | T-732 | 3 |
| G6.22 | Partner console for an SI: child workspaces, licence pool, statement | MISSING | Could | L | T-733 | 3 |

## Shared-file users (suggested merge order, top of the list)

| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/frontend/src/lib/api-types.gen.ts` | T-602, T-610, T-611, T-612, T-614, T-616, T-618, T-620, T-621, T-623, T-625, T-627, T-629, T-631, T-633, T-640, T-641, T-642, T-643, T-645, T-646, T-647, T-648, T-649, T-650, T-651, T-652, T-653, T-654, T-655, T-656, T-657, T-658, T-659, T-660, T-661, T-662, T-663, T-664, T-665, T-670, T-671, T-672, T-674, T-675, T-677, T-678, T-680, T-681, T-682, T-683, T-684, T-685, T-686, T-687, T-688, T-690, T-691, T-692, T-693, T-694, T-695, T-696, T-697, T-710, T-712, T-714, T-715, T-717, T-719, T-721, T-723, T-724, T-725, T-726, T-727, T-728, T-729, T-732, T-733, T-740, T-741, T-742, T-743, T-744, T-745, T-746, T-747, T-748, T-749, T-750, T-751, T-752, T-753, T-754, T-755, T-756, T-757, T-758, T-760, T-761, T-762, T-763, T-764, T-765, T-766, T-767, T-768, T-769, T-770, T-771, T-772, T-773, T-774, T-775, T-776, T-777, T-778, T-780, T-781, T-782, T-785, T-787, T-789, T-791, T-792, T-793, T-794, T-795, T-796, T-798, T-800, T-802, T-804 |
| `apps/backend/openapi.json` | T-602, T-610, T-611, T-612, T-614, T-616, T-618, T-620, T-621, T-623, T-625, T-627, T-629, T-631, T-633, T-640, T-642, T-645, T-647, T-649, T-650, T-651, T-652, T-654, T-656, T-658, T-659, T-660, T-662, T-663, T-665, T-670, T-671, T-672, T-674, T-675, T-677, T-678, T-680, T-681, T-682, T-683, T-684, T-685, T-686, T-687, T-688, T-690, T-691, T-692, T-693, T-694, T-695, T-696, T-697, T-710, T-712, T-714, T-715, T-717, T-719, T-721, T-723, T-724, T-725, T-726, T-727, T-728, T-729, T-732, T-733, T-740, T-741, T-742, T-743, T-744, T-745, T-746, T-747, T-748, T-749, T-750, T-751, T-752, T-753, T-754, T-755, T-756, T-757, T-758, T-760, T-761, T-762, T-763, T-764, T-765, T-766, T-767, T-768, T-769, T-770, T-771, T-772, T-773, T-774, T-775, T-776, T-777, T-778, T-780, T-781, T-782, T-785, T-787, T-789, T-791, T-792, T-793, T-794, T-795, T-796, T-798, T-800, T-802, T-804 |
| `apps/backend/app/services/flags.py` | T-600, T-610, T-614, T-618, T-620, T-625, T-629, T-631, T-640, T-642, T-644, T-645, T-647, T-649, T-650, T-651, T-652, T-654, T-658, T-659, T-660, T-663, T-665, T-670, T-672, T-673, T-675, T-677, T-678, T-680, T-682, T-684, T-686, T-688, T-690, T-691, T-692, T-693, T-694, T-695, T-697, T-710, T-711, T-712, T-714, T-715, T-717, T-719, T-721, T-723, T-724, T-725, T-726, T-727, T-728, T-729, T-732, T-733, T-740, T-741, T-742, T-743, T-744, T-745, T-746, T-748, T-749, T-750, T-751, T-752, T-753, T-754, T-755, T-757, T-758, T-760, T-761, T-762, T-763, T-764, T-765, T-766, T-768, T-770, T-772, T-774, T-775, T-776, T-777, T-778, T-780, T-781, T-782, T-784, T-785, T-787, T-789, T-791, T-792, T-794, T-795, T-796, T-798, T-800, T-802, T-804 |
| `apps/frontend/src/lib/i18n.ts` | T-603, T-610, T-611, T-613, T-615, T-617, T-619, T-622, T-624, T-626, T-628, T-630, T-632, T-633, T-641, T-643, T-644, T-646, T-648, T-649, T-650, T-651, T-653, T-655, T-657, T-658, T-659, T-661, T-662, T-664, T-665, T-671, T-672, T-674, T-676, T-677, T-679, T-681, T-683, T-684, T-685, T-687, T-689, T-690, T-691, T-692, T-693, T-694, T-696, T-711, T-713, T-716, T-718, T-719, T-720, T-722, T-723, T-724, T-725, T-726, T-727, T-730, T-731, T-732, T-733, T-741, T-743, T-744, T-745, T-747, T-749, T-752, T-754, T-756, T-758, T-760, T-761, T-762, T-763, T-764, T-765, T-766, T-767, T-768, T-769, T-770, T-771, T-772, T-773, T-774, T-775, T-776, T-777, T-778, T-779, T-780, T-781, T-783, T-784, T-786, T-788, T-790, T-793, T-797, T-799, T-805 |
| `apps/frontend/src/lib/types.ts` | T-610, T-611, T-613, T-615, T-617, T-619, T-622, T-624, T-626, T-628, T-630, T-632, T-633, T-641, T-643, T-644, T-646, T-648, T-649, T-650, T-651, T-653, T-655, T-657, T-658, T-659, T-661, T-662, T-664, T-665, T-671, T-672, T-674, T-676, T-677, T-679, T-681, T-683, T-684, T-685, T-687, T-689, T-690, T-691, T-692, T-693, T-694, T-696, T-711, T-713, T-716, T-718, T-719, T-720, T-722, T-723, T-724, T-725, T-726, T-727, T-730, T-731, T-732, T-733, T-741, T-743, T-744, T-745, T-747, T-749, T-752, T-754, T-756, T-758, T-760, T-761, T-762, T-763, T-764, T-765, T-766, T-767, T-768, T-769, T-770, T-771, T-772, T-773, T-774, T-775, T-776, T-777, T-778, T-781, T-797, T-805 |
| `apps/backend/app/routers/__init__.py` | T-610, T-618, T-620, T-629, T-631, T-645, T-647, T-654, T-663, T-670, T-672, T-674, T-675, T-678, T-680, T-682, T-684, T-686, T-690, T-691, T-692, T-693, T-694, T-695, T-697, T-710, T-712, T-714, T-715, T-717, T-719, T-721, T-723, T-724, T-725, T-727, T-729, T-732, T-733, T-745, T-748, T-750, T-755, T-760, T-762, T-764, T-766, T-768, T-770, T-772, T-774, T-776, T-777, T-780, T-781, T-782, T-785, T-787, T-789, T-796, T-798, T-802, T-804 |
| `apps/frontend/src/lib/api.ts` | T-619, T-622, T-630, T-632, T-671, T-672, T-674, T-676, T-679, T-681, T-683, T-684, T-687, T-690, T-691, T-692, T-693, T-694, T-696, T-711, T-713, T-716, T-718, T-719, T-720, T-722, T-723, T-724, T-725, T-727, T-730, T-731, T-732, T-733, T-741, T-743, T-744, T-745, T-749, T-752, T-756, T-758, T-760, T-762, T-764, T-765, T-766, T-768, T-770, T-772, T-774, T-776, T-777 |
| `apps/backend/app/models/__init__.py` | T-612, T-620, T-627, T-629, T-631, T-644, T-645, T-660, T-662, T-663, T-670, T-673, T-681, T-682, T-691, T-692, T-695, T-697, T-710, T-715, T-719, T-723, T-724, T-727, T-729, T-733, T-744, T-748, T-750, T-753, T-760, T-763, T-764, T-766, T-776, T-782, T-785, T-789, T-794, T-796, T-798, T-802, T-804 |
| `apps/frontend/src/features/settings/Settings.tsx` | T-600, T-601, T-645, T-732, T-741, T-743, T-744, T-745, T-758, T-762, T-763, T-768, T-771, T-775, T-778, T-799, T-805 |
| `apps/backend/app/config.py` | T-645, T-647, T-649, T-654, T-656, T-658, T-659, T-660, T-663, T-683, T-685, T-686, T-751, T-752, T-757, T-791 |
| `apps/frontend/src/lib/api/models.ts` | T-624, T-659, T-780, T-783, T-786, T-788, T-790, T-791, T-794, T-795, T-799, T-801, T-803 |
| `apps/frontend/src/lib/api/dataset.ts` | T-602, T-641, T-648, T-649, T-653, T-655, T-657, T-658, T-661, T-662, T-664, T-793 |
| `apps/frontend/src/features/project/Models.tsx` | T-659, T-683, T-687, T-780, T-783, T-790, T-791, T-794, T-795, T-801, T-805 |
| `apps/backend/app/models/streams.py` | T-670, T-673, T-675, T-678, T-680, T-688, T-690, T-694, T-723, T-728 |
| `apps/backend/app/schema/streams.py` | T-670, T-675, T-678, T-680, T-688, T-690, T-694, T-714, T-723, T-728 |
| `apps/frontend/src/lib/api/qa.ts` | T-610, T-611, T-613, T-615, T-617, T-626, T-628, T-633, T-646 |
| `apps/backend/app/schema/dataset.py` | T-611, T-618, T-633, T-640, T-647, T-649, T-725, T-727, T-761 |
| `apps/backend/app/routers/images.py` | T-614, T-631, T-647, T-649, T-660, T-662, T-692, T-727, T-728 |
| `apps/backend/app/schema/identity.py` | T-618, T-640, T-733, T-740, T-742, T-747, T-762, T-768, T-777 |
| `apps/frontend/src/features/streams/StreamDetail.tsx` | T-676, T-677, T-681, T-690, T-694, T-711, T-720, T-730, T-731 |
| `apps/backend/app/routers/training.py` | T-642, T-658, T-659, T-770, T-780, T-798, T-800, T-802 |
| `apps/frontend/src/routes/project/ops.routes.tsx` | T-718, T-719, T-722, T-723, T-724, T-725, T-726, T-727 |
| `apps/frontend/src/features/editor/Editor.tsx` | T-615, T-626, T-632, T-644, T-648, T-692, T-749 |
| `apps/frontend/tests/nav.test.mjs` | T-619, T-622, T-671, T-679, T-733, T-752, T-756 |
| `apps/backend/app/handlers/training.py` | T-642, T-644, T-659, T-663, T-794, T-798, T-802 |
| `apps/backend/app/routers/workspaces.py` | T-645, T-740, T-741, T-742, T-744, T-745, T-747 |
| `apps/backend/app/routers/streams.py` | T-671, T-675, T-677, T-680, T-690, T-694, T-728 |
| `apps/frontend/src/lib/nav/registry.ts` | T-671, T-713, T-733, T-752, T-756, T-765, T-766 |
| `apps/backend/app/schema/__init__.py` | T-688, T-714, T-725, T-746, T-755, T-782, T-798 |
| `apps/frontend/src/lib/nav/project/ops.ts` | T-718, T-719, T-722, T-723, T-724, T-725, T-727 |
| `apps/backend/app/models/project.py` | T-618, T-640, T-647, T-649, T-727, T-748 |
| `apps/backend/app/models/identity.py` | T-618, T-640, T-733, T-740, T-742, T-747 |
| `apps/frontend/src/routes/workspace.routes.tsx` | T-671, T-733, T-752, T-756, T-765, T-766 |
| `apps/backend/app/streams/manager.py` | T-673, T-677, T-680, T-690, T-694, T-695 |
| `apps/backend/app/worker.py` | T-674, T-714, T-757, T-772, T-795, T-798 |
| `apps/frontend/src/features/project/Train.tsx` | T-684, T-685, T-780, T-799, T-801, T-803 |
| `apps/frontend/src/routes/public.routes.tsx` | T-716, T-764, T-765, T-772, T-773, T-797 |
| `apps/frontend/src/features/project/ProjectSettings.tsx` | T-610, T-630, T-632, T-691, T-696 |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | T-643, T-644, T-653, T-658, T-664 |
| `apps/backend/app/adapters/vlm_ad.py` | T-644, T-645, T-654, T-663, T-665 |
| `apps/frontend/src/features/streams/Streams.tsx` | T-671, T-672, T-674, T-689, T-694 |
| `apps/backend/app/schema/training.py` | T-684, T-686, T-780, T-782, T-798 |
| `apps/backend/app/models/training.py` | T-684, T-686, T-780, T-782, T-798 |
| `apps/backend/app/routers/runs.py` | T-781, T-791, T-794, T-795, T-800 |
| `apps/frontend/src/index.css` | T-603, T-754, T-756, T-797 |
| `apps/backend/app/routers/quality.py` | T-610, T-614, T-616, T-625 |
| `apps/backend/app/services/labeling_ops.py` | T-611, T-612, T-633, T-748 |
| `apps/backend/app/routers/labeling.py` | T-611, T-612, T-627, T-633 |
| `apps/frontend/src/features/project/QA.tsx` | T-617, T-628, T-646, T-662 |
| `apps/backend/app/handlers/insights.py` | T-647, T-649, T-654, T-658 |
| `apps/frontend/src/features/project/Dataset.tsx` | T-648, T-649, T-655, T-665 |
| `apps/backend/app/routers/insights.py` | T-650, T-651, T-665, T-792 |
| `apps/frontend/src/lib/api/insights.ts` | T-650, T-651, T-665, T-792 |
| `apps/backend/app/handlers/__init__.py` | T-683, T-685, T-686, T-791 |
| `apps/frontend/src/features/governance/Privacy.tsx` | T-741, T-760, T-761, T-764 |
| `apps/backend/app/routers/compliance.py` | T-750, T-751, T-752, T-753 |
| `apps/frontend/src/features/trust/TrustCentre.tsx` | T-765, T-774, T-775, T-779 |
| `apps/backend/app/models/incidents.py` | T-766, T-772, T-773, T-775 |

## Cards

| Task | Title | BEYOND rows | Hours | R7 | Depends on |
| --- | --- | --- | --- | --- | --- |
| [T-600](T-600.md) | One message catalogue and a real language switch | G5.22 | 3 | no | none (it lands before every other wave-F screen, which needs its plumbing) |
| [T-601](T-601.md) | Thai dates, numbers and the count formatters every screen uses | G5.22 | 2.5 | no | T-600 (the locale preference and `localeTag()`) |
| [T-602](T-602.md) | Exports and documents speak the same language as the screen | G5.22 | 2.5 | no | T-600 (catalogue), T-601 (formatters) |
| [T-603](T-603.md) | Thai typography under real strings: no stretch, no mid-word cut | G5.22 | 2.5 | no | T-600 (catalogue), T-601 (formatters), T-473 (`.clamp-2`, `lib/text.ts`) |
| [T-610](T-610.md) | Choose a quality metric and threshold per class | G1.17 | 3 | no | T-600 (the message catalogue every new string is keyed into) |
| [T-611](T-611.md) | Let a reviewer overrule a consensus majority | G1.1 | 3 | no | none (extends the shipped `task_23` surface) |
| [T-612](T-612.md) | Seed the answer key into a batch at a rate | G1.2 | 3 | no | T-610 (the per-class threshold the score uses) |
| [T-613](T-613.md) | Show the answer-key pool and every attempt | G1.2 | 2.5 | no | T-612 (the pool routes and the attempt history), T-600 (the message catalogue) |
| [T-614](T-614.md) | Score a submission with three attempts and hints | G1.3 | 3 | no | T-610 (per-class thresholds), T-612 (the attempt log the cap counts) |
| [T-615](T-615.md) | Ask for the score before an image goes to review | G1.3 | 2.5 | no | T-614 (the score route), T-600 (the message catalogue) |
| [T-616](T-616.md) | Measure agreement per class and swapped pairs | G1.4 | 3 | no | T-610 (the per-class threshold the report scores at) |
| [T-617](T-617.md) | Put agreement, swaps and reviewers on one screen | G1.4 | 2.5 | no | T-616 (the report route), T-600 (the message catalogue) |
| [T-618](T-618.md) | Give every image a priority, a stage and a cap | G1.5 | 3 | no | none (the queue is the base the stage graph in T-620 builds on) |
| [T-619](T-619.md) | Open a queue instead of hunting board cards | G1.5 | 2.5 | no | T-618 (the queue API), T-600 (the message catalogue) |
| [T-620](T-620.md) | Define the label path as named stages | G1.6 | 2.5 | no | T-618 (`Image.stage` and the queue read the same field), T-610 (the shared threshold vocabulary) |
| [T-621](T-621.md) | Move an image along the stage path | G1.6 | 3 | no | T-620 (the graph), T-618 (the queue rows it moves) |
| [T-622](T-622.md) | Draw the label path and publish it | G1.6 | 3 | no | T-620 (the graph), T-621 (move and reroute), T-600 (the message catalogue) |
| [T-623](T-623.md) | Give a tracked object an identity and an exit | G1.9 | 3 | no | none (extends `task_22` and `services/video.py`) |
| [T-624](T-624.md) | List the tracks beside the video timeline | G1.9 | 2.5 | no | T-623 (the track routes), T-600 (the message catalogue) |
| [T-625](T-625.md) | Show what disagrees with the answer key | G1.10 | 2.5 | yes | T-610 (per-class thresholds), T-614 (the matcher this extends) |
| [T-626](T-626.md) | Review an image against the answer key | G1.10 | 3 | no | T-625 (the conflicts route), T-600 (the message catalogue) |
| [T-627](T-627.md) | Score a labeler on a trial set before live work | G1.11 | 3 | yes | T-612 (the approved answer-key pool), T-614 (the matcher and attempt log), T-625 (per-class conflict rows) |
| [T-628](T-628.md) | Read a trial scorecard before hiring | G1.11 | 2.5 | no | T-627 (the trial routes), T-600 (the message catalogue) |
| [T-629](T-629.md) | Run a customer's checker when a label is saved | G1.12 · owner-gated | 3 | yes | T-611 (a label event exists to trigger on), T-610 (the class vocabulary the payload uses) |
| [T-630](T-630.md) | Install and watch an extension package | G1.12 · owner-gated | 2.5 | no | T-629 (the extension routes), T-600 (the message catalogue) |
| [T-631](T-631.md) | Store the label form as a document | G1.13 | 3 | no | none (annotations are already free JSON on `Image`) |
| [T-632](T-632.md) | Build the form and render it in the editor | G1.13 | 3 | no | T-631 (the form document and its validation), T-600 (the message catalogue) |
| [T-633](T-633.md) | Account for hours per stage and objects per hour | G1.16 | 3 | no | T-618 (`Image.stage`, the field time is attributed to), T-620 (the stage vocabulary), T-600 (the message catalogue) |
| [T-640](T-640.md) | Store a prompt pack on the class, apply its exclusions | G4.1 | 3 | yes | none (it lands the egress consent seam every later VLM card reads) |
| [T-641](T-641.md) | Edit the class pack, and build classes from a list | G4.1 | 3 | no | T-640 (the pack column, validation and collision rule) |
| [T-642](T-642.md) | Confidence bands, the escalation threshold, per-band counts | G4.3 | 3 | no | none (independent of the prompt pack; land after T-640 so `handlers/training.py` stays linear) |
| [T-643](T-643.md) | The review policy panel and two queues on the board | G4.3 | 2.5 | no | T-642 (the bands, the preview totals, the `bucket=review` tag) |
| [T-644](T-644.md) | Keep a doubted box, flag it, store the crop | G4.4 | 3 | yes | T-640 (the egress gate) and T-642 (the image outcome this verdict rides on) |
| [T-645](T-645.md) | Judge rubric: verdict, reason and score per label | G4.5 | 3 | yes | T-640 (the egress gate), T-644 (the verdict shape a judge row sits beside) |
| [T-646](T-646.md) | A Judge tab with a rubric picker and a results table | G4.5 | 2.5 | no | T-645 (the rubric engine, the runs and their scope shapes) |
| [T-647](T-647.md) | Question sets that answer into per-image attributes | G4.6 | 3 | yes | T-645 (the egress gate and the adapter call pattern) |
| [T-648](T-648.md) | Question set editor, answer columns and the filter chip | G4.6 | 2.5 | no | T-647 (the question store, the answer job and the `attr` filter) |
| [T-649](T-649.md) | Describe a batch: caption and keywords become tags | G4.7 | 2.5 | yes | T-645 (the egress gate) |
| [T-650](T-650.md) | Named clusters on the map, with lasso-to-label | G4.8 | 3 | no | none (reads the feature cache `services/insights_embedding.py` already writes) |
| [T-651](T-651.md) | Per-class coverage and gap report with targets | G4.9 | 3 | no | T-650 (cluster membership, for "missing from N clusters") |
| [T-652](T-652.md) | Margin sampling, a per-class floor and a stated budget | G4.10 | 3 | no | none (the engine, the cap and the pick batch already ship) |
| [T-653](T-653.md) | The active-learning card: reasons, cap and budget | G4.10 | 2.5 | no | T-652 (reasons, floor, exploration and the budget line) |
| [T-654](T-654.md) | A discovery sweep that names classes nobody asked for | G4.11 | 3 | yes | T-645 (the egress gate and the constrained-answer pattern) |
| [T-655](T-655.md) | The Discover objects panel: rank, inspect, promote | G4.11 | 2.5 | no | T-654 (the sweep, its crops and the ignore list) |
| [T-656](T-656.md) | Track a concept from one phrase, with stable ids | G4.12 | 3 | no | none (reuses `services/track.py` and the `task_22` video surface) |
| [T-657](T-657.md) | The track list: review a track as a unit | G4.12 | 2.5 | no | T-656 (the track routes, the ids and the delete action) |
| [T-658](T-658.md) | A disagreement queue between two auto-label models | G4.13 | 3 | yes | none (reuses `resolve()` and the image rows the batch already scopes) |
| [T-659](T-659.md) | Teacher → student: agreement table and a promotion gate | G4.14 | 3 | no | T-644 (the source and verdict stamps on a teacher label) |
| [T-660](T-660.md) | Synthetic fills for a thin class, with provenance | G4.15 | 3 | no | T-651 (the thin-class entry point and its target) |
| [T-661](T-661.md) | The Add examples dialog: method, preview, provenance | G4.15 | 2.5 | no | T-660 (the build job, the recipes and the tags) |
| [T-662](T-662.md) | Harvest rejected boxes as hard negatives | G4.16 | 2.5 | no | T-644 (the `box_checks` rows and their crops) |
| [T-663](T-663.md) | A labelling job the agent plans, trials, then runs | G4.17 | 3 | yes | T-645 (the egress gate), T-642 (the review bands the plan escalates with) |
| [T-664](T-664.md) | The new-job sheet: write, trial, approve, report | G4.17 | 2.5 | no | T-663 (the plan, trial, approve and report endpoints) |
| [T-665](T-665.md) | Ask the dataset a structural question in words | G4.18 | 3 | yes | T-645 (the egress gate and the constrained-answer pattern) |
| [T-670](T-670.md) | Give a plant sites, lines and stations | G3.2 | 3 | no | none (every later station card attaches here) |
| [T-671](T-671.md) | A station page that owns its cameras and model | G3.2 | 3 | no | T-670 (sites, lines, stations, camera attachment and the station counts) |
| [T-672](T-672.md) | Discover cameras and prove the password first | G3.1 | 3 | yes | none (it extends the existing stream create dialog; `Streams.tsx` is its only screen) |
| [T-673](T-673.md) | Spool events to disk before the quota drops them | G3.7 | 3 | no | T-670 (a spooled event names its station, so the drained row is attributable) |
| [T-674](T-674.md) | Drain the spool and show what is buffered | G3.7 | 3 | no | T-673 (the spool table, the writer and the ceiling policy) |
| [T-675](T-675.md) | Record a verdict with a reason code and a piece id | G3.3 | 3 | no | T-670 (a verdict names its station and takes the station's reason codes) |
| [T-676](T-676.md) | An operator screen for one gesture per piece | G3.3 | 2.5 | no | T-675 (the verdict route and the reason list), T-674 (`SpoolBadge` for the local-only notice) |
| [T-677](T-677.md) | Let a rule follow a production schedule | G3.4 | 3 | no | T-670 (the optional shift template is stored on the station) |
| [T-678](T-678.md) | Group alarms across cameras with an owner and a snooze | G3.5 | 3 | no | T-670 (a group names its station, so four cameras on one cell collapse and four lines do not) |
| [T-679](T-679.md) | A queue screen that acks, assigns and snoozes | G3.5 | 3 | no | T-678 (grouping, ack, assign and snooze), T-670 (the station a group names) |
| [T-680](T-680.md) | Assemble an evidence clip with pre- and post-roll | G3.6 | 3 | no | T-670 (a clip names its station in the event payload), T-675 (a verdict travels with the clip) |
| [T-681](T-681.md) | Hold a clip as evidence past retention | G3.6 | 2.5 | no | T-680 (the clip file and its 409 shortfall contract) |
| [T-682](T-682.md) | Pin a model build to the device it was built for | G3.8 | 2.5 | no | T-670 (a device serves a station, and the station page links the pairing) |
| [T-683](T-683.md) | Replay a golden set before a build may serve | G3.8 | 3 | no | T-682 (the builds, their profiles and the device pairing) |
| [T-684](T-684.md) | Give a training run a deployment target and a budget | G3.9 | 2.5 | no | T-682 (the device families and their TRT/CUDA bands are the same vocabulary) |
| [T-685](T-685.md) | Pick a configuration from measured accuracy and latency | G3.9 | 3 | no | T-684 (the target profile and the budget on a run) |
| [T-686](T-686.md) | Prune and quantise a model with a measured delta | G3.10 | 3 | no | T-682 (the build path and its profile), T-684 (the target the result is judged against) |
| [T-687](T-687.md) | Read the optimisation report and compare with production | G3.10 | 3 | no | T-686 (the optimise job and its report), T-682 (the build profile it names) |
| [T-688](T-688.md) | Decide what the line does when the model is down | G3.11 | 3 | yes | T-670 (a station owns the outputs), T-673 (a spooled event still counts as "the model was working") |
| [T-689](T-689.md) | Show and test the fault policy for a station | G3.11 | 2.5 | yes | T-688 (the policy routes, the watchdog and the fault rows), T-671 (the station page that reads the banner) |
| [T-690](T-690.md) | Decode a barcode or QR into a checked lot code | G3.12 | 3 | no | T-670 (a code rule belongs to a station's camera), T-675 (a verdict names the piece the code read) |
| [T-691](T-691.md) | Verify printed text against an expected value | G3.13 | 2.5 | no | T-670 (a check is registered per station and field) |
| [T-692](T-692.md) | Measure in millimetres against a tolerance band | G3.14 | 3 | no | T-671 (the station page and its calibration section), T-670 (the station the scale belongs to) |
| [T-693](T-693.md) | Read first-pass yield per shift and station | G3.15 | 3 | no | T-670 (station and shift windows), T-675 (the verdicts that make a yield) |
| [T-694](T-694.md) | Guard a camera against a drifted scene | G3.16 | 2.5 | no | T-670 (a drift belongs to a station's camera), T-680 (the clamp-and-cooldown pattern this reuses) |
| [T-695](T-695.md) | A versioned event envelope with a dead-letter queue | G3.17 | 3 | yes | T-670 (site/line/station in the envelope), T-675 (verdict and reason in the envelope) |
| [T-696](T-696.md) | Publish events to a plant broker with a delivery log | G3.17 | 3 | yes | T-695 (the envelope, the sink model, the dead-letter and the replay) |
| [T-697](T-697.md) | Pair a device that sends metadata instead of pixels | G3.18 · owner-gated | 3 | yes | T-695 (the envelope shape a device reuses), T-670 (a device serves a station) |
| [T-710](T-710.md) | Bind every disposition to a lot that survives the audit | G6.1 | 3 | no | T-670 (a unit is inspected at a station), T-675 (the verdict vocabulary this record extends) |
| [T-711](T-711.md) | The lot bar: OK, NG or rework on the station screen | G6.1 | 2.5 | no | T-710 (the lot routes), T-600 (the message catalogue), T-601 (date and count formatters) |
| [T-712](T-712.md) | First-pass yield and the defect Pareto by lot and shift | G6.2 | 3 | no | T-710 (the dispositions), T-670 (line and station), T-693 (the shift windows and their yield definition) |
| [T-713](T-713.md) | A yield board with a Pareto and a lot drill-down | G6.2 | 3 | no | T-712 (the yield routes), T-600 (catalogue), T-601 (date, count and percent formatters) |
| [T-714](T-714.md) | LINE evidence with an acknowledgement ladder | G6.7 | 3 | yes | T-670 (who is on shift for tier two); the LINE channel it extends ships in `task_33` |
| [T-715](T-715.md) | Pair a panel to a station and boot it in Thai | G6.5 | 3 | yes | T-670 (the station and its line), T-710 (the lot the panel is inspecting), T-690 (the lot code it scans) |
| [T-716](T-716.md) | The glove-first kiosk: one instruction, two targets | G6.5 | 3 | no | T-715 (pairing and the boot payload), T-711 (the disposition vocabulary it presents) |
| [T-717](T-717.md) | One step installs a vertical pack's classes and station | G6.6 | 3 | no | T-640 (the class prompt field the pack writes), T-670 (the station it creates), T-250 (the model family the station names) |
| [T-718](T-718.md) | The pack gallery: what it installs, item by item | G6.6 | 2.5 | no | T-717 (the catalogue and install route), T-600 (catalogue copy) |
| [T-719](T-719.md) | A shift handover brief the outgoing shift can send | G6.4 | 3 | yes | T-712 (yield so far), T-710 (open NG and rework), T-714 (the acknowledgement state it counts) |
| [T-720](T-720.md) | Acknowledge an incident and edit the ladder | G6.7 | 2.5 | no | T-714 (the ack state and the escalation policy), T-600 (catalogue), T-601 (dates) |
| [T-721](T-721.md) | One document sheet engine and the safety summary | G6.8 | 3 | no | T-601 (dates and counts), T-602 (the locale of a generated document), T-675 (the verdict vocabulary the incident table prints) |
| [T-722](T-722.md) | Preview the daily safety sheet and sign it | G6.8 | 2.5 | no | T-721 (the sheet route and its supervisor gate), T-600 (catalogue), T-601 (dates) |
| [T-723](T-723.md) | Planogram slots and a shelf-gap exception list | G6.10 · owner-gated | 3 | no | T-670 (the station the bay belongs to), T-711 (the disposition vocabulary a gap is not) |
| [T-724](T-724.md) | Read tags against a price master and list mismatches | G6.11 | 3 | no | T-602 (the CSV writer conventions), `task_32` (the OCR payload this card reads) |
| [T-725](T-725.md) | A grading station that measures size and assigns a grade | G6.12 · owner-gated | 3 | no | T-710 (the lot unit the grade is stored on), T-670 (the station), T-602 (document locale conventions) |
| [T-726](T-726.md) | An exporter lot report with grade mix and photographs | G6.13 | 3 | no | T-721 (the one document engine), T-710 (the lot and its units), T-725 (the grades the mix counts) |
| [T-727](T-727.md) | Field capture that queues offline and syncs later | G6.14 | 3 | no | none (it extends the shipped upload and hash-check path in `routers/images.py`; no station, lot or new transport) |
| [T-728](T-728.md) | Plate blur, static masks and a fail-closed policy | G6.16 | 3 | yes | T-680 (the clip the export policy governs), T-690 (a plate read is the same optional-driver shape) |
| [T-729](T-729.md) | An evidence package with a hash manifest and a cover | G6.15 | 3 | yes | T-728 (the redaction policy the package honours), T-680 (the clip), T-681 (the hold), T-721 (the cover sheet) |
| [T-730](T-730.md) | The evidence dialog: window, items and redaction | G6.15 | 2.5 | no | T-729 (the package routes), T-728 (the export policy it offers), T-721 (the cover sheet it previews) |
| [T-731](T-731.md) | Camera privacy controls and the export choice | G6.16 | 2.5 | no | T-728 (the policy fields and the preview route), T-730 (the export choice in the evidence dialog), T-600 (catalogue) |
| [T-732](T-732.md) | An offline licence file that verifies on the box | G6.20 · owner-gated | 3 | yes | none (a deployment-wide state; `apps/inference` and `deploy/` are the install surfaces it documents) |
| [T-733](T-733.md) | A partner console: children, a pool and a statement | G6.22 · owner-gated | 3 | yes | T-430 (the tenancy model it must not fork), T-670 (the camera count a licence is measured in) |
| [T-740](T-740.md) | Session policy store enforced at refresh and reuse | G5.3 | 3 | yes | none (the screen is T-743; step-up is T-741) |
| [T-741](T-741.md) | Step-up re-authentication before destructive actions | G5.3 | 3 | yes | T-740 (the same sign-in policy store; a step-up ticket is bounded by it) |
| [T-742](T-742.md) | Office and VPN address rules with a named refusal | G5.3 | 2.5 | yes | T-740 (the same policy surface and admin gate) |
| [T-743](T-743.md) | Sign-in policy screen with live consequence lines | G5.3 | 3 | yes | T-740 (policy + member-session routes), T-741 (the step-up sheet it reuses), T-742 (the range rules) |
| [T-744](T-744.md) | Ownership transfer with two confirmations and one audit row | G5.4 | 3 | yes | T-741 (the step-up sheet gates the hand-over) |
| [T-745](T-745.md) | Offboarding sweep: everything that depends on a member | G5.4 | 3 | yes | T-744 (both edit `routers/workspaces.py`; the sweep is the second half of the same flow) |
| [T-746](T-746.md) | Hash chain over the audit rows and a verify route | G5.5 | 3 | yes | none (T-747 renders it and adds the floor) |
| [T-747](T-747.md) | Retention floor no one can lower, and the Integrity tab | G5.5 · owner-gated | 3 | yes | T-746 (the chain and its verify route) |
| [T-748](T-748.md) | Per-image revisions and an object-scoped history route | G5.6 | 3 | no | none (T-749 renders it) |
| [T-749](T-749.md) | History rail: field deltas and restore as a new revision | G5.6 | 3 | no | T-748 (the revisions and the two routes) |
| [T-750](T-750.md) | DSAR case object with a 30-day statutory clock | G5.9 · owner-gated | 2.5 | yes | T-744 (the `models/compliance.py` module it appends to) |
| [T-751](T-751.md) | Find and export one person: scoped search and bundle | G5.9 · owner-gated | 3 | yes | T-750 (the case object and the router it appends to) |
| [T-752](T-752.md) | Erase one person and print a signed certificate | G5.9 · owner-gated | 3 | yes | T-751 (find and export), T-750 (the case), T-744 (the `Members` sheet patterns it reuses) |
| [T-753](T-753.md) | Processing register rows, transfers and consent records | G5.10 · owner-gated | 3 | yes | T-750 (the compliance router), T-752 (the Compliance page's first tab) |
| [T-754](T-754.md) | Register screen and the export an auditor takes away | G5.10 · owner-gated | 3 | yes | T-753 (the routes), T-752 (the Compliance page shell) |
| [T-755](T-755.md) | Thai invoice object: VAT lines and dry-run numbering | G5.16 · owner-gated | 3 | yes | T-412 (the `BillingInvoice` row and `pricing.py` the plan prices live in) |
| [T-756](T-756.md) | The tax-invoice document, print-first and draft-marked | G5.16 · owner-gated | 3 | yes | T-755 (the invoice row and its satang totals), T-754 (the print stylesheet block) |
| [T-757](T-757.md) | PromptPay and transfer instructions under a mock provider | G5.16 · owner-gated | 2.5 | yes | T-755 (the invoice row and `due_at`), T-412 (the mock provider boundary) |
| [T-758](T-758.md) | Invoice request, dunning clock and credit notes in one list | G5.16 · owner-gated | 3 | yes | T-755 (the invoice rows), T-756 (the document), T-757 (the payment instructions and reminders) |
| [T-760](T-760.md) | Retention rules a customer writes, one per data class | G5.7 · owner-gated | 3 | yes | none (it is the base T-761 previews and freezes) |
| [T-761](T-761.md) | Preview a sweep, then freeze a project under hold | G5.7 · owner-gated | 3 | yes | T-760 (the rules the preview evaluates) |
| [T-762](T-762.md) | A sandbox that is a mode, behind a driver seam | G5.8 | 3 | yes | none (it defines the seam T-763 fills) |
| [T-763](T-763.md) | Test keys, a refused attach, a signed promotion | G5.8 | 3 | yes | T-762 (the environment column and the driver) |
| [T-764](T-764.md) | A sub-processor register with an objection window | G5.11 · owner-gated | 3 | yes | none (the trust page T-765 links to it) |
| [T-765](T-765.md) | A trust page that says what is not certified | G5.12 · owner-gated | 3 | yes | T-764 (the register it links to), the DPA route that already ships |
| [T-766](T-766.md) | An incident with a 72-hour clock and a scope count | G5.13 · owner-gated | 3 | yes | none (T-767 drafts and sends from it) |
| [T-767](T-767.md) | Draft the controller notice, send it, keep the evidence | G5.13 · owner-gated | 3 | yes | T-766 (the incident, its clock and its scope count) |
| [T-768](T-768.md) | A storage driver seam and an honest "not available" | G5.15 · owner-gated | 3 | yes | none (T-769 fills the form behind it) |
| [T-769](T-769.md) | Connect a bucket, prove a write, and hold a key reference | G5.15 · owner-gated | 3 | yes | T-768 (the driver seam, the columns and the mode route) |
| [T-770](T-770.md) | A per-project budget that refuses before it spends | G5.17 | 3 | no | none (T-771 renders it) |
| [T-771](T-771.md) | Show the cost before the click, and who can raise the cap | G5.17 | 2.5 | no | T-770 (the budget routes and the estimate) |
| [T-772](T-772.md) | A public status page fed by probes we already compute | G5.18 · owner-gated | 3 | yes | T-766 (the incident model its banner reads) |
| [T-773](T-773.md) | Incident history, subscribers and the postmortem | G5.18 · owner-gated | 2.5 | yes | T-766 (the incident record), T-772 (the page and the sampler) |
| [T-774](T-774.md) | Measure uptime, and say when there is not enough | G5.19 · owner-gated | 3 | yes | T-772 (the samples), T-765 (the trust page section) |
| [T-775](T-775.md) | A credit claim that exists only once a schedule does | G5.19 · owner-gated | 2.5 | yes | T-774 (the measured month), T-765 (the page it sits on) |
| [T-776](T-776.md) | One help panel: what's new, docs, a report | G5.20 | 3 | yes | none (it opens beside every screen) |
| [T-777](T-777.md) | A checklist that advances only on real work | G5.21 | 3 | no | none (T-778 reads the same state) |
| [T-778](T-778.md) | Who actually labels, and who never logged in | G5.21 | 2.5 | yes | T-777 (the same workspace state and the counts helper) |
| [T-779](T-779.md) | Keyboard resize, a skip link, and a failing gate | G5.24 | 3 | no | T-490 (the scan harness), T-765 (the trust page that carries the statement), T-762 (it edits the same layout file) |
| [T-780](T-780.md) | One run keeps its whole configuration | G2.2 | 3 | no | none (it is the base every other G2 card reads) |
| [T-781](T-781.md) | Every run as one sortable ledger row | G2.3 | 3 | no | T-780 (the configuration columns come from the stored snapshot) |
| [T-782](T-782.md) | Promotion becomes a request with an approver | G2.4 | 2.5 | no | none (the alias pointer and event table already exist) |
| [T-783](T-783.md) | The promotion queue a second person answers | G2.4 | 2.5 | no | T-782 (the request contract and its routes) |
| [T-784](T-784.md) | A run node that says what went in and can be re-run | G2.5 | 3 | no | T-780 (the configuration and the `?fromModel=` seeding it exposes) |
| [T-785](T-785.md) | A slice keeps its file list, saved and re-runnable | G2.7 | 3 | no | none (evaluation detections and the manifest already exist) |
| [T-786](T-786.md) | Click a slice and land on the images to relabel | G2.7 | 2.5 | no | T-785 (the slice, saved-slice and batch routes) |
| [T-787](T-787.md) | Score the hold-out with the duplicates removed | G2.8 | 3 | no | none (pHash grouping and evaluation already ship) |
| [T-788](T-788.md) | The leak chip and the two numbers side by side | G2.8 | 2.5 | no | T-787 (the audit route and the cleaned-split setting) |
| [T-789](T-789.md) | A model card that ships beside the weights | G2.6 | 3 | no | T-785 (slice numbers), T-787 (the audited hold-out) for the auto-filled facts only |
| [T-790](T-790.md) | Write the card on the model page | G2.6 | 2.5 | no | T-789 (the card contract, its publish rule and the bundle route) |
| [T-791](T-791.md) | Answer "how fast on our box" with a per-format table | G2.11 | 3 | no | T-780 (benchmark rows sit beside the run's configuration) |
| [T-792](T-792.md) | Coverage: the conditions this data cannot separate | G2.9 | 3 | no | none (the embedding job and its 2-D projection already ship) |
| [T-793](T-793.md) | Work the suspect queue in batches, and reach Train from it | G2.10 | 2 | no | none (queue, ranking, verdicts and precision all ship behind `task_28`) |
| [T-794](T-794.md) | Per-run host telemetry, not just loss curves | G2.15 | 3 | no | none (the GPU ledger already samples used VRAM and the holder) |
| [T-795](T-795.md) | A failed run explains itself and retries unchanged | G2.14 | 3 | no | T-780 (`?fromModel=` restores the arguments the retry needs) |
| [T-796](T-796.md) | A report block document with a public link | G2.16 | 3 | yes | T-781 (the runs block reads the ledger), T-785 (the slice block) |
| [T-797](T-797.md) | Build the report, print it as a PDF | G2.16 | 3 | yes | T-796 (the report contract, publish and the public route) |
| [T-798](T-798.md) | Pools, priorities and a quota the scheduler enforces | G2.12 | 3 | no | none (the queue, the worker claim and the GPU ledger already ship) |
| [T-799](T-799.md) | The queue page and the pool picker | G2.12 | 3 | no | T-798 (pools, ordering, quota and interrupt routes) |
| [T-800](T-800.md) | Mint a one-run command for the customer's own GPU | G2.13 | 3 | yes | T-798 (the pool a remote runner advertises and claims from) |
| [T-801](T-801.md) | Run on my hardware, and see it in the dashboard | G2.13 | 2.5 | no | T-800 (the mint route, the run token and the state route) |
| [T-802](T-802.md) | A parameter space becomes a set of trial runs | G2.1 · owner-gated | 3 | no | T-780 (each trial stores its own configuration), T-781 (the trial rows are ledger rows) |
| [T-803](T-803.md) | The sweep panel and the trial rows | G2.1 · owner-gated | 3 | no | T-802 (the sweep routes, the estimate and pruning) |
| [T-804](T-804.md) | A narrow extension point for our analysis and theirs | G2.17 · owner-gated | 3 | yes | T-781 (an extension reads ledger fields), T-789 (the card can cite an extension's metric) |
| [T-805](T-805.md) | The Extensions list and the panel slot it fills | G2.17 · owner-gated | 3 | no | T-804 (the registry, validator and run route) |

## Judgment calls

- **A feature is one card unless it has a seam.** 101 features → 171 cards (1.7 per feature): the backlog's own density is 1.3 cards per parity row, and every card here stays inside 3 hours, so a `M` feature that is one screen is one card while `G1.6`, `G3.9` and `G5.9` split schema → service → screen. Nothing is padded and no card hides a 6-hour job.
- **`G5.22` (Thai) is four cards at the head of the wave**, not one `L`: the catalogue and the switch (T-600), the formatters (T-601), exports (T-602) and the typography proof (T-603). Every later band adds keys to the same catalogue, which is why it runs first.
- **BEYOND §4 non-goals still get a card** because the owner directive says every Must, Should and Could of the matrix is planned: `G1.12`, `G2.1`, `G2.17`, `G3.18`, `G6.10`, `G6.12` are written and their Notes open with `Owner-hold:`, so nobody schedules them without overruling §4 first.
- **`G5.1`, `G5.2`, `G5.14` and `G5.23` have no card here.** The first three are owned by parity rows `7-F7.41`, `7-F7.35`, `7-F7.45`; `G5.23` is folded into `G5.22` per BEYOND §1, and this wave does not build a second-locale framework.
- **`G1.1` and `G2.10` are HAVE but carry cards** because their own gap cell names real work (winner override, suspect-queue surface); they are additions to a shipped flow, not a rebuild.
- **Owner-gated cards.** Thai VAT invoicing (T-755–T-758), DSAR and the processing register (T-750–T-754), the audit retention floor (T-747), retention policy and legal hold (T-760–T-761), sub-processor notice (T-764), the trust centre (T-765), breach notice (T-766–T-767), BYO bucket and CMK (T-768–T-769), status/SLA claims (T-772–T-775), the offline licence (T-732) and the partner console (T-733) plan an interface, a mock or a dry run, charge nothing and assert no legal fact.
