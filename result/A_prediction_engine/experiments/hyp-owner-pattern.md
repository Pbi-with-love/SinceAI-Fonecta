# hyp-owner-pattern — hypothesis #5, owner's own pattern (basis `OWNER_PATTERN`)

Branch `hyp/owner-pattern`, from `main` at `8bdc599`. Reference: **dev 2026 54.49 · back-test 2025 53.23** (reproduced
in this worktree with `python3`; `python` is not on PATH here). Keep rule: rule 7 (sum up, neither season down > 0.3).

## Analysis before any change (labels read in a scratch script only, never in `model.py`)

Scope: rows where the business never entered this `day_key` before the snapshot (history `NONE`) and the baseline had
no candidate or only `PEERS`. 6,527 rows (dev 2026) / 7,368 (back-test 2025).

- **The base rate is against us.** Among missed rows of businesses that entered *other* day_keys, 1,143 need a change
  but 4,711 are already right (dev 2026; 1,481 vs 4,692 in the back-test). Any rule has to be sharp.
- **Closures on MAJOR / SOFT / EVE_MAJOR days carry over.** Owners whose entries on other public holidays and major
  eves were all closed (≥ 2 day_keys), and whose shown hours were open, were closed on the target day 60–97 % of the
  time depending on the day_key (INDEPENDENCE_DAY lowest, NEW_YEARS_DAY highest).
- **Most of these closures are already caught by PEERS.** The rule only gains on rows where peers stay quiet. There the
  truth is closed 69 % (dev) / 59 % (back-test) without a gate.
- **Peer gate.** When the peer cell's `closed_share_among_entered` is below 0.3, owners with this pattern were mostly
  open (2 of 13 closed in dev 2026, 0 of 20 in the back-test). Above it, the rule pays.
- **Not transferable (simulated, negative on both seasons):**
  - Closure patterns onto EVE_MINOR (NYE, EPIPHANY_EVE), INTER (INTERDAY), OBS and COMM days.
  - Using the owner's mean "closer residual" against peers: monotonic, but rarely above 50 % closed.
  - Owner patterns as a *veto* of PEERS (owner never closed on same-class days): peers were still right 14 of 24 / 28 of 44.
  - Whether the owner entered other Christmas-window days ("omission means regular"): no signal.
- **Special hours (the "637 other hours" rows) are not predictable from the owner's own entries.**
  - On EVE_MINOR targets, owners whose eve entries were shortened hours were regular on 62 % of the target rows
    (189 of 304 in dev 2026), so suggesting any special hours loses −0.5 per row.
  - Copying the owner's modal special-hours string on MAJOR/SOFT/EVE_MAJOR days nets about −14 to +3 points per
    season, depending on the variant.

## #1 Closed on all other holidays entered → closed (KEEP)
Hypothesis: a business that never entered this public holiday (or major eve), but was closed on every other public
holiday / major eve it entered (≥ 2 distinct day_keys), is closed on this one too — when closing that day is not rare for
its business type (peer `closed_share_among_entered` ≥ 0.3).
Change: `explain()` gets one `if cand is None:` block right before the peer block, calling `_owner_pattern()`:
- target `day_class` (from `calendar_special_days.csv`, by country + day_key) ∈ {MAJOR, SOFT, EVE_MAJOR}
- the business has no holiday entry for this day_key in any season, and none for this date (otherwise last year /
  two years ago decide)
- its own latest entry per other day_key of class MAJOR/SOFT/EVE_MAJOR, entered before the snapshot: ≥ 2 day_keys,
  all `closed`
- peer cell (country, city tier, segment, day_key) has `closed_share_among_entered` ≥ 0.3
- evidence, e.g. `closed on all 2 holidays it entered (EASTER_MONDAY 2025-04-21, GOOD_FRIDAY 2026-04-03); 88% of peers
  who entered hours for XMAS_DAY were closed`

**How it works for a business we have never seen:** it uses only that business's own audit log (filtered by
`entered_at < snapshot`), the public calendar's `day_class`, and the peer cell of its segment. No entity IDs, no labels.
A new customer with no history (e.g. `FI-D0017`) gets nothing from this rule and falls through to peers.

Threshold sweep (real `model.py`, `evaluate.score()`, `OWNER_MIN_HOLIDAYS` = N, `OWNER_PEER_MIN` = p):

| N | p | Dev 2026 | Back-test 2025 | Sum | Harmful dev / bt |
|---|---|---|---|---|---|
| 2 | off (1.01) | 54.49 | 53.23 | 107.72 | 224 / 249 |
| 2 | 0.2 | 55.18 | 53.97 | 109.15 | 240 / 283 |
| 2 | 0.25 | 55.18 | 53.97 | 109.15 | 239 / 283 |
| **2** | **0.3** | **55.20** | **54.03** | **109.23** | 238 / 280 |
| 2 | 0.35 | 55.20 | 54.03 | 109.23 | 238 / 278 |
| 2 | 0.4 | 55.11 | 53.95 | 109.06 | 238 / 278 |
| 2 | 0.5 | 55.01 | 53.90 | 108.91 | 234 / 270 |
| 1 | 0.4 | 55.03 | 54.08 | 109.11 | 246 / 295 |
| 3 | 0.3 | 55.07 | 53.99 | 109.06 | 233 / 267 |
| 3 | 0.4 | 55.01 | 53.92 | 108.93 | 233 / 265 |
| 4 | 0.4 | 54.90 | 53.85 | 108.75 | 233 / 260 |

Chosen N = 2, p = 0.3: the best value on both seasons and the middle of the flat region 0.2–0.35, so not tuned to one
season (rule 8). Every value tried improves both seasons.

`OWNER_PATTERN` outcomes by day_key (rows / exact / wrong state / net points):

| day_key | Dev 2026 | Back-test 2025 |
|---|---|---|
| XMAS_EVE | 49 / 44 / 5 / +39 | 89 / 81 / 8 / +73 |
| XMAS_DAY | 42 / 40 / 2 / +38 | 72 / 67 / 5 / +62 |
| BOXING_DAY | 38 / 32 / 6 / +26 | 85 / 70 / 15 / +55 |
| NEW_YEARS_DAY | 39 / 38 / 1 / +37 | 70 / 65 / 5 / +60 |
| EPIPHANY | 54 / 43 / 11 / +32 | 87 / 75 / 12 / +63 |
| INDEPENDENCE_DAY | 5 / 3 / 2 / +1 | 28 / 21 / 7 / +14 |

Many of these rows were PEERS rows before (same answer, `closed`). The net gain over the baseline is +38 points (dev) and
+45 points (back-test).

Dev 2026: 54.49 → **55.20**   Back-test 2025: 53.23 → **54.03**
Wrong-state: 224 → 238 (dev), 249 → 280 (back-test)   Missed: 2,034 → 1,975 (dev), 2,167 → 2,074 (back-test)
Exact: 3,171 → 3,223 (dev), 3,267 → 3,343 (back-test)
Decision: **KEEP** — sum +1.51, both seasons up (+0.71 / +0.80).

Evaluator output, dev 2026:
```
Score: 55.2 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     3585
  precision_exact                      0.899
  recall_exact                         0.6
  harmful_suggestions                  238
  search_views_protected_pct           58.0
  closed_door_views_prevented_pct      70.8
  businesses_contacted                 737
  avg_dates_per_contacted_business     4.86
  ignored_prediction_rows_not_in_labels 10025
  breakdown: {"correct_silence": 5525, "missed": 1975, "exact": 3223, "harmful_wrong_state": 238, "same_state_off": 48, "spam_wrong_hours": 53, "redundant_confirm": 16, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}
```
Evaluator output, back-test 2025:
```
Score: 54.03 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     3742
  precision_exact                      0.893
  recall_exact                         0.591
  harmful_suggestions                  280
  search_views_protected_pct           56.4
  closed_door_views_prevented_pct      69.9
  businesses_contacted                 735
  avg_dates_per_contacted_business     5.09
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5302, "missed": 2074, "exact": 3343, "harmful_wrong_state": 280, "same_state_off": 73, "spam_wrong_hours": 46}
```
Error report: matches `evaluate.py` (55.2 / 54.03) and `explain()` on every row. Basis `OWNER_PATTERN`: 227 rows,
200 exact, 27 wrong state (dev); 431 rows, 379 exact, 52 wrong state (back-test).

Merge notes:
- No overlap with `hyp-two-year`: the rule returns nothing when the business entered this day_key in any season.
- It runs before the peer block and takes over rows where peers would also say `closed` (same answer). If `hyp-peer-tuning`
  makes peers *stay quiet* on some of those rows, this block still suggests `closed` there; re-score after that merge.

## #2 Allow one non-closed holiday (closed share ≥ 0.75 instead of all) (REVERT)
Hypothesis: owners with 3 of 4 holidays closed behave like all-closed owners; requiring all closed loses recall.
Change: `_owner_pattern()` fires when ≥ 2 day_keys are closed and they are ≥ `OWNER_CLOSED_SHARE` of the related entries.
Sweep (N = 2): share 1.0 → 55.20 / 54.03 · 0.75 → 55.10 / 54.43 · 0.6 → 55.03 / 54.06 · (0.75, peer ≥ 0.4) → 55.11 / 54.36.
Dev 2026: 55.20 → 55.10   Back-test 2025: 54.03 → 54.43
Wrong-state: 238 → 284 (dev), 280 → 328 (back-test)   Missed: 1,975 → 1,915 (dev), 2,074 → 1,979 (back-test)
Decision: **REVERT**. Rule 7 alone would pass (sum +0.30, dev −0.10), but the parameter helps only one season and costs
+46 / +48 wrong-state rows. Rule 8 says to prefer the conservative value (all closed), and rule 14 points the same way.
Evaluator output (dev 2026, then back-test 2025):
```
Score: 55.1 / 100   (dev_labels_2026.csv)
  suggestions_made 3673 · precision_exact 0.889 · recall_exact 0.607 · harmful_suggestions 284
  breakdown: {"correct_silence": 5497, "missed": 1915, "exact": 3264, "harmful_wrong_state": 284, "same_state_off": 48, "spam_wrong_hours": 53, "redundant_confirm": 17, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}
Score: 54.43 / 100   (dev_labels_2025_backtest.csv)
  suggestions_made 3861 · precision_exact 0.884 · recall_exact 0.604 · harmful_suggestions 328
  breakdown: {"correct_silence": 5278, "missed": 1979, "exact": 3414, "harmful_wrong_state": 328, "same_state_off": 73, "spam_wrong_hours": 46}
```

## Simulated only, not implemented (exact replica of the scorer on label rows; it matched the real model to 0.01 on #1 and #2)
- **Owners with a single related holiday entered, all closed** (N = 1), peer gate 0.4 / 0.5 / 0.6 / 0.7 / 0.8: dev −0.07 /
  −0.06 / −0.02 / 0.00 / 0.00, back-test +0.12 / +0.11 / +0.09 / −0.04 / −0.02. Never positive on both seasons.
- **SCHOOL_BREAK same-season siblings** (autumn-break entry → Christmas-break dates): dev 11 exact but 6 wrong state
  (autumn closures did not carry over); the back-test has no such rows, so rule 8 cannot justify it. Not attempted.

## #3 Same-season sibling dates of the same day_key (KEEP)
Hypothesis: if the owner already entered one INTERDAY date this season (e.g. 28 Dec closed) but not the others, the other
dates of the same between-holidays period follow the same entry.
Change: in `_owner_pattern()`, when the business has entries for this calendar day_key **only in this season** (none in
earlier seasons, which belong to last year / two years ago) and they all have the same value, copy it. Calendar day_keys
only (EVENT and SCHOOL_BREAK are excluded); today only INTERDAY has several dates per season. The `_owner_index()` now
keeps every entry per day_key (rule #1 still uses the latest per day_key, unchanged). Evidence: `already entered closed for
INTERDAY 2026-12-28 this season`. No parameter.
Dev 2026: 55.20 → **55.24**   Back-test 2025: 54.03 → **54.13**
Wrong-state: 238 → 238 (dev), 280 → 280 (back-test)   Missed: 1,975 → 1,973 (dev), 2,074 → 2,068 (back-test)
Rows: 2 (dev) and 6 (back-test), all exact. It fires on 0 test rows of 2026 (all OWNER_PATTERN suggestions on
`targets_2026.csv`: dev 227 + 2, test 670 + 0, demo 5 + 0), so its effect on the organisers' score is nil today.
Decision: **KEEP**. Rule 7 passes (sum +0.14, both up), no new wrong state, no tuned parameter.
Evaluator output (dev 2026, then back-test 2025):
```
Score: 55.24 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     3587
  precision_exact                      0.899
  recall_exact                         0.6
  harmful_suggestions                  238
  search_views_protected_pct           58.0
  closed_door_views_prevented_pct      70.8
  businesses_contacted                 737
  avg_dates_per_contacted_business     4.87
  ignored_prediction_rows_not_in_labels 10025
  breakdown: {"correct_silence": 5525, "missed": 1973, "exact": 3225, "harmful_wrong_state": 238, "same_state_off": 48, "spam_wrong_hours": 53, "redundant_confirm": 16, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}
Score: 54.13 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     3748
  precision_exact                      0.894
  recall_exact                         0.592
  harmful_suggestions                  280
  search_views_protected_pct           56.6
  closed_door_views_prevented_pct      70.3
  businesses_contacted                 735
  avg_dates_per_contacted_business     5.1
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5302, "missed": 2068, "exact": 3349, "harmful_wrong_state": 280, "same_state_off": 73, "spam_wrong_hours": 46}
```
Error report: matches `evaluate.py` (55.24 / 54.13) and `explain()` on every row. Output deterministic (two runs, `cmp`).
