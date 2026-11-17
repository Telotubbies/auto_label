"""Inference catalogue: the one server-owned list of engine pins and GPU presets (T-1002).

Every engine row carries an exact version and the release page it was read from, and every
container is digest-pinned, so no client string can become a shell argument and no two screens
can disagree about a version. ``install_spec`` is the only place an install command is built,
and it is derived from the pins below: there is no ``extra_args`` and no user-supplied input.
A pin that cannot be verified stays out of the catalogue rather than shipping as ``latest``.

Numbers and digests were read from the engine's own release page or registry on ``checked_on``.
"""

import re

VERSION = re.compile(r"^[0-9][0-9A-Za-z.+_-]*$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
# T-1023: the engine's own health endpoint, read by the worker on its loopback only. It is never
# part of a public row, so no screen and no API client can call it.
OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/api/version"

# One row per installable engine. `runtimes` lists only runtimes we can install without a
# floating tag; `container` is a repo@sha256 digest, and `package` an exact pip requirement.
ENGINES: list[dict] = [
    {
        "id": "ollama",
        "name": "Ollama",
        "summary": "Runs quantised models on one host with one command; the default engine.",
        "version": "0.40.16",
        "default": True,
        "runtimes": ["docker"],
        "os": ["linux", "macos", "windows"],
        "accelerator": ["cpu", "nvidia", "metal"],
        "min_driver": None,
        "cuda_min": None,
        "cuda_max": None,
        "disk_mb": 3240,
        "package": None,
        "container": "ollama/ollama@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592",
        "health_url": OLLAMA_HEALTH_URL,
        "source_url": "https://github.com/ollama/ollama/releases/tag/v0.40.16",
        "checked_on": "2026-11-17",
        "notes": "Bundles its own CUDA and Metal runtimes, so there is no separate driver pin. "
                 "The 3.2 GB figure is the image; the model file is counted with the model.",
    },
    {
        "id": "vllm",
        "name": "vLLM",
        "summary": "High-throughput serving for Hugging Face models, with an OpenAI-compatible API.",
        "version": "0.34.0",
        "default": False,
        "runtimes": ["uv", "pip", "docker"],
        "os": ["linux"],
        "accelerator": ["nvidia"],
        "min_driver": "575.51",
        "cuda_min": "12.8",
        "cuda_max": "13.2",
        "disk_mb": 10774,
        "package": "vllm==0.34.0",
        "container": "vllm/vllm-openai@sha256:20fdb089454afbb324efa4110a2c025ff7b27cc1a086e07aa580b18df8ad1ce1",
        "source_url": "https://pypi.org/project/vllm/0.34.0/",
        "checked_on": "2026-11-17",
        "notes": "The release ships CUDA 12.8, 12.9 and 13.2 builds; the driver floor is the "
                 "CUDA 12.9 one, so an older driver needs the forward-compatibility libraries.",
    },
    {
        "id": "llamacpp",
        "name": "llama.cpp",
        "summary": "Runs GGUF files on CPU, Metal, Vulkan or CUDA; the smallest footprint.",
        "version": "1.0.0",
        "default": False,
        "runtimes": ["uv", "pip"],
        "os": ["linux", "macos", "windows"],
        "accelerator": ["cpu", "metal", "nvidia", "vulkan"],
        "min_driver": None,
        "cuda_min": None,
        "cuda_max": None,
        "disk_mb": 1200,
        "package": "llama-cpp-python[server]==0.3.37",
        "container": None,
        "source_url": "https://github.com/ggml-org/llama.cpp/releases/tag/v1.0.0",
        "checked_on": "2026-11-17",
        "notes": "GGUF models only and no CUDA requirement. The pip runtime is the "
                 "llama-cpp-python server; no container tag is digest-pinned yet, so docker "
                 "is not offered.",
    },
    {
        "id": "sglang",
        "name": "SGLang",
        "summary": "Fast serving for structured output, long context and multi-turn prompts.",
        "version": "0.5.23",
        "default": False,
        "runtimes": ["uv", "pip", "docker"],
        "os": ["linux"],
        "accelerator": ["nvidia"],
        "min_driver": "580.65",
        "cuda_min": "13.0",
        "cuda_max": None,
        "disk_mb": 15365,
        "package": "sglang[all]==0.5.23",
        "container": "lmsysorg/sglang@sha256:f832b5c39559c9caa900b22ad37c76fcce66470676855c42052102c537812f1f",
        "source_url": "https://pypi.org/project/sglang/0.5.23/",
        "checked_on": "2026-11-17",
        "notes": "Needs CUDA 13: CUDA 12 wheels and images stopped at 0.5.19.",
    },
    {
        "id": "tensorrtllm",
        "name": "TensorRT-LLM",
        "summary": "NVIDIA's fastest path, at the cost of one compiled engine per GPU.",
        "version": "1.2.1",
        "default": False,
        "runtimes": ["docker"],
        "os": ["linux"],
        "accelerator": ["nvidia"],
        "min_driver": "580.65",
        "cuda_min": "13.0",
        "cuda_max": "13.0",
        "disk_mb": 19970,
        "package": None,
        "container": "nvcr.io/nvidia/tensorrt-llm/release@sha256:33cd085b772947bd22b7273886539331420404e5d2a4a039945241945ff927b9",
        "source_url": "https://github.com/NVIDIA/TensorRT-LLM/releases/tag/v1.2.1",
        "checked_on": "2026-11-17",
        "notes": "Strict driver, CUDA and TensorRT match, and one built engine per GPU. The "
                 "pinned image carries CUDA 13.0 and TensorRT 10.14.1; pip is not offered.",
    },
    {
        "id": "onnxruntime",
        "name": "ONNX Runtime GenAI",
        "summary": "Serves ONNX models on CPU, NVIDIA or DirectML without a CUDA toolkit.",
        "version": "0.20.0",
        "default": False,
        "runtimes": ["uv", "pip"],
        "os": ["linux", "macos", "windows"],
        "accelerator": ["cpu", "nvidia", "directml"],
        "min_driver": None,
        "cuda_min": None,
        "cuda_max": None,
        "disk_mb": 1500,
        "package": "onnxruntime-genai==0.20.0",
        "container": None,
        "source_url": "https://pypi.org/project/onnxruntime-genai/0.20.0/",
        "checked_on": "2026-11-17",
        "notes": "LLM serving needs onnxruntime-genai, not onnxruntime alone. DirectML is "
                 "Windows only, and no container tag is digest-pinned yet.",
    },
    {
        "id": "triton",
        "name": "Triton Inference Server",
        "summary": "Serves many models behind one endpoint; the NVIDIA server, not the compiler.",
        "version": "2.74.0",
        "default": False,
        "runtimes": ["docker"],
        "os": ["linux"],
        "accelerator": ["nvidia"],
        "min_driver": "580.65",
        "cuda_min": "13.0",
        "cuda_max": "13.9",
        "disk_mb": 9012,
        "package": None,
        "container": "nvcr.io/nvidia/tritonserver@sha256:b404f7de5dbeeefe0b17d7d149745a50d0989a25d0d831433b5ba63c716c2fcd",
        "source_url": "https://github.com/triton-inference-server/server/releases/tag/v2.74.0",
        "checked_on": "2026-11-17",
        "notes": "The pinned image is the 26.10 release, which reports server 2.74.0 on CUDA 13. "
                 "Not to be confused with the OpenAI Triton compiler of the same name.",
    },
]

# One row per calculator preset; the numbers are the vendor's rounded figures, and `cpu` is
# the only row with no vendor. `Custom` is the screen's own last entry, not a row here.
GPUS: list[dict] = [
    {"id": "rtx4090", "name": "RTX 4090 24 GB", "vram_gb": 24, "bw_gbs": 1008, "fp16_tflops": 165,
     "source_url": "https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4090/"},
    {"id": "a100_80", "name": "A100 80 GB", "vram_gb": 80, "bw_gbs": 2039, "fp16_tflops": 312,
     "source_url": "https://www.nvidia.com/en-us/data-center/a100/"},
    {"id": "h100_80", "name": "H100 80 GB", "vram_gb": 80, "bw_gbs": 3350, "fp16_tflops": 989,
     "source_url": "https://www.nvidia.com/en-us/data-center/h100/"},
    {"id": "l40s", "name": "L40S 48 GB", "vram_gb": 48, "bw_gbs": 864, "fp16_tflops": 181,
     "source_url": "https://www.nvidia.com/en-us/data-center/l40s/"},
    {"id": "l4", "name": "L4 24 GB", "vram_gb": 24, "bw_gbs": 300, "fp16_tflops": 121,
     "source_url": "https://www.nvidia.com/en-us/data-center/l4/"},
    {"id": "t4", "name": "T4 16 GB", "vram_gb": 16, "bw_gbs": 320, "fp16_tflops": 65,
     "source_url": "https://www.nvidia.com/en-us/data-center/tesla-t4/"},
    {"id": "rtx3090", "name": "RTX 3090 24 GB", "vram_gb": 24, "bw_gbs": 936, "fp16_tflops": 71,
     "source_url": "https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3090/"},
    {"id": "a6000", "name": "RTX A6000 48 GB", "vram_gb": 48, "bw_gbs": 768, "fp16_tflops": 77,
     "source_url": "https://www.nvidia.com/en-us/design-visualization/rtx-a6000/"},
    {"id": "rtx6000ada", "name": "RTX 6000 Ada 48 GB", "vram_gb": 48, "bw_gbs": 960, "fp16_tflops": 91,
     "source_url": "https://www.nvidia.com/en-us/design-visualization/rtx-6000/"},
    {"id": "orin64", "name": "Jetson AGX Orin 64 GB", "vram_gb": 64, "bw_gbs": 204, "fp16_tflops": 85,
     "source_url": "https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/"},
    {"id": "cpu", "name": "CPU only", "vram_gb": 0, "bw_gbs": 0, "fp16_tflops": 0, "source_url": None},
]

_BY_ID = {row["id"]: row for row in ENGINES}
_GPU_BY_ID = {row["id"]: row for row in GPUS}
PUBLIC_ENGINE_FIELDS = ("id", "name", "summary", "version", "default", "runtimes", "os",
                        "accelerator", "min_driver", "cuda_min", "cuda_max", "disk_mb",
                        "source_url", "checked_on", "notes")
PUBLIC_GPU_FIELDS = ("id", "name", "vram_gb", "bw_gbs", "fp16_tflops", "source_url")


def engine(engine_id: str) -> dict:
    """The full row for ``engine_id``; unknown ids raise ``KeyError`` — there is no fallback."""
    return _BY_ID[engine_id]


def gpu(gpu_id: str) -> dict:
    """The row for ``gpu_id``; unknown ids raise ``KeyError``."""
    return _GPU_BY_ID[gpu_id]


def install_spec(engine_id: str, runtime: str) -> dict:
    """The install command for one engine and runtime, built only from the verified pins.

    Unknown engines and runtimes the engine does not offer raise ``KeyError``. This is the only
    place an argv exists; an engine that is not pinned by digest cannot offer ``docker``.
    """
    row = engine(engine_id)
    if runtime not in row["runtimes"]:
        raise KeyError(f"{engine_id} does not offer the {runtime} runtime")
    if runtime == "docker":
        if not row["container"]:
            raise KeyError(f"{engine_id} has no digest-pinned container")
        argv = ["docker", "pull", row["container"]]
    else:
        if not row["package"]:
            raise KeyError(f"{engine_id} has no pinned package")
        argv = (["uv", "pip", "install", row["package"]] if runtime == "uv"
                else ["pip", "install", row["package"]])
    return {"engine": engine_id, "version": row["version"], "runtime": runtime,
            "package": row["package"], "container": row["container"], "argv": argv}


def public_catalog() -> dict:
    """What every screen reads: no argv, no package, no container digest."""
    return {
        "engines": [{field: row[field] for field in PUBLIC_ENGINE_FIELDS} for row in ENGINES],
        "gpus": [{field: row[field] for field in PUBLIC_GPU_FIELDS} for row in GPUS],
        "sources": sorted({row["source_url"] for row in (*ENGINES, *GPUS) if row["source_url"]}),
    }


def validate() -> None:
    """Raise ``ValueError`` if a row could ship a floating pin or a mystery preset."""
    ids = [row["id"] for row in ENGINES]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate engine ids")
    if ENGINES[0]["id"] != "ollama" or ENGINES[0].get("default") is not True:
        raise ValueError("ollama must be the first engine and the default")
    if [row["id"] for row in ENGINES if row.get("default")] != ["ollama"]:
        raise ValueError("exactly one engine may be the default")
    if not str(ENGINES[0].get("health_url") or "").startswith("http://127.0.0.1:"):
        raise ValueError("the ollama health check must be on the worker's loopback")
    for row in ENGINES:
        if not VERSION.match(row["version"]) or "latest" in row["version"].lower():
            raise ValueError(f"{row['id']}: version is not an exact pin")
        if not str(row["source_url"]).startswith("https://"):
            raise ValueError(f"{row['id']}: no source url")
        if row["container"] and not DIGEST.search(row["container"]):
            raise ValueError(f"{row['id']}: container is not digest-pinned")
        if "docker" in row["runtimes"] and not row["container"]:
            raise ValueError(f"{row['id']}: docker offered without a digest")
        if any(runtime not in ("uv", "pip", "docker") for runtime in row["runtimes"]):
            raise ValueError(f"{row['id']}: unknown runtime")
        if not row["disk_mb"] or row["disk_mb"] < 0:
            raise ValueError(f"{row['id']}: no disk estimate")
    gpu_ids = [row["id"] for row in GPUS]
    if len(set(gpu_ids)) != len(gpu_ids):
        raise ValueError("duplicate gpu ids")
    for row in GPUS:
        if row["id"] != "cpu" and not (row["vram_gb"] > 0 and row["bw_gbs"] > 0 and row["fp16_tflops"] > 0):
            raise ValueError(f"{row['id']}: missing vendor numbers")
        if row["id"] != "cpu" and not str(row["source_url"]).startswith("https://"):
            raise ValueError(f"{row['id']}: no source url")
    return None
