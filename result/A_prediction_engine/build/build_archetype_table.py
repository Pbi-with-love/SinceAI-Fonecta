#!/usr/bin/env python3
"""Learner for the "archetype habit table" experiment (basis ARCHETYPE_TABLE). Standard library only.

    python result/A_prediction_engine/build/build_archetype_table.py     # writes tables/, prints the audit

This is the ONLY Part A script that reads labels/ for the table: labels/dev_truth_history.csv, the organisers' training
data (true hours of the 802 dev businesses on every special day 2024 -> 5 Nov 2026). model.py never opens labels/; it
only reads the files written here (result/A_prediction_engine/tables/archetype_table_<season>.json).

What it learns: for each kind of business and special day, how often businesses were actually closed although their
published regular hours for that weekday said open. Counts only, no per-business values:

    cell -> [businesses, business_days, closed_days]

Cells (the back-off order model.py uses, first cell with >= MIN_BUSINESSES businesses wins):
    L1 segment x day_key x country -> L2 archetype x day_key x country -> L3 archetype x day_key -> L4 archetype x day_class

Human's rules (AGENTS.local.md):
  * time cut: the season-2026 tables learn only from truth dates < 2026-11-06, the 2025 back-test tables only from
    truth dates < 2025-11-06. Asserted per row and per table; the newest training date of every table is printed.
  * out of sample: dev businesses are split into N_FOLDS fixed folds (by business, seeded shuffle of the sorted dev IDs
    from data/splits.csv). Table "fold<k>" learns from the other folds and is used for dev businesses in fold k; table
    "all" learns from every dev business and is used for test and demo businesses (and for the in-sample comparison).
  * only business-days whose published regular hours for that weekday, in force on that date, were open.
Output is deterministic: sorted keys, integer counts, no timestamps.
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
D = lambda *p: os.path.join(ROOT, "data", *p)  # noqa: E731
TRUTH = os.path.join(ROOT, "labels", "dev_truth_history.csv")

SNAP = {2026: "2026-11-06", 2025: "2025-11-06"}  # season -> snapshot; training truth dates must be strictly before it
SEED = 20261107
N_FOLDS = 5
MIN_BUSINESSES = 15  # applied by model.py when it backs off; stored here so model.py can check it reads what it expects
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def dev_folds(splits_path=None, seed=SEED, n_folds=N_FOLDS):
    """entity_id -> fold (0..n_folds-1) for every dev business in data/splits.csv. model.py derives the same map."""
    with open(splits_path or D("splits.csv"), encoding="utf-8") as f:
        dev = sorted(r["entity_id"] for r in csv.DictReader(f) if r["split"] == "dev")
    random.Random(seed).shuffle(dev)
    return {eid: i % n_folds for i, eid in enumerate(dev)}


def day_str(obj):
    if not obj or obj.get("isClosed"):
        return "closed"
    return ",".join(f"{i['start']}-{i['end']}" for i in obj.get("openIntervals", [])) or "closed"


def regular_on(versions, ds):
    """Published regular hours for the weekday of ISO date ds, from the version in force on ds (None if none)."""
    from datetime import date
    then = [r for r in versions if r["effective_from"] == "before-2024" or r["effective_from"] <= ds]
    if not then:
        return None
    best = max(then, key=lambda r: "0000" if r["effective_from"] == "before-2024" else r["effective_from"])
    return day_str(best["hours"][DAYS[date.fromisoformat(ds).weekday()]])


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cell_keys(seg, arch, key, cc, cls):
    keys = [f"L1|{seg}|{key}|{cc}", f"L2|{arch}|{key}|{cc}", f"L3|{arch}|{key}"]
    if cls:  # EVENT and SCHOOL_BREAK are not calendar days: no day_class level
        keys.append(f"L4|{arch}|{cls}")
    return keys


def load_inputs():
    ents = {e["meta"]["id"]: e for e in json.load(open(D("entities.json"), encoding="utf-8"))["response"]["entities"]}
    arch = {r["segment"]: r["archetype"] for r in csv.DictReader(open(D("categories.csv"), encoding="utf-8"))}
    cal_class = {(r["country"], r["date"]): r["day_class"]
                 for r in csv.DictReader(open(D("calendar_special_days.csv"), encoding="utf-8"))}
    reg = defaultdict(list)
    for line in open(D("regular_hours_history.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        reg[r["entity_id"]].append(r)
    with open(TRUTH, encoding="utf-8") as f:
        truth = list(csv.DictReader(f))
    return ents, arch, cal_class, reg, truth


def build(season, ents, arch, cal_class, reg, truth, folds):
    cut = SNAP[season]
    # One pass: the usable training rows of this season (dev, before the cut, regular hours open that weekday).
    used, skipped_regular_closed, skipped_after_cut = [], 0, 0
    for r in truth:
        eid, ds = r["entity_id"], r["date"]
        assert eid in folds, f"truth row for a non-dev business {eid}"
        if not ds < cut:
            skipped_after_cut += 1
            continue
        reg_then = regular_on(reg[eid], ds)
        if reg_then in (None, "closed"):
            skipped_regular_closed += 1
            continue
        e = ents[eid]
        seg, cc = e["c_segment"], e["meta"]["countryCode"]
        used.append((eid, ds, cell_keys(seg, arch[seg], r["day_key"], cc, cal_class.get((cc, ds))),
                     r["truth_hours"] == "closed"))

    tables, newest, n_rows = {}, {}, {}
    for name in ["all"] + [f"fold{k}" for k in range(N_FOLDS)]:
        held_out = None if name == "all" else int(name[4:])
        bus, days, closed = defaultdict(set), defaultdict(int), defaultdict(int)
        last, n = "", 0
        for eid, ds, keys, is_closed in used:
            if held_out is not None and folds[eid] == held_out:
                continue  # out of fold: never learn from the businesses this table will be used for
            assert ds < cut, f"time cut violated: {ds} >= {cut}"  # audit, per training row
            last, n = max(last, ds), n + 1
            for k in keys:
                bus[k].add(eid)
                days[k] += 1
                closed[k] += int(is_closed)
        assert last < cut, f"{season}/{name}: newest training date {last} is not before {cut}"
        tables[name] = {k: [len(bus[k]), days[k], closed[k]] for k in sorted(bus)}
        newest[name], n_rows[name] = last, n
    meta = {
        "season": season, "snapshot": cut, "truth_dates_before": cut, "seed": SEED, "n_folds": N_FOLDS,
        "min_businesses": MIN_BUSINESSES, "levels": ["L1 segment|day_key|country", "L2 archetype|day_key|country",
                                                     "L3 archetype|day_key", "L4 archetype|day_class"],
        "cell_value": ["businesses", "business_days", "closed_days"],
        "newest_training_date": newest, "training_rows": n_rows,
        "skipped": {"truth_date_not_before_snapshot": skipped_after_cut,
                    "regular_hours_closed_that_weekday": skipped_regular_closed},
        "source_sha256": {"labels/dev_truth_history.csv": sha256(TRUTH), "data/splits.csv": sha256(D("splits.csv"))},
    }
    return {"meta": meta, "folds": dict(sorted(folds.items())), "tables": tables}


def main():
    os.makedirs(TABLES, exist_ok=True)
    ents, arch, cal_class, reg, truth = load_inputs()
    folds = dev_folds()
    sizes = [sum(1 for v in folds.values() if v == k) for k in range(N_FOLDS)]
    print(f"dev businesses {len(folds)} in {N_FOLDS} folds (seed {SEED}): sizes {sizes}")
    print(f"truth rows {len(truth)}, dates {min(r['date'] for r in truth)} -> {max(r['date'] for r in truth)}")
    for season in (2026, 2025):
        out = build(season, ents, arch, cal_class, reg, truth, folds)
        m = out["meta"]
        path = os.path.join(TABLES, f"archetype_table_{season}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            f.write("\n")
        print(f"\nseason {season}: truth dates < {m['truth_dates_before']} -> {os.path.relpath(path, ROOT)}  "
              f"sha256 {sha256(path)[:16]}")
        print(f"  skipped: {m['skipped']}")
        for name in out["tables"]:
            t = out["tables"][name]
            ok = sum(1 for v in t.values() if v[0] >= MIN_BUSINESSES)
            print(f"  table {name:6s} training rows {m['training_rows'][name]:6d}  newest training date "
                  f"{m['newest_training_date'][name]}  (< {m['snapshot']}: OK)  cells {len(t)} "
                  f"(>= {MIN_BUSINESSES} businesses: {ok})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
