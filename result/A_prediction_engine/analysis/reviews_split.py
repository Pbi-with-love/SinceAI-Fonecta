"""Reviews feasibility, step 4 split: is the problem misreading ('closed early' read as 'closed') or wrong reviews?
Prerequisites (outputs/ is not committed), from the repo root:
    python result/A_prediction_engine/analysis/error_report.py --season 2026 --predictions predictions_2026.csv --rows outputs/report/rows_final_2026.csv
    python result/A_prediction_engine/model.py --season 2025 --out outputs/ours_2025.csv
    python result/A_prediction_engine/analysis/error_report.py --season 2025 --predictions outputs/ours_2025.csv --rows outputs/report/rows_final_2025.csv
Then:  python result/A_prediction_engine/analysis/reviews_split.py
ANALYSIS ONLY: reads labels/ (through the error-report rows); never imported by model.py. Results: EXPERIMENTS.md, "Reviews feasibility".
"""
import csv, re, collections as C
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from reviews_feasibility import classify, reviews, cutoff_ms, ER, SPECIFIC_HOURS
EARLY = re.compile(r"\bjo\b|redan|allerede|already|aikaisin|tidigt|tidlig|early|stängde|stengte|sulki|closed at|klo \d|kl\.? ?\d", re.I)
CLOSE_AT = re.compile(r"(?:stängde de redan|stengte (?:de )?allerede|closed at|sulkivat jo|closed already at)\s*(?:kl\.?\s*)?(\d{1,2})(?:[:.](\d{2}))?", re.I)
for season in (2026, 2025):
    pre = [x for x in (classify(r) for r in reviews if r["publisherDate"] < cutoff_ms(season)) if x and x["closed"] and x["hol"]]
    kind = C.defaultdict(set); close_at = {}
    for x in pre:
        k = "EARLY_CLOSE" if (EARLY.search(x["text"]) or SPECIFIC_HOURS.search(x["text"])) else "FULL_DAY"
        for h in set(x["hol"]):
            kind[(x["loc"], h)].add(k)
            m = CLOSE_AT.search(x["text"])
            if m: close_at[(x["loc"], h)] = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    rows = {(r["entity_id"], r["date"]): r for r in csv.DictReader(open(f"{ROOT}/outputs/report/rows_final_{season}.csv", encoding="utf-8"))}
    labels = list(csv.DictReader(open(ER.LABELS[season], encoding="utf-8")))
    need = sum(1 for l in labels if l["expected_action"] in ("SUGGEST", "FLAG"))
    quiet = [l for l in labels if (l["entity_id"], l["day_key"]) in kind and rows[(l["entity_id"], l["date"])]["action"] == "NO_ACTION"
             and l["displayed_hours_at_snapshot"] != "closed"]
    print(f"\n######## season {season}: quiet rows with a closure review naming the day_key: {len(quiet)}")
    for name in ("FULL_DAY", "EARLY_CLOSE"):
        sel = [l for l in quiet if kind[(l["entity_id"], l["day_key"])] == {name}]
        truth = C.Counter("closed" if l["truth_hours"] == "closed" else ("needs other hours" if l["expected_action"] == "SUGGEST" else "already right (open)") for l in sel)
        oc = C.Counter(ER.outcome("SUGGEST", "closed", l)[0] for l in sel); pts = sum(ER.outcome("SUGGEST", "closed", l)[1] for l in sel)
        print(f"  {name:<12} rows {len(sel):>4} | truth: {dict(truth)} | suggest 'closed': exact {oc['exact']}, wrong {oc['wrong_state']} -> {100*pts/need:+.2f} score")
        if name == "EARLY_CLOSE":
            pts2, oc2 = 0.0, C.Counter()
            for l in sel:
                c = close_at.get((l["entity_id"], l["day_key"])); sh = l["displayed_hours_at_snapshot"]
                if not c or "," in sh or sh in ("closed", "00:00-23:59"): continue
                h = f"{sh[:5]}-{c}"
                o, p, _ = ER.outcome("SUGGEST", h, l); oc2[o] += 1; pts2 += p
            print(f"  {'':<12} instead suggest '<shown opening>-<time in review>' where the review gives a closing time: {dict(oc2)} -> {100*pts2/need:+.2f} score")
    mixed = [l for l in quiet if len(kind[(l["entity_id"], l["day_key"])]) > 1]
    print(f"  mixed signals: {len(mixed)} rows")
