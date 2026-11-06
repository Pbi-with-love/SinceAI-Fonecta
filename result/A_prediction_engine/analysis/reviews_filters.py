"""Reviews feasibility, step 4 filters: can a cheap filter (timing, recency, count, peers) make the review rule pay?
Prerequisites (outputs/ is not committed), from the repo root:
    python result/A_prediction_engine/analysis/error_report.py --season 2026 --predictions predictions_2026.csv --rows outputs/report/rows_final_2026.csv
    python result/A_prediction_engine/model.py --season 2025 --out outputs/ours_2025.csv
    python result/A_prediction_engine/analysis/error_report.py --season 2025 --predictions outputs/ours_2025.csv --rows outputs/report/rows_final_2025.csv
Then:  python result/A_prediction_engine/analysis/reviews_filters.py
ANALYSIS ONLY: reads labels/ (through the error-report rows); never imported by model.py. Results: EXPERIMENTS.md, "Reviews feasibility".
"""
import csv, json, collections as C
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from datetime import date, datetime, timezone, timedelta
from reviews_feasibility import classify, reviews, cutoff_ms, cal, ER, SPECIFIC_HOURS
dates_by = C.defaultdict(list)
for r in cal: dates_by[(r["country"], r["day_key"])].append(date.fromisoformat(r["date"]))
ents = {e["meta"]["id"]: e for e in json.load(open(f"{ROOT}/data/entities.json", encoding="utf-8"))["response"]["entities"]}
tiers = {r["city"]: r["city_tier"] for r in csv.DictReader(open(f"{ROOT}/data/cities.csv", encoding="utf-8"))}
bench = {(r["country"], r["city_tier"], r["segment"], r["day_key"]): r for r in csv.DictReader(open(f"{ROOT}/data/peer_benchmarks.csv", encoding="utf-8"))}
def cyc(d): return d.year if d.month >= 2 else d.year - 1
print("--- sample of reviews the regex says name specific hours (season 2026 cutoff):")
pre26 = [x for x in (classify(r) for r in reviews if r["publisherDate"] < cutoff_ms(2026)) if x]
for t, n in C.Counter(x["text"] for x in pre26 if x["specific_hours"]).most_common(6): print(f"  {n:>3}  {t[:110]}")
print("  specific-hours reviews that also name a target holiday:", sum(1 for x in pre26 if x["specific_hours"] and x["hol"]))
for season in (2026, 2025):
    cut = cutoff_ms(season)
    pre = [x for x in (classify(r) for r in reviews if r["publisherDate"] < cut) if x and x["closed"] and x["hol"]]
    sig = C.defaultdict(list)
    for x in pre:
        rd = datetime.fromtimestamp(x["ms"] / 1000, tz=timezone.utc).date()
        cc = ents[x["loc"]]["meta"]["countryCode"]
        for k in set(x["hol"]):
            occ = [d for d in dates_by[(cc, k)] if timedelta(0) <= rd - d <= timedelta(days=10)]
            sig[(x["loc"], k)].append({"timely": bool(occ), "season": cyc(occ[0]) if occ else None, "rd": rd})
    rows = {(r["entity_id"], r["date"]): r for r in csv.DictReader(open(f"{ROOT}/outputs/report/rows_final_{season}.csv", encoding="utf-8"))}
    labels = list(csv.DictReader(open(ER.LABELS[season], encoding="utf-8")))
    quiet = [l for l in labels if (l["entity_id"], l["day_key"]) in sig and rows[(l["entity_id"], l["date"])]["action"] == "NO_ACTION"
             and l["displayed_hours_at_snapshot"] != "closed"]
    def peer(l):
        e = ents[l["entity_id"]]; b = bench.get((e["meta"]["countryCode"], tiers[e["address"]["city"]], e["c_segment"], l["day_key"]))
        return float(b["closed_share_among_entered"]) if b and b["closed_share_among_entered"] else 0.0
    filters = {
        "all (as step 4)": lambda s, l: True,
        "posted 0-10 days after that holiday": lambda s, l: any(v["timely"] for v in s),
        "timely and from last season": lambda s, l: any(v["timely"] and v["season"] == cyc(date.fromisoformat(l["date"])) - 1 for v in s),
        ">= 2 reviews": lambda s, l: len(s) >= 2,
        "peer closed share >= 0.5": lambda s, l: peer(l) >= 0.5,
        "timely and peer >= 0.5": lambda s, l: any(v["timely"] for v in s) and peer(l) >= 0.5,
    }
    need = sum(1 for l in labels if l["expected_action"] in ("SUGGEST", "FLAG"))
    print(f"\n######## season {season}: rows where the engine is quiet, shown open, and a closure review names the day_key: {len(quiet)}")
    for name, f in filters.items():
        sel = [l for l in quiet if f(sig[(l["entity_id"], l["day_key"])], l)]
        oc = C.Counter(ER.outcome("SUGGEST", "closed", l)[0] for l in sel)
        pts = sum(ER.outcome("SUGGEST", "closed", l)[1] for l in sel)
        print(f"  {name:<38} rows {len(sel):>4}  exact {oc['exact']:>3}  wrong state {oc['wrong_state']:>3}  "
              f"-> {pts:+6.1f} pts = {100*pts/need:+.2f} score")
