# Part 4 — Area 4 Versions, preprocessing, augmentation, export

Gap rows: 32 (23 PARTIAL, 9 MISSING) · Cards: 42 · Hours: 115

Hours are attributed once, to the card's primary row; a row that only shares another row's card shows `—` and that card's hours appear on its primary row. The 14 HAVE rows are protected by the guard lane (`T-001`–`T-007`) and carry no card.

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 4-F4.1 | HAVE | — (guard T-001) | — | — | — |
| 4-F4.2 | HAVE | — (guard T-001) | — | — | — |
| 4-F4.3 | PARTIAL | T-217 | B | S | 3 |
| 4-F4.4 | PARTIAL | T-217, T-218 | B | S | 2.5 |
| 4-F4.5 | PARTIAL | T-219 (+ area 7 trash window) | B | S | 3 |
| 4-F4.6 | MISSING | T-222 | B | S | — |
| 4-F4.7 | PARTIAL | T-222 (+ area 5 train-side lock) | B | S | 3 |
| 4-F4.8 | HAVE | — (guard T-005) | — | — | — |
| 4-F4.9 | HAVE | — (guard T-002) | — | — | — |
| 4-F4.10 | HAVE | — (guard T-002) | — | — | — |
| 4-F4.11 | HAVE | — (guard T-002) | — | — | — |
| 4-F4.12 | PARTIAL | area 2, band T-060–T-119 | — | M | — |
| 4-F4.13 | PARTIAL | T-192, T-198, T-199 | A | M | 8 |
| 4-F4.14 | PARTIAL | T-215, T-216 | B | M | 6 |
| 4-F4.15 | PARTIAL | T-191, T-214 | A/B | S | 4 |
| 4-F4.16 | PARTIAL | T-194, T-220, T-221 | A/B | M | 7 |
| 4-F4.17 | HAVE | — (guard T-003) | — | — | — |
| 4-F4.18 | PARTIAL | T-197, T-198 | A | M | 3 |
| 4-F4.19 | HAVE | — (guard T-003) | — | — | — |
| 4-F4.20 | PARTIAL | T-200 | B | S | 2.5 |
| 4-F4.21 | MISSING | T-202, T-198 | B | M | 3 |
| 4-F4.22 | MISSING | T-201 | B | S | 3 |
| 4-F4.23 | PARTIAL | T-192, T-204, T-205 | B | M | 5.5 |
| 4-F4.24 | MISSING | T-206, T-207 | B | M | 6 |
| 4-F4.25 | PARTIAL | T-203 | B | M | 3 |
| 4-F4.26 | MISSING | T-192, T-195, T-196 | A | M | 5.5 |
| 4-F4.27 | PARTIAL | T-190, T-191, T-193 | A | S | 5.5 |
| 4-F4.28 | HAVE | — (guard T-001) | — | — | — |
| 4-F4.29 | PARTIAL | T-190, T-214 | A/B | S | — |
| 4-F4.30 | PARTIAL | T-208, T-209, T-210, T-215 | B | M | 9 |
| 4-F4.31 | MISSING | T-211, T-215 | B | M | 3 |
| 4-F4.32 | MISSING | T-212, T-213, T-215 | B | M | 5 |
| 4-F4.33 | PARTIAL | T-216 | B | S | — |
| 4-F4.34 | PARTIAL | T-224, T-225 | B | S | 4.5 |
| 4-F4.35 | PARTIAL | T-226, T-227, T-228, T-229 | B | M | 12 |
| 4-F4.36 | HAVE | — (guard T-004) | — | — | — |
| 4-F4.37 | PARTIAL | T-225 | B | S | — |
| 4-F4.38 | MISSING | T-230, T-231 | C | M | 5.5 |
| 4-F4.39 | PARTIAL | area 2, band T-060–T-119 | — | M | — |
| 4-F4.40 | HAVE | — (guard T-006) | — | — | — |
| 4-F4.41 | HAVE | — (guard T-006) | — | — | — |
| 4-F4.42 | MISSING | area 2, band T-060–T-119 | — | M | — |
| 4-F4.43 | PARTIAL | area 2, band T-060–T-119 | — | S | — |
| 4-F4.44 | HAVE | — (guard T-006) | — | — | — |
| 4-F4.45 | HAVE | — (guard T-006) | — | — | — |
| 4-F4.46 | PARTIAL | T-223 (+ area 5 train-side chip) | B | S | 2.5 |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| apps/backend/app/services/recipe.py (owner T-190) | T-190, T-195, T-197, T-204, T-206, T-208, T-209, T-211 |
| apps/backend/app/services/imaging.py (owner T-197) | T-197, T-200, T-201, T-202, T-208, T-209, T-210, T-211, T-212, T-213 |
| apps/backend/app/services/versioning.py (owner T-195) | T-195, T-201, T-202, T-203, T-206, T-213 |
| apps/backend/app/services/tiling.py (owner T-204) | T-204 |
| apps/backend/app/services/exporters.py (owner T-226) | T-226, T-227, T-228, T-229 |
| apps/backend/app/routers/versions.py (owner T-192) | T-191, T-192, T-199, T-216, T-223, T-230 |
| apps/backend/app/handlers/versioning.py (owner T-218) | T-218, T-230 |
| apps/backend/app/config.py | T-190 |
| apps/backend/app/services/flags.py | T-190 (`task_190`), T-217 (`task_217`), T-224 (`task_224`), T-230 (`task_230`) |
| apps/backend/tests/test_versioning_v2.py | T-194, T-217, T-221, T-222 |
| apps/backend/tests/test_r1_cancel_artifacts.py | T-218 (the one `progress` stub gains a parameter) |
| apps/backend/tests/test_versions_export.py (owner T-224) | T-224, T-225, T-230, T-231 |
| apps/backend/tests/test_tiling_version.py | T-204 (one parametrised case per mode) |
| apps/backend/openapi.json + apps/frontend/src/lib/api-types.gen.ts | T-191, T-192, T-223, T-230 (regenerate last on the branch) |
| apps/frontend/src/features/project/Versions.tsx (owner T-194) | T-194, T-217, T-219 — plus area 2's one-line mounts from T-100/T-101/T-134, which must rebase onto T-194's split |
| apps/frontend/src/features/project/versions/VersionWizard.tsx (owner T-194) | T-194, T-196, T-198, T-214, T-215, T-216, T-222 |
| apps/frontend/src/features/project/versions/VersionList.tsx (owner T-217) | T-217 |
| apps/frontend/src/features/project/versions/VersionDetail.tsx (owner T-219) | T-219, T-220, T-221, T-222, T-223, T-224 |
| apps/frontend/src/features/project/versions/steps/PreprocessStep.tsx (owner T-198) | T-198, T-199, T-200, T-201, T-202, T-205, T-207 |
| apps/frontend/src/features/project/versions/steps/SourceStep.tsx (owner T-196) | T-196 |
| apps/frontend/src/features/project/versions/steps/OutputStep.tsx (owner T-214) | T-214 |
| apps/frontend/src/features/project/versions/steps/AugmentStep.tsx (owner T-216) | T-216 |
| apps/frontend/src/features/project/versions/ExportDialog.tsx (owner T-224) | T-224, T-225, T-231, T-226 |
| apps/frontend/src/lib/recipe.ts (owner T-193) | T-193, T-196, T-197, T-200, T-201, T-202, T-204, T-205, T-206, T-207, T-208, T-209, T-210, T-211, T-212, T-213, T-214, T-215 |
| apps/frontend/src/lib/api/dataset.ts | T-191, T-192, T-223, T-231 |
| apps/frontend/src/lib/types.ts | T-192, T-195, T-199, T-216, T-223, T-224, T-231 |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-190 | Recipe contract, pipeline order and plan caps | A | 3 | R3 | no | `apps/backend/app/services/recipe.py` |
| T-191 | Validate version create and expose plan limits | A | 2 | R3 | no | `apps/backend/tests/test_version_recipe_api.py` |
| T-192 | Version preview endpoint: counts, conflicts, sample, tiles | A | 3 | R3 | yes | `apps/backend/app/routers/versions.py` |
| T-193 | Frontend recipe mirror with node-side copy | A | 2.5 | R4 | no | `apps/frontend/src/lib/recipe.ts`, `versions/ConflictList.tsx` |
| T-194 | Split the version screens and build the wizard shell | A | 3 | R4 | no | `versions/VersionWizard.tsx` |
| T-195 | Tag rules select the version's source pool | A | 3 | R3 | no | `apps/backend/app/services/versioning.py` |
| T-196 | Source step: pool counts and the tag-rule matrix | A | 2.5 | R4 | no | `versions/steps/SourceStep.tsx` |
| T-197 | Six resize modes with label-correct geometry | A | 3 | R3 | no | `apps/backend/app/services/imaging.py` |
| T-198 | Preprocessing step: an ordered pipeline | A | 3 | R4 | no | `versions/steps/PreprocessStep.tsx` |
| T-199 | Preview panel with labels drawn on the image | A | 2 | R4 | no | `versions/PreviewPanel.tsx` |
| T-200 | Contrast: stretch, equalise, adaptive | B | 2.5 | R4+R3 | no | `versions/ContrastCard.tsx` |
| T-201 | Static crop by percentage with an overlay | B | 3 | R4+R3 | no | `versions/CropCard.tsx` |
| T-202 | Isolate objects: box crops, detection→classification | B | 3 | R3 | no | `versions/IsolateCard.tsx` |
| T-203 | Null images: keep a percentage, say what null means | B | 3 | R4+R3 | no | `versions/NullPolicyCard.tsx` |
| T-204 | Tiling: grid and fixed-aspect modes | B | 3 | R3 | no | `apps/backend/app/services/tiling.py` |
| T-205 | Tiling card: mode, overlap, padding, tile count | B | 2.5 | R4 | no | `versions/TilingCard.tsx` |
| T-206 | Class surgery: omit, rename, merge | B | 3 | R3 | no | `apps/backend/tests/test_class_surgery.py` |
| T-207 | Class surgery panel with a regex preview | B | 3 | R4 | no | `versions/ClassSurgery.tsx` |
| T-208 | Ordered augmentation list, tiers, parameter table | B | 3 | R3 | no | `apps/backend/tests/test_augment_pipeline.py` |
| T-209 | Geometric augmentations: crop, shear, 90° direction | B | 3 | R3 | no | `apps/backend/tests/test_augment_geometry.py` |
| T-210 | Photometric: hue, camera gain, motion blur | B | 3 | R3 | no | `apps/backend/tests/test_augment_photometric.py` |
| T-211 | Box-level augmentation | B | 3 | R3 | no | `apps/backend/tests/test_augment_in_boxes.py` |
| T-212 | Cutout | B | 2 | R3 | no | `apps/backend/tests/test_augment_cutout.py` |
| T-213 | Mosaic | B | 3 | R3 | no | `apps/backend/tests/test_augment_mosaic.py` |
| T-214 | Output step: multiplier, cap, estimate | B | 2 | R4 | no | `versions/steps/OutputStep.tsx` |
| T-215 | Augmentation catalogue dialog | B | 3 | R4 | no | `versions/AugmentCatalogue.tsx` |
| T-216 | Augmentation step: ordered cards and guidance | B | 3 | R4 | no | `versions/steps/AugmentStep.tsx` |
| T-217 | Version index rows with a delta chip and live states | B | 3 | R4 | no | `versions/VersionList.tsx`, `versions/recipeDigest.ts` |
| T-218 | Version job phases: preprocess, augment, write | B | 2.5 | R3 | no | `apps/backend/app/handlers/versioning.py` |
| T-219 | Version detail plus guarded delete | B | 3 | R4 | no | `versions/VersionDetail.tsx`, `versions/DeleteVersionDialog.tsx` |
| T-220 | "What changed" diff panel | B | 2 | R4 | no | `versions/WhatChanged.tsx` |
| T-221 | Trainings and exports on the version page | B | 2 | R4 | no | `versions/VersionRuns.tsx` |
| T-222 | Recipe summary, the baked-in lock, reuse | B | 3 | R4 | no | `versions/RecipeSummary.tsx` |
| T-223 | Version readiness: blockers and warnings | B | 2.5 | R4+R3 | no | `apps/backend/app/services/versions_ready.py`, `versions/ReadinessList.tsx` |
| T-224 | Export dialog: format chips, download, progress | B | 2.5 | R4 | no | `versions/ExportDialog.tsx`, `tests/test_versions_export.py` |
| T-225 | "Use from code" and round-trip loss notes | B | 2 | R4 | yes | `versions/UseFromCode.tsx` |
| T-226 | Format registry, task filtering, multi-label, CLIP | B | 3 | R3 | no | `apps/backend/app/services/exporters.py` |
| T-227 | Darknet and RetinaNet writers | B | 3 | R3 | no | `apps/backend/tests/test_export_darknet_retinanet.py` |
| T-228 | TFRecord writer | B | 3 | R3 | no | `apps/backend/app/services/tfrecord.py` |
| T-229 | Semantic PNG mask writer | B | 3 | R3 | no | `apps/backend/tests/test_export_png_mask.py` |
| T-230 | Bucket delivery uploader | C | 3 | R3 | yes | `apps/backend/app/services/bucket_sink.py` |
| T-231 | Export destination wiring and storage menu | C | 2.5 | R4+R3 | yes | `versions/ExportDestinationMenu.tsx`, `tests/test_export_destination_api.py` |

## Judgment calls
- 4-F4.12 → area 2 (band T-060–T-119), per the brief's cross-area table; the wizard's step-2 rebalance entry stays untouched here and area 2's card lands the strategies. My cards only pass `rebalance` through `recipe.normalize` unchanged.
- 4-F4.39, 4-F4.42, 4-F4.43 → area 2 (band T-060–T-119) as health-chart work; the exact card ids are the PM's to fill from that area's part index.
- 4-F4.5 → trash window half mapped to area 7 (7-F7.43, "Trash who/when/days-left"); T-219 ships only the consequence + typed-name confirm, because this repo has no trash table and inventing one here would collide with area 7's model.
- 4-F4.7 → the version-side half is T-222 (recipe shown, frozen-at-generation lock); the train-side half (locked recipe rows beside the model picker) is area 5's, band T-250–T-309, and T-222 must not edit `Train.tsx`.
- 4-F4.46 → T-223 owns the readiness endpoint and the version-side list; the S8 Train health chip is area 5's, and T-223's `RULES` table is the shared source for it (stated in the card's notes).
- 4-F4.38 → wave C, not B: the work is connector-adjacent (credentials, outbound write, bucket kinds), which §3 assigns to C even though it is reached from the export dialog.
- 4-F4.15 / 4-F4.29 → split A/B: T-191 is the A-row plumbing (`GET /versions/limits`) so the plan cap is correct from day one; T-214 is the estimate UI.
- 4-F4.33 → no card of its own: the guidance panel is one block inside T-216 (same file, same reviewer), so the row shows `—` hours and lists T-216.
- 4-F4.37 → no card of its own: the round-trip notes live in T-225 beside the code snippet they warn about.
- Guard ids T-001–T-007 are the guard lane's; the HAVE mapping above is by subject (immutability, wizard/recipe contract, preprocessing round-trip, export artefacts, training linkage, analytics cache). T-007 is unclaimed by this area — remap freely if the guard lane numbers them differently.
- Flags: four new keys only — `task_190` (recipe v2 surface), `task_217` (version page v2), `task_224` (export dialog v2), `task_230` (bucket delivery). Every other card states which of these four it hides behind; no card invents its own key.
- `VersionList.tsx` / `VersionDetail.tsx` are created by T-194 as a markup move and immediately owned by T-217 / T-219 so no later card claims them exclusively.
- Foreign-band merges into my files: area 2's T-100 (a route in `routers/versions.py`), T-101 (a rebalance button in `Versions.tsx`), T-134 (mask branches in `versioning.py` and `exporters.py`) all list those files as **Shared**, so no exclusive collision exists. T-194's `Versions.tsx` split must merge first and T-100/T-101/T-134 rebase their one line onto the new container.
