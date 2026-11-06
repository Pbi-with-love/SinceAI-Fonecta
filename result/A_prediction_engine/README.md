# Part A — Prediction engine

- `model.py`: our engine. Started as an exact copy of `examples/baseline.py`.
- `analysis/error_report.py`: where points are won and lost, by basis, history, day_key, segment… (labels are read here only, never in `model.py`).
- `EXPERIMENTS.md`: every attempt, kept or reverted, with scores.

Run from the repo root:

```bash
python result/A_prediction_engine/model.py --season 2026
python evaluation/evaluate.py --predictions outputs/ours_2026.csv
python result/A_prediction_engine/model.py --season 2025
python evaluation/evaluate.py --predictions outputs/ours_2025.csv --labels labels/dev_labels_2025_backtest.csv
```

Error report (run from the same checkout as the predictions):

```bash
python result/A_prediction_engine/analysis/error_report.py --season 2026 --predictions outputs/ours_2026.csv
python result/A_prediction_engine/analysis/error_report.py --season 2025 --predictions outputs/ours_2025.csv
```
