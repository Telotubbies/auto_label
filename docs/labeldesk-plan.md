> **Status (2026-10-30):** implemented in [`apps/`](../apps/README.md); deployment in [`DEPLOY.md`](DEPLOY.md). Kept for history.

# LabelDesk — consolidated plan (supersedes clone_plan.md scope)

> Roboflow-style labeling platform ของตัวเอง ชื่อ LabelDesk — ~100 users, single GPU host.
> Design reference: `design-ref/roboflow/` (29 screens + tokens + module tree).

## Stack (locked)

| ส่วน | เลือกใช้ | สถานะในโค้ดตอนนี้ |
|---|---|---|
| Frontend | Vite + React 19 + TS | ✅ มี |
| UI | Tailwind v4 + shadcn-style + Lucide | ✅ (hand-rolled primitives — swap shadcn/Radix ทีหลังได้) |
| Router | TanStack Router | ⏳ migrate จาก react-router v7 (task T-ROUTE) |
| Data | TanStack Query | ⏳ wrap `lib/api.ts` (task T-QUERY) |
| Big lists | TanStack Virtual | ⏳ Browse grid (task T-VIRT) |
| Annotate | react-konva + Zustand | ✅ editor ทำงานแล้ว; เพิ่ม Smart Polygon + approve/reject |
| Backend | FastAPI | ✅ skeleton; ต้องต่อ pipeline จริง |
| DB/files | PostgreSQL + MinIO | ⏳ compose profile; `DATABASE_URL` fallback sqlite |
| GPU jobs | Redis + worker | ⏳ `api/worker.py` → `pipeline_cli.py` / `inference.py` |
| Auth | JWT roles Admin/Labeler/Reviewer (+OIDC ทีหลัง) | ครึ่ง — เพิ่ม roles guard |
| Deploy | Docker Compose เครื่องเดียว | ⏳ `docker-compose.labeldesk.yml` |

## Task map (spec → work)

| # | Spec | Task | ไฟล์หลัก |
|---|---|---|---|
| T-NAME | ชื่อ LabelDesk | rename title/logo/sidebar/login | index.html, shell.tsx, Login.tsx |
| T-ROUTE | TanStack Router | migrate routes (code-based) | App.tsx → router.tsx |
| T-QUERY | TanStack Query | `useQuery`/`useMutation` ทุก list+save | lib/api.ts + features |
| T-VIRT | virtual grid | Browse uses `<Grid>` virtualizer | Browse.tsx |
| T-UP | upload | dropzone + per-file progress + dedupe hash (SHA-256 ฝั่ง client เทียบ server) | Upload.tsx, api /uploads |
| T-KANBAN | kanban 4 คอลัมน์ | Unassigned→Annotating→Review→Done + assignment to user | AnnotateBoard.tsx, api /jobs, /assignments |
| T-EDITOR | editor เต็ม | tool rail ครบ, shortcuts, undo/redo, **approve/reject**, **Smart Polygon→SAM 3.1** | Editor.tsx |
| T-SAM | smart polygon | POST /infer/sam-point {image_id, points[]} → mask→polygon | api → `sam3_auto_label/src/inference.py` |
| T-DS | dataset filters | filter by class/status/split + raw query | Browse.tsx + api |
| T-VER | versions | preprocess+augment config → export 11 formats ผ่าน `exporters.py` | misc.tsx Versions, api /versions/{id}/export |
| T-TRAIN | train | launch `yolo26_ppe` 02_train + mAP chart + confusion matrix (อ่าน `reports/inputs/final_eval_results.json`) | misc.tsx Train, api /jobs/train |
| T-DEP | deploy | ONNX download + test-image inference | misc.tsx ProjDeploy, api /models/{id}/infer |
| T-DB | postgres+minio | SQLAlchemy models + presigned upload/download | api/db.py, api/storage.py |
| T-JOBS | redis worker | enqueue sam/train/export jobs, poll status | api/worker.py, api/queue.py |
| T-AUTH | roles guard | Admin/Labeler/Reviewer on routes + nav | store.ts, api deps |
| T-COMPOSE | docker | compose: web, api, postgres, minio, redis, worker(gpu) | docker-compose.labeldesk.yml |

## Order of execution

1. Quick deltas (this session): rename, Review column, approve/reject UI, deps, compose file, api extension stubs
2. T-QUERY + T-VIRT + T-ROUTE (frontend plumbing)
3. T-DB + T-JOBS + T-UP (backend plumbing)
4. T-EDITOR + T-SAM (the money feature — ใช้ SAM 3.1 จริงของ repo)
5. T-KANBAN + T-DS + T-VER + T-TRAIN + T-DEP
6. Pixel-diff polish vs `design-ref/` + Docker Compose bring-up
