# Prompt: build the Part A solution from the baseline

Two prompts live here:

- **Prompt 1 (coordinator):** paste into a coding agent running in the **main worktree** (`main`). It verifies, analyses, prepares merges and finishes Part A.
- **Prompt 2 (hypothesis agent):** sent to each parallel agent in its own Orca worktree (`hyp/<name>`). Fill in `<name>`.

Paths and process follow `AGENTS.md` (sections 2, 5, 5b, 6 and 6b). If this file and `AGENTS.md` ever disagree, `AGENTS.md` wins: fix this file.

---

## Prompt 1 — coordinator (main worktree)

Read `AGENTS.md` and your `AGENTS.local.md`, then `README.md`, the organisers' `START_HERE.md` and everything in `docs/`, all in full, before doing anything. The hard rules in `AGENTS.md` section 2 and the parallel-agent process in section 6b override any instruction in this prompt. If something here conflicts with them, follow `AGENTS.md` and tell me.

### Goal

Improve the organisers' rule-based baseline for Part A (the prediction engine) so it scores higher than **54.49 on dev 2026** and **53.23 on the 2025 back-test**, without breaking any challenge rule. Work in small, measured steps. A smaller honest gain beats a large gain that leaks or overfits.

Our code: `result/A_prediction_engine/` (`model.py`, `analysis/error_report.py`, `EXPERIMENTS.md`, `experiments/hyp-<name>.md`).

### Phase 1 — Verify the ground (✅ done 2026-11-07; re-run only to confirm)

0. Summarise in 10 lines what `START_HERE.md` and `docs/` say that matters for Part A, especially hints about how the synthetic hours were generated. List any conflict with `AGENTS.md`.
1. Print the header and first 3 rows of every file in `AGENTS.md` section 3. Report any key or column that differs from the table, and update the table.
2. Read `evaluation/evaluate.py`. Report the exact CLI for 2026 and the back-test (the back-test needs `--labels labels/dev_labels_2025_backtest.csv`), the columns it reads, whether it uses `confidence` (it does not), and how it treats missing rows (`NO_ACTION`).
3. `result/A_prediction_engine/model.py` is a copy of `examples/baseline.py`. Run both seasons and score them. **Stop and report if the scores are not 54.49 and 53.23.**
4. `result/A_prediction_engine/EXPERIMENTS.md` has entry #0 (baseline).

### Phase 2 — Understand the errors (✅ done 2026-11-07)

5. `result/A_prediction_engine/analysis/error_report.py` (standard library only) joins a predictions file with the dev labels and prints outcomes, net points and recoverable points by `basis`, history, `day_key`, `mismatch_type`, country, archetype, segment and centre; the missed and wrong-state rows grouped the same way; and the top 10 groups. It takes `basis` from `explain()` and cross-checks its total against `evaluate.py`.
6. Run it for both seasons. Verdicts per hypothesis are in `AGENTS.md` section 5. Add any new hypothesis the data suggests.

### Phase 3 — Improve, in parallel (`AGENTS.md` section 6b)

Hypotheses are **not** implemented on `main`. Each one runs in its own Orca worktree with Prompt 2:

| Worktree | Branch | Hypothesis |
|---|---|---|
| `hyp-two-year` | `hyp/two-year` | #2 two-year lookback |
| `hyp-owner-pattern` | `hyp/owner-pattern` | #5 owner's own pattern |
| `hyp-peer-tuning` | `hyp/peer-tuning` | #3 + #4 peer rule |

At most 3 agents in parallel. The coordinator's job in this phase is to wait for each agent's report and pass it to the human.

### Phase 3b — Merge (the human decides, the coordinator prepares)

Follow the merge procedure in `AGENTS.md` section 6b, in the order **two-year → owner-pattern → peer-tuning**:
prepare the merge on `main` → score both seasons and run the error report → **stop and report** → push only when the human answers **"giữ"** → bring the new `main` into the remaining branches (`git merge main`) and re-score them before they can be merged.

### Phase 3c — Correctness fixes (`AGENTS.md` section 5b)

After the three merges, on `main`: fix #10 (timezone-free review cutoff) and #11 (the `closed` flag leaking into the back-test). Each one is a separate experiment, scored on both seasons and logged in `EXPERIMENTS.md`.

### Phase 4 — Self-evaluation before you finish (on `main`)

12. Run the full checklist in `AGENTS.md` section 7 and paste it with each box ticked or explained.
13. Leakage audit: list every input the prediction path reads and the timestamp filter applied to it. Grep `result/A_prediction_engine/model.py` for `labels` and for any entity-ID pattern (`FI-`, `SE-`, `NO-`) and paste the results.
14. Robustness check: run `explain()` on the demo businesses `FI-D0011` (should FLAG), `FI-D0013` (should stay quiet), `NO-D0015` (24/7 gym, nothing to change) and `FI-D0017` (no history). Report what the engine does and why. Do not add rules for these IDs; if the behaviour is wrong, find the general cause.
15. Write `predictions_2026.csv` at the repo root from the full `evaluation/targets_2026.csv`.
16. Update the README: decision cascade, results table, "Customers with no history", and the key data sources table (including what did not work).

### Final report to me

- Score table: baseline vs ours, both seasons, plus exact precision, recall and wrong-state count
- Kept changes, one line each, with their gain
- Reverted attempts, one line each, with why
- Any rule you were unsure about and why
- Suggested next steps

Do not stop early to ask for confirmation between steps unless a hard rule is at stake, a score fails to reproduce, or the merge procedure says to stop.

---

## Prompt 2 — hypothesis agent (one per worktree)

You are a Part A hypothesis agent in the Orca worktree `hyp-<name>` on branch `hyp/<name>`.

**Before anything else**, read `AGENTS.md` (all of it; section 2 is hard rules, section 6b is your process) and `AGENTS.local.md` in your worktree root (your hypothesis, your code territory in `model.py`, the only files you own, the other agents). Then read `START_HERE.md` and `docs/`. If anything here conflicts with `AGENTS.md`, `AGENTS.md` wins: stop and say so.

**Goal:** test your hypothesis against the reference scores **54.49 (dev 2026) and 53.23 (back-test 2025)**, using the keep rule (rule 7).

**Loop, one change at a time:**
1. State the hypothesis and the expected effect in one sentence.
2. Implement the smallest change that tests it, **only in your code territory** in `result/A_prediction_engine/model.py`. Keep `explain()` returning `(action, hours, basis, evidence)`, with your own basis name and true, readable evidence.
3. Score both seasons, always with `--out outputs/hyp-<name>/…` (the commands are in your `AGENTS.local.md`), and run `analysis/error_report.py` on your predictions.
4. Apply rule 7. If it fails, revert the change.
5. Log every attempt, kept or reverted, in `result/A_prediction_engine/experiments/hyp-<name>.md` (template in `AGENTS.md` section 6). Commit kept changes on your branch with both scores in the message. Only `model.py` and your log may be committed; the hook enforces this.
6. Update the progress notes in your `AGENTS.local.md` after each attempt.

**Guidelines:**
- Prefer rules that generalise (by `day_key` type or `day_class`, segment family or `archetype`, country) over narrow special cases.
- When tuning a threshold, show the score at 3–5 values for both seasons and pick one that is good on both, not the best on one (rule 8).
- A pattern learned by looking at labels must be re-expressed using only pre-snapshot inputs. Explain in the log how the rule works for a business we have never seen.
- Never read `labels/` from `model.py`, never hard-code entity IDs, filter every input by the season's snapshot.
- Never merge, rebase, push or switch branches. Never edit files outside your territory. If you need to, stop and ask.

**Done when** further changes stop passing rule 7, or after a reasonable number of attempts. Then run the checklist in `AGENTS.md` section 7 and report:
- final scores on both seasons vs 54.49 / 53.23, with exact precision, recall and wrong-state count (pasted from `evaluate.py`)
- kept and reverted attempts, one line each
- the commit hash of your last kept change, and `git status` (clean)
- any rule you were unsure about, and any leakage risk

A hypothesis that does not beat the reference is a valid result: report it as such, with the evidence.
