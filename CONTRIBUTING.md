# Contributing to LabelDesk

This file covers how to prepare a change and hand it back for merge. Operational and branch rules are in [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md).

## Before you start

1. Read the project engineering standards, the relevant ADRs in `docs/adr/`, and the code around the area you plan to change. The standards file is maintained by the owner and is not tracked on this branch yet; ask the merger for the current copy.
2. Create a task worktree and branch. Do not edit the integrator checkout and do not work on `main` or `feat/labeldesk-v2` directly.
3. Check `git status` and leave unrelated files alone. Never delete untracked files that you did not create.
4. If the change touches both the frontend and the backend, plan two jobs. The backend merges first, and the frontend change ships behind a feature flag.
5. If the change needs a decision that will outlive the task, write an ADR before the code.

## Naming

The approved names are `apps/frontend` for the web app and `apps/backend` for the API. The directories are still `apps/web` and `apps/api`; the rename is pending. Use the planned names in new prose and give the current path when a reader needs to run a command today. Do not rename the directories as part of an unrelated task.

## Making the change

- Match the existing structure. Backend routers stay thin, logic lives in `services/` or `adapters/`, and every workspace-scoped query filters by `workspace_id`.
- Keep one responsibility per file. Split a file that passes roughly 400 lines along a real seam.
- Put feature code in its own module. Routers, worker handlers, web routes, navigation entries, API client files, models, and migrations should not all be appended to one shared file.
- Add tests for every behavior change. Use fakes for GPU and network calls, and mark real hardware tests with `gpu` or `slow`.
- Do not put secrets, tokens, or absolute machine paths in code or tests.
- Follow the formatters and linters in the standards: `ruff format` and `ruff check` for Python, `biome check` for TypeScript. The frontend build must pass with `npm run build`.
- Use conventional commit subjects: `feat:`, `fix:`, `chore:`, `docs:`. Keep the subject in lowercase and under about 72 characters.

## Documentation

- Update the README or the relevant topic document when behavior, commands, environment variables, or paths change.
- Add or update a runbook when an operator has to do something new.
- Add an ADR for a structural decision, a contract change, or a choice that is expensive to reverse.
- Record user-visible changes under `Unreleased` in [CHANGELOG.md](CHANGELOG.md). Do not invent a release date or version.
- State what you verified. If you did not run a check, say so in the handoff.

## Verification

Run the narrowest useful checks while you work, then the full relevant gate before handing off:

```bash
# Backend, from apps/backend (today apps/api)
pytest -q

# Frontend, from apps/frontend (today apps/web)
npm run build
npm test
```

The API suite includes a short CPU training run. The frontend test script only covers the tests present in `apps/web/tests`. If a check needs a GPU, a model file, or a network service, mark it and report that it was skipped.

## Handoff

- Commit your own work. Do not push. Agents never push from a task worktree.
- Tell the merger the branch name, the checks you ran, and anything you could not verify.
- Do not merge your own branch.
- Do not remove the worktree until the branch is merged and clean. `git worktree remove` refuses when untracked files exist, and you should not work around that with `--force`.

## Security

Report vulnerabilities through the process in [SECURITY.md](SECURITY.md). Do not open a public issue for a suspected vulnerability, and do not include live credentials in a report or a test fixture.
