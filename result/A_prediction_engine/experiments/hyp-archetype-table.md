# hyp-archetype-table — archetype habit table (basis `ARCHETYPE_TABLE`)

Branch `hyp/archetype-table`, from `main` at `6b2146f` (Part A freeze exception approved by the human on 2026-11-07).
Reference, reproduced in this worktree with `python3`: **dev 2026 65.92 · back-test 2025 62.73**, wrong state 383 / 377,
needless 161 (140 + 21) / 87 (87 + 0), missed 1,095 / 1,369, exact 3,982 / 3,945.
Keep rule (human, AGENTS.local.md): the **out-of-sample** score rises in **both** seasons **and** the wrong-state count
does not rise in either season.

## What was built

| File | Role |
|---|---|
| `build/build_archetype_table.py` | Learner. The only script that reads `labels/dev_truth_history.csv`. Writes `tables/archetype_table_<season>.json` and prints the time-cut audit |
| `tables/archetype_table_2026.json`, `tables/archetype_table_2025.json` | Counts only: `cell -> [businesses, business_days, closed_days]`, for the table `all` and `fold0`…`fold4`, plus `meta` (cut, seed, newest training date per table, input SHA-256) and the fold map. ~0.95 MB each, deterministic bytes |
| `model.py` | New `if cand is None:` block calling `_archetype_candidate()`, lazy loader `_arch()`, `_arch_table_name()`. Reads only the table file of its own season, plus `data/splits.csv` and `data/categories.csv` |
| `build/run_archetype.py` | Experiment runner: runs `model.main()` unchanged with `ARCH_PLACE` / `ARCH_THRESHOLD` / `ARCH_IN_SAMPLE` overridden, scores with `evaluate.py`; `--sweep` reproduces the table below; `--in-sample` is the comparison switch |
| `build/audit_archetype.py` | Leakage / snapshot / out-of-fold / determinism audit in code (output below) |

How the human's 7 rules are implemented:
1. `model.py` never opens `labels/`: the learner writes `tables/`, and `model.py` reads only those tables. Checked at runtime with a `sys.audit` hook (audit §3).
2. **Time cut.** The 2026 tables use truth dates `< 2026-11-06`; the 2025 tables use `< 2025-11-06`. Asserted per row and per table in the learner. The audit rebuilds the tables from pre-cut rows and compares them. `model.py` asserts that the file's `meta.snapshot` equals its own snapshot and that every newest training date is before it. Newest training dates: 2026 → 2026-11-05 (every table), 2025 → 2025-11-05 / 2025-11-04 (fold4).
3. **Out of sample.** 5 fixed folds by business: sorted dev IDs from `data/splits.csv`, `random.Random(20261107).shuffle`, `i % 5` (sizes 161/161/160/160/160). A dev business in fold k uses `fold<k>`, which was learned from the other ~641 businesses; test and demo businesses use `all`. `model.py` derives the fold map itself and asserts that it equals the map stored in the table file. In-sample (comparison only) = every dev business uses `all`.
4. **Minimum cell 15 businesses**, with back-off `L1 segment×day_key×country → L2 archetype×day_key×country → L3 archetype×day_key → L4 archetype×day_class`. The first cell with ≥ 15 businesses decides; if its P(closed) is below the threshold, stay quiet (no further back-off).
5. **Regular hours open only.** In training: business-days whose published regular hours, in force on that truth date, were open for that weekday (9,662 / 6,126 truth rows skipped). At prediction time: `regular(eid, d)` as of the snapshot is not `closed`. One extra guard: the block stays quiet if the owner already entered something for this very date (8 rows reach the block with such an entry on dev 2026).
6. Configurations (a) and (b) are both implemented behind `ARCH_PLACE` ("a" = new block after owner pattern, before peers; "b" = replaces the peer block). Swept below.
7. Evidence, e.g. *"In earlier seasons, hair salon businesses in Sweden whose regular hours said open were closed on Christmas Eve in 90% of cases (n=20 businesses, 40 business-days; dev history before 2026-11-06)."* `explain_full()` unchanged. `_evidence_lines()` unchanged: its generic branch already handles a full sentence.

## Results: config × threshold × season

Real `model.py` + `evaluation/evaluate.py` for every cell (`python3 result/A_prediction_engine/build/run_archetype.py --sweep`).
OOS = out of sample (the default). Needless = `spam_wrong_hours` + `redundant_confirm`. Wrong = `harmful_wrong_state`.

| config | thr | dev 2026 OOS | wrong | needless (spam+red.) | missed | back-test 2025 OOS | wrong | needless (spam+red.) | missed | dev 2026 in-sample | 2025 in-sample |
|---|---|---|---|---|---|---|---|---|---|---|---|
| off (= main) | - | 65.92 | 383 | 161 (140+21) | 1095 | 62.73 | 377 | 87 (87+0) | 1369 | - | - |
| a | 0.80 | 65.95 | **384** | 161 (140+21) | 1092 | 62.82 | **378** | 87 (87+0) | 1363 | 65.97 | 62.86 |
| a | 0.85 | **65.97** | 383 | 161 (140+21) | 1092 | **62.84** | 377 | 87 (87+0) | 1363 | 65.97 | 62.84 |
| **a** | **0.90** | **65.95** | **383** | 161 (140+21) | 1093 | **62.82** | **377** | 87 (87+0) | 1364 | 65.95 | 62.82 |
| a | 0.95 | 65.92 | 383 | 161 (140+21) | 1095 | 62.77 | 377 | 87 (87+0) | 1367 | 65.92 | 62.79 |
| b | 0.80 | 65.51 | 296 | 161 (140+21) | 1247 | 61.35 | 265 | 87 (87+0) | 1626 | 65.97 | 61.87 |
| b | 0.85 | 64.73 | 287 | 161 (140+21) | 1304 | 60.22 | 255 | 87 (87+0) | 1707 | 65.27 | 60.88 |
| b | 0.90 | 64.12 | 280 | 161 (140+21) | 1349 | 59.12 | 244 | 87 (87+0) | 1788 | 64.16 | 59.32 |
| b | 0.95 | 63.51 | 278 | 160 (140+20) | 1386 | 57.94 | 237 | 87 (87+0) | 1867 | 63.58 | 58.06 |

Against the keep rule:
- **(a) 0.80** fails: +1 wrong-state row in each season (NO-00108 Boxing Day, archetype × day_key cell at 82 %, truth was open as shown).
- **(a) 0.85** and **(a) 0.90** pass: the score rises in both seasons and wrong state is unchanged.
- **(a) 0.95** fails: the dev 2026 score does not rise.
- **(b)** fails at every threshold. It removes 87–140 wrong-state rows per season, but misses 150–500 more rows: the table cannot reach the peer rule's exact closures at P ≥ 0.80. The score drops 0.4–4.8 points.

In-sample vs out-of-sample: **no gap for config (a)** (65.95 / 62.82 both ways at 0.90). Config (b) shows the gap that rule 3 is there to expose: up to +0.66 (back-test, 0.85) in sample.

**Chosen setting: (a) at 0.90.** 0.85 is one exact row better per season (NO-00212, Christmas Day in both seasons; cell 89 % in 2026). But 0.80, the next step down, already adds a wrong-state row in each season. 0.90 keeps a margin from that cliff and adds 23 instead of 37 unscored test suggestions (rule 14: when unsure, stay quiet; rule 8: prefer the conservative value when the gain is this small).

### Evaluator output, chosen setting (default `model.py`: config a, 0.90, out of sample)

```
$ python3 result/A_prediction_engine/model.py --season 2026 --out outputs/hyp-archetype-table/ours_2026.csv
wrote 17376 actions -> outputs/hyp-archetype-table/ours_2026.csv
$ python3 evaluation/evaluate.py --predictions outputs/hyp-archetype-table/ours_2026.csv

Score: 65.95 / 100   (dev_labels_2026.csv)
  rows                                 11100
  rows_needing_action                  5398
  suggestions_made                     4626
  precision_exact                      0.861
  recall_exact                         0.741
  harmful_suggestions                  383
  search_views_protected_pct           73.3
  closed_door_views_prevented_pct      84.7
  businesses_contacted                 749
  avg_dates_per_contacted_business     6.18
  ignored_prediction_rows_not_in_labels 12739
  breakdown: {"correct_silence": 5366, "missed": 1093, "exact": 3984, "harmful_wrong_state": 383, "same_state_off": 91, "spam_wrong_hours": 140, "redundant_confirm": 21, "flag_correct": 11, "missed_closed_business": 4, "suggest_to_closed_business": 7}

$ python3 result/A_prediction_engine/model.py --season 2025 --out outputs/hyp-archetype-table/ours_2025.csv
wrote 4526 actions -> outputs/hyp-archetype-table/ours_2025.csv
$ python3 evaluation/evaluate.py --predictions outputs/hyp-archetype-table/ours_2025.csv --labels labels/dev_labels_2025_backtest.csv

Score: 62.82 / 100   (dev_labels_2025_backtest.csv)
  rows                                 11118
  rows_needing_action                  5654
  suggestions_made                     4526
  precision_exact                      0.873
  recall_exact                         0.699
  harmful_suggestions                  377
  search_views_protected_pct           68.1
  closed_door_views_prevented_pct      81.9
  businesses_contacted                 747
  avg_dates_per_contacted_business     6.06
  ignored_prediction_rows_not_in_labels 0
  breakdown: {"correct_silence": 5228, "missed": 1364, "exact": 3950, "harmful_wrong_state": 377, "same_state_off": 112, "spam_wrong_hours": 87}
```

In sample, same setting (`build/run_archetype.py --season <s> --in-sample`): `Score: 65.95 / 100 (dev_labels_2026.csv)`,
`Score: 62.82 / 100 (dev_labels_2025_backtest.csv)`.

Error report (`analysis/error_report.py`, "CSV matches model.explain() on every row" in both seasons), by basis:

| basis | dev 2026 rows / exact / wrong | back-test 2025 rows / exact / wrong | main (reference) |
|---|---|---|---|
| ARCHETYPE_TABLE | 107 / 102 / 4 | 218 / 207 / 11 | — |
| PEERS | 305 / 202 / 103 | 475 / 342 / 133 | 410 / 302 / 107 · 688 / 544 / 144 |
| NONE (missed) | 1,081 | 1,353 | 1,083 · 1,358 |

## Why the gain is so small (analysis; labels read in a scratch script only, never in `model.py`)

Probe on dev 2026, config (a) with the table muted: 6,364 rows reach the block. 5,479 are eligible (regular hours open, nothing entered for the date).
- **Where the table is confident, the peer rule already fires.** Among eligible rows with cell P(closed) ≥ 0.80 (214 rows), peers suggest `closed` on 210. Truth was closed on 194 of the 214 (91 %). So config (a) mostly takes over peer rows with the same answer: about 105 / 213 rows move from basis PEERS to ARCHETYPE_TABLE with identical outcomes. It adds new suggestions only where `peer_benchmarks.csv` has no usable cell:
  - NO-00212 optician (Norway, town): no peer cell at all.
  - SE-00640 hair salon (Sweden, ski resort): no peer cell at all.
  - SE-00269 massage (Sweden, town, Epiphany): the peer cell has an empty `closed_share_among_entered`.
  That is 2 rows on dev 2026, 5 on the back-test, all exact.
- **The target rows are not a type-level habit.** The 459 missed "shown open, actually closed" rows on dev 2026 that reach the block sit mostly in cells with P(closed) 0.2–0.6 (mode ≈ 0.4); 49 have no cell, and only 4 are at ≈ 0.8 or above. A base rate per business type cannot pick them out: in those cells most businesses that reach this block stay open (for example, in the 0.30–0.35 bucket, 43 of 243 rows were closed).
- **Selection effect:** rows reaching the block are less often closed than the cell's base rate. Bucket 0.50–0.55: 59 of 205 closed. The businesses with no own history for a day are disproportionately the ones open as usual. At the top the table is well calibrated: 0.80–0.85 → 85 %, 0.85–0.90 → 85 %, 0.90–0.95 → 95 %, ≥ 0.95 → 97 % closed.
- **Config (b)** removes the peer rule's mid-confidence closures (peer cells at 50–80 %). That cuts wrong state by about 90–140 rows, but the exact rows it loses are worth more.

## Audit (`python3 result/A_prediction_engine/build/audit_archetype.py`, exit 0)

```
1-2. time cut and out-of-fold tables
  OK    2026: 58711 truth rows kept, all dated < 2026-11-06
  OK    2026: stored tables (all + 5 folds) == rebuild from rows dated < 2026-11-06 only
  OK    2026: newest training date per table ['2026-11-05'] all < 2026-11-06
  OK    2026: build() drops rows >= 2026-11-06 by itself (same result from all rows)
  OK    2026: fold0 == table from the 641 businesses outside fold 0
  OK    2026: fold1 == table from the 641 businesses outside fold 1
  OK    2026: fold2 == table from the 642 businesses outside fold 2
  OK    2026: fold3 == table from the 642 businesses outside fold 3
  OK    2026: fold4 == table from the 642 businesses outside fold 4
  OK    2026: stored fold map == data/splits.csv + seed 20261107
  OK    2025: 36146 truth rows kept, all dated < 2025-11-06
  OK    2025: stored tables (all + 5 folds) == rebuild from rows dated < 2025-11-06 only
  OK    2025: newest training date per table ['2025-11-04', '2025-11-05'] all < 2025-11-06
  OK    2025: build() drops rows >= 2025-11-06 by itself (same result from all rows)
  OK    2025: table differs from one learned with 2026-season rows
  OK    2025: fold0 == table from the 641 businesses outside fold 0
  OK    2025: fold1 == table from the 641 businesses outside fold 1
  OK    2025: fold2 == table from the 642 businesses outside fold 2
  OK    2025: fold3 == table from the 642 businesses outside fold 3
  OK    2025: fold4 == table from the 642 businesses outside fold 4
  OK    2025: stored fold map == data/splits.csv + seed 20261107
2b. model.py uses the out-of-fold table for every dev business
  OK    2026: 802 dev businesses -> own out-of-fold table, 2215 others -> all (mismatches: [])
  OK    2026: no dev business is scored with a table that contains it
  OK    2026: in-sample switch -> 'all' for everyone
  OK    2025: 802 dev businesses -> own out-of-fold table, 0 others -> all (mismatches: [])
  OK    2025: no dev business is scored with a table that contains it
  OK    2025: in-sample switch -> 'all' for everyone
3-4. model.py never opens labels/; each season opens its own table; deterministic CSVs
  OK    2026 run 1: 27 files opened, none under labels/ []
  OK    2026 run 1: opens tables/archetype_table_2026.json only
  OK    2026 run 2: 27 files opened, none under labels/ []
  OK    2026 run 2: opens tables/archetype_table_2026.json only
  OK    2026: two model.py runs give byte-identical CSVs (sha256 49c1b0cfd085c75d)
  OK    2025 run 1: 27 files opened, none under labels/ []
  OK    2025 run 1: opens tables/archetype_table_2025.json only
  OK    2025 run 2: 27 files opened, none under labels/ []
  OK    2025 run 2: opens tables/archetype_table_2025.json only
  OK    2025: two model.py runs give byte-identical CSVs (sha256 fccdac65a0f06033)
  OK    model.py code has no string literal naming labels (found: [])
  OK    table build run 1: byte-identical to the committed tables (2026 bcf9324e0f52e986, 2025 b77bfc4d0c91c8df)
  OK    table build run 2: byte-identical to the committed tables (2026 bcf9324e0f52e986, 2025 b77bfc4d0c91c8df)

ALL CHECKS PASSED
```

## #1 Archetype habit table, config (a), threshold 0.90
Hypothesis: what businesses of the same type actually did on a special day, learned from the organisers' training data
(dev truth history), finds closures that `peer_benchmarks.csv` misses, because the peer file counts only owners who
entered hours.
Change: a new `ARCHETYPE_TABLE` block after owner pattern, before peers. It suggests `closed` when the first cell with
≥ 15 businesses (segment×day_key×country → archetype×day_key×country → archetype×day_key → archetype×day_class) shows
P(closed) ≥ 0.90, the weekday's regular hours are open and the owner entered nothing for the date. Out-of-fold tables
are used for dev businesses. `CONFIDENCE["ARCHETYPE_TABLE"] = 0.95`, measured out of sample with the same add-one
smoothing as the other bases: (102 + 207 + 1) / (107 + 218 + 2).
Dev 2026: 65.92 → **65.95** (in sample 65.95)   Back-test 2025: 62.73 → **62.82** (in sample 62.82)
Wrong-state: 383 → 383 · 377 → 377   Missed: 1,095 → 1,093 · 1,369 → 1,364   Needless: 161 → 161 · 87 → 87
Decision: **KEEP by the human's rule**. The out-of-sample score rises in both seasons and wrong state does not rise
(AGENTS.md rule 7 also holds: sum +0.12, neither season down). **The gain is tiny**: +2 / +5 exact rows from 3
businesses that have no usable peer cell. The hypothesis's main target, missed no-history closures, is not reached.
The human may reasonably prefer not to merge ~1.9 MB of labels-derived tables for 7 rows.

## Did not work
- **Config (b), replace the peer rule**, at 0.80–0.95: −0.41 to −4.79 points per season (table above). It cuts wrong
  state a lot (383 → 278–296, 377 → 237–265) but misses 150–500 more rows.
- **(a) at 0.80**: +1 wrong-state row per season. **(a) at 0.95**: no dev gain.

## Doubts and leakage risks
- **Same-population training.** The tables are learned from labels of the dev businesses we also score. The 5-fold
  out-of-fold scheme removes self-leakage (audit §2). For (a) at 0.90 the in-sample and out-of-sample scores are
  identical, so the reported score does not depend on that.
- **Test businesses see a bigger table.** They use `all` (802 businesses vs ~641 per fold), so more fine cells pass the
  15-business minimum. On the full `targets_2026.csv`, config (a) at 0.90 adds 23 unscored test suggestions (all
  `closed`); 0.85 would add 37. The calibration above (≥ 0.90 → 95–97 % closed out of sample) is the best estimate of
  their accuracy.
- **`CONFIDENCE["PEERS"]` (0.77) is now stale.** The table takes over PEERS' most certain rows. The remaining PEERS
  rows were exact 202 / 305 (dev 2026) and 342 / 475 (back-test), about 0.70 smoothed. I did not change it; it is
  outside this experiment's territory.
- **The back-test table has one winter of data** (Dec 2024 / Jan 2025, plus 2024–2025 spring holidays), so its winter
  cells are smaller than the 2026 ones.
- **Regular-hours filter in training** uses the published regular hours in force on each truth date
  (`effective_from ≤ date < cut`). It does not use the label file `dev_regular_hours_truth.csv`. Businesses closed for
  good are not removed from the counts (their closure is not timestamped), which can only push P(closed) up slightly.
- `predictions_2026.csv` at the repo root was **not** regenerated: the hook forbids it on this branch. Regenerate it
  on `main` if this is merged.
- `build/run_archetype.py` overrides class attributes for the sweep. The default `model.py` (config a, 0.90, out of
  sample) does not read environment variables or flags for this, so its output stays deterministic (audit §4).
