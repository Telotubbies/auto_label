"""VRAM and throughput estimate: one pure answer over validated inputs (T-1004).

The formulas are PLAN §2.3, the GPU presets and engine ids come from the T-1002 catalogue, and
nothing here reads or writes the database. The engine overhead and usable-fraction defaults live
here because the catalogue rows carry install facts, not serving defaults.
"""

from math import isfinite
from typing import Literal

from pydantic import BaseModel

from . import inference_catalog

GIB = 1024 ** 3
MIB = 1024 ** 2
PLAN_SOURCES = [
    "https://blog.eleuther.ai/transformer-math/",
    "https://kipp.ly/transformer-inference-arithmetic/",
    "https://docs.vllm.ai/en/latest/configuration/conserving_memory.html",
]

# PLAN §2.3 items 1-2 and the card's GGUF bit figures (8.5 and 4.8 bits per weight).
BYTES_PER_WEIGHT = {
    "fp32": 4.0, "bf16": 2.0, "fp16": 2.0, "fp8": 1.0, "int8": 1.0, "int4": 0.5,
    "gguf_q8": 1.0625, "gguf_q4_k_m": 0.6,
}

# PLAN §2.3 item 5. The catalogue does not carry a serving overhead, so the measured figures
# live with the formula they feed. ONNX Runtime and Triton have no published figure: 1 GiB.
ENGINE_OVERHEAD_GIB = {
    "ollama": 0.5, "vllm": 2.0, "llamacpp": 0.5, "sglang": 1.5,
    "tensorrtllm": 2.0, "onnxruntime": 1.0, "triton": 1.0,
}
# PLAN §2.3 item 6: vLLM's gpu_memory_utilization default, llama.cpp has no such knob.
ENGINE_USABLE = {
    "ollama": 0.95, "vllm": 0.9, "llamacpp": 0.95, "sglang": 0.9,
    "tensorrtllm": 0.9, "onnxruntime": 0.95, "triton": 0.9,
}

Quant = Literal["fp32", "bf16", "fp16", "fp8", "int8", "int4", "gguf_q8", "gguf_q4_k_m"]


class ModelIn(BaseModel):
    params_b: float
    active_params_b: float | None = None
    layers: int
    kv_heads: int
    head_dim: int


class GpuIn(BaseModel):
    preset: str | None = None
    vram_gb: float | None = None
    bw_gbs: float | None = None
    fp16_tflops: float | None = None


class EstimateIn(BaseModel):
    model: ModelIn
    quant: Quant
    context: int
    batch: int
    users: int = 1
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    gpu: GpuIn
    gpu_count: int = 1
    tensor_parallel: int = 1
    engine: str
    usable: float | None = None


def _bound(value: float) -> str:
    """A range endpoint as a reader expects it: 0.01, 200, 1,000,000."""
    if float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:g}"


def _number(value, label: str, low: float, high: float) -> float:
    """A finite number in range, or a 422 sentence that names the field."""
    if value is None or not isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    if value < low or value > high:
        raise ValueError(f"{label} must be between {_bound(low)} and {_bound(high)}.")
    return float(value)


def _gpu(body: EstimateIn) -> dict:
    """The preset row, or the custom numbers; a preset's custom fields are ignored."""
    gpu = body.gpu
    if gpu.preset not in (None, "custom"):
        try:
            row = inference_catalog.gpu(gpu.preset)
        except KeyError:
            raise ValueError("Unknown GPU preset.") from None
        if row["vram_gb"] <= 0 or row["bw_gbs"] <= 0 or row["fp16_tflops"] <= 0:
            raise ValueError("GPU VRAM, bandwidth and FP16 TFLOPS must be positive.")
        return row
    for value, label in ((gpu.vram_gb, "Custom VRAM"), (gpu.bw_gbs, "Custom bandwidth"),
                         (gpu.fp16_tflops, "Custom FP16 TFLOPS")):
        if value is None or not isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be a positive number.")
    return {"name": "custom GPU", "vram_gb": gpu.vram_gb, "bw_gbs": gpu.bw_gbs,
            "fp16_tflops": gpu.fp16_tflops}


def _engine(body: EstimateIn) -> tuple[float, float]:
    try:
        inference_catalog.engine(body.engine)
    except KeyError:
        raise ValueError("Unknown engine.") from None
    return ENGINE_OVERHEAD_GIB[body.engine], ENGINE_USABLE[body.engine]


def _assumptions(body: EstimateIn, gpu: dict, sequences: int, tp: int,
                 overhead: float, usable: float, prompt: int) -> list[str]:
    """Every default and factor the answer used, with its value, so nothing hides in the maths."""
    active = body.model.active_params_b or body.model.params_b
    return [
        f"Weights: {body.quant} at {BYTES_PER_WEIGHT[body.quant]:.4g} bytes per weight.",
        f"KV cache: {1.0 if body.quant == 'fp8' else 2.0:.0f} bytes per element and "
        f"2 × {body.model.layers} layers × {body.model.kv_heads} KV heads × "
        f"{body.model.head_dim} head dim bytes per token.",
        f"Concurrent sequences: batch {body.batch} × concurrent users {body.users} = {sequences}.",
        f"Activations: max(5% of total weights, 256 MiB) × (1 + 0.02 × {sequences}) per GPU.",
        f"Framework overhead: {body.engine} {overhead:.1f} GiB per GPU.",
        f"Usable VRAM: {usable:.2f} × {gpu['vram_gb']:g} GB per GPU (default from {body.engine}).",
        "Decode: 70% of peak bandwidth and 25% of FP16 TFLOPS; prefill: 40% MFU.",
        "Estimate: 0.8 × min(memory-bound, compute-bound); range 0.6–1.2 × estimate.",
        f"Time to first token: 2 × {active:g}B active params × {prompt} prompt tokens, TP {tp}; "
        "the attention term is omitted.",
        "Activations and framework overhead are heuristics, not measurements (PLAN §2.3 items 4–5).",
        f"Working set: weights / {tp} + KV / {tp} + activations + overhead per GPU.",
    ]


def _memory(weights_b: float, kv_b: float, sequences: int, tp: int, overhead: float,
            usable: float, vram_gb: float) -> tuple[float, float, float]:
    """Activations, total per GPU and usable VRAM: PLAN §2.3 items 4–6, in one place."""
    activations_b = max(0.05 * weights_b, 256 * MIB) * (1 + 0.02 * sequences)
    total_b = weights_b / tp + kv_b / tp + activations_b + overhead * GIB
    usable_b = usable * vram_gb * GIB
    return activations_b, total_b, usable_b


def fit(params_b: float, quant: Quant, engine: str, layers: float, kv_heads: float,
        head_dim: float, context: float, vram_gb: float, sequences: int = 1) -> dict:
    """The memory verdict for one catalogue variant on one GPU; the catalogue's fit check.

    Same formulas as :func:`estimate`, with tensor parallel 1 and no throughput: a catalogue row
    asks only whether the weights, KV and overhead fit the card.
    """
    if quant not in BYTES_PER_WEIGHT:
        raise ValueError("Unknown quantisation.")
    if engine not in ENGINE_OVERHEAD_GIB:
        raise ValueError("Unknown engine.")
    weights_b = params_b * 1e9 * BYTES_PER_WEIGHT[quant]
    kv_b = (2 * layers * kv_heads * head_dim * (1.0 if quant == "fp8" else 2.0)
            * context * sequences)
    _, total_b, usable_b = _memory(weights_b, kv_b, sequences, 1, ENGINE_OVERHEAD_GIB[engine],
                                   ENGINE_USABLE[engine], vram_gb)
    short = (total_b - usable_b) / GIB
    return {"fits": total_b <= usable_b, "total_gb": round(total_b / GIB, 2),
            "usable_gb": round(usable_b / GIB, 2), "shortfall_gb": round(max(0.0, short), 1),
            "verdict": (f"Fits with {-short:.1f} GB spare." if short <= 0
                        else f"Does not fit: {short:.1f} GB short.")}


def estimate(body: EstimateIn) -> dict:
    """The per-GPU memory, fits verdict, decode ceilings and TTFT for one validated request."""
    model = body.model
    params = _number(model.params_b, "Parameters", 0.01, 2000.0)
    active = _number(model.active_params_b if model.active_params_b is not None else params,
                     "Active parameters", 0.01, 2000.0)
    layers = _number(model.layers, "Layers", 1, 200)
    kv_heads = _number(model.kv_heads, "KV heads", 1, 256)
    head_dim = _number(model.head_dim, "Head dim", 8, 512)
    context = _number(body.context, "Context", 128, 1_000_000)
    batch = _number(body.batch, "Batch", 1, 1024)
    if body.users is None or not isfinite(body.users) or body.users < 1:
        raise ValueError("Concurrent users must be at least 1.")
    if body.users > 10_000:
        raise ValueError("Concurrent users must be at most 10,000.")
    users = float(body.users)
    gpu_count = _number(body.gpu_count, "GPU count", 1, 64)
    tp = _number(body.tensor_parallel, "Tensor parallel", 1, gpu_count)
    if int(kv_heads) % int(tp):
        raise ValueError(f"KV heads ({int(kv_heads)}) must divide by tensor parallel ({int(tp)}).")
    if body.prompt_tokens is not None:
        prompt = _number(body.prompt_tokens, "Prompt tokens", 1, 1_000_000)
    else:
        prompt = context
    if body.output_tokens is not None:
        _number(body.output_tokens, "Output tokens", 1, 1_000_000)
    gpu = _gpu(body)
    overhead, default_usable = _engine(body)
    usable = _number(body.usable if body.usable is not None else default_usable,
                     "Usable fraction", 0.5, 1.0)

    sequences = int(batch) * int(users)
    weights_b = params * 1e9 * BYTES_PER_WEIGHT[body.quant]
    kv_token_b = 2 * layers * kv_heads * head_dim * (1.0 if body.quant == "fp8" else 2.0)
    kv_b = kv_token_b * context * sequences
    activations_b, total_b, usable_b = _memory(weights_b, kv_b, sequences, int(tp), overhead,
                                               usable, gpu["vram_gb"])
    overhead_b = overhead * GIB
    fits = total_b <= usable_b

    memory_tps = sequences * 0.7 * gpu["bw_gbs"] * 1e9 / ((weights_b + kv_b) / tp)
    compute_tps = tp * gpu["fp16_tflops"] * 1e12 * 0.25 / (2 * active * 1e9)
    estimate_tps = 0.8 * min(memory_tps, compute_tps)
    ttft_ms = (2 * active * 1e9 * prompt) / (tp * gpu["fp16_tflops"] * 1e12 * 0.4) * 1000

    if fits:
        verdict = f"Fits on this card with {(usable_b - total_b) / GIB:.1f} GB spare."
    else:
        verdict = f"Does not fit: {(total_b - usable_b) / GIB:.1f} GB short."

    return {
        "per_gpu": {
            "weights_gb": round(weights_b / tp / GIB, 3),
            "kv_gb": round(kv_b / tp / GIB, 3),
            "activations_gb": round(activations_b / GIB, 3),
            "overhead_gb": round(overhead_b / GIB, 3),
            "total_gb": round(total_b / GIB, 3),
            "usable_gb": round(usable_b / GIB, 3),
        },
        "total_gb": round(total_b * gpu_count / GIB, 3),
        "fits": fits,
        "verdict": verdict,
        "throughput": {
            "memory_bound_tps": round(memory_tps, 2),
            "compute_bound_tps": round(compute_tps, 2),
            "estimate_tps": round(estimate_tps, 2),
            "low_tps": round(estimate_tps * 0.6, 2),
            "high_tps": round(estimate_tps * 1.2, 2),
        },
        "ttft_ms": round(ttft_ms, 1),
        "assumptions": _assumptions(body, gpu, sequences, int(tp), overhead, usable, int(prompt)),
        "sources": list(PLAN_SOURCES),
    }
