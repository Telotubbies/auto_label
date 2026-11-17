# Beyond Roboflow — edge and industrial vision (Group 3)

Method: fetched 14 pages on 2026-11-17 — DeepStream `nvdsanalytics` and `nvmsgbroker` plugin references, TAO overview / quantisation-aware training / DeepStream integration, Triton model repository, Edge Impulse EON Tuner and Deployment, ONVIF Profile S and Profile M, Axis ACAP index, Milestone XProtect product page, Keyence vision-system index, Viso.ai home. Not opened: Cognex (two URLs answered 429), Genetec (docs render client-side, nothing returned), the Viso Now docs body, DeepStream `nvstreammux` / `nvtracker`, Edge Impulse drift and data-acquisition pages.

Feature count: **18** (G3.1–G3.18). `PARTIAL` below always names the control that is missing, not just the surface that is present. The industrial buyer compares LabelDesk with a machine-vision cell and a VMS, not with a labelling tool, and asks four questions our parity plan does not answer: where is this camera in my plant, what happens when the line network drops, how does a reject reach the PLC, and which model build is on device 14.

If only three of these land before the first factory pilot, they are G3.2 (a station the customer recognises), G3.11 (a reject that reaches the line controller) and G3.7 (a night shift that survives a dropped link). G3.4 and G3.16 are the two small ones that remove the loudest trial complaints — false alarms outside production hours and a camera that drifts without telling anyone. Everything else in this file is depth a buyer asks about in the second meeting.

---

### G3.1 Commission a camera with discovery, a credential test and a pinned stream profile (ONVIF, ACAP)

- **What the user does:** types a subnet range, gets the cameras that answer, picks one, enters the password once, chooses which stream profile to analyse, and never sees credentials in a URL again.
- **Who uses it:** an integrator or plant electrician commissioning 20–60 cameras on one site, not a data scientist.
- **Flow:** 1. Streams → New stream opens a `Discover` step beside today's URL field. 2. `[loading: probing <n> addresses]` → table of devices with model, firmware, address. 3. `[empty: nothing answered — check the VLAN, or paste a URL]`. 4. Pick a device → media profile (main/sub) with resolution, codec, fps printed → `Test` shows one frame and the round-trip time. 5. `[error: 401 — password rejected]`, `[error: 403 — camera user lacks the media role]`, `[error: timeout — discovery answered, media did not]`. 6. Save → the source is sealed and the row reads `rtsp://camera-07 ••••@…`.
- **Why it is easy:** the profile is picked from what the camera reports instead of being typed into a URL, and the password is proven before the stream starts, so a mistake fails in the dialog rather than as a stream stuck in `reconnecting`.
- **Products with it:** ONVIF Profile S says a conformant client "can configure, request, and control video streaming" from a device and covers PTZ, multicasting and relay outputs (https://www.onvif.org/profiles/profile-s/); Axis ACAP exposes video, the event and parameter systems and I/O to an on-device app (https://developer.axis.com/acap/).
- **Why it matters for LabelDesk:** the only onboarding path today is a pasted RTSP URL with `user:pass@` inside it — the exact string a customer forwards to a colleague in chat.
- **LabelDesk code evidence:** `apps/frontend/src/features/streams/Streams.tsx:123-124` (single URL field, credentials in the URL, allowlist hint); `apps/backend/app/streams/creds.py:1-9` (credentials sealed at rest, never returned); `apps/backend/app/streams/guard.py:7` (non-public addresses blocked, so a discovery probe needs its own allowlist path); no ONVIF/discovery route found (searched `onvif|ONVIF|discover|ws-discovery|GetProfiles` in `apps/backend/app`; the only hit is a comment at `creds.py:36`).
- **Suggested status:** PARTIAL — a source can be entered, sealed and started; discovery, profile choice and credential pre-test are absent.
- **Suggested priority / size:** Should / M.

### G3.2 Plant → line → station → camera, with a station that owns its model and threshold (Cognex-style cell, Keyence)

- **What the user does:** creates a site, lines under it, stations under a line, then attaches cameras and a model to a station instead of to a project.
- **Who uses it:** a quality engineer at a plant with three lines and eleven inspection points who reports yield per line; an integrator who must name the cell the way the plant does.
- **Flow:** 1. Workspace → `Sites` (new level between workspace and project). 2. Site → `Lines` → `Stations`; each station row shows camera count, model, last event, today's reject count. 3. Station page → attach a camera, attach a model or anomaly artifact, set threshold and reject action. 4. `[empty: a station with no camera shows an "attach a camera" row instead of a chart]`. 5. The streams wall groups by station.
- **Why it is easy:** the hierarchy is the customer's own vocabulary, so "Line 2 / Press / Infeed" is found by the name on the plant drawing; one station row answers "which model is on this cell and how did it do today".
- **Products with it:** Keyence describes each system as a controller-based cell doing pre-processing, measurement and an OK/NG judgement with results tied to stored images (https://www.keyence.com/products/vision/vision-sys/); DeepStream keeps analytics configuration per stream id (`[roi-filtering-stream-<n>]`, `[line-crossing-<n>]`) inside one batched pipeline (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html).
- **Why it matters for LabelDesk:** a Thai factory buys per line, and a morning report that cannot separate Line 1 from Line 3 is unusable; without this every line becomes its own project and the model list fragments.
- **LabelDesk code evidence:** `apps/backend/app/models/training.py:56-73` (`AnomalyStation` = one "production station (camera/line)" with its own threshold, unique per **project**, no camera, no parent); `apps/backend/app/routers/anomaly.py:82-123` (station list/create); `apps/backend/app/routers/streams.py:248,260` (a `Stream` is keyed only by workspace + project); no site/line/shift model found (searched `site|station|shift|line_id|plant` under `apps/backend/app/models` — only `AnomalyStation`).
- **Suggested status:** PARTIAL — a station exists as an anomaly-only container inside one project; hierarchy, camera attachment and per-line reporting are absent.
- **Suggested priority / size:** Must / M.

### G3.3 Operator verdict with a reason code and a piece identifier (industrial inspection app)

- **What the user does:** on a station screen, looks at the frame, presses Accept or Reject, picks a reason the plant defined, and optionally scans or types the piece/lot id.
- **Who uses it:** a line operator on a touch screen; later the quality engineer who groups rejects by reason.
- **Flow:** 1. Station → `Operator` view: large frame, verdict buttons, reason list, running counters. 2. Reject → reason sheet (`scratch`, `dent`, `contamination`, `wrong part`, `other`, defined per station) → confirm. 3. `[loading: saving]` under a second, then the next frame loads itself. 4. `[error: offline — verdict queued, N waiting]` (see G3.7). 5. Every verdict lands in the event list with reviewer, reason and time; the list gains a reason filter and a per-reason count.
- **Why it is easy:** one gesture per piece with the reason attached while the operator is already looking at the defect; asking later costs a second pass over the video.
- **Products with it:** DeepStream attaches analytics output per object and per frame (`NvDsAnalyticsObjInfo`) for an operator application to read (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html); Keyence states image and result data are both output and stored for traceability (https://www.keyence.com/products/vision/vision-sys/).
- **Why it matters for LabelDesk:** our verdict is a boolean, so a customer can say "34 % rejected" but never "34 % rejected because of flash" — the number that changes the process.
- **LabelDesk code evidence:** `apps/backend/app/routers/streams.py:540-553` (`ReviewIn.reviewed: bool` is the whole vocabulary); `:61-64` (`event_out` carries no reason or operator); `apps/frontend/src/features/streams/StreamDetail.tsx:678-686` (Reviewed switch and badge per event); `:533,612-616` (filter is Reviewed / Unreviewed only).
- **Suggested status:** PARTIAL — one boolean per event; reason codes, a piece id and a counted breakdown are missing.
- **Suggested priority / size:** Should / M.

### G3.4 Rule windows: a zone rule that counts only during production hours (machine-vision recipe, VMS schedule)

- **What the user does:** sets an active window per rule or per station, so alarms stay quiet during cleaning, changeover and planned stops, and a shift count is not diluted by the night.
- **Who uses it:** a shift supervisor tired of acknowledging the same 40 night alarms; an engineer who needs a count per shift, not per day.
- **Flow:** 1. Stream detail → Zones & rules → `Active` with a day/hour grid (default all day, marked as the default). 2. `[empty: no window set — rule runs always]`. 3. Outside the window nothing is evaluated; the stream counters show `Suppressed by schedule` so the silence is explained. 4. Optional shift template (`A 06:00-14:00`, `B 14:00-22:00`, `C 22:00-06:00`) applied to a line at once.
- **Why it is easy:** geometry and threshold stay untouched; the clock is the only new control, so nobody duplicates a rule three times for three shifts.
- **Products with it:** Milestone markets rules and automated notification workflows as part of alarm handling (https://www.milestonesys.com/products/software/xprotect/); DeepStream holds rule configuration per stream in a config group, which a schedule extends (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html).
- **Why it matters for LabelDesk:** every factory trial starts with a false-alarm complaint, and a schedule is the cheapest way to cut noise without weakening the rule.
- **LabelDesk code evidence:** `apps/backend/app/routers/streams.py:148-195` (rule fields: class, op, k, for_s, zone_id, line, direction, seconds — no time window); `apps/backend/app/streams/rules.py:88-106` (`step` evaluates every rule on every frame regardless of clock); `apps/backend/app/streams/manager.py:690` (engine built once with fixed cooldown and ttl); no schedule field found (searched `shift|schedule|window|active_hours` under `apps/backend/app`).
- **Suggested status:** MISSING — rules are always on.
- **Suggested priority / size:** Should / S.

### G3.5 Alarm queue with acknowledgement, cross-camera de-duplication and snooze (VMS alarm manager)

- **What the user does:** works a queue, takes ownership of an alarm, acknowledges it with a note, merges the four copies of one event arriving from four overlapping cameras, and snoozes a known nuisance for an hour.
- **Who uses it:** a control-room operator or a shift leader on a phone.
- **Flow:** 1. Alerts → `Queue`: unacknowledged first, grouped by rule + zone + a 30-second window, each group showing camera count. 2. Open a group → frame plus member events → `Acknowledge` (records who, when) → `Assign to me` → optional note. 3. `Snooze 1h` hides a group and records the reason. 4. `[empty: nothing unacknowledged — shows the last 24 h count]`. 5. `[error: someone else acknowledged it first — row updates and buttons disable]`.
- **Why it is easy:** grouping happens on the server, so the operator acknowledges one thing instead of eight; snooze is a state with a reason, so "why was this ignored" is answerable.
- **Products with it:** Milestone lists Alarm Manager, Smart Map and automated notification as the operator surface for prioritising alarms (https://www.milestonesys.com/products/software/xprotect/); ONVIF Profile M defines event interfaces for counting and recognition analytics that a queue consumes (https://www.onvif.org/profiles/profile-m/).
- **Why it matters for LabelDesk:** our events are de-duplicated per track by a fixed timer, but nothing owns an alarm, so two operators either ignore it or both chase it.
- **LabelDesk code evidence:** `apps/backend/app/streams/rules.py:62-80` (`cooldown_s` per (rule, track), default 30, hard-coded at `manager.py:690`; no grouping across streams); `apps/backend/app/routers/streams.py:506-537` (filters rule/class/reviewed; no owner, no ack time); `:544-553` (PATCH sets `reviewed` only); `apps/backend/app/routers/alerts.py:1` (channel CRUD, test send, delivery history — no queue).
- **Suggested status:** PARTIAL — per-track cooldown only; ownership, cross-camera grouping, snooze and a queue surface are missing.
- **Suggested priority / size:** Should / M.

### G3.6 Evidence clip with pre-roll and post-roll, held against retention (VMS evidence)

- **What the user does:** opens an alarm and gets a short clip — seconds before and after the trigger — not a single still, and marks the clip as evidence so retention does not delete it.
- **Who uses it:** a quality manager investigating a customer complaint; a security lead handing a clip to an auditor.
- **Flow:** 1. Event detail → `Clip` tab: `[loading: assembling 12 s from buffer]` → player with the trigger marked on the timeline. 2. Download MP4, or `Hold` → reason, holder, expiry. 3. `[error: pre-roll unavailable — stream started 3 s before the event]` states the shortfall instead of serving a truncated clip. 4. Held clips list who holds them and when they expire; deleting a stream does not delete a held clip.
- **Why it is easy:** the clip comes from a rolling buffer the worker already holds, so nobody scrubs a four-hour recording for six seconds; the hold is one action with an owner, which is what an audit asks.
- **Products with it:** Milestone describes Evidence Lock (protecting selected video, audio and metadata from deletion), Evidence Manager and digital signing of exported footage (https://www.milestonesys.com/products/software/xprotect/); ONVIF Profile M allows images inside a metadata stream, which is how a VMS stitches a clip around an alarm (https://www.onvif.org/profiles/profile-m/).
- **Why it matters for LabelDesk:** a still cannot show motion, and most industrial disputes are about motion ("it was already scratched when it arrived").
- **LabelDesk code evidence:** `apps/backend/app/streams/manager.py:807-871` (event record: snapshot JPEG only), `:912-925` (`_save_frames` writes `snapshot` plus one clean `.src.jpg`); `apps/backend/app/routers/streams.py:341-361` (deleting a stream erases every event file, so no hold can survive); `apps/frontend/src/features/streams/StreamDetail.tsx:721` (event row: badge and still); no clip writer found (searched `clip|pre_roll|post_roll|mp4|buffer` under `apps/backend/app/streams`).
- **Suggested status:** MISSING — stills are stored and signed; clips and holds are not.
- **Suggested priority / size:** Should / M.

### G3.7 Store-and-forward on the edge while the link or the quota is down (DeepStream edge, VMS edge storage)

- **What the user does:** keeps inspecting when the plant network or the cloud link drops; verdicts and images queue on the box, the operator still sees pass/fail, and the queue drains in order on reconnect without duplicate rows.
- **Who uses it:** a plant with an unreliable uplink, or a night shift whose storage quota filled at 02:00.
- **Flow:** 1. Edge status: `Buffered: 1,284 events · 412 MB · oldest 3 h`. 2. A policy sets the disk ceiling and what drops first (images before verdicts). 3. On reconnect `[loading: draining 1,284]` with a rate, then `Drained · 0 rejected`. 4. `[error: clock skew — events ordered by device time]`. 5. The station screen shows a link badge so the operator knows verdicts are local-only.
- **Why it is easy:** the verdict path never waits for the network; the only visible change is one counter and one badge, so a shift stops being timed around the uplink.
- **Products with it:** Milestone lists edge storage and failover recording per variant (https://www.milestonesys.com/products/software/xprotect/); Axis ACAP runs the application on the camera and reports locally, the same compute-near-the-sensor premise (https://developer.axis.com/acap/).
- **Why it matters for LabelDesk:** our worker writes the event row and JPEG in one transaction and drops the image on quota, so a quota event at night loses evidence exactly when it matters.
- **LabelDesk code evidence:** `apps/backend/app/streams/manager.py:835-857` (snapshot saved, then `_quota_error = "storage quota reached: event snapshots are not being saved"` — the row is still inserted without an image), `:557-590` (backoff covers the camera link, not the server link); `apps/backend/app/routers/streams.py:556-574` (dataset ingest assumes the file is already on the server); no spool found (searched `spool|outbox|offline|sync_queue|pending` under `apps/backend/app/streams`).
- **Suggested status:** MISSING — the worker is online-only and quota failure degrades silently.
- **Suggested priority / size:** Must / L.

### G3.8 Device-bound engine registry: which build runs on which box, and does it still pass the golden set (TAO, Triton)

- **What the user does:** sees per device the model version, engine artifact, the TensorRT/CUDA version it was built against, and whether a replay of a fixed golden image set still passes before that build is allowed to serve.
- **Who uses it:** an ML engineer shipping to a Jetson fleet; a technician who replaces one box and needs the same build back.
- **Flow:** 1. Model → `Builds` tab: one row per target profile (`Jetson Orin · TRT 10.3 · CUDA 12.6`) with state and size. 2. `Build for…` queues it; `[error: engine built against TRT 10.1 will not load here]` appears on the device row, not at inference time. 3. `Replay golden set` runs 20 stored images → `18/20 match, 2 class flips` against the previous build. 4. `Pin to device` records the pairing; a mismatch reads `build not for this profile`.
- **Why it is easy:** the compatibility rule is enforced where the pairing is made, so a wrong engine is refused at assignment instead of crashing in production; the replay gives one number for "did this build change behaviour".
- **Products with it:** TAO states machine-specific optimisations happen at engine creation, a distinct engine is needed per target environment, and an engine built against another TensorRT/CUDA version is unsupported (https://docs.nvidia.com/tao/tao-toolkit/text/ds_tao/deepstream_tao_integration.html); Triton keeps each model version in a numeric subdirectory under a version policy and ties a TensorRT plan to a compute capability (https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_repository.html).
- **Why it matters for LabelDesk:** we build engines and record nothing about the environment or the device, so the first field replacement is a support ticket with no artifact trail.
- **LabelDesk code evidence:** `apps/backend/app/handlers/versioning.py:51-70` (`run_export_engine` writes `DATA_DIR/engines/<model>.engine` with `half=True`; no profile, no TRT/CUDA record); `apps/backend/app/routers/training.py:355-376` (one engine job per project, deduped); `apps/backend/app/adapters/tensorrt_ad.py:31-39` (predict needs an engine path, error says "re-export it"); `apps/backend/app/services/deployments.py:1-106` (alias switch + one-step rollback, hosted path only); `apps/backend/app/routers/remote.py:1-5,85-104` (the only device protocol is a GPU worker claiming training jobs).
- **Suggested status:** PARTIAL — builds and hosted rollback exist; device pairing, environment record and golden replay do not.
- **Suggested priority / size:** Should / M.

### G3.9 Target-aware model search against a device budget (Edge Impulse EON Tuner)

- **What the user does:** names the target device and its budget (RAM, flash, latency), runs a search that proposes configurations, and picks one from a table of accuracy against measured latency and memory instead of guessing.
- **Who uses it:** an engineer fitting a model onto a Jetson Nano or an SBC that already runs a camera pipeline.
- **Flow:** 1. Train → `Deployment target` as the first field: device profile or manual budget. 2. `Find configurations` → `[loading: trial 7/24, best so far 0.81 mAP @ 41 ms]`. 3. Table sortable by accuracy, latency, size, with the Pareto front marked. 4. `Use this one` creates the run pre-filled. 5. `[error: no configuration fits 512 MB — lowest measured is 610 MB]` names the binding constraint. 6. `Extend search` adds time and keeps earlier trials.
- **Why it is easy:** the constraint is a number the device imposes, so the search returns something runnable rather than the most accurate thing that will not fit; the Pareto view replaces a spreadsheet.
- **Products with it:** Edge Impulse EON Tuner runs hardware-aware searches over input, processing and learning blocks, uses Bayesian optimisation, and reports per-trial results filtered and sorted by metric (https://docs.edgeimpulse.com/docs/edge-impulse-studio/eon-tuner); its deployment page prints estimated latency, flash and RAM for the target before deploying (https://docs.edgeimpulse.com/studio/projects/deployment).
- **Why it matters for LabelDesk:** we ask for architecture, image size and batch with no device in the loop, so the customer learns the model is too slow after paying for the run.
- **LabelDesk code evidence:** `apps/frontend/src/features/project/Train.tsx:92-114` (fast/advanced fields: epochs, image size, batch, max minutes — no target, no memory or latency budget); `apps/backend/app/adapters/catalog.py:33-40` (fixed variant list); `apps/backend/app/adapters/ultralytics_ad.py:222` (train kwargs: data, epochs, imgsz, batch).
- **Suggested status:** MISSING — training has no notion of a deployment target.
- **Suggested priority / size:** Should / L.

### G3.10 Compression pipeline with an accuracy-versus-latency report (TAO prune → QAT/PTQ → build)

- **What the user does:** takes a trained model through prune, quantise and build as one job and reads one report: accuracy before and after each step, plus latency and size at the end.
- **Who uses it:** an ML engineer preparing an edge deployment who must show "we lost 0.4 mAP and gained 3× speed".
- **Flow:** 1. Model → `Optimise`: prune ratio, INT8 calibration set (a split or folder), build profile. 2. `[loading: pruning · calibrating · building]` with three stages; cancel keeps the last good artifact. 3. Report: baseline / pruned / quantised, each with mAP, median latency, p95, size. 4. `[error: calibration set has 12 images — 200 recommended]` warns and still permits. 5. `Compare with current production` overlays the metrics the deployment alias uses.
- **Why it is easy:** the trade-off is one table produced by the job that writes the artifact, so nothing is re-measured by hand in a notebook.
- **Products with it:** TAO lists pruning, quantisation-aware training, post-training quantisation and distillation as separate optimisations, QAT emulating INT8 error during training and serialising ranges for TensorRT (https://docs.nvidia.com/tao/tao-toolkit/text/overview.html, https://docs.nvidia.com/tao/tao-toolkit/text/quantization_aware_training.html); Triton exposes optimisation and a performance analyser for the served model (https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_repository.html).
- **Why it matters for LabelDesk:** our only optimisation is a half-precision build, so a buyer comparing with a TAO pipeline sees no path from checkpoint to quantised artifact.
- **LabelDesk code evidence:** `apps/backend/app/handlers/versioning.py:51-70` (`build(..., "engine", half=True, ...)` — one precision mode, no calibration, no prune, no metrics stored); `apps/backend/app/adapters/tensorrt_ad.py:1-39` (engine treated as an opaque artifact); `apps/backend/app/handlers/training.py:160-173` (evaluation runs on accuracy only, never per optimisation step).
- **Suggested status:** PARTIAL — an FP16 engine can be built and cached; no prune, no INT8, no accuracy delta.
- **Suggested priority / size:** Should / M.

### G3.11 Reject output to the PLC, Modbus/OPC-UA and the MES record (machine-vision cell, DeepStream broker)

- **What the user does:** binds a rule or station verdict to an output — a digital output firing the reject solenoid, a Modbus coil, an OPC-UA tag, an MES record — and tests it without a physical line.
- **Who uses it:** an automation engineer integrating the cell with the line controller; the person who decides whether LabelDesk can be part of the line at all.
- **Flow:** 1. Station → `Outputs` → type (`digital IO`, `Modbus TCP`, `OPC-UA`, `MQTT`, `HTTP/MES`), address, pulse width, verdict-to-value map. 2. `Test` sends a dry-run pulse and shows round-trip time; `[error: connect refused :502]` names the address. 3. `[empty: no outputs — verdicts stay in LabelDesk]`. 4. Run view logs the last 20 dispatches and failures, so a missed reject is visible. 5. A `fault` policy decides what the line does when the output is unreachable (hold / fire reject / stop).
- **Why it is easy:** verdict-to-wire is a row, tested in place, so no bridge service is written and the operator can see whether the last reject actually signalled.
- **Products with it:** DeepStream ships protocol adapters (Kafka, MQTT, AMQP, Redis, Azure IoT) plus a custom adapter interface for exactly this egress (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvmsgbroker.html); Keyence states processed results drive OK/NG judgement, sorting and communication with other devices, including direct robot-controller connection (https://www.keyence.com/products/vision/vision-sys/).
- **Why it matters for LabelDesk:** without an output we are an advisory overlay on a reject station, and the integrator will pick a vendor that can stop the part.
- **LabelDesk code evidence:** `apps/backend/app/routers/alerts.py:1` (alert channels: webhook and email only); `apps/backend/app/services/workflows.py:17-21` (`SINK_KINDS = ("response", "annotations")`); `apps/backend/app/streams/rules.py:88-106` (a fired rule produces an event dict and nothing else); no industrial protocol code found (searched `modbus|opcua|opc_ua|pymodbus|asyncua|digital_output|mqtt|kafka` in `apps/backend/app`: no matches).
- **Suggested status:** MISSING — the only egress is an HTTP webhook.
- **Suggested priority / size:** Must / M.

### G3.12 Symbol reading: barcode, QR and DataMatrix with a lot/part check (industrial code reader)

- **What the user does:** draws a region, picks a symbology, and gets the decoded string per image; a configured pattern (lot, date code, part number) marks each read as matching or not.
- **Who uses it:** a packaging or electronics line engineer proving the right label went on the right box; a QA lead tracing a lot.
- **Flow:** 1. A `Code` region type appears beside the shape tools (or a stream rule `kind: code`). 2. Draw the region on a frame, choose symbologies (Code128, EAN, QR, DataMatrix), set the expected pattern with wildcards. 3. `[loading: reading]` → value, symbology, match, region overlay. 4. `[error: undecodable — low contrast at 0.3 MP; try the sub-stream]`. 5. Event and export carry `code.value` and `code.match`, so a lot is searchable.
- **Why it is easy:** the decode is an annotation field, so it flows into existing filters and exports; the pattern check is one text field, not a script.
- **Products with it:** Keyence lists code reading among the inspection items its systems perform and stores results with the image (https://www.keyence.com/products/vision/vision-sys/); ONVIF Profile M defines metadata and events for counting and license-plate analytics, the same read-then-assert shape (https://www.onvif.org/profiles/profile-m/).
- **Why it matters for LabelDesk:** our OCR reads text inside a box a labeller drew; a line without a scanner expects the tool to find and decode the symbol itself.
- **LabelDesk code evidence:** `apps/backend/app/services/ocr.py:114-152` (OCR text is read off an annotation via `ocr_of`/`_text_of`; nothing decodes a symbol); `apps/backend/app/routers/ocr.py:29-41` (template list/set for OCR fields); no decoder found (searched `barcode|qr|QR|datamatrix|zxing|pyzbar` in `apps/backend/app`: no matches).
- **Suggested status:** MISSING — no symbol decoding at all.
- **Suggested priority / size:** Should / M.

### G3.13 Printed-code verification: expected string versus read string (OCV, not OCR)

- **What the user does:** registers the expected text for an inspection point (serial pattern, date-code format) and gets pass/fail per character class instead of a free-text dump.
- **Who uses it:** a packaging QA engineer checking lot and expiry codes where one wrong digit is a recall.
- **Flow:** 1. OCR template gains `Expected` (literal or pattern) and `Grading` (`exact`, `pattern`, `ignore case`). 2. Run over a batch → `match` / `mismatch` with the first differing position highlighted. 3. `[error: expected pattern has no value for this station — fill it once]`. 4. Mismatches become a dataset filter and a stream event type. 5. Export carries expected, read and verdict.
- **Why it is easy:** the grader sits on the template that already defines where the text is, so nothing is drawn per image and the same template serves the next lot.
- **Products with it:** Keyence describes character recognition for lot codes and OK/NG judgement as one inspection item with stored results (https://www.keyence.com/products/vision/vision-sys/); TAO lists optical character detection and recognition as trainable tasks for this check (https://docs.nvidia.com/tao/tao-toolkit/text/overview.html).
- **Why it matters for LabelDesk:** a customer cannot use today's OCR dump as a quality gate — someone still reads 900 strings.
- **LabelDesk code evidence:** `apps/backend/app/services/ocr.py:59-114` (`mask_pii`, `clean_ocr`, `ocr_of` — normalise and mask, no comparison with an expected value); `:152-192` (`markdown_for`, `json_for` export the read text); `apps/backend/app/routers/ocr.py:41-58` (template stores field positions only).
- **Suggested status:** PARTIAL — text is captured, templated and exported; verification is absent.
- **Suggested priority / size:** Should / S.

### G3.14 Calibrated millimetre metrology with tolerance bands (machine-vision measurement, Keyence)

- **What the user does:** puts a known-size target in the scene once, sets mm-per-pixel, then measures distance, diameter or angle and gets a value in millimetres that is inside or outside a tolerance band, recorded per piece.
- **Who uses it:** a quality engineer who must report a dimension rather than a box; an auditor who needs the calibration record behind the number.
- **Flow:** 1. Station → `Calibrate`: capture the target, click two reference points, type the known distance → scale stored with timestamp and operator. 2. Editor gains a measure tool: two edges → `12.4 mm`, `in tolerance` or `over by 0.3 mm`. 3. `[error: no calibration on this station — measurements disabled]` instead of a silent pixel count. 4. Each measurement is stored with value, unit and calibration id. 5. Re-calibration prompted after N days or a camera move; old values keep the id they were measured under.
- **Why it is easy:** one scale per station turns every later measurement into the unit on the drawing, and keeping the calibration id is what makes the record auditable.
- **Products with it:** Keyence describes pre-calibration and scaling holding ±10 µm accuracy and lists measurement beside defect detection (https://www.keyence.com/products/vision/vision-sys/); DeepStream keeps rule coordinates resolution-independent and scales them to the runtime stream (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html) — the same normalisation a millimetre scale must survive.
- **Why it matters for LabelDesk:** parity row 3-F3.5 asks for a measuring guide; an industrial buyer needs calibration, tolerance and an audit trail, which is a different feature.
- **LabelDesk code evidence:** no measurement or calibration code in the editor (searched `calibrat|mm_per_px|pixel_per_mm|measure|metrolog` in `apps/backend/app`: only evaluation calibration at `services/insights_eval.py:155` and a comment at `models/project.py:103`); shape kinds are `bbox|obb|polygon|keypoints` with no scalar value (`apps/backend/app/services/track.py:26-69` enumerates them).
- **Suggested status:** MISSING — extends 3-F3.5, which additionally only asks for a measuring guide.
- **Suggested priority / size:** Should / M.

### G3.15 Shift board: throughput, reject rate and first-pass yield per station (industrial BI)

- **What the user does:** opens a board at shift start and reads pieces inspected, rejected, first-pass yield, top reason and the trend against the previous shift, per station and per line.
- **Who uses it:** a shift leader and a plant manager, on a wall screen or a phone, without opening a query builder.
- **Flow:** 1. Dashboards → `Shift` widget: shift picker (A/B/C or a custom calendar), station filter. 2. Tiles: inspected, rejected, yield %, top reason, average dwell in the zone. 3. Click a tile → the underlying events, filtered. 4. `[empty: no verdicts this shift — the station ran but nobody confirmed]` separates silence from zero rejects. 5. Export the shift as CSV for MES reconciliation.
- **Why it is easy:** the numbers count verdicts already recorded, so the shift view is a grouping, not a new data path; the empty state stops the classic "no data means zero rejects" mistake.
- **Products with it:** Keyence positions 100 % in-line inspection as a throughput and consistency gain over manual judgement, with results tied to stored images (https://www.keyence.com/products/vision/vision-sys/); Milestone exposes a central dashboard and Smart Wall for live operational numbers (https://www.milestonesys.com/products/software/xprotect/).
- **Why it matters for LabelDesk:** we chart events per hour and dwell, but yield is the number the customer's manager is measured on; without it we are a tool, not a system.
- **LabelDesk code evidence:** `apps/backend/app/services/insights_stream.py:1-5` (event volume per rule/zone/class, dwell distribution, hourly heatmap, cameras), `:198-213` (hourly grid and daily totals — no shift, no yield); `apps/frontend/src/features/streams/StreamAnalytics.tsx:195` (Events tile, "Last N days"); `apps/backend/app/services/labeling_ops.py` counts labeler throughput, a different population (labellers, not pieces).
- **Suggested status:** PARTIAL — hourly event analytics exist; shift calendar, yield and reason breakdown are missing.
- **Suggested priority / size:** Should / M.

### G3.16 Lighting and focus guard per camera against a reference frame (machine-vision robustness)

- **What the user does:** records a reference frame for a camera, sets limits, and gets one alert when the scene drifts — lamp ageing, a moved light, a knocked focus ring, a dirty window — before accuracy falls.
- **Who uses it:** a maintenance technician, and the ML engineer who otherwise learns about a lighting change from an accuracy drop two weeks later.
- **Flow:** 1. Stream detail → `Reference`: `Capture reference` from the current frame, then limits for mean luminance, contrast and sharpness. 2. A check runs on analysed frames; a breach raises one event per cooldown, not per frame. 3. `[loading: comparing 12 frames]` on demand. 4. `[error: camera is 41 % darker than reference — check the light]` with both frames side by side. 5. The stream's counters show a `Scene drift` state, so the wall shows it without opening the stream.
- **Why it is easy:** the three numbers are already computed for uploaded images, so the guard is a comparison with a stored baseline, not a new model; one alert per drift keeps it out of the alarm queue's way.
- **Products with it:** Keyence treats stable illumination as the precondition for inspection and sells lighting and filters to hold it (https://www.keyence.com/products/vision/vision-sys/); ONVIF Profile M can carry scene metadata and device events, where a drift event belongs (https://www.onvif.org/profiles/profile-m/).
- **Why it matters for LabelDesk:** a camera that still sends frames looks healthy in our UI while producing garbage — the commonest cause of a silent accuracy regression in a factory.
- **LabelDesk code evidence:** `apps/backend/app/services/quality.py:1-13,33-50` (sharpness = Laplacian variance, luminance = mean, stored per image at ingest, classes `blurry|dark|ok|unknown`); `apps/backend/app/streams/manager.py:628,713` (watchdog notices **no new frame**, not a dim frame); `apps/backend/app/routers/streams.py:67-82` (`stream_out` exposes fps/frames/detections/events, no scene metrics).
- **Suggested status:** PARTIAL — metrics exist for uploaded images; no per-camera baseline, stream-time check or alert.
- **Suggested priority / size:** Should / S.

### G3.17 A typed event envelope and a broker sink (Kafka/MQTT) for plant systems (DeepStream msgbroker)

- **What the user does:** maps a stream event onto a fixed JSON envelope (site, line, station, camera, rule, objects, verdict, reason, timestamps, model version) and subscribes a broker or endpoint to it, with a replay of the last N events for a new subscriber.
- **Who uses it:** an integrator wiring LabelDesk into an MES or data lake; the person who will not accept "we POST a summary string".
- **Flow:** 1. Station → `Event output` → schema version (read-only JSON preview), transport (MQTT topic, Kafka topic, webhook), filter (rule, class, verdict). 2. `Send test event` → status and latency. 3. `[empty: no output configured — events stay in the timeline]`. 4. Delivery log per output: last 20 attempts, retry state, dead-letter count. 5. Mapping screen for extra fields (piece id from a code read, shift id).
- **Why it is easy:** the envelope is versioned and previewed, so the downstream team codes against a contract instead of reverse-engineering our timeline; the filter is set once per output, not per rule.
- **Products with it:** DeepStream's message broker sends JSON over Kafka, MQTT, AMQP, Redis or a custom adapter, configured by connection string and topic (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvmsgbroker.html); ONVIF Profile M streams metadata and events over the metadata stream, the event service or MQTT (https://www.onvif.org/profiles/profile-m/).
- **Why it matters for LabelDesk:** our event is a rule dict plus a summary sentence, which no MES can ingest, and a broker sink is what makes a factory pilot survive a security review.
- **LabelDesk code evidence:** `apps/backend/app/routers/streams.py:61-64` (`event_out` = id, ts, rule dict, summary string, snapshot, reviewed, predictions); `apps/backend/app/streams/manager.py:807` (prediction payload whitelists class/class_id/track_id/confidence/x/y/width/height — no station, verdict or model version); `apps/backend/app/routers/alerts.py:1` (webhook/email channels, no broker); `apps/backend/app/services/workflows.py:20` (`SINK_KINDS = ("response", "annotations")`).
- **Suggested status:** PARTIAL — an event row and a webhook exist; envelope contract, broker transport, replay and dead-letter do not.
- **Suggested priority / size:** Should / M.

### G3.18 Run the analytics on the camera and send only metadata (ACAP, DeepStream on-device)

- **What the user does:** installs a small package on the camera or station box and LabelDesk receives detections and events instead of video, so a 40-camera site no longer needs 40 uplinks.
- **Who uses it:** an integrator at a bandwidth-constrained or no-cloud site; a plant IT lead who will not open an outbound video path.
- **Flow:** 1. Streams → `Edge mode`: show the compatible package and what it needs (device model, firmware line). 2. `Pair` issues a one-time token; the device shows `Paired` with firmware and model version. 3. Events arrive with `source: edge` and no snapshot unless the device may upload one. 4. `[error: package rejected by the device — ACAP version 4]` names the mismatch instead of a silent disconnect. 5. Stream detail shows `processing on device` and the server-side model picker is disabled with a reason.
- **Why it is easy:** account, rules and event list stay the same; only the compute location moves, so a pilot built on cloud inference can be re-pointed per camera without re-labelling.
- **Products with it:** Axis ACAP runs applications on the camera with access to video, event and parameter systems and I/O, and reports local processing to cut bandwidth and latency (https://developer.axis.com/acap/); DeepStream does the same on a Jetson or GPU box, attaching analytics metadata per frame and per object (https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html).
- **Why it matters for LabelDesk:** a factory with 60 cameras on a 20 Mbps uplink cannot stream them all; our only architecture is central decode, which caps the account at a handful of cameras.
- **LabelDesk code evidence:** `apps/backend/app/streams/manager.py:691-737` (the server opens the source, decodes, infers and tracks in-process); `apps/backend/app/routers/streams.py:469-496` (frames and MJPEG proxied from the server); no device agent or metadata-only ingest found (searched `edge|agent|pair|onvif|metadata_stream|push_event` in `apps/backend/app`: no matches).
- **Suggested status:** MISSING — every stream is decoded on our side.
- **Suggested priority / size:** Could / L.

---

## Already covered by PARITY.md (no card)

- `6-F6.41` source types and the missing ONVIF discovery, `6-F6.42` capture settings — G3.1 adds commissioning controls (credential test, profile pin), not a new source type.
- `6-F6.43` zones, lines and counters — count, zone, line-with-direction and dwell already exist; G3.4/G3.5 add time and ownership, not geometry.
- `6-F6.15` typed event store, `6-F6.16` human verdicts, `6-F6.17` review session, `6-F6.18` watchdog alerts — G3.3/G3.5/G3.17 add reason codes, ack ownership and a broker contract.
- `6-F6.46` edge fleet management (config push, approval, windows) — G3.8 stops at build/device pairing and does not re-plan the fleet console.
- `6-F6.14` monitoring plus `services/drift.py` (MMD two-sample drift) — production drift monitoring exists; no card.
- `5-F5.26` median latency, `5-F5.27` accuracy-vs-latency comparison — G3.9/G3.10 add the device budget and the optimisation report; the metric surface is parity's.
- `5-F5.52` anomaly project with a good-only station — the station model exists; G3.2 extends it upward.
- `3-F3.5` measurement guide in real units — G3.14 supersedes it with calibration and tolerance.
- `6-F6.33` deploy a workflow to an endpoint or device — the chooser; G3.8 is the artifact bookkeeping behind it.

## Title-only / unverified

- **Cognex In-Sight / VisionPro:** two product URLs answered HTTP 429 this session (`/products/machine-vision/in-sight-2d-vision-systems`, `/products/machine-vision/2d-machine-vision-systems/in-sight-2d-vision-systems`). No Cognex claim is made above; the inspection cards lean on Keyence. In-Sight's spreadsheet-style job/recipe model, PLC output blocks and operator view are unverified here.
- **Genetec Security Center:** the techdocs host returned a client-side shell and the product page returned no content. Alarm acknowledgement, incident reporting and map flows are not cited from Genetec anywhere above.
- **Viso.ai:** only the marketing home page loaded (`https://viso.ai/`); it claims a prompt-to-app builder, a camera gateway, edge/on-prem/cloud deployment and 10,000+ camera scale, but `docs.now.viso.ai` returned an empty body. No flow, screen or limit from Viso is asserted.
- **Edge Impulse drift detection, data acquisition and OTA:** index only, pages not opened — no drift or OTA claim is attributed to Edge Impulse. Only the EON Tuner and Deployment pages were read.
- **DeepStream `nvstreammux`, `nvtracker`, `nvdsosd`, 360 D app:** not opened, so tracker configuration detail (reid, per-stream batching, low-level library choice) is unverified; G3.8 rests on the TAO/DeepStream integration page, not tracker docs.
- **Triton Model Analyzer, model pipelines, rate limiter:** linked from the model-repository page but not read; no measurement methodology is attributed to them.
- **Milestone Incident Manager, Smart Map configuration, alarm-to-action rules:** named on the product page, not read in detail; the cards cite only what that page states.
- **Keyence VS-G "dedicated storage" and AI tuning:** marketing description only. The ±10 µm figure is the vendor's own for the XT 3D model, repeated as a claim, not a measurement.
- **ACAP packaging, signing and VAPIX specifics:** index page only; the pairing flow in G3.18 is our proposal, not a description of Axis tooling.
