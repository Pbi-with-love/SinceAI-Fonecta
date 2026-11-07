#!/usr/bin/env python3
"""Neighbour table for the "KNN on holiday behaviour" experiment, source B (basis KNN_BEHAVIOR). Standard library only.

    python3 result/A_prediction_engine/build/build_knn_truth.py     # writes tables/knn_truth_<season>.json, prints audit

This is the ONLY Part A script of this experiment that reads labels/ for prediction inputs: labels/dev_truth_history.csv,
the organisers' training data (true hours of the 802 dev businesses on every special day 2024 -> 5 Nov 2026).
model.py never opens labels/; it only reads the files written here.

What it writes per season: the behaviour vector of every dev business, built from its true hours on special days
dated strictly before that season's snapshot (2026: < 2026-11-06, back-test 2025: < 2025-11-06):

    vectors: entity -> {day_key: [state, closing minute or null]}     (state relative to the published regular hours
                                                                         of that weekday in force on that date)
    folds:   entity -> fold 0..4  (5 fixed folds by business: seeded shuffle of the sorted dev IDs in data/splits.csv)

The states come from model.knn_state() / model.knn_vector(), so source A (holiday history, computed inside model.py)
and source B use exactly the same definitions. model.py uses the folds out of sample: a dev business only draws
neighbours from the other 4 folds; test and demo businesses draw from every dev business.
Output is deterministic: sorted keys, integers, no timestamps.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PART_A = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PART_A))
TABLES = os.path.join(PART_A, "tables")
TRUTH = os.path.join(ROOT, "labels", "dev_truth_history.csv")
D = lambda *p: os.path.join(ROOT, "data", *p)  # noqa: E731
sys.path.insert(0, PART_A)
import model  # noqa: E402  (state definitions only; model.py itself never reads labels/)

SNAP = {2026: "2026-11-06", 2025: "2025-11-06"}
SEED = 20261107
N_FOLDS = 5


def dev_folds(seed=SEED, n_folds=N_FOLDS):
    """entity_id -> fold for every dev business in data/splits.csv (same scheme as the archetype-table experiment)."""
    with open(D("splits.csv"), encoding="utf-8") as f:
        dev = sorted(r["entity_id"] for r in csv.DictReader(f) if r["split"] == "dev")
    random.Random(seed).shuffle(dev)
    return {eid: i % n_folds for i, eid in enumerate(dev)}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inputs():
    reg = defaultdict(list)
    for line in open(D("regular_hours_history.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        reg[r["entity_id"]].append(r)
    with open(TRUTH, encoding="utf-8") as f:
        truth = list(csv.DictReader(f))
    return reg, truth


def build(season, reg, truth, folds):
    cut = SNAP[season]
    days = defaultdict(lambda: defaultdict(list))
    used = skipped = 0
    newest = ""
    for r in truth:
        eid, ds = r["entity_id"], r["date"]
        assert eid in folds, f"truth row for a non-dev business {eid}"
        if not ds < cut:
            skipped += 1
            continue
        assert ds < cut, f"time cut violated: {ds} >= {cut}"  # audit, per training row
        newest, used = max(newest, ds), used + 1
        days[eid][r["day_key"]].append((ds, r["truth_hours"], model.regular_in_force(reg[eid], ds, cut)))
    assert newest < cut, f"{season}: newest truth date {newest} is not before {cut}"
    vectors = {eid: {k: [s, c] for k, (s, c) in model.knn_vector(days[eid]).items()} for eid in sorted(days)}
    meta = {"season": season, "snapshot": cut, "newest_truth_date": newest, "truth_rows_used": used,
            "truth_rows_on_or_after_snapshot_skipped": skipped, "seed": SEED, "n_folds": N_FOLDS,
            "states": ["CLOSED", "REGULAR", "SHORT_CLOSE", "OTHER_HOURS"],
            "source_sha256": {"labels/dev_truth_history.csv": sha256(TRUTH), "data/splits.csv": sha256(D("splits.csv")),
                              "data/regular_hours_history.jsonl": sha256(D("regular_hours_history.jsonl"))}}
    return {"meta": meta, "folds": dict(sorted(folds.items())), "vectors": vectors}


def dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def main():
    os.makedirs(TABLES, exist_ok=True)
    reg, truth = load_inputs()
    folds = dev_folds()
    sizes = [sum(1 for v in folds.values() if v == k) for k in range(N_FOLDS)]
    print(f"dev businesses {len(folds)} in {N_FOLDS} folds (seed {SEED}): sizes {sizes}")
    print(f"truth rows {len(truth)}, dates {min(r['date'] for r in truth)} -> {max(r['date'] for r in truth)}")
    for season in (2026, 2025):
        out = build(season, reg, truth, folds)
        path = os.path.join(TABLES, f"knn_truth_{season}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps(out))
        m = out["meta"]
        n_keys = [len(v) for v in out["vectors"].values()]
        states = defaultdict(int)
        for v in out["vectors"].values():
            for s, _ in v.values():
                states[s] += 1
        print(f"\nseason {season}: truth dates < {m['snapshot']} -> {os.path.relpath(path, ROOT)}  sha256 {sha256(path)[:16]}")
        print(f"  rows used {m['truth_rows_used']}, skipped (on/after snapshot) {m['truth_rows_on_or_after_snapshot_skipped']}, "
              f"newest truth date {m['newest_truth_date']} (< {m['snapshot']}: OK)")
        print(f"  businesses {len(out['vectors'])}, known day_keys per business min {min(n_keys)} / "
              f"median {sorted(n_keys)[len(n_keys) // 2]} / max {max(n_keys)}; states {dict(sorted(states.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
