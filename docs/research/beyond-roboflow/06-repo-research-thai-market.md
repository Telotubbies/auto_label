# G6 — this repo's own research, plus the Thai market (2026-11-17)

Scope: the repo's `research/notes/` (fourteen notes in four Thai-named folders) and `reports/`
(four reports, also Thai) plus what Thai factories, safety teams, retailers, farms and CCTV
operators actually buy. Deduped against `docs/research/roboflow-parity/PARITY.md` (334 rows).

Method and caveats:

- The repo notes are mostly search-snippet research, not primary pages. Where a card leans on
  one, the source line says `via research/notes/...` and the URL is the one the note cites,
  **not** a page opened in this session. Pages I fetched myself are marked `[fetched]`.
- Code was read at HEAD `3bde0ba`, not `fe8ef1a` as the shared brief says. The authoritative
  list of what has shipped is the flag registry at `services/flags.py:21-34`: tasks 10b, 20c,
  22, 23 and **28 through 34, plus 36**, are on the branch behind `task_*` flags (suspect queue,
  anomaly station, tiling, workflow builder, Thai OCR, LINE/Slack/email alerts, edge presets,
  batch inference). Task 27 (semantic search, collections) and 35 (edge fleet) are **not**.
  Several items in `reports/ฟีเจอร์ที่ยังขาดเทียบคู่แข่ง.md` are therefore already built and do
  not appear as cards here — see the dedupe table.
- Evidence field is the only place line numbers appear; they drift by a few lines across merges.
- No Thai text in this file by design; the lead merges the owner summary.

## Already covered by PARITY.md (no card)

| Candidate from the repo notes | Where it already lives |
| --- | --- |
| Semantic search, collections, "more like this" | 1-F4.3, 2-F2.27–29 — still unbuilt; task 27 has not landed |
| Suspect-label queue from model/label disagreement | 5-F5.25, 6-F6.16; `services/suspects.py`, `services/suspect_queue.py` exist |
| Good-only anomaly station with threshold | 5-F5.52 (HAVE); `routers/anomaly.py`, `models/training.py:56` |
| Tiling / SAHI, tiled inference | 4-F4.23, 6-F6.35; `services/tiling.py` |
| No-code workflow builder, block catalogue | 6-F6.21–28 (an L-sized gap) |
| Batch inference over stored images | 6-F6.4; `services/batch_inference.py:43` now exists (task 36) |
| Edge export presets (ONNX/OpenVINO/INT8/Jetson/Hailo) | 4-F4.35, 6-F6.45; `services/edge.py:26-53` (task 34) |
| Thai document OCR with PII masks and template presets | Not a parity row; **built** at `services/ocr.py:27-56` — keep, but do not sell as a moat |
| LINE / Slack / email as an alert channel | 7-F7.51; **built** with throttle and quiet hours at `services/alerts.py:1-10,110-132` |
| Cross-workspace rollup for multi-site customers | 7-F7.61 (MISSING) — franchise dashboards are this row, not a new feature |
| MCP server / agent API, public dataset hub, blind model arena | 1-F2.5, 1-F4.4, 5-F5.27 |

The remaining 22 cards are the parts of the Thai-sector requirement set that neither parity
nor the shipped tasks 27–36 describe.

---

### G6.1 Lot-bound inspection record with a disposition (OK / NG / rework) (Thai factory QC, via `research/notes/ฟีเจอร์ที่ยังขาดเทียบคู่แข่ง/sector_use_cases.md`)
- **What the user does:** an inspector at the end of a line opens the station screen, the last inspected unit's verdict is already there, and they either accept it, flip it to NG with a defect class, or send it to rework with a reason. Every verdict is stamped with the lot (or work-order) number and the inspector's badge.
- **Who uses it:** a QC inspector on a two-shift line who must answer "which lot was this, who passed it, and what happened to the unit" a week later.
- **Flow:** 1. Station list (`/projects/:id/anomaly` today) → pick a station → `[empty]` "no units inspected since 06:00". 2. Verdict card shows the unit image, the model's regions, and two large buttons. 3. NG opens a defect-class picker limited to the line's taxonomy; rework opens a reason list and a due date. 4. Submit → `[loading]` synchronous write → the card moves to the next unit. 5. `[error: lot closed]` when the operator scans a lot that already shipped; the unit is blocked, not silently accepted.
- **Why it is easy:** one screen, two buttons and a class picker; the lot comes from a barcode scan or from the batch the images were uploaded under, so nothing is typed twice.
- **Products with it:** no fetched product ships a lot-bound disposition; the sector evidence that Thai electronics lines run AI inspection for PCB, packaging and HDD parts is [Unimon via research_notes](https://unimon.co.th/en/blog/thailand-manufacturing-ai-predictive-maintenance-guide), and the estate geography (Chonburi, Rayong, Laem Chabang) is [IEAT fetched](https://www.ieat.go.th/en).
- **Why it matters for LabelDesk:** we already have stations, thresholds and verdict-like anomaly results, but nothing that survives an audit. A defect model without a lot-bound record is a demo; with it, it replaces a paper checklist, which is what the buyer is actually paying to retire.
- **LabelDesk code evidence:** `models/training.py:56-60` (`AnomalyStation`: one station, one artifact, one threshold); `routers/anomaly.py:29-36` (station fields: name, threshold, status, artifact, metrics); `models/project.py:86-110` (`Image` has `batch_id` and `tags`, no lot/station/disposition field); `features/project/Anomaly.tsx:36-85` (heatmap and "suspicious regions", no verdict control).
- **Suggested status:** PARTIAL — the station object and a per-station threshold exist for anomaly only; there is no disposition, no lot binding, and no rework state.
- **Suggested priority / size:** Must / M.

### G6.2 First-pass yield and defect Pareto per lot, line and shift (Thai factory QC, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** opens a yield board, picks a line and a date range, and reads first-pass yield (units passing with no rework ÷ units inspected), the top five defect classes by count, and whether the drop started on the night shift or after a threshold change.
- **Who uses it:** a production or QA manager in the Monday meeting, and the engineer who has to explain why a line's yield fell 4 points.
- **Flow:** 1. Insights → Yield tab → `[empty]` "no dispositions recorded for this line" with a link to the station. 2. Line and date pickers; the board recomputes. 3. Table of lots with FPY, NG count and rework count; click a lot → the units behind the number. 4. `[loading]` on recompute; `[error: retention window]` when the range reaches past the project's retention policy.
- **Why it is easy:** the numbers come from dispositions already recorded at the station, so the board is a group-by, not a second data entry job.
- **Products with it:** no CV labelling product in this group publishes an FPY metric; the demand driver (inspector shortage and skill variance) is [Unimon via research_notes](https://unimon.co.th/en/blog/thailand-manufacturing-ai-predictive-maintenance-guide).
- **Why it matters for LabelDesk:** FPY is the number a factory director signs the renewal against. Our analytics stop at dataset and model quality, so the buyer has to export to a spreadsheet to prove the model paid for itself.
- **LabelDesk code evidence:** `services/insights.py` (distribution/geometry aggregates only); `routers/labeling.py:22-27` (labeler stats); `services/insights_dashboards.py:20-24` and `routers/dashboards.py:30-86` (widget dashboards, project-scoped, no yield widget). Searched `yield|rework|lot|traceab` across `apps/backend/app` — no match outside `batch_id`.
- **Suggested status:** MISSING — no disposition data exists to aggregate.
- **Suggested priority / size:** Must / M.

### G6.3 Reject signal to the machine over Modbus / OPC-UA / MQTT with a fail-safe (Thai factory QC, inference from `research/notes/.../sector_use_cases.md`)
- **What the user does:** binds one stream event to one output coil or tag ("NG on line 3 → coil 12 high for 300 ms"), then watches a signal log that records every pulse with the verdict that caused it, the latency, and whether the PLC acknowledged.
- **Who uses it:** an automation engineer at the integrator, with the line's PLC programmer in the room; not a data scientist.
- **Flow:** 1. Stream → Outputs → `[empty]` "no outputs bound" with a Modbus/OPC-UA/MQTT choice. 2. Endpoint form (host, port, unit id, tag), then a test pulse; `[error: connect refused]` and `[error: write rejected by PLC]` are different messages. 3. Bind a rule to the output, set pulse width and a dead-man timeout. 4. Signal log: time, event id, pulse sent, ack, latency. 5. `[error: comms lost]` banner on the stream with a stop-the-line option.
- **Why it is easy:** one binding form and one log; the fail-safe is a checkbox ("stop the conveyor if no verdict arrives in N ms") rather than code in a PLC.
- **Products with it:** none of the fetched platforms exposes an OT write path; the requirement is inferred in the sector note, and the closest shipped thing in this repo is the alert sink, which is HTTP only ([LINE Messaging API fetched](https://developers.line.biz/en/docs/messaging-api/sending-messages/) as the shape of an outbound call).
- **Why it matters for LabelDesk:** a factory cannot reject a part with a LINE message. Without an OT output we are a monitoring tool beside the line instead of a control in it, and the integrator cannot bill for the install.
- **LabelDesk code evidence:** `services/alerts.py:31` (`LINE_PUSH_URL`), `:217` (`_send_line`) — the only outbound integrations are LINE, Slack and email; `routers/webhooks.py` is HTTP. Searched `modbus|opc.?ua|mqtt|plc` across `apps/backend/app` — no match.
- **Suggested status:** MISSING — no OT connector of any kind.
- **Suggested priority / size:** Should / M.

### G6.4 Shift handover brief written at the end of a shift (Thai factory QC + safety, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** at 07:50 the outgoing operator or supervisor presses "hand over", reviews a one-screen brief (open NG units, unresolved reworks, cameras offline, threshold changes, alerts nobody acknowledged, yield so far), edits two lines of free text, and sends it to the incoming shift's LINE group and to the shift log.
- **Who uses it:** a shift supervisor handing over a production line or a security desk; the incoming person reads it on a phone.
- **Flow:** 1. Project → Ops → Handover → `[empty]` "nothing open this shift". 2. Auto-filled blocks with counts and links to the exact units. 3. Free-text notes, then send. 4. `[loading]` "building brief"; `[error: LINE group not configured]` with a link to channels. 5. The next shift's brief opens with "carried over from previous shift" items marked.
- **Why it is easy:** the list is assembled from state the product already holds (open reviews, offline cameras, unacknowledged events), so the human only types what a machine cannot know.
- **Products with it:** no fetched platform ships a shift handover artefact; the labour context (inspector shortage, skill variance) is [Unimon via research_notes](https://unimon.co.th/en/blog/thailand-manufacturing-ai-predictive-maintenance-guide).
- **Why it matters for LabelDesk:** handover is where defects and safety incidents get lost between shifts, and it is the cheapest artefact that makes the product part of a daily ritual rather than a dashboard somebody opens when something breaks.
- **LabelDesk code evidence:** `services/insights_stream.py` and `routers/insights.py` aggregate events, but no handover surface; searched `handover|shift` in `apps/backend/app` and `apps/frontend/src` — no match. Closest: `features/project/qa/Workforce.tsx` (labeler stats, not operations).
- **Suggested status:** MISSING — nothing assembles a shift summary.
- **Suggested priority / size:** Should / S.

### G6.5 Glove-first Thai operator screen at the station (Thai operations, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** stands at a 15-inch touch panel, taps a 64 px button with a gloved hand, and sees one verdict, one image and one instruction in Thai; no menu, no English, no scroll.
- **Who uses it:** a line operator who has never used an annotation tool, on a shared panel with a fixed camera and a barcode scanner.
- **Flow:** 1. Panel boots into a station-locked view (`[loading] connecting to station`) with the line name and shift. 2. Live frame, verdict badge, and two buttons: "pass" and "fail", both labelled in Thai on screen. 3. Fail → defect tiles with photos of each class, tap one. 4. Confirm → next unit. 5. `[error: camera offline]` fills the panel with the reason and the supervisor's phone number, because a blank screen makes the operator improvise.
- **Why it is easy:** one screen with two targets; the class picker uses photographs of real defects, so training a new operator is a two-minute conversation.
- **Products with it:** no fetched product in this group ships an operator kiosk; the requirement follows from the Thai-language floor in [IEAT-fetched estate context](https://www.ieat.go.th/en) and the Thai factory QC need recorded in the repo notes.
- **Why it matters for LabelDesk:** the current UI is a desktop annotation tool with no i18n layer. A buyer's operators cannot use it, which caps us at the QC engineer's desk and leaves the station to a competitor's appliance.
- **LabelDesk code evidence:** `apps/frontend/src/features/` has no station or kiosk feature (14 folders, listed); no Thai string anywhere in `src` (searched `Sarabun|buddhist|พ.ศ.`); `features/project/Anomaly.tsx` is a desktop card layout with sliders and a heatmap.
- **Suggested status:** MISSING — no i18n layer, no station-locked surface.
- **Suggested priority / size:** Must / L.

### G6.6 IC/PCB defect class pack with a pass/fail station (Thai electronics QC, `ml/sam3_auto_label/ic_defect_pipeline.py`)
- **What the user does:** creates a project from an "IC / PCB cosmetic defects" pack, gets a class set (burnt chip, damaged IC, scorched IC, cracked chip), passes/fails whole units rather than drawing boxes, and sees per-unit defect crops saved beside the verdict.
- **Who uses it:** an electronics QC engineer at a Chonburi or Lamphun plant who has a few hundred images and no ML team.
- **Flow:** 1. New project → sector pack list → `[empty]` "no pack installed" until one is chosen. 2. Pack installs classes, a station, a threshold and an example dataset pointer; `[loading]` per item. 3. Upload good units → anomaly fit; upload defects → class labels. 4. Station run → per-unit verdict plus `objects/defect_XX.png` crops. 5. `[error: too few good units]` names the minimum instead of failing at training time.
- **Why it is easy:** the defect vocabulary and the patch-anomaly recipe arrive pre-wired, so the first pass/fail run is an upload, not a research task.
- **Products with it:** no fetched platform ships a defect-class pack; the working recipe is this repo's own pipeline, and the demand is [Unimon via research_notes](https://unimon.co.th/en/blog/thailand-manufacturing-ai-predictive-maintenance-guide).
- **Why it matters for LabelDesk:** it is the only vertical where we have a demonstrated model, a class list and a station in one place — and the pack format is the reusable commercial unit for every other vertical here.
- **LabelDesk code evidence:** `ml/sam3_auto_label/ic_defect_pipeline.py:2-20` (DINOv3 patch bank + SAM 3.1, per-unit `defects.json`), `:251-254` (default prompts include "scorched ic", "cracked chip"); `routers/anomaly.py:23` (pack gate `task_29`); no pack registry in `models/project.py`.
- **Suggested status:** PARTIAL — the pipeline runs standalone and is not wired into the app; there is no pack format.
- **Suggested priority / size:** Must / M.

### G6.7 LINE alert with evidence and an acknowledgement ladder (Thai operations / safety, [LINE Messaging API fetched](https://developers.line.biz/en/docs/messaging-api/sending-messages/))
- **What the user does:** gets a LINE message with the snapshot, the zone, the time and three buttons; taps "acknowledge" and the incident closes, or does nothing and the next tier is paged after ten minutes.
- **Who uses it:** a site supervisor or security lead who lives in LINE and will not install another app.
- **Flow:** 1. Channel setup already exists (`[empty]` "no channel", `[error: LINE channel access token is required]`). 2. Rule → escalation policy: tier 1 person, tier 2 group, wait time per tier. 3. Device receives a Flex message with the snapshot and quick-reply buttons. 4. Tap → webhook postback → incident shows "acknowledged by X at hh:mm". 5. No tap → tier 2 fires; `[error: postback signature invalid]` is logged, not swallowed.
- **Why it is easy:** acknowledgement happens inside the chat the supervisor already has open, with no login and no app install.
- **Products with it:** LINE ships push/multicast and reply messages, image and Flex messages, quick replies and postback webhooks ([fetched](https://developers.line.biz/en/docs/messaging-api/sending-messages/)); the channel catalogue is at the [Messaging API index fetched](https://developers.line.biz/en/docs/messaging-api/).
- **Why it matters for LabelDesk:** we send one-way LINE messages today with no proof anyone read them, so an auditor cannot tell an ignored alert from a handled one. The ack ladder turns notifications into an incident record, which is the thing a safety buyer audits.
- **LabelDesk code evidence:** `services/alerts.py:1-10` (LINE Messaging API push; LINE Notify retired 2025-03-31), `:110-132` (throttle and quiet hours), `:200-210` (text body with snapshot link); `features/settings/Alerts.tsx:34-69` (channel card, test send, delivery list, active toggle); no postback route anywhere — searched `postback` across `apps/backend/app` — no match.
- **Suggested status:** PARTIAL — delivery, throttle and quiet hours work; acknowledgement, escalation tiers and read state do not exist.
- **Suggested priority / size:** Must / M.

### G6.8 Daily safety summary PDF for an inspector (Thai safety, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** at 17:00 opens "today's safety sheet", checks the counts, adds a remark, and downloads a two-page PDF: PPE compliance rate per zone, incidents with thumbnails, cameras offline, and the supervisor's name.
- **Who uses it:** a safety officer preparing for a factory inspector or an internal EHS audit; they need a document, not a dashboard.
- **Flow:** 1. Ops → Safety → Daily sheet → `[empty]` "no events yet today". 2. Preview with per-zone counts and a thumbnail strip; toggle zones in or out. 3. "Generate" → `[loading]` render → download. 4. `[error: no supervisor assigned]` blocks signing, because an unsigned sheet is not evidence.
- **Why it is easy:** one preview, one button, one file; the numbers are already computed for the stream dashboard.
- **Products with it:** no fetched platform generates a safety sheet; the Thai construction and manufacturing pilot evidence is [JETRO via research_notes](https://www.jetro.go.jp/ext_images/_News/announcement/2021/d38074f8efc798ae/NIPPONSTEELENGINEERING_en.pdf).
- **Why it matters for LabelDesk:** the dashboard is for us; the PDF is for the customer's regulator. Without it, every site rebuilds the report in Excel and our numbers never reach the person who signs.
- **LabelDesk code evidence:** no PDF or report generator — searched `pdf|weasy|reportlab|fpdf` across `apps/backend/app` — no match; `routers/dashboards.py:52-62` shares dashboards by token, which is the closest artefact.
- **Suggested status:** MISSING — no document output of any kind.
- **Suggested priority / size:** Should / M.

### G6.9 PPE and zone-intrusion pack installed in one step (Thai construction and factory safety, `ml/sam3_auto_label/config/ppe_4class.yaml`)
- **What the user does:** installs a pack that creates the four PPE classes with working thresholds, a zone rule for a machine area, a dwell rule for a walkway, and an alert channel stub; then points it at one RTSP camera and sees violations within an hour.
- **Who uses it:** a safety lead at a construction site or plant who has cameras and a rulebook but no model.
- **Flow:** 1. New project → Safety pack → `[empty]` until installed. 2. Pack summary lists classes, prompts, thresholds, rules and what is still unset. 3. Add camera (RTSP), draw one zone, test on a recorded clip. 4. Live: violations appear with clip thumbnails. 5. `[error: helmet class below threshold on this camera angle]` after a calibration sample, instead of months of silent misses.
- **Why it is easy:** the class set and thresholds are already tuned in this repo's pipeline, so the user draws one polygon instead of writing four prompts.
- **Products with it:** the four classes (person, helmet, closed footwear, harness) and their thresholds are this repo's own config; Thai helmet-detection accuracy varying by mounting point (73.7–89.5%) is [Thai Journal via research_notes](https://ph01.tci-thaijo.org/index.php/lej/article/view/265965).
- **Why it matters for LabelDesk:** PPE is the fastest land product in the region and we have a working class set. Shipping it as a pack, with the camera-angle caveat built into onboarding, converts a demo into a two-day install.
- **LabelDesk code evidence:** `ml/sam3_auto_label/config/ppe_4class.yaml:1-16` (person 0.7, helmet 0.25, closed footwear 0.25, harness 0.25); `ml/sam3_auto_label/README.md:3`; `streams/rules.py:1-19` (count/zone/line/dwell engine); no pack installer — `Home.tsx:14-20` creates a blank project from a type card.
- **Suggested status:** PARTIAL — classes, rules and prompts all exist separately; nothing installs them together.
- **Suggested priority / size:** Must / S.

### G6.10 Shelf-gap and planogram slot compliance (Thai retail, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** photographs or streams a bay, and the product returns each shelf row as slots: filled, empty, wrong product, or blocked by a carton. A gap becomes a task ("row 3, 4 facings missing") and closes when the next capture shows it filled.
- **Who uses it:** a store or area manager running a planogram audit across branches, and a merchandiser who needs the gap list before a supplier visit.
- **Flow:** 1. Project → Shelf audit → define a bay layout by drawing shelf lines once. 2. Capture from a phone or an existing camera. 3. Result: per-slot status with a confidence, and `[empty]` "bay matches planogram" when nothing is wrong. 4. Gap list → assign → re-capture → auto-close. 5. `[error: shelf lines do not match this photo]` when the camera moved.
- **Why it is easy:** the layout is drawn once per bay and reused on every capture; the output is a short list of exceptions, not a picture of a shelf.
- **Products with it:** no fetched shelf-analytics product was confirmed for Thailand; the retail CV evidence is 7-Eleven's face/behaviour rollout ([Retail Insight via research_notes](https://www.retail-insight-network.com/news/facial-recognition-introduced-11000-thai-7-eleven-stores/)) and Guardforce's CCTV+RFID work ([Yahoo Finance via research_notes](https://finance.yahoo.com/news/guardforce-ai-extends-thailand-retail-102050867.html)).
- **Why it matters for LabelDesk:** retail is the vertical with the most cameras per baht of contract, and gap compliance is the one task a merchandiser will pay per branch per week for. Our zone and dwell primitives cover intrusions, not slots.
- **LabelDesk code evidence:** `streams/rules.py:1-19` (anchor-point geometry for people/objects; no slot or grid concept); `features/streams/ZoneEditor.tsx` (free polygons only); no planogram model in `models/project.py`.
- **Suggested status:** MISSING — no grid, slot or planogram primitive.
- **Suggested priority / size:** Could / L.

### G6.11 Price-tag read-back against a price master (Thai retail, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** captures a shelf edge, and every price tag is read and compared with the branch's price list; mismatches are listed with the tag crop, the shelf price and the master price, ready to print and replace.
- **Who uses it:** a store manager handling a promotion changeover, and a loss-prevention officer who suspects tag swaps.
- **Flow:** 1. Retail → Price check → upload or capture. 2. `[loading]` OCR over the tag regions. 3. Result table: match, mismatch, unreadable; `[empty]` "no tags found in this image" with a re-shoot hint. 4. Import the price master from CSV, with `[error: duplicate SKU]`. 5. Export the mismatch list.
- **Why it is easy:** the price master is a CSV the branch already has; the output is a print list, not a report.
- **Products with it:** none fetched; the Thai retail loss-prevention context is the 7-Eleven and Guardforce material above ([via research_notes](https://www.retail-insight-network.com/news/facial-recognition-introduced-11000-thai-7-eleven-stores/)).
- **Why it matters for LabelDesk:** it reuses the OCR annotation payload we just built and pairs it with a join key, which is the difference between an OCR demo and a retail product. It also gives the sales team a per-branch, per-week unit of work.
- **LabelDesk code evidence:** `services/ocr.py:20-45` (text/keyvalue/table payloads and Thai template presets; none for price tags), `routers/ocr.py` (annotation payload and export, no external master join); no CSV price master concept in `models/`.
- **Suggested status:** PARTIAL — the OCR payload exists; there is no comparison, no master list and no exception list.
- **Suggested priority / size:** Could / M.

### G6.12 Fruit grading station by size and defect (Thai agriculture, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** puts a durian or mango on a tray, the camera measures it against a known scale, the model assigns a grade, and the station prints or shows a grade label that goes on the crate.
- **Who uses it:** a packing-house operator on a sorting line, and the exporter's QC lead who signs the lot.
- **Flow:** 1. Station screen: one fruit, one grade, one label. 2. `[empty]` "place a fruit on the tray" until a detection appears. 3. Size class from a calibration object, defect class from the model, grade from a rule table the QC lead edits. 4. Confirm → label → next. 5. `[error: calibration object not visible]` rather than a wrong size band.
- **Why it is easy:** the grade rule is a small editable table (size band × defect count → grade), so the exporter's own standard can be entered without a developer.
- **Products with it:** Thai export-fruit sizing and grading with reported 93% size accuracy is [AgriEngineering via research_notes](https://www.mdpi.com/2624-7402/7/11/377); durian CT scanning for ripeness and seed-boring worms is [Thailand.go.th via research_notes](https://thailand.go.th/event-detail/D5-WP3-PRD2-2).
- **Why it matters for LabelDesk:** grading is a classification task with a physical decision attached; our classification projects have no notion of a station, a scale or a label. Adding them makes an existing task type sellable to exporters.
- **LabelDesk code evidence:** `models/project.py:19-43` (project types include classification; no grade or scale fields); `features/editor/Editor.tsx` class-chip path handles single-label classification; no calibration or label-print surface — searched `grade|calibrat` across `apps/backend/app` — no match.
- **Suggested status:** MISSING — no grading, calibration or label output.
- **Suggested priority / size:** Could / L.

### G6.13 Exporter lot report with grade mix and photographs (Thai agriculture, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** at the end of a packing run, generates a lot report: lot number, farm or orchard id, fruit count per grade, defect photographs, inspector name and signature block, in Thai, for the buyer abroad.
- **Who uses it:** an exporter's QC lead answering a buyer's complaint, and a customs or buyer audit months later.
- **Flow:** 1. Lot → Reports → `[empty]` "lot has no graded units". 2. Choose grade columns and photo count per defect class. 3. Generate → `[loading]` → PDF with a QR back to the lot. 4. `[error: lot not closed]` blocks issuing until every unit has a grade, because a partial report is worse than none.
- **Why it is easy:** the lot already holds every grade decision, so the report is a selection plus a template.
- **Products with it:** no fetched platform produces an export lot report; the grading evidence is the same [AgriEngineering via research_notes](https://www.mdpi.com/2624-7402/7/11/377).
- **Why it matters for LabelDesk:** exporters are paid on grade mix and blamed on defects; a lot report is the artefact that makes the model's output commercially usable. It also shares a renderer with the safety sheet, so it is one engine and two templates.
- **LabelDesk code evidence:** no document renderer (searched `pdf|reportlab|weasy` — no match); `models/project.py` has no lot entity beyond `Batch` (`:76-93`), and batches carry no grade or signatory.
- **Suggested status:** MISSING — no report, no lot sign-off.
- **Suggested priority / size:** Could / M.

### G6.14 Offline field capture with deferred sync (Thai agriculture and site inspection, extends 2-F2.5 and 3-F3.53)
- **What the user does:** in an orchard or on a site with no signal, takes 200 photos in a capture session; each is queued locally with a geotag and a session name, and uploads when the phone finds Wi-Fi, resuming where it stopped.
- **Who uses it:** a field agronomist or a site surveyor on a one-day collection trip, away from the office.
- **Flow:** 1. Mobile capture → "new session" → `[empty]` "0 photos, no signal". 2. Shoot; each photo shows a queued badge with size and geotag. 3. Review and delete weak shots offline. 4. Back in range: `[loading] uploading 137 of 200`, then complete. 5. `[error: 3 photos rejected — unreadable]` listed per file, not as a total.
- **Why it is easy:** the queue is visible and editable before upload, so a bad shot is deleted in the field instead of costing bandwidth and a re-trip.
- **Products with it:** the parity row 2-F2.5 notes field data must round-trip through the gallery; the agri capture context is the sector note's drone/phone requirement, via [research_notes](https://www.mdpi.com/2624-7402/7/11/377).
- **Why it matters for LabelDesk:** the delta over 2-F2.5 and 3-F3.53 is the session object, the geotag and the resumable queue — the three things that decide whether a 200-photo field trip survives. Without them, every field customer is a support ticket.
- **LabelDesk code evidence:** `features/project/Upload.tsx:66-129` (browser selection and chunked upload, no persistence across reload); `features/playground/useCamera.ts` (playground only); `services/imaging.py:26-28` (EXIF orientation, no GPS extraction). Searched `geotag|offline|capture session` — no match.
- **Suggested status:** MISSING — no offline queue, no geotag, no session.
- **Suggested priority / size:** Should / M.

### G6.15 Evidence package for police or insurer (Thai CCTV retrofit, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** selects an incident, adds the twenty minutes around it, and exports a package: the clip, three stills, the event log, the camera's location, a SHA-256 of each file, and a one-page Thai cover sheet naming the operator and time.
- **Who uses it:** a security manager at a retail chain or an estate responding to a police request or an insurance claim.
- **Flow:** 1. Event → "export evidence" → choose window and items. 2. Preview of what will be included; `[empty]` "this event has no clip" if only a snapshot exists. 3. Generate zip + hash manifest; `[loading]`. 4. Download; the audit log records who exported what, when. 5. `[error: footage already past retention]` states the policy rather than producing a broken zip.
- **Why it is easy:** one dialog, one zip, one hash list; the cover sheet is generated, not typed.
- **Products with it:** no fetched platform ships a chain-of-custody export; the legal frame is the PDPA regulator's guidance and model-contract library at [PDPC fetched](https://www.pdpc.or.th/).
- **Why it matters for LabelDesk:** without a hash manifest, our exports are screenshots with no evidentiary weight, and a security buyer will keep using the NVR's own export. It is also the cheapest visible PDPA answer we can ship.
- **LabelDesk code evidence:** `services/streamaudit.py:50-64` (records who viewed a stream — good, already there); `routers/streams.py:61-66` (event carries a snapshot path only); `services/retention.py:1-9` (frames, snapshots, events swept per project). Searched `sha256|manifest|evidence` in stream paths — no export manifest.
- **Suggested status:** PARTIAL — view auditing and snapshots exist; there is no clip, no hash manifest, no package.
- **Suggested priority / size:** Should / M.

### G6.16 Redaction control for faces and plates across capture, live view and export (Thai CCTV retrofit / PDPA, `apps/backend/app/services/faceblur.py`)
- **What the user does:** turns on "blur people" for a public-area camera and "blur plates" for a gate camera, draws static masks over neighbours' windows, and chooses whether the export keeps the blur or the original (with a reason, recorded).
- **Who uses it:** a CCTV operator in a retail or estate control room, and the DPO who has to answer a complaint.
- **Flow:** 1. Camera settings → Privacy → toggles for faces, plates, and a static-mask polygon tool. 2. `[loading]` detection on the next frame; a live preview shows what the public will see. 3. Export dialog: "redacted (default)" or "original — requires approval" with a reason field. 4. `[error: face detector unavailable]` fails closed and blocks the camera from entering a dataset.
- **Why it is easy:** the toggles sit on the camera the operator already edits, and the fail-closed behaviour is visible instead of silent.
- **Products with it:** face/plate blur options exist in NVR-class tools and in open-source anonymisers, per `research/notes/.../emerging_features.md` (EgoBlur, Brighter AI) — [EgoBlur via research_notes](https://oosmetrics.com/repo/facebookresearch/EgoBlur).
- **Why it matters for LabelDesk:** we blur faces already, which is more than most competitors, but there is no plate path, no static mask and no export-time choice, so a PDPA complaint still lands on the customer with no record of what we did.
- **LabelDesk code evidence:** `services/faceblur.py:1-10,69` (Haar cascade, padded-square Gaussian blur, fails closed), `handlers/streams.py:105-108` and `routers/images.py:88,130` (applied on stream frames and ingest when `project.face_blur`); searched `plate` across backend and frontend — no match; no mask polygon model.
- **Suggested status:** PARTIAL — faces are blurred on ingest and stream; plates, static masks and export policy are absent.
- **Suggested priority / size:** Should / M.

### G6.17 Camera readiness survey before a project starts (Thai CCTV retrofit, via `research/notes/.../sector_use_cases.md`)
- **What the user does:** adds each existing camera's RTSP URL and the product pulls six frames at different times of day, measures resolution, sharpness, night-time grain, frame rate and field of view, then prints a per-camera verdict: usable, needs a better angle, needs light, replace.
- **Who uses it:** an integrator quoting a retrofit on analogue or mixed IP cameras, before promising accuracy.
- **Flow:** 1. New project → "survey cameras" → add N URLs. 2. `[loading]` pulling samples; per-camera card with thumbnails. 3. Verdict per camera with the reason; export as a PDF for the quote. 4. `[error: stream has no keyframe]` and `[error: night sample unavailable]` explained in place.
- **Why it is easy:** the survey runs before any model exists, so a bad camera is a conversation with the customer instead of a failed pilot.
- **Products with it:** no fetched platform ships a pre-sales camera survey; Thai field evidence that mounting point alone moves accuracy between 73.7% and 89.5% is [Thai Journal via research_notes](https://ph01.tci-thaijo.org/index.php/lej/article/view/265965).
- **Why it matters for LabelDesk:** our stream page accepts an RTSP URL and shows online or offline, which is not the same as "this camera will never work at night". A survey artefact also gives the SI something to bill in week one.
- **LabelDesk code evidence:** `routers/streams.py:386-407` (start/stop), `:469-487` (latest frame and MJPEG); `services/runtime_state.py` (status only). No probe, no quality metrics per camera, no PDF.
- **Suggested status:** MISSING — no readiness or quality probe on a camera.
- **Suggested priority / size:** Should / S.

### G6.18 Thai tax documents: 7% VAT tax invoice, PromptPay QR, 3% withholding certificate (Thai operations, [Revenue Department VAT fetched](https://www.rd.go.th/english/6043.html), [PIT fetched](https://www.rd.go.th/english/6045.html))
- **What the user does:** a finance admin issues a monthly invoice in THB with the seven required tax-invoice elements, a PromptPay QR for the exact amount, and a downloadable withholding certificate for the customer's accounts payable.
- **Who uses it:** the customer's AP clerk and our finance person; the buyer's procurement checklist.
- **Flow:** 1. Billing → invoice list → `[empty]` "no invoices this cycle". 2. Generate: period, line items (cameras, seats, on-prem licence), VAT 7%, total. 3. Issue → PDF + QR; `[error: buyer tax id missing]` blocks issuing, because an invoice without it is not usable for input-tax credit. 4. Record payment (transfer or QR confirmation) → status. 5. Export a monthly withholding summary.
- **Why it is easy:** the invoice template already carries the legally required fields and the QR encodes the exact payable amount, so the buyer's AP process needs no email thread.
- **Products with it:** Thai VAT is 7% and a tax invoice must show issuer name/address/tax id, purchaser name/address, serial number, description/value/quantity, VAT amount and date ([RD fetched](https://www.rd.go.th/english/6043.html)); service fees carry 3% withholding ([RD fetched](https://www.rd.go.th/english/6045.html)). PromptPay QR specifics were not fetched — see unverified.
- **Why it matters for LabelDesk:** billing is currently "contact your LabelDesk operator", so every deal closes through a manual quote and a bank transfer. A corporate buyer cannot pay us without a tax invoice and cannot book the cost without a withholding certificate; this is the difference between a pilot and a purchase order.
- **LabelDesk code evidence:** `config.py:87-108` (`PLANS` limits and `CREDIT_COST`; no currency, no price), `features/settings/Settings.tsx:973-975` ("contact your LabelDesk operator"), `services/metering.py:91-106` (quota checks, no ledger to invoice from).
- **Suggested status:** MISSING — no billing integration, no invoice, no THB price.
- **Suggested priority / size:** Must / L.

### G6.19 Buddhist-era dates, TH Sarabun and Thai numerals in every generated document (Thai operations, [PDPC fetched](https://www.pdpc.or.th/))
- **What the user does:** exports a report and gets the date in Buddhist-era form (17 Nov 2569), Thai digits where the template asks for them, TH Sarabun New at 16 pt for the body, and a Latin fallback for model names and ids.
- **Who uses it:** any Thai customer attaching our output to an internal or government document; the person who currently retypes our dates.
- **Flow:** 1. Any report surface → format selector: Thai (BE) or ISO. 2. `[loading]` render with the font embedded. 3. Preview shows the exact page; `[error: font not available]` falls back to a bundled copy rather than a substituted face. 4. Download and open in Word without reflow.
- **Why it is easy:** one locale switch per workspace, one bundled font, one date formatter; the user never edits a date again.
- **Products with it:** Thai government publications themselves date in BE — every PDPC page title carries a BE year such as 2569 ([PDPC fetched](https://www.pdpc.or.th/)); TH Sarabun New is the standard Thai document face (font licensing and the exact SIPA release were not fetched — see unverified).
- **Why it matters for LabelDesk:** a report with a Gregorian year and a substituted font reads as a foreign tool, and in a Thai procurement pack it is the first thing a clerk notices. It is a day of work that changes how every document is received.
- **LabelDesk code evidence:** no i18n layer and no Thai string in the frontend (searched `Sarabun|buddhist|พ.ศ.` across `apps/frontend/src`); `services/exporters.py` writes dataset formats only; there is no document renderer to attach a locale to.
- **Suggested status:** MISSING — no locale-aware rendering anywhere.
- **Suggested priority / size:** Should / S.

### G6.20 Air-gapped on-premises install with an offline licence and signed model bundles (Thai enterprise / PDPA, `apps/inference/README.md`)
- **What the user does:** installs from a single archive on a machine with no internet, enters a licence file issued by us, and later applies a signed model bundle copied in on a USB stick; each step is verified locally.
- **Who uses it:** an IT engineer at a bank, hospital or factory that will not let images leave the building.
- **Flow:** 1. Install → `[error: licence missing]` with the machine fingerprint to send us. 2. Paste the licence file → features unlock. 3. Model update: drop a signed bundle → verify signature → `[error: signature invalid, bundle rejected]`. 4. Health page shows version, expiry and last successful verification. 5. Offline for 90 days → read-only mode, data export still allowed.
- **Why it is easy:** three artifacts (installer, licence, bundle), each verified on the box, with no call-home requirement to install.
- **Products with it:** the inference server here is Docker CPU/GPU with read-only mounts and a Jetson cross-build that is explicitly untested (`apps/inference/README.md:58-99`); the compliance motive is the PDPA regulator's cross-border posture at [PDPC fetched](https://www.pdpc.or.th/) and the cross-border rules summarised in `research/notes/.../positioning.md` ([Tilleke via research_notes](https://www.tilleke.com/insights/thailands-regulations-for-cross-border-personal-data-transfer-come-into-force/24/)).
- **Why it matters for LabelDesk:** "data stays in Thailand" is the one claim competitors cannot copy cheaply, but today a self-hosted install still needs our platform to train, and there is no licence mechanism at all. Without offline licensing, an air-gapped deal is unpaid.
- **LabelDesk code evidence:** `apps/inference/README.md:58-99` (CPU/GPU run, `--read-only`, untested Jetson); `deploy/docker-compose.yml` profile; `services/edge.py:26-53` (export presets, no licence); searched `licence|license|activation` in backend services — model-licence metadata only.
- **Suggested status:** PARTIAL — an inference container exists; there is no offline install path, licence or signed update.
- **Suggested priority / size:** Should / L.

### G6.21 PDPA pack: CCTV notice, consent and ROPA register, cross-border transfer record (Thai operations, [PDPC fetched](https://www.pdpc.or.th/))
- **What the user does:** fills a short form per camera site (purpose, zone, retention, notice text), and the product produces the on-site notice in Thai, a ROPA row, a consent or legitimate-interest record, and a cross-border transfer entry whenever the workspace's data region is outside Thailand.
- **Who uses it:** a DPO or an IT compliance lead at a customer with CCTV analytics, preparing for an audit or answering a data-subject request.
- **Flow:** 1. Governance → PDPA → `[empty]` "no processing activities recorded". 2. Add activity: purpose, data categories, retention, recipients, region. 3. Generate notice PDF and a register export; `[error: retention longer than policy]` blocks saving. 4. Data-subject request → search by camera, site and time window → export what we hold for that window. 5. `[error: sub-processor not approved]` when a new vendor is added without consent recorded.
- **Why it is easy:** the register and the notice come from the same record, so a change in retention updates both, and the sub-processor gate already exists as a rule.
- **Products with it:** PDPC publishes guidelines, model contracts, DPO registration and a breach-notification channel ([PDPC fetched](https://www.pdpc.or.th/)); the sector-specific CCTV guidance is still at consultation stage per `research/notes/.../positioning.md` ([HLC via research_notes](https://hlc.com/en/publications/thailand-pdpc-consults-on-sectorspecific-pdpa-guidelines)).
- **Why it matters for LabelDesk:** we already hold retention, residency and a DPA, but the customer still has to invent the paperwork. Shipping the paperwork is a procurement unlock, and it must be drafted by a Thai lawyer before we claim compliance in public.
- **LabelDesk code evidence:** `routers/privacy.py:1,14-16,80-102` (retention, residency `th|sg|us`, DPA version), `:227` (sub-processor needs controller consent); `services/erasure.py`; `services/retention.py:1-9`. No ROPA, notice text, consent record or data-subject search — searched `consent` — one docstring mention only.
- **Suggested status:** PARTIAL — retention, residency, DPA and erasure exist; the register, notice and subject-access path do not.
- **Suggested priority / size:** Must / M.

### G6.22 Partner console for an SI: child workspaces, camera-licence pool, monthly statement (Thai channel motion, via `research/notes/.../positioning.md`)
- **What the user does:** an integrator signs in once, sees their customer workspaces, allocates camera or project licences from a pool they bought, and downloads a monthly statement of what each customer consumed — without seeing the customer's images unless invited.
- **Who uses it:** a Thai system integrator or CCTV distributor reselling LabelDesk, currently modelled on the Tapway distributor route.
- **Flow:** 1. Partner home → customer list → `[empty]` "no customers yet" with an invite link. 2. Create a child workspace, assign a licence quantity, set the customer's data region. 3. `[error: licence pool exhausted]` at allocation. 4. Monthly statement: per customer, licences used, overage, amount. 5. Escalate a support case with the customer's consent, gaining read access for a fixed window.
- **Why it is easy:** one login, one pool, one statement; the partner never handles the customer's API keys.
- **Products with it:** the distributor-led, per-camera model is already being run in Thailand ([CRN Asia via research_notes](https://www.crnasia.com/news/2025/distributor/vision-ai-software-developer-tapway-partners-three-thai-firm)); the industrial-estate geography that makes one SI cover many plants is [IEAT fetched](https://www.ieat.go.th/en).
- **Why it matters for LabelDesk:** we have no way to sell through a partner, so every deal needs our own salesperson in the room. The delta over 7-F7.61 is tenancy and money: a licence pool, a statement, and time-boxed support access — not just a rollup dashboard.
- **LabelDesk code evidence:** `routers/workspaces.py` (workspace CRUD and membership, no parent/child relation); `routers/admin.py` + `app/superadmin.py` (platform-operator console, not a reseller); `config.py:89-108` (plans, no licence pool). Searched `reseller|partner|parent_ws|licence pool` — no match.
- **Suggested status:** MISSING — workspaces are flat and only the platform operator can see across them.
- **Suggested priority / size:** Could / L.

---

## Reading the notes: what holds and what to discount

- **Richest, in order:** `reports/ฟีเจอร์ที่ยังขาดเทียบคู่แข่ง.md` (the only place that maps sectors to platform requirements and ranks them, and it cites primary Thai sources per row); `research/notes/.../sector_use_cases.md` (twelve sectors, each with an explicit "inference" and "gaps" block, which is why most cards here can name a buyer); `research/notes/.../inference_streams_vlm.md` (the only note that fetches vendor docs and separates `[fetched]` from `[search-snippet]`); `research/notes/.../positioning.md` (buyer pain, local competitors, channel model).
- **Thinnest:** `roboflow_features.md` and `annotation_autolabel.md` for this group's purpose — they re-describe parity, which `PARITY.md` already owns; `data_layer.md` and `saas_platform_mlops.md` are strong on S3/mirroring and billing ladders but almost silent on Thai specifics.
- **Numbers not to repeat:** the two Thailand market sizes (USD 430M AI inspection vs USD 87M industrial machine vision) use different definitions and are vendor research; the repo note already warns against comparing them. No credible figure for a Thai annotation or CV-platform market exists.
- **Evidence that is old or absent:** Thai retail CV rests on a 2018 seven-eleven rollout; no named Thai PCB/IC factory case study; no bin-picking or robot-arm deployment; no sourced pallet-counting or parcel-damage project; no MEA (only PEA) energy evidence.
- **The backlog in the report is partly stale.** Tasks 27–38 were the report's ranking; on `3bde0ba` the suspect queue, anomaly station, tiling, workflow builder, OCR, LINE alerts, edge presets and batch inference have shipped (flags 28–34 and 36). The unshipped remainder of that list (semantic search, edge fleet, PLC output, industrial camera ingest, attributes and image groups, plate blur, DICOM, geo/thermal, THB billing) is where this file's cards sit, plus the sector surfaces the report never specified.
- **Where this file deliberately disagrees with the notes:** they treat the sector requirement as "a pack of features"; the cards here treat a pack as *classes + station + document + escalation*, because the document and the escalation are what a Thai buyer signs for.

## Title-only / unverified

- **PromptPay QR specifics.** Two BOT URLs returned 404 and web search was unavailable this session, so the QR payload format (EMVCo merchant-presented, amount field, bill-payment vs credit-transfer) is not verified here. Treat G6.18's QR item as a design sketch and read the BOT/ITMX spec before building.
- **TH Sarabun New licensing and the SIPA release.** Not fetched. Do not bundle a font until the licence is read.
- **e-Tax Invoice by Email/PDF** (Revenue Department notification, XML/PDF signature requirements). Only the paper tax-invoice element list was fetched; the electronic route is unconfirmed.
- **Thai Agricultural Standard for durian grades** (TAS/DOA grading sheet). The ACFS PDF 404'd; every grade boundary in G6.12 and G6.13 is a placeholder until the standard is read.
- **PDPC sector guidance for CCTV analytics** is described in the repo notes as a draft at consultation stage ([HLC via research_notes](https://hlc.com/en/publications/thailand-pdpc-consults-on-sectorspecific-pdpa-guidelines)); I did not find the PDF, so do not describe it as binding.
- **7-Eleven Thailand face/behaviour analytics** dates from 2018 and is the only Thai retail CV deployment in the notes; the per-branch planogram demand in G6.10 is inferred, not sourced.
- **LINE Notify shutdown** — the repo already codifies its retirement as 2025-03-31 (`services/alerts.py:8`); I confirmed the Messaging API path but did not fetch a Notify discontinuation notice.
- **OIC AI governance guideline 2025** and the BoT AI risk guideline are referenced in the repo notes but neither primary document was opened; do not quote them in sales material.
