# LabelDesk go-to-market positioning and differentiation (Thailand/SEA)

Note: search tool returned summaries, not fetched pages; figures are as reported by those results. Evidence is thin in several areas (see Gaps).

## 1. Market size and trends for CV in Thailand/SEA

### Takeaway
No dedicated Thailand computer-vision market figure was found; adjacent segment estimates exist but disagree in scope. Adoption is early and talent-constrained, which favors tools that lower ML skill needs.

### Cited Findings
- Thailand AI inspection market ~USD 430.2M in 2025, to ~USD 2,074M by 2030 (25.2% CAGR) — [MarketsandMarkets](https://www.marketsandmarkets.com/Market-Reports/geography/ai-inspection-market/Thailand) (vendor research firm, treat cautiously)
- Thailand industrial machine vision ~USD 87.32M (2024), 7.24% CAGR 2025-2032 — [Data Bridge](https://www.databridgemarketresearch.com/nucleus/thailand-industrial-machine-vision-market); the same publisher's 3D figure (USD 70.61B) is implausible, likely mislabeled — [Data Bridge](https://www.databridgemarketresearch.com/nucleus/thailand-3-dimesional-machine-vision-market)
- Fewer than 20% of ~600 surveyed Thai organisations had adopted AI at organisation level in 2024; NECTEC cites weak domestic tech, limited data access, skills shortage — [Asia News Network](https://asianews.network/?p=292796)
- AWS-Strand: AI use 43% of Thai businesses but 74% at basic level; 56% cite digital talent shortage; readiness startups 47%, large enterprises 24%, SMEs 17% — [Nation Thailand](https://www.nationthailand.com/business/40068656) (conflicts with the <20% figure above due to different definitions)
- FTI poll: 48% of executives use AI in some processes; manufacturing/supply chain have room to grow; barriers are skills, funding, usable data — [Pattaya Mail](https://www.pattayamail.com/latestnews/news/ai-set-to-reshape-thailands-economy-within-five-years-fti-poll-finds-567715)

### Inferences
- Demand is real but immature; "no ML team needed" is a valid wedge for manufacturers and SMEs.

### Gaps
- No credible Thailand/SEA data-annotation or CV-platform market size found.

## 2. Buyer pain points: PDPA, Thai OCR, on-prem, cost, talent

### Takeaway
PDPA treats biometrics as sensitive data and constrains overseas processing, supporting a local/on-prem story; talent shortage is the most consistently cited barrier.

### Cited Findings
- Biometric data is sensitive under PDPA (explicit consent, strict access control); overseas cloud or third-party AI providers must follow cross-border transfer rules; PDPC cross-border notifications effective 24 March 2024 — [Tilleke & Gibbins](https://www.tilleke.com/insights/thailands-regulations-for-cross-border-personal-data-transfer-come-into-force/24/), [Pertama Partners](https://www.pertamapartners.com/insights/thailand-pdpa-ai-data-protection-draft-ai-law)
- Bank of Thailand AI Risk Management Guidelines for financial providers released 12 Sept 2025 — [Tilleke & Gibbins](https://www.tilleke.com/insights/thailand-insurance-industry-ai-and-privacy-regulatory-updates/25/) (text on data residency not verified)
- PDPC has issued personal data protection guidelines for AI systems — [Tilleke & Gibbins](https://www.tilleke.com/insights/thailand-issues-personal-data-protection-guidelines-for-ai-systems)
- Thai talent shortage cited by ETDA/NSTDA survey (3,758 approached, 580 responded), PwC, AWS-Strand — [Asia News Network](https://asianews.network/thailands-ai-moment-ambition-agents-and-a-skills-deficit/), [Nation Thailand](https://www.nationthailand.com/business/40068656)

### Inferences
- Face/person CCTV analytics is the most PDPA-sensitive use case; on-prem/edge is a compliance feature, not just preference.
- Thai OCR is already served by local players and open models (see section 3); LabelDesk should not lead with generic OCR.

### Gaps
- No source found confirming a binding on-prem requirement for banks, factories or government; no evidence on cost sensitivity specific to Thai buyers.

## 3. Local Thai/regional competitors

### Takeaway
Thai-language document AI has clear incumbents; industrial/CCTV vision is served by regional vision-AI vendors and machine-vision incumbents through channel partners.

### Cited Findings
- iApp Technology (Bangkok): eKYC, speech, document OCR; lists banks, insurers, government agencies as customers; Thai bank-book OCR API; 2026 Thai document OCR benchmark whitepaper (vendor claims) — [iApp](https://iapp.co.th/), [benchmark](https://iapp.co.th/whitepapers/thai-document-ocr-benchmark-2026.pdf)
- Typhoon OCR: open VLM from SCB 10X for Thai/English documents — [arXiv](https://arxiv.org/html/2601.14722v1)
- Alflow: Thai document reading, claims ISO 27001/PDPA compliance, 98.5% accuracy (unverified, Product Hunt) — [Product Hunt](https://www.producthunt.com/products/alflow/reviews)
- Tapway (Malaysia) Vision AI sold in Thailand via Advantech, Appomax, S I Media; target 500 camera licenses in 12 months — [CRN Asia](https://www.crnasia.com/news/2025/distributor/vision-ai-software-developer-tapway-partners-three-thai-firm)
- Ailytics (Singapore): industrial CCTV safety analytics, US$7.4M Series A, 400+ deployments in 15 countries — [Thailand Business News](https://www.thailand-business-news.com/?p=336534)
- Machine vision incumbents: Cognex (Thai listing), MVTec partner SP Vision Technology, Allied Vision via Dynatech; Midea Chonburi AI machine vision QC — [MVTec](https://www.mvtec.com/company/news/article/new-certified-integration-partner-spvisiontechnology), [Huawei](https://www.huawei.com/en/media-center/multimedia/photos/midea-thai-qc-machine-vision)
- Roboflow: Public/Core/Enterprise tiers; Enterprise custom with reported SaaS/VPC/on-prem; Core price reported inconsistently ($79 vs $39/mo); credits $4-$6 — [PricingSaaS](https://pricingsaas.com/companies/roboflow), [Roboflow pricing](https://roboflow.com/pricing)

### Inferences
- Tapway/Ailytics show the channel-led, camera-license model is already being tried in Thailand; LabelDesk must differentiate on the build-your-own-model workflow.

### Gaps
- Sertis, Vulcan Coalition, Gosoft, Landing AI, V7, Encord Thai presence: not found. Thai bank/government CV vendors beyond iApp not identified.

## 4. Pricing, vertical vs horizontal, partnership channels

### Takeaway
Little direct regional evidence; the only concrete channel evidence is distributor/SI-led licensing per camera.

### Cited Findings
- Tapway sells through distributors/SIs with per-camera licenses — [CRN Asia](https://www.crnasia.com/news/2025/distributor/vision-ai-software-developer-tapway-partners-three-thai-firm)
- Roboflow recently cut/reshaped pricing (credits, streaming) in Jul-Oct 2026 — [usagepricing](https://www.usagepricing.com/blueprint/activity/roboflow-2026-10-04-core-price-cut-free-credits) (secondary, unconfirmed)

### Inferences
- THB-priced, per-camera or per-project licensing plus SI revenue share fits observed channels; a low Core-like tier plus on-prem annual license mirrors the Roboflow ladder at a local price.

### Gaps
- No evidence found on SEA SaaS pricing norms, vertical-vs-horizontal outcomes, or robot/NVR vendor partnerships (Hikvision, Dahua etc.). Needs further research.

## 5. Thai government programs

### Takeaway
BOI software promotion and depa funding exist, but specifics for AI were not confirmed.

### Cited Findings
- BOI consolidated software/digital platform/content into activity 5.10 (2021); March 2024 split into "development" and "improvement"; improvement not eligible for CIT exemption — [Tilleke](https://www.tilleke.com/insights/thailands-boi-revamps-promoted-digital-activities/), [BOI](https://www.boi.go.th/upload/digitalpromotion.pdf)
- depa AI/digital grants roadshow aimed at 15,600 businesses, applications closed 16 Jan 2026 — [Thailand.go.th](https://www.thailand.go.th/issue-focus-detail/depa-targets-15600-businesses-with-ai-and-digital-grants-to-boost-competitiveness-in-southern-thailand)
- depa Digital Transformation Fund / mini transformation voucher for SMEs — [depa](https://www.depa.or.th/en/digitalservice/digital-transformation-fund/goals-and-areas)

### Inferences
- Customers (SMEs) may offset LabelDesk cost via depa vouchers if LabelDesk is an accredited provider; LabelDesk itself may qualify for BOI development-category software promotion (needs adviser).

### Gaps
- NIA programs: nothing found. Current 2026 BOI/depa eligibility not verified.

## 6. Differentiation theses (hypotheses supported by the above)

1. Sovereign by design (on-prem/edge plus Thai-hosted SaaS, PDPA pack). Evidence: biometrics sensitive, cross-border rules, BOT AI guidelines. Strength: moderate; binding on-prem mandates unverified.
2. "No ML team" end-to-end for factories/SMEs (SAM 3.1 + VLM auto-label to deploy). Evidence: talent shortage 56%, <20% org adoption, manufacturing lagging. Strength: strong.
3. Channel-first through SIs, camera/NVR and automation distributors with per-camera licensing. Evidence: Tapway model, Midea-type deployments run through integrators. Strength: moderate; own partner evidence missing.
4. Thai-vertical packs (Thai-text-in-scene, factory QC, PPE/safety CCTV) rather than horizontal parity with Roboflow. Evidence: Ailytics/Tapway verticalize on CCTV; Thai OCR already crowded so avoid pure document OCR. Strength: weak-moderate; no direct vertical-vs-horizontal data.
5. Subsidy-aligned local procurement: THB invoicing, Thai support, depa-voucher and BOI-friendly packaging. Evidence: depa SME funds. Strength: weak; program specifics unverified.
