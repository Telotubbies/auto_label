# Inference/Deployment, Video & CCTV Stream Analytics, VLM Serving and GPU Scheduling for a CV SaaS (LabelDesk)

Context: LabelDesk is a Roboflow-like SaaS. The demo box is one RTX 3080 Ti (12 GB) running vLLM with Qwen2.5-VL-7B AWQ 4-bit and RTSP streams. Research date: 2026-10-31.

Source labels:
- **[fetched]** means the page was opened and read during this session.
- **[search-snippet]** means the claim came from search-result summaries only. Check it against the source before quoting it externally.
- **[known-ref, not re-fetched]** marks canonical paper or doc URLs cited from prior knowledge. The URLs are stable, but this session did not re-read them.

---

## Q1. Deployment options (Roboflow, Ultralytics HUB, Landing AI, Edge Impulse, NVIDIA, AWS Panorama): hosted API, SDKs, edge, export formats, quantization, batching, versioning/rollback, A/B or shadow

### Takeaway
The market-standard package has four parts:
- a hosted REST API, with serverless CPU and dedicated GPU tiers;
- a self-hostable Docker inference server for CPU, GPU, TensorRT and Jetson;
- an async batch job service for stored images and video;
- a visual pipeline builder (Roboflow Workflows).

Server-side, NVIDIA Triton is the reference design for versioned model repositories, explicit load/unload and dynamic batching. TensorRT gives large speedups, but it adds a long first-load compile step, so engines need caching.

### Cited Findings
**Roboflow**
- Roboflow lists three managed deployment options plus Batch Processing. [search-snippet] — [Roboflow Managed Deployments](https://docs.roboflow.com/deploy/roboflow-managed-deployments-overview)
  - **Serverless Hosted API:** runs on CPU, scales automatically with calls, and does not yet support GPU-only models, so latency can be higher.
  - **Dedicated Deployments:** dedicated GPU or CPU, suited to heavy models like SAM2. They do not autoscale.
  - **Batch Processing:** fully managed and no-code, for stored image and video sets. Jobs run asynchronously, billing is per server-hour, and it is not for real-time use.
- The Serverless Hosted API v2 is called as a REST API. [search-snippet] — [Roboflow Serverless v2 REST](https://docs.roboflow.com/deploy/serverless-hosted-api-v2/use-with-the-rest-api)
- A Korean-language doc page says Dedicated Deployments run only in US data centers. [search-snippet] — [Roboflow KO docs](https://docs.roboflow.com/roboflow/roboflow-ko/undefined-3/roboflow-managed-deployments-overview)
- Sources disagree on Custom Python Blocks. One page says they cannot run on the Serverless API. Another says they are supported on Dedicated Deployments and self-hosted servers. [search-snippet] — [Deploy a Workflow](https://docs.roboflow.com/workflows/deploy/deploy-a-workflow)
- Roboflow Inference (the open-source server) runs in Docker on x86 CPU, GPU, ARM and Jetson, plus AWS Lambda. [search-snippet] — [Roboflow Inference Docker quickstart (mirror)](https://huggingface.co/spaces/Sankie005/Docker_ml/blob/main/docs/quickstart/docker.md)
  - Separate images exist for CPU, GPU, GPU+TensorRT and Jetson, tagged by JetPack version (jetson-6.2.0, 6.0.0, 5.1.1, 4.6.1, 4.5.0).
  - JetPack 4 is deprecated, and Roboflow recommends JetPack 6.
  - `pip install inference-cli && inference server start` detects the JetPack version and picks a container automatically.
  - Jetson install docs: [Roboflow Jetson install](https://docs.roboflow.com/deployment/ko/self-hosted/inference-server/install/jetson). Legacy page: [Roboflow Jetson (Legacy)](https://docs.roboflow.com/deploy/legacy-documentation/enterprise-nvidia-jetson).
- TensorRT in Roboflow Inference: [search-snippet] — [Roboflow Jetson (Legacy)](https://docs.roboflow.com/deploy/legacy-documentation/enterprise-nvidia-jetson); [Roboflow Jetson install](https://docs.roboflow.com/deployment/ko/self-hosted/inference-server/install/jetson)
  - Older pages enable it with `ONNXRUNTIME_EXECUTION_PROVIDERS=TensorrtExecutionProvider`.
  - Current docs warn that a model's first load needs a heavy compile and optimization step, sometimes over 15 minutes. They recommend a persistent cache volume so compiled engines survive restarts.
- Roboflow Workflows is a computation graph of "Workflow Blocks" that pipes and parallelizes data through models, logic and custom code. [search-snippet] — [Roboflow Inference repo docs](https://docsearch.algolia.com/mcp/docs/repo/roboflow/inference)

**NVIDIA Triton (model management, versioning, rollback)**
- Triton has three model control modes. [fetched] — [Triton Model Management](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_management.html)
  - **NONE** (default) loads everything at startup and ignores changes.
  - **EXPLICIT** (`--model-control-mode=explicit`, `--load-model`) loads and unloads only through the model-control API.
  - **POLL** (`--repository-poll-secs`) auto-detects repository changes. NVIDIA warns it is not synchronized with repository edits and does not recommend it for production.
- Versions are subdirectories in the model repository. When a version is removed, in-flight requests to it complete and new requests fail. The default served version depends on the model's version policy. [fetched] — [Triton Model Management](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_management.html)
- Changing only `instance_count` updates a model without a full reload. Models load in the background while existing models keep serving (`--model-load-thread-count`, default 4). [fetched] — [Triton Model Management](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_management.html)

**Frigate (edge/NVR detector targets, for comparison of export targets)**
- Frigate's official detectors: [fetched] — [Frigate Object Detectors](https://docs.frigate.video/configuration/object_detectors/)
  - Coral EdgeTPU (TFLite)
  - Hailo-8/8L
  - OpenVINO (Intel CPU, iGPU, Arc, NPU)
  - ONNX (CPU, OpenVINO, ROCm or TensorRT)
  - TensorRT on Jetson (`-tensorrt-jp6`, engines built on-device at startup)
  - Apple Silicon via ZMQ
  - Deepstack/CodeProject.AI over the network
- Community detectors include RKNN, MemryX, AMD XDNA2, Synaptics and AXERA. YOLOv9 is the recommended ONNX/OpenVINO model, and 320x320 input is recommended. [fetched] — [Frigate Object Detectors](https://docs.frigate.video/configuration/object_detectors/)

### Inferences
- **Must-have for LabelDesk:**
  - a hosted REST endpoint per model version, with an API key;
  - a Python SDK;
  - a self-hostable Docker inference image, at least CPU and NVIDIA GPU;
  - an async batch job over a dataset or video.
  - This set mirrors Roboflow's baseline, and Roboflow defines user expectations here.
- **Should-have:**
  - ONNX export plus a TensorRT FP16 engine with a persistent engine cache, because first-load compiles can take 15+ minutes;
  - pinned version aliases (for example "production" pointing at v7) for one-click rollback, modelled on Triton's EXPLICIT load/unload.
- **Differentiator:** shadow or A/B traffic splitting between model versions. None of the fetched sources documents it as a built-in Roboflow feature (see Gaps).
- **Note:** Roboflow's serverless tier is CPU-only. A small GPU-backed hosted endpoint for VLM and SAM-class models is a gap LabelDesk could exploit on its own GPU.

### Gaps
- Not fetched or verified this session:
  - Ultralytics HUB / Ultralytics export formats. The export docs, [docs.ultralytics.com/modes/export](https://docs.ultralytics.com/modes/export/) [known-ref, not re-fetched], list ONNX, TensorRT, OpenVINO, CoreML, TFLite and others, with half/int8 flags. Confirm before citing.
  - Landing AI (LandingLens) deployment options.
  - Edge Impulse (EON compiler).
  - AWS Panorama's status. I believe AWS announced end-of-support for Panorama, but did not verify this in this session.
- Did not fetch Triton's dynamic-batching or rate-limiter pages, or the TensorRT INT8 calibration docs. Calibration needs a representative dataset, which is a natural fit for a labeling platform, but this needs a citation.
- Found no source confirming that Roboflow offers native A/B or shadow deployment.

---

## Q2. Video/CCTV analytics: RTSP ingestion, NVDEC decoding, frame sampling, MOT (ByteTrack/BoT-SORT/OC-SORT), zones/lines/dwell, events/alerts, NVR (Frigate), privacy, reconnection, streams per GPU

### Takeaway
Two reference architectures dominate:
- **Roboflow InferencePipeline** (Python): RTSP and multi-source, `max_fps` sampling with drop-oldest for live streams, auto-reconnect, and sinks, combined with the `supervision` library for tracking, zones and annotation.
- **NVIDIA DeepStream** (GStreamer): `nvurisrcbin`, `nvstreammux` batching, `nvinfer` and `nvtracker` on NVDEC.

Reconnection is the most common real-world pain point, even in DeepStream 7.x/8.0. Streams per GPU has no published constant. It has to be benchmarked per model and resolution.

### Cited Findings
**Roboflow InferencePipeline** [fetched] — [Roboflow InferencePipeline](https://docs.roboflow.com/reference/inference/inference-python/inference-pipeline)
- **Sources:** `video_reference` accepts a webcam ID, file, URL, RTSP URL, or a list of these. Each source in a list gets its own consumer thread, and a multiplexer collects their frames.
- **Sampling:** `max_fps` caps the processing rate. For live streams, older frames are dropped so the pipeline works on the most recent frame. Video files are processed frame by frame.
- **Multi-source batching:** `batch_collection_timeout` sets how long to wait for each source. A source that misses the timeout yields `None`.
- **Sink modes:** `sink_mode` is `SEQUENTIAL`, `BATCH` or `ADAPTIVE` (the default).
- **Reconnect:** streams reconnect automatically after connectivity loss. The page gives no retry or timing parameters.
- **Built-in sinks:** `render_boxes`, `UDPSink` (JSON over UDP), `multi_sink` and `VideoFileSink`.
- **Workflows and custom logic:** `init_with_workflow(workflow_specification | workspace_name+workflow_id)`, with optional profiling (`ENABLE_WORKFLOWS_PROFILING`). `init_with_custom_logic` accepts arbitrary callables.

**supervision** [fetched; the landing page did not name ByteTrack, blur or dwell explicitly] — [Roboflow supervision](https://supervision.roboflow.com/latest/)
- Object tracking with persistent IDs.
- Polygon Zone and Line Zone for counting and filtering.
- Annotators, InferenceSlicer and Detection Smoother.
- Video utilities.
- Dataset loading and conversion (YOLO, COCO, VOC) and metrics (mAP, confusion matrix).

**Multi-object tracking papers** [known-ref, not re-fetched]
- **ByteTrack** (Zhang et al., ECCV 2022): associates nearly every detection box, including low-score ones, in a second association pass. — [arXiv 2110.06864](https://arxiv.org/abs/2110.06864)
- **OC-SORT** (Cao et al., CVPR 2023): an "observation-centric" Kalman re-update that is robust to occlusion and non-linear motion. — [arXiv 2203.14360](https://arxiv.org/abs/2203.14360)
- **BoT-SORT** (Aharon et al., 2022): adds camera-motion compensation, an improved Kalman state and optional ReID to ByteTrack. It is the default tracker alongside ByteTrack in Ultralytics. — [arXiv 2206.14651](https://arxiv.org/abs/2206.14651)

**DeepStream**
- **Reconnect behaviour:**
  - Forum guidance is to use `nvurisrcbin` rather than `uridecodebin`, because uridecodebin cannot reconnect RTSP. [search-snippet] — [NVIDIA forum: RTSP reconnects](https://forums.developer.nvidia.com/t/deepstream-parallel-inference-app-add-rtsp-reconnects/301659)
  - One user had it working on DS 6.3 via `rtsp-reconnect-interval-sec` and `rtsp-reconnect-attempts`. [search-snippet] — [NVIDIA forum: Handling RTSP failures](https://forums.developer.nvidia.com/t/handling-rtsp-stream-failures-and-auto-reconnection-in-deepstream/336677)
- **Known reconnect bugs:** [search-snippet]
  - On DS 7.1 with 8 RTSP channels, `nvurisrcbin` can enter an endless reconnect loop that only an app restart fixes. — [NVIDIA forum DS 7.1 loop](https://forums.developer.nvidia.com/t/deepstream-7-1-nvurisrcbin-fails-to-recover-from-rtsp-disconnection-and-enters-infinite-reconnection-loop/379718)
  - One camera can stay frozen for good after a brief network blip. — [NVIDIA forum: stuck reconnect](https://forums.developer.nvidia.com/t/nvurisrcbin-reconnect-logic-gets-permanently-stuck-after-a-brief-rtsp-network-blip-one-camera-freezes-for-good/376544)
  - `rtsp_reconnect_interval` stops taking effect after a while. — [NVIDIA forum](https://forums.developer.nvidia.com/t/nvurisrcbin-rtsp-reconnect-interval-lose-efficacy-in-the-end/336662)
- **New nvstreammux problems:** [search-snippet]
  - One RTSP dropout cut the other streams from about 20 FPS to about 5. The legacy nvstreammux did not show this.
  - Dynamically adding sources with adaptive batching errored, and the error disappeared without nvtracker.
  - Source: [NVIDIA forum: dynamic sources new nvstreammux](https://forums.developer.nvidia.com/t/cant-add-new-rtsp-source-dynamically-using-new-nvstreammux-and-adaptative-batching/268007)
- **Streams per GPU:** NVIDIA staff say capacity depends on the platform and model load, and suggest splitting pipelines across GPUs when one GPU is saturated. A thread asking about roughly 1000 cameras per GPU ended without an answer. [search-snippet] — [NVIDIA forum: many RTSP streams](https://forums.developer.nvidia.com/t/large-number-of-rtsp-streams-nvstreammux-or-separate-pipeline-per-camera/229269)

**Frigate (NVR)**
- Frigate runs motion detection first and sends only the regions with motion to the object detector. Inference is designed for accelerators, not CPU. [fetched] — [Frigate Object Detectors](https://docs.frigate.video/configuration/object_detectors/)
- Frigate has a separate "Generative AI" section with review summaries and object descriptions. It was linked from the page but not read. [fetched (nav only)] — [Frigate Object Detectors](https://docs.frigate.video/configuration/object_detectors/)

### Inferences
- **Must-have:**
  - RTSP ingestion with auto-reconnect and per-stream health status (online, reconnecting, offline);
  - a `max_fps` sampling setting with drop-oldest frames;
  - ByteTrack tracking;
  - line-crossing counts and polygon zones;
  - an event log with webhook alerts.
  - Roboflow InferencePipeline plus supervision already covers most of this in Python, so it is the fastest route on the 3080 Ti.
- **Should-have:**
  - motion-gated inference, Frigate-style, to raise streams per GPU;
  - dwell time per zone, computed from track ID enter/exit timestamps;
  - a face- or person-blur privacy annotator;
  - NVDEC hardware decode, for example via `ffmpeg -hwaccel cuda` or DeepStream.
- **Differentiator:** VLM "event narration" on alert clips, similar to Frigate's GenAI review summaries, using the Qwen2.5-VL already on the box. Another option is a Frigate integration that pulls Frigate events or snapshots into LabelDesk for labeling and active learning.
- **Operational:** plan a supervisor and watchdog that restarts a stuck stream process. Even DeepStream's built-in reconnect fails in the field.

### Gaps
- Not fetched this session, so no citations:
  - DeepStream official docs (nvstreammux/nvtracker reference, NvDCF/NvSORT/NvDeepSORT trackers, NVDEC session limits);
  - the supervision `ByteTrack`, `BlurAnnotator`/`PixelateAnnotator` and dwell-time tutorial pages.
- No authoritative streams-per-GPU numbers for an RTX 3080 Ti. GeForce cards have NVENC session caps but not NVDEC caps. This is an unverified recollection and needs a citation.
- NVIDIA Metropolis and AWS Panorama were not researched.

---

## Q3. VLM serving: vLLM (PagedAttention), multimodal, AWQ/GPTQ, sleep mode, gpu-memory-utilization, OpenAI API, structured output; alternatives; Qwen2.5-VL grounding format; memory on 12 GB

### Takeaway
vLLM is the right default. It exposes an OpenAI-compatible server and supports AWQ/GPTQ. It now does structured outputs through `response_format` / `structured_outputs` (the old `guided_json` was removed in v0.12.0). Sleep mode can free GPU memory on demand, which is useful when sharing one GPU with training. Qwen2.5-VL emits JSON `bbox_2d` boxes in absolute pixel coordinates of the resized image. On 12 GB, `max_pixels`, `max-model-len` and `limit-mm-per-prompt` are the main memory levers.

### Cited Findings
**Sleep mode** [fetched] — [vLLM Sleep Mode](https://docs.vllm.ai/en/latest/features/sleep_mode.html)
- **Level 1** offloads weights to CPU RAM and discards the KV cache. Use it to wake the same model later.
- **Level 2** discards weights and KV cache. Use it to load a different or updated model, via `reload_weights`.
- **Enabling on a server:** `VLLM_SERVER_DEV_MODE=1` plus `--enable-sleep-mode`.
- **Endpoints:** `POST /sleep?level=1|2`, `POST /wake_up` (optional `?tags=weights|kv_cache`), `GET /is_sleeping` and `POST /release_kv_cache_memory`. CUDA-graph memory can be offloaded too.
- **Platforms:** CUDA and ROCm.
- **Latency:** the page gives no wake-up latency figures.
- The Ascend sleep-mode docs describe the same two levels. — [vLLM Ascend sleep mode](https://docs.vllm.ai/projects/ascend/en/latest/user_guide/feature_guide/sleep_mode/)

**Structured outputs** [fetched] — [vLLM Structured Outputs](https://docs.vllm.ai/en/latest/features/structured_outputs.html)
- **Backends:** `xgrammar` or `guidance`, with `auto` as the default.
- **Constraint types:** choice, regex, JSON schema (including from Pydantic), EBNF grammar and structural_tag.
- **OpenAI API usage:** pass `response_format={"type":"json_schema",...}`, or `extra_body={"structured_outputs": {...}}` for the other types. `beta.chat.completions.parse()` with a Pydantic model also works.
- **Deprecations:**
  - `guided_json`, `guided_regex`, `guided_choice`, `guided_grammar` and `guided_decoding_backend` were removed in v0.12.0.
  - `lm-format-enforcer` is deprecated as of v0.33.0 and scheduled for removal in v0.35.0.

**PagedAttention** (Kwon et al., SOSP 2023) [known-ref, not re-fetched] — [arXiv 2309.06180](https://arxiv.org/abs/2309.06180)
- Stores the KV cache in non-contiguous fixed-size blocks, like OS virtual-memory paging.
- This nearly eliminates fragmentation and enables sharing.
- The paper reports 2–4x throughput over prior systems at the same latency.

**Qwen2.5-VL grounding**
- The tech report says Qwen2.5-VL grounds objects with boxes or points and supports absolute-coordinate and JSON formats for spatial reasoning. [search-snippet] — [Qwen2.5-VL Technical Report, arXiv 2502.13923](https://arxiv.org/abs/2502.13923)
- The output schema is `{"bbox_2d": [x1,y1,x2,y2], "label": "..."}` in absolute pixel coordinates (not normalized). [search-snippet] — [LearnOpenCV: Object detection with Qwen2.5-VL](https://learnopencv.com/object-detection-with-vlms-ft-qwen2-5-vl/)
- Boxes are expressed in the coordinates of the image after resizing. Rescale using the official `smart_resize` (factor 28) to map back to the original image. [search-snippet] — [zenn.dev fine-tuning write-up](https://zenn.dev/liushuzhi/articles/5936def67dbdf4)

**Memory levers on small GPUs**
- Lower `max_pixels` in `mm_processor_kwargs` (for example 768*768) and limit images per prompt. [search-snippet] — [vLLM forum: Qwen2.5-VL-7B](https://discuss.vllm.ai/t/problem-with-qwen2-5-vl-7b/1065)
- The vLLM recipe for Qwen2.5-VL-7B bounds per-image resolution with `max_pixels` and uses `--limit-mm-per-prompt '{"image":10,"video":0}'`. [search-snippet] — [vLLM Recipes: Qwen2.5-VL-7B](https://recipes.vllm.ai/Qwen/Qwen2.5-VL-7B-Instruct)
- The default per-image token estimate is based on 28x28 patches per token, so lowering `max_pixels` shrinks the token count. [search-snippet] — [vLLM issue #20123](https://github.com/vllm-project/vllm/issues/20123)
- The Qwen docs name `--max-model-len` as the first OOM knob. [search-snippet] — [Qwen docs: vLLM deployment](https://qwen.readthedocs.io/en/v2.5/deployment/vllm.html)
- One user on a 24 GB RTX 4090 still hit CUDA OOM after setting min/max pixels. [search-snippet] — [HF discussion: VRAM requirement](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct/discussions/18)

**Alternatives** [known-ref, not re-fetched]
- **SGLang:** RadixAttention prefix caching plus a structured-generation frontend. — [arXiv 2312.07104](https://arxiv.org/abs/2312.07104)
- TGI, Ollama and LMDeploy were not researched this session.

### Inferences
- **Recommended 3080 Ti config:**
  - Qwen2.5-VL-7B-AWQ;
  - `--max-model-len` about 4096–8192;
  - `--limit-mm-per-prompt '{"image":1-2,"video":0}'`;
  - `max_pixels` about 768*768 or lower;
  - `--gpu-memory-utilization` set to leave headroom for a YOLO/SAM process (for example 0.6–0.75);
  - `--max-num-seqs` kept small.
  - These values are my estimate, not from a cited benchmark. Measure them.
- **Must-have:** VLM auto-label requests should always use the JSON-schema `response_format`, so `bbox_2d` and `label` are parsed reliably. The client must then rescale boxes from smart_resize space to original pixels.
- **Should-have:** use sleep mode (level 1) to hand the GPU to a training job and wake the VLM afterwards. It needs `VLLM_SERVER_DEV_MODE`, so do not expose those endpoints publicly.
- **Differentiator:** grounded VLM pre-labeling with prompts like "find all X", with confidence handled via SAM refinement. Qwen grounding is not calibrated, so treat it as a proposal source and not ground truth.

### Gaps
- Found no source giving exact VRAM figures for Qwen2.5-VL-7B-AWQ on 12 GB.
- Did not obtain quantitative grounding-reliability numbers (RefCOCO etc.) from the tech report. Pull them from Table(s) in [arXiv 2502.13923](https://arxiv.org/abs/2502.13923).
- No 2025–2026 comparison of SGLang, TGI, Ollama and LMDeploy for VLMs was fetched.
- Sleep-mode wake latency is not documented.

---

## Q4. GPU scheduling/sharing for mixed workloads (training + inference + LLM) on one or a few GPUs

### Takeaway
Plain time-slicing is the only sharing mode available on a GeForce RTX 3080 Ti, and it has no memory or fault isolation. MIG is limited to recent datacenter GPUs. In practice, a single 12 GB card needs application-level scheduling:
- a job queue that serializes training against the VLM;
- vLLM sleep or wake around training jobs;
- LRU loading and unloading of detector models, in the style of Triton EXPLICIT mode.

The research literature (Clockwork, AlpaServe, Gandiva) supports predictable, centrally scheduled model placement and time-slicing over naive co-location.

### Cited Findings
- **Kubernetes time-slicing** (NVIDIA GPU Operator): [fetched] — [NVIDIA GPU Operator: GPU sharing](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
  - **How it works:** one GPU is advertised as N "replicas" via a ConfigMap (`sharing.timeSlicing.resources[].replicas`).
  - **Isolation:** replicas have no memory or fault isolation.
  - **Proportionality:** requesting more than one replica does not give proportional compute.
  - **Monitoring:** DCGM can't attribute metrics to containers.
  - **Hardware:** time-slicing works on GPUs without MIG.
- **MIG:** partitions a GPU in hardware with memory and fault isolation, only on "the latest generations" of NVIDIA GPUs. [fetched] — [NVIDIA GPU Operator: GPU sharing](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
  - MIG is A100/A30/H100-class only, not GeForce. [known-ref, not re-fetched] — [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/)
- **MPS:** lets multiple processes share the GPU concurrently through a single context. [known-ref, not re-fetched] — [NVIDIA MPS docs](https://docs.nvidia.com/deploy/mps/index.html)
- **Triton EXPLICIT mode** is the building block for model multiplexing and LRU loading: load and unload via API, with background loading while other models serve. [fetched] — [Triton Model Management](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_management.html)
- **vLLM sleep level 1/2** frees VLM weights and KV cache on demand, which lets one GPU alternate between the LLM and training. [fetched] — [vLLM Sleep Mode](https://docs.vllm.ai/en/latest/features/sleep_mode.html)
- **Papers** [known-ref, not re-fetched]:
  - **Clockwork** (Gujarati et al., OSDI 2020): makes DNN inference predictable by centralizing scheduling and running one model at a time per GPU, to meet tail-latency SLOs. — [USENIX OSDI '20](https://www.usenix.org/conference/osdi20/presentation/gujarati)
  - **AlpaServe** (Li et al., OSDI 2023): uses model parallelism to statistically multiplex several models across GPUs and absorb bursty traffic. — [arXiv 2302.11665](https://arxiv.org/abs/2302.11665)
  - **Gandiva** (Xiao et al., OSDI 2018): time-slicing, suspend-resume and migration for deep-learning training jobs on GPU clusters. — [USENIX OSDI '18](https://www.usenix.org/conference/osdi18/presentation/xiao)

### Inferences
- **Must-have (single GPU demo):**
  - a single GPU job queue (training, batch auto-label, live stream) with priorities;
  - training jobs trigger `POST /sleep?level=1` on vLLM and `/wake_up` afterwards;
  - detector models are loaded LRU with a VRAM budget.
- **Should-have:** expose GPU state (VRAM used, active job, sleeping models) in the admin UI, and refuse or queue jobs that would OOM.
- **Differentiator / later:** Kubernetes with GPU Operator time-slicing, or Ray Serve multiplexing, once there are multiple GPUs. MIG only matters if datacenter GPUs are rented.
- **Not worth it on the 3080 Ti:** MPS between the trainer and vLLM. There is no memory isolation, and vLLM pre-allocates via `gpu-memory-utilization`, so OOM risk stays.

### Gaps
- Not fetched: Ray Serve model multiplexing docs, Run:ai fractional GPU docs, and MPS behaviour/limits on GeForce Ampere. No citations were gathered for these.
- No quantitative measurements found of vLLM wake-up time, or of co-running YOLO training with vLLM on a 12 GB card.
