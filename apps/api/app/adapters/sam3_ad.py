"""SAM 3.1 family: text-prompted segmentation and box refinement (delegates to services.segment)."""
import importlib.util
import time

from ..config import SAM_ENABLED, SAM_ROOT
from ..services import segment
from .base import Availability, register


class Sam3Adapter:
    family = "sam3"

    def probe(self) -> Availability:
        if SAM_ENABLED == "0":
            return Availability(False, "disabled by LD_SAM_ENABLED=0")
        st = segment.sam_status()
        if st["loaded"]:
            return Availability(True, vram_mb=segment.SAM_VRAM_MB)
        if st["error"]:
            return Availability(False, st["error"])
        if importlib.util.find_spec("torch") is None:
            return Availability(False, "torch not installed")
        if not (SAM_ROOT / "checkpoints" / "sam3.1_multiplex.pt").exists():
            return Availability(False, f"SAM checkpoint missing under {SAM_ROOT / 'checkpoints'}")
        return Availability(True, vram_mb=segment.SAM_VRAM_MB)

    def capabilities(self, variant: str) -> set[str]:
        return {"segment", "text-prompt", "box-prompt"}

    def runtime_key(self, variant: str, weights: str | None) -> str:
        return "sam3"

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5) -> dict:
        t0 = time.time()
        prompts = list(classes) if classes else ([prompt] if prompt else [])
        if not prompts:
            raise ValueError("sam3 needs classes or prompt")
        preds = []
        for i, poly, score in segment.sam_text(im, prompts, conf):
            pts = [(poly[k] * im.width, poly[k + 1] * im.height) for k in range(0, len(poly), 2)]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            preds.append({"class": prompts[i], "class_id": i, "confidence": round(score, 4),
                          "x": round((min(xs) + max(xs)) / 2, 1), "y": round((min(ys) + max(ys)) / 2, 1),
                          "width": round(max(xs) - min(xs), 1), "height": round(max(ys) - min(ys), 1),
                          "points": [{"x": round(x, 1), "y": round(y, 1)} for x, y in pts]})
        return {"model": f"{self.family}:{variant}", "predictions": preds, "time": round(time.time() - t0, 4),
                "image": {"width": im.width, "height": im.height}}

    def segment_box(self, im, box_xyxy_px):
        return segment.sam_box(im, box_xyxy_px)


register(Sam3Adapter())
