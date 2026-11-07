#!/usr/bin/env python3
"""Audit for the KNN-on-behaviour experiment (source B and A). Standard library only. Exit code 1 if a check fails.

    python3 result/A_prediction_engine/build/audit_knn.py

1. labels/ removed: model.py (config: source B, after OWNER_PATTERN, min shared 3, K 20, threshold 0.9, and source A) runs
   in a temp tree that has result/, data/ and evaluation/ but NO labels/; output must be byte-identical to the normal run.
2. No file under labels/ is opened by model.py (sys.audit hook), and each season opens only its own knn_truth table.
3. Time cut: the stored tables equal a rebuild from truth rows dated < the snapshot only; newest truth date < snapshot;
   source A drops history rows entered on/after the snapshot (checked on a vector built with and without them).
4. Out of fold: every dev business draws neighbours only from the other 4 folds (never itself, never its fold);
   test/demo businesses use all dev businesses; fold map == data/splits.csv + seed.
5. Determinism: two runs byte-identical per season and source; tables rebuilt twice byte-identical.
6. No entity IDs in model.py's code (string literals / comments outside docstrings).
"""
from __future__ import annotations

import ast, csv, hashlib, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PART_A = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PART_A))
sys.path.insert(0, HERE); sys.path.insert(0, PART_A)
import build_knn_truth as bt  # noqa: E402
import model  # noqa: E402

FAIL = []
RUN = r"""
import os, sys, json
opened = []
sys.addaudithook(lambda ev, a: opened.append(os.path.abspath(str(a[0]))) if ev == "open" and a and isinstance(a[0], (str, bytes, os.PathLike)) else None)
sys.path.insert(0, %r)
import model
model.Baseline.KNN_SOURCE, model.Baseline.KNN_MIN_SHARED, model.Baseline.KNN_K, model.Baseline.KNN_THRESHOLD = %r, 3, 20, 0.9
sys.argv = ["model.py", "--season", %r, "--out", %r]
model.main()
print("OPENED_JSON " + json.dumps(sorted(set(opened))))
"""


def check(ok, msg):
    print(("  OK    " if ok else "  FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def run(part_a, src, season, out):
    r = subprocess.run([sys.executable, "-c", RUN % (part_a, src, str(season), out)], check=True, capture_output=True, text=True)
    return json.loads(r.stdout.split("OPENED_JSON ", 1)[1])


def main():
    labels_dir = os.path.join(ROOT, "labels") + os.sep
    with tempfile.TemporaryDirectory() as tmp:
        tree = os.path.join(tmp, "tree")
        os.makedirs(tree)
        shutil.copytree(os.path.join(ROOT, "result"), os.path.join(tree, "result"), ignore=shutil.ignore_patterns("__pycache__"))
        os.symlink(os.path.join(ROOT, "data"), os.path.join(tree, "data"))
        os.symlink(os.path.join(ROOT, "evaluation"), os.path.join(tree, "evaluation"))
        assert not os.path.exists(os.path.join(tree, "labels"))
        print("1-2, 5. labels/ removed, no labels/ opened, own table only, deterministic")
        for src in ("B", "A"):
            for season in (2026, 2025):
                o1, o2, o3 = (os.path.join(tmp, f"{src}{season}_{i}.csv") for i in (1, 2, 3))
                op1 = run(PART_A, src, season, o1)
                run(PART_A, src, season, o2)
                run(os.path.join(tree, "result", "A_prediction_engine"), src, season, o3)
                b1, b2, b3 = (open(p, "rb").read() for p in (o1, o2, o3))
                check(b1 == b2, f"{src}/{season}: two runs byte-identical ({sha(b1)})")
                check(b1 == b3, f"{src}/{season}: run in a tree WITHOUT labels/ is byte-identical")
                check(not [p for p in op1 if p.startswith(labels_dir)], f"{src}/{season}: no file under labels/ opened")
                mine = os.path.join(PART_A, "tables", f"knn_truth_{season}.json")
                other = os.path.join(PART_A, "tables", f"knn_truth_{2025 if season == 2026 else 2026}.json")
                if src == "B":
                    check(mine in op1 and other not in op1, f"{src}/{season}: opens knn_truth_{season}.json only")
                else:
                    check(not [p for p in op1 if os.sep + "tables" + os.sep in p], f"{src}/{season}: source A opens no tables/ file")
    print("3. time cut")
    reg, truth = bt.load_inputs()
    folds = bt.dev_folds()
    for season in (2026, 2025):
        cut = bt.SNAP[season]
        st = open(os.path.join(bt.TABLES, f"knn_truth_{season}.json"), encoding="utf-8").read()
        pre = [r for r in truth if r["date"] < cut]
        rb, sj = bt.build(season, reg, pre, folds), json.loads(st)
        check(rb["vectors"] == sj["vectors"] and rb["folds"] == sj["folds"],
              f"{season}: stored vectors == rebuild from {len(pre)} truth rows dated < {cut} only (build() also drops later rows itself)")
        check(json.loads(st)["meta"]["newest_truth_date"] < cut, f"{season}: newest truth date {json.loads(st)['meta']['newest_truth_date']} < {cut}")
        b = model.Baseline(season)
        n_late = sum(1 for rows in b.hol.values() for r in rows if r["entered_at"] >= cut)
        b._knn_hist = None
        hv = b._knn_hist_vectors()
        b2 = model.Baseline(season)
        for k in list(b2.hol):
            b2.hol[k] = [r for r in b2.hol[k] if r["entered_at"] < cut]
        check(hv == b2._knn_hist_vectors(), f"{season}: source A vectors unchanged when the {n_late} history rows entered on/after {cut} are deleted")
        check(all(v == v for v in hv.values()), f"{season}: source A vectors for {len(hv)} businesses built")
    print("4. out of fold")
    for season in (2026, 2025):
        b = model.Baseline(season)
        b.KNN_SOURCE = "B"
        tb = b._knn_truth()
        check(tb["folds"] == folds, f"{season}: fold map == data/splits.csv + seed {bt.SEED}")
        bad = 0
        _, split = b._knn_meta()
        for eid in sorted(b.ents):
            if b.ents[eid].get("c_entityRole") == "SHOPPING_CENTRE":
                continue
            name, pool = b._knn_pool(eid)
            if split.get(eid) == "dev":
                bad += (name != f"B:fold{folds[eid]}") or eid in pool or any(folds[o] == folds[eid] for o in pool) or len(pool) < 600
            else:
                bad += (name != "B:all") or len(pool) != 802
        check(bad == 0, f"{season}: every dev business -> pool of the other 4 folds (no self, no own fold); others -> all 802 dev")
    print("6. no entity IDs in model.py")
    src_text = open(os.path.join(PART_A, "model.py"), encoding="utf-8").read()
    ids = re.findall(r"\b(?:FI|SE|NO)-(?:M|D)?\d{3,5}\b", src_text)
    check(not ids, f"no entity-ID literal in model.py ({ids[:3]})")
    tree_ast = ast.parse(src_text)
    lits = [n.value for n in ast.walk(tree_ast) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "label" in n.value.lower() and len(n.value) < 40]
    check(not lits, f"no string literal naming labels ({lits[:3]})")
    print(f"\n{'ALL CHECKS PASSED' if not FAIL else f'{len(FAIL)} CHECK(S) FAILED'}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
