# ADR 0002: The OpenAPI document is the front and back contract

- Status: Accepted; only the SDK half is implemented
- Date: 2026-11-03
- Related: [Architecture overview](../architecture/overview.md), [ADR 0001](0001-repository-layout.md)

## Context

The backend is a FastAPI application. FastAPI builds an OpenAPI document from the routers and Pydantic models, and serves it at `/openapi.json`. The document describes paths, operations, parameters, request bodies, and response models.

The frontend currently defines its own types in `apps/frontend/src/lib/types.ts` and calls the API through `apps/frontend/src/lib/api.ts`. Nothing checks those types against the backend. A backend field rename can merge and leave the frontend reading a missing property until a user hits the screen.

The SDK is further along. `tools/gen_sdk.py` projects the OpenAPI document down to an operation map in `apps/sdk/labeldesk/_generated.py`. `apps/backend/tests/test_sdk_cli.py` regenerates the map from the live schema and fails when the committed map drifts. That test only covers operations, methods, paths, scopes, and parameters. It does not cover response body types, and it does not cover the frontend.

A separate repository would make this worse. The producer and consumer would release on different schedules, and the contract would need its own versioning and publication process.

## Decision

1. The OpenAPI document published by the backend is the single description of the HTTP contract.
2. The SDK operation map stays generated from that document, and the lockstep test stays in the API suite.
3. Frontend TypeScript types are generated from the same document. The frontend build fails when the checked-in generated output does not match the current schema.
4. A change that touches both sides is two tasks. The backend changes and merges first. The frontend uses the new shape behind a `task_<id>` feature flag, default off, and merges second.
5. There is no repository split. Both halves stay in this repository so one review sees the contract change.

## Current state

| Part | State |
|---|---|
| Backend publishes OpenAPI | Implemented. FastAPI serves `/openapi.json`. |
| SDK operation map generated | Implemented in `tools/gen_sdk.py`. |
| SDK lockstep test | Implemented in `apps/backend/tests/test_sdk_cli.py`. |
| Frontend types generated | Not implemented. `apps/frontend/src/lib/types.ts` is hand-written. |
| Frontend build fails on schema drift | Not implemented. |
| Feature flag convention | Implemented. Workspace flags are exposed by the API and read by the frontend. |

Until the generator lands, the contract rule is a process rule on the frontend side. A reviewer should treat an API shape change without a matching `types.ts` change as a finding.

## Consequences

- The schema has one owner, and a contract change is visible in one diff.
- Backend work can merge before frontend work without leaving a broken main branch, because the frontend change waits behind a flag.
- The frontend build becomes slower once generation runs as part of it. That cost buys a real failure instead of a runtime surprise.
- Generated types will not cover behavior: status codes with conditional bodies, signed URL formats, or fields the OpenAPI model does not annotate. Those still need tests.
- The SDK test proves operation drift only. Response model changes need their own tests on the API side.

## What the generator must do when it lands

- Read the schema from the app object, not from a running server, so CI does not need a live database.
- Write to a checked-in file and fail on a dirty diff.
- Keep the output deterministic: stable ordering, no timestamps, no machine paths.
- Run before `tsc -b` in the frontend build script.
- Cover request and response bodies, not only operation names.

No frontend type generator exists yet. Do not add a build step that calls one until it is merged.

## Alternatives considered

**Hand-written types with a review checklist.** This is the current state. It fails silently and depends on every reviewer noticing every field.

**Generate a client instead of types.** Possible later. It would add a dependency and hide the fetch layer. Generating types keeps the existing thin client and its refresh-token behavior.

**Version the API and let the frontend pin a version.** Rejected for now. The app is one repository and one deployment. Versioning would add work without removing the need to update the frontend.
