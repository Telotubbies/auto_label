# CV adoption by sector (2025-2026), Thailand/SEA focus, and platform requirements

Note on evidence quality: 12 web searches (snippets only, no page fetches). Many sources are vendor or market-research pages. Sector "platform requirements" are inferences, listed separately. Uncited items from general domain knowledge are flagged in Gaps.

## 1. Manufacturing (visual inspection, PCB/IC, robots, PPE)

### Takeaway
Thailand's electronics/semiconductor/HDD base drives AI inspection demand, motivated by inspector labor shortages. Market sizes vary wildly by report and are unreliable.

### Cited Findings
- One report sizes Thailand AI inspection at ~USD 430M (2025) to ~2.07B (2030), 25.2% CAGR — [MarketsandMarkets](https://www.marketsandmarkets.com/Market-Reports/geography/ai-inspection-market/Thailand); a different report puts industrial machine vision at ~USD 87M in 2032, defect detection fastest-growing at 8% — [Databridge](https://www.databridgemarketresearch.com/nucleus/thailand-industrial-machine-vision-market). Definitions differ; do not compare.
- Electronics makers deploy AI visual inspection for PCB assembly, semiconductor packaging, HDD parts (generic claim, no named factories) — [Unimon](https://unimon.co.th/en/blog/thailand-manufacturing-ai-predictive-maintenance-guide)
- Labor shortage and inspector skill variance cited as the driver — [Unimon](https://unimon.co.th/en/blog/thailand-manufacturing-ai-predictive-maintenance-guide)
- Visionatics panel inspection (Intel partner brief) is an example vendor — [Intel ARK](https://ark.intel.com/content/dam/www/central-libraries/us/en/documents/2023-06/visionatics-panel-inspection-solution-partner-brief.pdf)
- AIS + Huawei Cloud positioning Thailand as AI-era manufacturing hub with 5G — [Khaosod English](https://www.khaosodenglish.com/sponsored/2026/08/03/ais-business-partners-with-huawei-cloud-to-advance-global-cloud-and-intelligent-5g-solutions-positioning-thailand-as-an-ai-era-manufacturing-hub/) (sponsored content)
- Nippon Steel Engineering's Thai subsidiary (TNS) piloted CCTV ML for unsafe conditions/worker state at manufacturing and construction sites; >70% of Thai accidents reportedly in these industries — [JETRO](https://www.jetro.go.jp/ext_images/_News/announcement/2021/d38074f8efc798ae/NIPPONSTEELENGINEERING_en.pdf)

### Inferences
- Platform needs: few-defect / anomaly detection (good-only training), high-res tiling for small defects, oriented boxes and fine masks, industrial camera ingest, ONNX/TensorRT export, edge/PLC/OPC-UA output, active learning for drift, per-line model versioning. Robot bin-picking adds 6D pose, depth/point cloud labeling.
- PPE detection is a fast "land" product (standard classes, CCTV RTSP).

### Gaps
- No sourced Thai bin-picking or robot-arm vision deployments found. No named Thai PCB/IC factory case studies.

## 2. Banking and finance (KYC, OCR, cheques)

### Takeaway
BoT permitted bank facial-recognition eKYC since 2020; Thai ID OCR, liveness and face match are a mature vendor market. Document AI for Thai is advancing via open VLMs.

### Cited Findings
- BoT approved facial recognition for bank eKYC; six banks incl. KBank, Bangkok Bank, SCB authorised initially — [Khaosod English](https://www.khaosodenglish.com/news/crimecourtscalamity/2020/02/07/bank-of-thailand-approves-use-of-facial-recognition-in-banks/amp/); [Bangkok Post](https://www.bangkokpost.com/business/1851949/banks-allowed-to-use-facial-recognition)
- Krungsri was first with facial-recognition ID — [Bangkok Post](https://www.bangkokpost.com/business/news/1639748/krungsri-first-with-facial-recognition-id)
- Banks use biometrics against cybercrime (2025) — [FinTech Global](https://fintech.global/2025/03/26/how-thailands-banks-are-using-biometric-tech-to-fight-cybercrime/)
- KBTG's AINU named best verification technology 2024 — [The Asian Banker](https://theasianbanker.com/updates-and-articles/best-verification-technology-is-kbtg-ainu-2024)
- National Digital ID (NDID) verification route — [Bangkok Bank](https://www.bangkokbank.com/en/personal/digital-banking/ndid)
- Vendors: iApp Thai ID OCR (self-reported 98.13% char accuracy) — [iApp](https://iapp.co.th/blog/what-is-ekyc-complete-guide); Keesing, Didit also offer Thai coverage — [Didit](https://didit.me/de/solutions/countries/thailand/)
- Typhoon OCR (SCB 10X): open Thai/English VLM for document extraction, Markdown/HTML table output, v1.5 2B, Apache 2.0 for some releases; vendor-reported wins over GPT-4o/Gemini 2.5 Flash on Thai docs incl. financial reports, forms, handwriting — [arXiv 2601.14722](https://arxiv.org/html/2601.14722v1); [HF model card](https://huggingface.co/scb10x/typhoon-ocr1.5-2b)
- PDPA: biometric data is sensitive (s.26), needing explicit consent; PDPC draft sector guidance covers face/fingerprint access control and CCTV analytics (notice, retention, access limits) — [HLC](https://hlc.com/en/publications/thailand-pdpc-consults-on-sectorspecific-pdpa-guidelines)

### Inferences
- Needs: OCR text-line and key-value/field annotation, document layout (tables, forms), Thai script with tone marks and Thai/Arabic digits, ID-card field templates, synthetic document generation, PII masking in annotation UI, on-prem/VPC deployment and audit logs (PDPA, bank policy), spoof/presentation-attack datasets for liveness, VLM fine-tuning data export (image-to-Markdown/JSON).

### Gaps
- Comarch's claim that biometric verification is mandatory over THB 50,000 is unverified. No sourced Krungthai/Bangkok Bank cheque-processing initiatives found. Exact current BoT eKYC notification text not retrieved.

## 3. Insurance (claims)

### Takeaway
Thai motor insurance AI is real but mostly pre-inspection/photo triage; OIC issued AI governance guidance in 2025.

### Cited Findings
- KBTG + Muang Thai Insurance AI vehicle inspection auto-marks damage and routes to human second check; image-quality model filters bad photos — [Techsauce](https://techsauce.co/en/pr-news/kbtg-teams-with-muang-thai-insurance-in-developing-insurtech-an-ai-based-vehicle-inspection-a-thai-first); [Google Cloud](https://cloud.google.com/blog/products/ai-machine-learning/identifying-vehicle-damage-effectively-with-explainable-ai)
- CamCom + ERGO Insurance Thailand AI car inspection partnership — [CamCom](https://camcom.ai/camcom-ergo-insurance-thailand-partnership)
- Pipeline paper on Thai nationwide motor claims — [arXiv 2603.18508](https://arxiv.org/abs/2603.18508)
- OIC "AI Governance Guidelines 2025" (reported in search summary; primary document not read) — see [arXiv listing context](https://arxiv.org/abs/2603.18508) is NOT the source; treat as unverified.

### Inferences
- Needs: part-level segmentation plus damage severity attributes, image-quality classification, multi-image per claim grouping, explainability overlays, human-in-the-loop review queue, cost-estimation field linkage.

### Gaps
- No named insurer with full claims-settlement automation. OIC guideline primary source not found.

## 4. Retail

### Takeaway
Thai retail CV evidence is dated; large retailers mostly announce cloud/AI partnerships.

### Cited Findings
- 7-Eleven Thailand: face recognition and behavior analytics in 11,000 stores (2018, Remark) — [Retail Insight Network](https://www.retail-insight-network.com/news/facial-recognition-introduced-11000-thai-7-eleven-stores/)
- Lotus's opened an employee-free store with True Digital (2023) — [IoT M2M Council](https://www.iotm2mcouncil.org/iot-library/news/smart-retail-news/lotus-opens-thailands-first-autonomous-store/)
- CP Axtra partners with Tencent Cloud and Alibaba Cloud on AI — [Tirto](https://tirto.id/cp-axtra-unveils-digital-transformation-vision-and-partners-with-tencent-cloud-to-power-ai-driven-retail-tech-hgTN)
- Guardforce AI: CCTV analytics plus RFID in Thai retail — [Yahoo Finance](https://finance.yahoo.com/news/guardforce-ai-extends-thailand-retail-102050867.html)

### Inferences
- Needs: dense small-object detection (SKU), fine-grained classification with few examples per SKU, planogram compliance, product-embedding/retrieval, frequent catalog updates, face-blur privacy for PDPA.

### Gaps
- No confirmed Thai shelf-analytics deployment.

## 5. Logistics

### Takeaway
Little public evidence of Thai carrier OCR specifics; Kerry has automated sorting.

### Cited Findings
- Kerry Express "Smart Sorting" and "Digital Mapping" at Bangna (2023), OCR not explicitly described — [Kerry](https://th.kerryexpress.com/th/news/271979/fasttechsmartsorting-2)
- Prime Vision Address Vision: printed/handwritten address OCR for parcel sorting — [Prime Vision](https://primevision.com/address-vision-simplifies-and-expedites-ocr-implementation-for-postal-and-parcel-sorting-operations/)
- Thailand Post uses Shipsy platform — [Shipsy](https://thaipost.app.shipsy.ai/)

### Inferences
- Needs: Thai address OCR (handwritten, mixed Thai/English), label key-value fields, barcode/DM, damage classification, pallet counting (dense detection/counting), video-based tracking labels.

### Gaps
- No sourced Flash/Thailand Post OCR details; no pallet-counting or damage sources.

## 6. Agriculture

### Takeaway
Durian grading is the standout Thai use case; crop disease evidence not found.

### Cited Findings
- ARDA "Durian CT-scan" AI for ripeness and seed-boring worms, ~3 s per fruit, claimed 95% (government event page) — [Thailand.go.th](https://thailand.go.th/event-detail/D5-WP3-PRD2-2)
- Thailand uses AI to boost durian export quality — [VnExpress](https://e.vnexpress.net/news/tech/tech-news/thailand-uses-ai-to-boost-durian-export-quality-5077751.html); [AWS](https://resources.awscloud.com/together-we-innovate-manufacturing-edition/automating-durian-grading-and-inspection-with-computer-vision)
- Real-time sizing/grading of Thai export fruit, up to 93.33% size grading accuracy — [AgriEngineering/MDPI](https://www.mdpi.com/2624-7402/7/11/377)
- Durian ripeness via tapping sound (audio, KMITL) — [KMITL Expo](https://expo.kmitl.ac.th/en/innovations/6a94607625a24a6ccdc1e753)

### Inferences
- Needs: multimodal data (X-ray/CT, audio, RGB), classification with fine grade classes, small datasets, outdoor-variability augmentation, edge devices on sorting lines, drone/orthomosaic tiling for disease.

### Gaps
- No Thai rice/cassava disease sources found.

## 7. Healthcare

### Takeaway
Siriraj/Perceptra Inspectra CXR is the flagship; AI diagnostics are regulated as medical devices by Thai FDA, with UDI for SaMD from 20 June 2026.

### Cited Findings
- Inspectra CXR with Siriraj, trained on >1.9M CXRs, in use since 2019, >95% accuracy claim — [Siriraj](https://www2.si.mahidol.ac.th/en/news-events/siriraj-develops-ai-technology-for-medical-imaging-with-over-95-accuracy/); [KMUTT](https://en-ripo.kmutt.ac.th/research_highlights/inspectracxr/); [Perceptra](https://perceptra.tech/resources/perceptra-siriraj-cxr-mou-2019/)
- Siriraj YOLO for centroblast counting — [AAP](https://www.aap.com.au/aapreleases/cision20240804ae76302/)
- Thai FDA SaMD guidance (classification, registration, modification); UDI labeling for SaMD classes 2-4 from 20 June 2026 — [Tilleke](https://www.tilleke.com/insights/thailand-introduces-udi-labeling-requirements-for-software-as-a-medical-device/41/); [OpenGov Asia](https://opengovasia.com/thailand-ensuring-ai-medical-devices-align-with-international-standards/)

### Inferences
- Needs: DICOM ingest, 3D volume/slice labeling, windowing, expert-reviewer workflows with inter-rater agreement, de-identification, audit trail and model/dataset versioning (supports regulatory file), on-prem hosting. A general platform should position as training-data tooling, not as a medical device itself.

### Gaps
- Inspectra Thai FDA registration unconfirmed; national benefit package inclusion unconfirmed.

## 8. Construction

### Takeaway
Only the TNS/Nippon Steel pilot found; PPE and worker-state recognition is the use case.

### Cited Findings
- See TNS pilot above — [JETRO](https://www.jetro.go.jp/ext_images/_News/announcement/2021/d38074f8efc798ae/NIPPONSTEELENGINEERING_en.pdf)
- Thai AI-camera helmet detection (motorcycle) accuracy varied 73.7% to 89.5% by installation point — [Thai Journal](https://ph01.tci-thaijo.org/index.php/lej/article/view/265965)

### Inferences
- Needs: camera-angle diversity, small persons, PPE attribute labels, pose/action labels, video tracking, edge NVR integration, alert rules.

### Gaps
- No Thai labor regulation on AI safety monitoring found.

## 9. Energy and utilities

### Takeaway
PEA-Huawei AI substations and EGAT drone work exist; MEA not found.

### Cited Findings
- PEA with Huawei: AI substations, optical-visual linkage, auto meter reading, oil-leak warning — [Digital Terminal](https://digitalterminal.in/tech-companies/huawei-partners-with-pea-to-introduce-next-gen-intelligent-ai-powered-substations-in-thailand); [Huawei](https://e.huawei.com/eu/case-studies/solutions/digital-site/2025-provincial-electricity-authority)
- Terra Drone power line inspection for EGAT (~1 cm GSD, tree-trimming report) — [Geoconnexion](https://geoconnexion.com/news/terra-drone-optimizes-long-distance-power-line-inspection)
- AeroSky (PTTEP) drone services; Siemens Aerosophia grid inspection — [Kaohoon](https://kaohoon.com/?p=448159); [Siemens](https://www.siemens.com/th-th/products/aerosophia-power-grid-inspections-solution/)
- PEA smart meter AMI (2021, Moxa) — [Moxa](https://moxa.com.cn/Moxa/media/Resources/Case-Studies/PEA-Italthai-Moxa-SuccessStory-2021-chs_1.pdf)

### Inferences
- Needs: dial/digit meter OCR, tiny-defect detection on large aerial images, thermal imagery, geotagged data, rare-fault anomaly handling, edge on drones/substation gateways.

### Gaps
- No MEA data.

## 10. Smart city / government

### Takeaway
Bangkok scaled AI plate-reading enforcement cameras (6 to 27) and adaptive signals; most of ~60,000 cameras cannot support AI.

### Cited Findings
- AI CCTV reads plates and matches Department of Land Transport database — [Vietnam News/AsiaNews](https://vietnamnews.vn/life-style/1655072/don-t-stop-here-ai-cameras-set-to-catch-traffic-violators-in-thailand.html)
- 27 AI cameras for New Year 2025 (up from 6) — [Pattaya Mail](https://www.pattayamail.com/thailandnews/bangkok-ensures-safety-for-new-year-2025-enhanced-security-measures-and-traffic-management-with-advanced-technology-485133)
- Motorcycle footpath enforcement, THB 2,000 fine — [Nation](https://www.nationthailand.com/thailand/general/40028763)
- Adaptive signals at 74 intersections; most BMA cameras unusable for AI — [Smart Cities World](https://www.smartcitiesworld.net/news/bangkok-to-deploy-ai-based-traffic-prediction-technology-8455) (single-site claim)
- Toyota Mobility Foundation / Waycare traffic AI in Bangkok — [Rekor](https://www.rekor.ai/post/toyota-mobility-foundation-works-with-rekor-subsidiary-waycare-technologies-to-improve-traffic-congestion-and-safety-in-central-bangkok-using-artificial-intelligence)
- PDPC draft guidance on CCTV analytics — [HLC](https://hlc.com/en/publications/thailand-pdpc-consults-on-sectorspecific-pdpa-guidelines)

### Inferences
- Needs: Thai license-plate OCR (province names, special plates), night/rain data, video tracking and violation-event labels, low-res/legacy camera robustness, edge boxes, privacy masking.

### Gaps
- No Thai court/PDPC ruling on public CCTV AI found.

## Cross-sector platform requirement summary (inference)
Thai-script OCR and layout labeling; anomaly detection with few defects; video/tracking; DICOM/3D/point cloud; edge export (ONNX/TensorRT/PLC); on-prem/VPC and PII masking for PDPA; audit trails; VLM/OCR fine-tune export; human review queues.
