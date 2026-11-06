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
