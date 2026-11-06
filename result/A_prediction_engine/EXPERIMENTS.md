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
