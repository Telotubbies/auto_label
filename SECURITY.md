# Security policy

## Supported versions

This repository has no released support window. Security fixes land on `feat/labeldesk-v2` and then move to `main` after the release gate. Older branches and tags do not receive fixes unless the owner says otherwise.

## Reporting a vulnerability

Do not open a public issue, pull request, or discussion for a suspected vulnerability.

Use the private vulnerability reporting feature on the GitHub repository if it is enabled. If it is not enabled, contact the repository owner through a private channel. The owner handle in [CODEOWNERS](CODEOWNERS) is a placeholder and must be replaced before this policy can route reports. Do not send reports to an address you found in a commit or a test fixture.

Include:

- the affected component and version or commit,
- the steps to reproduce, with the smallest request or file that triggers the issue,
- the impact you believe it has,
- any logs, but remove tokens, cookies, and personal data first.

Expect an acknowledgement when the owner is available. This project has no paid response-time commitment.

## Scope

In scope:

- the API in `apps/backend` (today `apps/api`),
- the web app in `apps/frontend` (today `apps/web`),
- the worker, SDK, and inference packages under `apps/`,
- the deployment files in `deploy/`,
- authentication, authorization, tenant isolation, file handling, and secret storage.

Out of scope:

- vulnerabilities in third-party dependencies that have no exploitable path in this code. Report those upstream and tell us if this project needs to pin or patch.
- denial of service from a machine with unlimited resources and no rate limit bypass,
- issues that require a compromised host, a stolen `LD_SECRET`, or database write access,
- the research pipeline's model quality, which is covered in the README's known limits.

## Controls already in the code

These are the main defenses a reporter should know about. Each has tests or a clear code path.

| Control | Where |
|---|---|
| Password hashing with PBKDF2-SHA256 | `apps/api/app/security.py` |
| Short-lived access tokens and hashed refresh tokens | `apps/api/app/security.py`, `apps/api/app/routers/auth.py` |
| API keys stored as hashes with scopes | `apps/api/app/apikeys.py` |
| Signed, expiring file URLs | `apps/api/app/security.py`, `apps/api/app/main.py` |
| Secrets encrypted at rest with a key derived from `LD_SECRET` | `apps/api/app/services/secretbox.py` |
| SSRF guard for user-supplied image URLs | `apps/api/app/services/safefetch.py` |
| Upload size and image pixel limits | `apps/api/app/config.py`, `apps/api/app/services/imaging.py` |
| Per-IP rate limits on login, signup, refresh, and API keys | `apps/api/app/ratelimit.py` |
| Worker authentication with a shared token | `apps/api/app/routers/remote.py` |
| Security headers and API response caching rules | `apps/api/app/main.py` |
| Non-root API container | `apps/api/Dockerfile` |
| Demo seed disabled in production | `apps/api/app/bootstrap.py` |
| Dev mail inbox closed unless explicitly enabled on localhost | `apps/api/app/routers/devmail.py`, `deploy/.env.example` |

## Handling secrets

`LD_SECRET` protects encrypted database values and signed tokens. Treat a leaked `LD_SECRET` as a full compromise: rotate it, set `LD_SECRET_OLD` during the migration, and follow the rotation steps in [docs/DEPLOY.md](docs/DEPLOY.md). Removing an old key before the rows are re-encrypted makes those rows unreadable.

Do not paste production logs, database dumps, `.env` files, or model checkpoints into an issue. Use the private reporting channel for anything sensitive.
