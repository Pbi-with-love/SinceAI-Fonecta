# build/ — KNN on holiday behaviour (hyp/knn-behavior)

Standard library only (no new dependencies).

| File | Purpose |
|---|---|
| `build_knn_truth.py` | Source B: behaviour vectors of the 802 dev businesses from `labels/dev_truth_history.csv` (dates < snapshot), 5 fixed folds by business (seed 20261107) -> `tables/knn_truth_<season>.json`. The only script here that reads `labels/` for inputs. |
| `sweep_knn.py` | Grid sweep, analysis only (reads labels to score, with `evaluation/evaluate.py`'s own `score()`). |
| `audit_knn.py` | Audit: labels/ removed, time cut, out-of-fold pools, determinism, no entity IDs. |
| `model_knn_experiment.py` | The experimental `model.py` (KNN_BEHAVIOR block, source A and B). **`model.py` itself is reverted to `part-a-final`.** To reproduce: `cp build/model_knn_experiment.py model.py`, then run the scripts above (they `import model`). |
