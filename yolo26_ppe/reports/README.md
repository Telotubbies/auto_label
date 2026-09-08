# yolo26_ppe/reports — PDF Report

Complete Thai-language report (XeLaTeX) for the YOLO26 PPE project.

## Structure

```text
reports/
├── final/
│   └── report.pdf              
├── source/
│   ├── report.tex              # LaTeX source
│   ├── report_plan.md          # Report outline
│   ├── figures/                # PDF/PNG charts (training curves, confusion matrix, Pareto)
│   └── fonts/
│       └── Sarabun-Regular.ttf # Thai font
├── inputs/                     # JSON used to generate the report
│   ├── final_eval_results.json
│   ├── onnx_export_results.json
│   └── sam3_benchmark_results.json
├── metrics/                    # Metrics summaries in various formats
│   ├── comparison_report.md
│   ├── eval_all.json
│   ├── model_comparison.csv
│   ├── model_comparison.json
│   ├── train_v2_summary.json
│   └── tune_*.json             # Hyperparameter tuning results per model
└── build/                      # XeLaTeX intermediate files (.aux, .log, .toc)
```



## How to Rebuild

```bash
cd reports/source
xelatex report.tex
xelatex report.tex   # Run twice for cross-references
mv report.pdf ../final/
```

Or run via pipeline: `scripts/pipeline/08_generate_report_figures.py`

## inputs/

JSON inputs for the report — pulled from `../artifacts/evaluation/`. If data changes, regenerate before building the PDF.

## metrics/

Metrics summaries in readable formats:

- `comparison_report.md` — Model comparison table
- `model_comparison.csv` — For Excel
- `tune_*.json` — Ultralytics Tune results per model

## Cautions

- XeLaTeX is required for the Thai font (Sarabun)
- Do not edit `final/report.pdf` directly — edit `source/report.tex` and rebuild
- `build/` contains intermediate files — can be deleted when rebuilding
- If data in `inputs/` changes, the PDF must be rebuilt or the report will be out of date
