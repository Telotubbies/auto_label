import { defineConfig, devices } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import type { AddressInfo } from 'node:net'
import { tmpdir } from 'node:os'
import path from 'node:path'

// The smoke run owns its store: a fresh seed every time, and apps/backend/data is never touched.
// The wipe runs once, in the server command below; doing it at config load races a second load.
const dataDir = path.join(process.env.TMP || tmpdir(), 'labeldesk-e2e-data')

// The API's output, so a failed sign-in can name it instead of a bare timeout (see e2e/fixtures).
const apiLog = path.join(process.env.TMP || tmpdir(), 'labeldesk-e2e-api.log')

// Playwright evaluates this file in the runner and again in the worker process, so a port chosen
// here must survive the second load: the first load writes it down, later loads read it.
const portFile = path.join(process.env.TMP || tmpdir(), 'labeldesk-e2e-ports.json')

const freePort = () => new Promise<number>((resolve, reject) => {
  const server = createServer()
  server.on('error', reject)
  server.listen(0, '127.0.0.1', () => {
    const { port } = server.address() as AddressInfo
    server.close(() => resolve(port))
  })
})

let ports: { api: number; web: number }
try {
  const saved = JSON.parse(readFileSync(portFile, 'utf8'))
  if (!saved.api || !saved.web || saved.api === saved.web) throw new Error('incomplete port file')
  ports = saved
} catch {
  const api = await freePort()
  let web = await freePort()
  while (web === api) web = await freePort()
  ports = { api, web }
  writeFileSync(portFile, JSON.stringify(ports))
}
const { api: apiPort, web: webPort } = ports

const apiUrl = `http://127.0.0.1:${apiPort}`
const webUrl = `http://127.0.0.1:${webPort}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: webUrl,
    trace: 'retain-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'e2e', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // e2e/app.py is the real API with the fake worker; it refuses to start without LD_E2E=1.
      command: `python -c "import os,shutil;shutil.rmtree(os.environ['LD_E2E_DATA'],ignore_errors=True)" && python -m uvicorn e2e.app:app --host 127.0.0.1 --port ${apiPort} > "${apiLog}" 2>&1`,
      cwd: path.resolve(import.meta.dirname, '../backend'),
      url: `${apiUrl}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        LD_DATA_DIR: dataDir,
        LD_E2E_DATA: dataDir,
        LD_E2E: '1',
        LD_EMBEDDED_WORKER: '1',
        LD_MAIL_DEV: '1',
        LD_RATE_LIMIT: '0',          // the suite signs in once per spec, past the 8-per-5-minutes login limit
        LD_SEED_DEMO: '1',
        LD_SUPERADMINS: 'demo@labeldesk.dev',
        LD_ENV: 'development',
        LD_SECRET: 'labeldesk-e2e-smoke-secret-0123456789',
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
      cwd: import.meta.dirname,
      url: webUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { ...process.env, LD_API_PROXY: apiUrl },
    },
  ],
})
