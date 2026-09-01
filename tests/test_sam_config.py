import re
from pathlib import Path

import pytest
import yaml

from config import Config, ConfigError, load_config, parse_config, save_config


def valid_config(**overrides):
    raw = {
        "categories": [
            {"id": 1, "name": "person", "prompt": "person", "threshold": 0.7},
            {"id": 2, "name": "helmet", "prompt": "helmet"},
        ]
    }
    raw.update(overrides)
    return raw


def write_yaml(tmp_path, raw):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_parse_config_builds_typed_config_with_defaults(tmp_path):
    cfg = parse_config(valid_config(), base_dir=str(tmp_path))

    assert isinstance(cfg, Config)
    assert cfg.base_dir == str(tmp_path)
    assert cfg.categories[1].threshold == -1.0
    assert cfg.inference.confidence_threshold == 0.4
    assert cfg.output.formats == ["coco"]


def test_load_config_and_save_config_round_trip(tmp_path):
    source = write_yaml(
        tmp_path,
        valid_config(
            inference={"confidence_threshold": 0.25, "resolution": 512, "device": "cpu"},
            annotation={"bbox": False, "segmentation": True, "segmentation_encoding": "polygon"},
            output={"formats": ["coco", "yolo"], "save_viz": False},
            checkpoint={"enabled": False, "auto_resume": False, "clear_on_success": False},
        ),
    )

    loaded = load_config(str(source))
    saved = tmp_path / "saved.yaml"
    save_config(loaded, str(saved))
    reloaded = load_config(str(saved))

    assert reloaded.categories == loaded.categories
    assert reloaded.inference == loaded.inference
    assert reloaded.annotation == loaded.annotation
    assert reloaded.output == loaded.output
    assert reloaded.checkpoint == loaded.checkpoint


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        ([], "config"),
        ({}, "categories"),
        (valid_config(categories=[{"id": 1, "name": "person"}]), "categories[0].prompt"),
        (valid_config(categories=[{"id": 1, "name": "person", "prompt": "person"}, {"id": 1, "name": "helmet", "prompt": "helmet"}]), "categories[1].id"),
        (valid_config(categories=[{"id": 1, "name": "person", "prompt": "person"}, {"id": 2, "name": "person", "prompt": "worker"}]), "categories[1].name"),
        (valid_config(categories=[{"id": 1, "name": "person", "prompt": "person", "threshold": -0.5}]), "categories[0].threshold"),
        (valid_config(inference={"confidence_threshold": 1.1}), "inference.confidence_threshold"),
        (valid_config(inference={"resolution": 0}), "inference.resolution"),
        (valid_config(inference={"device": "tpu"}), "inference.device"),
        (valid_config(inference={"gpu_ops": "false"}), "inference.gpu_ops"),
        (valid_config(annotation={"bbox": False, "segmentation": False}), "annotation"),
        (valid_config(output={"formats": ["unknown"]}), "output.formats"),
        (valid_config(output={"viz_figsize": [10]}), "output.viz_figsize"),
        (valid_config(checkpoint=[]), "checkpoint"),
    ],
)
def test_parse_config_reports_invalid_field(raw, field, tmp_path):
    with pytest.raises(ConfigError, match=rf"^{re.escape(field)}"):
        parse_config(raw, base_dir=str(tmp_path))


def test_load_config_reports_yaml_syntax_with_path(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("categories: [", encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config(str(path))

    assert str(path) in str(exc_info.value)


def test_load_config_uses_application_directory_for_relative_paths(tmp_path):
    path = write_yaml(tmp_path, valid_config(output={"input_dir": "images", "output_dir": "labels"}))

    cfg = load_config(str(path))

    assert cfg.input_path.endswith(str(Path("sam3_auto_label") / "images"))
    assert cfg.output_path.endswith(str(Path("sam3_auto_label") / "labels"))
