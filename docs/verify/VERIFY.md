# Verify a LabelDesk change in the running app

Unit tests prove a function; this route proves the flow. Run it from a lane worktree, once per card,
before the card goes to review. It has five stages: **Launch, Doctor, Drive, Evidence, Cleanup**.

The route runs on Windows PowerShell 5.1, from `apps/frontend/e2e` (the T-1200 harness) and
`apps/backend`. It never reads or writes the main checkout.

## Set the run variables

```powershell
$card = 'T-1102'
$wt   = 'B:/02_Projects/ld-worktrees/t-1102'          # this lane's worktree, never E:/02_Projects/auto_label
$wtPath = (Resolve-Path $wt).Path                     # backslash form, for process checks
$evidence = "B:/02_Projects/ld-tmp/evidence/$card"
$run      = "B:/02_Projects/ld-tmp/verify/$card"      # this run's throwaway data and logs
$env:TMP  = 'B:\02_Projects\ld-tmp\pytest'
$env:TEMP = $env:TMP

if ($wt -eq 'E:/02_Projects/auto_label') { throw 'BLOCKED: the main checkout is read-only' }
New-Item -ItemType Directory -Force $evidence, $run | Out-Null
```

The demo seed writes to `$run/data`, never to `apps/backend/data`. Login in every stage is
`demo@labeldesk.dev` / `demo1234`, created by `LD_SEED_DEMO=1` on first start.

## 1. Launch

**1a. Install inside the worktree.** One venv and one `npm ci` per lane; never in the main checkout.

```powershell
cd "$wt/apps/backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt

cd "$wt/apps/frontend"
npm ci
```

Completion criterion: both commands exit `0`, and `"$wt/apps/backend/.venv/Scripts/python.exe"` and
`"$wt/apps/frontend/node_modules"` exist.

**1b. Pick two free ports.** A port that is already listening is a BLOCKED, not something to reuse.

```powershell
function Get-FreePort {
  $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
  $l.Start(); $port = ([System.Net.IPEndPoint]$l.LocalEndpoint).Port; $l.Stop(); $port
}
$apiPort = Get-FreePort
do { $webPort = Get-FreePort } while ($webPort -eq $apiPort)
"api=$apiPort web=$webPort" | Set-Content "$run/ports.txt"

# Playwright uses fixed names under TMP; remember what this run did not create, so Cleanup
# never deletes another lane's state.
@{
  data  = Test-Path "$env:TMP/labeldesk-e2e-data"
  log   = Test-Path "$env:TMP/labeldesk-e2e-api.log"
  ports = Test-Path "$env:TMP/labeldesk-e2e-ports.json"
} | ConvertTo-Json | Set-Content "$run/playwright-temp-before.json"
```

**1c. Start the API and the web app, and record their PIDs.** The API is the real `app.main:app`;
Drive below starts its own T-1200 instance with the fake worker. Because `LD_DATA_DIR` points at the
empty `$run/data` and `LD_SEED_DEMO=1`, this first start creates and seeds the demo workspace.

```powershell
$env:LD_DATA_DIR        = "$run/data"
$env:LD_SEED_DEMO       = '1'
$env:LD_EMBEDDED_WORKER = '1'
$env:LD_MAIL_DEV        = '1'
$env:LD_RATE_LIMIT      = '0'
$env:LD_ENV             = 'development'
$env:LD_SECRET          = 'labeldesk-verify-only-secret-0123456789abcdef'

$api = Start-Process -FilePath "$wtPath\apps\backend\.venv\Scripts\python.exe" `
  -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$apiPort") `
  -WorkingDirectory "$wtPath\apps\backend" -PassThru `
  -RedirectStandardOutput "$run/api.out.log" -RedirectStandardError "$run/api.err.log"

$env:LD_API_PROXY = "http://127.0.0.1:$apiPort"
$web = Start-Process -FilePath 'node.exe' `
  -ArgumentList @("$wtPath\apps\frontend\node_modules\vite\bin\vite.js",'--host','127.0.0.1','--port',"$webPort",'--strictPort') `
  -WorkingDirectory "$wtPath\apps\frontend" -PassThru `
  -RedirectStandardOutput "$run/web.out.log" -RedirectStandardError "$run/web.err.log"

@{ api_pid = $api.Id; web_pid = $web.Id; api_port = $apiPort; web_port = $webPort } |
  ConvertTo-Json | Set-Content "$run/pids.json"
Get-Content "$run/pids.json"
```

Completion criterion: `pids.json` holds two live PIDs that this shell started.

**1d. Wait for readiness.** `/api/readyz` is the API gate (database, data directory, secret, worker);
the frontend gate is an HTTP `200` on the Vite root.

```powershell
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
  curl.exe -fsS "http://127.0.0.1:$apiPort/api/readyz" 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 1
}
$webReady = $false
for ($i = 0; $i -lt 120; $i++) {
  curl.exe -fsS "http://127.0.0.1:$webPort/" 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $webReady = $true; break }
  Start-Sleep -Seconds 1
}
if (-not $ready)    { throw "BLOCKED: API not ready; see $run/api.err.log" }
if (-not $webReady) { throw "BLOCKED: web app not ready; see $run/web.err.log" }
curl.exe -fsS "http://127.0.0.1:$apiPort/api/readyz" | Set-Content "$evidence/readyz.json"
Get-Content "$evidence/readyz.json"
```

Completion criterion: `readyz.json` contains `"ok":true` and all four checks `true`.

## 2. Doctor

Prove the instance belongs to this run before trusting a result. Any failed check is **BLOCKED**:
stop, write the reason in the report, and do not claim the change works.

```powershell
$dr = Get-Content "$run/pids.json" | ConvertFrom-Json
$apiProc = Get-CimInstance Win32_Process -Filter "ProcessId=$($dr.api_pid)"
$webProc = Get-CimInstance Win32_Process -Filter "ProcessId=$($dr.web_pid)"

# Worktree and port, from the processes this run started.
if ($apiProc.ExecutablePath -notlike "$wtPath*") { throw "BLOCKED: API PID is not this worktree: $($apiProc.ExecutablePath)" }
if ($webProc.CommandLine -notlike "*$wtPath*")   { throw "BLOCKED: web PID is not this worktree: $($webProc.CommandLine)" }
if ($apiProc.CommandLine -notlike "*--port $($dr.api_port)*") { throw 'BLOCKED: API PID is not on the recorded port' }
if ($webProc.CommandLine -notlike "*--port $($dr.web_port)*") { throw 'BLOCKED: web PID is not on the recorded port' }

# Nobody else owns those ports. On Windows a venv launcher may hand the socket to its child,
# so the listener must be the recorded PID or one of its descendants.
function Test-RunProcess([int]$ownerPid, [int]$rootPid) {
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
  for ($i = 0; $i -lt 5 -and $p; $i++) {
    if ($p.ProcessId -eq $rootPid) { return $true }
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)" -ErrorAction SilentlyContinue
  }
  return $false
}
$apiOwner = (Get-NetTCPConnection -LocalPort $dr.api_port -State Listen).OwningProcess
$webOwner = (Get-NetTCPConnection -LocalPort $dr.web_port -State Listen).OwningProcess
if (-not (Test-RunProcess $apiOwner $dr.api_pid)) { throw 'BLOCKED: API port is owned by another process' }
if (-not (Test-RunProcess $webOwner $dr.web_pid)) { throw 'BLOCKED: web port is owned by another process' }

# The seed is present: wrong password must fail, the demo account must succeed.
# Write the JSON body to a file: PowerShell 5.1 strips double quotes from an inline native argument.
'{"email":"demo@labeldesk.dev","password":"wrong-password"}' | Set-Content "$run/login-wrong-body.json" -Encoding ascii
$wrongStatus = curl.exe -sS -o "$run/login-wrong.json" -w "%{http_code}" `
  -H 'Content-Type: application/json' --data-binary "@$run/login-wrong-body.json" `
  "http://127.0.0.1:$($dr.api_port)/api/auth/login"
$wrongBody = Get-Content "$run/login-wrong.json" -Raw
if ($wrongStatus -ne '401' -or $wrongBody -notmatch 'invalid email or password') {
  throw "BLOCKED: expected 401 invalid email or password, got $wrongStatus $wrongBody"
}

'{"email":"demo@labeldesk.dev","password":"demo1234"}' | Set-Content "$run/login-demo-body.json" -Encoding ascii
$login = curl.exe -sS -H 'Content-Type: application/json' --data-binary "@$run/login-demo-body.json" `
  "http://127.0.0.1:$($dr.api_port)/api/auth/login" | ConvertFrom-Json
if (-not $login.token) { throw 'BLOCKED: demo seed missing (login returned no token)' }

@{ worktree = $wt; api_pid = $dr.api_pid; web_pid = $dr.web_pid
   api_port = $dr.api_port; web_port = $dr.web_port
   readyz = (Get-Content "$evidence/readyz.json" -Raw | ConvertFrom-Json)
   wrong_password_status = [int]$wrongStatus; demo_login = 'ok' } |
  ConvertTo-Json -Depth 5 | Set-Content "$evidence/doctor.json"
Get-Content "$evidence/doctor.json"
```

Completion criterion: `doctor.json` names this worktree, the two recorded PIDs and ports, the readyz
payload, `wrong_password_status: 401` and `demo_login: "ok"`.

**Unusable environment, in order of likelihood.** Missing seed: the wrong-password check returns `401`
but the demo login returns `401` too; stop and check `LD_SEED_DEMO` and `LD_DATA_DIR`. API down:
`readyz` never answers; read `$run/api.err.log`. Locked port: `Start-Process` exits, or the listener is
owned by a PID this run did not record; pick new ports and start again, never stop the other process.

## 3. Drive

The harness starts the **real API through `apps/backend/e2e/app.py`** (fake jobs, no GPU) and the Vite
dev server on its own free ports, wipes its own data directory, and seeds the demo workspace. Put the
worktree venv first on `PATH` so its `python` is the one Playwright starts.

```powershell
$env:PATH = "$wtPath\apps\backend\.venv\Scripts;$env:PATH"
$env:PLAYWRIGHT_HTML_REPORT = "$evidence/playwright-report"
$env:PLAYWRIGHT_HTML_OPEN   = 'never'
cd "$wt/apps/frontend"
npm run e2e -- e2e/core-loop.spec.ts --reporter=html,list --trace=on --output="$evidence/playwright-results"
$e2eExit = $LASTEXITCODE
"npm run e2e exit=$e2eExit" | Tee-Object "$evidence/e2e-exit.txt"
```

Completion criterion: exit `0`, `1 passed`, and the HTML report and trace exist under `$evidence`.

Feature map, one file per feature under [`features/`](features/):

| Feature | Spec and step | Route | Expected result | Detail |
| --- | --- | --- | --- | --- |
| Sign in, including the wrong-password failure | `e2e/core-loop.spec.ts`, step 1 | `/login` | wrong password shows `invalid email or password`; demo password lands on `/labeldesk-demo` with the `Projects` heading | [features/auth.md](features/auth.md) |
| Open the seeded project | `e2e/core-loop.spec.ts`, step 2 | `/labeldesk-demo` → `/labeldesk-demo/p/ppe-detection/browse` | `Dataset` heading and breadcrumb `PPE Detection` | [features/project-open.md](features/project-open.md) |
| Upload one image | `e2e/core-loop.spec.ts`, step 3 | `/labeldesk-demo/p/ppe-detection/upload` | `Uploaded 1 … failed 0`, then `one.jpg` is in the dataset | [features/upload.md](features/upload.md) |

A new feature gets its own `features/<name>.md` in the same shape: starting state, route, selectors,
actions, expected result, failure conditions, spec.

## 4. Evidence

Save everything under `B:/02_Projects/ld-tmp/evidence/<card>/`; the report links this folder, not a
terminal scrollback. Record each stage command with the exit code it returned:

| Stage | Command | Exit code |
| --- | --- | --- |
| 1a | `python -m venv .venv` | |
| 1a | `.venv\Scripts\python.exe -m pip install -r requirements.txt` | |
| 1a | `npm ci` | |
| 1d | `curl.exe -fsS http://127.0.0.1:<apiPort>/api/readyz` | |
| 3 | `npm run e2e -- e2e/core-loop.spec.ts --reporter=html,list --trace=on --output=<evidence>/playwright-results` | |

```powershell
Copy-Item "$env:TMP/labeldesk-e2e-api.log" "$evidence/e2e-api.log" -Force
$lines = Get-Content "$evidence/e2e-api.log" | ForEach-Object { try { $_ | ConvertFrom-Json } catch { } }
$logins = $lines | Where-Object { $_.route -eq '/api/auth/login' }
$logins | ConvertTo-Json -Depth 5 | Set-Content "$evidence/login-log-lines.json"
$ids = $logins.request_id | Sort-Object -Unique
$ids | ForEach-Object { Select-String -Path "$evidence/e2e-api.log" -SimpleMatch $_ | ForEach-Object Line } |
  Set-Content "$evidence/request-id-lines.txt"
$ids | Set-Content "$evidence/request-ids.txt"

# The trace bundles the action screenshots; unzip it so a reviewer can see them without the viewer.
$trace = Get-ChildItem "$evidence/playwright-results" -Recurse -Filter trace.zip | Select-Object -First 1
if (-not $trace) { throw 'BLOCKED: no trace.zip in the Playwright output' }
Expand-Archive $trace.FullName -DestinationPath "$evidence/trace" -Force
Get-ChildItem "$evidence/trace/resources" -Filter *.jpg | Select-Object -First 5
Get-ChildItem "$evidence" -Recurse -File | Select-Object FullName, Length
```

Completion criterion: `login-log-lines.json` has one `401` line and one `200` line for
`/api/auth/login`, each with a `request_id`; `request-ids.txt` lists those ids; the HTML report,
`trace.zip` and the unzipped action screenshots are in the folder.

What to hand the reviewer:

| Evidence | Path |
| --- | --- |
| Commands and exit codes | the report's command table |
| Readiness and environment | `$evidence/readyz.json`, `$evidence/doctor.json` |
| Playwright result | `$evidence/playwright-report/index.html`, `$evidence/e2e-exit.txt` |
| Screenshot and trace | `$evidence/playwright-results/**/trace.zip`, `$evidence/trace/resources/*.jpg` (the trace's action screenshots) |
| API log joined by request id | `$evidence/e2e-api.log`, `$evidence/login-log-lines.json` |

## 5. Cleanup

Stop only the PIDs recorded in `pids.json`, and delete only the state this run created. The evidence
stays; the worktree venv and `node_modules` stay for the lane's next run.

```powershell
$dr = Get-Content "$run/pids.json" | ConvertFrom-Json
$before = Get-Content "$run/playwright-temp-before.json" | ConvertFrom-Json
$webProc = Get-CimInstance Win32_Process -Filter "ProcessId=$($dr.web_pid)"
if ($webProc -and $webProc.CommandLine -like "*$wtPath*") { taskkill /PID $dr.web_pid /T /F | Out-Null }
$apiProc = Get-CimInstance Win32_Process -Filter "ProcessId=$($dr.api_pid)"
if ($apiProc -and $apiProc.ExecutablePath -like "$wtPath*") { taskkill /PID $dr.api_pid /T /F | Out-Null }
Start-Sleep -Seconds 2                       # let SQLite release the data directory
Remove-Item -Recurse -Force $run

# Playwright's own temp state: delete only the paths this run created.
if (-not $before.data)  { Remove-Item -Recurse -Force "$env:TMP/labeldesk-e2e-data" -ErrorAction SilentlyContinue }
if (-not $before.log)   { Remove-Item -Force "$env:TMP/labeldesk-e2e-api.log" -ErrorAction SilentlyContinue }
if (-not $before.ports) { Remove-Item -Force "$env:TMP/labeldesk-e2e-ports.json" -ErrorAction SilentlyContinue }
```

Completion criterion: neither recorded PID is alive, the ports no longer listen, `$run` is gone, and
the evidence folder is intact. A process this run did not start is never stopped: if the command line
no longer matches the recorded worktree, leave it alone and note it.

## Hard rules

- **Main checkout is read-only.** Every install, server and test runs under `$wt`.
- **Free ports only.** A port already in use means pick another one; never kill the owner.
- **No real hardware.** Drive uses `e2e/app.py`; it does not call a GPU, vLLM, SAM or an external URL.
- **Assertions stay as written.** A failing step is a finding for the card that owns it, not a spec to
  loosen. A card's own change is proven by its own spec; this route runs the shared specs that cover
  the flow it touched.
