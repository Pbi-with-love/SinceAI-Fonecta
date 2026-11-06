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

## #2 newest older season (lookback past two seasons)
Hypothesis: if there is no entry two seasons back either, the newest entry for the `day_key` from any older season
still predicts this season (the generator repeats each business's holiday habit year to year, with some change); for
2026 this reaches the cycle-2023 entries (Dec 2023 / Jan 2024), expected about +3.0 on dev and no effect on the
back-test (there is no season before 2023).
Change: `_two_seasons_ago()` takes the newest season with `cycle <= cycle(d) - 2` (latest date in it). Basis
`TWO_YEARS_AGO` when it is two seasons back, `OLDER_SEASON` when older; evidence still names the date used.
Dev 2026: 61.17 → 64.15   Back-test 2025: 60.12 → 60.12
Wrong-state: 271 → 346 (2026), 310 → 310 (2025)   Missed: 1550 → 1245 (2026), 1631 → 1631 (2025)
Exact precision / recall: 0.882 / 0.668 → 0.86 / 0.715 (2026); back-test unchanged
Error report (2026): OLDER_SEASON 507 rows: 345 exact, 26 off, 87 wrong-state, 46 noise (net 241.5 points);
OLDER_ONLY missed rows 320 → 15.
Decision: KEEP (rule 7: sum +2.98, neither season drops). **Rule 8 caveat:** the back-test cannot measure this
(nothing older than 2023), so the gain is dev-only. No threshold was tuned (it is "use the newest entry the business
made"), which is why I kept it, but it is a separate commit so the human can drop it with one `git revert`.

```
Score: 64.15 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4473
  precision_exact                      0.86
  recall_exact                         0.715
  harmful_suggestions                  346
  search_views_protected_pct           70.9
  closed_door_views_prevented_pct      80.8
  businesses_contacted                 750
  avg_dates_per_contacted_business     5.96
  ignored_prediction_rows_not_in_labels 12232
  breakdown: {"correct_silence": 5367, "missed": 1245, "exact": 3845, "harmful_wrong_state": 346, "same_state_off": 114, "spam_wrong_hours": 140, "redundant_confirm": 21, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

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

## #3 align the old special hours to today's regular hours
Hypothesis: the generator models habits relative to regular hours ("open as usual, close at 15:00"). An old entry
that shares one end with that day's regular hours at the time should keep that end tied to the regular hours: the
copied hours are off when the old date fell on another weekday (e.g. NYE 2023 was a Sunday, 12:00-18:00 regular,
entered 12:00-17:00; this year's Wednesday regular is 10:00-20:00 and the truth is 10:00-17:00).
Change: `_align_to_regular()`: regular hours in force on the old date (published version with `effective_from` on
or before it) for the old weekday vs `regular(eid, d)`. Same opening as then → today's regular opening + old
closing; same closing as then → old opening + today's regular closing. Single-interval entries only; closed days and
REGULAR entries unchanged. Evidence still shows the old entry as entered.
Dev 2026: 64.15 → 64.34   Back-test 2025: 60.12 → 60.21
Wrong-state: 346 → 346 (2026), 310 → 310 (2025)   Missed: 1245 → 1245 (2026), 1631 → 1631 (2025)
Exact: 3845 → 3858 (2026), 3727 → 3733 (2025); same_state_off 114 → 101, 130 → 124
Error report: TWO_YEARS_AGO exact 727 → 741 (2026), 723 → 729 (2025).
Label check (scratch): opening-side shifts fixed 26 / broke 3 rows (2026) and 23 / 5 (2025); closing-side shifts
fixed 0 / broke 10 (2026) and 0 / 12 (2025), all "fixed 12:00-18:00"-style days such as EPIPHANY on a Saturday.
Decision: KEEP (rule 7: both seasons up, sum +0.28). Refined in #4.

```
Score: 64.34 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4473
  precision_exact                      0.863
  recall_exact                         0.718
  harmful_suggestions                  346
  search_views_protected_pct           71.0
  closed_door_views_prevented_pct      80.8
  businesses_contacted                 750
  avg_dates_per_contacted_business     5.96
  ignored_prediction_rows_not_in_labels 12228
  breakdown: {"correct_silence": 5367, "missed": 1245, "exact": 3858, "harmful_wrong_state": 346, "same_state_off": 101, "spam_wrong_hours": 140, "redundant_confirm": 21, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

Score: 60.21 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     4254
  precision_exact                      0.878
  recall_exact                         0.66
  harmful_suggestions                  310
  search_views_protected_pct           64.2
  closed_door_views_prevented_pct      75.6
  businesses_contacted                 746
  avg_dates_per_contacted_business     5.7
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5233, "missed": 1631, "exact": 3733, "harmful_wrong_state": 310, "same_state_off": 124, "spam_wrong_hours": 87}
```

## #4 alignment: opening side only
Hypothesis: #3's closing-side shift is wrong in general (a day that kept only the regular closing is a fixed-hours
day such as 12:00-18:00), while the opening-side shift is right; dropping the closing side should help both seasons.
Change: `_align_to_regular()` only handles "same opening as the regular hours then, different closing": it returns
today's regular opening + the old closing (if that is still a valid interval). Everything else is copied as is.
Dev 2026: 64.34 → 64.49   Back-test 2025: 60.21 → 60.38
Wrong-state: 346 → 346 (2026), 310 → 310 (2025)   Missed: 1245 → 1245 (2026), 1631 → 1631 (2025)
Exact: 3858 → 3868 (2026), 3733 → 3745 (2025); same_state_off 101 → 91, 124 → 112
Error report: TWO_YEARS_AGO exact 741 → 742 (2026), 729 → 741 (2025); OLDER_SEASON exact 344 → 353 (2026).
Decision: KEEP (rule 7: both seasons up, sum +0.32). Both seasons agree on the direction, so this is not a
dev-only choice (rule 8).

```
Score: 64.49 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4473
  precision_exact                      0.865
  recall_exact                         0.719
  harmful_suggestions                  346
  search_views_protected_pct           71.2
  closed_door_views_prevented_pct      80.8
  businesses_contacted                 750
  avg_dates_per_contacted_business     5.96
  ignored_prediction_rows_not_in_labels 12228
  breakdown: {"correct_silence": 5367, "missed": 1245, "exact": 3868, "harmful_wrong_state": 346, "same_state_off": 91, "spam_wrong_hours": 140, "redundant_confirm": 21, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

Score: 60.38 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     4254
  precision_exact                      0.88
  recall_exact                         0.662
  harmful_suggestions                  310
  search_views_protected_pct           64.6
  closed_door_views_prevented_pct      75.6
  businesses_contacted                 746
  avg_dates_per_contacted_business     5.7
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5233, "missed": 1631, "exact": 3745, "harmful_wrong_state": 310, "same_state_off": 112, "spam_wrong_hours": 87}
```

## #5 skip an old opening that falls on today's regular day off
Hypothesis: an old entry with open hours, made for a weekday the business normally opened, says little about a date
that now falls on a weekday the business is regularly closed (the special hours were a variation of a normal working
day). Label check on #2: such rows were 10 good / 9 wrong (dev) and 3 good / 15 wrong (back-test).
Change: in `_two_seasons_ago()`, if today's regular hours for d are `closed`, the old entry is open hours and the
regular hours in force on the old date (its weekday) were open, return no candidate (fall through to the next block).
An old opening on a weekday that was *also* a regular day off (e.g. a florist opening on Father's Day Sunday) is still
copied. `_regular_on()` factored out of `_align_to_regular()`; no other behaviour change.
Dev 2026: 64.49 → 64.60   Back-test 2025: 60.38 → 60.59
Wrong-state: 346 → 338 (2026), 310 → 295 (2025)   Missed: 1245 → 1247 (2026), 1631 → 1634 (2025)
Exact: 3868 → 3866 (2026), 3745 → 3742 (2025)
Error report: TWO_YEARS_AGO wrong-state 64 → 61 (2026), 90 → 75 (2025); OLDER_SEASON 87 → 82 (2026).
Decision: KEEP (rule 7: both seasons up, sum +0.32).

```
Score: 64.6 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4463
  precision_exact                      0.866
  recall_exact                         0.719
  harmful_suggestions                  338
  search_views_protected_pct           71.0
  closed_door_views_prevented_pct      80.8
  businesses_contacted                 750
  avg_dates_per_contacted_business     5.95
  ignored_prediction_rows_not_in_labels 12200
  breakdown: {"correct_silence": 5375, "missed": 1247, "exact": 3866, "harmful_wrong_state": 338, "same_state_off": 91, "spam_wrong_hours": 140, "redundant_confirm": 21, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

Score: 60.59 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     4236
  precision_exact                      0.883
  recall_exact                         0.662
  harmful_suggestions                  295
  search_views_protected_pct           64.6
  closed_door_views_prevented_pct      75.6
  businesses_contacted                 746
  avg_dates_per_contacted_business     5.68
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5248, "missed": 1634, "exact": 3742, "harmful_wrong_state": 295, "same_state_off": 112, "spam_wrong_hours": 87}
```

## #6 an old "regular hours" entry falls through
Hypothesis: an `isRegularHours` entry two or more seasons old is weak evidence (in #2's label check these rows needed
action 9 of 80 times on dev and 19 of 48 on the back-test, against about 1 in 9 for old `closed` entries), but today
it yields cand = regular = shown, which silences the row and stops the peer block from acting.
Change: `_two_seasons_ago()` returns no candidate for an old REGULAR entry, so the cascade continues.
Dev 2026: 64.60 → 64.68   Back-test 2025: 60.59 → 60.79
Wrong-state: 338 → 339 (2026), 295 → 296 (2025)   Missed: 1247 → 1242 (2026), 1634 → 1622 (2025)
Exact: 3866 → 3871 (2026), 3742 → 3754 (2025)
Error report: PEERS 477 → 484 rows, exact 388 → 393 (2026); 840 → 853 rows, exact 726 → 738 (2025).
Decision: KEEP (rule 7: both seasons up, sum +0.28). Merge note: these rows now go to whatever follows this block,
the owner-pattern block and then the peer block after the merges, so re-score this effect after each merge.

```
Score: 64.68 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4469
  precision_exact                      0.866
  recall_exact                         0.72
  harmful_suggestions                  339
  search_views_protected_pct           71.1
  closed_door_views_prevented_pct      80.8
  businesses_contacted                 750
  avg_dates_per_contacted_business     5.96
  ignored_prediction_rows_not_in_labels 12225
  breakdown: {"correct_silence": 5374, "missed": 1242, "exact": 3871, "harmful_wrong_state": 339, "same_state_off": 91, "spam_wrong_hours": 140, "redundant_confirm": 21, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

Score: 60.79 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     4249
  precision_exact                      0.884
  recall_exact                         0.664
  harmful_suggestions                  296
  search_views_protected_pct           64.7
  closed_door_views_prevented_pct      75.8
  businesses_contacted                 746
  avg_dates_per_contacted_business     5.7
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5247, "missed": 1622, "exact": 3754, "harmful_wrong_state": 296, "same_state_off": 112, "spam_wrong_hours": 87}
```

## #7 evidence text for aligned hours (no score change)
Hypothesis: none (product rule 13). After #4 the suggested opening can differ from the old entry, so the evidence
must say why. Also measured the "raise confidence when both seasons agree" part of the hypothesis.
Change: when the opening was moved, evidence is `(old date, "<old hours> (opened as usual, closed at HH:MM)")`, e.g.
`("2023-12-24", "08:00-14:00 (opened as usual, closed at 14:00)")` for a suggestion of 06:00-14:00. Docstring updated.
Dev 2026: 64.68 → 64.68   Back-test 2025: 60.79 → 60.79 (both CSVs byte-identical to #6)
Agreement (dev 2026 only; the back-test has a single older season): TWO_YEARS_AGO rows whose 2023 entry has the same
value are 85% exact and 5% wrong-state (262 rows); rows with only a 2024 entry are 86% exact and 8% wrong-state (558
rows); when the two seasons disagree on open/closed, the newer one is exact on 14 of 17. Agreement is not a useful
filter. `confidence` is not scored, and `main()` writes a constant, so nothing was changed for it.
Decision: KEEP (evidence only).

## Summary for the merge
Final (commit after #7): **dev 2026 64.68 (+10.19 vs 54.49) · back-test 2025 60.79 (+7.56 vs 53.23)**.
Wrong-state 224 → 339 (2026), 249 → 296 (2025); missed 2034 → 1242, 2167 → 1622; exact 3171 → 3871, 3267 → 3754.

- Code: `_two_seasons_ago()`, `_regular_on()`, `_align_to_regular()` plus a 2-line block right after the last-year
  block in `explain()`. Nothing else in `model.py` changed (no edits to `load()`, `entry()`, `regular()`,
  `displayed()`, the FLAG, shopping-centre, last-year or peer blocks, or `main()`).
- Merge conflict to expect: `hyp-owner-pattern` also inserts a block between last year and peers. Keep both, mine
  first: … last year → two years ago → owner pattern → peers.
- #6 sends old REGULAR entries (and #5 sends old openings that now fall on a regular day off) to the next block. Today
  that is the peer block; after the merge it is the owner-pattern block. Re-score that.
- Rule 8 decision for the human: the `OLDER_SEASON` fallback (#2) is measurable only on dev. To drop it, change
  `cycle(x) <= cycle(d) - 2` to `cycle(x) == cycle(d) - 2` in `_two_seasons_ago()` (a `git revert` of #2 would
  conflict with later commits). Measured on the final code: **dev 61.45 · back-test 60.79** (vs 64.68 · 60.79):
  precision 0.886, recall 0.671, harmful 268 on dev.
