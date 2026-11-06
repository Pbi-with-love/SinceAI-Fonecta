#!/usr/bin/env python3
"""Part A error report: where do our predictions win and lose points? Standard library only.

ANALYSIS ONLY. This script reads labels/ and must never be imported by model.py (AGENTS.md rule 2).

    python result/A_prediction_engine/analysis/error_report.py                   # dev 2026, outputs/ours_2026.csv
    python result/A_prediction_engine/analysis/error_report.py --season 2025     # back-test, outputs/ours_2025.csv
    python result/A_prediction_engine/analysis/error_report.py --predictions outputs/hyp-x/ours_2026.csv \
        --json outputs/hyp-x/report_2026.json --rows outputs/hyp-x/rows_2026.csv

For every dev label row it computes:
  outcome, points   exactly as evaluation/evaluate.py scores the row (the total is cross-checked against evaluate.py)
  recoverable       best possible points minus points earned (best = 1 if the row needs a change or a flag, else 0)
  basis             what model.explain() says produced the action; "<BASIS>=SHOWN" means a candidate existed but
                    matched what is shown, so the engine stayed quiet
  history           what the business itself entered before the snapshot for this day_key:
                    ENTERED_FOR_DATE (this exact date) > LAST_SEASON > OLDER_ONLY > NONE
Action and hours come from the predictions CSV; explain() is called only for the basis, and any disagreement between
the two is reported (it means the CSV was not produced by this model.py).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)                   # result/A_prediction_engine
ROOT = os.path.dirname(os.path.dirname(ENGINE))  # repo (or worktree) root
sys.path.insert(0, ENGINE)
import model  # noqa: E402  our engine, from the same checkout as this script

LABELS = {2026: os.path.join(ROOT, "labels", "dev_labels_2026.csv"),
          2025: os.path.join(ROOT, "labels", "dev_labels_2025_backtest.csv")}

# Report columns. Each evaluate.py outcome is counted in exactly one of them.
COLUMN_OF = {
    "exact": "exact", "near": "near", "same_state_off": "off",
    "wrong_state": "wrong",
    "missed": "missed", "missed_closed_business": "missed",
    "redundant_confirm": "noise", "spam_wrong_hours": "noise", "unneeded_flag": "noise",
    "flag_on_change": "other", "flag_correct": "other", "suggest_to_closed_business": "other",
    "correct_silence": "quiet_ok",
}
COLS = ("rows", "need", "exact", "near", "off", "wrong", "missed", "noise", "other", "pts", "recov")
DIMS = ("expected", "basis", "history", "day_key", "mismatch", "country", "archetype", "segment", "centre")
PAIR_DIMS = ("basis", "history", "day_key", "mismatch", "country", "archetype")


def load_evaluator():
    spec = importlib.util.spec_from_file_location("evaluate", os.path.join(ROOT, "evaluation", "evaluate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EV = load_evaluator()


def outcome(action, hours, label):
    """(outcome, points, best) for one row. Mirrors evaluation/evaluate.py score() line by line."""
    exp, truth, shown = label["expected_action"], label["truth_hours"], label["displayed_hours_at_snapshot"]
    if exp == "SUGGEST":
        if action == "SUGGEST":
            if hours == truth:
                return "exact", 1.0, 1.0
            if (hours == "closed") != (truth == "closed"):
                return "wrong_state", -1.0, 1.0
            if EV.near(hours, truth):
                return "near", 0.6, 1.0
            return "same_state_off", 0.2, 1.0
        if action == "FLAG":
            return "flag_on_change", 0.05, 1.0
        return "missed", 0.0, 1.0
    if exp == "FLAG":
        if action == "FLAG":
            return "flag_correct", 1.0, 1.0
        if action == "SUGGEST":
            return "suggest_to_closed_business", (0.3 if hours == "closed" else -1.0), 1.0
        return "missed_closed_business", 0.0, 1.0
    if action == "SUGGEST":
        if hours == shown:
            return "redundant_confirm", -0.1, 0.0
        if (hours == "closed") != (shown == "closed"):
            return "wrong_state", -1.0, 0.0
        return "spam_wrong_hours", -0.5, 0.0
    if action == "FLAG":
        return "unneeded_flag", -0.1, 0.0
    return "correct_silence", 0.0, 0.0


def history_index(bl):
    """(entity_id, day_key) -> seasons with an entry entered before the snapshot; (entity_id, date) entered set."""
    snap = bl.snap.isoformat()
    seasons, exact = defaultdict(set), set()
    for (eid, ds), rows in bl.hol.items():
        for r in rows:
            if r["entered_at"] < snap:
                seasons[(eid, r["day_key"])].add(model.cycle(date.fromisoformat(ds)))
                exact.add((eid, ds))
    return seasons, exact


def history_label(seasons, exact, eid, d, key):
    if (eid, d.isoformat()) in exact:
        return "ENTERED_FOR_DATE"
    s, cyc = seasons.get((eid, key), set()), model.cycle(d)
    if cyc - 1 in s:
        return "LAST_SEASON"
    if any(x < cyc - 1 for x in s):
        return "OLDER_ONLY"
    return "NONE"


def new_stats():
    return {c: 0 for c in COLS} | {"pts": 0.0, "recov": 0.0}


def add(stats, rec):
    stats["rows"] += 1
    stats["need"] += rec["best"] > 0
    col = COLUMN_OF[rec["outcome"]]
    if col in stats:
        stats[col] += 1
    stats["pts"] += rec["points"]
    stats["recov"] += rec["recoverable"]


def fmt_row(name, s):
    cells = "".join(f"{s[c]:>8.1f}" if c in ("pts", "recov") else f"{s[c]:>8}" for c in COLS)
    return f"  {str(name)[:40]:<40}{cells}{s['recov'] / s['rows']:>9.2f}"


def print_table(title, groups, top):
    items = sorted(groups.items(), key=lambda kv: (-kv[1]["recov"], str(kv[0])))
    print(f"\n== {title}  ({len(items)} groups, by recoverable points)")
    print(f"  {'group':<40}" + "".join(f"{c:>8}" for c in COLS) + f"{'rec/row':>9}")
    for g, s in items[:top]:
        print(fmt_row(g, s))
    if len(items) > top:
        print(f"  … {len(items) - top} more groups (raise --top)")


def print_counts(title, recs, top):
    total = len(recs)
    print(f"\n== {title}: {total} rows")
    if not total:
        return
    for dim in DIMS:
        c = Counter(r[dim] for r in recs)
        parts = ", ".join(f"{g} {n} ({100 * n / total:.0f}%)" for g, n in c.most_common(top))
        more = f", … {len(c) - top} more" if len(c) > top else ""
        print(f"  {dim:<9} {parts}{more}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026, choices=[2025, 2026])
    ap.add_argument("--predictions", default=None, help="default: outputs/ours_<season>.csv")
    ap.add_argument("--labels", default=None, help="default: the dev labels of --season")
    ap.add_argument("--top", type=int, default=12, help="groups shown per table")
    ap.add_argument("--json", default=None, help="write group statistics as JSON")
    ap.add_argument("--rows", default=None, help="write one CSV row per label row (outcome, basis, history, …)")
    a = ap.parse_args()
    pred_path = a.predictions or os.path.join(ROOT, "outputs", f"ours_{a.season}.csv")
    label_path = a.labels or LABELS[a.season]

    preds = EV.load_predictions(pred_path)
    labels = list(csv.DictReader(open(label_path, encoding="utf-8")))
    bl = model.Baseline(a.season)
    seasons, exact = history_index(bl)
    archetype = {r["segment"]: r["archetype"]
                 for r in csv.DictReader(open(os.path.join(ROOT, "data", "categories.csv"), encoding="utf-8"))}

    recs, disagree = [], []
    for lab in labels:
        eid, ds, key = lab["entity_id"], lab["date"], lab["day_key"]
        d = date.fromisoformat(ds)
        act, hrs, _ = preds.get((eid, ds), ("NO_ACTION", "", None))
        m_act, m_hrs, basis, evidence = bl.explain(eid, d, key)
        if (m_act, EV.norm(m_hrs) if m_act == "SUGGEST" else "") != (act, hrs if act == "SUGGEST" else ""):
            disagree.append((eid, ds, act, hrs, m_act, m_hrs))
        out, pts, best = outcome(act, hrs, lab)
        ent = bl.ents[eid]
        seg = ent.get("c_segment", "")
        recs.append({
            "entity_id": eid, "date": ds, "day_key": key, "action": act, "hours": hrs,
            "truth": lab["truth_hours"], "shown": lab["displayed_hours_at_snapshot"],
            "expected": lab["expected_action"], "mismatch": lab["mismatch_type"] or "NONE",
            "outcome": out, "points": pts, "best": best, "recoverable": round(best - pts, 3),
            "basis": "NONE" if basis is None else (f"{basis}=SHOWN" if m_act == "NO_ACTION" else basis),
            "evidence": "" if evidence is None else str(evidence),
            "history": history_label(seasons, exact, eid, d, key),
            "country": ent["meta"]["countryCode"], "segment": seg, "archetype": archetype.get(seg, "?"),
            "centre": "IN_CENTRE" if ent.get("c_shoppingCenterEntityId") else "STANDALONE",
        })

    # Cross-check against the organisers' scorer: the report must agree with evaluate.py to the last decimal.
    need = sum(1 for r in recs if r["best"] > 0)
    ours = round(max(0.0, 100 * sum(r["points"] for r in recs) / need), 2) if need else 0.0
    official = EV.score(preds, label_path)
    print(f"Error report · season {a.season} · {os.path.relpath(pred_path, ROOT)} vs {os.path.relpath(label_path, ROOT)}")
    print(f"  score {ours}  (evaluate.py: {official['score_0_100']})  rows {len(recs)}  needing action {need}")
    if ours != official["score_0_100"]:
        sys.exit("ERROR: report score differs from evaluate.py — the outcome rules are out of sync.")
    if disagree:
        print(f"  WARNING: {len(disagree)} rows where the CSV differs from model.explain() — was the CSV made by this "
              f"model.py? First: {disagree[0]}")
    else:
        print("  CSV matches model.explain() on every row.")

    tot = Counter(r["outcome"] for r in recs)
    pts = defaultdict(float)
    for r in recs:
        pts[r["outcome"]] += r["points"]
    print("\n== Outcomes (rows, points)")
    for o, n in tot.most_common():
        print(f"  {o:<28}{n:>7}{pts[o]:>10.1f}")
    print(f"  {'recoverable points total':<28}{'':>7}{sum(r['recoverable'] for r in recs):>10.1f}")

    groups = {dim: defaultdict(new_stats) for dim in DIMS}
    pairs = {(x, y): defaultdict(new_stats) for x, y in itertools.combinations(PAIR_DIMS, 2)}
    for r in recs:
        for dim in DIMS:
            add(groups[dim][r[dim]], r)
        for (x, y), g in pairs.items():
            add(g[(r[x], r[y])], r)

    print("\nColumns: need = truth is SUGGEST/FLAG · off = same state, >30 min off · noise = message that was not "
          "needed · other = FLAG outcomes · pts = points earned · recov = points still available · rec/row = recov/rows")
    for dim in DIMS:
        print_table(f"by {dim}", groups[dim], a.top)

    print_counts("MISSED (needed action, we stayed quiet)", [r for r in recs if COLUMN_OF[r["outcome"]] == "missed"], 6)
    print_counts("WRONG STATE (open/closed flipped, -1 each)", [r for r in recs if r["outcome"] == "wrong_state"], 6)

    singles = [(f"{dim}={g}", s) for dim in DIMS for g, s in groups[dim].items()]
    twos = [(f"{x}={gx} & {y}={gy}", s) for (x, y), g in pairs.items() for (gx, gy), s in g.items()]
    print_table("TOP 10 single groups", dict(sorted(singles, key=lambda t: -t[1]["recov"])[:10]), 10)
    print_table("TOP 10 two-way groups", dict(sorted(twos, key=lambda t: -t[1]["recov"])[:10]), 10)

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"season": a.season, "predictions": os.path.relpath(pred_path, ROOT), "score": ours,
                       "outcomes": dict(tot), "groups": {d: dict(g) for d, g in groups.items()}}, f, indent=1, sort_keys=True)
        print(f"\nwrote {a.json}")
    if a.rows:
        os.makedirs(os.path.dirname(os.path.abspath(a.rows)), exist_ok=True)
        with open(a.rows, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(recs[0]))
            w.writeheader()
            w.writerows(recs)
        print(f"wrote {a.rows}")


if __name__ == "__main__":
    main()
