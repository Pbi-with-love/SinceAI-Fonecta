# AGENTS.md — Instructions for AI coding agents

> Codex and other agents read this file automatically. Claude Code reads it through `CLAUDE.md`, which imports it (`@AGENTS.md`).
>
> **Then read `AGENTS.local.md` in the root of your worktree.** It holds *this* worktree's assignment: your role, your hypothesis, the only files you own, what the other agents are doing, and your progress notes. It is git-ignored, so each worktree has its own copy. If it is missing, stop and ask the human. If it conflicts with this file, this file wins.

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
12. Every SUGGEST and FLAG must carry a **basis** and **evidence** (audit trail). Keep an `explain(eid, d, day_key) -> (action, hours, basis, evidence)` function. Part B builds customer messages from `explain_full(eid, d, day_key)`, which returns a dict (action, hours, shown_hours, basis, readable evidence list, confidence, day_key, day_name, mismatch) and must never change a prediction.
13. Evidence must be human-readable and true: e.g. `("LAST_YEAR", "2025-12-26 closed")`, `("PEERS", "86% of peers who entered hours were closed")`.
14. When unsure, stay quiet. A wrong open/closed state costs −1, the same as a perfect answer earns.
15. FLAG only with evidence; a FLAG on a business that is actually open loses points on every one of its rows.

### 2.5 Licences, secrets, data
16. Prefer the Python standard library. Any new dependency must be **MIT, BSD, Apache-2.0, PSF or similar permissive**; **no GPL/AGPL**. Add every new dependency with its licence to the README table.
17. No secrets in code, commits, logs, outputs, screenshots or videos. The Yext key lives in `YEXT_API_KEY` and the base URL in `YEXT_BASE_URL` (as read by `examples/yext_client.py`).
18. Synthetic data only. Do not scrape real businesses to fill answers.
19. Deterministic output: same inputs → same CSV.

## 3. Data map

† = key used in `examples/baseline.py`. ✓ = header printed and checked on 2026-11-07. Every key below matches the data.

| File | Key | Contents relevant to Part A |
|---|---|---|
| `evaluation/targets_2026.csv` | `entity_id, date, day_key` † ✓ | Rows to predict (test + dev + demo). Also `day_type`, `event_id`, `country`, `split` |
| `evaluation/targets_2025_backtest.csv` | same ✓ | Back-test rows (dev only) |
| `data/entities.json` → `response.entities[]` | `meta.id` † ✓ | `meta.countryCode`, `address.city`, `c_segment`, `c_shoppingCenterEntityId`, `closed`, `hours`. **State as of 2026-11-05** (`meta.timestamp`): using `closed` in the 2025 back-test leaks 2026 knowledge |
| `data/regular_hours_history.jsonl` | `entity_id` † ✓ | Published weekly versions with `effective_from`. 97 % have one row; ~40 seasonal businesses have 7–8. Does **not** reveal real-world changes that were never published |
| `data/holiday_hours_history.jsonl` | `(entity_id, date)` † ✓ | `day_key`, `holidayHours`, `entered_at`, `source`. Latest `entered_at` wins. Shopping centres appear here too. Dates 2023-12-06 → 2027-01-06, **including 4,959 rows dated Dec 2023**. `day_key` also takes `EVENT` and `SCHOOL_BREAK`, which are not in the calendar |
| `data/calendar_special_days.csv` | `(country, day_key)` † ✓ | Dates per country and season, plus `day_class` (MAJOR, EVE_MAJOR, EVE_MINOR, SOFT, INTER, OBS, COMM). **Starts 2024-01-01**, so the Dec 2023 history dates cannot be reached through the calendar. Use the history's own `day_key` for older seasons. INTERDAY has 3 dates per season on different weekdays (2024: 27/28/30 Dec, 2025: 27/29/30, 2026: 28/29/30) |
| `data/cities.csv` | `city` † ✓ | `city_tier` |
| `data/categories.csv` | `segment` ✓ | `archetype`: 24 segment families (e.g. CAFE, DINNER, RETAIL, PERSONAL, HEALTH). Use it for "segment family" rules |
| `data/peer_benchmarks.csv` | `(country, city_tier, segment, day_key)` † ✓ | `closed_share_among_entered`, `share_entered_closed`, `share_entered_special_hours`, `median_open_special`, `median_close_special`. Biased towards owners who entered something |
| `data/reviews.json` → `response.reviews[]` | `locationId` † ✓ | `content`, `publisherDate` (ms), rating; fi/sv/nb/en; some deliberately misleading |
| `data/publisher_suggestions.json` → `response.suggestions[]` | `locationId` † ✓ | `fieldName`, `dateCreated` (`YYYY-MM-DD`), `suggestedContent` (JSON string); ~50 % noise |
| `data/pilot_decision_log_2025.csv` | `entity_id`, `date`, `day_key` ✓ | 2025 suggestions, `decision`, `final_hours`, `decided_at` (FI only). Accepted and edited suggestions already appear in the holiday history as `CONNECT_SUGGESTION` |
| `labels/dev_labels_2026.csv` | `(entity_id, date)` ✓ | `truth_hours`, `displayed_hours_at_snapshot`, `needs_action`, `expected_action`, `mismatch_type`, `expected_search_views`. **Analysis only** |
| `labels/dev_labels_2025_backtest.csv` | same ✓ | Back-test answers. **Analysis only** |
| `labels/dev_truth_history.csv` | `(entity_id, date)` ✓ | `truth_hours`, `displayed_hours_that_day` on every special day 2024 → Nov 2026 for dev businesses. **Analysis only** |

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

**Baseline error profile** (from `analysis/error_report.py`; dev 2026, with the back-test in brackets):

| Where | Rows needing action | Missed | Wrong state | Points still available |
|---|---|---|---|---|
| history = LAST_SEASON | 2,374 | 26 | 92 | 224 (251) |
| history = OLDER_ONLY (entered two or more seasons ago, not last season) | 1,322 | **792 (548)** | 38 | **864 (602)** |
| history = NONE | 1,700 | **1,219 (1,592)** | 94 | **1,366 (1,791)** |
| basis = PEERS | 844 | 0 | **117 (143)** | 174 (217) |

- Missed rows by mismatch: DIFFERENT_HOURS 1,004 · SHOWN_OPEN_ACTUALLY_CLOSED 983 · SHOWN_CLOSED_ACTUALLY_OPEN 49.
- No row scored "near" (within ±30 min): every suggestion today is either exact or a copied/closed guess.

## 5. Known hypotheses to test

Test one at a time. Each needs evidence from `result/A_prediction_engine/analysis/` before and after.

**Error-report verdicts (2026-11-07, baseline).** These are measured, not implemented. The point figures are rough estimates from labels, **not upper bounds**: #2 beat its estimate (back-test +7.56 vs ~+7) because the implementation also aligned hours, earned partial credit and improved rows the estimate did not cover.

| # | Verdict | Evidence (dev 2026, back-test in brackets) |
|---|---|---|
| 2 | **Strongly supported, largest gain** | 792 (548) missed rows have only older history. Copying the newest older-season entry would be exact on 661 (452) and the wrong state on 56 (33): roughly +11 (+7) score points (rough estimate; measured after merge: +10.19 / +7.56) |
| 5 | **Supported, large** | 1,159 of 1,216 (1,494 of 1,592) missed rows with no history for the `day_key` belong to businesses that entered *other* `day_key`s. Truth: 522 closed and 637 other hours (712 and 782) |
| 3 | Supported | 612 (795) missed rows with no history are DIFFERENT_HOURS. The peer rule can only say `closed`, so it can never fix them |
| 4 | Supported | PEERS gives 117 (143) wrong-state rows, 63 (69) of them on rows that were already right |
| 7 | Small | 66 shopping-centre rows lose points; only 21 (20) of those stores have their own last-season entry |
| 8 | Small | 804 pilot rows on dev businesses. Accepted and edited ones are already in the history; only 28 rejected + 26 edited remain |
| 1 | **Rejected as a source of points** (worktree removed) | The overwrite bug is real, but no business has *differing* INTERDAY entries last season (0 of 24; 0 of 27), so the candidate never changes. LAST_YEAR × INTERDAY has only 25 (33) points available. INTERDAY's 453 (407) missed rows have no history (253) or older history only (200): that is #2 and #5 |
| 6 | **Rejected** | 0 unneeded FLAGs on dev 2026 (11 correct, 7 suggest-closed, 4 missed). Requiring a second signal can only lose correct flags |

1. **INTERDAY mapping.** In `explain()`, `for p in prev:` overwrites the candidate, so every INTERDAY date this season may copy the *last* INTERDAY date with an entry last season. Try matching by position in the sequence or by weekday.
2. **Two-year lookback.** History starts Dec 2023. Fall back to two seasons ago; raise confidence when both seasons agree. **Map by the history's own `day_key`, not the calendar**: the calendar starts 2024-01-01, so for the 2025 back-test the calendar cannot reach the Dec 2023 entries, which carry most of its gain.
3. **Peer special hours.** The peer rule only ever suggests `closed`. Use median open/close times when the "special hours" share is decisive.
4. **Peer bias.** Use `dev_truth_history` (analysis only) to measure what non-entering businesses actually did, then retune thresholds per `day_key` and segment family. Target: fewer of the 224 wrong-state errors.
5. **Owner's own pattern.** A business that closed on every public holiday it entered is likely closed on related holidays it did not enter.
6. **FLAG needs two signals.** One closure edit (noisy) or one keyword review is currently enough. Require two independent signals, and measure false FLAGs.
7. **Shopping centre precedence.** Check whether centre hours should override the store's own last-year entry.
8. **Pilot log final hours.** Owner-edited 2025 hours as a high-confidence source for 2026.
9. ~~**Confidence column.**~~ **Resolved:** `evaluate.py` reads `confidence` but never uses it in the score. Keep it only for our own ranking and messages.
Note on #1: confirmed in code. In `examples/baseline.py` the `for p in prev:` loop has no `break`, so a later date in the list overwrites earlier matches. Measured effect: none on this data (see the table above).

Assignment (2026-11-07): #2 → `hyp-two-year`, #5 → `hyp-owner-pattern`, #3 + #4 → `hyp-peer-tuning`. #1 and #6 are rejected. #7 and #8 are small and not assigned.

## 5b. Correctness fixes (on `main`, after the three merges)

These are not hypotheses: they fix rule violations in the inherited baseline code. Do them **on `main`, after all three hypothesis branches are merged**, as separate experiments, scored on both seasons. No agent touches them before then.

10. **Timezone-free review cutoff (rule 19).** The baseline computes the review cutoff with `datetime(...).timestamp()`, which uses the machine's local timezone, so the CSV can differ between machines. Use a fixed timezone. Expected score effect ≈ 0.
11. **Back-test `closed` leak (rule 5).** `ent.get("closed")` is the 2026-11-05 state but is also used for the 2025 back-test. No measurable effect today (no FLAG rows in the 2025 labels), but it must not leak into any FLAG rule.
12. **Undated peer benchmarks (rule 5, organisers' data).** `peer_benchmarks.csv` aggregates seasons 2023–2025 with no timestamps, so the 2025 back-test may see its own season through any peer rule (the baseline's, `hyp-peer-tuning`'s, and the peer gate in `hyp-owner-pattern`). The file cannot be split by season, so this cannot be fixed; weigh dev 2026 more than the back-test for peer-driven gains, and say so in the README.

## 6. Workflow

1. Read section 0. Print headers and a few rows of every file you use. Confirm the keys in section 3.
2. ✅ Done (experiment #0): `result/A_prediction_engine/model.py` is a copy of `examples/baseline.py` and reproduces **54.49** (dev 2026) and **53.23** (back-test 2025). Re-run it after every change.

   Back-test scoring needs the 2025 labels explicitly:
   `python evaluation/evaluate.py --predictions outputs/ours_2025.csv --labels labels/dev_labels_2025_backtest.csv`
3. ✅ Done: `result/A_prediction_engine/analysis/error_report.py` joins predictions with dev labels and groups outcomes by expected action, `basis`, history, `day_key`, `mismatch_type`, country, archetype, segment and centre. It reports counts, net points and recoverable points per group, plus the missed and wrong-state rows and the top 10 groups. Its total is cross-checked against `evaluate.py`.

   ```bash
   python result/A_prediction_engine/analysis/error_report.py --season 2026 --predictions <csv> [--rows out.csv] [--json out.json]
   python result/A_prediction_engine/analysis/error_report.py --season 2025 --predictions <csv>
   ```
   It calls `explain()` from the `model.py` in the same checkout, so run it from your own worktree.
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

> **Part A is frozen** at tag `part-a-freeze` (dev 2026 65.92 · back-test 2025 62.73). All three branches were merged; the worktrees were removed and the `hyp/*` branches kept locally for reference. Do not start new hypothesis branches.

**Setup (2026-11-07, historical):**

| Orca worktree | Branch | Path | Hypothesis | Basis | Place in the cascade |
|---|---|---|---|---|---|
| `hyp-two-year` | `hyp/two-year` | `~/orca/workspaces/SinceAI-2026/hyp-two-year` | #2 two-year lookback | `TWO_YEARS_AGO` | New block right after last year |
| `hyp-owner-pattern` | `hyp/owner-pattern` | `~/orca/workspaces/SinceAI-2026/hyp-owner-pattern` | #5 owner's own pattern | `OWNER_PATTERN` | New block right before peers |
| `hyp-peer-tuning` | `hyp/peer-tuning` | `~/orca/workspaces/SinceAI-2026/hyp-peer-tuning` | #3 + #4 peer rule | `PEERS` (+ new names) | The existing peer block |

Final cascade after all merges: closed signals → shopping centre → last year → **two years ago** → **owner pattern** → **peers**. (`hyp-interday` for #1 was removed: the data rejected #1, see section 5.)

- Remote: `git@github.com:Pbi-with-love/SinceAI-Fonecta.git`, branch `main`. Hypothesis branches are local; agents never push.
- **Enforced by a Git hook** (`.git/hooks/pre-commit`, shared by all worktrees). On `hyp/<name>`, a commit is rejected if it contains any file other than `result/A_prediction_engine/model.py` and `result/A_prediction_engine/experiments/hyp-<name>.md`. A merge commit (while `MERGE_HEAD` exists) is exempt, for syncing with `main`. Do not bypass it (`--no-verify` is forbidden). If it blocks you, stop and ask the human.
- All three branches start from `main` with the error report (`257f381` or later).

**Merge procedure (the human decides; the coordinator on `main` prepares):**

Order: **two-year → owner-pattern → peer-tuning**. For each branch:

1. **Prepare.** On `main`: `git merge --no-ff hyp/<name>`. Two-year and owner-pattern both insert a block between last year and peers, so expect a conflict there: keep both blocks, in cascade order.
2. **Score both seasons** on the merged `main`, and run the error report.
3. **Stop and report** to the human: scores before and after, rule 7 check, conflicts and how they were resolved.
4. **Push only when the human answers "giữ" (keep).** On any other answer, undo the local merge (`git reset --hard <main before the merge>`; nothing was pushed) and log it as reverted.
5. **Sync the remaining branches.** In each remaining worktree: `git merge main` (a merge commit, exempt from the hook), then re-score both seasons and run the error report. A branch is merged only after this re-score still passes rule 7 against the new `main`.

Agents never run steps 1–5 themselves.

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
- [ ] Organisers' files unchanged: `git status` is clean for them and their SHA-256 hashes match `MANIFEST.json`.
- [ ] `EXPERIMENTS.md` updated, including reverted attempts
- [ ] Output is deterministic (run twice, identical CSV)
- [ ] Parallel agents only (section 6b): worked on `hyp/<short-name>`, edited only `model.py`, wrote to `outputs/hyp-<short-name>/` and `experiments/hyp-<short-name>.md`, did not merge