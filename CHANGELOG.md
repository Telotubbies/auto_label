# Changelog

Notable changes to this repository, newest first. The format follows Keep a Changelog, and versions follow SemVer for the components that declare one.

There are no dated release entries for LabelDesk in this file. The API and worker packages report version 1.0.0 and the web package reports 0.1.0; those numbers are build metadata, not release notes. Before this file existed, history lived in `git log`.

## Unreleased

### Added

- Repository README covering the LabelDesk application and the PPE pipeline.
- `CONTRIBUTING.md`, `SECURITY.md`, and `CODEOWNERS` with a placeholder owner.
- Architecture overview at `docs/architecture/overview.md`.
- ADR 0001 for the repository layout and ADR 0002 for the front and back contract.
- Git workflow guide at `docs/GIT_WORKFLOW.md`.
- Runbooks for local start and recovery after an unexpected shutdown.

### Changed

- The README, CONTRIBUTING, runbooks, architecture overview, ADRs and SECURITY now describe the current layout.
- Renamed the application folders to `apps/frontend` and `apps/backend`; commands, CI, `tools/ld-task`, `.gitignore` and CODEOWNERS use the new paths.

### Fixed

- Nothing in this change set.
