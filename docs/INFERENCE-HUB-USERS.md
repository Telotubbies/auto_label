# Inference Hub

The Inference Hub is where a workspace admin prepares a machine to run models: install an engine,
download a model onto a host, check whether a model will fit a graphics card, and hand a segmentation
model to auto-label. It sits in the workspace rail under **Build**, and it is the same page for all
four jobs.

Open it at `/<workspace>/inference`. The tab you are on lives in the URL (`?tab=engines`,
`?tab=models`, `?tab=calculator`, `?tab=segmentation`), so a refresh or a shared link opens the same
view.

**Who sees it.** Owners and admins see the whole page. Every other member may call the calculator in
the API, but the page itself is gated for admins in this release. If you are not an admin, ask one to
run the calculation for you.

A **host** is a machine running the LabelDesk worker: the GPU box in your office, a rented server, or
a notebook. The host picker at the top of the page decides which machine every tab talks about, and
the picker remembers nothing — check it before you press an action.

---

## Engines — "can this machine run it, and what gets installed?"

The tab lists the engines the catalogue supports, in order, with the version each one is pinned to:

| Engine | What it is for |
| --- | --- |
| **Ollama** | quantised models on one host with little setup; the default choice and the first row |
| **vLLM** | high-throughput serving of Hugging Face models on NVIDIA cards |
| **llama.cpp** | GGUF files on CPU, Apple silicon or a small GPU; the smallest footprint |
| **SGLang** | an alternative high-throughput server for NVIDIA cards |
| **TensorRT-LLM** | container-only serving on NVIDIA cards, with a strict driver and CUDA match |
| **ONNX Runtime GenAI** | pip runtime for exported models, on CPU or CUDA |
| **Triton Inference Server** | NVIDIA's container serving platform (not the Triton compiler) |

Each row answers five questions: which version is pinned, which runtime it installs with (a container
image by digest, or a Python environment built with `uv` or `pip`), which operating system and
accelerator it needs, how much disk it takes, and whether this host can run it.

**The three states you will see.** *Not installed* is the normal start. *Installed <version>* means
the host reported that exact pin. A **blocked** row is greyed out with the reason next to it, for
example "Needs driver 575.51 or newer; the host reports 550.54." Blocked is information, not an error:
the host told us what it has, and the catalogue says what the engine needs.

**Installing.** Tick one or more rows, press **Review install plan**, and read the sheet before you
confirm. It names the host, shows the exact command per engine in monospace, the total bytes, the free
disk after the install and any warning. Nothing has run yet. Tick "I understand this installs software
on <host>" and press **Install**; the job card then shows the phase, the percentage, the last lines of
the engine's own output, and a **Cancel** button. Only one engine job runs on a host at a time.

**Uninstalling** is the row menu's **Uninstall**, confirmed in a sheet that names the engine and the
host. It removes only what the hub installed: the engine's own environment or image, never the
worker's training environment.

---

## Models — "which model fits this host, and what does it cost in disk?"

The catalogue lists models with their family, parameter count, variants (quantisation and format),
download size, licence, and the estimated memory each variant needs on the picked host. Filters
narrow by family, size, quantisation, licence, **Fits this host** and **Installed**.

A **variant** is one way to get the same model: a smaller quantisation is less accurate and much
smaller. The sheet shows the file list with bytes, the total, the free disk after the download, the
licence, and — if the model is gated — whether the host has a token (see *Gated licences* below). A
download that cannot fit is refused in the sheet with the shortfall, not queued and failed later.

**Row states.** `Queued`, `Downloading 43%` (it resumes where it stopped), `Installed`. A cancelled or
failed download leaves no half file behind: the partial tree is removed and the row goes back to
`Not installed`, with the reason kept on the job card.

**One model per host.** In this release a host holds one downloaded model. Downloading a second asks
you to remove the current one first. The point is the disk: the largest single model plus one engine
is the ceiling, and the downloader also refuses to eat the last 20 % of free space.

**Ollama tags.** Rows whose engine is Ollama carry a tag such as `qwen3:4b` instead of a file list.
Pulling a tag is a different job from downloading files, and in this release it runs from the pull
endpoint rather than the tab's Download button; the operator runbook has the command.

**Removing** is on the host's assets panel (**Manage on host** under the table, or the panel below
it), confirmed in a sheet that names the model and the bytes it frees.

---

## Calculator — "will it fit, and how fast will it roughly be?"

Every number here is an **estimate**, not a measurement, and the page says so under the results. It
is also the tab that needs no host: it is a model of the hardware, and it stores nothing.

You give it a model (a catalogue preset or your own numbers), the precision or quantisation, the
context window, the batch and how many users share it, the prompt and output length, a graphics card
preset or its own VRAM with memory bandwidth and FP16 throughput, how many cards and how they are
split (tensor parallel), and which engine would run it — the engine supplies its own memory overhead
and usable-VRAM fraction. Press **Show estimate** on a narrow screen; on a desktop the answer appears
beside the form.

**Reading the answer, in this order:**

1. **Fit verdict.** *Fits* or *Does not fit*, with the headroom or the shortfall in GB. Under it, the
   per-GPU memory is broken down into weights, KV cache, activations and framework overhead, then
   total against usable. Usable is 95 % of VRAM by default (Ollama, llama.cpp), and 90 % for engines
   that reserve the rest themselves (vLLM, SGLang, TensorRT-LLM).
2. **Two ceilings.** Decode throughput is computed twice: once as *memory-bound* (how fast the card
   can stream weights and cache through its bandwidth) and once as *compute-bound* (how fast its
   arithmetic could go). The lower one wins, and on one consumer card a 7B model is almost always
   memory-bound.
3. **tok/s, as an estimate and a range.** The headline figure is `0.8 × the lower ceiling`; the range
   is `0.6 … 1.2 ×` that figure. Read the range, not the middle number. With a prompt length given,
   the same panel shows the estimated time to first token.
4. **Assumptions.** The panel lists every default it used, including the factors above. If your
   number matters for a purchase, read it.

The formulas and their sources are public and cited: weights and arithmetic intensity from
EleutherAI's *Transformer Math 101* <https://blog.eleuther.ai/transformer-math/>, KV cache and the
memory-versus-FLOPs roofline from Kipply's *Transformer Inference Arithmetic*
<https://kipp.ly/transformer-inference-arithmetic/>, and framework memory behaviour from vLLM's
*Conserving Memory* <https://docs.vllm.ai/en/latest/configuration/conserving_memory.html>.

**What an estimate is not.** It is not a benchmark of your card, your driver or your model build. It
assumes the memory follows the published formulas, a stated usable fraction, and fixed efficiency
factors (0.7 of peak bandwidth, 0.25 MFU for decode, 0.4 for prefill). Real numbers on real hardware
are the next step; until they exist, treat the figure as a sizing check and the range as the honest
error bar.

---

## Segmentation — "what is provisioned here, and can this project use it?"

The tab lists the segmentation models the hub knows (SAM 3.1, SAM2, YOLO-seg sizes, Mask2Former) with
their working resolutions' VRAM, parameter count, licence, source, and one state per host:

- **Ready** — the weights are on this host and the model is registered, so it can be used.
- **Missing checkpoint** — the catalogue lists it but the host has no weights.
- **Not supported on this OS** — the model cannot run on the host's platform.

A licence badge with a warning tone means the licence restricts use: **AGPL** for the Ultralytics
families (a model under AGPL affects the terms of what you distribute with it) and **Non-commercial**
where the weights may not be used commercially. The badge is there so nobody discovers it later.

**Use for auto-label.** Choose a project above the grid, then press **Use for auto-label** on a Ready
row. The dataset opens with the Auto label dialog already on that model, with the project's classes
in the picker. That is the whole handoff: it fills the dialog in, and you still press the dialog's own
button. It does not change a project's default model, and it never writes annotations by itself.

**Provisioned** therefore means "this host has the weights and can offer the model right now". It says
nothing about how good the result will be on your images; run a preview, check a few masks, then
label.

---

## Gated licences

Some weights are **gated**: the licence is accepted per account on the model's own site, not
downloaded anonymously. The hub shows a **Gated** badge and the licence name, and refuses the download
until the host reports that a Hugging Face token is present.

What that means in practice:

- Someone with the Hugging Face account that owns the token accepts the model's terms there. The hub
  does not accept terms for you and does not record that you did.
- The token is put in the worker's environment by the operator. It is never typed into this page, and
  the page only ever learns that a token exists, never its value.
- A gated licence is still a licence: the badge names it, and using the weights commercially may need
  a separate agreement with the publisher.

---

## When something is wrong

The page always says what happened in place: a failed request shows its own sentence with a retry, an
offline host shows its last report and refuses actions, a blocked row carries its reason, and an empty
filter result offers **Clear filters**. Job failures keep the engine's last output line.

For anything that needs a machine, open the operator runbook:
[`INFERENCE-HUB.md`](INFERENCE-HUB.md) — it has the three locks, the first install, the six common
failures and the rollback. **Quote the job id**: it is on the job card and in the job's URL, it is
what support needs, and it is all they need.
