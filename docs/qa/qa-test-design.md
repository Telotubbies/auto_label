---
title: "QA Design: Why Each Test Function Exists"
category: "QA"
order: 20
status: "Verified"
---

## QA Design: Why Each Test Function Exists

| Field | Value |
| --- | --- |
| SDLC Phase | 5 (Testing and QA) |
| Status | Accepted |
| Owner | QA Lead |
| Reviewers | Engineering Team, Tech Lead |
| Audience | Developers, QA, Auditors |
| Last Updated | 2026-09-10 |
| Supersedes | none |

---

## 1. Test Strategy

### 1.1 Archetype and Pyramid Ratio

This project is a CLI tool with logic-dense pure functions and heavy
external dependencies (SAM 3.1 model, GPU, Ultralytics). The archetype is
library / devtools / CLI.

| Level | Ratio | Count | Rationale |
| --- | --- | --- | --- |
| Unit | 80% | 56 tests | Logic lives in pure functions (path sanitization, bbox conversion, split logic, focal loss math, config validation, provenance, label validation) |
| Integration | 15% | 14 tests | Module interactions (checkpoint save/load, model dict structure, ONNX script existence) |
| E2E | 5% | 1 test (skipped) | Full SAM batch on real image (requires WSL venv + GPU + 3.34 GB checkpoint) |
| Static | 5% | 6 tests | Config file scans and source-code security audits (no execution) |

Total: 76 tests collected, 75 passed, 1 skipped.

### 1.2 Case Selection Method

Equivalence classes and boundaries drive case selection, not enumeration:

| Method | Applied To | Example |
| --- | --- | --- |
| Equivalence: valid path | `test_accepts_path_inside_base` | One representative of "path inside base" |
| Equivalence: invalid path | `test_rejects_dotdot_traversal` | One representative of "path outside base" |
| Boundary: empty input | `test_requires_batch_or_input` | Both None = error |
| Boundary: zero-width bbox | `test_min_width_not_zero` | bbox [0,0,0,0] must not collapse |
| Boundary: out-of-range bbox | `test_clips_to_unit_range` | Negative coords must clip to [0,1] |
| Property: determinism | `test_split_is_deterministic` | Same seed = same split (invariant over runs) |
| Property: losslessness | `test_split_is_lossless` | Union of splits = full set (no overlap) |
| Property: focal modulation | `test_focal_loss_reduces_easy_examples` | focal(easy) < bce(easy) (invariant) |

### 1.3 Mutation Score Target

Target: mutation score >= 60% on changed logic-dense files.

The most mutation-sensitive files are:

| File | Mutation Risk | Tests That Bite |
| --- | --- | --- |
| `pipeline_cli._sanitize_path` | High (security boundary) | 5 tests in `test_path_safety.py` |
| `01_prepare_dataset.bbox_to_yolo` | High (math transform) | 4 tests in `test_dataset_prep.py` |
| `focal_patch.FocalBCE` | Medium (loss math) | 3 tests in `test_focal_patch.py` |
| `batch_segment.checkpoint_*` | Medium (state persistence) | 3 tests in `test_sam_batch.py` |

### 1.4 Flake Quarantine Policy

No flaky tests exist in the current suite. The policy if one appears:

1. Quarantine immediately with `pytest.skip` and a tracking bug
2. Root-cause before re-enabling (shared state, timing, network, ordering)
3. Time-boxed: owner + deadline, not `it.skip` forever

The 1 skipped test (TC-01) is not flaky. It is deterministically skipped
because the `sam3` vendored module is not importable on Windows. It runs
in the WSL/Linux venv where the module exists.

---

## 2. Per-Test-Function Rationale

This section explains why each test function exists, what invariant it
protects, and what bug it would catch if the production code changed.

### 2.1 TC-03: Path Traversal (`tests/unit/test_path_safety.py`)

ISO 27001 A.14.1.2 requires input validation at system boundaries. The
`_sanitize_path` function is the security boundary between user-provided
paths and the filesystem. A failure here allows directory traversal attacks.

#### TestSanitizePath (5 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_rejects_dotdot_traversal` | Classic `../../../etc/passwd` attack. If `_sanitize_path` stops calling `resolve()` or drops the `relative_to` check, this fails. | Path must stay inside base dir | Attacker reads arbitrary files |
| `test_rejects_absolute_path_outside_base` | Attacker passes `/etc/shadow` directly. Tests that absolute paths are contained, not just relative ones. | Absolute paths also checked | Attacker bypasses via absolute path |
| `test_accepts_path_inside_base` | Positive case. If `_sanitize_path` becomes too aggressive (rejects valid paths), the pipeline breaks for legitimate users. | Valid paths must pass | Pipeline unusable |
| `test_accepts_path_without_base` | When `base_dir=None`, no containment check. Tests that the function does not crash when base is not provided (used in some CLI paths). | None base = no containment | CLI crashes on optional base |
| `test_rejects_symlink_escape` | Symlink inside base pointing outside. `resolve()` follows symlinks, so the resolved path escapes base. If someone replaces `resolve()` with `absolute()`, this fails. | Symlinks resolved before containment check | Symlink bypass traversal protection |

#### TestResolveInputDir (4 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_rejects_traversal_via_input_path` | User-facing wrapper around `_sanitize_path`. If `resolve_input_dir` stops delegating to `_sanitize_path`, this catches it. | Input path sanitized | Traversal via `--input` flag |
| `test_rejects_traversal_via_batch` | Batch name is joined to base dir. If someone replaces `Path.joinpath` with string concat, `../` in batch name escapes. | Batch name sanitized | Traversal via `--batch` flag |
| `test_requires_batch_or_input` | Boundary case: both None. If the function stops validating "at least one required", the pipeline crashes downstream with a confusing error. | At least one input source | Cryptic NoneType error downstream |
| `test_accepts_valid_batch` | Positive case for batch resolution. If the batch-to-path logic breaks, the pipeline cannot find input images. | Valid batch resolves to dir | Pipeline cannot find images |

#### TestResolveOutputDir (3 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_rejects_traversal_in_sam_mode` | Output path in SAM mode. If output sanitization is removed, attacker writes annotations anywhere. | Output path sanitized | Write annotations to arbitrary dir |
| `test_requires_batch_when_no_output` | Boundary: SAM mode with no output path and no batch. If the default-output logic is removed, the pipeline crashes. | Default output derived from batch | Pipeline crashes on missing output |
| `test_unknown_mode_raises` | Boundary: invalid mode string. If the mode validation is removed, the pipeline silently does nothing. | Mode must be sam/yolo/pred | Silent failure on typo |

### 2.2 TC-04: Focal Patch (`tests/unit/test_focal_patch.py`)

ADR-002 documents the decision to monkey-patch `v8DetectionLoss.bce` with
`FocalBCE`. If the patch silently fails, training falls back to standard
BCE, which underperforms on rare classes (harness, boots). The
`FOCAL_PATCH_APPLIED` flag is the runtime canary.

#### TestFocalPatchApplication (3 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_flag_is_true` | The flag is checked at runtime. If the patch fails silently, the flag stays False and training uses wrong loss. | Patch applied on import | Training uses standard BCE (class imbalance unaddressed) |
| `test_focalbce_class_exists` | If someone renames `FocalBCE` or removes it, the import fails. | Class defined in module | ImportError at training time |
| `test_focalbce_is_nn_module` | `FocalBCE` must be a `nn.Module` so Ultralytics can call it like `self.bce(pred, target)`. If it becomes a plain function, the patch crashes. | Must subclass nn.Module | Patch crashes on `self.bce(...)` call |

#### TestFocalBCEBehavior (3 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_output_shape_matches_input` | `FocalBCE` must return per-element loss (reduction='none') because Ultralytics applies its own reduction. If reduction changes to 'mean', the loss scalar breaks the loss aggregation. | Shape: (N, M) in, (N, M) out | Loss aggregation crashes on shape mismatch |
| `test_focal_loss_reduces_easy_examples` | Core focal loss property: easy examples (high p_t) get lower loss than plain BCE. If the modulating factor `(1-p_t)^gamma` is removed, focal = BCE and the class imbalance fix is gone. | focal(easy) < bce(easy) | Focal loss has no effect (equivalent to BCE) |
| `test_focal_loss_keeps_hard_examples` | Core focal loss property: hard examples retain more loss than easy examples. If the modulating factor is inverted, hard examples get suppressed and the model never learns rare classes. | hard_ratio > easy_ratio | Model ignores hard (rare class) examples |

#### TestV8DetectionLossPatched (1 test)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_bce_is_focalbce_after_patch` | Verifies the patch target (`v8DetectionLoss.__init__`) is callable after patching. Cannot fully instantiate without a model, but confirms the patch did not break the class. | Patched __init__ is callable | Patch corrupts the class |

### 2.3 TC-05: Dataset Split (`tests/unit/test_dataset_prep.py`)

NFR-05 requires training reproducibility with seed=42. FR-23 requires
80/10/10 split. If the split logic changes, training results are not
reproducible and the reported metrics become invalid.

#### TestBboxToYolo (4 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_basic_conversion` | COCO bbox [x,y,w,h] to YOLO [cx,cy,w,h] normalized. If the formula changes (e.g., x instead of x+w/2), all YOLO labels are wrong. | cx = (x + w/2) / img_w | All YOLO labels shifted |
| `test_all_values_in_unit_range` | YOLO format requires [0,1]. If normalization is removed, YOLO training crashes on out-of-range values. | All values in [0, 1] | YOLO training crashes |
| `test_clips_to_unit_range` | Bbox extending beyond image bounds must clip. If clipping is removed, negative or >1 values break YOLO. | Clips to [0, 1] | Out-of-range labels |
| `test_min_width_not_zero` | Zero-width bbox produces zero-area label, which YOLO ignores. The min 0.001 floor prevents silent data loss. | min(w, h) >= 0.001 | Valid objects dropped from training |

#### TestSplitRatios (3 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_split_produces_correct_ratios` | 80/10/10 of 913 = 730/91/92. If the ratio constants change, the split is wrong and metrics are not comparable across runs. | 730/91/92 for n=913 | Split ratios wrong |
| `test_split_is_lossless` | No image in two splits, all images covered. If the slice logic has an off-by-one, images are lost or duplicated. | Splits are disjoint and complete | Images lost or duplicated |
| `test_split_is_deterministic` | Same seed = same split. If `random.seed` is removed or the shuffle order changes, results are not reproducible. | Same seed = same output | Non-reproducible training |

#### TestEndToEndSplitWithSyntheticData (1 test)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_split_no_data_loss` | Uses synthetic COCO data to verify the split covers all images. Catches integration bugs that unit tests on the algorithm alone might miss. | All image IDs in exactly one split | Images dropped during conversion |

### 2.4 TC-06: Oversampling (`tests/unit/test_dataset_prep.py`)

R-01 (class imbalance) is mitigated by oversampling. If the oversampling
multiplier is wrong, rare classes (boots, harness) remain underrepresented
and mAP50 for those classes stays near zero.

#### TestOversamplingLogic (8 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_multiplier_capped_at_10x` | Cap prevents overfitting from excessive duplication. If the cap is removed, a class with 10 images and target 5000 gets 500x duplication. | max multiplier = 10 | Overfitting on rare classes |
| `test_multiplier_under_cap` | Normal case: harness 102 -> target 500 = 4x. If the integer division changes to float, the multiplier is wrong. | 500 // 102 = 4 | Wrong duplication count |
| `test_no_oversample_when_target_met` | If current >= target, no duplication. If this check is removed, already-balanced classes get unnecessary duplication. | Skip when current >= target | Unnecessary duplication |
| `test_oversampling_increases_class_count` | After oversampling, count = original * multiplier. If the loop logic changes (e.g., multiplier instead of multiplier-1 extra copies), the count is wrong. | total = original * multiplier | Wrong final class count |
| `test_oversample_targets_defined` | The `OVERSAMPLE_TARGETS` dict must target boots (class 2) and harness (class 4). If someone removes a target, that class stays imbalanced. | boots and harness targeted | Rare classes stay imbalanced |
| `test_split_ratios_are_80_10_10` | Constants must match the documented 80/10/10. If someone changes the dict, the split is wrong. | {"train": 0.8, "val": 0.1, "test": 0.1} | Wrong split ratios |
| `test_random_seed_is_42` | Seed must be 42 for reproducibility. If someone changes the seed, all prior results are not reproducible. | RANDOM_SEED == 42 | Non-reproducible training |
| `test_coco_to_yolo_mapping_complete` | All 5 COCO category IDs (1-5) must map to YOLO IDs (0-4). If a mapping is missing, that class is silently dropped. | {1,2,3,4,5} -> {0,1,2,3,4} | Class silently dropped from training |

### 2.5 TC-09 + TC-12: Config Static (`tests/unit/test_config_static.py`)

ISO 27001 A.13.1.1 requires network binding controls. MLflow must bind
to 127.0.0.1, not 0.0.0.0. TC-12 ensures setup.py and pipeline_cli.py
agree on the checkpoint path, preventing "file not found" errors.

#### TestMLflowLocalhost (3 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_host_is_localhost` | MLflow must bind to 127.0.0.1. If someone changes it to 0.0.0.0, the tracking server is exposed to the network. | host == "127.0.0.1" | Network-exposed MLflow |
| `test_host_not_wildcard` | Explicit negative check. If the host becomes "0.0.0.0", this fails even if the positive check is removed. | host != "0.0.0.0" | Network-exposed MLflow |
| `test_port_is_int` | Port must be a valid int (1-65535). If someone puts a string in YAML, MLflow crashes at startup. | port is int in valid range | MLflow startup crash |

#### TestCheckpointLocationMatch (4 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_setup_py_uses_correct_path` | setup.py downloads the checkpoint. If the path constant changes, the checkpoint is downloaded to the wrong location. | CKPT_PATH references sam3.1_multiplex.pt in checkpoints/ | Checkpoint in wrong dir |
| `test_pipeline_cli_uses_correct_path` | pipeline_cli.py checks the checkpoint. If the path changes here but not in setup.py, the check always fails. | pipeline_cli references same path | Checkpoint check always fails |
| `test_check_sam_checkpoint_function_matches` | The runtime function must return the same path. If the function builds the path differently, it reports "not found" even when the file exists. | Function returns path with sam3.1_multiplex.pt | False "checkpoint missing" error |
| `test_config_ckpt_path_property_matches` | The Config dataclass property must produce the same path. If the property uses a different base, SAM inference looks in the wrong place. | cfg.ckpt_path == base/checkpoints/sam3.1_multiplex.pt | SAM looks in wrong dir |

### 2.6 TC-10 + TC-11: Security Static (`tests/unit/test_security_static.py`)

ISO 27001 A.14.2.1 (no secrets) and A.14.2.5 (no command injection). These
are static scans because they audit source files, not runtime behavior.

#### TestNoSecretsInCode (2 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_no_hardcoded_secrets` | Scans all .py, .sh, .yaml for API keys, passwords, AWS credentials, private keys, GitHub tokens. If someone commits a secret, this fails. | No secrets in source | Credential leak |
| `test_no_secrets_in_yaml_configs` | YAML configs are a common place for credentials. Separate scan ensures YAML files are checked even if the main scan misses them. | No secrets in YAML | Credential leak via config |

#### TestNoShellTrue (2 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_no_shell_true_in_pipeline_cli` | `shell=True` enables command injection. If someone adds `subprocess.call(cmd, shell=True)`, user input can execute arbitrary commands. | No shell=True in pipeline_cli.py | Command injection vulnerability |
| `test_no_shell_true_in_all_python` | Broader scan across all project Python files. Catches shell=True in any file, not just the CLI. | No shell=True in any project .py | Command injection anywhere |

### 2.7 TC-01 + TC-02: SAM Batch (`tests/integration/test_sam_batch.py`)

These are integration tests because they exercise the checkpoint module's
save/load/delete cycle, which involves filesystem I/O and JSON
serialization. TC-01 (full SAM inference) is skipped on Windows because
the `sam3` vendored module requires the WSL/Linux venv.

#### TestSAMBatchSingleImage (1 test, skipped on Windows)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_produces_coco_and_yolo_outputs` | End-to-end: SAM on one image produces COCO JSON and YOLO labels. If the export pipeline breaks, no annotations are generated. | COCO + YOLO output generated | No annotations produced |

#### TestSAMResumeFromCheckpoint (3 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_checkpoint_skips_processed_images` | Save a checkpoint, load it back, verify processed images are retained. If the serialization drops the "processed" dict, resume re-processes all images. | Checkpoint round-trips correctly | Resume re-processes everything |
| `test_fresh_deletes_checkpoint` | `--fresh` flag calls `delete_checkpoint`. If the delete function stops removing the file, `--fresh` silently resumes from old state. | delete_checkpoint removes file | --fresh does not start clean |
| `test_corrupt_checkpoint_ignored` | Corrupt JSON must return None, not crash. If `load_checkpoint` stops catching JSON errors, a corrupt file crashes the entire batch run. | Corrupt checkpoint = None (not exception) | Batch crashes on corrupt checkpoint |

### 2.8 TC-07 + TC-08: YOLO Training (`tests/integration/test_yolo_training.py`)

These tests verify the structure of the training pipeline without running
actual GPU training. The `MODELS` dict in `pipeline_cli.py` defines the 4
model variants. If the dict changes, training produces the wrong models.

#### TestYOLOTrainingFourModels (6 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_four_model_directories_exist` | All 4 model dirs must exist after training. If a dir is renamed, the evaluation script cannot find the weights. | 4 dirs: nano/small detection/segmentation | Evaluation cannot find weights |
| `test_best_weights_exist` | Each model must have `best.pt`. If training crashes silently, no weights are saved. | best.pt exists | Training failed silently |
| `test_model_variants_covered` | At least 1 model must have weights. If all 4 fail, this catches it. | At least 1 model trained | All training failed |
| `test_pipeline_cli_models_dict_has_four` | The `MODELS` dict must have exactly 4 entries. If someone adds or removes a variant, the pipeline trains the wrong set. | len(MODELS) == 4 | Wrong number of models trained |
| `test_each_model_has_required_fields` | Each model entry must have weights, task, label, project, best, data, batch. If a field is missing, training crashes with a KeyError. | All required fields present | KeyError during training |
| `test_model_tasks_are_correct` | Detection models have task='detect', segmentation has task='segment'. If swapped, Ultralytics trains the wrong task type. | task field matches variant | Wrong task type trained |

#### TestONNXExport (4 tests)

| Test | Why It Exists | Invariant Protected | Bug Caught If Code Changes |
| --- | --- | --- | --- |
| `test_onnx_files_exist` | ONNX export must produce .onnx files. If export fails silently, no deployment artifacts exist. | At least 1 .onnx file exists | Export failed silently |
| `test_onnx_files_are_valid_size` | ONNX files must be 0.1-50 MB. If export produces a 0-byte file or a 500 MB file, deployment fails. | 0.1 MB <= size <= 50 MB | Corrupt or oversized export |
| `test_onnx_export_script_exists` | The export script `04_export_and_evaluate_onnx.py` must exist. If renamed, the pipeline cannot export. | Script file exists | Export step missing |
| `test_onnx_export_script_has_benchmark` | The script must include benchmark/inference/latency logic. If benchmarking is removed, NFR-06 (latency <= 35 ms) cannot be verified. | Script references benchmark | No latency verification |

---

## 3. Test Infrastructure Rationale

### 3.1 Why `conftest.py` Uses `importlib.util.spec_from_file_location`

The dataset prep script `01_prepare_dataset.py` has a filename starting
with a digit. Python module names cannot start with a digit, so `import
01_prepare_dataset` is a syntax error. The `importlib` approach loads the
file by path without requiring a valid module name.

### 3.2 Why Integration Tests Use `monkeypatch` for `sys.argv`

`batch_segment.main()` calls `argparse.parse_args()` which reads `sys.argv`.
When pytest runs, `sys.argv` contains pytest's own arguments (e.g.,
`tests/unit/ tests/integration/ -v`). Without `monkeypatch.setattr(sys,
"argv", [...])`, argparse sees pytest's args and exits with error code 2.

### 3.3 Why TC-01 Is Skipped on Windows

The vendored `sam3` module contains Linux-specific GPU code (ROCm, CUDA
extensions). On Windows, `import sam3.model_builder` raises
`ModuleNotFoundError`. The test uses `skip_no_sam3` which checks
importability at collection time. This is not flaky: the skip is
deterministic based on the platform.

### 3.4 Why Static Tests Exclude `tests/` from `shell=True` Scan

The test file `test_security_static.py` itself contains the string
`shell=True` in its assertion code (e.g., `if "shell=True" in line:`).
If tests are not excluded, the scan reports itself as a violation. The
exclusion is documented in the test: "Exclude test files, they
legitimately reference shell=True in assertions."

### 3.5 Why Static Tests Exclude Virtual Environments

The `.venv_windows/` directory contains third-party packages (pip, torch,
numpy, sympy) that use `shell=True` legitimately. Scanning them produces
hundreds of false positives. The `SKIP_DIRS` set excludes all venv
variants: `.venv_windows`, `.venv`, `venv`, `sam3_venv`.

---

## 4. Verification Evidence

Last test run: 2026-09-10

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.3.4
plugins: anyio-4.11.0, asyncio-0.25.0, cov-6.0.0

collected 76 items

tests/integration/test_sam_batch.py::TestSAMBatchSingleImage::test_produces_coco_and_yolo_outputs SKIPPED
tests/integration/test_sam_batch.py::TestSAMResumeFromCheckpoint ... (3 PASSED)
tests/integration/test_yolo_training.py ... (10 PASSED)
tests/unit/test_config_static.py ... (7 PASSED)
tests/unit/test_dataset_prep.py ... (16 PASSED)
tests/unit/test_focal_patch.py ... (7 PASSED)
tests/unit/test_path_safety.py ... (12 PASSED)
tests/unit/test_provenance.py ... (16 PASSED)
tests/unit/test_security_static.py ... (4 PASSED)

======================= 75 passed, 1 skipped in 9.55s ========================
```

Command: `python -m pytest tests/ -v --tb=short`

Result: 75 passed, 1 skipped, 0 failed.

---

## 6. Document Redundancy Analysis

The docs tree has 17 files across 5 subdirectories. Several pairs overlap
in content. This section identifies each overlap, explains why both
copies exist, and recommends whether to keep, merge, or remove.

### 6.1 Overlap Map

| Doc A | Doc B | Overlapping Content | Verdict |
| --- | --- | --- | --- |
| `00-overview.md` | `sdlc/01-overview.md` | Business objectives, scope, requirements table, KPIs | Keep both: 00 is project-level, sdlc/01 is SDLC-phase-level with risk register and traceability |
| `01-requirements.md` | `sdlc/01-overview.md` | Functional/non-functional requirements, FR/NFR tables | Keep both: 01 is hardware/software requirements, sdlc/01 is business analysis + requirements analysis with traceability matrix |
| `architecture/01-system-architecture.md` | `sdlc/02-design.md` | System architecture diagram, component list, 3-mode CLI | Keep both: architecture/01 is detailed (PlantUML diagrams, hardware utilization), sdlc/02 is SDLC-phase summary with ADRs |
| `design/01-component-design.md` | `sdlc/02-design.md` | Component responsibilities table | Keep both: design/01 has 11 detailed component cards with file:line refs, sdlc/02 has a summary table |
| `pipeline/01-pipeline-flow.md` | `sdlc/02-design.md` | Data flow diagram | Keep both: pipeline/01 has the state-machine flowchart, sdlc/02 has the activity diagram |
| `sdlc/03-ops.md` (test cases) | `qa/qa-test-design.md` (this doc) | TC-01 through TC-12 test case definitions | Keep both: sdlc/03 has the test case table (what to test), this doc has the rationale (why each test function exists) |

### 6.2 Redundancy Verdict

No doc is a pure duplicate of another. Each pair above has a different
audience, scope, or level of detail:

- `00-overview.md` is for project newcomers (high-level, 1 page).
- `sdlc/01-overview.md` is for SDLC auditors (phase gate, risk register,
  traceability matrix).
- `architecture/01-system-architecture.md` is for architects (detailed
  diagrams, hardware utilization).
- `sdlc/02-design.md` is for SDLC phase 3-4 gate review (ADRs, technical
  debt, security controls).
- `sdlc/03-ops.md` test cases are for QA planning (what to test).
- `qa/qa-test-design.md` is for QA engineers (why each test function
  exists, what invariant it protects).

The SDLC docs (`sdlc/01`, `sdlc/02`, `sdlc/03`) intentionally summarize
content from the detailed docs (`00-overview`, `architecture/`,
`design/`, `pipeline/`) because they serve a different purpose: SDLC
phase gate review. Removing the summary from SDLC docs would break the
traceability chain required by the SDLC documentation skill.

### 6.3 True Duplicates (None Found)

No file is a byte-for-byte or content-for-content duplicate of another.
The closest pair is the requirements tables in `01-requirements.md` and
`sdlc/01-overview.md`, but they differ:

- `01-requirements.md` has hardware/software/dependency tables.
- `sdlc/01-overview.md` has risk register, stakeholder table, and
  traceability matrix.

---

## 7. Last Check: Why Each Component Must Exist

### 7.1 Why the Test Suite Must Exist

The SDLC documentation skill requires a test plan and test cases for
phase 5 exit criteria. Without the test suite:

- TD-01 (no automated tests) remains Critical and open.
- R-04 (no automated tests) remains High risk in the risk register.
- NFR-08, NFR-09, NFR-10, NFR-11 (security) cannot be verified.
- The pre-deployment checklist item `python -m pytest tests/` has no
  suite to run.
- Regression bugs (path traversal, focal patch failure, split logic)
  are caught only at runtime, not at commit time.

### 7.2 Why Each Test File Must Exist

| File | Why It Must Exist | What Happens Without It |
| --- | --- | --- |
| `test_path_safety.py` | Security boundary tests (ISO 27001 A.14.1.2). Without these, path traversal is untested and regressions are caught only when an attacker exploits them. | Path traversal vulnerability ships to production |
| `test_focal_patch.py` | Training correctness tests. Without these, a silent focal patch failure means training uses standard BCE and rare classes underperform. | mAP50 for harness/boots degrades silently |
| `test_dataset_prep.py` | Data integrity tests. Without these, a split bug or bbox conversion bug produces corrupt training data and all downstream metrics are invalid. | All training metrics invalid |
| `test_config_static.py` | Config consistency tests. Without these, MLflow binds to 0.0.0.0 (network exposure) or the checkpoint path mismatch causes "file not found" at runtime. | Security exposure or runtime crash |
| `test_security_static.py` | Security audit tests (ISO 27001 A.14.2.1, A.14.2.5). Without these, committed secrets and shell=True injection are caught only by manual review. | Credential leak or command injection |
| `test_sam_batch.py` | Checkpoint integrity tests. Without these, resume/fresh/corrupt-checkpoint behavior is untested and data loss on crash is possible. | Data loss on crash, resume broken |
| `test_yolo_training.py` | Training pipeline structure tests. Without these, the MODELS dict or ONNX export script can change silently and training produces wrong models. | Wrong models trained, no deployment artifacts |

### 7.3 Why `conftest.py` Must Exist

The `conftest.py` provides 5 session-scoped fixtures:

| Fixture | Why It Must Exist | What Happens Without It |
| --- | --- | --- |
| `repo_root` | Every test needs the repo root path. Without a shared fixture, each test computes it independently (code duplication). | Path duplication in every test |
| `pipeline_cli` | `pipeline_cli.py` is not in a package. It must be imported by adding the repo root to `sys.path`. Without the fixture, each test does this manually. | sys.path manipulation in every test |
| `config_module` | `config.py` is in `sam3_auto_label/src/`. Same sys.path issue. | Same as above |
| `prepare_dataset_module` | `01_prepare_dataset.py` starts with a digit. Cannot be imported normally. Must use `importlib.util.spec_from_file_location`. | Cannot import the module at all |
| `focal_patch_module` | `focal_patch.py` is in `yolo26_ppe/`. Same importlib approach for consistency. | Manual import in every test |

### 7.4 Why `pytest.ini` Must Exist

`pytest.ini` defines 3 markers (`unit`, `integration`, `static`) and
enables `--strict-markers`. Without it:

- Markers are not registered and `--strict-markers` rejects them.
- `pytest -m unit` cannot select only unit tests.
- `pytest -m integration` cannot select only integration tests.
- The test suite cannot be split by level in CI.

### 7.5 Why This QA Doc Must Exist

The SDLC documentation skill requires a test plan for phase 5. The test
cases table in `sdlc/03-ops.md` answers "what to test." This doc answers
"why this test function exists, what invariant it protects, and what bug
it catches." Without this doc:

- A new QA engineer cannot understand the rationale behind each test.
- Code review cannot evaluate whether a test change is safe.
- Mutation testing cannot identify which tests protect which invariants.
- The test strategy (pyramid ratio, case selection, flake policy) is not
  documented.

---

## 8. References

- `tests/conftest.py` - Shared fixtures
- `pytest.ini` - Markers and config
- `docs/sdlc/03-ops.md` - Test cases table (TC-01 through TC-12)
- `docs/sdlc/02-design.md` - Section 4.2.1 Test Infrastructure
- `docs/sdlc/01-overview.md` - Section 2.6 Traceability Matrix
- `docs/00-overview.md` - Project overview
- `docs/01-requirements.md` - Hardware/software requirements
- `docs/architecture/01-system-architecture.md` - System architecture
- `docs/design/01-component-design.md` - Component design
