# sam3_auto_label/config — YAML Configuration

Config files for defining classes, thresholds, inference, annotation, and output paths for SAM 3.1 auto-labeling

## Files

| File | Number of classes | When to use |
|------|-----------|----------|
| `ppe_6class.yaml` | 6 | default config — used with the main pipeline |

## ppe_6class.yaml Structure

```yaml
categories:        # list of classes + per-class threshold
  - id, name, prompt, threshold

inference:         # inference settings
  confidence_threshold, resolution, device, gpu_ops, pipeline_export

annotation:        # annotations to generate
  bbox, segmentation, segmentation_encoding (rle | polygon)

output:            # output format + paths
  formats, save_viz, input_dir, output_dir, viz_dpi, viz_figsize

checkpoint:        # resume settings
  enabled, auto_resume, clear_on_success
```

Config values are read with `yaml.safe_load()`, then converted to dataclasses and validated before loading the model. Errors will indicate the invalid field, e.g. `inference.confidence_threshold` or `categories[1].id`

Key validation rules:

- `categories` must not be empty; `id` and `name` must be unique
- category `threshold` must be `-1` or within the range `0..1`
- `confidence_threshold` must be within `0..1`; `resolution` must be greater than `0`
- booleans must be YAML booleans (`true` / `false`), not quoted strings
- `device` must be `auto`, `cpu`, `cuda`, `rocm`, or `mps`
- `viz_figsize` must have 2 positive numeric values

## All Classes (6 classes)

| id | name | prompt | threshold | Description |
|----|------|--------|-----------|----------|
| 1 | person | person | 0.7 | Person |
| 2 | helmet | helmet | 0.25 | Safety helmet |
| 3 | boots | boots | 0.25 | Safety boots/rubber boots |
| 4 | shoes | shoes | 0.25 | Canvas shoes/covered-heel shoes |
| 5 | sandals | flip-flops | 0.3 | Sandals/flip-flops |
| 6 | harness | safety harness | 0.25 | Safety harness/lanyard |

## threshold

- `threshold: -1` = use the global `inference.confidence_threshold`
- `threshold: 0` = accept all (no filtering)
- Other values = override for that specific class only

person uses 0.7 because it is abundant and clearly visible, while other classes use 0.25 to avoid missing small objects

## path

Paths in config are **absolute paths for WSL2**:

```yaml
input_dir: /mnt/e/02_Projects/auto_label/data/raw
output_dir: /mnt/e/02_Projects/auto_label/data/sam_outputs_ground_truth
```

If running directly on Windows or another machine, override at runtime:

```bash
python src/batch_segment.py --input <path> --output <path>
```

## Adding a New Config

If you need a new set of classes or thresholds:

1. Copy `ppe_6class.yaml` to a new file
2. Modify categories/thresholds as needed
3. Run: `python src/batch_segment.py --config config/<new_file>.yaml`
4. Remember to update `SUPPORTED_FORMATS` in `src/config.py` if adding a new format
