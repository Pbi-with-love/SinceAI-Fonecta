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
