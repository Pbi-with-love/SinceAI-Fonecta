# Experiments — Part A

Rule: keep a change only if dev 2026 + back-test 2025 improves and neither score drops by more than 0.3 (see `AGENTS.md` §2.2).

| # | Name | Dev 2026 | Back-test 2025 | Decision |
|---|---|---|---|---|
| 0 | Baseline reproduction | 54.49 | 53.23 | KEEP (reference) |

## #0 Baseline reproduction
Hypothesis: copying `examples/baseline.py` into `result/A_prediction_engine/model.py` reproduces the organisers' scores.
Change: copy; only the repo-root path, docstring and default output name (`outputs/ours_<season>.csv`) changed.
Dev 2026: 54.49   Back-test 2025: 53.23
Wrong-state: 224 (dev) / 249 (back-test)   Missed: 2,034 (dev) / 2,167 (back-test)
Output for 2026 is byte-identical to `outputs/baseline_predictions_2026.csv`.
Decision: KEEP — reference point for every later experiment.

## Baseline error profile (analysis, not an experiment)
Tool: `analysis/error_report.py`. It agrees with `evaluate.py` (54.49 / 53.23) and with `explain()` on every row.
- Points still available: 2,456 dev 2026 / 2,644 back-test 2025.
- Missed rows: history NONE 1,219 (1,592) · OLDER_ONLY 792 (548) · LAST_SEASON 26 (27).
- Wrong state: PEERS 117 (143) · LAST_YEAR 81 (81) · SHOPPING_CENTRE 26 (25).
- Hypothesis verdicts and upper bounds: `AGENTS.md` section 5.
