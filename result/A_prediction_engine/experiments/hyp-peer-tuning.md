# hyp-peer-tuning: AGENTS.md section 5, #3 (peer special hours) + #4 (peer bias)

Branch `hyp/peer-tuning`, started from `main` at `8bdc599`. Reference scores: **dev 2026 54.49 · back-test 2025 53.23**.
Only the peer block in `model.py` is changed (`_peer_candidate()`, called where the baseline peer rule was).
All scores below are pasted from `evaluation/evaluate.py`; the throwaway analysis scripts live in
`outputs/hyp-peer-tuning/` (not committed) and read labels for analysis only.

## Analysis before the experiments (labels used for study only)

Rows that reach the peer block (no FLAG, no shopping-centre candidate, no last-year candidate): 8,223 (dev 2026) and
8,464 (back-test 2025). The baseline peer rule (`closed_share_among_entered ≥ 0.7` and `share_entered_closed ≥ 0.15`)
earns +669.7 / +846.0 points there, with 117 / 143 wrong-state rows.

**Peer bias (#4).** `labels/dev_truth_history.csv`, 2024 season (not one of the two scored seasons): for dev businesses
that had entered **nothing** for that date and were shown open, the share that was actually closed, by the peers'
`share_entered_closed` (share of *all* peers that entered "closed"):

| share_entered_closed | 0–.05 | .05–.10 | .10–.15 | .15–.20 | .20–.25 | .25–.30 | .30–.35 | .35–.40 | ≥ .40 |
|---|---|---|---|---|---|---|---|---|---|
| actually closed (2024) | 0.08 | 0.27 | 0.40 | 0.50 | 0.69 | 0.79 | 0.83 | 0.94 | 0.95 |
| actually closed (peer-block rows, 2025) | 0.07 | 0.29 | 0.40 | 0.57 | 0.75 | 0.83 | 0.89 | 0.96 | 0.98 |
| actually closed (peer-block rows, 2026) | 0.08 | 0.28 | 0.39 | 0.52 | 0.76 | 0.82 | 0.92 | 0.94 | 0.98 |

Suggesting `closed` earns +1 if right and −1 if wrong, so it pays only when more than half are closed. The break-even
sits at `share_entered_closed` ≈ 0.15 in all three seasons, which supports the existing 0.15 floor. Above it, the
second threshold (`closed_share_among_entered ≥ 0.7`) is stricter than needed: with `share_entered_closed ≥ 0.15`,
cells with `closed_share_among_entered` 0.5–0.7 were closed 62–65 % of the time (2025 and 2026).

By calendar `day_class` (2024, non-entering businesses, `share_entered_closed ≥ 0.15`): on **minor eves**
(`EVE_MINOR`: New Year's Eve, Epiphany Eve, Maundy Thursday, Easter Saturday, May Eve, Pentecost Eve) only 30–50 % were
closed even where 50–90 % of enterers were closed; public holidays (`MAJOR`, `SOFT`) and the major eves
(`EVE_MAJOR`: Christmas Eve, Midsummer Eve) were mostly closed. The same split shows in the baseline peer rule's points
on dev rows: EVE_MINOR −3.0 / −10.0, INTER −4.0 / −2.1, COMM −2.0 / −2.0 (2025 / 2026, measured at
`closed_share_among_entered ≥ 0.5`), while MAJOR, EVE_MAJOR and SOFT are strongly positive in both seasons.

**Peer special hours (#3).** On shown-open peer-block rows, suggesting the peer median special hours
(`median_open_special`–`median_close_special`) loses points on every `day_key` in both seasons (e.g. INTERDAY
−357 / −392, EPIPHANY_EVE −121 / −124, XMAS_EVE −27 / −23). Using the business's own opening time plus the peer median
closing time is no better. The reason: when peers entered special hours, the business we are looking at usually still
keeps its shown hours (−0.5 per needless message) or is closed (−1), and an open suggestion is rarely exact.

## #1 Peer closed only on public holidays and major eves
Hypothesis: peer "closed" majorities do not carry over to businesses that entered nothing on minor eves, inter-days,
commercial days and observances; dropping the peer `closed` suggestion on those day classes removes wrong-state errors.
Change: `_peer_candidate()` suggests `closed` only when the calendar `day_class` of (country, date) is `MAJOR`,
`EVE_MAJOR` or `SOFT`. Thresholds unchanged (0.7 / 0.15). Evidence text is now readable, e.g.
"86% of similar businesses (cafe, capital, FI) that entered XMAS_DAY hours were closed; 41% of all of them entered closed".
Dev 2026: 54.49 → 54.59   Back-test 2025: 53.23 → 53.19   (sum 107.72 → 107.78)
Wrong-state: 224 → 196 (249 → 228)   Missed: 2034 → 2063 (2167 → 2196)
Exact precision 0.901 → 0.909 (0.899 → 0.903); recall 0.590 → 0.586 (0.578 → 0.574)
Error report, PEERS basis: 912 → 859 rows, wrong 117 → 89, points 669.7 → 674.8 (2026); 1,123 → 1,088 rows,
wrong 143 → 122 (2025). By history: rows with no history for the day_key +11.0 / +3.0 points, rows with only older
history −5.9 / −5.0 (those are the rows the two-year lookback will take after its merge).
Generalises: uses only the public calendar's day class for the business's country and date, so it applies the same
way to any business, including one we have never seen.
Decision: KEEP — sum improves (+0.06), neither season drops more than 0.3 (back-test −0.04), 28 / 21 fewer wrong-state
suggestions.

```
Score: 54.59 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     3466
  precision_exact                      0.909
  recall_exact                         0.586
  harmful_suggestions                  196
  search_views_protected_pct           56.9
  closed_door_views_prevented_pct      68.8
  businesses_contacted                 737
  avg_dates_per_contacted_business     4.7
  ignored_prediction_rows_not_in_labels 9659
  breakdown: {"correct_silence": 5553, "missed": 2063, "exact": 3149, "harmful_wrong_state": 196, "same_state_off": 48, "spam_wrong_hours": 53, "redundant_confirm": 16, "flag_correct": 11, "missed_closed_business": 7, "suggest_to_closed_business": 4}

Score: 53.19 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     3591
  precision_exact                      0.903
  recall_exact                         0.574
  harmful_suggestions                  228
  search_views_protected_pct           54.9
  closed_door_views_prevented_pct      67.3
  businesses_contacted                 735
  avg_dates_per_contacted_business     4.89
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5331, "missed": 2196, "exact": 3244, "harmful_wrong_state": 228, "same_state_off": 73, "spam_wrong_hours": 46}
```

## #2 Peer closed when a majority of enterers closed (0.7 → 0.5)
Hypothesis: with `share_entered_closed ≥ 0.15` and the day-class gate of #1, `closed_share_among_entered ≥ 0.7` is
stricter than the data supports; cells at 0.5–0.7 were closed 62–65 % of the time, so suggesting `closed` there earns
more exact hits than it costs in wrong-state errors.
Change: `PEER_MIN_CLOSED_AMONG_ENTERED` 0.7 → 0.5. `PEER_MIN_SHARE_ENTERED_CLOSED` stays 0.15.

Threshold grid with the real `model.py` (on top of #1), dev 2026 / back-test 2025, wrong-state in brackets:

| closed_among_entered ≥ | share_entered_closed ≥ | dev 2026 | back-test 2025 |
|---|---|---|---|
| 0.7 (#1) | 0.15 | 54.59 (196) | 53.19 (228) |
| 0.6 | 0.15 | 55.36 (251) | 54.45 (292) |
| **0.5** | **0.15** | **56.11 (289)** | **55.18 (338)** |
| 0.4 | 0.15 | 56.14 (318) | 55.32 (366) |
| 0.5 | 0.125 | 55.64 (354) | 54.79 (407) |
| 0.5 | 0.175 | 56.25 (245) | 55.10 (289) |
| 0.5 | 0.2 | 55.59 (222) | 54.27 (258) |
| 0.6 | 0.175 | 55.61 (221) | 54.49 (260) |

Choice: 0.5 / 0.15. 0.4 adds +0.03 / +0.14 but the 0.4–0.5 cells are a coin flip (closed 50–56 %), so rule 14
says stay quiet there. Moving the 0.15 floor to 0.175 helps dev (+0.14) and hurts the back-test (−0.08), so rule 8
keeps the simpler, unchanged value; 0.15 is also the break-even in the independent 2024 calibration above.
Dev 2026: 54.59 → 56.11   Back-test 2025: 53.19 → 55.18   (vs reference 54.49 / 53.23: +1.62 / +1.95)
Wrong-state: 196 → 289 (228 → 338)   Missed: 2063 → 1834 (2196 → 1902)   Exact: 3149 → 3324 (3244 → 3466)
Exact precision 0.909 → 0.890 (0.903 → 0.884); recall 0.586 → 0.618 (0.574 → 0.613)
Error report, PEERS basis: 859 → 1,128 rows, points 674.8 → 756.7 (2026); 1,088 → 1,420 rows, 844.0 → 956.0 (2025).
By history: no history for the day_key +33.0 / +72.0 points, only older history +48.9 / +40.0. The second group will
mostly go to the two-year lookback after its merge, so expect roughly +0.6 / +1.3 score from this change after it.
Trade-off: this change raises wrong-state suggestions (−1 each) because each extra one is outweighed by ~2 exact
hits; it does not meet the "fewer wrong-state" target by itself (#1 does).
Generalises: two shares from `peer_benchmarks.csv` for the business's own (country, city tier, segment, day_key)
cell; any business with a peer cell gets the same rule.
Decision: KEEP — sum +3.51, both seasons up.

```
Score: 56.11 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     3735
  precision_exact                      0.89
  recall_exact                         0.618
  harmful_suggestions                  289
  search_views_protected_pct           60.2
  closed_door_views_prevented_pct      74.7
  businesses_contacted                 752
  avg_dates_per_contacted_business     4.97
  ignored_prediction_rows_not_in_labels 10411
  breakdown: {"correct_silence": 5513, "missed": 1834, "exact": 3324, "harmful_wrong_state": 289, "same_state_off": 48, "spam_wrong_hours": 53, "redundant_confirm": 17, "flag_correct": 11, "missed_closed_business": 7, "suggest_to_closed_business": 4}

Score: 55.18 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     3923
  precision_exact                      0.884
  recall_exact                         0.613
  harmful_suggestions                  338
  search_views_protected_pct           58.2
  closed_door_views_prevented_pct      73.1
  businesses_contacted                 750
  avg_dates_per_contacted_business     5.23
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5293, "missed": 1902, "exact": 3466, "harmful_wrong_state": 338, "same_state_off": 73, "spam_wrong_hours": 46}
```
