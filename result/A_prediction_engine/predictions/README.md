# Part A predictions (frozen at `part-a-final`)

Output of `result/A_prediction_engine/model.py`. One row per action; rows not listed count as `NO_ACTION`.
Columns: `entity_id,date,action,hours,confidence`. The `confidence` column is a constant `0.6` inherited from the
organisers' baseline; the evaluator reads it but never uses it. Real confidence levels come from `explain_full()`.

| File | Season | Rows | Score | How it was made |
|---|---|---|---|---|
| `predictions_2026.csv` | 2026 (dev + test + demo) | 17,351 | dev 65.92 | `python result/A_prediction_engine/model.py --season 2026 --out result/A_prediction_engine/predictions/predictions_2026.csv` |
| `backtest_2025.csv` | 2025 back-test (dev only) | 4,521 | back-test 62.73 | `python result/A_prediction_engine/model.py --season 2025 --out result/A_prediction_engine/predictions/backtest_2025.csv` |

`predictions_2026.csv` is byte-identical to the file at the repo root, which is the copy to submit
(`START_HERE.md`: "`predictions_2026.csv` in the repository root"). Regenerate both together if the model ever changes.
