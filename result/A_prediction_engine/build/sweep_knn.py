#!/usr/bin/env python3
"""Grid sweep for the "KNN on holiday behaviour" experiment. ANALYSIS ONLY: reads labels/ to score; model.py never
imports this file. Standard library only.

    python3 result/A_prediction_engine/build/sweep_knn.py [--out outputs/hyp-knn-behavior/sweep.json]

For both seasons it runs model.explain() on every dev label row, once with the KNN block off (reference = main at
part-a-final) and once per configuration, and scores each run with evaluation/evaluate.py's own score() (cross-checked
row by row with a per-row copy of the same rules). Grid (AGENTS.local.md): source A | B; placement after OWNER_PATTERN
| replacing it; minimum shared day_keys 2 | 3; K 5 | 10 | 20; threshold 0.6 | 0.7 | 0.8 | 0.9. Source B is scored out
of sample (dev businesses use only the other 4 folds) and, for comparison, in sample.

Reported per configuration and season: score, exact, wrong state, needless (spam_wrong_hours + redundant_confirm),
missed, rows the block touches (KNN gave a candidate), rows whose action changed vs the reference, and net points by
day group (delta vs the reference).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
PART_A = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PART_A))
sys.path.insert(0, PART_A)
import model  # noqa: E402

LABELS = {2026: os.path.join(ROOT, "labels", "dev_labels_2026.csv"),
          2025: os.path.join(ROOT, "labels", "dev_labels_2025_backtest.csv")}
GROUPS = {"INTERDAY": "between", "XMAS_EVE": "eves", "NYE": "eves", "EPIPHANY_EVE": "eves",
          "DEC23": "shopping", "BLACK_FRIDAY": "shopping", "SCHOOL_BREAK": "shopping",
          "XMAS_DAY": "major", "BOXING_DAY": "major", "NEW_YEARS_DAY": "major", "EPIPHANY": "major",
          "INDEPENDENCE_DAY": "major"}
GROUP_ORDER = ("between", "eves", "shopping", "major", "other")
REF = {2026: 65.92, 2025: 62.73}
REF_WRONG = {2026: 383, 2025: 377}


def load_evaluator():
    spec = importlib.util.spec_from_file_location("evaluate", os.path.join(ROOT, "evaluation", "evaluate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EV = load_evaluator()


def row_points(r, a, h):
    """(outcome, points) for one label row, the same rules as evaluation/evaluate.py score()."""
    exp, truth, shown = r["expected_action"], r["truth_hours"], r["displayed_hours_at_snapshot"]
    if exp == "SUGGEST":
        if a == "SUGGEST":
            if h == truth:
                return "exact", 1.0
            if (h == "closed") != (truth == "closed"):
                return "harmful_wrong_state", -1.0
            if EV.near(h, truth):
                return "near", 0.6
            return "same_state_off", 0.2
        if a == "FLAG":
            return "flag_on_change", 0.05
        return "missed", 0.0
    if exp == "FLAG":
        if a == "FLAG":
            return "flag_correct", 1.0
        if a == "SUGGEST":
            return "suggest_to_closed_business", 0.3 if h == "closed" else -1.0
        return "missed_closed_business", 0.0
    if a == "SUGGEST":
        if h == shown:
            return "redundant_confirm", -0.1
        if (h == "closed") != (shown == "closed"):
            return "harmful_wrong_state", -1.0
        return "spam_wrong_hours", -0.5
    if a == "FLAG":
        return "unneeded_flag", -0.1
    return "correct_silence", 0.0


def run(bl, labels):
    """Predict every label row; returns (preds dict for evaluate.score, per-row list)."""
    preds, rows = {}, []
    for r in labels:
        d = date.fromisoformat(r["date"])
        a, h, basis, _ = bl.explain(r["entity_id"], d, r["day_key"])
        h = EV.norm(h)
        if a != "NO_ACTION":
            preds[(r["entity_id"], r["date"])] = (a, h, None)
        rows.append((a, h, basis))
    return preds, rows


def summarise(labels, preds, rows, ref_rows, labels_path):
    res = EV.score(preds, labels_path)
    outc, pts_g, ref_g = Counter(), defaultdict(float), defaultdict(float)
    total = 0.0
    touched = changed = 0
    for r, (a, h, basis), (ra, rh, _) in zip(labels, rows, ref_rows):
        o, p = row_points(r, a, h)
        _, rp = row_points(r, ra, rh)
        outc[o] += 1
        total += p
        g = GROUPS.get(r["day_key"], "other")
        pts_g[g] += p
        ref_g[g] += rp
        touched += basis == "KNN_BEHAVIOR"
        changed += (a, h) != (ra, rh)
    mx = res["rows_needing_action"]
    mine = round(max(0.0, 100 * total / mx), 2)
    assert mine == res["score_0_100"], f"per-row total {mine} != evaluate.py {res['score_0_100']}"
    b = res["breakdown"]
    assert {k: v for k, v in outc.items() if v} == {k: v for k, v in b.items() if v}, (dict(outc), b)
    return {"score": res["score_0_100"], "exact": b.get("exact", 0), "wrong": b.get("harmful_wrong_state", 0),
            "needless": b.get("spam_wrong_hours", 0) + b.get("redundant_confirm", 0),
            "spam": b.get("spam_wrong_hours", 0), "redundant": b.get("redundant_confirm", 0),
            "missed": b.get("missed", 0), "near": b.get("near", 0), "off": b.get("same_state_off", 0),
            "touched": touched, "changed": changed,
            "group_delta": {g: round(pts_g[g] - ref_g[g], 1) for g in GROUP_ORDER},
            "group_net": {g: round(pts_g[g], 1) for g in GROUP_ORDER}}


def configs():
    for src, repl, ms, k, thr in itertools.product(("A", "B"), (False, True), (2, 3), (5, 10, 20), (0.6, 0.7, 0.8, 0.9)):
        yield {"source": src, "replace_owner": repl, "min_shared": ms, "k": k, "threshold": thr}


def apply(bl, c, in_sample=False):
    bl.KNN_SOURCE = c["source"]
    bl.KNN_REPLACES_OWNER = c["replace_owner"]
    bl.KNN_MIN_SHARED = c["min_shared"]
    bl.KNN_K = c["k"]
    bl.KNN_THRESHOLD = c["threshold"]
    bl.KNN_IN_SAMPLE = in_sample
    for k, v in c.get("extra", {}).items():
        setattr(bl, k, v)


def name(c):
    return (f"{c['source']} {'repl' if c['replace_owner'] else 'after'} ms{c['min_shared']} k{c['k']:<2d} "
            f"t{c['threshold']:.1f}" + "".join(f" {k}={v}" for k, v in c.get("extra", {}).items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "hyp-knn-behavior", "sweep.json"))
    ap.add_argument("--only", default=None, help="restrict to source A or B")
    ap.add_argument("--extra", default=None, help="JSON dict of extra class attributes applied to every configuration")
    a = ap.parse_args()
    extra = json.loads(a.extra) if a.extra else {}
    out = {"reference": {}, "configs": []}
    cfgs = [dict(c, extra=extra) for c in configs() if a.only in (None, c["source"])]
    results = {i: {"config": c} for i, c in enumerate(cfgs)}
    for season in (2026, 2025):
        t0 = time.time()
        labels = list(csv.DictReader(open(LABELS[season], encoding="utf-8")))
        bl = model.Baseline(season)
        bl.KNN_SOURCE = None
        ref_preds, ref_rows = run(bl, labels)
        ref = summarise(labels, ref_preds, ref_rows, ref_rows, LABELS[season])
        out["reference"][str(season)] = ref
        print(f"season {season} reference: score {ref['score']} exact {ref['exact']} wrong {ref['wrong']} "
              f"needless {ref['needless']} missed {ref['missed']}", flush=True)
        for i, c in enumerate(cfgs):
            apply(bl, c)
            p, rows = run(bl, labels)
            results[i][str(season)] = summarise(labels, p, rows, ref_rows, LABELS[season])
            if c["source"] == "B":
                apply(bl, c, in_sample=True)
                p, rows = run(bl, labels)
                results[i][f"{season}_in_sample"] = summarise(labels, p, rows, ref_rows, LABELS[season])["score"]
        print(f"season {season}: {len(cfgs)} configurations in {time.time() - t0:.0f} s", flush=True)
    out["configs"] = [results[i] for i in range(len(cfgs))]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    hdr = (f"{'config':32s} {'dev26':>6s} {'Δ':>6s} {'bt25':>6s} {'Δ':>6s} {'wr26':>5s} {'wr25':>5s} {'nl26':>5s} "
           f"{'nl25':>5s} {'ex26':>5s} {'ex25':>5s} {'tch26':>5s} {'tch25':>5s} {'in26':>6s} {'in25':>6s}  keep")
    print("\n" + hdr)
    for r in out["configs"]:
        c, x, y = r["config"], r["2026"], r["2025"]
        keep = (x["score"] > REF[2026] and y["score"] > REF[2025] and x["wrong"] <= REF_WRONG[2026] and
                y["wrong"] <= REF_WRONG[2025])
        print(f"{name(c):32s} {x['score']:6.2f} {x['score'] - REF[2026]:+6.2f} {y['score']:6.2f} "
              f"{y['score'] - REF[2025]:+6.2f} {x['wrong']:5d} {y['wrong']:5d} {x['needless']:5d} {y['needless']:5d} "
              f"{x['exact']:5d} {y['exact']:5d} {x['touched']:5d} {y['touched']:5d} "
              f"{r.get('2026_in_sample', float('nan')):6.2f} {r.get('2025_in_sample', float('nan')):6.2f}  "
              f"{'KEEP' if keep else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
