# LabelDesk ต้องเปลี่ยน navigation เป็นวงจรข้อมูลถึง deploy

**ข้อสรุปหลัก:** nav ปัจจุบันของ LabelDesk (`shell.tsx`) มีแค่ 4 รายการระดับ workspace และ 3 กลุ่มระดับ project (DATA / MODELS / DEPLOY) ซึ่งเรียงตาม lifecycle ถูกทิศแล้ว แต่ยังไม่รองรับสิ่งที่ Tasks 10, 20, 23, 24, 25, 26 สร้างหรือกำลังจะสร้าง เพราะ **ไม่มีหน้า Insights, Streams, Review/Quality, Lineage, Drift, Audit log, Members, Integrations/API keys, Usage เป็นรายการ nav ของตัวเอง ไม่มี global search/command palette และ role-gating ใช้วิธีซ่อนรายการ (`can(i.min)`) ซึ่งทำให้ผู้ใช้ไม่เห็นว่ามีฟีเจอร์นี้อยู่**. แพลตฟอร์มข้อมูล/ML รายใหญ่ทำสามอย่างที่ LabelDesk ยังไม่ทำ คือ จัดกลุ่มตาม lifecycle พร้อมแยก governance ออกมาเป็นกลุ่มของตัวเอง (Snowflake Horizon, Dataiku Govern), แสดงรายการที่ติดสิทธิ์เป็นไอคอน lock แทนการซ่อน (Databricks) และมีช่องค้นหารวมพร้อม recents. งานวิจัยชี้ว่าความเจ็บปวดหลักอยู่ที่ data quality และการ handoff ระหว่างบทบาท ไม่ใช่การ train ดังนั้นแกนของ nav ควรเป็น Data -> Label/Quality -> Train/Evaluate -> Deploy/Monitor โดย version และ lineage ตัดผ่านทุกขั้น. ข้อเสนอคือจัด nav ใหม่เป็น 2 ระดับ (workspace 8 รายการ, project 5 กลุ่ม 17 หน้า), ให้ Cmd/Ctrl+K เป็นทางเข้าเร็วสำหรับผู้เชี่ยวชาญ, และเพิ่ม backlog Tasks 51-66 (16 รายการ) ที่ต่อจาก Tasks 27-50. ความเชื่อมั่นของหลักฐาน: **ปานกลาง** สำหรับโครงเมนูของแพลตฟอร์ม (เป็น docs ไม่ใช่ screenshot ของแอป) และ **ต่ำ** สำหรับ command palette และ persona view ซึ่งไม่มีงานวิจัยหรือเอกสารรองรับตรง ๆ ยกเว้น Ultralytics ที่ยืนยันว่ามี Ctrl/Cmd+K

## nav ปัจจุบันเรียง lifecycle ถูกแต่ซ่อนของและขาดทางเข้าหลัก

จาก `shell.tsx` ระดับ workspace มี Projects, Models, Playground, Deployments ใน sidebar และ Activity, Settings ที่ท้าย sidebar. ระดับ project มี DATA (Upload Data, Annotate, Dataset, Versions, Analytics, Classes & Tags), MODELS (Train, Models), DEPLOY (Deploy & Test, Project Settings) โดยแต่ละรายการมี `min` role ของ annotator / reviewer / admin และรายการที่ต่ำกว่าสิทธิ์ถูก `filter` ทิ้ง. breadcrumb อยู่ใน TopBar, มี GpuBadge, JobTray และปุ่ม theme แต่ไม่มี search ใน shell (ไม่พบ command palette ในโค้ดที่ตรวจ; คำว่า palette ปรากฏเฉพาะใน `glass.tsx`, `theme.ts`, `Settings.tsx`, `Editor.tsx` ซึ่งยังไม่ได้เปิดอ่านว่าเป็น palette ของสีหรือของ command) ส่วน `App.tsx` มี route เพียง models, deployments, activity, playground, settings ระดับ workspace และ upload, annotate, browse, versions, analytics, classes, train, models, deploy, settings ระดับ project (Streams น่าจะอยู่ในหน้า Deploy แต่ยังไม่ได้ตรวจ; ถือเป็นข้อสันนิษฐาน).

เมื่อเทียบกับ backlog จุดที่ nav ไม่รองรับมี 5 จุด. หนึ่ง Task 20 (Insights Studio) ระบุ "Dataset -> Insights tab" ต่อ version, Model page + Compare page, Pipeline graph DAG และ Dashboard builder แต่ nav มีแค่ "Analytics" หน้าเดียว จึงไม่มีที่วางสำหรับ lineage, compare และ dashboard. สอง Task 23 (consensus, honeypot, labeler dashboard) ต้องการหน้า Review/Quality และ workforce ซึ่ง nav ปัจจุบันซ่อนจาก annotator ทั้งหมด. สาม Task 24 (connectors, API keys, webhooks) และ Task 26 (RBAC สองระดับ, audit log, super-admin) ต้องการ Integrations, Members, Audit ซึ่งตอนนี้ยัดอยู่ใต้ `settings/*` เดียว. สี่ Task 25 (alias production/staging, drift, usage) ต้องการหน้า Monitor ที่ผูกกับ Deployments. ห้า Task 18 (landing) และ Task 21 (auth) ปิดงานฝั่ง public แล้ว แต่ยังไม่มี onboarding/Home สำหรับผู้ใช้ใหม่. ข้อสังเกตเรื่องการซ่อน: แพลตฟอร์มที่ศึกษาไม่ได้ทำเหมือนกันหมด Databricks ใช้ไอคอน lock กับรายการที่ผู้ใช้ไม่มี entitlement ([Databricks navigate workspace](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)) ขณะที่ CVAT/Encord/Roboflow ใช้ role-gate ระดับหน้า (หลักฐานเป็นการอนุมานจากชื่อ role ใน docs ไม่ใช่การยืนยัน UI) ([Encord llms.txt](https://docs.encord.com/llms.txt); [Roboflow llms.txt](https://docs.roboflow.com/llms.txt)).

## แพลตฟอร์มใหญ่จัดกลุ่มตาม lifecycle และแยก governance ออกมา

กลุ่มแพลตฟอร์มข้อมูล/ML ให้ภาพที่สอดคล้องกัน. Databricks แบ่ง sidebar เป็นกลุ่มตามงาน โดยกลุ่ม AI/ML เรียง Playground, Agents, AI Gateway, Experiments, Features, Models, Serving ซึ่งใกล้เคียงลำดับ lifecycle, มีช่องค้นด้านบนที่ครอบคลุม notebook, query, dashboard, UC table, job และรายการที่เพิ่งดู แต่ **เอกสารไม่ได้อธิบาย command palette แยกต่างหาก** ([Databricks](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)). Snowsight จัดใหม่เป็น Work with data / Horizon Catalog / Manage โดยยก Governance & security (Trust Center, Tags & policies, Users & roles) ออกมาเป็นกลุ่มของตัวเอง และให้ผู้ใช้ pin shortcut ได้ **3 หน้า** พร้อมลากจัดลำดับ ([Snowsight navigation](https://docs.snowflake.com/en/user-guide/snowsight-navigation)). Vertex AI จัดตาม lifecycle ตั้งแต่ Feature Store, Model Registry (version, alias, label), evaluation, Pipelines (lineage, caching), Experiments, Model Monitoring (drift, skew) ถึง endpoints ([Vertex AI intro](https://docs.cloud.google.com/vertex-ai/docs/start/introduction-unified-platform)). SageMaker ผูก lineage เข้ากับ model version: Models > Registered models > Model Groups > version > แท็บ Lineage ที่เป็นแผนที่เชิงโต้ตอบของ dataset, training job, approval, model, endpoint ([SageMaker lineage](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-lineage-view-studio.html)). Dataiku แยก Govern เป็น node ต่างหากจาก Design พร้อม workflow sign-off ([Dataiku Govern](https://doc.dataiku.com/dss/14/governance/navigation.html)). Azure Foundry ให้ประเมินได้จากทั้งหน้ารวมและหน้าของ model และประเมินจาก production traces ได้ ([Foundry evaluate](https://learn.microsoft.com/en-us/Azure/foundry/how-to/evaluate-generative-ai-app)). W&B เน้น Reports ที่แชร์ได้และ Registry ที่มี lineage ([W&B site](https://site.wandb.ai/?p=1170); [CoreWeave docs](https://docs.coreweave.com/forge-home)). หลักฐานของ Azure, W&B, Hugging Face, Dataiku, DataRobot มาจาก search snippet เป็นส่วนใหญ่ จึงใช้ได้ระดับ "รูปแบบที่พบซ้ำ" ไม่ใช่รายละเอียดเมนู.

กลุ่ม CV/labeling ให้ภาพที่ใกล้ LabelDesk กว่า แต่ **ยืนยันได้ระดับ docs เท่านั้น** (เมนูในแอปอยู่หลัง login). ที่ยืนยันดีที่สุดคือ Ultralytics Platform: sidebar บนสุดคือ Search (Ctrl/Cmd+K), Home, Explore, Agents ตามด้วย Annotate, Train, Deployments (แสดง 5 รายการล่าสุดของแต่ละกลุ่ม), ท้ายสุดคือ Help, Settings, เมนูบัญชี (สลับ workspace, activity, ทัวร์ซ้ำ) และมี Trash ที่เก็บ 30 วัน ([Ultralytics quickstart](https://docs.ultralytics.com/platform/quickstart/)). CVAT มีหน้าระดับบนคือ Projects, Tasks, Jobs, Cloud storages, Requests, Models, Bulk actions, Search ([CVAT docs](https://docs.cvat.ai/docs/)). FiftyOne Enterprise เปิดด้วยหน้า Datasets ที่มี pinned datasets, search และ sort พร้อมแท็บ Manage (Access: "Can view"/"Can manage") และ Discussion panel ([FiftyOne enterprise app](https://docs.voxel51.com/enterprise/app.html)). Encord แยกพื้นที่ Index, Active, Annotate, Workflows, Analytics, Admin และกำหนด role ต่างกันระหว่าง Taskers กับ Managers/Admins ([Encord llms.txt](https://docs.encord.com/llms.txt)). Roboflow จัด docs เป็น Workspaces, Projects/Datasets, Teams & Roles (Labeler/Reviewer, Audit Logs), Models, Workflows, Deployment, Monitoring ([Roboflow llms.txt](https://docs.roboflow.com/llms.txt)). V7 ใช้ Workflows แบบ stage (Annotate, Review, Model, Consensus) ([V7 llms.txt](https://docs.v7labs.com/llms.txt)). รูปแบบที่เห็นใน 3 ราย ขึ้นไป คือ Home/Dashboard, Datasets, Annotate/Tasks, Review/QA, Models, Deploy/Monitor, Workflows/Automation, Integrations, Team/Roles, Settings/Billing, Trash. **ข้อควรระวังเรื่อง persona:** แพลตฟอร์มทำ persona เป็นการจำกัดหน้าตาม role ไม่ใช่แอปแยก (การอนุมานของโน้ต) และไม่มีแหล่งที่ยืนยัน persona-based switching ในแพลตฟอร์ม ML.

## งานวิจัยชี้ว่าต้องเด่นเรื่อง data quality, lineage และ slice ไม่ใช่การ train

เอกสารวิจัยให้เหตุผลเชิงโครงสร้างสำหรับ nav. Sambasivan และคณะสัมภาษณ์ 53 practitioner พบว่า **92% เจอ data cascades** (ปัญหาข้อมูลที่สะสมแล้วส่งผลปลายน้ำ) ซึ่งมัก "มองไม่เห็นและล่าช้า" ([Google Research, CHI 2021](https://research.google/pubs/everyone-wants-to-do-the-model-work-not-the-data-work-data-cascades-in-high-stakes-ai/)) ผลคือสถานะคุณภาพข้อมูลควรเป็น badge ใน nav ไม่ใช่รายงานที่ต้องเข้าไปหา (ข้อนี้เป็นข้อสรุปของเรา). Shankar และคณะ (18 MLE) สรุปว่าความสำเร็จขึ้นกับ Velocity, Validation, Versioning ([arXiv 2209.09125](https://arxiv.org/abs/2209.09125)) และ Nahar และคณะ (45 คน, 28 องค์กร) พบจุดชนกันที่ requirements, data และ integration ระหว่างบทบาท ([arXiv 2110.10234](https://arxiv.org/pdf/2110.10234)) จึงควรมี artifact ร่วม (data spec, model card, target metric) ที่ annotator, ML engineer และ product owner เห็นตรงกัน. Sculley และคณะเตือนเรื่อง undeclared consumers ([NeurIPS 2015](https://neurips.cc/virtual/2015/poster/5680)) ซึ่งรองรับหน้า Lineage ที่แสดงว่า dataset version ถูกใช้ที่ไหนก่อนลบ. ด้าน platform paper TFX, Michelangelo และ MLflow ให้ object model เดียวตลอดทาง (dataset, run, model, deployment) และให้ทุก training run เป็น record ที่เทียบกันได้ ([TFX](https://research.google/pubs/tfx-a-tensorflow-based-production-scale-machine-learning-platform/); [Uber](https://www.uber.com/en-UA/blog/michelangelo-machine-learning-platform/); [MLflow](https://www.cs.berkeley.edu/~alig/papers/mlflow.pdf)); ease.ml/ci เสนอ gate ก่อน promote และเตือนเมื่อ test set เก่าเกินไป ([MLSys 2019](https://proceedings.mlsys.org/paper_files/paper/2019/hash/4284d31e68c0a4a39dcdad167ac4bd72-Abstract.html)). งาน evaluation (Errudite, Zeno, Domino) เห็นตรงกันว่า **slice เป็นวัตถุกลาง** โดย Errudite เสนอ query ที่บันทึกและรันซ้ำได้ ([IDL](https://idl.uw.edu/papers/errudite)) และ Domino ค้นหา slice ที่อ่อนอัตโนมัติ แต่ตั้งชื่อถูกเพียง **35% ของ setting** ([arXiv 2203.14960](https://arxiv.org/pdf/2203.14960)) จึงต้องแสดงเป็น "สมมติฐาน" ให้คนยืนยัน และงานเหล่านี้ไม่ใช่ CV detection โดยตรง. สิ่งที่งานวิจัยไม่ให้: ผลศึกษา IA เฉพาะ CV platform ไม่มี และ **ไม่พบงานวิจัยเรื่อง command palette** (โน้ตค้นหาแล้วไม่พบ). หลักฐาน UX ที่มีคือ progressive disclosure (ผ่านแหล่งรอง), training wheels (Carroll), และ CommandMaps ที่ผู้เชี่ยวชาญเร็วขึ้นแต่ novice ไม่ต่างจากเมนูปกติ ([CHI 2012](https://hci.cs.umanitoba.ca/publications/details/improving-command-selection-with-commandmaps)); Findlater และ McGrenere เทียบเมนู adaptive กับ adaptable ([CHI 2004](https://www.cs.ubc.ca/labs/edapt/papers/findlater2004.pdf)). ข้อสรุปเชิงออกแบบ: ตำแหน่งเมนูคงที่ ปล่อยให้ผู้ใช้ pin เอง ไม่เรียงอัตโนมัติ, nav ที่มองเห็นต้องคงไว้สำหรับ novice, ส่วน palette เป็นทางลัดของผู้เชี่ยวชาญ (การอนุมาน).

## ข้อเสนอ: nav ใหม่สองระดับ พร้อมกติกา role, lock และ search

หลักการ 5 ข้อ: (1) เรียงตาม lifecycle Data -> Label/Quality -> Train/Evaluate -> Deploy/Monitor และคงตำแหน่งไว้ (CommandMaps); (2) governance แยกกลุ่มของตัวเอง (Snowflake, Dataiku); (3) แสดงรายการที่ติดสิทธิ์พร้อมไอคอน lock แทนการซ่อน (Databricks) ยกเว้นรายการที่ role นั้นไม่มีทางได้ใช้เลย; (4) badge สถานะคุณภาพ/drift/job บน nav เพื่อแก้ปัญหา "มองไม่เห็นและล่าช้า"; (5) ผู้ใช้ pin ได้ 3 รายการ (Snowflake). ชื่อที่ติด `*` คือหน้าที่ยังไม่มีใน nav ปัจจุบัน และ `(T#)` คือ task ที่สร้างฟีเจอร์นั้น.

### Nav tree ที่เสนอ

```
TOP BAR (ทุกหน้า)
  [Workspace switcher] > breadcrumb          [Search  Ctrl/Cmd+K]  [GPU badge] [Jobs] [Notifications] [Theme] [Account]

WORKSPACE LEVEL (sidebar)
  Home*                  สถิติ workspace, งานที่รอฉัน (task queue / review), recent, quick actions, onboarding checklist
  Projects               รายการ project (ปักหมุดได้)
  Explore* (D)           template / dataset ตัวอย่าง (ไว้หลัง Task 48)
  ---- BUILD ----
  Models                 registry ข้าม project: version, alias, license, approval (T25, T2)
  Playground             (T6)
  Deployments            alias production/staging, streams ข้าม project, drift/monitor (T10, T25)
  ---- GOVERN (แสดงตาม role, มี lock) ----
  Members & Roles*       RBAC 2 ชั้น + custom roles (T26)
  Audit log*             filter + export รวมการดู footage (T26)
  Usage & Billing*       GPU-sec, stream-hours, quota (T25)
  Integrations*          cloud connectors, API keys, webhooks, SDK (T24)
  ---- FOOTER ----
  Pinned (สูงสุด 3), Trash* (30 วัน), Activity, Settings (profile, security/MFA, preferences, DPA/PDPA), Help/Tour

PROJECT LEVEL (panel ใน project)
  OVERVIEW*              สรุป project: dataset health badge, run ล่าสุด, model ที่ deploy, งานค้าง
  DATA
    Upload                 + batch / connector sync (T24)
    Dataset                grid, filter, Collections*, semantic search* (T27)
    Versions               + version diff (T20a)
    Classes & Tags         ontology, attributes* (T39)
    Insights               เดิม "Analytics": class dist, geometry, leakage, embedding map (T20a)
  LABEL
    Annotate               task queue / board (annotator เข้าที่นี่ก่อน)
    Review & Quality*      review queue เรียงตาม disagreement, consensus, honeypot (T23), suspect-label* (T28)
    Team performance*      throughput, accuracy, AI-acceptance (T23)
  MODELS
    Train                  (T2, T8)
    Runs & Compare*        ตาราง run, overlay curve, compare 2-4 model (T20b)
    Evaluate*              PR/CM drill-down, slice, TIDE, weak slices* (T20b, T16)
    Models                 version + แท็บ Lineage* (T20c)
  DEPLOY
    Deploy & Test         predict, export (TensorRT) (T14)
    Streams*              กล้อง, rules, events (T10, T13)
    Monitor*              drift, active-learning queue, alert (T25)
    Lineage & Dashboards*  DAG + dashboard builder (T20c)
  SETTINGS
    Project settings      retention, access (Can view / Can manage), danger zone
```

### กติกา role และ locked item

ปัจจุบัน role ในโค้ดคือ annotator < reviewer < admin และ Task 26 จะแทนด้วย workspace owner/admin/billing/member กับ project manager/reviewer/labeler/viewer. ข้อเสนอเป็น **default view + progressive disclosure ไม่ใช่การซ่อนถาวร**. Labeler/annotator เห็นเพียง Home (task queue), Annotate, Dataset (อ่าน) และ Help: กลุ่มอื่นไม่แสดงเลยเพราะไม่มีเส้นทางไปใช้ (ลด cognitive load; Encord, LandingLens, Supervisely จำกัด labeler ให้ label อย่างเดียว ตาม docs). Reviewer เห็นเพิ่ม Review & Quality, Insights, Versions, Models, Evaluate. ML engineer/project manager เห็น Train, Runs & Compare, Deploy, Streams, Monitor. Workspace admin/owner เห็นกลุ่ม GOVERN ครบ. Billing เห็นเฉพาะ Usage & Billing. Viewer อ่านอย่างเดียว. รายการที่ role ต่ำกว่าขั้นแต่ **มีเส้นทางขอสิทธิ์ได้** (เช่น Train สำหรับ reviewer, Audit log สำหรับ member) แสดงเป็นสีจางพร้อมไอคอน lock และ tooltip บอก role ที่ต้องมี กับปุ่ม "ขอสิทธิ์" (Databricks ใช้ lock กับ entitlement; การใช้กับ role และปุ่มขอสิทธิ์เป็นข้อเสนอของเรา). ฟีเจอร์ที่ติดแผน (plan) เช่น SSO, audit export ใช้ lock ลักษณะเดียวกันแต่ชี้ไปหน้า upgrade: หน้าใน route ต้องบังคับสิทธิ์ที่ฝั่ง server เสมอ (nav เป็นแค่การนำทาง).

### Search และ command palette

ช่อง Search ใน top bar ค้นข้ามชนิดออบเจ็กต์: project, dataset/version, class, run, model, deployment, stream, member, และหน้า nav ทั้งหมด พร้อมรายการ recents (รูปแบบ Databricks: ค้นข้ามชนิด + recents; CVAT มีหน้า Search; FiftyOne ค้นชื่อ/tag/media type; Labelbox Catalog ใช้ vector search). การเรียกด้วย **Ctrl/Cmd+K ยืนยันเฉพาะ Ultralytics** ([Ultralytics quickstart](https://docs.ultralytics.com/platform/quickstart/)); **ไม่มีแหล่งอื่นในโน้ตที่ยืนยันว่า Databricks, Snowflake, Vertex, SageMaker, Roboflow, Encord หรือ CVAT มี command palette และไม่มีงานวิจัยวัดผล** จึงตั้งเป็นสมมติฐานที่ต้องวัดจาก usage เอง. ขอบเขตรอบแรก: ค้นหา + กระโดดไปหน้า + action ไม่กี่อย่าง (New project, Upload, Start training, Open Trash) และให้ Task 27 ต่อยอดเป็น semantic search ของภาพ. แผน Task 11 ระบุ "command palette" ไว้ในรายการ chrome ที่ใช้ Liquid Glass อยู่แล้ว แต่ตรวจโค้ดไม่พบการ implement ใน `shell.tsx` จึงถือเป็นช่องว่างที่ค้างอยู่.

## backlog ต้องเพิ่มต่อจาก Task 50: ย้ายเมนู เปิด surface ที่ขาด แล้วเชื่อมวงจรคุณภาพ

Tasks 27-50 เดิมเน้นความสามารถเชิงอุตสาหกรรมเทียบ Roboflow (semantic search, suspect-label, anomaly, workflows, OCR, edge, PLC) และไม่ได้แก้ IA ของแอป. ตารางด้านล่างคือรายการ **ใหม่** ที่ไม่ซ้ำกับ 27-50 (ซ้ำเมื่อไรอ้างอิง task เดิมแทน). Priority: M = จำเป็นต่อวงจรหลักหรือบล็อกงาน nav, S = รอบถัดไป, D = เลื่อนได้. ความแข็งแรงของหลักฐานระบุท้ายแถว (แข็ง = มีแหล่งตรง, กลาง = หลายแหล่งทางอ้อม, อ่อน = อนุมานของเรา).

| # | ชื่อ | Scope | P | แหล่ง / หลักฐาน |
| --- | --- | --- | --- | --- |
| 51 | Nav v2 shell | ปรับ `shell.tsx`/`App.tsx` ตามต้นไม้ด้านบน: กลุ่ม BUILD/GOVERN, project panel 5 กลุ่ม, redirect route เดิม, ทดสอบ role matrix | M | Databricks/Snowflake nav (กลาง); backlog T20-26 ไม่มีที่วาง (แข็ง) |
| 52 | Global search + command palette | Ctrl/Cmd+K ค้น project/dataset/run/model/stream/member + recents + action สั้น ๆ; endpoint ค้นรวมฝั่ง server; keyboard + a11y | M | [Ultralytics](https://docs.ultralytics.com/platform/quickstart/) (ยืนยัน palette); [Databricks](https://docs.databricks.com/gcp/en/workspace/navigate-workspace) (search รวม); ประโยชน์ต่อ expert: CommandMaps (อ่อน-กลาง) |
| 53 | Locked-item pattern + request access | ไอคอน lock + tooltip role/plan ที่ต้องมี + ปุ่มขอสิทธิ์ถึง admin; server enforcement คงเดิม | M | [Databricks](https://docs.databricks.com/gcp/en/workspace/navigate-workspace) (แข็ง); ปุ่มขอสิทธิ์เป็นข้อเสนอเรา (อ่อน) |
| 54 | Home / workspace dashboard + onboarding | สถิติ (dataset, images, annotations, models, deployments), งานที่รอฉัน, recent activity, checklist ผู้ใช้ใหม่, guided tour ซ้ำได้ | M | [Ultralytics Home + tours](https://docs.ultralytics.com/platform/quickstart/) (แข็ง); LandingLens 7 ขั้น ([docs](https://landinglens.docs.landing.ai/landinglens-workflow)) |
| 55 | Project Overview + health badges | หน้า Overview ต่อ project และ badge บน nav: dataset health (T9), suspect-label (T28), drift (T25), job ที่รัน | M | [Sambasivan CHI 2021](https://research.google/pubs/everyone-wants-to-do-the-model-work-not-the-data-work-data-cascades-in-high-stakes-ai/) (ปัญหาแข็ง, วิธีแก้เป็นอนุมาน) |
| 56 | Review & Quality hub | รวมหน้า review queue, consensus, honeypot, labeler performance (T23) เป็นกลุ่ม LABEL; task queue สำหรับ annotator แทนการเลือกภาพเอง | M | Encord/V7/CVAT QA ([Encord](https://docs.encord.com/llms.txt); [V7](https://docs.v7labs.com/llms.txt); [CVAT](https://docs.cvat.ai/docs/)) (กลาง) |
| 57 | Lineage tab บน model + registry states | แท็บ Lineage: upload batch -> version -> run -> model -> deployment (ต่อ T20c), สถานะ approval (draft/approved/production) และแสดง "ใครใช้ version นี้" ก่อนลบ | M | [SageMaker lineage](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-lineage-view-studio.html); [Sculley](https://neurips.cc/virtual/2015/poster/5680) (กลาง) |
| 58 | Promotion gate + stale-test warning | เกณฑ์ก่อนตั้ง alias production (เช่น mAP ต้องไม่ตกเกิน x บน holdout) และเตือนเมื่อ test set ถูกใช้ซ้ำมาก/ล้าสมัย; ต่อ T25 alias | S | [ease.ml/ci](https://proceedings.mlsys.org/paper_files/paper/2019/hash/4284d31e68c0a4a39dcdad167ac4bd72-Abstract.html) (กลาง; เป็นงานเชิงสถิติ ไม่ใช่ UI) |
| 59 | Saved slices + weak-slice suggestions | slice ที่ตั้งชื่อ/บันทึก/รันซ้ำได้ต่อ model ใหม่ (tag, size, brightness, source), ปุ่ม "ส่งไป relabel/active-learn", slice อัตโนมัติติดป้าย "สมมติฐาน" | S | [Errudite](https://idl.uw.edu/papers/errudite); [Zeno](https://arxiv.org/pdf/2302.04732); [Domino](https://arxiv.org/pdf/2203.14960) (กลาง; ไม่ใช่งาน detection โดยตรง) |
| 60 | Shareable reports | สร้างรายงานผล evaluation/compare เป็นลิงก์ภายใน workspace + export PDF/PNG; ต่อ dashboard builder T20c | S | [W&B Reports](https://site.wandb.ai/?p=1170) (กลาง); [Zeno](https://arxiv.org/pdf/2302.04732) |
| 61 | Trash + restore 30 วัน | ถังขยะ project/dataset/model/image ที่กู้ได้ 30 วัน เข้าถึงจาก sidebar และ search; เชื่อม retention T26 | S | [Ultralytics](https://docs.ultralytics.com/platform/quickstart/) (แข็ง); Roboflow มี Trash ([llms.txt](https://docs.roboflow.com/llms.txt)) |
| 62 | Pins + recents | pin สูงสุด 3 รายการต่อผู้ใช้ลากจัดลำดับได้, recents ใน search; ไม่เรียงเมนูอัตโนมัติ | S | [Snowsight](https://docs.snowflake.com/en/user-guide/snowsight-navigation); [Findlater & McGrenere](https://www.cs.ubc.ca/labs/edapt/papers/findlater2004.pdf) (กลาง) |
| 63 | Dataset access panel + discussion | แท็บ Manage ต่อ dataset/project: Access (Can view/Can manage), clone, danger zone และ comment thread ผูกกับ image/annotation | S | [FiftyOne Enterprise](https://docs.voxel51.com/enterprise/app.html) (แข็ง); Nahar ICSE 2022 เรื่อง handoff (กลาง) |
| 64 | Requests / background jobs page | หน้ารวม job ทั้ง workspace (สถานะ, retry, ผู้สั่ง, log) ต่อยอด JobTray ที่ดูได้เฉพาะ project ปัจจุบัน | S | [CVAT Requests](https://docs.cvat.ai/docs/) (แข็ง) |
| 65 | Shared artifacts: data spec + model card | หน้า spec ต่อ project (class definition, ตัวอย่างขอบเขต, target metric) และ model card สร้างอัตโนมัติจาก eval; annotator เห็น spec ในหน้า Annotate | S | [Nahar et al.](https://arxiv.org/pdf/2110.10234) (กลาง; ไม่ใช่ CV) |
| 66 | Eval จาก production traces | สุ่มเฟรม/ผล stream เข้า evaluation set เพื่อวัดซ้ำบนข้อมูลจริง (ต่อ T25 drift และ active learning) | D | [Foundry traces](https://learn.microsoft.com/en-us/Azure/foundry/how-to/evaluate-generative-ai-app) (กลาง; แนวคิดจาก LLM eval) |

ลำดับที่แนะนำ: **51 -> 52 -> 53 -> 54 -> 55** (ทำชุดเดียว เพราะแตะ `shell.tsx` ไฟล์เดียวกัน), ตามด้วย 56 และ 57 ซึ่งเป็นตัวเปิดทางเข้า Tasks 20c/23 ที่สร้างไปแล้วแต่ยังไม่มีที่วางใน nav. ข้อควรตรวจก่อนเริ่ม: ยังไม่ได้อ่านโค้ดของหน้า Deploy/Analytics/Settings จริง จึงยืนยันไม่ได้ว่าส่วนใดของ Tasks 20-26 ถูกใส่ไว้ใต้หน้าเดิมแล้ว (เช่น Streams, Audit, Members อาจอยู่ใน tab ภายใน) การย้ายต้องเริ่มจาก inventory route ที่ใช้งานจริง.

## อะไรควรสร้างเอง อะไรควรเชื่อม และอะไรควรข้าม

แพลตฟอร์มใหญ่มีบางชั้นที่ทีมเล็กสร้างให้เทียบเท่าไม่ได้ (notebook, warehouse, feature store, marketplace). ข้อเสนอด้านล่างอิงที่ว่า LabelDesk ขายความสามารถ "สร้างโมเดลตรวจสอบโดยไม่ต้องมีทีม ML" (จากรายงานก่อนหน้า) และงบหน่วยความจำ GPU/คนจำกัด. ทั้งหมดเป็นการตัดสินใจเชิงกลยุทธ์ของเรา ไม่ใช่ข้อเท็จจริงจากแหล่ง ยกเว้นข้อมูลของคู่แข่งที่อ้างไว้.

| สิ่งที่คู่แข่ง/แพลตฟอร์มมี | ตัดสินใจ | เหตุผลและวิธีทำ |
| --- | --- | --- |
| Notebook (Databricks, Snowflake, DataRobot) | **Integrate** | ให้ Python SDK/CLI (T24) + ปุ่ม "Open in Colab/Jupyter" พร้อม snippet ดึง dataset version/export; ไม่ host kernel เอง. FiftyOne ที่เชื่อมกับ CVAT ในรายการ integration ([CVAT docs](https://docs.cvat.ai/docs/)) เป็นแบบอย่างของการเชื่อมแทนการสร้าง |
| Data warehouse / SQL editor / Lakehouse | **Skip** (ให้ export) | ข้อมูลหลักเป็นภาพ+annotation ไม่ใช่ตาราง; เปิด export metadata/events เป็น CSV/Parquet และ webhook (T24) ให้ลูกค้านำเข้า BI/warehouse ของตนเอง; Dashboard builder ใน T20c ครอบคลุมความต้องการระดับโปรเจกต์แล้ว |
| BI / dashboard (Power BI-like) | **Build แบบจำกัด** | T20c มีอยู่ ให้คงขอบเขต 7 chart type + KPI และ export CSV; อย่าขยายเป็นเครื่องมือ BI ทั่วไป |
| Experiment tracking / registry (MLflow, W&B) | **Build เบา + Integrate** | มี run record และ registry ในตัว (T8, T25, 57); เสนอ export เป็น MLflow format หรือ W&B ผ่าน SDK ภายหลังแทนการสร้างฟีเจอร์เท่า W&B (sweeps, artifacts) |
| Feature Store (Vertex, Databricks) | **Skip** | ไม่มีโจทย์ tabular feature ใน CV loop; embedding ที่ cache สำหรับ T20a/T27 เพียงพอ |
| Pipelines orchestrator (Vertex Pipelines, TFX) | **Skip + Build workflow ระดับ block** | ใช้ No-code Workflow (T31) สำหรับ inference และ job queue ที่มีอยู่สำหรับ train; ไม่สร้าง DAG orchestrator ทั่วไป |
| Model hub / marketplace (Vertex Model Garden, HF) | **Integrate** | registry ของ adapter (ultralytics, rfdetr, hf) ดึงโมเดลจาก HF ได้แล้ว (T15); แสดง license badge (T2); ไม่ทำ marketplace เอง |
| AI assistant ใน nav (Genie, Cortex Code) | **Build แคบ** | ผู้ช่วยตอบจากข้อมูล project และอ้างอิงแหล่ง (รูปแบบ Databricks ที่อ้าง doc และปฏิเสธเมื่อไม่มีหลักฐาน; [Databricks](https://docs.databricks.com/gcp/en/workspace/navigate-workspace)) ผูกกับ MCP/agent API (T37) แทนแชตทั่วไป; ใช้สิทธิ์เดียวกับผู้ใช้ |
| Governance suite เต็ม (Horizon, Dataiku Govern) | **Build ส่วนที่ PDPA ต้องใช้** | RBAC, audit, retention, blur (T26) เท่านั้น; workflow sign-off ใช้ promotion gate (58) แทน |
| Fleet manager / Deployment Manager (Roboflow Enterprise) | **Build ภายหลัง** | T35; รอสัญญาณจาก design partner ก่อน |
| Public hub เช่น Universe/Explore | **Defer** | T48 หลังมีผู้ใช้ ไม่ใช่งาน nav รอบนี้ |
| Foundation-model eval ฝั่ง LLM (Weave, Foundry) | **Skip** | ไม่ใช่ขอบเขต CV detection; เก็บเฉพาะแนวคิด production traces (66) |

## ข้อสรุป

สิ่งที่เปลี่ยนจากภาพเดิม: ช่องว่างของ LabelDesk ไม่ได้อยู่ที่ฟีเจอร์ labeling หรือ train แล้ว (Tasks 1-26 ปิดไปมาก) แต่อยู่ที่ **ทางเข้าและความมองเห็น**. ฟีเจอร์ที่ทำไปแล้วใน Tasks 20, 23, 24, 25, 26 ไม่มีที่อยู่ใน nav ที่มี 4+9 รายการ ผู้ใช้จึงเข้าไม่ถึง และ role-gating แบบซ่อนทำให้ผู้ซื้อไม่เห็นว่าสิ่งนั้นมีอยู่. การย้ายไป nav v2 (Tasks 51-55) จึงมีผลต่อการขายและการ onboarding มากกว่าฟีเจอร์ใหม่หลายรายการใน Tasks 27-50 ควรทำก่อนเริ่ม Task 27 เพราะ semantic search (27) และ suspect-label (28) ต้องการ search bar และ badge ที่ nav v2 จัดให้.

สิ่งที่ยังไม่รู้: (1) ผู้เชี่ยวชาญของเราจะใช้ command palette จริงหรือไม่ ต้องวัดจาก usage หลังปล่อย เพราะไม่มีงานวิจัยและมีเพียง Ultralytics ที่ยืนยันว่ามีใน CV platform ตามโน้ต; (2) เมนูจริงในแอปของ Roboflow, Encord, V7, Labelbox, SuperAnnotate ยังไม่เคยยืนยัน เพราะอยู่หลัง login ควรสมัครทดลองใช้เพื่อ walk-through ก่อนฟรีซดีไซน์; (3) role ที่ใช้ใน UI ปัจจุบัน (annotator/reviewer/admin) กับ RBAC ใหม่ของ Task 26 ต้องจับคู่กันก่อนทำ Task 51; (4) มี persona ใดเป็นผู้ซื้อหลัก (ผู้จัดการโรงงานหรือ ML engineer ของ SI) เพราะนั่นกำหนดว่า Home ควรแสดงอะไรเป็นอย่างแรก.
