"""Qwen2.5-VL served by vLLM (OpenAI-compatible): schema-constrained grounding, verify, prompt parsing, VQA."""
import base64
import io
import json
import math
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from PIL import Image as PImage

from .. import config
from .base import Availability, register

MAX_PIXELS = 589824
MIN_PIXELS = 3136


def smart_resize(h: int, w: int, factor: int = 28, max_pixels: int = MAX_PIXELS,
                 min_pixels: int = MIN_PIXELS) -> tuple[int, int]:
    """Qwen2.5-VL rule: round to multiples of factor, then clamp the pixel count to [min, max]."""
    hb = max(factor, round(h / factor) * factor)
    wb = max(factor, round(w / factor) * factor)
    if hb * wb > max_pixels:
        beta = math.sqrt(h * w / max_pixels)
        hb = max(factor, math.floor(h / beta / factor) * factor)
        wb = max(factor, math.floor(w / beta / factor) * factor)
    elif hb * wb < min_pixels:
        beta = math.sqrt(min_pixels / (h * w))
        hb = math.ceil(h * beta / factor) * factor
        wb = math.ceil(w * beta / factor) * factor
    return hb, wb


def _data_url(im: PImage.Image) -> str:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class VlmAdapter:
    family = "vlm"

    def __init__(self, url: str | None = None, model: str | None = None, transport=None, timeout: float = 60.0):
        self.url = (url or config.VLM_URL).rstrip("/")
        self.model = model or config.VLM_MODEL
        self._client = httpx.Client(timeout=timeout, transport=transport)

    # ---- plumbing
    @property
    def _root(self) -> str:
        p = urlsplit(self.url)
        path = p.path[:-3] if p.path.endswith("/v1") else p.path
        return urlunsplit((p.scheme, p.netloc, path.rstrip("/"), "", ""))

    def _unreachable(self) -> RuntimeError:
        return RuntimeError(f"vLLM not reachable at {self.url}")

    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        try:
            r = self._client.request(method, url, **kw)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise self._unreachable() from e
        r.raise_for_status()
        return r

    def _chat(self, im: PImage.Image, text: str, **extra) -> str:
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": _data_url(im)}},
                    {"type": "text", "text": text}]}], **extra}
        r = self._request("POST", f"{self.url}/chat/completions", json=body)
        return r.json()["choices"][0]["message"]["content"] or ""

    # ---- adapter contract
    def probe(self) -> Availability:
        try:
            self._request("GET", f"{self.url}/models", timeout=3.0)
        except RuntimeError as e:
            return Availability(False, str(e))
        except httpx.HTTPError as e:
            return Availability(False, f"vLLM error at {self.url}: {e}")
        return Availability(True, vram_mb=6500)

    def capabilities(self, variant: str) -> set[str]:
        return {"detect", "open-vocab", "vqa"}

    def runtime_key(self, variant: str, weights: str | None) -> str | None:
        """vLLM keeps the weights on its own server; the scheduler ledger has no local lease."""
        return None

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5) -> dict:
        if prompt:
            t0 = time.time()
            text = self.ask(im, prompt)
            return {"model": f"{self.family}:{variant}", "predictions": [], "text": text,
                    "time": round(time.time() - t0, 4), "image": {"width": im.width, "height": im.height}}
        out = self.ground(im, list(classes or []))
        out["model"] = f"{self.family}:{variant}"
        return out

    # ---- grounding
    def ground(self, im: PImage.Image, classes: list[str]) -> dict:
        t0 = time.time()
        W, H = im.size
        h2, w2 = smart_resize(H, W)
        small = im.convert("RGB").resize((w2, h2)) if (w2, h2) != (W, H) else im
        schema = {"type": "object", "properties": {"objects": {"type": "array", "items": {
            "type": "object",
            "properties": {"label": {"enum": list(classes)},
                           "bbox_2d": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}},
            "required": ["label", "bbox_2d"]}}}, "required": ["objects"]}
        prompt = ("Locate every instance of these classes in the image: "
                  + json.dumps(classes, ensure_ascii=False)
                  + ". Answer with JSON matching the schema: {\"objects\": [{\"label\": <class name exactly as given>, "
                    "\"bbox_2d\": [x1, y1, x2, y2]}]} using pixel coordinates of this image.")
        preds = []
        if classes:
            content = self._chat(small, prompt, response_format={
                "type": "json_schema", "json_schema": {"name": "boxes", "schema": schema}})
            sx, sy = W / w2, H / h2
            try:
                for o in json.loads(content).get("objects", []):
                    if o["label"] not in classes:
                        continue
                    x1, y1, x2, y2 = (float(v) for v in o["bbox_2d"])
                    x1, x2 = sorted((min(max(x1 * sx, 0), W), min(max(x2 * sx, 0), W)))
                    y1, y2 = sorted((min(max(y1 * sy, 0), H), min(max(y2 * sy, 0), H)))
                    if x2 - x1 <= 0 or y2 - y1 <= 0:
                        continue
                    preds.append({"class": o["label"], "class_id": classes.index(o["label"]), "confidence": 0.5,
                                  "x": round((x1 + x2) / 2, 1), "y": round((y1 + y2) / 2, 1),
                                  "width": round(x2 - x1, 1), "height": round(y2 - y1, 1)})
            except (ValueError, TypeError, KeyError, AttributeError):
                preds = []
        return {"model": f"{self.family}:qwen2.5-vl-7b", "predictions": preds, "time": round(time.time() - t0, 4),
                "image": {"width": W, "height": H}}

    def verify(self, im: PImage.Image, box: tuple[float, float, float, float], cls: str) -> bool:
        x1, y1, x2, y2 = box
        mx, my = (x2 - x1) * 0.15, (y2 - y1) * 0.15
        crop = im.convert("RGB").crop((max(0, int(x1 - mx)), max(0, int(y1 - my)),
                                       min(im.width, math.ceil(x2 + mx)), min(im.height, math.ceil(y2 + my))))
        return self._choice(crop, f"Does this image show a {cls}? Answer yes or no.")

    def _choice(self, im: PImage.Image, question: str) -> bool:
        a = self._chat(im, question, structured_outputs={"choice": ["yes", "no"]}).strip().lower()
        return a.startswith("yes")

    def parse_prompt(self, text: str) -> list[str]:
        schema = {"type": "object", "properties": {"phrases": {"type": "array", "items": {"type": "string"}}},
                  "required": ["phrases"]}
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "user", "content":
                              "Extract up to 8 short noun phrases naming the objects to find in this request, "
                              "keeping the original language. Request: " + text}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "phrases", "schema": schema}}}
        content = self._request("POST", f"{self.url}/chat/completions", json=body).json()["choices"][0]["message"]["content"]
        try:
            return [str(p) for p in json.loads(content)["phrases"]][:8]
        except (ValueError, TypeError, KeyError):
            return []

    def ask(self, im: PImage.Image, question: str) -> str:
        return self._chat(im, question).strip()

    def ask_yes_no(self, im: PImage.Image, question: str) -> bool:
        return self._choice(im, question)

    # ---- sleep mode (vLLM dev-mode endpoints live at the server root)
    def sleep(self, level: int = 1) -> None:
        self._request("POST", f"{self._root}/sleep?level={int(level)}")

    def wake(self) -> None:
        self._request("POST", f"{self._root}/wake_up")

    def is_sleeping(self) -> bool:
        return bool(self._request("GET", f"{self._root}/is_sleeping").json().get("is_sleeping"))


register(VlmAdapter())
