# Clone Plan: Roboflow Console → auto_label Web UI

> เป้าหมาย: web app หน้าตาเหมือน `app.roboflow.com` ทุกหน้าของ console สำหรับ pipeline
> SAM 3.1 + YOLO26 ใน repo นี้ — user ~100 คน — React ทันสมัย — ผู้ใช้จะแก้ต่อเองหลังส่งมอบ

## Target

- URL: `https://app.roboflow.com/<workspace>` (หลัง login — user login เองใน Chrome debug profile)
- Scope: **ทุกหน้าของ console**
- Viewports: `1440×1400` (primary), `1920×1200` (large desktop) — Roboflow console เป็น desktop app; mobile ยิงไว้ดูเฉย ๆ ไม่ใช่เป้าหมาย
- Fidelity bar: side-by-side screenshot diff ≥ 90% ที่ 1440×1400 ทุกหน้า

## วิธี capture (ไม่ใช่ "download source")

`app.roboflow.com` ship ออกมาเป็น minified webpack bundle — โหลดมาอ่าน/ใช้ต่อไม่ได้
วิธีที่ได้ผลเหมือน 100%: **drive เบราว์เซอร์จริงผ่าน CDP** แล้วดึง

- screenshot matrix ทุกหน้า / ทุก state (hover, modal, empty state)
- Sniper CSS: computed style เฉพาะ property ที่ต้องการ (ห้าม dump `getComputedStyle` ทั้งก้อน)
- fonts (`@font-face` + `.woff2` URLs), inline SVG icons, favicon/logo
- DOM structure → แปลงเป็น semantic React (ไม่ copy div-soup)
- animation detection (CSS/JS lib) → Framer Motion equivalent

**เครื่องมือ (ใช้ซ้ำจาก clone Datadog รอบก่อน):**

- `E:\03_Thesis\webservice\scripts\cdp.py` — `CDP_PORT=9223 python -X utf8 cdp.py list|eval <substr> "<js>"`
- `dd-sniper.js`, `dd-text.js`, `dd-layout.js`, `dd-assets.js`, `dd-components.js`, `dd-vocab.js`, `dd-sprite.js`, `dd-merge.py` — copy มา adapt เป็น `rf-*.js`
- Chrome profile ใหม่ `E:\chrome-rf` + `--remote-debugging-port=9223`
- **Gotcha (จาก observation log):** ห้ามเขียน capture ลง dir ที่ gitignore (read tool เปิดไม่ได้) → เก็บที่ `design-ref/roboflow/` (ไม่ติด ignore แล้วเช็กแล้ว); CDP Chrome เล่น `<video>` autoplay ไม่ได้ → ถ้าเจอวิดีโอให้ดึง poster frame

## Screens ที่ต้องยิง (checklist)

| # | Route (Roboflow) | เนื้อหา |
|---|---|---|
| 1 | `/` workspace home | sidebar ซ้าย, topbar, project cards grid, usage stats |
| 2 | `/{ws}/{project}` | project overview, health check, dataset summary |
| 3 | `/{ws}/{project}/images` | image grid, filters, upload drag-drop modal |
| 4 | `/{ws}/{project}/annotate` | **annotation canvas** — left tool rail, canvas, right panel (classes/annotations), top bar |
| 5 | `/{ws}/{project}/versions` | dataset versions table, generate modal |
| 6 | `/{ws}/{project}/models` / train | training config, job list, metrics |
| 7 | `/{ws}/{project}/deploy` | deployment options, code snippets, hosted API |
| 8 | `/{ws}/settings`, members, API keys | settings pages, invite flow |
| 9 | upload flow / empty states / modals / dropdowns / toasts | states รองทั้งหมด |
| 10 | login/signup pages | clone หน้าตาไว้ (auth logic เป็นของเรา) |

## Tech Stack (ตัดสินใจแล้ว)

| Layer | Choice |
|---|---|
| Frontend | `web/` — Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui |
| Routing/Data | react-router v7 + TanStack Query + Zustand (canvas/UI state) |
| Annotate canvas | **react-konva** — bbox + polygon + edit + zoom/pan + shortcuts + SAM-assist |
| Backend | `api/` — FastAPI + SQLAlchemy + SQLite (100 users พอ) + JWT auth (roles: admin/annotator/viewer) |
| Jobs | FastAPI BackgroundTasks → wrap `pipeline_cli.py` / `sam3_auto_label` (SAM batch, YOLO train) |
| Serve | dev: vite proxy → uvicorn :8000; prod: nginx static + uvicorn (ทีหลัง) |

## Folder Structure

```
auto_label/
  web/                  # Vite React app
    src/
      components/       # ui/ (shadcn), layout/ (AppShell, Sidebar, Topbar)
      features/         # workspace/, projects/, dataset/, annotate/, models/, deploy/, settings/, auth/
      lib/              # api client, tokens.css, utils
      assets/           # fonts (self-host), icons, media
  api/                  # FastAPI
    routers/            # auth, workspaces, projects, images, annotations, jobs, models
    core/               # config, security (JWT), db
    services/           # pipeline_adapter.py → pipeline_cli.py subprocess
  design-ref/roboflow/  # captures (screens/, tokens.json, assets/) — commit ได้
  docs/clone_plan.md    # ไฟล์นี้
```

## Design Tokens (เติมหลัง capture)

- Colors / typography / spacing / radii / shadows → `web/src/lib/tokens.css` + Tailwind theme
- Roboflow palette โดยคร่าว: light theme, purple accent, Inter font — **ยืนยันค่าจริงจาก capture เท่านั้น**

## Task Breakdown

| Task | Deliverable | Verify |
|---|---|---|
| T0 Capture | `design-ref/roboflow/` ครบ 10 screens × 2 viewports + tokens.json + assets | checklist ตาราง Screens ข้างบนครบ |
| T1 Tokens | `tokens.css` + Tailwind theme + รายชื่อ component inventory | ตาราง token ในไฟล์นี้เต็ม |
| T2 Scaffold | `web/` run ได้ + `api/` `/health` + JWT login/register | `npm run dev` เปิดได้, `pytest api/` pass |
| T3 AppShell + Home | sidebar/topbar/workspace home + projects grid | pixel-diff ≥90% |
| T4 Dataset | images grid + upload modal + filters | pixel-diff ≥90% |
| T5 Annotate | canvas ครบ: bbox/polygon/select/pan/zoom, class panel, annotation list, prev/next, shortcuts, SAM-assist endpoint | manual test + pixel-diff |
| T6 Versions/Models/Deploy/Settings | ครบทุกหน้าที่เหลือ | pixel-diff ≥90% |
| T7 Backend wiring | CRUD จริง + SAM job ผ่าน pipeline_cli (dry-run ได้) | API tests + e2e flow demo |
| T8 Polish | checklist clone-anywebsite ครบ + no console errors | final stitch compare |

## Review Focus (สิ่งที่น่าจะพัง)

1. **Annotate canvas fidelity** — Roboflow ใช้ canvas+DOM overlay ผสม; react-konva อาจ render ต่างเล็กน้อย → เทียบ screenshot เป็นหลัก ไม่ไล่ pixel-perfect ระดับ sub-pixel
2. **SAM-assist latency** — SAM 3.1 รันบน WSL2 ROCm; API ต้อง async job + progress, ห้าม block request
3. **Auth ง่าย ๆ ก็ยังต้องถูก** — JWT secret ใน env, bcrypt hash, refresh flow, role guard ทั้ง front/back
4. **Images ขนาดใหญ่** — thumbnail generation + lazy load; อย่าเสิร์ฟ raw 4K ทั้ง grid
5. **License/asset** — clone หน้าตา/flow ได้ แต่ logo ชื่อ "Roboflow" ห้ามใช้ → แบรนด์เป็น `auto_label` / ชื่อ workspace ของตัวเอง

## Phase 0: Capture Session (ทำตอนนี้)

1. เปิด Chrome: `--remote-debugging-port=9223 --user-data-dir=E:\chrome-rf https://app.roboflow.com`
2. User login เอง (ผมไม่แตะ credential)
3. ผมยิง screenshot + extract ทีละหน้า — คุณอาจต้องช่วยคลิกเข้าหน้าที่ต้องใช้ dataset จริง (annotate ต้องมี image + class อยู่แล้วถึงเห็น UI เต็ม)
