# AGENTS.md — Instructions for AI coding agents

> Codex and other agents read this file automatically. Claude Code reads it through `CLAUDE.md`, which imports it (`@AGENTS.md`).

You are working on our team's entry for the Fonecta challenge "Connect Suggests – Customer Approves" (Since AI Hackathon 2026). Read this whole file before writing any code. The rules in section 2 are **hard rules**: if a task seems to require breaking one, stop and ask the human instead.

## 0. Read first

Before any code, read these organisers' documents in full:

1. `START_HERE.md` (dataset root): scenario, file overview, mock API, scoring, submission rules.
2. Everything in `docs/`: data dictionary, `DEMO_SCENARIOS.md`, assumptions, `LIVE_SOURCES.md`, `README_TEMPLATE.md`.
3. `examples/baseline.py`, `examples/quickstart.py`, `examples/yext_client.py`, `evaluation/evaluate.py`.

If the organisers' documents disagree with this file about data, columns or scoring, **the organisers' documents win**: follow them and update this file. The assumptions document may describe how the synthetic data was generated; patterns stated there are fair game for rules, as long as rules use only allowed inputs (section 2).

## 1. Context

Fonecta Connect publishes local businesses' information (opening hours, photos, reviews) to 35+ channels through Yext. Owners forget to enter holiday hours, so channels show "open" when the door is locked. Our system predicts, for every (business, special date), whether the shown hours will be wrong and what the right hours are.

**Current scope: Part A, the prediction engine only.** Do not build messaging, n8n workflows, UIs or Yext writes unless the human asks.

For each row in `evaluation/targets_2026.csv` (columns include `entity_id`, `date`, `day_key`) the engine outputs one of:

| Action | Meaning |
|---|---|
| `SUGGEST` + hours | Shown hours will be wrong; propose the right ones |
| `NO_ACTION` | Shown hours are already right; stay quiet (rows not written = NO_ACTION) |
| `FLAG` | Needs a human, e.g. closed for good |

Output CSV: `entity_id,date,action,hours[,confidence]` (confidence optional), one row per action for rows of `targets_2026.csv`. The final `predictions_2026.csv` keeps dev rows as well as test rows. `hours` is `closed` or `HH:MM-HH:MM` intervals joined by commas (same as `day_str()` in the baseline).

Scenario clock: snapshot **2026-11-06** for the 2026 season and **2025-11-06** for the back-test. Seasons start in February (`cycle()` in the baseline).

## 2. Hard rules

### 2.1 No leakage
1. At prediction time, use **only data timestamped strictly before the snapshot** of the season being predicted:
   - `holiday_hours_history`: `entered_at < snapshot`
   - `regular_hours_history`: `effective_from == "before-2024"` or `< snapshot`
   - `reviews`: `publisherDate < snapshot` (milliseconds since epoch)
   - `publisher_suggestions`: `dateCreated < snapshot`
   - `analytics_daily`, `pilot_decision_log_2025`, events, weather: only rows dated before the snapshot
2. **Never read anything under `labels/` inside the prediction code path.** Labels are for `evaluation/` and `result/A_prediction_engine/analysis/` only. This includes `dev_truth_history.csv` and `dev_regular_hours_truth.csv`.
3. You may *study* labels in `result/A_prediction_engine/analysis/` to discover general patterns, then encode those patterns as rules that use only allowed inputs. Never copy an answer from labels into a prediction.
4. **No per-entity hard-coding.** No `if entity_id == ...`, no lookup tables keyed by entity ID, no special cases for demo IDs (`*-D00xx`). Every rule must apply to any business.
5. The 2025 back-test must use the 2025 snapshot consistently. A rule that only works because it sees 2026 data when predicting 2025 is leakage.

### 2.2 Honest evaluation
6. Every change is scored on **both** dev 2026 and back-test 2025 with `evaluation/evaluate.py`.
7. Keep a change only if it **improves the sum of the two scores and does not drop either score by more than 0.3 points**. Otherwise revert it and log it as "did not work".
8. Thresholds and parameters tuned on dev must be justified by the back-test. If a parameter only helps one season, prefer the simpler or more conservative value.
9. If you add ML: train on dev only, split folds **by entity** (never by row), keep every feature pre-snapshot, fix random seeds, and report the score with and without the model.
10. Never claim a score you did not just measure. Paste the evaluator's output into `result/A_prediction_engine/EXPERIMENTS.md`.

### 2.3 Do not touch the organisers' files
11. Read-only: `START_HERE.md`, `data/`, `evaluation/`, `labels/`, `examples/`, `mock_api/`, `docs/`. Our code lives in `result/` (one folder per part: `A_prediction_engine`, `B_contact_decide`, `C_apply_yext`, `D_learning_permission`, `E_demo_submission`).

### 2.4 Product rules (affect later parts, respect them now)
12. Every SUGGEST and FLAG must carry a **basis** and **evidence** (audit trail). Keep an `explain(eid, d, day_key) -> (action, hours, basis, evidence)` function; Part B builds customer messages from it.
13. Evidence must be human-readable and true: e.g. `("LAST_YEAR", "2025-12-26 closed")`, `("PEERS", "86% of peers who entered hours were closed")`.
14. When unsure, stay quiet. A wrong open/closed state costs −1, the same as a perfect answer earns.
15. FLAG only with evidence; a FLAG on a business that is actually open loses points on every one of its rows.

### 2.5 Licences, secrets, data
16. Prefer the Python standard library. Any new dependency must be **MIT, BSD, Apache-2.0, PSF or similar permissive**; **no GPL/AGPL**. Add every new dependency with its licence to the README table.
17. No secrets in code, commits, logs, outputs, screenshots or videos. The Yext key lives in `YEXT_API_KEY` and the base URL in `YEXT_BASE_URL` (as read by `examples/yext_client.py`).
18. Synthetic data only. Do not scrape real businesses to fill answers.
19. Deterministic output: same inputs → same CSV.

## 3. Data map

Keys marked † are confirmed in `examples/baseline.py`. Verify the rest against the data dictionary in `docs/` and by printing file headers before relying on them.

| File | Key | Contents relevant to Part A |
|---|---|---|
| `evaluation/targets_2026.csv` | `entity_id, date, day_key` † | Rows to predict (test + dev + demo) |
| `evaluation/targets_2025_backtest.csv` | same | Back-test rows (dev only) |
| `data/entities.json` → `response.entities[]` | `meta.id` † | `meta.countryCode`, `address.city`, `c_segment`, `c_shoppingCenterEntityId`, `closed`, `hours` |
| `data/regular_hours_history.jsonl` | `entity_id` † | Published weekly versions with `effective_from`. 97 % have one row; ~40 seasonal businesses have 7–8. Does **not** reveal real-world changes that were never published |
| `data/holiday_hours_history.jsonl` | `(entity_id, date)` † | `day_key`, `holidayHours`, `entered_at`, `source`. Latest `entered_at` wins. Shopping centres appear here too |
| `data/calendar_special_days.csv` | `(country, day_key)` † | Dates per country and season; maps last season's date to this season's |
| `data/cities.csv` | `city` † | `city_tier` |
| `data/peer_benchmarks.csv` | `(country, city_tier, segment, day_key)` † | `closed_share_among_entered`, `share_entered_closed`, median special open/close times. Biased towards owners who entered something |
| `data/reviews.json` → `response.reviews[]` | `locationId` † | `content`, `publisherDate` (ms), rating; fi/sv/nb/en; some deliberately misleading |
| `data/publisher_suggestions.json` → `response.suggestions[]` | `locationId` † | `fieldName`, `dateCreated`; ~50 % noise |
| `data/pilot_decision_log_2025.csv` | business id | 2025 suggestions, decisions, owner-edited final hours (FI only) |
| `labels/dev_labels_2026.csv` | `(entity_id, date)` | `truth_hours`, `displayed_hours_at_snapshot`, `expected_action`, `mismatch_type`, `expected_search_views`. **Analysis only** |
| `labels/dev_labels_2025_backtest.csv` | same | Back-test answers. **Analysis only** |
| `labels/dev_truth_history.csv` | `(entity_id, date)` | True hours on every special day for dev businesses. **Analysis only** |

Derived concept used everywhere:

```
shown(eid, d) = latest holiday entry for (eid, d) entered before snapshot,
                unless missing or isRegularHours → published regular hours for weekday(d)
```

## 4. Problem shape (dev 2026)

- 11,100 rows: 5,376 need SUGGEST, 22 need FLAG, 5,702 are NO_ACTION.
- Among SUGGEST: shown open / actually closed 3,391 (63 %), different hours 1,925, shown closed / actually open 60.
- INTERDAY (days between Christmas and New Year) is 9,051 of 41,755 target rows.
- About 40 % of needed changes have no history for that `day_key`.
- Baseline: 54.49 dev / 53.23 back-test; exact precision 0.901, recall 0.59; 2,034 missed rows (0 points); 224 wrong-state guesses (−224 points), mostly the peer rule guessing closed for businesses that were open.

## 5. Known hypotheses to test (not yet verified)

Test one at a time. Each needs evidence from `result/A_prediction_engine/analysis/` before and after.

1. **INTERDAY mapping.** In `explain()`, `for p in prev:` overwrites the candidate, so every INTERDAY date this season may copy the *last* INTERDAY date with an entry last season. Try matching by position in the sequence or by weekday.
2. **Two-year lookback.** History starts Dec 2023. Fall back to two seasons ago; raise confidence when both seasons agree.
3. **Peer special hours.** The peer rule only ever suggests `closed`. Use median open/close times when the "special hours" share is decisive.
4. **Peer bias.** Use `dev_truth_history` (analysis only) to measure what non-entering businesses actually did, then retune thresholds per `day_key` and segment family. Target: fewer of the 224 wrong-state errors.
5. **Owner's own pattern.** A business that closed on every public holiday it entered is likely closed on related holidays it did not enter.
6. **FLAG needs two signals.** One closure edit (noisy) or one keyword review is currently enough. Require two independent signals, and measure false FLAGs.
7. **Shopping centre precedence.** Check whether centre hours should override the store's own last-year entry.
8. **Pilot log final hours.** Owner-edited 2025 hours as a high-confidence source for 2026.
9. ~~**Confidence column.**~~ **Resolved:** `evaluate.py` reads `confidence` but never uses it in the score. Keep it only for our own ranking and messages.

Note on #1: confirmed in code. In `examples/baseline.py` the `for p in prev:` loop has no `break`, so a later date in the list overwrites earlier matches. The effect on the score is not measured yet.

## 6. Workflow

1. Read section 0. Print headers and a few rows of every file you use. Confirm the keys in section 3.
2. ✅ Done (experiment #0): `result/A_prediction_engine/model.py` is a copy of `examples/baseline.py` and reproduces **54.49** (dev 2026) and **53.23** (back-test 2025). Re-run it after every change.

   Back-test scoring needs the 2025 labels explicitly:
   `python evaluation/evaluate.py --predictions outputs/ours_2025.csv --labels labels/dev_labels_2025_backtest.csv`
3. Build `result/A_prediction_engine/analysis/error_report.py`: join predictions with dev labels and group outcomes by `basis`, `day_key`, segment, country, has-history, `mismatch_type`. Report counts and net points per group.
4. Pick the group with the largest recoverable points. Form a hypothesis, implement it, score both seasons, run the error report again.
5. Log every attempt in `result/A_prediction_engine/EXPERIMENTS.md` (template below), kept or not. If the project uses Git, commit kept changes with the scores in the message.
6. When finished, write `predictions_2026.csv` at the repo root from the full `targets_2026.csv`.

`EXPERIMENTS.md` entry template:

```
## #N <short name>
Hypothesis: ...
Change: ...
Dev 2026: before → after   Back-test 2025: before → after
Wrong-state: before → after   Missed: before → after
Decision: KEEP / REVERT — reason
```

## 6b. Parallel agents (Part A only)

Team plan:

| Phase | How |
|---|---|
| Verify + error analysis (section 6, steps 2–3) | 1 agent, sequential |
| Hypothesis testing (section 5) | 2–3 agents in parallel: one branch and one hypothesis each |
| Merge | The human, one branch at a time, re-scoring after each merge |
| LLM review | 1 script, run offline once, results cached |

This section applies only to Part A hypothesis testing. Section 6 steps 2–3 (reproduce the baseline, build `result/A_prediction_engine/analysis/error_report.py`) are done by **one agent, sequentially**, before any parallel work starts.

**Prerequisite:** parallel work needs Git. The project has no Git yet. The human sets it up and commits the reproduced baseline and the error report to `main` before the first parallel agent starts.

1. One agent = one hypothesis from section 5, on its own Git branch `hyp/<short-name>` (or a Git worktree, e.g. an Orca worktree). Never work on `main`.
2. Branch from the latest `main` that already has the reproduced baseline and the error report.
3. Only edit `result/A_prediction_engine/model.py`. Do not edit `result/A_prediction_engine/analysis/`, `result/A_prediction_engine/EXPERIMENTS.md`, `evaluation/`, `README.md`, `AGENTS.md`, `CLAUDE.md` or any shared script. If the error report needs a change, stop and ask the human.
4. Write outputs to `outputs/hyp-<short-name>/` so agents never overwrite each other's files. `model.py` writes to `outputs/ours_<season>.csv` by default, so always pass `--out`, e.g. `--out outputs/hyp-<short-name>/ours_2026.csv`.
5. Log results in `result/A_prediction_engine/experiments/hyp-<short-name>.md` using the template in section 6, not in `EXPERIMENTS.md`. The human merges these logs into `EXPERIMENTS.md`.
6. Compare against the scores of the `main` you branched from, on both seasons, using the keep rule (rule 7).
7. Do not merge. The human merges winning branches **one at a time**, re-scores both seasons after each merge, and keeps a merge only if it still passes rule 7 (two changes that each help alone may not add up).
8. Run at most 3 agents in parallel.

**LLM review** (e.g. classifying multilingual reviews): one offline script run once, with results cached to a file that `model.py` reads. `model.py` itself never calls an LLM, so its output stays deterministic (rule 19). The script follows the no-leakage rules in section 2.1: it only reads inputs dated before each season's snapshot, and it never reads `labels/`.

## 7. Self-review checklist (run before saying "done")

- [ ] `START_HERE.md` and `docs/` read; any conflict with this file resolved in their favour
- [ ] Both seasons scored in this session; numbers pasted from the evaluator output
- [ ] No file under `labels/` is opened by `result/A_prediction_engine/model.py`
- [ ] Every input is filtered by the snapshot of the season being predicted
- [ ] No entity IDs or demo IDs appear in rules
- [ ] `explain()` still returns `(action, hours, basis, evidence)` with true, readable evidence
- [ ] No new dependency without a permissive licence listed in the README
- [ ] No secrets anywhere
- [ ] Organisers' files unchanged. The project has no Git yet, so check the SHA-256 hashes in `MANIFEST.json` (or `git status` once Git is set up).
- [ ] `EXPERIMENTS.md` updated, including reverted attempts
- [ ] Output is deterministic (run twice, identical CSV)
- [ ] Parallel agents only (section 6b): worked on `hyp/<short-name>`, edited only `model.py`, wrote to `outputs/hyp-<short-name>/` and `experiments/hyp-<short-name>.md`, did not merge