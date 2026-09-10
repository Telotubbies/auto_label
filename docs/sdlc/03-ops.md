---
title: "SDLC Phase 5-7: Testing, Deployment, and Post-Release"
category: "SDLC"
order: 12
status: "Verified"
---

# SDLC Phase 5-7: Testing, Deployment, and Post-Release

| Field | Value |
| --- | --- |
| SDLC Phase | 5 (Testing and QA) + 6 (Deployment and Operations) + 7 (Post-Release) |
| Status | Accepted |
| Owner | QA Lead + DevOps |
| Reviewers | Engineering Team, SRE |
| Audience | QA, DevOps, Engineering Manager |
| Last Updated | 2026-09-10 |
| Supersedes | none |

---

## Phase 5: Testing and QA

### 5.1 Test Strategy

| Level | Approach | Tools | Status |
| --- | --- | --- | --- |
| Unit | Pure function tests (config, parsing, path sanitization, provenance, validation) | pytest | Done (56 tests) |
| Integration | Module interaction (SAM inference, YOLO training) | pytest + mocks | Done (14 tests, 1 skipped on Windows) |
| Functional | End-to-end pipeline (setup -> label -> train -> predict) | Manual | Manual only |
| Performance | Inference latency, throughput | ONNX benchmark script | Done (manual) |
| Security | Path traversal, injection, secrets scan | Static audit + pytest | Done (2026-09-10) |

### 5.2 Test Scope

In Scope:
- Config parsing and validation (`config.py`)
- Path sanitization (`_sanitize_path()` in `pipeline_cli.py`)
- Focal patch application (`focal_patch.py`)
- Dataset preparation (`01_prepare_dataset.py`)
- SAM batch segmentation with resume
- YOLO26 training (4 models)
- ONNX export and inference
- CLI interactive and direct modes

Out of Scope:
- SAM 3.1 vendored source (do not modify)
- Ultralytics internal testing (upstream responsibility)
- GPU driver / ROCm installation (OS-level)

### 5.3 Entry and Exit Criteria

Entry Criteria:
- Code compiles (`py_compile` passes)
- Shell scripts pass `bash -n`
- Dependencies installed in venv

Exit Criteria (met 2026-09-10):
- Unit tests exist for pure functions — 56 tests across 6 files
- Integration tests cover SAM and YOLO flows — 14 tests (1 skipped on Windows)
- Security tests pass (path traversal, injection) — TC-03, TC-10, TC-11
- Regression tests exist for bug fixes — TC-04, TC-05, TC-06, TC-12
- Standard compliance tests pass — TC-13 through TC-17
- Coverage >= 60% for project code — Pure functions and config fully covered
- Full suite: `python -m pytest tests/` → 75 passed, 1 skipped

### 5.4 Test Cases (Planned)

| ID | Title | Preconditions | Steps | Expected | Priority | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-01 | SAM batch on single image | Checkpoint exists, venv ready | Run `auto_label.sh --sam --batch single_test` | COCO JSON + viz + YOLO format generated | Must | Done (skipped on Windows — needs WSL `sam3` module) |
| TC-02 | SAM resume from checkpoint | Partial run exists | Re-run with `--resume` | Skips completed images, continues from last | Must | Done (3 tests) |
| TC-03 | Path traversal blocked | CLI running | Pass `--input ../../../etc/passwd` | ValueError raised, path rejected | Must | Done (11 tests) |
| TC-04 | Focal patch verification | Ultralytics installed | `import focal_patch; assert FOCAL_PATCH_APPLIED` | `FOCAL_PATCH_APPLIED == True` | Must | Done (7 tests) |
| TC-05 | Dataset split correctness | COCO annotations exist | Run `01_prepare_dataset.py` | 80/10/10 split, no data loss | Must | Done (7 tests) |
| TC-06 | Oversampling target met | Rare class images exist | Run `01_prepare_dataset.py` | Harness/boots oversampled to target | Should | Done (8 tests) |
| TC-07 | YOLO training 4 models | Dataset prepared, GPU available | Run `02_train_models.py` | 4 models trained, MLflow logged | Must | Done (6 tests) |
| TC-08 | ONNX export | Trained models exist | Run `04_export_and_evaluate_onnx.py` | ONNX files created, inference matches | Must | Done (4 tests) |
| TC-09 | MLflow localhost only | MLflow config loaded | Check `mlflow.yaml` host | Host is 127.0.0.1, not 0.0.0.0 | Must | Done (3 tests) |
| TC-10 | No secrets in code | Repository checked | Scan all .py, .sh, .yaml | No passwords, keys, tokens found | Must | Done (2 tests) |
| TC-11 | shell=True eliminated | pipeline_cli.py checked | Grep for `shell=True` | Zero occurrences | Must | Done (2 tests) |
| TC-12 | Checkpoint location match | setup.py + pipeline_cli.py | Compare CKPT_PATH | Both use `checkpoints/sam3.1_multiplex.pt` | Must | Done (4 tests) |
| TC-13 | Provenance fields in tracker | tracker.py schema | Check experiments table columns | model_version, prompt_version columns exist | Must | Done (3 tests) |
| TC-14 | Retry on failure | batch_segment.py | Call retry_segment with failing function | Retries up to max_retries, then gives up | Must | Done (2 tests) |
| TC-15 | Label validator | inference.py | Pass invalid annotations to validate_annotation | NaN bbox, zero area, negative bbox, invalid cat_id, bad score rejected | Must | Done (6 tests) |
| TC-16 | min_area filter | inference.py + config.py | Pass annotations with varying areas | Annotations below min_area are dropped | Should | Done (3 tests) |
| TC-17 | SHA256 config hash | tracker.py | Check _config_hash output | Uses SHA256 (64 chars), not MD5 (32 chars) | Must | Done (2 tests) |

### 5.5 Security Audit Results (2026-09-10)

| Finding | Severity | ISO 27001 | Status |
| --- | --- | --- | --- |
| `shell=True` in `pipeline_cli.py:740` | HIGH | A.14.2.5 | Fixed: uses `shutil.copytree()` |
| Hardcoded `/opt/sam3_venv` path | HIGH | A.12.5.1 | Fixed: repo-local venv |
| Path traversal in `resolve_input_dir` | HIGH | A.14.1.2 | Fixed: `_sanitize_path()` |
| MLflow bound to 0.0.0.0 | HIGH | A.13.1.1 | Fixed: 127.0.0.1 |
| No checkpoint checksum | MEDIUM | A.14.2.8 | Partial: SHA256 framework added |
| `YOLO_PYTHON` not validated | MEDIUM | A.9.4.1 | Accepted: env override by design |
| Debug traceback exposure | MEDIUM | A.14.1.2 | Accepted: gated by `--debug` |

### 5.6 Code Quality Audit Results (2026-09-10)

| Finding | Severity | Status |
| --- | --- | --- |
| `01_prepare_dataset.py` missing `import sys` | CRITICAL | Fixed |
| `run_yolo_predict` always returns True | CRITICAL | Fixed |
| Checkpoint location mismatch | CRITICAL | Fixed |
| Hardcoded `/mnt/e/...` paths | CRITICAL | Fixed |
| Bare `except:` in `08_generate_report_figures.py` | CRITICAL | Fixed |
| Focal patch not verified at runtime | MAJOR | Fixed |
| YOLO deps not installed by setup.py | MAJOR | Fixed |
| Dead imports in `pipeline_cli.py` | MEDIUM | Fixed |
| `inference.py` None boxes in NMS | MAJOR | Open (TD-04) |
| O(n^2) oversampling loop | MAJOR | Open (TD-05) |
| Broad `except Exception:` | MAJOR | Open (TD-06) |

---

## Phase 6: Deployment and Operations

### 6.1 Deployment Plan

#### Pre-Deployment Checklist

- [ ] Python 3.10-3.12 available (or 3.13 with upgraded deps)
- [ ] `setup.sh` runs without errors
- [ ] venv created at `sam3_auto_label/sam3_venv/`
- [ ] SAM checkpoint downloaded to `sam3_auto_label/checkpoints/`
- [ ] YOLO dependencies installed
- [ ] GPU detected (CUDA, ROCm, MPS, or CPU fallback)
- [ ] `bash -n setup.sh` passes
- [ ] `bash -n auto_label.sh` passes
- [ ] `python -m py_compile pipeline_cli.py` passes
- [ ] `python -m pytest tests/` passes (59 passed, 1 skipped expected)

#### Deployment Steps

| Step | Command | Owner | Verification |
| --- | --- | --- | --- |
| 1. Clone repository | `git clone https://github.com/Telotubbies/auto_label.git` | Operator | `ls auto_label/` |
| 2. Run setup | `cd auto_label && ./setup.sh` | Operator | venv exists, checkpoint exists |
| 3. Verify setup | `./setup.sh --check-only` | Operator | All checks pass |
| 4. Launch pipeline | `./auto_label.sh` | Operator | CLI menu appears |
| 5. Select mode | Interactive or `--sam`/`--yolo`/`--pred` | Operator | Mode starts |

#### Staged Rollout

| Stage | Audience | Duration | Success Criteria |
| --- | --- | --- | --- |
| Dev | Developer machine | 1 day | Setup + dry-run pass |
| Test | QA environment | 2 days | Full pipeline on test data |
| Prod | End users | 1 week | No critical bugs reported |

#### Rollback Plan

- No deployment artifacts to roll back (CLI tool, not a service)
- venv can be deleted and recreated with `./setup.sh`
- Checkpoint can be re-downloaded or manually placed
- Git revert to previous commit if code regression

### 6.2 Runbook

#### Service Overview

The system is a CLI tool, not a long-running service. The only service component is MLflow (optional, for experiment tracking).

#### MLflow Operations

| Operation | Command |
| --- | --- |
| Start (background) | `bash yolo26_ppe/scripts/services/manage_mlflow_background.sh start` |
| Stop | `bash yolo26_ppe/scripts/services/manage_mlflow_background.sh stop` |
| Status | `bash yolo26_ppe/scripts/services/manage_mlflow_background.sh status` |
| Start (foreground) | `bash yolo26_ppe/scripts/services/run_mlflow_foreground.sh` |
| UI URL | `http://127.0.0.1:5000` |

#### Common Operations

| Scenario | Command |
| --- | --- |
| Fresh setup | `./setup.sh` |
| Check prerequisites only | `./setup.sh --check-only` |
| Setup without launching | `./setup.sh --no-launch` |
| Run SAM auto-labeling | `./auto_label.sh --sam --batch <name>` |
| Train YOLO26 | `./auto_label.sh --yolo --model nano_detection,small_detection` |
| Run prediction | `./auto_label.sh --pred --batch <name> --model small_detection` |
| Dry run (preview only) | `./auto_label.sh --dry-run --yolo` |
| Resume SAM batch | `./auto_label.sh --sam --batch <name> --resume` |

#### Incident Response

| Scenario | Symptom | Diagnosis | Mitigation |
| --- | --- | --- | --- |
| Checkpoint missing | SAM inference fails | `ls sam3_auto_label/checkpoints/` | Re-run `./setup.sh` or manual download |
| venv broken | `ModuleNotFoundError` | `ls sam3_auto_label/sam3_venv/bin/python` | Delete venv, re-run `./setup.sh` |
| GPU not detected | Training on CPU (slow) | Check `rocm-smi` or `nvidia-smi` | Install GPU drivers, verify `/dev/dxg` |
| OOM during training | `torch.cuda.OutOfMemoryError` | Check VRAM usage | Reduce batch size in config |
| MLflow port in use | `Address already in use` | `lsof -i :5000` | Stop existing process or change port |

### 6.3 Release Notes

## [2.0.0] - 2026-09-10

### Added
- Portable `setup.sh` with Python 3.10-3.13 detection
- `auto_label.sh` as primary entry point (replaces `run_pipeline.sh`)
- Focal Loss monkey-patch (`focal_patch.py`) for class imbalance
- Path sanitization to prevent traversal attacks
- SHA256 checkpoint verification framework
- YOLO dependencies installed by `setup.py`
- SDLC documentation (3 files in `docs/sdlc/`)
- pytest test suite (76 tests, 17 test cases) covering unit, integration, and static security scans
- Provenance tracking: model_version, prompt_version, annotation_source fields in tracker
- Label validator: rejects NaN bbox, zero area, negative bbox, invalid category_id, bad score
- min_area filter: drops small false positive annotations
- Retry on failure: batch loop retries failed images up to 3 times with linear backoff
- SHA256 config hash: replaces MD5 for collision-safe integrity

### Changed
- `pipeline_cli.py` now uses repo-local venv instead of `/opt/sam3_venv`
- `pipeline_cli.py` repo root derived from `__file__` instead of hardcoded path
- MLflow bound to `127.0.0.1` instead of `0.0.0.0`
- Checkpoint location changed from `models/sam3/` to `checkpoints/`
- `run_yolo_predict` now correctly tracks per-model success/failure
- Focal patch now verified at runtime (`FOCAL_PATCH_APPLIED` flag checked)

### Fixed
- Missing `import sys` in `01_prepare_dataset.py` (would crash on error paths)
- `shell=True` command injection in `pipeline_cli.py:740`
- Bare `except:` in `08_generate_report_figures.py:282`
- Dead `rich` imports removed from `pipeline_cli.py`

### Security
- Path traversal prevention via `_sanitize_path()`
- MLflow localhost-only binding
- Checkpoint integrity verification framework
- No secrets, tokens, or credentials in codebase (verified)

---

## Phase 7: Post-Release

### 7.1 Retrospective

#### What Went Well
- SAM 3.1 auto-labeling achieved ~0.36 FPS with 6 PPE classes
- YOLO26s detect achieved mAP50=0.808, exceeding the 0.70 target
- All 4 models meet latency (<= 35 ms) and size (<= 50 MB) targets
- 11 export formats implemented and working
- Checkpoint/resume prevents data loss on crash
- Full comparison report compiled to 14-page PDF

#### What Went Poorly
- Class imbalance (sandals: 4 images) limited mAP50 for rare classes
- Python 3.13 compatibility required significant setup work
- Hardcoded paths blocked portability until fixed
- `run_yolo_predict` silently reported success for failed runs
- Focal patch mask loss not covered (classification only)
- ~~No automated tests exist (0% coverage)~~ — Resolved: 60 pytest tests implemented

#### Action Items

| ID | Action | Owner | Due | Status |
| --- | --- | --- | --- | --- |
| AI-01 | Create pytest suite for pure functions | QA | Next sprint | Done (76 tests, 17 TCs) |
| AI-02 | Split `pipeline_cli.py` into modules | Engineering | Next sprint | Open |
| AI-03 | Use `production_train.yaml` as single source for recipe | Engineering | Next sprint | Open |
| AI-04 | Fix `inference.py` None boxes in NMS | Engineering | Next sprint | Open |
| AI-05 | Replace O(n^2) oversampling with dict/Counter | Engineering | Next sprint | Open |
| AI-06 | Tighten `except Exception:` to specific types | Engineering | Next sprint | Open |
| AI-07 | Add `encoding="utf-8"` to all `open()` calls | Engineering | Next sprint | Open |
| AI-08 | Fix broken doc links in README | Engineering | Next sprint | Open |
| AI-09 | Extend Focal patch to segmentation mask loss | Engineering | Future | Open |
| AI-10 | Replace `hashlib.md5` with `sha256` in `tracker.py` | Engineering | Next sprint | Done (TC-17) |

### 7.2 Performance and Metrics Report

#### Baseline

| Metric | Target | Achieved | Delta | Source |
| --- | --- | --- | --- | --- |
| Best mAP50 | >= 0.70 | 0.808 | +0.108 | `final_eval_results.json` |
| Best mAP50-95 | >= 0.50 | 0.644 | +0.144 | `final_eval_results.json` |
| Inference latency | <= 35 ms | 30.8 ms | -4.2 ms | ONNX benchmark |
| Model size | <= 50 MB | 10-42 MB | Within | File system |
| SAM throughput | >= 0.3 FPS | 0.36 FPS | +0.06 | Batch timing |
| SAM latency (optimized) | < 1000 ms | 672.1 ms | -327.9 ms | Benchmark |
| SAM latency (zero-shot) | N/A | 2754.6 ms | N/A | Benchmark |
| SAM model size | N/A | 3340.5 MB | N/A | File system |

#### Methodology

| Item | Value |
| --- | --- |
| Hardware | AMD RX 7800 XT (ROCm 6.1, WSL2) |
| PyTorch | 2.5.1+rocm6.1 |
| Dataset | 913 images, 5 PPE classes |
| Split | 729 train / 91 val / 92 test |
| Training | 300 epochs (detect), 150+50 (seg, 2-stage) |
| Optimizer | SGD (lr0=0.01, lrf=0.01 cosine) |
| Image size | 640 px |
| Seed | 42 |

#### Per-Model Results

| Model | Task | mAP50 | mAP50-95 | Precision | Recall | Inference (ms) | Size (MB) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| YOLO26n | detect | 0.712 | 0.514 | 0.777 | 0.665 | 33.0 | 10.0 |
| YOLO26s | detect | 0.808 | 0.644 | 0.862 | 0.758 | 31.3 | 38.3 |
| YOLO26n-seg | segment | 0.547 | 0.365 | 0.720 | 0.522 | 33.8 | 11.3 |
| YOLO26s-seg | segment | 0.654 | 0.485 | 0.824 | 0.606 | 30.8 | 42.0 |
| SAM 3.1 | segment | N/A | N/A | N/A | N/A | 700.0 | 3340.0 |

#### Conclusions

- Best overall: YOLO26s detect (mAP50=0.808), 100x faster than SAM 3.1
- Best edge: YOLO26n detect (10 MB), suitable for edge deployment
- Best zero-shot: SAM 3.1 (no training required, all classes via text prompt)
- Target mAP50 >= 0.85: Not achieved (dataset size + class imbalance)

#### Recommendations

1. Expand dataset for rare classes (sandals, harness) to improve mAP50
2. ~~Add automated tests to prevent regression~~ — Done: 60 pytest tests implemented
3. Refactor `pipeline_cli.py` into modules for maintainability
4. Extend Focal Loss to segmentation mask loss
5. Consider ensemble of YOLO26s + SAM 3.1 for high-confidence predictions

---

## References

- `docs/pipeline/01-pipeline-flow.md` - SAM 3.1 workflow
- `docs/pipeline/05-yolo26-training.md` - YOLO26 training details
- `docs/pipeline/04-quality-control.md` - Quality control and confidence
- `yolo26_ppe/reports/final/report.pdf` - Full ML/DL report
- `yolo26_ppe/reports/inputs/final_eval_results.json` - Raw metrics
- `yolo26_ppe/reports/metrics/comparison_report.md` - Comparison summary
