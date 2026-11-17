"""Model catalogue: the one server-owned list of downloadable weights (T-1010).

Every row names the exact repository commit its bytes were read from, the licence the weights
carry and whether Hugging Face gates the repo. A variant is one quantisation of a row: its files,
their pinned sizes and, for LFS files, the sha256 the worker verifies. Nothing here performs a
fetch; the plan is pure and the download job (T-1011) executes on the worker.

The fit verdict is the T-1004 estimator and the disk refusal is one 20% margin, so the catalogue
never carries a second formula. A repo id is always ``owner/name``: no URL, no path and no user
string can reach a download. Rows were read from the Hugging Face API on ``checked_on`` and the
worker's live metadata wins at download time; the log states any difference.

Owner decision PLAN §12: the catalogue lists the Ollama tag for each model next to the Hugging
Face files, and one host holds at most one downloaded model.
"""

import hashlib
import json
import re

from . import inference_estimate

GIB = 1024 ** 3
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
PICKLE = (".bin", ".pt", ".pth", ".pkl", ".pickle", ".ckpt")
# The working context a catalogue fit verdict assumes; the calculator is where another is tried.
FIT_CONTEXT = 4096
DISK_MARGIN = 0.8
TOKEN_BLOCK = ("This model needs a Hugging Face token on the worker. "
               "Set `HF_TOKEN` there, not here.")
PICKLE_BLOCK = ("This variant ships a pickle weight (.bin/.pt); only safetensors and GGUF "
                "files are offered.")
# The estimator's quantisation vocabulary; a 4-bit repack is INT4 and Q4_0 is the closest GGUF row.
QUANT = {"BF16": "bf16", "FP8": "fp8", "AWQ": "int4", "GPTQ": "int4",
         "Q8_0": "gguf_q8", "Q4_K_M": "gguf_q4_k_m", "Q4_0": "gguf_q4_k_m"}
# A licence name containing this word must carry the non-commercial badge.
NON_COMMERCIAL = ("NON-COMMERCIAL", "NONCOMMERCIAL", "AGPL", "RESEARCH ONLY")
# T-1023: an Ollama tag is `name:tag`, lower-case, and never a client string that becomes a command.
TAG = re.compile(r"^[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*$")
ONE_MODEL = ("This host already holds {model}. One model per host: remove the current model "
             "first, or replace it in one confirmed step.")



class InvalidRepo(ValueError):
    """A repo id, revision or variant that would not name a catalogue download."""


def _files(*rows: tuple) -> list[dict]:
    return [{"path": path, "bytes": size, "sha256": sha} for path, size, sha in rows]


def _variant(variant_id: str, quant: str, fmt: str, engine: str, repo: str, revision: str,
             files: list[dict]) -> dict:
    return {"id": variant_id, "quant": quant, "format": fmt, "engine": engine, "repo": repo,
            "revision": revision, "bytes": sum(file["bytes"] for file in files), "files": files}


MODELS: list[dict] = [
    {
        "id": "qwen2.5-vl-7b", "name": "Qwen2.5-VL 7B Instruct", "family": "Qwen2.5-VL",
        "repo": "Qwen/Qwen2.5-VL-7B-Instruct", "revision": "cc594898137f460bfe9f0759e9844b3ce807cfb5",
        "ollama_tag": "qwen2.5vl:7b",
        "params_b": 8.3, "layers": 28, "kv_heads": 4, "head_dim": 128, "context_max": 128000,
        "licence": {"name": "Apache-2.0",
                    "url": "https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct/blob/main/LICENSE",
                    "gated": False, "non_commercial": False},
        "engine": ["vllm"], "safetensors_only": True,
        "source_url": "https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct",
        "checked_on": "2026-11-18",
        "variants": [
            _variant("bf16", "BF16", "safetensors", "vllm",
                     "Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5",
                     _files(("chat_template.json", 1050, None),
                            ("config.json", 1374, None),
                            ("generation_config.json", 216, None),
                            ("merges.txt", 1671839, None),
                            ("model-00001-of-00005.safetensors", 3900233256,
                             "e97b877e47fde53a6c6e77aafb36e58e91ee9d95c4a3eeac6f1b5c0e6a1c986e"),
                            ("model-00002-of-00005.safetensors", 3864726320,
                             "a9a300a43b4724eee2abe7c18ceb26768d0ab011eb0cad19d9bfd2476a24d024"),
                            ("model-00003-of-00005.safetensors", 3864726424,
                             "111223d173e00bbee81cba1216fad28668df3476706b7fd26f4d5b50f8b3a507"),
                            ("model-00004-of-00005.safetensors", 3864733680,
                             "ef47f634fa57d46ee134edcc09f34085a47da1e16c12a2abe0d67118be6d72ed"),
                            ("model-00005-of-00005.safetensors", 1089994880,
                             "0c859795ad3a627a9b95bcb762e059d5b768a4a36fdd4affeff269d93fdecc67"),
                            ("model.safetensors.index.json", 57619, None),
                            ("preprocessor_config.json", 350, None),
                            ("tokenizer.json", 7031645, None),
                            ("tokenizer_config.json", 5702, None),
                            ("vocab.json", 2776833, None))),
            _variant("awq", "AWQ", "safetensors", "vllm",
                     "Qwen/Qwen2.5-VL-7B-Instruct-AWQ", "536a35794df8831aa814970ee8f89eff577e7718",
                     _files(("added_tokens.json", 605, None),
                            ("chat_template.json", 1049, None),
                            ("config.json", 1415, None),
                            ("generation_config.json", 249, None),
                            ("merges.txt", 1671853, None),
                            ("model-00001-of-00002.safetensors", 3982163944,
                             "4f75e3de726546ee43620d1227d3596cd3ba0fdd19f11faeea71de578d2d1052"),
                            ("model-00002-of-00002.safetensors", 2941808440,
                             "dae4128bbfd2b8d489e838048edc0bbe6e31f269d9b96fa3effe11cc534b8f0c"),
                            ("model.safetensors.index.json", 89593, None),
                            ("preprocessor_config.json", 575, None),
                            ("special_tokens_map.json", 613, None),
                            ("tokenizer.json", 11422063,
                             "5eee858c5123a4279c3e1f7b81247343f356ac767940b2692a928ad929543214"),
                            ("tokenizer_config.json", 5776, None),
                            ("vocab.json", 2776833, None))),
        ],
    },
    {
        "id": "qwen3-vl-8b", "name": "Qwen3-VL 8B Instruct", "family": "Qwen3-VL",
        "repo": "Qwen/Qwen3-VL-8B-Instruct", "revision": "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b",
        "ollama_tag": "qwen3-vl:8b",
        "params_b": 8.8, "layers": 36, "kv_heads": 8, "head_dim": 128, "context_max": 262144,
        "licence": {"name": "Apache-2.0",
                    "url": "https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct/blob/main/LICENSE",
                    "gated": False, "non_commercial": False},
        "engine": ["vllm"], "safetensors_only": True,
        "source_url": "https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct",
        "checked_on": "2026-11-18",
        "variants": [
            _variant("bf16", "BF16", "safetensors", "vllm",
                     "Qwen/Qwen3-VL-8B-Instruct", "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b",
                     _files(("chat_template.json", 5499, None),
                            ("config.json", 1474, None),
                            ("generation_config.json", 269, None),
                            ("merges.txt", 1671839, None),
                            ("model-00001-of-00004.safetensors", 4902275944,
                             "d5d0aef0eb170fc7453a296c43c0849a56f510555d3588e4fd662bb35490aefa"),
                            ("model-00002-of-00004.safetensors", 4915962496,
                             "8be88fb5501e4d5719a6d4cc212e6a13480330e74f3e8c77daa1a68f199106b5"),
                            ("model-00003-of-00004.safetensors", 4999831048,
                             "83de00eafe6e0d57ccd009dbcf71c9974d74df2f016c27afb7e95aafd16b2192"),
                            ("model-00004-of-00004.safetensors", 2716270024,
                             "0a88b98e9f96270973f567e6a2c103ede6ccdf915ca3075e21c755604d0377a5"),
                            ("model.safetensors.index.json", 67759, None),
                            ("preprocessor_config.json", 390, None),
                            ("tokenizer.json", 7032403, None),
                            ("tokenizer_config.json", 10868, None),
                            ("video_preprocessor_config.json", 385, None),
                            ("vocab.json", 2776833, None))),
            _variant("fp8", "FP8", "safetensors", "vllm",
                     "Qwen/Qwen3-VL-8B-Instruct-FP8", "9cdc6310a8cb770ce18efaf4e9935334512aee45",
                     _files(("chat_template.json", 5497, None),
                            ("config.json", 12005, None),
                            ("generation_config.json", 241, None),
                            ("model-00001-of-00002.safetensors", 5363407552,
                             "e2dea2e85e643ef7045c31a485a426631a1e0a84e463f8b2c7e9c6682a06eafd"),
                            ("model-00002-of-00002.safetensors", 5226891960,
                             "3dc64ec934af27a7007d265014e907aff9e16658d409e5cd4cf79869bf2bd8c1"),
                            ("model.safetensors.index.json", 94475, None),
                            ("preprocessor_config.json", 336, None),
                            ("tokenizer.json", 10179867, None),
                            ("tokenizer_config.json", 10868, None),
                            ("video_preprocessor_config.json", 331, None),
                            ("vocab.json", 4957462, None))),
        ],
    },
    {
        "id": "llama-3.1-8b", "name": "Llama 3.1 8B Instruct", "family": "Llama 3.1",
        "repo": "meta-llama/Llama-3.1-8B-Instruct",
        "revision": "0e9e39f249a16976918f6564b8830bc894c89659", "ollama_tag": "llama3.1:8b",
        "params_b": 8.03, "layers": 32, "kv_heads": 8, "head_dim": 128, "context_max": 131072,
        "licence": {"name": "Llama 3.1 Community License",
                    "url": "https://llama.meta.com/llama3_1/license/",
                    "gated": True, "non_commercial": False},
        "engine": ["vllm"], "safetensors_only": True,
        "source_url": "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
        "checked_on": "2026-11-18",
        "variants": [
            _variant("bf16", "BF16", "safetensors", "vllm",
                     "meta-llama/Llama-3.1-8B-Instruct", "0e9e39f249a16976918f6564b8830bc894c89659",
                     _files(("config.json", 855, None),
                            ("generation_config.json", 184, None),
                            ("model-00001-of-00004.safetensors", 4976698672,
                             "2b1879f356aed350030bb40eb45ad362c89d9891096f79a3ab323d3ba5607668"),
                            ("model-00002-of-00004.safetensors", 4999802720,
                             "09d433f650646834a83c580877bd60c6d1f88f7755305c12576b5c7058f9af15"),
                            ("model-00003-of-00004.safetensors", 4915916176,
                             "fc1cdddd6bfa91128d6e94ee73d0ce62bfcdb7af29e978ddcab30c66ae9ea7fa"),
                            ("model-00004-of-00004.safetensors", 1168138808,
                             "92ecfe1a2414458b4821ac8c13cf8cb70aed66b5eea8dc5ad9eeb4ff309d6d7b"),
                            ("model.safetensors.index.json", 23950, None),
                            ("special_tokens_map.json", 296, None),
                            ("tokenizer.json", 9085657, None),
                            ("tokenizer_config.json", 55351, None))),
            _variant("awq", "AWQ", "safetensors", "vllm",
                     "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4",
                     "db1f81ad4b8c7e39777509fac66c652eb0a52f91",
                     _files(("config.json", 1039, None),
                            ("generation_config.json", 189, None),
                            ("model-00001-of-00002.safetensors", 4677265296,
                             "e152d461dbe23f8e7606edbd1cc859a2cdc85a46766d8cb6a629eb88832c5718"),
                            ("model-00002-of-00002.safetensors", 1050673280,
                             "3e9a36ad418b0cd9b253f65771552d7dc05cf1abf1170b94de4b4d546aac255d"),
                            ("model.safetensors.index.json", 63480, None),
                            ("special_tokens_map.json", 295, None),
                            ("tokenizer.json", 9085658, None),
                            ("tokenizer_config.json", 55351, None))),
            _variant("gptq", "GPTQ", "safetensors", "vllm",
                     "hugging-quants/Meta-Llama-3.1-8B-Instruct-GPTQ-INT4",
                     "f184d2b18e2b7c257af79aa0bc53ef3ee505caa2",
                     _files(("config.json", 1169, None),
                            ("generation_config.json", 184, None),
                            ("model-00001-of-00002.safetensors", 4971321368,
                             "5b28fc9d399562b4cb2ea3da3651d68b347782668e7f3f0db20dbf0a8cd02a19"),
                            ("model-00002-of-00002.safetensors", 764398520,
                             "ac6cc79867b25c1a2415e043aea7c33c5a0caffdee28c2e229d96b49e52cfb1d"),
                            ("model.safetensors.index.json", 96180, None),
                            ("quantize_config.json", 264, None),
                            ("special_tokens_map.json", 296, None),
                            ("tokenizer.json", 9084449, None),
                            ("tokenizer_config.json", 55351, None))),
        ],
    },
    {
        "id": "gemma-3-27b", "name": "Gemma 3 27B IT", "family": "Gemma 3",
        "repo": "google/gemma-3-27b-it", "revision": "005ad3404e59d6023443cb575daa05336842228a",
        "ollama_tag": "gemma3:27b",
        "params_b": 27.43, "layers": 62, "kv_heads": 16, "head_dim": 128, "context_max": 131072,
        "licence": {"name": "Gemma Terms of Use",
                    "url": "https://ai.google.dev/gemma/terms",
                    "gated": True, "non_commercial": False},
        "engine": ["llamacpp", "vllm"], "safetensors_only": False,
        "source_url": "https://huggingface.co/google/gemma-3-27b-it",
        "checked_on": "2026-11-18",
        "variants": [
            _variant("bf16", "BF16", "safetensors", "vllm",
                     "google/gemma-3-27b-it", "005ad3404e59d6023443cb575daa05336842228a",
                     _files(("added_tokens.json", 35, None),
                            ("chat_template.json", 1615, None),
                            ("config.json", 972, None),
                            ("generation_config.json", 215, None),
                            ("model-00001-of-00012.safetensors", 4854573696,
                             "4da0290139f018bdea488b556c136d0f0ca4506fe5f5555cd97c0f6f2e886add"),
                            ("model-00002-of-00012.safetensors", 4954792944,
                             "bf17dbadf9c7cd696e4768639601c3300ea659e49f018000956078cefd475cdf"),
                            ("model-00003-of-00012.safetensors", 4954792976,
                             "c12b9d629d07b4583e19a467713f92b5c1ae8c9d7ef11faf1bdb91c4c7b59efc"),
                            ("model-00004-of-00012.safetensors", 4954793016,
                             "7171ed512e46c90cb579a58f66851bad09b028220422ceb1ae85080ab4ffb958"),
                            ("model-00005-of-00012.safetensors", 4954793016,
                             "9fb9667695749e55d808f407d78f18f80bd8ff999175c2c480cad7075ff5b2cf"),
                            ("model-00006-of-00012.safetensors", 4954793016,
                             "91ae339063266e0c12da89af8aa0cfdb3f9dc9bb1b4b2678863793a28026dbe7"),
                            ("model-00007-of-00012.safetensors", 4954793016,
                             "0497dda2b32df5d583caaffae35a96f3524a1e4305b850f4b1ce2e60fc354fe4"),
                            ("model-00008-of-00012.safetensors", 4954793016,
                             "9061b71b9cc82e187bd72c8f4594c5c1d900b0bc98c416d72902209514cf8ac4"),
                            ("model-00009-of-00012.safetensors", 4954793016,
                             "ebf2e19c3385d4b342e1517639293fe093ad793f41895862713e38603635c769"),
                            ("model-00010-of-00012.safetensors", 4954793016,
                             "d651ceb24678d80796a36f9a026f7178631b44e9d86f6f87e52093d915f702ad"),
                            ("model-00011-of-00012.safetensors", 4954793016,
                             "4a2de7fa772158381c7569a5699cadb9da3b06d92b802f54ac1c09f4a2c2e594"),
                            ("model-00012-of-00012.safetensors", 462476696,
                             "61f4d0c537a889d474396c6fb21ebb90946a64d70345403d47627ecb559e8e91"),
                            ("model.safetensors.index.json", 126651, None),
                            ("preprocessor_config.json", 570, None),
                            ("processor_config.json", 70, None),
                            ("special_tokens_map.json", 662, None),
                            ("tokenizer.json", 33384568,
                             "4667f2089529e8e7657cfb6d1c19910ae71ff5f28aa7ab2ff2763330affad795"),
                            ("tokenizer.model", 4689074,
                             "1299c11d7cf632ef3b4e11937501358ada021bbdf7c47638d13c0ee982f2e79c"),
                            ("tokenizer_config.json", 1156999, None))),
            _variant("q4_0", "Q4_0", "gguf", "llamacpp",
                     "google/gemma-3-27b-it-qat-q4_0-gguf",
                     "17cf0f6ad611f1a57a1640daa57eb427d6e67ed6",
                     _files(("gemma-3-27b-it-q4_0.gguf", 17229630496,
                             "7b131f721b95bd06ef4066e18ed2febed15ad6620f61c6eaf37832837ca109fe"),
                            ("mmproj-model-f16-27B.gguf", 857739168,
                             "54cb61c842fe49ac3c89bc1a614a2778163eb49f3dec2b90ff688b4c0392cb48"))),
        ],
    },
    {
        "id": "qwen2.5-7b-gguf", "name": "Qwen2.5 7B Instruct", "family": "Qwen2.5",
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "revision": "bb5d59e06d9551d752d08b292a50eb208b07ab1f", "ollama_tag": "qwen2.5:7b",
        "params_b": 7.62, "layers": 28, "kv_heads": 4, "head_dim": 128, "context_max": 32768,
        "licence": {"name": "Apache-2.0",
                    "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/blob/main/LICENSE",
                    "gated": False, "non_commercial": False},
        "engine": ["llamacpp"], "safetensors_only": False,
        "source_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF",
        "checked_on": "2026-11-18",
        "variants": [
            _variant("q8_0", "Q8_0", "gguf", "llamacpp", "Qwen/Qwen2.5-7B-Instruct-GGUF",
                     "bb5d59e06d9551d752d08b292a50eb208b07ab1f",
                     _files(("qwen2.5-7b-instruct-q8_0-00001-of-00003.gguf", 3980069248,
                             "26e30cb4559f0d9e9e11f34d351292af6f42199ce3fa742b5e7c5af4bc35b0f0"),
                            ("qwen2.5-7b-instruct-q8_0-00002-of-00003.gguf", 3942935680,
                             "e93856ce0cb05d5abd698eb439c0fea3acd412d9040f5ab7d2d4d088add5287d"),
                            ("qwen2.5-7b-instruct-q8_0-00003-of-00003.gguf", 175520480,
                             "8f29c0e4173d4d92d35c52a7c5807c34a3edfe6bb078ea785d145b7d88c16e44"))),
            _variant("q4_k_m", "Q4_K_M", "gguf", "llamacpp", "Qwen/Qwen2.5-7B-Instruct-GGUF",
                     "bb5d59e06d9551d752d08b292a50eb208b07ab1f",
                     _files(("qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", 3993201344,
                             "dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db"),
                            ("qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf", 689872288,
                             "539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a"))),
        ],
    },
]

# T-1023 / PLAN §12.3: the Ollama tags a host may pull. A tag is one quantised model in Ollama's
# own store, so it has no file list: the byte figure is the Q4_K_M download the Ollama Library
# published on ``checked_on``, and Ollama's manifest is authoritative at pull time. The row's
# engine is Ollama; ``variant`` is the catalogue id the estimator and the UI share.
OLLAMA_TAGS: list[dict] = [
    {
        "id": "qwen3-4b", "tag": "qwen3:4b", "name": "Qwen3 4B", "family": "Qwen3",
        "params_b": 4.0, "layers": 36, "kv_heads": 8, "head_dim": 128, "context_max": 40960,
        "quant": "Q4_K_M", "variant": "q4_k_m", "bytes": 2_500_000_000,
        "licence": {"name": "Apache-2.0",
                    "url": "https://huggingface.co/Qwen/Qwen3-4B/blob/main/LICENSE",
                    "gated": False, "non_commercial": False},
        "source_url": "https://ollama.com/library/qwen3", "checked_on": "2026-11-18",
    },
    {
        "id": "qwen3-8b", "tag": "qwen3:8b", "name": "Qwen3 8B", "family": "Qwen3",
        "params_b": 8.2, "layers": 36, "kv_heads": 8, "head_dim": 128, "context_max": 40960,
        "quant": "Q4_K_M", "variant": "q4_k_m", "bytes": 5_200_000_000,
        "licence": {"name": "Apache-2.0",
                    "url": "https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE",
                    "gated": False, "non_commercial": False},
        "source_url": "https://ollama.com/library/qwen3", "checked_on": "2026-11-18",
    },
    {
        "id": "gemma3-4b", "tag": "gemma3:4b", "name": "Gemma 3 4B IT", "family": "Gemma 3",
        "params_b": 4.3, "layers": 34, "kv_heads": 4, "head_dim": 256, "context_max": 131072,
        "quant": "Q4_K_M", "variant": "q4_k_m", "bytes": 3_300_000_000,
        "licence": {"name": "Gemma Terms of Use", "url": "https://ai.google.dev/gemma/terms",
                    "gated": False, "non_commercial": False},
        "source_url": "https://ollama.com/library/gemma3", "checked_on": "2026-11-18",
    },
    {
        "id": "llama3.2-3b", "tag": "llama3.2:3b", "name": "Llama 3.2 3B Instruct",
        "family": "Llama 3.2", "params_b": 3.2, "layers": 28, "kv_heads": 8, "head_dim": 128,
        "context_max": 131072, "quant": "Q4_K_M", "variant": "q4_k_m",
        "bytes": 2_000_000_000,
        "licence": {"name": "Llama 3.2 Community License",
                    "url": "https://llama.meta.com/llama3_2/license/",
                    "gated": False, "non_commercial": False},
        "source_url": "https://ollama.com/library/llama3.2", "checked_on": "2026-11-18",
    },
]

_OLLAMA_BY_TAG = {row["tag"]: row for row in OLLAMA_TAGS}


class UnknownTag(KeyError):
    """A tag the Ollama catalogue does not list; the route turns it into a 422."""


def model(model_id: str) -> dict:
    """The row for ``model_id``; an id the catalogue does not list raises ``KeyError``."""
    for row in MODELS:
        if row["id"] == model_id:
            return row
    raise KeyError(model_id)


def variant(row: dict, variant_id: str) -> dict:
    """One variant of ``row``; an id the row does not offer raises ``KeyError``."""
    for item in row["variants"]:
        if item["id"] == variant_id:
            return item
    raise KeyError(variant_id)


def validate_repo(repo) -> str:
    """An ``owner/name`` repo id, or ``InvalidRepo``: no URL, no path, no empty string."""
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise InvalidRepo("A model repository must be owner/name; URLs, paths and empty ids are "
                          "refused.")
    return repo


def _is_pickle(path: str) -> bool:
    return path.lower().endswith(PICKLE)


def _gpu_gb(inventory: dict | None) -> float | None:
    """The first GPU's VRAM in GB as the host reported it, or None when it reported no GPU."""
    for gpu in (inventory or {}).get("gpus") or []:
        if isinstance(gpu, dict) and gpu.get("vram_mb"):
            return round(float(gpu["vram_mb"]) / 1024, 1)
    return None


def disk_block(total_bytes: int | None, free_gb: float | None) -> str | None:
    """The disk refusal, or None: a download must leave 20% of the host's free space alone."""
    if total_bytes is None or free_gb is None:
        return None
    needed = total_bytes / GIB
    if needed <= float(free_gb) * DISK_MARGIN:
        return None
    return (f"Needs {needed:.1f} GB, host has {float(free_gb):.1f} GB free; the download keeps "
            f"20% of the disk free.")


def fit(row: dict, variant_row: dict, inventory: dict | None) -> dict | None:
    """The T-1004 memory verdict for one variant on the host's first GPU; None with no GPU."""
    vram_gb = _gpu_gb(inventory)
    if vram_gb is None:
        return None
    return inference_estimate.fit(row["params_b"], QUANT[variant_row["quant"]],
                                  variant_row["engine"], row["layers"], row["kv_heads"],
                                  row["head_dim"], FIT_CONTEXT, vram_gb)


def _installed(inventory: dict | None) -> list[dict]:
    return [item for item in (inventory or {}).get("models") or [] if isinstance(item, dict)]


def _is_installed(installed: list[dict], model_id: str, variant_id: str) -> bool:
    return any(item.get("id") == model_id and (item.get("variant") in (None, variant_id))
               for item in installed)


def _blocked(row: dict, variant_row: dict, inventory: dict | None, memory: dict | None,
             with_fit: bool = True) -> list[str]:
    """Every reason this variant may not be downloaded, in the order the sheet shows them."""
    reasons = []
    if row["licence"]["gated"] and (inventory or {}).get("hf_token") is not True:
        reasons.append(TOKEN_BLOCK)
    if any(_is_pickle(file["path"]) for file in variant_row["files"]):
        reasons.append(PICKLE_BLOCK)
    disk = disk_block(variant_row["bytes"], ((inventory or {}).get("disk") or {}).get("models_free_gb"))
    if disk:
        reasons.append(disk)
    if with_fit and memory is not None and not memory["fits"]:
        reasons.append(f"This model does not fit the host's GPU: {memory['verdict']}")
    return reasons


def _warnings(row: dict, inventory: dict | None, memory: dict | None, online: bool,
              one_model: bool = True) -> list[str]:
    out = []
    free_gb = ((inventory or {}).get("disk") or {}).get("models_free_gb")
    if free_gb is None:
        out.append("The host has not reported free disk space, so the disk check was skipped.")
    if memory is None:
        out.append("The host reports no GPU, so the fit estimate is unavailable.")
    if not online:
        out.append("The host is offline; the download waits for it to report again.")
    if one_model:
        for item in _installed(inventory):
            if item.get("id") and item.get("id") != row["id"]:
                out.append(ONE_MODEL.format(model=item["id"]))
                break
    return out


def _plan_id(host: dict, model_id: str, variant_id: str, inventory: dict | None) -> str:
    """A digest of what the plan depends on, so a stale plan is visible instead of executed."""
    inv = inventory or {}
    body = json.dumps({"host": host.get("id"), "model": model_id, "variant": variant_id,
                       "models": sorted(item.get("id") or "" for item in _installed(inv)),
                       "disk_free_gb": ((inv.get("disk") or {}).get("models_free_gb")),
                       "hf_token": inv.get("hf_token") is True}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _gate(row: dict) -> dict:
    licence = row["licence"]
    return {"gated": licence["gated"], "licence": licence["name"], "url": licence["url"],
            "non_commercial": licence["non_commercial"]}


def plan(host: dict, model_id: str, variant_id: str) -> dict:
    """The dry run for one variant on one host: files, bytes, disk after, gate and blocks."""
    row = model(model_id)
    variant_row = variant(row, variant_id)
    validate_repo(variant_row["repo"])
    if not COMMIT.fullmatch(variant_row["revision"]):
        raise InvalidRepo("A model revision must be a pinned commit, not a branch.")
    inventory = host.get("inventory")
    memory = fit(row, variant_row, inventory)
    total = variant_row["bytes"]
    free_gb = ((inventory or {}).get("disk") or {}).get("models_free_gb")
    return {
        "plan_id": _plan_id(host, model_id, variant_id, inventory),
        "model": model_id, "variant": variant_id,
        "files": [dict(file) for file in variant_row["files"]],
        "total_bytes": total,
        "disk_free_gb": free_gb,
        "disk_after_gb": None if free_gb is None else round(float(free_gb) - total / GIB, 1),
        "gate": _gate(row),
        "token_present": (inventory or {}).get("hf_token") is True,
        "blocked": _blocked(row, variant_row, inventory, memory),
        "warnings": _warnings(row, inventory, memory, host.get("online", True)),
        "fit": memory,
    }


def _ollama_fit(row: dict, inventory: dict | None) -> dict | None:
    """The same T-1004 verdict, with the tag's Q4_K_M quant and Ollama's own overhead."""
    vram_gb = _gpu_gb(inventory)
    if vram_gb is None:
        return None
    return inference_estimate.fit(row["params_b"], QUANT[row["quant"]], "ollama",
                                  row["layers"], row["kv_heads"], row["head_dim"],
                                  FIT_CONTEXT, vram_gb)


def _ollama_blocked(row: dict, inventory: dict | None, memory: dict | None) -> list[str]:
    """Why this tag may not be pulled: the one-model rule first, then disk and the fit."""
    out = []
    other = next((item.get("id") for item in _installed(inventory)
                  if item.get("id") and item.get("id") != row["id"]), None)
    if other:
        out.append(ONE_MODEL.format(model=other))
    disk = disk_block(row["bytes"], ((inventory or {}).get("disk") or {}).get("models_free_gb"))
    if disk:
        out.append(disk)
    if memory is not None and not memory["fits"]:
        out.append(f"This model does not fit the host's GPU: {memory['verdict']}")
    return out


def ollama_pull(host: dict, tag: str) -> dict:
    """The pull dry run for one catalogue tag: the exact argv, bytes, fit and every block."""
    row = _OLLAMA_BY_TAG.get(str(tag))
    if row is None:
        raise UnknownTag(str(tag))
    inventory = host.get("inventory")
    memory = _ollama_fit(row, inventory)
    blocked = _ollama_blocked(row, inventory, memory)
    if any(item.get("id") == row["id"] for item in _installed(inventory)):
        blocked.insert(0, "This model is already installed on this host.")
    free_gb = ((inventory or {}).get("disk") or {}).get("models_free_gb")
    return {
        "id": row["id"], "tag": row["tag"], "variant": row["variant"], "quant": row["quant"],
        # Rebuilt from the catalogue row, never from the request string.
        "argv": ["ollama", "pull", row["tag"]],
        "bytes": row["bytes"],
        "disk_free_gb": free_gb,
        "disk_after_gb": None if free_gb is None else round(float(free_gb) - row["bytes"] / GIB, 1),
        "blocked": blocked,
        "warnings": _warnings(row, inventory, memory, host.get("online", True), one_model=False),
        "fit": memory,
    }


def _ollama_rows(inventory: dict | None) -> list[dict]:
    """The tag rows shaped like the Hugging Face rows, so one Models tab renders both."""
    installed = _installed(inventory)
    rows = []
    for row in OLLAMA_TAGS:
        memory = _ollama_fit(row, inventory)
        blocked = _ollama_blocked(row, inventory, memory)
        is_installed = any(item.get("id") == row["id"] for item in installed)
        rows.append({
            "id": row["id"], "name": row["name"], "family": row["family"],
            "repo": None, "revision": None, "ollama_tag": row["tag"],
            "params_b": row["params_b"], "context_max": row["context_max"],
            "licence": dict(row["licence"]), "engine": ["ollama"], "safetensors_only": False,
            "source_url": row["source_url"], "checked_on": row["checked_on"],
            "variants": [{
                "id": row["variant"], "quant": row["quant"], "format": "tag",
                "engine": "ollama", "bytes": row["bytes"],
                "vram_gb": None if memory is None else memory["total_gb"],
                "fits": None if memory is None else memory["fits"],
                "fit_verdict": None if memory is None else memory["verdict"],
                "assumed_context": FIT_CONTEXT, "installed": is_installed, "blocked": blocked,
            }],
            "installed": is_installed,
            "fits": None if memory is None else memory["fits"],
            "blocked": blocked,
        })
    return rows


def public_models(host: dict) -> dict:
    """The catalogue joined with this host's installed state, fit verdict and block reasons.

    ``files`` stays out: the plan returns them, and the list never carries a repo path.
    """
    inventory = host.get("inventory")
    installed = _installed(inventory)
    rows = []
    for row in MODELS:
        smallest = min(row["variants"], key=lambda item: item["bytes"])
        variants = []
        for variant_row in row["variants"]:
            memory = fit(row, variant_row, inventory)
            variants.append({
                "id": variant_row["id"], "quant": variant_row["quant"],
                "format": variant_row["format"], "engine": variant_row["engine"],
                "bytes": variant_row["bytes"],
                "vram_gb": None if memory is None else memory["total_gb"],
                "fits": None if memory is None else memory["fits"],
                "fit_verdict": None if memory is None else memory["verdict"],
                "assumed_context": FIT_CONTEXT,
                "installed": _is_installed(installed, row["id"], variant_row["id"]),
                "blocked": _blocked(row, variant_row, inventory, memory),
            })
        any_fit = [item["fits"] for item in variants if item["fits"] is not None]
        rows.append({
            "id": row["id"], "name": row["name"], "family": row["family"],
            "repo": row["repo"], "revision": row["revision"], "ollama_tag": row["ollama_tag"],
            "params_b": row["params_b"], "context_max": row["context_max"],
            "licence": dict(row["licence"]), "engine": list(row["engine"]),
            "safetensors_only": row["safetensors_only"], "source_url": row["source_url"],
            "checked_on": row["checked_on"],
            "variants": variants,
            "installed": any(item["installed"] for item in variants),
            "fits": any(any_fit) if any_fit else None,
            "blocked": _blocked(row, smallest, inventory, None, with_fit=False),
        })
    rows.extend(_ollama_rows(inventory))
    return {"host": host.get("id"), "assumed_context": FIT_CONTEXT, "models": rows}


def validate() -> None:
    """Raise ``ValueError`` if a row could offer a floating pin, a pickle or a dishonest licence."""
    ids = [row["id"] for row in MODELS]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate model ids")
    for row in MODELS:
        validate_repo(row["repo"])
        if not COMMIT.fullmatch(row["revision"]):
            raise ValueError(f"{row['id']}: revision is not a pinned commit")
        if not str(row["licence"]["url"]).startswith("https://"):
            raise ValueError(f"{row['id']}: no licence url")
        if row["licence"]["gated"] and row["licence"]["name"] == "Apache-2.0":
            raise ValueError(f"{row['id']}: a gated weight set cannot be Apache-2.0")
        upper = row["licence"]["name"].upper()
        if any(word in upper for word in NON_COMMERCIAL) and not row["licence"]["non_commercial"]:
            raise ValueError(f"{row['id']}: a non-commercial licence must say so")
        if not row["variants"]:
            raise ValueError(f"{row['id']}: no variants")
        for variant_row in row["variants"]:
            validate_repo(variant_row["repo"])
            if not COMMIT.fullmatch(variant_row["revision"]):
                raise ValueError(f"{row['id']}/{variant_row['id']}: revision is not a commit")
            if variant_row["quant"] not in QUANT:
                raise ValueError(f"{row['id']}/{variant_row['id']}: unknown quantisation")
            if not variant_row["files"]:
                raise ValueError(f"{row['id']}/{variant_row['id']}: no files")
            for file in variant_row["files"]:
                if not file["bytes"] or file["bytes"] < 0:
                    raise ValueError(f"{row['id']}/{variant_row['id']}: {file['path']} has no size")
                if _is_pickle(file["path"]):
                    raise ValueError(f"{row['id']}/{variant_row['id']}: offers a pickle weight")
    tag_ids = [row["id"] for row in OLLAMA_TAGS]
    tags = [row["tag"] for row in OLLAMA_TAGS]
    if len(set(tag_ids)) != len(tag_ids) or len(set(tags)) != len(tags):
        raise ValueError("duplicate Ollama tag rows")
    if set(tag_ids) & set(ids):
        raise ValueError("an Ollama tag row reuses a Hugging Face model id")
    for row in OLLAMA_TAGS:
        if not TAG.fullmatch(row["tag"]):
            raise ValueError(f"{row['tag']}: not an Ollama tag")
        if row["quant"] not in QUANT:
            raise ValueError(f"{row['tag']}: unknown quantisation")
        if not row["bytes"] or row["bytes"] < 0:
            raise ValueError(f"{row['tag']}: no download size")
        if not str(row["source_url"]).startswith("https://"):
            raise ValueError(f"{row['tag']}: no source url")
        if not str(row["licence"]["url"]).startswith("https://"):
            raise ValueError(f"{row['tag']}: no licence url")
    return None
