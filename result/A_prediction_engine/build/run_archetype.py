#!/usr/bin/env python3
"""Experiment runner for the archetype habit table (hyp-archetype-table). Standard library only.

Runs model.main() unchanged with the ARCHETYPE_TABLE settings overridden, then scores with evaluation/evaluate.py.

    # one run (same CSV model.py would write with these settings)
    python result/A_prediction_engine/build/run_archetype.py --season 2026 --place a --threshold 0.90 \
        --out outputs/hyp-archetype-table/a_090_2026.csv
    python result/A_prediction_engine/build/run_archetype.py --season 2026 --place a --threshold 0.90 --in-sample \
        --out outputs/hyp-archetype-table/a_090_2026_insample.csv     # comparison only: dev sees its own history

    # the sweep: off / config a / config b x thresholds 0.80 0.85 0.90 0.95 x both seasons, out of sample,
    # plus in-sample for every setting; prints a markdown table
    python result/A_prediction_engine/build/run_archetype.py --sweep

--place: "a" = new block after owner pattern, before peers; "b" = replaces the peer rule; "off" = main's cascade.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PART_A = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PART_A))
OUT = os.path.join(ROOT, "outputs", "hyp-archetype-table")
LABELS = {2026: os.path.join(ROOT, "labels", "dev_labels_2026.csv"),
          2025: os.path.join(ROOT, "labels", "dev_labels_2025_backtest.csv")}
THRESHOLDS = (0.80, 0.85, 0.90, 0.95)


def run_one(season, place, threshold, in_sample, out):
    """Write the predictions CSV in a fresh process (no state shared between settings)."""
    code = ("import sys; sys.path.insert(0, %r); import model; B = model.Baseline; "
            "B.ARCH_PLACE = %r; B.ARCH_THRESHOLD = %r; B.ARCH_IN_SAMPLE = %r; "
            "sys.argv = ['model.py', '--season', %r, '--out', %r]; model.main()"
            % (PART_A, "" if place == "off" else place, threshold, in_sample, str(season), out))
    subprocess.run([sys.executable, "-c", code], check=True, stdout=subprocess.DEVNULL)


def evaluate(season, csv_path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "evaluation", "evaluate.py"), "--predictions", csv_path,
                        "--labels", LABELS[season], "--json"], check=True, capture_output=True, text=True)
    return json.loads(r.stdout)


def summary(res):
    b = res["breakdown"]
    return {"score": res["score_0_100"], "wrong": b.get("harmful_wrong_state", 0), "missed": b.get("missed", 0),
            "exact": b.get("exact", 0), "needless": b.get("spam_wrong_hours", 0) + b.get("redundant_confirm", 0),
            "spam": b.get("spam_wrong_hours", 0), "redundant": b.get("redundant_confirm", 0)}


def sweep():
    os.makedirs(OUT, exist_ok=True)
    settings = [("off", None)] + [(p, t) for p in ("a", "b") for t in THRESHOLDS]
    rows = []
    for place, thr in settings:
        row = {"place": place, "thr": thr}
        for season in (2026, 2025):
            for ins in ((False,) if place == "off" else (False, True)):
                tag = f"{place}_{'off' if thr is None else int(round(thr * 100))}_{season}" + ("_insample" if ins else "")
                path = os.path.join(OUT, "sweep", tag + ".csv")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                run_one(season, place, thr or 0.9, ins, path)
                res = evaluate(season, path)
                with open(path[:-4] + ".json", "w", encoding="utf-8") as f:
                    json.dump(res, f, indent=2, sort_keys=True)
                row[(season, ins)] = summary(res)
        rows.append(row)
    print("| config | thr | dev 2026 OOS | wrong | needless (spam+red.) | missed | back-test 2025 OOS | wrong | "
          "needless (spam+red.) | missed | dev 2026 in-sample | 2025 in-sample |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    def cells(s):
        return f"{s['score']:.2f} | {s['wrong']} | {s['needless']} ({s['spam']}+{s['redundant']}) | {s['missed']}"

    def ins(s):
        return "-" if s is None else f"{s['score']:.2f}"

    for row in rows:
        thr = "-" if row["thr"] is None else f"{row['thr']:.2f}"
        print(f"| {row['place']} | {thr} | {cells(row[(2026, False)])} | {cells(row[(2025, False)])} "
              f"| {ins(row.get((2026, True)))} | {ins(row.get((2025, True)))} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--season", type=int, default=2026, choices=[2025, 2026])
    ap.add_argument("--place", default="a", choices=["a", "b", "off"])
    ap.add_argument("--threshold", type=float, default=0.90)
    ap.add_argument("--in-sample", action="store_true", help="comparison only: dev businesses see the all-dev table")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.sweep:
        return sweep()
    out = a.out or os.path.join(OUT, f"run_{a.place}_{a.season}.csv")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run_one(a.season, a.place, a.threshold, a.in_sample, out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
