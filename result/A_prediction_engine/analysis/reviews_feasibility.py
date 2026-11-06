"""Reviews feasibility, steps 1-4: can customer reviews recover the rows the frozen engine still misses?
Shared helpers (classify, aliases, cutoff) are imported by reviews_filters.py and reviews_split.py.
Prerequisites (outputs/ is not committed), from the repo root:
    python result/A_prediction_engine/analysis/error_report.py --season 2026 --predictions predictions_2026.csv --rows outputs/report/rows_final_2026.csv
    python result/A_prediction_engine/model.py --season 2025 --out outputs/ours_2025.csv
    python result/A_prediction_engine/analysis/error_report.py --season 2025 --predictions outputs/ours_2025.csv --rows outputs/report/rows_final_2025.csv
Then:  python result/A_prediction_engine/analysis/reviews_feasibility.py
ANALYSIS ONLY: reads labels/ (through the error-report rows); never imported by model.py. Results: EXPERIMENTS.md, "Reviews feasibility".
"""
import csv, json, re, collections as C
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from datetime import date, datetime, timezone, timedelta
import error_report as ER                     # outcome() = evaluate.py's scoring, cross-checked

# Holiday aliases, lower-case stems (handle fi inflection). Ordered: longer / more specific first.
ALIASES = [
 ("DEC23", ["lille julaften", "lillejulafton", "aatonaat", "day before christmas eve"]),
 ("EPIPHANY_EVE", ["loppiaisaat", "trettondagsafton", "epiphany eve"]),
 ("XMAS_EVE", ["jouluaat", "julafton", "julaften", "christmas eve"]),
 ("BOXING_DAY", ["tapaninpäiv", "annandag jul", "andre juledag", "2. juledag", "boxing day"]),
 ("XMAS_DAY", ["joulupäiv", "juldag", "første juledag", "1. juledag", "christmas day"]),
 ("NYE", ["uudenvuodenaat", "nyårsafton", "nyttårsaften", "new year's eve", "new years eve"]),
 ("NEW_YEARS_DAY", ["uudenvuodenpäiv", "nyårsdag", "nyttårsdag", "new year's day", "new years day"]),
 ("EPIPHANY", ["loppiai", "trettondedag", "trettondag jul", "epiphany"]),
 ("INDEPENDENCE_DAY", ["itsenäisyyspäiv", "självständighetsdag", "independence day"]),
 ("LUCIA", ["lucia"]),
 ("FATHERS_DAY", ["isänpäiv", "fars dag", "farsdag", "father's day", "fathers day"]),
 ("BLACK_FRIDAY", ["black friday"]),
 ("INTERDAY", ["välipäiv", "mellandag", "romjul", "between christmas and new year"]),
 # non-target holidays (counted as holiday mentions only)
 ("EASTER_MONDAY", ["toisena pääsiäispäiv", "2. pääsiäispäiv", "annandag påsk", "andre påskedag", "easter monday"]),
 ("EASTER_SATURDAY", ["pääsiäislauant", "påskafton", "påskeaften", "easter saturday"]),
 ("EASTER_SUNDAY", ["pääsiäispäiv", "påskdag", "første påskedag", "easter sunday"]),
 ("GOOD_FRIDAY", ["pitkäperjant", "pitkänäperjant", "långfredag", "langfredag", "good friday"]),
 ("MAUNDY_THURSDAY", ["kiirastorst", "skärtorsdag", "skjærtorsdag", "maundy"]),
 ("MAY_EVE", ["vappuaat", "valborg", "may day eve"]),
 ("MAY_DAY", ["vappu", "första maj", "1. mai", "arbeidernes dag", "may day"]),
 ("ASCENSION", ["helatorst", "himmelsfärd", "himmelfart", "ascension"]),
 ("MIDSUMMER_EVE", ["juhannusaat", "midsommarafton", "sankthans", "midsummer eve"]),
 ("MIDSUMMER_DAY", ["juhannuspäiv", "midsommardag", "midsummer day"]),
 ("MOTHERS_DAY", ["äitienpäiv", "mors dag", "morsdag", "mother's day"]),
 ("NATIONAL_DAY", ["nationaldag", "17. mai", "grunnlovsdag", "national day"]),
 ("ALL_SAINTS", ["pyhäinpäiv", "alla helgons", "all saints"]),
 ("PENTECOST", ["helluntai", "pingst", "pinse", "pentecost", "whit"]),
]
CLOSED = re.compile(r"kiinni|suljet|ei ollut|stängt|stängd|stengt|closed|wasn.t open|was not open", re.I)
HOURS = re.compile(r"aukiolo|\bauki\b|öppettid|öppet|åpningstid|åpent|\båpen\b|opening hours|\bhours\b|\bopen\b", re.I)
FOR_GOOD = re.compile(r"för gott|lopettan|pysyvästi|closed down|for good|lagt ned|stengt for godt|permanent", re.I)
SPECIFIC_HOURS = re.compile(r"\b\d{1,2}[:.]\d{2}\b|\b(?:klo|kl\.?|at)\s?\d{1,2}\b|\b\d{1,2}\s?[–-]\s?\d{1,2}\b")
GENERIC_HOLIDAY = re.compile(r"on the holiday|pyhien|pyhäpäiv|helgdag|helgtid|helligdag|röda dag", re.I)
TARGET_KEYS = {"DEC23","EPIPHANY_EVE","XMAS_EVE","BOXING_DAY","XMAS_DAY","NYE","NEW_YEARS_DAY","EPIPHANY",
               "INDEPENDENCE_DAY","LUCIA","FATHERS_DAY","BLACK_FRIDAY","INTERDAY"}

def holidays_in(text):
    t, found = text.lower(), []
    for key, stems in ALIASES:
        for s in stems:
            if s in t:
                found.append(key); t = t.replace(s, " ")   # consume so shorter aliases cannot re-match
                break
    return found

def cutoff_ms(season):  # snapshot as midnight UTC; the ±3 h around it does not matter here
    return int(datetime(season, 11, 6, tzinfo=timezone.utc).timestamp() * 1000)

reviews = json.load(open(f"{ROOT}/data/reviews.json", encoding="utf-8"))["response"]["reviews"]
cal = [r for r in csv.DictReader(open(f"{ROOT}/data/calendar_special_days.csv", encoding="utf-8"))]
cal_by_country = C.defaultdict(list)
for r in cal: cal_by_country[r["country"]].append((date.fromisoformat(r["date"]), r["day_key"]))
ents = {e["meta"]["id"]: e for e in json.load(open(f"{ROOT}/data/entities.json", encoding="utf-8"))["response"]["entities"]}

def classify(r):
    txt = r["content"] or ""
    if not txt: return None
    hol = holidays_in(txt)
    c = bool(CLOSED.search(txt)) and not FOR_GOOD.search(txt)
    h = bool(HOURS.search(txt))
    g = bool(GENERIC_HOLIDAY.search(txt)) and not hol
    if not (hol or ((c or h) and not FOR_GOOD.search(txt))): return None
    if not hol and not g and not c: return None     # "hours changed" etc. without a closure or a holiday: not holiday info
    return {"loc": r["locationId"], "ms": r["publisherDate"], "hol": hol, "closed": c, "generic": g,
            "specific_hours": bool(SPECIFIC_HOURS.search(txt)), "text": txt}

def inferred_key(rv):  # generic "on the holiday": nearest special day 0–7 days before the review
    d = datetime.fromtimestamp(rv["ms"] / 1000, tz=timezone.utc).date()
    cc = ents[rv["loc"]]["meta"]["countryCode"]
    best = [(d - x, k) for x, k in cal_by_country[cc] if timedelta(0) <= d - x <= timedelta(days=7)]
    return min(best)[1] if best else None

def main():
  for season in (2026, 2025):
      cut = cutoff_ms(season)
      pre = [x for x in (classify(r) for r in reviews if r["publisherDate"] < cut) if x]
      named = [x for x in pre if x["hol"]]
      rows = list(csv.DictReader(open(f"{ROOT}/outputs/report/rows_final_{season}.csv", encoding="utf-8")))
      labels = {(r["entity_id"], r["date"]): r for r in csv.DictReader(open(ER.LABELS[season], encoding="utf-8"))}
      missed = [r for r in rows if r["outcome"] in ("missed", "missed_closed_business")]
      missed_biz = {r["entity_id"] for r in missed}
      missed_keys = C.defaultdict(set)
      for r in missed: missed_keys[r["entity_id"]].add(r["day_key"])
      on_missed = [x for x in pre if x["loc"] in missed_biz]
      same_key = [x for x in on_missed if set(x["hol"]) & missed_keys[x["loc"]]]
      print(f"\n######## season {season} (reviews before {season}-11-06)")
      print(f"1-2. holiday/hours reviews: {len(pre)} on {len({x['loc'] for x in pre})} businesses "
            f"(naming a holiday: {len(named)}; generic 'on the holiday': {sum(x['generic'] for x in pre)}; with a closure word: {sum(x['closed'] for x in pre)})")
      print(f"     of all 3,032 businesses; dev businesses with a missed row: {len(missed_biz)}; "
            f"reviews on those businesses: {len(on_missed)} on {len({x['loc'] for x in on_missed})} businesses")
      print(f"3.   reviews naming the day_key of one of that business's missed rows: {len(same_key)} "
            f"on {len({x['loc'] for x in same_key})} businesses; naming specific hours: {sum(x['specific_hours'] for x in on_missed)} of {len(on_missed)}")
      tgt = C.Counter(k for x in named for k in x["hol"])
      print("     holidays named (target day_keys):", {k: n for k, n in tgt.most_common() if k in TARGET_KEYS})
      # 4. Rule: suggest "closed" for (business, day_key) when a pre-snapshot review names that day_key with a closure word.
      for variant in ("named", "named+generic"):
          sig = C.defaultdict(int)
          for x in pre:
              if not x["closed"]: continue
              keys = set(x["hol"])
              if variant == "named+generic" and x["generic"]:
                  k = inferred_key(x)
                  if k: keys.add(k)
              for k in keys: sig[(x["loc"], k)] += 1
          touched = [l for l in labels.values() if (l["entity_id"], l["day_key"]) in sig]
          truth_closed = sum(l["truth_hours"] == "closed" for l in touched)
          rowmap = {(r["entity_id"], r["date"]): r for r in rows}
          delta = fixed = broke = 0.0
          out_new = C.Counter()
          for l in touched:
              cur = rowmap[(l["entity_id"], l["date"])]
              if cur["action"] != "NO_ACTION": continue            # only fill rows where the engine stays quiet
              if l["displayed_hours_at_snapshot"] == "closed": continue   # suggesting "closed" again = no message
              o, p, _ = ER.outcome("SUGGEST", "closed", l)
              out_new[o] += 1; delta += p - float(cur["points"])
          need = sum(1 for l in labels.values() if l["expected_action"] in ("SUGGEST", "FLAG"))
          n_t = len(touched)
          print(f"4.   [{variant}] (business, day_key) signals: {len(sig)}; dev rows touched: {n_t}; truth closed {truth_closed} "
                f"({100*truth_closed/max(1,n_t):.0f}%), truth open {n_t-truth_closed} ({100*(n_t-truth_closed)/max(1,n_t):.0f}% = wrong state if suggested)")
          print(f"        on rows where the engine is quiet now: {dict(out_new)} -> {delta:+.1f} points = {100*delta/need:+.2f} score")


if __name__ == "__main__":
    main()
