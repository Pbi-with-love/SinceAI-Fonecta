# hyp/knn-behavior — KNN on holiday behaviour

Branch from `part-a-final` (86e8adf). Reference: dev 2026 **65.92**, back-test 2025 **62.73**; wrong state 383 / 377;
needless 161 / 87 (spam + redundant); exact 3,982 / 3,945; missed 1,099 / 1,369 (both reproduced this session with `evaluate.py`).

## #K1 KNN_BEHAVIOR block (human's specification, grid fixed beforehand)
Hypothesis: businesses with alike holiday behaviour on the day_keys they entered behave alike on the ones they did not.

Change (code kept in `build/model_knn_experiment.py`; `model.py` is reverted):
- Behaviour vector per business: per day_key, the state **relative to the regular hours of that weekday then**:
  CLOSED / REGULAR / SHORT_CLOSE (same opening, earlier closing; closing time stored) / OTHER_HOURS; UNKNOWN = day not
  entered (or regular day off and stayed closed). Per day_key the newest season with an informative day, majority state.
- Similarity over day_keys both know (the target day_key never counts: X does not know it): share of matching states
  (SHORT_CLOSE matches fully at equal closing, half at >= 120 min apart), x 0.9, + 0.1 x attribute match (same archetype, same country).
- Neighbours = K most similar businesses that know the target day_key and share >= min_shared day_keys. Similarity-weighted vote;
  winner needs `threshold`. CLOSED -> `closed`; REGULAR -> X's regular hours (= shown, so stay quiet; it also blocks PEERS);
  SHORT_CLOSE -> X's regular opening + neighbours' lower-median closing; OTHER_HOURS -> no candidate. Below threshold or fewer than K
  neighbours -> falls through to PEERS. Not used when X has its own entry for the day_key.
- Source A: `holiday_hours_history` entered < snapshot, pool = all businesses (incl. test/demo, excl. shopping centres).
  Source B: `labels/dev_truth_history.csv` < snapshot via `build/build_knn_truth.py` -> `tables/knn_truth_<season>.json`;
  5 folds by business (seed 20261107): a dev business uses only the other 4 folds; test/demo use all 802 dev businesses.
  `model.py` reads only the table; in-sample = every business may use every dev business.
- Placement: after OWNER_PATTERN, before PEERS ("after"); and replacing OWNER_PATTERN ("repl").

Grid run in full (no pruning): source {A,B} x placement {after, repl} x min shared {2,3} x K {5,10,20} x threshold {0.6,0.7,0.8,0.9} = 96 configurations,
both seasons, out of sample. Raw output: `outputs/hyp-knn-behavior/sweep_grid.txt` / `.json` (git-ignored; reproduce with `build/sweep_knn.py`).
Min shared 2 vs 3 changes scores by <= 0.3 either way and no sign: not a deciding dimension. K: for source B, bigger K is better at high
thresholds (K=20 > 10 > 5 at 0.8); source A is bad everywhere. Threshold: higher is monotonically better; the best cell is always 0.9.

### Best row per source and placement (min shared 3, K 20, threshold 0.9; best by sum of the two scores)
| Source / placement | Dev 2026 | Back-test 2025 | Exact 26/25 | Wrong state 26/25 (ref 383/377) | Needless 26/25 (ref 161/87) | In-sample 26/25 |
|---|---|---|---|---|---|---|
| **B, after OWNER_PATTERN** | 65.80 (-0.12) | 62.79 (+0.06) | 4,009 / 3,981 | **415 / 409** | 165 / 89 | 66.20 / 63.18 |
| B, replaces OWNER_PATTERN | 65.69 (-0.23) | 62.58 (-0.15) | 3,996 / 3,954 | 408 / 394 | 165 / 89 | 66.07 / 63.00 |
| A, after OWNER_PATTERN | 63.17 (-2.75) | 60.16 (-2.57) | 4,066 / 4,058 | 590 / 617 | 218 / 128 | - |
| A, replaces OWNER_PATTERN | 63.03 (-2.89) | 60.00 (-2.73) | 4,050 / 4,032 | 582 / 600 | 218 / 128 | - |

Official `evaluate.py` on the chosen row (B/after/3/20/0.9): dev 65.8, exact 4009, harmful_wrong_state 415, spam 143, redundant 22, missed 1048;
back-test 62.79, exact 3981, harmful_wrong_state 409, spam 89, missed 1315 (matches the sweep).

Net points vs reference by day group (B/after/3/20/0.9; between holidays / eves / shopping days / major holidays / other):
dev 2026 0.0 / +2.7 / 0.0 / -9.1 / 0.0; back-test +3.0 / +4.2 / 0.0 / -4.0 / 0.0. Source A, same config: dev -124.3 / -17.7 / 0 / -6.1 / 0; back-test -136.0 / -5.3 / 0 / -4.0 / 0.
Rows touched (KNN produced a candidate, incl. "kept regular hours" votes that only keep silence): B 1,454 / 1,517; changed action: 64 / 71.
Other B cells (all 48): out-of-sample dev between -4.4 and +0.0, back-test between -4.5 and +0.06; wrong state rises in all 48 (min 394 on dev, 394 in 2025); in-sample is 0.3-1.5 points higher than out of sample (best in-sample 68.08 / 64.80 at K5 t0.8).

### Why it does not gain
- The block fires on 1,300-2,100 rows but almost all are "kept regular hours" votes (silence; the baseline missed nothing there).
  On rows where nothing earlier had a candidate and KNN actually suggests (B, K10, t0.8, ms3): dev 2026 71 exact vs **102 wrong state** + 15 spam; back-test 79 vs 97. At t0.9: 33 exact vs 30 wrong (dev), 33 vs 45 (back-test).
  Those are `closed` suggestions: neighbours that closed on the holidays they share with X are closed on the missing one ~50-70 % of the time, the same 0.2-0.6 band the reverted archetype table found. Behaviour similarity does not sharpen it enough.
- Mix of "closed" cells is why INTERDAY loses (dev -27 at t0.8): INTERDAY is mostly open for neighbours that closed on real holidays.
- The soft days the brief targets (SHORT_CLOSE on eves, OTHER_HOURS on shopping days) barely fire: SHORT_CLOSE votes rarely reach 0.9 and OTHER_HOURS has no transferable hours, so shopping days gain 0.0 and eves only +2.7 / +4.2.
- Source A (history only, the version that could ship for every business) is far worse than B: history is biased towards owners who entered and has few shared day_keys, so neighbours are noisy and wrong state goes up by 200+.

### Post-hoc variants (NOT part of the preregistered grid; reported, not selected)
Only on source B after OWNER_PATTERN, ms3, to see whether a rule fix existed. Attribute weight 0.0: -0.20 / -0.20 (K20 t0.9). `KNN_REGULAR_BLOCKS=False`: identical score at t0.9 (the regular votes were already silent). Attribute weight 0.3 (K10 t0.9): 66.14 (+0.22) / 63.07 (+0.34) but wrong state 391 / 392; weight 0.5 (K10 t0.9): 66.14 (+0.22) / 63.14 (+0.41), wrong state 384 / 381. These exceed the "small weight" in the spec, are tuned on the evaluation data, move towards the archetype table (reverted, #4 in EXPERIMENTS.md), and still fail the keep rule (wrong state > 383 / 377) and the +0.5 bar.

Decision: **REVERT** (model.py restored to `part-a-final`; build scripts, tables and this log kept).
- Keep rule: out-of-sample score must rise in BOTH seasons and wrong state must not rise. Best in-spec cell: dev -0.12, back-test +0.06, wrong state 415 / 409 (+32 / +32). Fails on dev score and on wrong state. No cell in the 96 satisfies the rule.
- Worth-merging bar (dev +0.5): not met by any configuration (best dev delta +0.00).

## Audit (`build/audit_knn.py`, output in `outputs/hyp-knn-behavior/audit.txt`) — ALL CHECKS PASSED
- Labels removed: model (source B and A, both seasons) run in a tree with no `labels/` gives byte-identical CSVs; a sys.audit hook shows no file under `labels/` opened; each season opens only its own `knn_truth_<season>.json`; source A opens no table.
- Time cut: stored tables == rebuild from truth rows dated < 2026-11-06 / < 2025-11-06 only (newest 2026-11-05 / 2025-11-05; 22,565 later rows excluded for 2025; asserted per row in the builder and per table at load in model.py). Source A: vectors identical when the 20,337 history rows entered on/after 2025-11-06 are deleted.
- Out of fold: fold map == `data/splits.csv` + seed 20261107 (folds 161/161/160/160/160); every dev business draws neighbours from the other 4 folds only (never itself, never its fold, pool >= 600); test/demo use all 802.
- Determinism: two runs byte-identical per season and source; tables built twice identical.
- No entity-ID literals in model.py; no string literal naming labels.
- Also: `sweep_knn.py` cross-checks its per-row scoring against `evaluate.py`'s total and breakdown for every configuration.
