# Feature: sign in

The entry to every other flow. Proven by `apps/frontend/e2e/core-loop.spec.ts`, **step 1, Sign in**.
This file is the feature reference for [VERIFY.md](../VERIFY.md); it does not restate the Playwright
code.

## Starting state

- Signed out: no session cookie or token in the browser profile.
- The browser opens `/` (the public landing page).
- The API is up and the demo seed exists (see Doctor in [VERIFY.md](../VERIFY.md)).

## Route

| Step | URL |
| --- | --- |
| Start | `http://127.0.0.1:<webPort>/` |
| After the Log in link | `http://127.0.0.1:<webPort>/login` |
| After the demo password | `http://127.0.0.1:<webPort>/labeldesk-demo` |

## Selectors

| Element | Selector used by the spec |
| --- | --- |
| Landing sign-in link | `getByRole('link', { name: 'Log in' }).first()` |
| Email field | `getByLabel('Email')` |
| Password field | `getByLabel('Password')` |
| Submit | `getByRole('button', { name: 'Sign in' })` |
| Error banner | `getByRole('alert')` |
| Workspace heading | `getByRole('heading', { name: 'Projects' })` |

## Actions and expected result

1. Click **Log in** on `/`.
   - Expected: the URL is `/login` and the sign-in form is visible.
2. Fill Email `demo@labeldesk.dev` and Password `wrong-password`; click **Sign in**.
   - Expected: the alert contains `invalid email or password` (case-insensitive), and the URL is
     still `/login`.
3. Replace the password with `demo1234`; click **Sign in**.
   - Expected: the URL is `/labeldesk-demo`, and the heading `Projects` is visible.
   - Expected: the workspace reply contains the seeded project list; no browser console error remains
     after the rejected attempt is cleared.

The demo account and the seed require `LD_SEED_DEMO=1` outside production. The wrong password must
never create a session.

## Failure conditions

| Symptom | Meaning |
| --- | --- |
| No alert, or the alert text is not `invalid email or password` | the sign-in failure is not the seeded contract; the card under test is wrong, or the API error shape changed |
| Wrong password lands on `/labeldesk-demo` | authentication accepted bad credentials; stop, this is a security finding |
| Correct password stays on `/login` or shows an alert | the seed is missing, the API is down, or the session cookie is rejected |
| URL is right but the `Projects` heading is absent | the workspace did not load; check the API log by request id |
| A console error remains after the rejected attempt is cleared | a frontend regression; the spec fails on it |

## API proof (same failure, without the browser)

Useful when the form fails and the cause is unclear. It is also the Doctor seed check.

```powershell
'{"email":"demo@labeldesk.dev","password":"wrong-password"}' |
  Set-Content "$run/login-wrong-body.json" -Encoding ascii
curl.exe -sS -o "$run/login-wrong.json" -w "%{http_code}" `
  -H 'Content-Type: application/json' --data-binary "@$run/login-wrong-body.json" `
  "http://127.0.0.1:<apiPort>/api/auth/login"
Get-Content "$run/login-wrong.json" -Raw
```

Expected: status `401` and a body whose `detail` is `invalid email or password`. The matching request
appears in the API log as one JSON line with `route: "/api/auth/login"`, `status: 401` and a
`request_id`; that id joins every line of the attempt.

## Evidence

- Playwright step result and screenshot from `$evidence/playwright-report/`.
- The `401` and `200` login lines in `$evidence/login-log-lines.json`, joined by
  `$evidence/request-id-lines.txt`.
- The console-error assertion in the spec: the rejected login is the one expected `401`; every later
  step must be clean.
