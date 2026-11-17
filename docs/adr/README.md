# Architecture decision records

Append-only. A reversed decision keeps its file and changes its status line; it is
never edited away or deleted.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-repository-layout.md) | One repository with an app-per-directory layout | Accepted, superseded in part by 0003 |
| [0002](0002-front-back-contract.md) | Front and back contract | Accepted |
| [0003](0003-repository-layout-v2.md) | Packages, ML layer, and research split | Accepted |
| [0004](0004-ml-own-repo.md) | ML pipelines live in their own repository | Accepted |
| [0005](0005-inference-hub.md) | The Inference Hub installs and downloads through worker jobs | Proposed |
| [0006](0006-rust-python-hybrid.md) | Rust only as Python extension modules for measured hot paths | Proposed |
