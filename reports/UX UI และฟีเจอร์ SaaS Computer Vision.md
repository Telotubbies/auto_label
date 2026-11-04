# ให้คนตรวจงาน AI และใช้กระจกเฉพาะ chrome

**คำตอบสั้น:** UX ของ LabelDesk ควรยึดหลักข้อเดียวกับที่งานวิจัย annotation ชี้มาตั้งแต่ปี 2016 คือ **ให้มนุษย์เป็นผู้ตรวจและแก้ผลของ SAM 3.1 / VLM ไม่ใช่ผู้วาดเอง** การให้คนยืนยันกล่องที่เครื่องเสนอลดเวลา annotation รวม 6–9 เท่า ([Papadopoulos et al. CVPR 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Papadopoulos_We_Dont_Need_CVPR_2016_paper.html)) และ data engine ของ SAM ลดเวลาต่อ mask จาก 34 เหลือ 14 วินาที ([Kirillov et al. ICCV 2023](https://arxiv.org/pdf/2304.02643)) LabelDesk v1 วางโครงนี้ไว้ถูกแล้ว ผลจาก auto-label ทุกชิ้นต้องผ่าน Review ก่อนเข้า Dataset และ prediction ที่ confidence ต่ำถูกดันขึ้นหัวคิว (§3.10 P5) ช่องว่างที่เหลือคือ "ความลึก" ของแต่ละจอ ได้แก่ click บวก/ลบใน Smart Polygon, กราฟ health ที่คลิกแล้วกรอง grid, confusion matrix ที่มี confidence slider และคลิก cell แล้วเห็นภาพ, หน้า event ของ CCTV ที่บอกเหตุผลของ trigger และมีสถานะ "reviewed" และการบอกความไม่แน่นอนของ VLM อย่างตรงไปตรงมา ส่วนภาพลักษณ์ที่ผู้ใช้ต้องการคือ "Liquid Glass" กับสีเข้มข้นแบบ Material 3 ซึ่งทำได้โดยไม่เสียความแม่นยำในการ label ถ้าใช้กฎ **"glass คือ chrome ไม่ใช่ content"** ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) Apple เองก็จำกัด Liquid Glass ไว้ที่ชั้น controls และ navigation ([Apple Newsroom](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)) และยังต้องลดความโปร่งใสลงระหว่าง beta หลังถูกวิจารณ์เรื่องการอ่านออก ([PhoneArena](https://www.phonearena.com/news/liquid-glass-returns-to-ios-26-toned-down-but-with-original-vision_id172532)) สีควรสร้างจาก seed เดียวผ่าน HCT ของ `material-color-utilities` ([MCU README](https://chromium.googlesource.com/external/github.com/material-foundation/material-color-utilities/+/91da30d89e70c3dc9575ec71a1ebe8874d881f29/README.md)) แล้วแยก palette สีของ class (Okabe-Ito + Glasbey) ออกจากสีแบรนด์อย่างเด็ดขาด สำหรับเดโม สิ่งที่คุ้มที่สุดคือแก้ 5 จุดในตาราง "แก้ก่อนเดโม" ท้ายหัวข้อ 6 ส่วนที่เหลือเป็น roadmap

**วิธีอ่านตาราง:** Tier ใช้ **M** = must-have, **S** = should-have, **D** = differentiator สถานะเทียบกับของเดิมใช้ **มี [v1]** = ระบุใน `apps/README.md`, **ออกแบบ (§)** = อยู่ใน `docs/sdlc/10-labeldesk-v2-sdlc.md` §3.9/§3.10, **ขาด** = ทั้งสองเอกสารไม่มี, **ไม่ระบุ** = เอกสารไม่ได้พูดถึง ทีมควรเปิดโค้ดตรวจก่อนสรุปว่าขาดจริง คำแนะนำที่เป็นข้อสรุปของผู้เขียนเอง (ไม่มีแหล่งยืนยันตรง) ระบุว่า "(ข้อเสนอ)"

## 1. Editor ต้องออกแบบให้คนแก้ผลจาก SAM ไม่ใช่วาดใหม่

งานวิจัยสายนี้ตลอด 14 ปีขยับไปทางเดียวกัน คือย้ายงานของคนจาก "วาด" ไปเป็น "ยืนยัน" และ "แก้" งานของ Su, Deng และ Fei-Fei พบว่าการวาดกล่องยากและช้ากว่าการตอบคำถามแบบตัวเลือกอย่างมีนัยสำคัญ ([Su et al. HCOMP 2012](https://cs.stanford.edu/groups/vision/pdf/bbox_submission.pdf)) งานรุ่นหลังอ้างช่วงเวลาวาดกล่องไว้ที่ 7–42 วินาที ([Russakovsky et al. CVPR 2015](https://ai.stanford.edu/~olga/papers/RussakovskyCVPR15.pdf)) การ click จุดสุดขอบ 4 จุด (extreme clicking) ใช้ราว **7 วินาทีต่อกล่อง เร็วกว่าการวาดราว 5 เท่า** โดยคุณภาพกล่องและผลของ detector เท่าเดิม ([Papadopoulos et al. ICCV 2017](https://openaccess.thecvf.com/content_iccv_2017/html/Papadopoulos_Extreme_Clicking_for_ICCV_2017_paper.html)) Fluid Annotation เริ่มจาก proposal ของ Mask R-CNN แล้วให้คนแก้ภาพทั้งภาพในรอบเดียว ใช้เวลาน้อยกว่า LabelMe ราว 3 เท่า แต่ผู้วิจัยรายงานด้วยว่า **ความเห็นไม่ตรงกันเรื่อง class คือแหล่งความคลาดเคลื่อนหลัก** และเครื่องมือ manual ยังให้ขอบที่แม่นกว่า ([Andriluka et al. ACM MM 2018](https://arxiv.org/abs/1806.07527)) ในยุค SAM เวลาต่อ mask ลดจาก 34 เหลือ 14 วินาที ซึ่งเร็วกว่า mask แบบ COCO 6.5 เท่า ([SAM paper](https://arxiv.org/pdf/2304.02643)) และงานด้านเกษตรปี 2026 วัดได้ 1.6 วินาทีต่อ mask ด้วย SAM 2 เทียบกับ 9.7 วินาทีด้วย polygon มือ แม้โดเมนจะต่างออกไป ([PMC12872900](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12872900/))

ผลต่อ LabelDesk มีสองข้อ ข้อแรกคือ flow ปัจจุบันเดินถูกทาง auto-label ไม่เคยเขียนลง Dataset โดยตรงและส่งเข้า Review เสมอ (§3.10 P5) ข้อที่สองคือ class picker ควรได้งบมากกว่าที่คิด เพราะ Fluid Annotation ชี้ว่า class คือจุดที่ผิดบ่อยที่สุด จุดนี้ VLM 7B ช่วยได้ตรง ๆ โดยเสนอชื่อ class ให้แต่ละ mask (ข้อเสนอ) ส่วนเรื่องความล้า งานที่ศึกษา annotation 9 ล้านชิ้นบน AMT พบว่าคุณภาพของ worker "คงที่อย่างยิ่ง" ตลอดช่วงเวลา ([Hata et al. CSCW 2017](https://ar5iv.labs.arxiv.org/html/1609.04855)) ดังนั้นการแทรก gold item และวัด throughput มีหลักฐานรองรับมากกว่าการบังคับพัก

**Click-to-segment** กลายเป็นรูปแบบมาตรฐานไปแล้ว CVAT ใช้ click ซ้ายเป็นจุดบวก click ขวาเป็นจุดลบ และจบด้วย `N` ([CVAT AI tools](https://docs.cvat.ai/docs/manual/advanced/ai-tools)) Supervisely ใช้ box prompt ร่วมกับ Shift+click เป็นจุดลบ และกด Space เพื่อจบ เมื่อใช้ SAM 3 ยังวาดกล่องรอบตัวอย่างเดียวแล้วให้ระบบ mask วัตถุที่หน้าตาคล้ายกันทั้งภาพได้ ([Supervisely Smart Tool](https://docs.supervisely.com/labeling/labeling-tools/smart-tool.md)) Roboflow Smart Select ที่ใช้ SAM 3 (พ.ย. 2025) ตัดปุ่ม modifier ออกทั้งหมด click นอก mask คือขยาย click ใน mask คือหด ([Roboflow changelog](https://docs.roboflow.com/changelog/explore-by-month/november-2025/use-sam-3-in-smart-select)) Smart Polygon ของ v1 รับแค่ box prompt (มี GrabCut เป็น fallback) ตาม `apps/README.md` จึงยังขาดชั้น refine ด้วย click ซึ่งเป็นตัวที่ทำให้ "แก้" ได้จริง

ด้าน **hotkey** ผู้ใช้ที่ย้ายมาจาก Roboflow จะคาดหวังชุดของ Roboflow คือ `b` box, `p` polygon, `s` smart polygon, `d` select, `n` null, ลูกศรซ้าย/ขวาเปลี่ยนภาพ, `0` = fit, `1` = 100%, `a`/`r` สำหรับ approve/reject ในโหมด review ([Roboflow shortcuts](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)) CVAT ให้ผู้ใช้ remap shortcut เองได้ ([CVAT changelog](https://www.cvat.ai/resources/changelog/keyboard-shortcut-customization)) และมี object list พร้อม Lock `L`, Occluded `Q`, z-order และ Propagate `Ctrl+B` ไปยัง N เฟรม รวมถึงการปรับ brightness/contrast/gamma ที่มีผลเฉพาะการแสดงผล ([CVAT editor](https://docs.cvat.ai/docs/annotation/annotation-editor/_print/))

ด้าน **performance** v1 ใช้ react-konva อยู่แล้ว Konva แนะนำให้แยกชั้น static ออกจากชั้นที่เปลี่ยนบ่อย แต่ให้มีจำนวน layer น้อย เพราะแต่ละ layer สร้างทั้ง scene canvas และ hit canvas ควรตั้ง `listening(false)` กับ node ที่ไม่ต้องรับ event และซ่อน node ที่อยู่นอก viewport ([Konva performance](https://konvajs.org/docs/posts/canvas-performance.html)) Labelbox พบว่าปรับ brightness ด้วย CSS `filter` บน canvas ซึ่งทำบน GPU "เร็วกว่ามาก" เมื่อเทียบกับ filter ของ Konva ที่วนทีละ pixel บน CPU ([Labelbox blog](https://labelbox.com/blog/case-study-image-labeling-with-javascript/)) Label Studio ยอมรับว่า browser ช้าลงเมื่อมี polygon ที่ pre-label ไว้จำนวนมาก ([Label Studio #4026](https://github.com/heartexlabs/label-studio/issues/4026)) ข้อนี้สำคัญกับ LabelDesk โดยตรง เพราะ SAM 3.1 text prompt ("all screws") สร้างได้หลายร้อย polygon ในภาพเดียว

| ฟีเจอร์ editor | Tier | สถานะ | หลักฐานและข้อแนะนำ |
| --- | --- | --- | --- |
| Box, polygon, undo/redo, autosave, approve/reject, shortcuts | M | มี [v1] | ปรับ hotkey ให้ตรงชุด Roboflow ([Roboflow](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)) |
| Remap shortcut + cheat sheet ใน Help | S | ไม่ระบุ | CVAT ([changelog](https://www.cvat.ai/resources/changelog/keyboard-shortcut-customization)); Sama รวม shortcut ไว้ในเมนู Help ([Sama](https://docs.sama.com/brightness-and-contrast-updated)) |
| Smart Polygon: click บวก/ลบ, live preview, Enter ยืนยัน, Esc ยกเลิก | M | บางส่วน (มีแค่ box prompt) | CVAT ([AI tools](https://docs.cvat.ai/docs/manual/advanced/ai-tools)); Roboflow ใช้ตำแหน่ง click แทน modifier ([changelog](https://docs.roboflow.com/changelog/explore-by-month/november-2025/use-sam-3-in-smart-select)) |
| ปรับความละเอียด polygon ตอนแปลงจาก mask | S | บางส่วน (ε คงที่ 0.4% ใน P5) | CVAT มีตัวเลือกจำนวนจุด approximation ([AI tools](https://docs.cvat.ai/docs/manual/advanced/ai-tools)) ควรเปิดเป็น slider |
| SAM 3.1 text prompt / "ตัวอย่างเดียว หาทั้งภาพ" ภายใน editor | D | บางส่วน (มีใน Auto Label dialog) | Supervisely ([Smart Tool](https://docs.supervisely.com/labeling/labeling-tools/smart-tool.md)) |
| VLM เสนอชื่อ class ให้ mask | D | ขาด | class คือจุดที่ผิดบ่อยที่สุด ([Fluid Annotation](https://arxiv.org/abs/1806.07527)) |
| Class picker ที่มีช่องค้นหา + hotkey ตัวเลข + สีคงที่ | M | บางส่วน (มี relabel) | Supervisely กำหนด hotkey และสีให้ class ตอนสร้าง ([Supervisely](https://docs.supervisely.com/labeling/labeling-tools/smart-tool.md)) |
| Object list: hide/lock/occluded/z-order | M | ไม่ระบุ | CVAT ([editor](https://docs.cvat.ai/docs/annotation/annotation-editor/_print/)) |
| Brightness/contrast/gamma เฉพาะการแสดงผล (CSS filter) | M | ไม่ระบุ | CVAT; ทำผ่าน GPU ได้เร็ว ([Labelbox](https://labelbox.com/blog/case-study-image-labeling-with-javascript/)) |
| Review mode แบบ verify อย่างเดียว (`a`/`r`) | S | บางส่วน (มี approve/reject) | การให้คนยืนยันเร็วกว่าวาด 6–9 เท่า ([CVPR 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Papadopoulos_We_Dont_Need_CVPR_2016_paper.html)) |
| Extreme-click box (4 จุด แล้วส่งต่อเป็น SAM seed) | D | ขาด | 7 วินาทีต่อกล่อง ([ICCV 2017](https://openaccess.thecvf.com/content_iccv_2017/html/Papadopoulos_Extreme_Clicking_for_ICCV_2017_paper.html)) |
| Konva 3 ชั้น (image / shapes / preview), list แบบ virtualized เมื่อเกิน ~100 object | M | ไม่ระบุ | ([Konva](https://konvajs.org/docs/posts/canvas-performance.html)); ตัวเลข 100 เป็นข้อเสนอ |
| Mask เป็น bitmap ชั้นเดียว, culling, R-tree เมื่อเกิน ~500 shape | S | ขาด | (ข้อเสนอ) ไม่พบ benchmark อิสระ |
| Tile/pyramid สำหรับภาพเกิน ~8k px (PCB/IC defect) | D | ขาด | OpenSeadragon ([package](https://openapps.pro/packages/openseadragon)) |
| Video: keyframe + interpolation, SAM track ไปข้างหน้า N เฟรม | M ถ้ารองรับวิดีโอ | ขาด (editor รองรับแค่ภาพ) | V7 ([interpolation](https://docs.v7labs.com/docs/use-interpolation-in-video-and-dicom)); Encord `Shift+T` ค่าเริ่ม 30 เฟรม ([Encord](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-sam2-video-tracking)) |
| Gold item + วัด throughput แทนการบังคับพัก | S | ขาด | ([Hata 2017](https://ar5iv.labs.arxiv.org/html/1609.04855)) |

ยังมีจุดที่ไม่รู้แน่ชัด ไม่มี vendor รายใดเผยตัวเลข latency ของ click-to-mask และไม่พบงาน CHI/UIST ปี 2024–2026 ที่ทดลองแบบควบคุมกับ UI annotation ยุค SAM ตัวเลขด้านความเร็วข้างต้นจึงมาจากงานของ Meta และงานโดเมนเฉพาะเท่านั้น

## 2. ทุกจอเรียงตาม lifecycle และทุกกราฟต้องคลิกต่อไปที่ภาพได้

ทุกแพลตฟอร์มใช้แกน lifecycle แบบเดียวกัน Ultralytics Platform เขียน flow ไว้ว่า Upload → Annotate → Train → Export → Deploy ([Ultralytics Platform](https://docs.ultralytics.com/platform)) LandingLens ใช้ 7 ขั้นตั้งแต่สร้าง project จนถึง deploy และวนกลับมาแก้ dataset ([LandingLens workflow](https://docs.landing.ai/landinglens/landinglens-workflow)) Edge Impulse เรียง sidebar ตั้งแต่ Data acquisition จนถึง Deployment ([EON Tuner docs](https://docs.edgeimpulse.com/docs/edge-impulse-studio/eon-tuner)) sidebar ของ project ใน LabelDesk จึงควรเรียงเป็น Upload → Annotate → Dataset → Health → Versions → Train/Models → Evaluate → Playground → Deploy → Streams ส่วน workspace switcher ที่ v1 มีอยู่แล้วก็วางตรงตำแหน่งเดียวกับที่ Ultralytics วางไว้ในเมนู account ([Ultralytics](https://docs.ultralytics.com/platform))

**Onboarding:** checklist อย่างเดียวไม่พอ benchmark ของ Userpilot จาก 188 บริษัทพบอัตราทำ checklist จบเฉลี่ยแค่ **19.2%** และเวลาจนผู้ใช้เห็นคุณค่า (time-to-value) เฉลี่ย 1 วัน 12 ชั่วโมง ([Userpilot](https://userpilot.com/saas-product-metrics/)) PAIR แนะนำให้ onboard เป็นขั้น บอกตั้งแต่ใช้ครั้งแรกว่าระบบทำอะไรได้และไม่ได้ และแนะนำฟีเจอร์ตอนผู้ใช้กำลังจะใช้ ([PAIR Mental Models](https://pair.withgoogle.com/chapter/mental-models/)) Roboflow ใช้การ fork dataset จาก Universe เป็นทางลัด ([Roboflow fork](https://docs.roboflow.com/datasets/universe/universe/fork-a-universe-dataset)) v1 seed ภาพ PPE ไว้ 40 ภาพ (`apps/README.md`) ซึ่งเป็นจุดเริ่มที่ดี ถ้าเพิ่มโมเดลที่เทรนเสร็จแล้วกับ stream ตัวอย่างที่เปิดวิดีโอวนไว้ ผู้ชมเดโมจะเห็นทั้ง loop ได้ภายในนาทีแรก (ข้อเสนอ) Ultralytics เป็นตัวอย่างที่ไม่ควรทำตาม เพราะให้เลือก data region ตอน onboarding แล้วเปลี่ยนภายหลังไม่ได้ ([Ultralytics](https://docs.ultralytics.com/platform))

**Upload:** Roboflow ข้ามภาพซ้ำเพื่อกันข้อมูลรั่วระหว่าง split ([Manage images](https://docs.roboflow.com/datasets/manage/manage-images.md)) แต่การข้ามแบบเงียบ ๆ ทำให้มีกระทู้แบบ "อัปโหลด 936 ภาพ บันทึกได้แค่ 120" ([Roboflow forum](https://discuss.roboflow.com/t/i-upload-936-images-but-only-120-get-save-into-roboflow/3188)) v1 dedupe ด้วย SHA-256 ทั้งฝั่ง client และ server แล้ว สิ่งที่ต้องเพิ่มคือสรุปหลังอัปโหลด "อัปโหลด N / ซ้ำ M / ล้มเหลว K" พร้อมเหตุผลรายไฟล์

**Dataset grid และ Health:** Labelbox มี filter ค้นหาด้วยภาษาธรรมชาติที่ใช้ embedding ของ CLIP-ViT-B-32 และ slider ปรับช่วง score ([Labelbox NL search](https://docs.labelbox.com/docs/natural-language-search)) รวมถึง similarity search แบบ "ภาพคล้ายกัน" ([Labelbox similarity](https://docs.labelbox.com/docs/similarity)) Health Check ของ Roboflow ทำ heatmap ให้ลากคลุมพื้นที่แล้วแสดงภาพที่ตรงกัน และ histogram จำนวน object ให้คลิกแท่งแล้วแสดงภาพในแท่งนั้น พร้อมคำแนะนำในตัว ([Roboflow Health Check](https://docs.roboflow.com/datasets/dataset-health-check)) v1 มีกราฟชุดเดียวกันแล้ว (class balance, histogram, heatmap) แต่เอกสารไม่ได้บอกว่าคลิกได้ ขณะที่ §3.10 P2 ออกแบบ warning ที่ลิงก์ไปยัง filter และ editor ("12 images are very blurry (link to filter)") และยึดหลักว่า "เสนอเท่านั้น ไม่ apply เงียบ ๆ" ซึ่งตรงกับ PAIR และ HAX

**Versions และ Training:** wizard ของ Roboflow เรียงเป็น split → preprocessing → augmentation → output multiplier → Generate ([Roboflow versions](https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version)) v1 มีครบทุกขั้น และ §3.10 P3 เพิ่ม `version_hash` และ `recipe.json` ซึ่งควรแสดงบนหน้า version ด้วย Ultralytics เปิดให้แก้ YAML ใน "Advanced Settings" เพื่อ override argument ใดก็ได้ แสดง **live cost estimate** และ stream loss curve แบบ real-time ([Ultralytics](https://docs.ultralytics.com/platform)) LandingLens แยกเป็น Fast Training กับ Custom Training ([LandingLens](https://docs.landing.ai/landinglens/custom-training)) แผนใน §3.9 (family card → variant chip → hyperparameter และ card ที่ใช้ไม่ได้แสดงเหตุผล) กับ stepper 11 ขั้นใน §P4 ตรงกับแนวนี้ ที่ยังขาดคือ preset "Fast" ปุ่มเดียว ช่อง Advanced JSON/YAML และตัวประมาณเวลาและ VRAM ก่อนกดเริ่ม

**Evaluation และ leaderboard:** หน้า evaluate ของ Roboflow มี confusion matrix ที่ **confidence slider เปลี่ยน matrix, precision และ recall ได้ทันที** โดยค่าเริ่มคือ threshold ที่คำนวณว่าดีที่สุด ([Roboflow Evaluate](https://docs.roboflow.com/models/evaluate/evaluate-trained-models)) และตั้งแต่ ก.ค. 2025 มี **Automated Model Improvement Recommendations** ที่ดึงมาจาก matrix ([Roboflow changelog](https://docs.roboflow.com/reference/changelog/changelog/july-2025/automated-model-improvement-recommendations)) §P4 ขั้น 8 คำนวณข้อมูลครบแล้ว (matrix, PR curve, F1-vs-confidence, threshold ที่ให้ F1 สูงสุด, gallery ภาพที่แย่ที่สุด) และ leaderboard ติดป้าย "not directly comparable" เมื่อโมเดลเทรนบนคนละ version ซึ่งละเอียดกว่าคู่แข่งที่ตรวจสอบมา ส่วนที่ต้องเติมคือชั้น interaction ได้แก่ slider ที่ขับ matrix, การคลิก cell แล้วเปิดภาพ GT เทียบ prediction และคำแนะนำ "แก้อะไรต่อ" ที่ลิงก์กลับไปยัง P2/P3

**Playground และ Deploy:** Ultralytics ให้ทดสอบในเบราว์เซอร์ได้สามทาง คือภาพของผู้ใช้ webcam และภาพตัวอย่าง มีแท็บ Export 17 format และ endpoint ที่ scale-to-zero เป็นค่าเริ่ม ซึ่ง cold start อาจนานถึง 1 นาที ([Ultralytics](https://docs.ultralytics.com/platform)) Playground ใน §3.9 (สูงสุด 3 โมเดลเทียบกัน, latency, ช่องถาม VLM, slider ที่กรองซ้ำฝั่ง client โดยไม่ต้อง run ใหม่) แข็งแรงกว่าของ Ultralytics ในแง่การเทียบ แต่ขาด webcam, แผงตัวอย่างโค้ด และสถานะ "กำลังโหลดโมเดล / ถูก evict" ซึ่งจำเป็น เพราะ GPU scheduler ของ LabelDesk evict โมเดลแบบ LRU และพัก vLLM ระหว่างเทรน (§3.6)

| จอ / ฟีเจอร์ | Tier | สถานะ | หลักฐานและข้อแนะนำ |
| --- | --- | --- | --- |
| Sidebar เรียงตาม lifecycle + workspace switcher | M | บางส่วน (มี switcher [v1]; ลำดับ sidebar ไม่ระบุ) | ([Ultralytics](https://docs.ultralytics.com/platform); [LandingLens](https://docs.landing.ai/landinglens/landinglens-workflow)) |
| Sample project ที่มีโมเดลเทรนแล้ว + stream ตัวอย่าง | S | บางส่วน (seed 40 ภาพ PPE) | checklist ทำจบแค่ 19.2% ([Userpilot](https://userpilot.com/saas-product-metrics/)) |
| Activity log ราย project | S | บางส่วน (audit log ระดับ workspace [v1]) | ([Ultralytics](https://docs.ultralytics.com/platform)) |
| Command palette Ctrl/Cmd+K | S | ขาด | (ข้อเสนอ) เข้ากับแนว keyboard-first ของ editor |
| สรุปผลอัปโหลด N/M/K พร้อมเหตุผล | M | ขาด (มี dedupe [v1]) | ([Roboflow forum](https://discuss.roboflow.com/t/i-upload-936-images-but-only-120-get-save-into-roboflow/3188)) |
| Grid แบบ virtualized + filter + bulk action | M | มี [v1] | เก็บ filter ไว้ใน URL เพื่อแชร์ view (ข้อเสนอ) |
| ค้นหาภาษาธรรมชาติ / ภาพคล้ายกัน (CLIP) | D | ขาด | ([Labelbox](https://docs.labelbox.com/docs/natural-language-search)) |
| กราฟ health ที่คลิก/ลากแล้วกรอง grid | M | บางส่วน (มีกราฟ [v1]; ลิงก์ไป filter ออกแบบใน P2) | ([Roboflow Health](https://docs.roboflow.com/datasets/dataset-health-check)) |
| คำแนะนำจาก health ที่ไปเติมค่าในฟอร์ม P3/P4 ให้ | S | ออกแบบ (§P2) | ต้องแสดงที่มาของแต่ละคำแนะนำ |
| Version wizard + แสดง hash/recipe | M | มี [v1] + ออกแบบ (§P3) | ([Roboflow](https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version)) |
| Family card ที่ disable พร้อมเหตุผล | M | ออกแบบ (§3.9) | ตรงกับ anti-goal "ไม่มีโมเดลที่ fail เงียบ" (§1.3) |
| Preset Fast + Advanced YAML/JSON | S | ขาด | ([Ultralytics](https://docs.ultralytics.com/platform); [LandingLens](https://docs.landing.ai/landinglens/custom-training)) |
| ประมาณเวลา/VRAM ก่อนเริ่มเทรน | D | ขาด | Ultralytics แสดงค่าใช้จ่ายสด ([Ultralytics](https://docs.ultralytics.com/platform)) |
| Live chart + stepper ของ stage + ปุ่ม stop | M | มี [v1] + ออกแบบ (§P4) | |
| Confusion matrix ที่ใช้ slider + คลิก cell แล้วเห็นภาพ GT/pred | M | บางส่วน (คำนวณใน §P4 ขั้น 8 แต่ยังไม่มี interaction) | ([Roboflow Evaluate](https://docs.roboflow.com/models/evaluate/evaluate-trained-models)) |
| Metric ราย class (ไม่ใช่แค่ mAP รวม) | M | ออกแบบ (§P4 ขั้น 8) | HAX G2 ([Amershi et al.](https://doi.org/10.1145/3290605.3300233)) |
| Leaderboard: mAP + latency + ป้าย "not comparable" | S | ออกแบบ (§P4) | |
| คำแนะนำ "แก้อะไรต่อ" ที่สร้างจาก matrix | D | ขาด | Roboflow เพิ่งเพิ่มเมื่อ ก.ค. 2025 ([changelog](https://docs.roboflow.com/reference/changelog/changelog/july-2025/automated-model-improvement-recommendations)) |
| Playground: ภาพ/วิดีโอ, เทียบ 3 โมเดล, latency, ถาม VLM | M | ออกแบบ (§3.9) | |
| Playground: webcam + ภาพตัวอย่าง | S | ขาด | ([Ultralytics](https://docs.ultralytics.com/platform)) |
| สถานะ cold-start / evict / "GPU กำลังเทรน" | M | บางส่วน (badge ผู้ถือ GPU ใน header, §P4) | cold start นานถึง 1 นาที ([Ultralytics](https://docs.ultralytics.com/platform)) |
| แผงตัวอย่างโค้ด (curl/Python/JS) + API key | M | บางส่วน (API + key [v1]) | ไม่พบแหล่งยืนยัน layout ของ vendor รายใด |
| ปุ่ม Export TensorRT + badge family/variant | S | ออกแบบ (§3.9) | |

## 3. หน้า CCTV ตัดสินกันที่ชั้นคัดกรอง event ไม่ใช่ที่การวาด zone

การวาด zone มีรูปทรงเรขาคณิตง่าย ๆ ผลิตภัณฑ์จึงแข่งกันที่การคัดกรอง (triage) และการยืนยันว่า event เป็นของจริง หน้า Review ของ Frigate วาง item บน **timeline แนวตั้งคู่กับ grid ของ preview ความละเอียดต่ำ** แค่ hover ก็เล่น preview และ **ทำเครื่องหมายว่าดูแล้ว** item แบ่งความรุนแรงเป็นสองระดับ คือ Alert (ค่าเริ่มคือ person และ car) กับ Detection และกรองตาม label และ zone ที่กำหนดได้ ([Frigate Review](https://docs.frigate.video/configuration/review)) Verkada รองรับ line crossing แบบทิศเดียวหรือสองทิศได้สูงสุด 4 เส้น และนับเมื่อ **จุดกึ่งกลางขอบล่างของกล่อง** ข้ามเส้น ([Verkada](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts)) ส่วน Compound Alert จะยิงเมื่อ trigger กับ filter ที่เป็นข้อความ AI ตรงกันบนคนหรือรถคันเดียวกัน ([Verkada Compound Alerts](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts/compound-alerts)) Spot AI ตั้ง dwell time ได้ราย zone และรายช่วงเวลา ([Spot AI](https://www.spot.ai/blog/ai-video-analytics-loitering-detection)) NVIDIA VSS มีโหมด **Alert Verification** ที่ให้ VLM ยืนยันผลของ CV pipeline ([NVIDIA VSS](https://docs.nvidia.com/vss/vision-agent/agent-workflows/alert-verification)) และมี toggle ใน UI ให้แสดงเฉพาะ alert ที่ VLM ยืนยันแล้ว ([VSS UI](https://docs.nvidia.com/vss/system-components/user-interface)) Line Counter ของ Roboflow ให้เลือก anchor (เช่น CENTER) เพื่อลดการนับผิดจากวัตถุที่แค่เฉียดเส้น ([Roboflow Line Counter](https://docs.roboflow.com/workflows/blocks/blocks/video-processing/line-counter))

LabelDesk เลือกจุดตัดสินเป็น bottom-centre ของกล่องตรงกับ Verkada อยู่แล้ว (§3.5) ข้อนี้ควรเขียนบอกไว้ในตัวแก้ไข zone ด้วย เพราะทั้ง Verkada และ Roboflow เปิดเผยรายละเอียดนี้ต่อผู้ใช้ VLM rule ใน §3.5 ที่ถาม yes/no ทุก N วินาทีคือ "Real-Time VLM Alert" ตามศัพท์ของ NVIDIA ([VSS Real-Time Alerts](https://docs.nvidia.com/vss/vision-agent/agent-workflows/real-time-alerts)) ทางที่คุ้มกว่าและใช้ GPU น้อยกว่าคือให้ VLM ตรวจ event ที่ count/zone rule ยิงแล้วเท่านั้น และแสดงเป็น badge "VLM verified" (ข้อเสนอ ตามแนว Alert Verification) ปุ่ม "send to dataset" (§3.5, FR-8) คือจุดเด่นที่ไม่พบในผลิตภัณฑ์ CCTV ที่ตรวจสอบมา จึงควรวางให้เห็นชัดบนการ์ด event ทุกใบ และให้เลือกว่าจะส่งเป็น "hard negative" เมื่อ event เป็น false positive (ข้อเสนอ ไม่พบแหล่งที่ทำ flow นี้)

| ฟีเจอร์ CCTV | Tier | สถานะ | หลักฐานและข้อแนะนำ |
| --- | --- | --- | --- |
| รายการ stream พร้อมจุดสถานะ (live / reconnecting / paused-by-training) | M | ออกแบบ (§3.9, NFR-3, §3.6) | จุดสถานะต้องมีข้อความกำกับ ไม่ใช้สีอย่างเดียว (WCAG 1.4.1) และจุดต้องได้ 3:1 ([W3C 1.4.11](https://w3.org/WAI/WCAG22/Understanding/non-text-contrast)) |
| Live MJPEG + overlay | M | ออกแบบ (§3.5) | |
| Zone editor บนเฟรม + แสดงจุด anchor | M | บางส่วน (polygon zone; ไม่แสดง anchor) | ([Verkada](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts)) |
| Line crossing มีลูกศรทิศทาง | M | ขาด | ([Roboflow Line Counter](https://docs.roboflow.com/workflows/blocks/blocks/video-processing/line-counter)) |
| Event: snapshot + เหตุผลของ trigger (rule, zone, class, conf, track) | M | บางส่วน (`rule`, `summary`, `predictions` มีใน row) | HAX G11 ([Amershi et al.](https://doi.org/10.1145/3290605.3300233)) |
| กรอง event (กล้อง, class, zone, วันที่) + สถานะ reviewed | M | ขาด | ([Frigate](https://docs.frigate.video/configuration/review)) |
| แบ่ง Alert กับ Detection | S | ขาด | ([Frigate](https://docs.frigate.video/configuration/review)) |
| Dwell time + ตารางเวลา | S | บางส่วน ("count ≥ k for t s") | ([Spot AI](https://www.spot.ai/blog/ai-video-analytics-loitering-detection)) |
| Compound rule (trigger AND คำถาม VLM) | D | บางส่วน (VLM rule แยกเดี่ยว) | ([Verkada](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts/compound-alerts)) |
| Badge "VLM verified" + filter เฉพาะที่ยืนยันแล้ว | D | ขาด | ([NVIDIA VSS](https://docs.nvidia.com/vss/system-components/user-interface)) |
| Send to dataset (+ เลือกเป็น hard negative) | D | ออกแบบ (FR-8) | |

## 4. ความเชื่อใจ AI ต้องปรับให้ตรงความจริง ไม่ใช่ทำให้สูงที่สุด

Guidelines for Human-AI Interaction ของ Microsoft มี 18 ข้อ แบ่งเป็น 4 ช่วง ได้แก่ ตอนเริ่ม ระหว่างใช้ ตอนระบบผิด และระยะยาว ผู้เขียนเน้นว่าไม่ได้ตั้งใจให้ใช้เป็น checklist ([Amershi et al. CHI 2019](https://doi.org/10.1145/3290605.3300233); [MSR](https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/)) ข้อที่เกี่ยวกับเครื่องมือ ML โดยตรงคือ G1 บอกว่าระบบทำอะไรได้, G2 บอกว่าทำได้ดีแค่ไหน, G9 ทำให้แก้ได้ง่าย, G11 บอกเหตุผล และ G18 แจ้งเมื่อระบบเปลี่ยน (ถอดความจากเอกสาร ทีมควรตรวจถ้อยคำจริงที่ DOI) PAIR เตือนว่าถ้าตั้งความคาดหวังสูงเกินไป ผู้ใช้จะเชื่อเกิน ถ้าต่ำเกินไป ผู้ใช้จะไม่ใช้ ([PAIR guidebook](https://pair.withgoogle.com/chapter/mental-models/))

งานเชิงทดลองให้ข้อสรุปที่ไม่ตรงกับสัญชาตญาณ Vasconcelos et al. พบว่าคำอธิบายลดการพึ่ง AI เกินควรได้ **เฉพาะเมื่อคำอธิบายนั้นทำให้ตรวจสอบ AI ได้ง่ายขึ้น** ถ้าแค่แปะคำอธิบายเพิ่ม การพึ่ง AI เกินควรไม่ลดลง ([Vasconcelos et al. CSCW 2023](https://arxiv.org/pdf/2212.06823)) Zhang, Liao และ Bellamy พบว่า confidence score ช่วยปรับความเชื่อใจให้ตรงความจริงได้ แต่ local explanation ไม่ช่วย ([Zhang et al. FAT* 2020](https://arxiv.org/pdf/2001.02114)) งานปี 2026 แย้งว่าตัวเลข confidence อาจทำให้ผู้ใช้รับรู้ความน่าเชื่อถือได้ตรงขึ้น แต่ไม่ได้ช่วยให้เลือกทางอื่นได้ดีขึ้น ([Frontiers Psychology 2026](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2026.1967356/full)) และงานภาครัฐพบ "selective adherence" คือคนทำตามคำแนะนำของอัลกอริทึมเมื่อมันตรงกับอคติของตัวเอง ([Alon-Barkat & Busuioc](https://academic.oup.com/jpart/article/33/1/153/6524536))

สำหรับ CV เครื่องมือที่ทำให้ "ตรวจสอบง่ายขึ้น" ก็คือภาพ ได้แก่ overlay ของ mask, GT เทียบ prediction และ gallery ของ FP/FN ไม่ใช่ข้อความอธิบาย นี่คือเหตุผลที่การคลิก cell ใน confusion matrix แล้วเห็นภาพสำคัญกว่าการเพิ่มย่อหน้าอธิบาย การออกแบบ VLM ใน §3.4 ซื่อตรงอยู่แล้ว (VLM ไม่มี score ที่ calibrate จึงซ่อน slider) แต่ค่า `confidence = 0.5` ที่ใส่ให้ทุกกล่องจะไปปรากฏใน editor และ Review queue เหมือนตัวเลขจริง ทางแก้คือแสดง badge "VLM · ไม่มีค่า confidence" แทนตัวเลข (ข้อเสนอ) ทำนองเดียวกับที่ Encord ใส่ confidence คงที่ 99% ให้ label ที่มาจาก interpolation เพื่อแยกออกจากของคน ([Encord interpolation](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-interpolation)) Auto Label dialog ที่บอกล่วงหน้าว่ากล่องจะถูกแปลงเป็น polygon ด้วย SAM หรือเก็บเป็นกล่อง (§3.3) คือ G1 ที่ทำได้ถูกต้อง

| ฟีเจอร์ด้าน trust | Tier | สถานะ | หลักฐานและข้อแนะนำ |
| --- | --- | --- | --- |
| ทุก annotation แสดงที่มา (`source = model_ref`) ด้วยสีหรือขอบต่างจากของคน | M | บางส่วน (เก็บ `source` แล้ว §P5; UI ไม่ระบุ) | HAX G9 ([Amershi](https://doi.org/10.1145/3290605.3300233)) |
| Accept/reject ทีละชิ้นและทั้งชุด | M | มี [v1] (approve/reject all) | |
| Badge "ไม่มี confidence" สำหรับ VLM แทน 0.5 | M | ขาด | ([Zhang 2020](https://arxiv.org/pdf/2001.02114); [Encord](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-interpolation)) |
| Threshold ที่ปรับได้และแสดงค่าเริ่ม (F1-optimal) | M | ออกแบบ (§P5) | ([Roboflow](https://docs.roboflow.com/models/evaluate/evaluate-trained-models)) |
| แจ้ง "โมเดลเปลี่ยน" เมื่อ deploy version ใหม่ให้ API/stream | M | ขาด | HAX G18 |
| การ์ด "ข้อจำกัด" ของโมเดล: version ที่ใช้เทรน + class ที่อ่อน | S | บางส่วน (lineage ใน §P5) | PAIR Errors + Graceful Failure ([Buildo summary](https://www.buildo.com/blog-posts/what-we-learned-from-googles-people-ai-guidebook)) |
| Error ของ AI มีทางทำต่อด้วยมือเสมอ | M | บางส่วน (GrabCut fallback, VLM retry) | ([PAIR via Buildo](https://www.buildo.com/blog-posts/what-we-learned-from-googles-people-ai-guidebook)) |
| Audit แบบ blind: ซ่อน pre-label ในตัวอย่างสุ่ม + วัดอัตรายอมรับโดยไม่แก้ | D | ขาด | (ข้อเสนอ) ต่อยอดจาก [Vasconcelos 2023](https://arxiv.org/pdf/2212.06823) |

## 5. Accessibility ภาษาไทย และความเร็วที่ผู้ใช้รับรู้ เป็นงานพื้นฐานที่ต้องทำ

**WCAG 2.2** เป็น W3C Recommendation ตั้งแต่ 5 ต.ค. 2023 เกณฑ์ใหม่ระดับ AA กระทบเครื่องมือ annotation โดยตรงสามข้อ ([W3C](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)) ข้อแรกคือ 2.5.7 Dragging Movements ซึ่งบังคับให้ทุกการลากมีทางเลือกแบบ click เดียว ข้อที่สองคือ 2.5.8 ที่กำหนดเป้า pointer ขั้นต่ำ 24×24 CSS px ([WebAIM](https://webaim.org/standards/wcag/wcag22)) ข้อที่สามคือ 2.4.11 ที่ห้าม focus ถูกบังทั้งหมดโดย sticky header หรือ overlay ส่วน 1.4.11 กำหนดให้ control, สถานะ selected/focused และกราฟิกที่มีความหมาย (รวมถึงกราฟ) มี contrast 3:1 ([W3C 1.4.11](https://w3.org/WAI/WCAG22/Understanding/non-text-contrast)) tldraw ซึ่งเป็น canvas SDK ประกาศว่าผ่าน WCAG 2.2 AA พร้อมรองรับ screen reader และการใช้คีย์บอร์ดเลื่อนไปมาระหว่าง shape ([tldraw](https://tldraw.dev/features/composable-primitives/accessibility)) จึงพิสูจน์ได้ว่า canvas ทำให้ accessible ได้จริง ไม่พบ VPAT/ACR ของ vendor CV labeling รายใด ([accessible.org](https://accessible.org/vpat-requirements-checklist/)) แต่ผลการค้นที่ไม่พบไม่ได้แปลว่าไม่มีอยู่จริง

**ภาษาไทย:** W3C ระบุว่าภาษาไทย "เว้นวรรคเพื่อแยกวลี ไม่ใช่แยกคำ" สระผสมใช้ glyph ได้ถึง 4 ตัวบวกวรรณยุกต์ และล้อมพยัญชนะต้นได้สามด้าน ([W3C thai-lreq](https://www.w3.org/TR/thai-lreq/)) แต่เอกสารนี้ยังเป็น draft และหัวข้อ line height (§8.4) ยังว่างอยู่ ค่า line-height ที่แนะนำด้านล่างจึงเป็นข้อเสนอ ปัญหาสระหรือวรรณยุกต์ถูกตัดมักมาจาก vertical metrics ของ font ไม่ใช่จาก CSS อย่างเดียว ([RightFont: Pattaya](https://rightfontapp.com/family/pattaya)) `Intl.Segmenter` เป็น Baseline แล้วและตัดคำไทยได้ (สวัสดีครับ → สวัสดี + ครับ) ([web.dev](https://web.dev/blog/intl-segmenter?hl=th)) แต่บางครั้งขอบเขตคำจะไม่ตรงกับที่ผู้ใช้คาด ([Firefox tests](https://searchfox.org/firefox-main/source/js/src/tests/non262/Intl/Segmenter/word.js)) locale ไทยแสดงปีเป็นพุทธศักราชโดยปริยาย ถ้าต้องการ ค.ศ. ต้องระบุ `-u-ca-gregory` ([York U Java technote](https://www.eecs.yorku.ca/teaching/docs/java/technotes/guides/intl/calendar.doc.html)) และผู้ใช้ที่คาดว่าจะเห็น ค.ศ. ก็สับสนจริง ([Mendix forum](https://community.mendix.com/link/space/app-development/questions/144408))

**ความเร็วที่ผู้ใช้รับรู้:** ขีดจำกัดของ Nielsen ยังใช้ได้ ตอบสนองภายใน 0.1 วินาทีผู้ใช้รู้สึกว่าทันที ภายใน 1 วินาทีความคิดไม่สะดุด และ 10 วินาทีคือขีดสุดที่ผู้ใช้ยังจดจ่ออยู่ได้ ([NN/g](https://nngroup.com/articles/website-response-times/)) งานที่นานกว่านั้นต้องแสดงเปอร์เซ็นต์ความคืบหน้า ([NN/g response time](https://www.nngroup.com/topic/response-time/)) skeleton เหมาะกับการโหลดทั้งหน้าและต้องตรงกับ layout จริง ([NN/g Skeleton](https://nngroup.com/articles/skeleton-screens/); [Tim Kadlec](https://timkadlec.com/remembers/2020/11/skeleton-screens/)) ส่วน inline loading ใช้กับการกระทำในตาราง ปุ่ม หรือ modal และ error ให้แสดงแบบ inline ([Carbon](https://carbondesignsystem.com/components/inline-loading/usage/)) v1 เตรียมพื้นไว้ดีแล้ว รายการภาพ 200 รูปตอบใน 19 ms และ analytics ที่ cache ไว้ใน 44 ms (`apps/README.md`) เกือบทุก view จึงไม่ต้องมี loader เลย งานที่ต้องออกแบบจริงคืองานยาว ได้แก่ auto-label การเทรน และการ export ซึ่งควรอยู่ใน job tray ที่ไปทำงานอื่นระหว่างรอได้

| ฟีเจอร์ | Tier | สถานะ | หลักฐานและข้อแนะนำ |
| --- | --- | --- | --- |
| UI นอก canvas ผ่าน WCAG 2.2 AA (4.5:1 text, 3:1 control/focus, 24 px, focus ไม่ถูกบัง) | M | ไม่ระบุ | ([W3C](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/); [WebAIM](https://webaim.org/standards/wcag/wcag22)) |
| วาดโดยไม่ต้องลาก: click มุมสองมุม, click ทีละจุด, ลูกศรขยับ, ช่อง X/Y/W/H | M | ไม่ระบุ | WCAG 2.5.7 |
| รายการ annotation ใน DOM ให้ screen reader อ่านได้ (sync กับ canvas) | M | ไม่ระบุ | ([tldraw](https://tldraw.dev/features/composable-primitives/accessibility)) |
| ขอบ annotation สองชั้น (ขอบนอกเข้ม ขอบในสว่าง) ให้ได้ 3:1 บนทุกภาพ | S | ขาด | WCAG 1.4.11 ([W3C](https://w3.org/WAI/WCAG22/Understanding/non-text-contrast)) |
| Login ไม่มีแบบทดสอบความจำ อนุญาต paste password หรือใช้ OIDC | M | บางส่วน (มี OIDC [v1]) | WCAG 3.3.8 |
| เผยแพร่ ACR (VPAT 2.5) | D | ขาด | ([VPAT 2.5Rev](https://design.sis.gov.uk/VPAT2.5Rev_WCAG_February2025.docx)) |
| สลับ UI ไทย/อังกฤษ คงศัพท์เทคนิค (mAP, epoch) เป็นอังกฤษ | M | ไม่ระบุ | (ข้อเสนอ) |
| ตัดข้อความไทยด้วย CSS ellipsis หรือ `Intl.Segmenter` ห้ามใช้ `slice()`; `word-break: normal` | M | ไม่ระบุ | ([web.dev](https://web.dev/blog/intl-segmenter?hl=th); [W3C word-break tests](https://www.w3.org/International/tests/html-css/line-break/results-word-break)) |
| วันที่ใช้ `th-TH-u-ca-gregory` เป็นค่าเริ่ม ให้เลือก พ.ศ. ได้ | M | ไม่ระบุ | ([Mendix](https://community.mendix.com/link/space/app-development/questions/144408)) ต้องทดสอบใน browser จริง |
| ค้นหา class/ภาพที่ตัดคำไทยได้ | D | ขาด | ([AttaCut](https://arxiv.org/pdf/1911.07056)) |
| Interaction บน canvas ตอบภายใน 0.1 s (optimistic + rollback) | M | บางส่วน (autosave [v1]) | ([NN/g](https://nngroup.com/articles/website-response-times/)) |
| Skeleton สำหรับ grid/dashboard; หน่วง loader ~300–500 ms | M | ไม่ระบุ | ([NN/g](https://nngroup.com/articles/skeleton-screens/)); ค่าหน่วงเป็นข้อเสนอ |
| Job tray: ความคืบหน้า N/total, ETA, ออกจากหน้าได้, แจ้งผ่าน `aria-live` | M | บางส่วน (live chart [v1]) | ([NN/g](https://www.nngroup.com/topic/response-time/)) |
| Stream ผล auto-label ทีละภาพระหว่าง job ยังรัน | S | บางส่วน (progress ต่อภาพ §P5) | (ข้อเสนอ) |
| Empty / error / loading ครบทุก list | M | ไม่ระบุ | ([Carbon](https://carbondesignsystem.com/components/inline-loading/usage/)) |

## 6. แนวทางการออกแบบ: glass ลอยอยู่บน chrome สีมาจาก HCT และ canvas ต้องทึบ

Liquid Glass ที่ Apple เปิดตัว 9 มิ.ย. 2025 คือวัสดุโปร่งแสงที่ "สะท้อนและหักเหสิ่งรอบตัว" ใช้กับ tab bar และ sidebar เพื่อ "ให้ความสนใจไปอยู่ที่ content" ([Apple Newsroom](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)) NN/g วิจารณ์ว่าผลลัพธ์ "เบา โปร่ง และหลายครั้งมองไม่เห็น" ([NN/g](https://nngroup.com/articles/liquid-glass)) นักพัฒนาชี้ว่า glass ควบคุมสิ่งที่อยู่ข้างหลังไม่ได้ จึงอ่านยากเมื่อวางบน content ที่รก ([9to5Mac](https://9to5mac.com/2025/09/15/ios-26-officially-launches-today-but-some-developers-arent-sure-it-should/)) และ Apple ลดความโปร่งใสลงใน beta ถัดมา ([mezha.ua](https://mezha.ua/en/news/ios-26-liquid-glass-beta-3-303201/amp/)) บน annotation canvas สิ่งที่อยู่ข้างหลังคือภาพที่กำลัง label และสีของ class ถ้าใช้ translucency ตรงนั้น สีและ contrast ที่ผู้ใช้เห็นจะเพี้ยน ความแม่นของการ label จะลดลงตามไปด้วย ข้อนี้คือข้อจำกัดหลักของทิศทาง design ทั้งหมด

ไม่พบงานวิจัยที่ประเมิน glass UI ในเครื่องมือที่ข้อมูลหนาแน่นหรือเครื่องมือ annotation โดยตรง กฎ "glass คือ chrome" มาจากบทความ practitioner หนึ่งชิ้นปี 2026 บวกกับขอบเขตที่ Apple กำหนดเอง ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) ตัวเลข "รู้จำ UI เร็วขึ้น 4 เท่า จาก 46 การศึกษา" ของ M3 Expressive มาจากสื่อ ไม่ใช่เอกสารของ Google ([Dezeen](https://www.dezeen.com/2025/05/28/google-ushers-in-age-of-expressive-interfaces-with-material-design-update/amp/)) จึงไม่ควรใช้อ้างในการนำเสนอ

### ใช้ glass ที่ไหน และห้ามใช้ที่ไหน

| พื้นผิว | Glass? | สเปก |
| --- | --- | --- |
| Top app bar, sidebar ของ project (วางบนพื้น gradient/mesh บาง ๆ) | ใช้ | blur ≤ 20px, saturate 140–180%, ขอบ 1px alpha ~0.28 ขอบบนสว่างกว่า ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) |
| Command palette, modal, sheet, Auto Label dialog | ใช้ | glass ทับ scrim ทึบ เพื่อให้ข้อความอยู่บนพื้นที่คุม contrast ได้ |
| Job tray / toast | ใช้ | วางห่างจาก element ที่มี focus (WCAG 2.4.11) |
| Toolbar ลอยและปุ่ม zoom บน canvas | ใช้แบบ tint หนา | alpha ≥ ~0.85 เพื่อให้ icon ได้ 3:1 บนทุกภาพ (ค่าเป็นข้อเสนอ) |
| Hero/landing/หน้า login | ใช้ refraction ได้ | `feDisplacementMap` ทำงานบน Chromium เท่านั้น ต้องมี fallback ([DEV](https://dev.to/devyatov/liquid-glass-on-the-web-6-ways-to-build-it-with-css-and-svg-3m07)) |
| Annotation canvas, label/chip ของ class บนภาพ | ห้าม | ใช้พื้นทึบ เพื่อไม่ให้สีภาพและสี class เพี้ยน |
| ตาราง, dataset grid, confusion matrix, กราฟ training, leaderboard | ห้าม | contrast จะเปลี่ยนตามพื้นหลัง ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) |
| Live MJPEG และ event snapshot | ห้าม | ใช้กรอบทึบ แถบสถานะทึบ |

จำกัดไว้ที่ 3–4 ชั้น glass ต่อ viewport ห้าม animate ค่า blur (ให้ animate opacity แทน) และใช้ `will-change` ให้น้อย เพราะ `backdrop-filter` ต้อง composite ทุกอย่างที่อยู่ข้างหลังใหม่ทุกเฟรม ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) ข้อนี้สำคัญกับเครื่องที่ใช้เดโม เพราะ GPU ตัวเดียวกันต้องรัน vLLM, SAM และ stream ไปพร้อมกัน ใน app ให้ใช้ frosted blur + saturate เป็นฐานที่ทำงานได้ทุก browser และไม่ใช้ refraction กับ chromatic aberration

### สี: seed เดียว → HCT → Tailwind v4 token และ palette ของ class แยกออกมา

`material-color-utilities` คือชุดอัลกอริทึมเบื้องหลัง dynamic colour ของ M3 HCT สร้างจาก hue และ chroma ของ CAM16 รวมกับ L* tone ส่วน tonal palette แต่ละชุดต่างกันแค่ tone และ scheme หนึ่งได้มาจาก key colour 5 ตัว ([MCU README](https://chromium.googlesource.com/external/github.com/material-foundation/material-color-utilities/+/91da30d89e70c3dc9575ec71a1ebe8874d881f29/README.md)) dynamic colour ปรับ contrast ได้โดยคง chroma ไว้ และใน codebase มี ColorSpec2025 กับ 2026 ([MCU dynamic_color](https://github.com/material-foundation/material-color-utilities/blob/051ed9a15be6a4d4b4774d2edec1ee3d64e9f771/dart/lib/dynamiccolor/dynamic_color.dart)) Linear ใช้แนวทางเดียวกัน คือสร้าง theme จาก input 3 ตัว (base, accent, contrast) ในปริภูมิ LCH แทนตัวแปรที่ตั้งมือ 98 ตัว และ input ด้าน contrast ให้ theme high-contrast มาเกือบฟรี ([Linear](https://linear.app/now/how-we-redesigned-the-linear-ui))

Pipeline ที่แนะนำ: สคริปต์ build-time ใช้ `@material/material-color-utilities` แปลง seed แบรนด์หนึ่งสีเป็น `SchemeTonalSpot` สำหรับ surface และ `SchemeVibrant` หรือ `SchemeExpressive` สำหรับ accent ที่ต้องการความ "premium" สร้างครบ light/dark และ contrast level 0, 0.5, 1.0 จากนั้นแปลงเป็น OKLCH แล้วเขียนออกเป็น CSS variable ใน `@theme` ของ Tailwind v4 ตามบทบาท (`--color-primary`, `--color-surface-container-high`, `--color-on-surface` ฯลฯ) ไม่ตั้งชื่อตาม hue (ข้อเสนอ สังเคราะห์จาก [MCU](https://chromium.googlesource.com/external/github.com/material-foundation/material-color-utilities/+/91da30d89e70c3dc9575ec71a1ebe8874d881f29/README.md) และ [Linear](https://linear.app/now/how-we-redesigned-the-linear-ui)) ถ้าทำ runtime re-tint ตาม accent ที่ผู้ใช้เลือกแบบ Material You ได้ จะนับเป็น differentiator

```css
/* tokens.generated.css  (สร้างจากสคริปต์ MCU ห้ามแก้ด้วยมือ) */
@theme {
  --color-primary: oklch(0.55 0.19 265);
  --color-on-primary: oklch(0.99 0 0);
  --color-surface: oklch(0.985 0.004 265);
  --color-surface-container-high: oklch(0.93 0.01 265);
  /* class palette: ชุดแยก ไม่ได้มาจาก seed */
  --color-class-0: #0072B2; --color-class-1: #E69F00; --color-class-2: #009E73;
}
```

**Palette ของ class ต้องแยกจากแบรนด์ทั้งหมด** ใช้ Okabe-Ito สำหรับ 8 class แรก เพราะออกแบบมาให้คนตาบอดสีแดง-เขียวส่วนใหญ่แยกได้ ([factoextra docs](https://rdrr.io/cran/factoextra/man/factoextra_palette.html)) และทำได้ดีเป็นพิเศษกับผู้ที่มีภาวะ deuteranopia ([Zeileis & Murrell](https://arxiv.org/pdf/2303.04918)) หลังจากนั้นขยายด้วย Glasbey ที่ใช้ Okabe-Ito เป็น seed และจำกัดช่วง lightness/chroma ได้ ([glasbey docs](https://glasbey.readthedocs.io/en/latest/creating_palettes.html)) เพราะ Glasbey เลือกสีที่ห่างกันมากที่สุดใน CIE-LAB ([Glasbey et al.](https://strathprints.strath.ac.uk/30312/)) ผูกสีกับ index ของ class ให้คงที่ v1 ให้ผู้ใช้ recolor ได้อยู่แล้ว (`apps/README.md`) จึงเหลือแค่เปลี่ยนค่าเริ่มจากสีสุ่มหรือสีที่ตั้งมือเป็น palette นี้ และแสดงชื่อ class คู่กับสีเสมอ (WCAG 1.4.1) confusion matrix และ heatmap ใช้ viridis เพราะเป็นค่าเริ่มของ scikit-learn ที่ผู้ใช้ ML คุ้นตา ([scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ConfusionMatrixDisplay.html)) สีสถานะ (running/ok/warn/error) ต้องมี icon และข้อความกำกับ เพราะไม่พบแหล่งที่กำหนดมาตรฐานสีของสถานะ job ใน ML

### Typography

ฝั่งละตินใช้ IBM Plex Sans ฝั่งไทยใช้ **Anuphan** ซึ่งเป็นฟอนต์ไทยแบบไม่มีหัวของ Cadson Demak ที่ออกแบบให้เข้าชุดกับ IBM Plex Sans (OFL) ([Anuphan GitHub](https://github.com/cadsondemak/Anuphan); [Google Fonts](https://fonts.google.com/specimen/Anuphan/about)) หรือใช้ IBM Plex Sans Thai ที่มีทั้งแบบมีหัวและไม่มีหัว 7 น้ำหนัก ([fontpad](https://www.fontpad.co.uk/?p=1772)) แบบไม่มีหัวเข้ากับโทนโมเดิร์นของ glass มากกว่า แบบมีหัวคุ้นตาผู้อ่านสูงวัยมากกว่า ใช้ Noto Sans Thai เป็น fallback self-host และแบ่ง subset ด้วย `unicode-range` ใช้ line-height 1.5–1.6 สำหรับเนื้อความไทย (ข้อเสนอ ยังไม่มีแหล่งกำหนดค่า) ห้ามใช้ `overflow: hidden` กับกล่องที่สูงคงที่ ทดสอบด้วยคำอย่าง "ปั่นป่วน" และ "ญู/ฐู" ตัวเลขใช้เลขอารบิกพร้อม `font-variant-numeric: tabular-nums` ในตาราง metric ไม่พบงานที่เปรียบเทียบการอ่านระหว่าง Plex Thai, Anuphan, Noto Sans Thai และ Sarabun ใน UI การเลือกฟอนต์จึงยังเป็นเรื่องรสนิยมบวกความเข้าชุดกัน

### Motion

แหล่งข้อมูลที่ใช้ได้ด้าน motion มีน้อย กฎที่มีหลักฐานรองรับคือ animate เฉพาะ opacity/transform ห้าม animate blur ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) และ feedback ของการกระทำบน canvas ต้องมาภายใน 0.1 วินาที ([NN/g](https://nngroup.com/articles/website-response-times/)) ดังนั้น motion ต้องไม่หน่วง feedback ห้ามมี transition ระหว่างวาดกล่อง เลือก หรือ pan ให้ใช้ motion ที่เด่นชัดตาม "expressive" เฉพาะจังหวะที่ไม่ขวางงาน ได้แก่ การเปิด modal/sheet, job เสร็จ และ event ใหม่เข้ามาใน timeline (ข้อเสนอ) motion spec ของ M3 Expressive และ `prefers-reduced-motion` ไม่ได้ถูกค้นในรอบนี้ ทีมควรอ่านจากแหล่งต้นทางก่อนกำหนดค่า duration/easing แต่การปิด motion ที่ไม่จำเป็นเมื่อผู้ใช้ตั้ง reduce motion ควรทำเป็นค่าเริ่ม (ข้อเสนอ)

### Fallback สำหรับ reduced transparency และ contrast

ให้พื้นทึบที่ contrast สูงเป็นค่าเริ่ม แล้วเปิด glass เฉพาะใต้ `@supports (backdrop-filter: blur(1px))` ร่วมกับ `@media (prefers-reduced-transparency: no-preference)` และเพิ่มขอบ 2px ใต้ `prefers-contrast: more` ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) `prefers-reduced-transparency` ยังไม่เป็น Baseline Chrome/Edge 119+ รองรับ แต่ Safari ยังไม่รองรับ ([MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-transparency)) จึงต้องมีสวิตช์ "ลดความโปร่งใส" ในหน้าตั้งค่าของ LabelDesk ด้วย และผูกสวิตช์นี้กับ contrast level 1.0 ของ MCU เพื่อให้ได้ theme high-contrast เต็มชุด Safari ไม่ resolve CSS custom property ภายใน `-webkit-backdrop-filter` ต้องเขียนค่าตายตัว ([BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)) surface โปร่งแสงไม่มี contrast ratio คงที่ ต้องวาง layer กึ่งทึบไว้ใต้ข้อความ แล้ววัด WCAG 1.4.3/1.4.11 กับพื้นหลังที่แย่ที่สุด ไม่ใช่พื้นหลังเฉลี่ย

```css
.glass { background: var(--color-surface-container-high); } /* ค่าเริ่ม: ทึบ */
@supports (backdrop-filter: blur(1px)) {
  @media (prefers-reduced-transparency: no-preference) {
    :root:not([data-transparency="reduced"]) .glass {
      background: oklch(0.98 0.01 265 / 0.72);
      -webkit-backdrop-filter: blur(16px) saturate(160%); /* Safari: ค่าตายตัว */
      backdrop-filter: blur(16px) saturate(160%);
    }
  }
}
@media (prefers-contrast: more) { .glass { border-width: 2px; } }
```

### แก้ก่อนเดโม

ในห้าข้อด้านล่าง ข้อแรกกับข้อสามเปลี่ยนแค่ค่าเริ่มหรือ label อีกสามข้อเป็น interaction ที่ต่อเข้ากับข้อมูลที่ §3.10 คำนวณไว้แล้ว

| # | งาน | เหตุผล |
| --- | --- | --- |
| 1 | เปลี่ยน palette class เริ่มต้นเป็น Okabe-Ito และห้าม glass บน canvas/ตาราง/กราฟ | ความแม่นของการ label และ WCAG 1.4.11 |
| 2 | Confusion matrix ที่มี confidence slider และคลิก cell แล้วเปิด gallery GT เทียบ pred | ข้อมูลมีแล้วใน §P4 ขั้น 8; ทำให้ "ตรวจสอบง่ายขึ้น" ([Vasconcelos](https://arxiv.org/pdf/2212.06823)) |
| 3 | Badge "VLM · ไม่มี confidence" แทน 0.5 และ badge ที่มาของ annotation | ความโปร่งใสตาม HAX G1/G2 |
| 4 | การ์ด event แสดงเหตุผล trigger + จุด anchor + ปุ่ม send to dataset ที่เห็นชัด | ช่วงไคลแมกซ์ของเดโม (§1.2) |
| 5 | สถานะ GPU/โมเดล (loading, evicted, paused-for-training) ใน Playground และ Streams | scheduler §3.6 ทำให้เกิด delay ที่ผู้ชมต้องเข้าใจได้ |

## Conclusion

ข้อที่งานรอบนี้เปลี่ยนความเข้าใจมากที่สุดคือ การแสดงผลที่สร้างความเชื่อใจให้ AI ใน CV คือ **ภาพที่ใช้ตรวจสอบ** ไม่ใช่ตัวเลข confidence หรือข้อความอธิบาย งานวิจัยพบว่าคำอธิบายลดการพึ่ง AI เกินควรได้เฉพาะเมื่อมันลดต้นทุนการตรวจสอบ ด้วยเหตุนี้งานที่คุ้มที่สุดของ LabelDesk จึงเป็น interaction ที่พาจากตัวเลขไปหาภาพ ได้แก่ cell ของ matrix ไปหา gallery, แท่ง histogram ไปหา grid และ event ไปหา snapshot และ dataset ข้อมูลเบื้องหลังเกือบทั้งหมดคำนวณไว้แล้วใน §3.10 ช่องว่างจริงจึงอยู่ที่ชั้น UI ไม่ใช่ชั้น ML

รสนิยมด้านภาพของผู้ใช้ไม่ได้ขัดกับความแม่นยำ ถ้าคิดว่า glass เป็นชั้นที่ลอยอยู่เหนือ workspace ไม่ใช่เป็นตัว workspace Liquid Glass กับ M3 Expressive แก้คนละปัญหา glass ให้ความรู้สึก premium กับ chrome ส่วน HCT ให้ระบบสีที่ปรับ contrast ได้ตามหลักการ ซึ่งทำให้ fallback สำหรับ reduced transparency กลายเป็นแค่ค่า contrast level หนึ่งในชุด token เดียวกัน ไม่ต้องดูแล theme แยกอีกชุด ความเสี่ยงที่ยังเหลือคือหลักฐานด้าน design ส่วนใหญ่เป็นแนวปฏิบัติของ practitioner ไม่ใช่การทดลอง หลังเดโมจึงควรทดสอบ usability กับ labeler จริงสัก 5 คน โดยเทียบโหมด glass กับโหมดทึบบนงาน review ซึ่งเป็นข้อมูลที่ยังไม่มีใครเผยแพร่
