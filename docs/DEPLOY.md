# Deploy LabelDesk ฟรี

## ภาพรวม: ทำไมต้องแยกเป็น 3 ส่วน

Vercel เป็น serverless จึงเหมาะกับ **หน้าเว็บ (static)** เท่านั้น ใช้รัน API หรือ train model ไม่ได้ เพราะ
แพ็กเกจจำกัดที่ 250 MB (torch ใหญ่เกินนี้), แต่ละ request รันได้ไม่กี่สิบวินาที, ไม่มี GPU และไม่มีดิสก์ถาวรไว้เก็บรูป

```
 ผู้ใช้ ──► Web (Vercel, ฟรี) ──► API + Postgres + ไฟล์ (VM ฟรี) ◄── labeldesk-worker (GPU ของคุณ / Kaggle / Colab)
                                     ▲  งานเบา: version, export, hosted inference         train, auto-label
```

| ส่วน | ใช้อะไร (ฟรี) | หมายเหตุ |
|---|---|---|
| Web | **Vercel** Hobby | หรือไม่ต้องใช้ก็ได้ เพราะ compose เสิร์ฟหน้าเว็บให้อยู่แล้ว |
| API + DB + ไฟล์ | **Oracle Cloud Always Free**: VM Ampere ARM 4 OCPU, RAM 24 GB, ดิสก์ 200 GB | เปิดตลอดและดิสก์ไม่หาย เป็นตัวเลือกที่คุ้มที่สุด |
| GPU worker | **เครื่องที่มี GPU ของคุณเอง** | ติดตั้งด้วย `pip install` แล้วรันได้เลย ไม่ต้องเปิด port |
| GPU สำรอง | **Kaggle Notebooks**: T4/P100 ฟรี 30 ชม./สัปดาห์ หรือ **Google Colab** | รัน worker ใน notebook ได้ |

ทางเลือกอื่นสำหรับ API: Render free (sleep หลัง 15 นาที ดิสก์หายเมื่อ deploy ใหม่) หรือ Hugging Face Spaces Docker (ดิสก์ไม่ถาวร)
ทั้งสองตัวต้องย้ายไฟล์ไปเก็บบน object storage ก่อน ซึ่งยังไม่ได้ทำ ตอนนี้จึงแนะนำ Oracle VM

---

## 1. API บน Oracle Cloud Always Free

1. สมัคร Oracle Cloud แล้วสร้าง Compute instance: shape `VM.Standard.A1.Flex` (4 OCPU / 24 GB), image Ubuntu 22.04
2. ใน VCN Security List เปิด ingress port **80** และ **443**
3. ชี้ DNS: ตั้ง `A labeldesk.example.com` และ `A api.labeldesk.example.com` ไปที่ public IP ของ VM
   (ถ้าไม่มีโดเมน ใช้ DuckDNS ฟรีได้)
4. บน VM รัน:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT   # Oracle Ubuntu ปิด firewall ไว้เป็นค่าเริ่มต้น
git clone https://github.com/Telotubbies/auto_label.git && cd auto_label/deploy
cp .env.example .env
sed -i "s/^LD_SECRET=.*/LD_SECRET=$(openssl rand -hex 32)/; s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/; s/^LD_WORKER_TOKEN=.*/LD_WORKER_TOKEN=$(openssl rand -hex 32)/" .env
nano .env            # แก้ LD_DOMAIN
sudo docker compose up -d --build
```

5. เปิด `https://labeldesk.example.com` แล้วสมัครบัญชีแรก หลังสมัครควรปิด sign-up โดยตั้ง `LD_SIGNUP_ENABLED=0` แล้วใช้ invite link เชิญคนอื่นแทน

> แค่นี้ก็ใช้งานได้ครบแล้ว (เว็บ, API, DB อยู่บน VM ตัวเดียว) ส่วนข้อ 2 ทำเฉพาะเมื่ออยากให้หน้าเว็บอยู่บน Vercel

## 2. (ไม่บังคับ) Web บน Vercel

1. Vercel → New Project → import repo → **Root Directory = `apps/web`** (ระบบตรวจเจอ Vite เอง)
2. Environment Variables: `VITE_API_URL = https://api.labeldesk.example.com`
3. Deploy แล้วนำ URL ที่ได้ (เช่น `https://labeldesk.vercel.app`) ไปใส่ใน `.env` ของ VM:
   `LD_CORS_ORIGINS=https://labeldesk.vercel.app` และ `LD_PUBLIC_URL` (ลิงก์ invite จะชี้ไปที่ URL นี้)
   จากนั้นรัน `sudo docker compose up -d` อีกครั้ง

## 3. GPU worker (train / auto-label)

Token ใช้ค่า `LD_WORKER_TOKEN` จาก `.env` บน VM

### เครื่องที่มี GPU ของคุณ (Windows / Linux / WSL)
```bash
pip install "git+https://github.com/Telotubbies/auto_label.git#subdirectory=apps/worker"
# ถ้าใช้ NVIDIA ให้ลง torch แบบ CUDA ก่อน: https://pytorch.org/get-started/locally/
labeldesk-worker --server https://api.labeldesk.example.com --token <LD_WORKER_TOKEN> --device 0
```
ถ้าจะใช้ base weights YOLO26 ที่มีในเครื่อง ให้เพิ่ม `--pretrained-dir yolo26_ppe/models/pretrained`
ถ้าจะใช้ SAM 3.1 auto-label ให้เพิ่ม `--sam-root sam3_auto_label` (ต้องมี checkpoint อยู่ในเครื่อง)
ถ้าอยากให้รันทุกครั้งที่เปิดเครื่อง: Linux ใช้ systemd หรือ `tmux`, Windows ใช้ Task Scheduler

### Kaggle / Colab (GPU ฟรี)
สร้าง notebook แล้วเปิด GPU accelerator จากนั้นรัน cell นี้:
```python
!pip -q install "git+https://github.com/Telotubbies/auto_label.git#subdirectory=apps/worker"
!labeldesk-worker --server https://api.labeldesk.example.com --token <LD_WORKER_TOKEN> --device 0
```
Kaggle ต้องเปิด Settings → Internet: On ด้วย worker จะดึงงานต่อไปเรื่อยๆ จนกว่าจะปิด session
ถ้าต้องการให้รันงานเดียวแล้วจบ ให้ใส่ `--once`

### ไม่มี GPU เลย
ตั้ง `LD_LOCAL_JOBS=version,export,export_engine,health,connector_sync,retention,extract_frames,track_forward,drift,active_learning,insights_images,insights_leakage,insights_embedding,train,autolabel` ใน `.env` แล้ว VM จะ train ด้วย CPU เอง
ช้ากว่า แต่โมเดล n/s ขนาดเล็กที่ 30–50 epochs บนรูปหลักร้อยใบยังพอรับได้

> ค่าเริ่มต้นของ `worker` ใน compose ครอบคลุมงาน CPU ทุกชนิด (`version,export,export_engine,health,connector_sync,retention,extract_frames,track_forward,drift,active_learning,insights_*`) — drift monitor จึงทำงานบน VM
> นี้ได้ทันที (ใช้สี/เลย์เอาต์ของรูปบน volume ถ้าไม่ได้ติดตั้ง CLIP) ส่วน `active_learning` ต้องรันโมเดลที่เทรนแล้ว
> เพื่อให้คะแนนรูป จึงต้องมี worker ที่โหลดโมเดลได้ (CPU/GPU) และไม่ควรย้ายไปไว้ที่ service `api`
> งาน `train`/`autolabel` ยังคงจ่ายให้ `labeldesk-worker` บนเครื่อง GPU ตามปกติ

---

## Live streams (egress)

กล้อง/ไฟล์วิดีโอที่เพิ่มในหน้า Streams ถูกดึงจาก **ตัว API เอง** ไม่ใช่จากเบราว์เซอร์:

- รับเฉพาะ `rtsp`, `rtsps`, `http`, `https` หรือไฟล์ที่อัปโหลด (`file:videos/<name>`) เท่านั้น
- ต้นทางต้อง resolve เป็น **public unicast** — ที่อยู่ private, loopback และ link-local จะถูกปฏิเสธ
  (กล้องใน LAN ต้องมี reverse proxy/public URL หรืออัปโหลดเป็นไฟล์วิดีโอ)
- HTTP(S) วิ่งผ่าน loopback guard ที่ pin IP และปฏิเสธ redirect ไปยังเครือข่ายภายใน
  ส่วน RTSP ถูกต่อด้วย IP ที่ตรวจแล้วโดยตรง เพื่อปิดช่อง DNS rebinding
- เปิด egress จาก container `api` ไปยัง port ของกล้องเท่าที่จำเป็น; ไม่ต้องเปิด ingress เพิ่ม

---

## หมุน LD_SECRET (secret rotation)

`LD_SECRET` เข้ารหัส connector credentials และ webhook signing secrets ที่เก็บใน DB
(ดู `apps/api/app/services/secretbox.py`)

1. ตั้ง `LD_SECRET` เป็นค่าใหม่ และ `LD_SECRET_OLD` เป็นค่าเก่า (คั่นหลายค่าด้วย `,` ได้)
2. รีสตาร์ท api/worker — MultiFernet จะถอดรหัสแถวเก่าได้ และ startup migration
   เขียนกลับด้วยคีย์ใหม่ให้อัตโนมัติ
3. ตรวจว่าแถวทั้งหมดอ่านได้แล้ว จึงลบ `LD_SECRET_OLD` ออก
4. ถ้าลบค่าเก่าก่อนที่แถวจะถูกเข้ารหัสใหม่ ข้อมูลลับเหล่านั้นจะอ่านไม่ได้ถาวร

## Checklist ก่อนเปิดให้คนอื่นใช้

- [ ] เปลี่ยน `LD_SECRET`, `POSTGRES_PASSWORD`, `LD_WORKER_TOKEN` จากค่าเริ่มต้น (คำสั่ง sed ในข้อ 1 ทำให้แล้ว)
- [ ] `LD_SEED_DEMO=0` (ค่าเริ่มต้นใน compose)
- [ ] ปิด sign-up หรือเปิดไว้โดยตั้งใจ
- [ ] ตั้ง `LD_SUPERADMINS=you@email` ถ้าต้องการเปลี่ยน plan ให้ workspace
- [ ] สำรองข้อมูล: `docker compose exec db pg_dump -U labeldesk labeldesk > backup.sql` และ volume `labeldesk_data` (เก็บรูป, export, weights)
- [ ] Oracle Free อาจ reclaim VM ที่ idle นาน ควรทำ backup ไว้เป็นประจำ
