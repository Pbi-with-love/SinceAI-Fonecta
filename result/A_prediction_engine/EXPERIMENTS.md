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

## #1 hyp/two-year merged (#2 two-year lookback) — KEEP (human: "giữ", 2026-11-07)
Hypothesis: when last season has no entry for the day_key, the business's own entry from two (or more) seasons back predicts it.
Change: new blocks TWO_YEARS_AGO (two seasons back) and OLDER_SEASON (three or more), matched by the history's own day_key; old opening aligned to today's regular opening; skipped on a regular day off; old "regular hours" entries fall through. Full log: `experiments/hyp-two-year.md`. Merge commit 77da749 (no conflicts).
Dev 2026: 54.49 → 64.68   Back-test 2025: 53.23 → 60.79
Wrong-state: 224 → 339 (249 → 296)   Missed: 2,038 → 1,246 (2,167 → 1,622)   Exact: 3,171 → 3,871 (3,267 → 3,754)
Checks on merged main: both seasons byte-identical on two runs; snapshot audit PASS on both seasons (every history row used has entered_at < snapshot; newest used 2025-11-05T18:59 for 2025); no labels/ or entity IDs in model.py.
Why the back-test beat the Phase-2 estimate (+7.56 vs ~+7.4): on the 548 rows the estimate covered, +7.82 (16 more exact than a plain copy thanks to the opening alignment, 30 same-state-off at +0.2, 18 left quiet); on all other rows −0.26 (70 newly messaged rows that were already right −50.5 pts, PEERS → TWO_YEARS_AGO +25.4, unreachable last-season EVENT/SCHOOL_BREAK rows +9.4).
Rule 8 note: OLDER_SEASON is worth +3.23 on dev and cannot be measured on the back-test (nothing before the 2023 season). Kept as merged: same logic as TWO_YEARS_AGO, no tuned parameter. Without it: 61.45 / 60.79.
Decision: KEEP — rule 7 passes (sum 107.72 → 125.47, neither season drops).

## #2 hyp/owner-pattern merged (#5 owner's own pattern) — KEEP (automatic under the human's freeze rules, 2026-11-07)
Hypothesis: a business that was closed on every other major holiday it entered is closed on a major holiday it never entered; same-season sibling dates (INTERDAY) copy each other.
Change: new OWNER_PATTERN block between TWO_YEARS_AGO and PEERS (day_class MAJOR/SOFT/EVE_MAJOR, ≥2 other holidays all closed, peer closed_share_among_entered ≥ 0.3). Full log: `experiments/hyp-owner-pattern.md`. Merge commit a883455 (synced with main b05c573 first, no conflicts).
Dev 2026: 64.68 → 65.42   Back-test 2025: 60.79 → 61.69
Wrong-state: 339 → 353 (296 → 327)   Missed: 1,246 → 1,185 (1,622 → 1,523)   Precision 0.866 → 0.865 (0.884 → 0.879)   Recall 0.720 → 0.730 (0.664 → 0.678)
Checks on merged main: byte-identical on two runs, both seasons; snapshot audit PASS on both seasons, including all 58,158 entries of the owner-pattern index; no labels/ or entity IDs.
Caveat (fix #12): the peer gate uses the undated peer_benchmarks, so the back-test gain may be inflated; the dev gain is clean.
Decision: KEEP — rule 7 passes (sum 125.47 → 127.11, neither season drops).

## #3 hyp/peer-tuning merged (#3 + #4 peer rule) — KEEP under the freeze rule (2026-11-07)
Hypothesis: peers' closures only carry over on public holidays and major eves; a lower "closed among entered" threshold with the same "entered closed" floor; never for round-the-clock businesses. (#3, peer median special hours, was tested and reverted on the branch: 72–78 % of its messages were needless or wrong.) Full log: `experiments/hyp-peer-tuning.md`.
Change: peer block moved into `_peer_candidate()`: day_class in MAJOR/EVE_MAJOR/SOFT, closed_share_among_entered ≥ 0.5 (was 0.7), share_entered_closed ≥ 0.15, skip "00:00-23:59". Synced twice with main (conflicts resolved by keeping both sides in cascade order; verified line by line). Merge commit bef8bb5.
Dev 2026: 65.42 → 65.92   Back-test 2025: 61.69 → 62.73
Wrong-state: 353 → 383 (327 → 377)   Missed: 1,185 → 1,099 (1,523 → 1,369)   Precision 0.865 → 0.861 (0.879 → 0.873)   Recall 0.730 → 0.741 (0.678 → 0.698)
Freeze rule (human): keep if dev gains ≥ +0.5 and the back-test does not drop; the back-test gain itself is not used (fix #12). Unrounded dev gain: **+0.500185** (+27.0 points; the threshold is 26.99). It passes by less than one row.
Checks on merged main: byte-identical on two runs and identical to the synced branch's output, both seasons; snapshot audit PASS on both seasons; no labels/ or entity IDs.
Decision: KEEP — freeze rule passes (and rule 7: sum 127.11 → 128.65).

## Part A frozen (2026-11-07)
Final: **dev 2026 65.92 · back-test 2025 62.73** (baseline 54.49 · 53.23). No new hypotheses. Correctness fixes #10 and #11 (AGENTS.md section 5b) are not applied; #12 cannot be fixed (organisers' data).

## Reviews feasibility (analysis only, after part-a-freeze, 2026-11-07)
Question: can customer reviews recover the rows the frozen engine still misses? No model change. Scripts: `analysis/reviews_feasibility.py` (steps 1–4), `analysis/reviews_filters.py` (filters) and `analysis/reviews_split.py` (closed all day vs closed early). They score with `analysis/error_report.py`'s outcome rules against the final error-report rows; prerequisites are in each script's docstring.

1. **Filter.** Reviews with text and `publisherDate` before the season's snapshot that mention a holiday (fi/sv/nb/en aliases with Finnish inflections, longest alias first) or a closure / opening-hours word ("closed for good" excluded).
2. **Counts** (dev 2026 cutoff, back-test 2025 cutoff in brackets): 3,804 (2,356) reviews on 2,019 (1,544) businesses; 3,581 (2,210) name a holiday; 2,952 (1,818) have a closure word. Dev businesses with a missed row: 465 (557). Reviews on those businesses: 662 (458), on 329 (293) businesses.
3. **Match with missed rows.** Only 61 (49) reviews name the `day_key` of one of that business's missed rows, on 57 (44) businesses. 266 of the 662 (190 of 458) contain a time, but mostly the hours shown online ("Online it said open 09:00–17:00") or the time of the visit ("klo 18.20"). 1,388 reviews name a target holiday together with a time.
4. **Rule "suggest closed when a closure review names the day_key"** (dev labels):
   - All touched rows: 398 (226). Truth is closed on 64 % (65 %) and open on 36 % (35 %), so 36 % would be wrong state.
   - On rows where the engine is quiet today (the only place it could add points): 43 exact vs **76 wrong state → −0.61** (33 vs 46 → −0.23).
   - Filters tried on those rows:

     | Filter | Score |
     |---|---|
     | Posted 0–10 days after that holiday | Identical: every review is "timely" |
     | Timely and from last season | −0.22 (−0.16) |
     | Peer closed share ≥ 0.5 | −0.07 (−0.04) |
     | ≥ 2 reviews | +0.09 (+0.04), but only 5 (2) rows |
   - **Split by meaning** (the regex read "closed early" as "closed"):
     - "Closed all day" reviews: 66 (36) rows, truth closed on only 27 (16); 38 (19) were already right and open. The reviews are wrong, not misread.
     - "Closed early" reviews: suggesting `<shown opening>-<closing time in the review>` gives 7 exact of 16 (3 of 9) → +0.11 (+0.04).
5. **Conclusion: not worth an LLM for the score.** Better parsing only helps the small "closed early" group. On the rows the engine still misses, full-day closure reviews are wrong more often than right: the truthful ones sit on businesses whose history the engine already uses. Best case about +0.1–0.2 on roughly 20 dev rows (~55 test rows). Use reviews in Part B as **evidence quoted in the message** and for prioritisation, not as a predictor.

## #4 hyp/archetype-table (habit table learned from dev truth) — REVERTED: value too small for its complexity (human, 2026-11-07)
Hypothesis: `peer_benchmarks.csv` counts only owners who entered hours; the organisers' training data `labels/dev_truth_history.csv` shows what businesses of each type *actually* did, so a table learned from it should find closures that peers miss.
Change (branch only, never merged): `build/build_archetype_table.py` learns P(closed) per cell from truth dates before each season's snapshot (2026: < 2026-11-06; 2025: < 2025-11-06), with 5 fixed folds by business (dev businesses use the table from the other 4 folds; test and demo use the all-dev table), a 15-business minimum and back-off (segment×day_key×country → archetype×day_key×country → archetype×day_key → archetype×day_class), counting only days whose regular hours were open. `model.py` reads only `tables/archetype_table_<season>.json` (~1.9 MB in total). Basis `ARCHETYPE_TABLE`. Branch `hyp/archetype-table` at 334fb8b (kept locally for reference); full log in that branch's `experiments/hyp-archetype-table.md`.

Out-of-sample results (reference main: 65.92 / 62.73, wrong state 383 / 377, needless 161 / 87):

| Config | Threshold | Dev 2026 | Wrong | Needless | Back-test 2025 | Wrong | Needless | In-sample dev / bt |
|---|---|---|---|---|---|---|---|---|
| (a) new block after owner pattern, before peers | 0.80 | 65.95 | 384 | 161 | 62.82 | 378 | 87 | 65.97 / 62.86 |
| (a) | 0.85 | 65.97 | 383 | 161 | 62.84 | 377 | 87 | 65.97 / 62.84 |
| (a) | **0.90** | **65.95** | 383 | 161 | **62.82** | 377 | 87 | 65.95 / 62.82 |
| (a) | 0.95 | 65.92 | 383 | 161 | 62.77 | 377 | 87 | 65.92 / 62.79 |
| (b) table replaces the peer rule | 0.80 | 65.51 | 296 | 161 | 61.35 | 265 | 87 | 65.97 / 61.87 |
| (b) | 0.85 | 64.73 | 287 | 161 | 60.22 | 255 | 87 | 65.27 / 60.88 |
| (b) | 0.90 | 64.12 | 280 | 161 | 59.12 | 244 | 87 | 64.16 / 59.32 |
| (b) | 0.95 | 63.51 | 278 | 160 | 57.94 | 237 | 87 | 63.58 / 58.06 |

- (a) at 0.85 and at 0.90 pass the pre-set keep rule (out-of-sample score up in both seasons, wrong state not up). At 0.90 the gain is +0.03 / +0.09: only +2 / +5 exact rows, from 3 businesses that have no usable peer cell. Where the table is confident (P ≥ 0.80), the peer rule already suggests the same "closed" on 210 of 214 rows. The missed closures sit in cells at P(closed) 0.2–0.6, so a type-level habit cannot pick them out.
- **(b) replacing the peer rule removes 87–140 wrong-state rows per season (383 → 278–296, 377 → 237–265), but loses 0.41–4.79 points**, because it misses 150–500 more exact closures.
- Independent verification by the coordinator, all passed:
  - `model.py` run without any `labels/` directory gives byte-identical output.
  - Flipping all 22,565 truth rows dated ≥ 2025-11-06 leaves all six 2025 tables unchanged.
  - Flipping the truth of the 161 fold-0 businesses leaves only the `fold0` table unchanged, and `model.py` gives fold-0 businesses `fold0` and test businesses `all`.
  - Tables and CSVs are byte-identical on rebuild and rerun.

Decision: **REVERTED.** +0.03 / +0.09 is within noise and does not justify a learner script that reads labels plus 1.9 MB of tables. The keep rule is a minimum condition, not an obligation to merge.
Lesson: the peer rule is the main source of wrong-state suggestions (251 of the 760 wrong-state rows over both seasons, 23 % of its suggestions), but its exact closures are worth more than its errors cost. The product answer is delivery, not prediction: peer-only suggestions go to the owner as a question (ASK), with `explain_full()` confidence LOW, or MEDIUM when the peer cell is very sure (93 % exact, 7 % wrong state).

## Part A closed (2026-11-07)
Final: **dev 2026 65.92 · back-test 2025 62.73** (baseline 54.49 · 53.23), tag `part-a-final`. `predictions_2026.csv` is unchanged since `part-a-freeze`. No new branches or experiments.
