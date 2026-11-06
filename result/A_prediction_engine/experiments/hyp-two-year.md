# hyp-two-year: hypothesis #2, two-year lookback (basis `TWO_YEARS_AGO`)

Branch `hyp/two-year`, branched from `main` at `8bdc599`.
Reference (that `main`, re-measured in this worktree): **dev 2026 54.49 · back-test 2025 53.23**.
Outputs: `outputs/hyp-two-year/<attempt>/` (not committed). Scratch analysis that reads labels lives outside the repo
and is never imported by `model.py`.

How the rule works for a business we have never seen: if the business has no entry for this `day_key` last season,
look up its own entry for the same `day_key` (as stored in the holiday history) in the season before that, entered
before the snapshot, and copy it (an `isRegularHours` entry becomes today's published regular hours). Suggest it only
if it differs from what is shown. A business without any entry for that `day_key` two seasons back gets nothing from
this rule and falls through to the peers. No IDs, no labels: only the business's own history before the snapshot.

## #1 two seasons ago, mapped by history day_key
Hypothesis: when last season has no entry for the `day_key`, the business's own entry two seasons ago
(`cycle(d) - 2`, matched by the history's own `day_key`, since the calendar cannot reach Dec 2023) predicts this
season's hours; expected about +6.7 (dev) and +6.9 (back-test) from a label-side estimate.
Change: new helper `_two_seasons_ago()` and a 2-line block right after the last-year block, only when `cand is None`.
If several dates exist for the `day_key` two seasons back (INTERDAY, EVENT, SCHOOL_BREAK), take the latest; matching
by weekday instead gave identical results in the estimate (no business has differing INTERDAY entries in one season).
Evidence: `(date two seasons ago, entry)`, e.g. `("2024-12-31", "10:00-15:00")`.
Dev 2026: 54.49 → 61.17   Back-test 2025: 53.23 → 60.12
Wrong-state: 224 → 271 (2026), 249 → 310 (2025)   Missed: 2034 → 1550 (2026), 2167 → 1631 (2025)
Exact precision / recall: 0.901 / 0.59 → 0.882 / 0.668 (2026); 0.899 / 0.578 → 0.876 / 0.659 (2025)
Error report: basis TWO_YEARS_AGO 882 rows (2026): 727 exact, 40 off, 64 wrong-state, 50 noise; 912 rows (2025):
723 exact, 57 off, 90 wrong-state, 42 noise. OLDER_ONLY missed rows 792 → 320 (2026), 548 → 27 (2025).
Decision: KEEP. Sum +13.57, both seasons up (rule 7).

```
Score: 61.17 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4073
  precision_exact                      0.882
  recall_exact                         0.668
  harmful_suggestions                  271
  search_views_protected_pct           65.9
  closed_door_views_prevented_pct      76.0
  businesses_contacted                 747
  avg_dates_per_contacted_business     5.45
  ignored_prediction_rows_not_in_labels 11225
  breakdown: {"correct_silence": 5462, "missed": 1550, "exact": 3592, "harmful_wrong_state": 271, "same_state_off": 88, "spam_wrong_hours": 95, "redundant_confirm": 20, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

Score: 60.12 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     4255
  precision_exact                      0.876
  recall_exact                         0.659
  harmful_suggestions                  310
  search_views_protected_pct           64.1
  closed_door_views_prevented_pct      75.6
  businesses_contacted                 746
  avg_dates_per_contacted_business     5.7
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5232, "missed": 1631, "exact": 3727, "harmful_wrong_state": 310, "same_state_off": 130, "spam_wrong_hours": 88}
```
