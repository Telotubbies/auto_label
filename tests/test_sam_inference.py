import pytest
import torch
from PIL import Image

import inference
from config import Category, Config


class FakeProcessor:
    def __init__(self):
        self.device = torch.device("cpu")
        self.outputs = {
            "first": {
                "scores": torch.tensor([0.2]),
                "boxes": torch.tensor([[0.0, 0.0, 8.0, 8.0]]),
                "masks": torch.ones((1, 1, 10, 10)),
            },
            "second": {
                "scores": torch.tensor([0.9]),
                "boxes": torch.tensor([[1.0, 1.0, 9.0, 9.0]]),
                "masks": torch.ones((1, 1, 10, 10)),
            },
        }

    def set_image(self, image):
        return {}

    def reset_all_prompts(self, state):
        return None

    def set_text_prompt(self, state, prompt):
        return self.outputs[prompt]


def test_segment_image_preserves_category_for_nms_survivor(monkeypatch):
    cfg = Config(categories=[Category(1, "first", "first", 0.0), Category(2, "second", "second", 0.0)])
    processor = FakeProcessor()
    monkeypatch.setattr(inference, "_gpu_bbox_nms", lambda *args, **kwargs: torch.tensor([False, True]))
    monkeypatch.setattr(inference, "masks_batch_to_rle_gpu", lambda *args, **kwargs: ([{"size": [10, 10], "counts": "100"}], [100]))

    annotations, next_id = inference.segment_image(processor, Image.new("RGB", (10, 10)), 7, 20, cfg)

    assert annotations[0]["category_id"] == 2
    assert annotations[0]["score"] == pytest.approx(0.9)
    assert annotations[0]["id"] == 20
    assert next_id == 21


def test_device_type_normalizes_string_and_torch_device():
    assert inference.device_type("cuda") == "cuda"
    assert inference.device_type(torch.device("cuda:0")) == "cuda"
    assert inference.device_type(torch.device("cpu")) == "cpu"
