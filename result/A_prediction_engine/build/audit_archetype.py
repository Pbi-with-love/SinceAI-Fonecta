#!/usr/bin/env python3
"""Snapshot / leakage / determinism audit for the archetype habit table (hyp-archetype-table). Standard library only.

    python result/A_prediction_engine/build/audit_archetype.py

Checks (exit code 1 if any fails):
  1. Time cut: every truth row behind each stored table is dated before that season's snapshot. The stored tables are
     rebuilt from scratch with only pre-snapshot rows and must match byte for byte; the newest training date of every
     table is before the snapshot; the 2025 tables differ from a no-cut build (so the cut really bites).
  2. Out of fold: every stored fold table equals a rebuild that drops that fold's businesses, and model.py maps every
     dev business in the targets to the fold table that never saw it (test/demo -> "all"; in-sample flag -> "all").
     The fold map in the table file equals the one model.py derives from data/splits.csv + seed.
  3. model.py opens nothing under labels/: both seasons are predicted under a sys.audit hook that records every file
     opened; none may be under labels/. Each season must open its own table file and not the other season's.
  4. Determinism: the tables built twice are byte-identical; model.py run twice per season gives byte-identical CSVs.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
PART_A = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PART_A))
sys.path.insert(0, HERE)
sys.path.insert(0, PART_A)
import build_archetype_table as bt  # noqa: E402

FAIL = []


def check(ok, msg):
    print(("  OK    " if ok else "  FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)


def dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def audit_tables():
    print("1-2. time cut and out-of-fold tables")
    ents, arch, cal_class, reg, truth = bt.load_inputs()
    folds = bt.dev_folds()
    for season in (2026, 2025):
        path = os.path.join(bt.TABLES, f"archetype_table_{season}.json")
        stored = open(path, encoding="utf-8").read()
        st = json.loads(stored)
        cut = bt.SNAP[season]
        # (1) rebuild from pre-cut rows only, independently of the stored file
        pre = [r for r in truth if r["date"] < cut]
        check(all(r["date"] < cut for r in pre), f"{season}: {len(pre)} truth rows kept, all dated < {cut}")
        rebuilt = bt.build(season, ents, arch, cal_class, reg, pre, folds)
        check(rebuilt["tables"] == st["tables"] and rebuilt["folds"] == st["folds"],
              f"{season}: stored tables (all + {bt.N_FOLDS} folds) == rebuild from rows dated < {cut} only")
        newest = st["meta"]["newest_training_date"]
        check(all(v < cut for v in newest.values()),
              f"{season}: newest training date per table {sorted(set(newest.values()))} all < {cut}")
        nocut = bt.build(season, ents, arch, cal_class, reg, truth, folds)  # build() itself drops rows >= cut
        check(dumps(nocut) == stored, f"{season}: build() drops rows >= {cut} by itself (same result from all rows)")
        if season == 2025:
            leaky = bt.build(2026, ents, arch, cal_class, reg, truth, folds)["tables"]["all"]
            check(leaky != st["tables"]["all"], "2025: table differs from one learned with 2026-season rows")
        # (2) each fold table learns only from the other folds' businesses
        for k in range(bt.N_FOLDS):
            others = [r for r in pre if folds[r["entity_id"]] != k]
            only = bt.build(season, ents, arch, cal_class, reg, others, folds)["tables"]["all"]
            check(only == st["tables"][f"fold{k}"],
                  f"{season}: fold{k} == table from the {sum(1 for v in folds.values() if v != k)} businesses "
                  f"outside fold {k}")
        check(st["folds"] == folds, f"{season}: stored fold map == data/splits.csv + seed {bt.SEED}")


def audit_model_mapping():
    print("2b. model.py uses the out-of-fold table for every dev business")
    import model
    for season, tf in ((2026, "targets_2026.csv"), (2025, "targets_2025_backtest.csv")):
        bl = model.Baseline(season)
        a = bl._arch()
        rows = list(csv.DictReader(open(os.path.join(ROOT, "evaluation", tf), encoding="utf-8")))
        eids = sorted({r["entity_id"] for r in rows})
        bad = [e for e in eids if bl._arch_table_name(e) != (f"fold{a['folds'][e]}" if a["split"][e] == "dev" else "all")]
        n_dev = sum(1 for e in eids if a["split"][e] == "dev")
        check(not bad, f"{season}: {n_dev} dev businesses -> own out-of-fold table, {len(eids) - n_dev} others -> all "
                       f"(mismatches: {bad[:5]})")
        st = json.load(open(os.path.join(bt.TABLES, f"archetype_table_{season}.json"), encoding="utf-8"))
        own = [e for e in eids if a["split"][e] == "dev" and st["folds"][e] != int(bl._arch_table_name(e)[4:])]
        check(not own, f"{season}: no dev business is scored with a table that contains it")
        bl.ARCH_IN_SAMPLE = True
        check(all(bl._arch_table_name(e) == "all" for e in eids), f"{season}: in-sample switch -> 'all' for everyone")


def audit_no_labels_and_determinism():
    print("3-4. model.py never opens labels/; each season opens its own table; deterministic CSVs")
    code = r"""
import os, sys, json
opened = []
sys.addaudithook(lambda ev, args: opened.append(os.path.abspath(str(args[0]))) if ev == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)) else None)
sys.path.insert(0, %r)
import model
sys.argv = ["model.py", "--season", %r, "--out", %r]
model.main()
print("OPENED_JSON " + json.dumps(sorted(set(opened))))
"""
    labels_dir = os.path.join(ROOT, "labels") + os.sep
    with tempfile.TemporaryDirectory() as tmp:
        for season in (2026, 2025):
            outs = []
            for i in (1, 2):
                out = os.path.join(tmp, f"run{i}_{season}.csv")
                r = subprocess.run([sys.executable, "-c", code % (PART_A, str(season), out)], check=True,
                                   capture_output=True, text=True)
                opened = json.loads(r.stdout.split("OPENED_JSON ", 1)[1])
                bad = [p for p in opened if p.startswith(labels_dir)]
                check(not bad, f"{season} run {i}: {len(opened)} files opened, none under labels/ {bad[:3]}")
                mine = os.path.join(bt.TABLES, f"archetype_table_{season}.json")
                other = os.path.join(bt.TABLES, f"archetype_table_{2025 if season == 2026 else 2026}.json")
                check(mine in opened and other not in opened,
                      f"{season} run {i}: opens tables/archetype_table_{season}.json only")
                outs.append(open(out, "rb").read())
            check(outs[0] == outs[1], f"{season}: two model.py runs give byte-identical CSVs (sha256 "
                                      f"{sha(outs[0])[:16]})")
        # static: no string literal in model.py's code (docstrings and comments excluded) mentions labels
        tree = ast.parse(open(os.path.join(PART_A, "model.py"), encoding="utf-8").read())
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body and
                isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docs and "label" in n.value.lower()]
        check(not lits, f"model.py code has no string literal naming labels (found: {lits[:3]})")
        # tables built twice -> same bytes (build into a temp copy, compare with the committed files)
        before = {s: open(os.path.join(bt.TABLES, f"archetype_table_{s}.json"), "rb").read() for s in (2026, 2025)}
        for i in (1, 2):
            with redirect_stdout(io.StringIO()):
                bt.main()
            after = {s: open(os.path.join(bt.TABLES, f"archetype_table_{s}.json"), "rb").read() for s in (2026, 2025)}
            check(after == before, f"table build run {i}: byte-identical to the committed tables "
                                   f"({', '.join(f'{s} {sha(after[s])[:16]}' for s in after)})")


def main():
    audit_tables()
    audit_model_mapping()
    audit_no_labels_and_determinism()
    print(f"\n{'ALL CHECKS PASSED' if not FAIL else f'{len(FAIL)} CHECK(S) FAILED'}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
