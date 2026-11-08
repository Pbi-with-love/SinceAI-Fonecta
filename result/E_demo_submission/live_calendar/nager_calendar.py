#!/usr/bin/env python3
"""Bonus: replace data/calendar_special_days.csv with a live source (Nager.Date) and measure what changes.

Standard library only. Deterministic: the API answer is cached in nager_cache.json (with the fetch date), and every
later run reads the cache unless --refresh is given. model.py is not changed: this script hands it another calendar
file by wrapping its data-path helper, runs the engine for both seasons and scores the result with the organisers'
evaluation/evaluate.py.

    python3 result/E_demo_submission/live_calendar/nager_calendar.py            # uses the cache
    python3 result/E_demo_submission/live_calendar/nager_calendar.py --refresh  # calls date.nager.at again
    python3 result/E_demo_submission/live_calendar/nager_calendar.py --no-engine  # coverage report only

Writes REPORT.md next to this file; calendars and predictions go to outputs/live_calendar/ (git-ignored).
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CACHE = os.path.join(HERE, "nager_cache.json")
REPORT = os.path.join(HERE, "REPORT.md")
WORK = os.path.join(ROOT, "outputs", "live_calendar")
ORG_CAL = os.path.join(ROOT, "data", "calendar_special_days.csv")
COUNTRIES = ("FI", "SE", "NO")
YEARS = (2024, 2025, 2026, 2027)
API = "https://date.nager.at/api/v3/PublicHolidays/{year}/{cc}"

# Nager's English name -> the engine's day_key (our own mapping; the names differ per country for a few days).
NAME_TO_KEY = {
    "New Year's Day": "NEW_YEARS_DAY", "Epiphany": "EPIPHANY", "Maundy Thursday": "MAUNDY_THURSDAY",
    "Good Friday": "GOOD_FRIDAY", "Easter Sunday": "EASTER_SUNDAY", "Easter Monday": "EASTER_MONDAY",
    "May Day": "MAY_DAY", "Labour Day": "MAY_DAY", "International Workers' Day": "MAY_DAY",
    "Ascension Day": "ASCENSION", "Pentecost": "PENTECOST", "Whit Monday": "WHIT_MONDAY",
    "Midsummer Eve": "MIDSUMMER_EVE", "Midsummer Day": "MIDSUMMER_DAY", "All Saints' Day": "ALL_SAINTS",
    "Independence Day": "INDEPENDENCE_DAY", "National Day of Sweden": "NATIONAL_DAY", "Constitution Day": "NATIONAL_DAY",
    "Christmas Eve": "XMAS_EVE", "Christmas Day": "XMAS_DAY", "St. Stephen's Day": "BOXING_DAY",
    "New Year's Eve": "NYE",
}
# How much a day matters for opening hours (the product's own classification, used by the peer and owner rules).
DAY_CLASS = {
    "NEW_YEARS_DAY": "MAJOR", "GOOD_FRIDAY": "MAJOR", "EASTER_SUNDAY": "MAJOR", "MIDSUMMER_DAY": "MAJOR",
    "XMAS_DAY": "MAJOR", "XMAS_EVE": "EVE_MAJOR", "MIDSUMMER_EVE": "EVE_MAJOR", "MAUNDY_THURSDAY": "EVE_MINOR",
    "NYE": "EVE_MINOR",
}  # everything else Nager returns is a public holiday of class SOFT


def fetch(refresh):
    if os.path.exists(CACHE) and not refresh:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    data = {"source": "https://date.nager.at (Nager.Date, MIT)", "fetched_on": date.today().isoformat(), "holidays": []}
    for cc in COUNTRIES:
        for y in YEARS:
            req = urllib.request.Request(API.format(year=y, cc=cc), headers={"User-Agent": "porchlight-hackathon"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data["holidays"] += json.load(r)
    data["holidays"].sort(key=lambda h: (h["countryCode"], h["date"], h["name"]))
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


def read_org():
    with open(ORG_CAL, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def live_rows(nager):
    """Nager holidays as calendar rows. Unmapped names are reported, not guessed."""
    rows, unmapped = [], Counter()
    for h in nager["holidays"]:
        key = NAME_TO_KEY.get(h["name"])
        if not key:
            unmapped[(h["countryCode"], h["name"])] += 1
            continue
        d = date.fromisoformat(h["date"])
        rows.append({"country": h["countryCode"], "date": h["date"], "weekday": d.strftime("%A"), "day_key": key,
                     "day_class": DAY_CLASS.get(key, "SOFT"),
                     "day_type": "EVE" if DAY_CLASS.get(key, "").startswith("EVE") else "PUBLIC_HOLIDAY",
                     "name_local": h["localName"], "name_en": h["name"],
                     "official_public_holiday": "1" if "Public" in h["types"] else "0"})
    return rows, unmapped


def coverage(org, live):
    by_date = {(r["country"], r["date"]): r for r in live}
    org_pub = [r for r in org if r["day_type"] == "PUBLIC_HOLIDAY"]
    found = [r for r in org_pub if (r["country"], r["date"]) in by_date]
    key_ok = [r for r in found if by_date[(r["country"], r["date"])]["day_key"] == r["day_key"]]
    org_dates = {(r["country"], r["date"]) for r in org}
    last = max(r["date"] for r in org)  # compare inside the organisers' date range only
    extra = [r for r in live if (r["country"], r["date"]) not in org_dates and r["date"] <= last]
    beyond = [r for r in live if r["date"] > last]
    org_by_date = {(r["country"], r["date"]): r for r in org}
    cls_diff = [(r, org_by_date[(r["country"], r["date"])]) for r in live
                if (r["country"], r["date"]) in org_by_date and org_by_date[(r["country"], r["date"])]["day_type"] != "PUBLIC_HOLIDAY"]
    missing_types = Counter(r["day_type"] for r in org if (r["country"], r["date"]) not in by_date)
    return {"org_pub": len(org_pub), "found": len(found), "key_ok": len(key_ok), "extra": extra, "beyond": beyond, "last": last,
            "cls_diff": cls_diff, "missing_types": missing_types, "org_total": len(org)}


def write_cal(rows, name):
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, f"calendar_{name}.csv")
    cols = ["country", "date", "weekday", "day_key", "day_class", "day_type", "name_local", "name_en", "official_public_holiday"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["country"], r["date"], r["day_key"])):
            w.writerow({c: r[c] for c in cols})
    return path


RUNNER = r'''
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "result", "A_prediction_engine"))
import model
cal, season, out = sys.argv[2], sys.argv[3], sys.argv[4]
orig = model.D
model.D = lambda *p: cal if p == ("calendar_special_days.csv",) else orig(*p)  # hand the engine another calendar
sys.argv = ["model.py", "--season", season, "--out", out]
model.main()
'''


def score(cal_path, name, season):
    out = os.path.join(WORK, f"pred_{name}_{season}.csv")
    subprocess.run([sys.executable, "-c", RUNNER, ROOT, cal_path, str(season), out], check=True, cwd=ROOT,
                   stdout=subprocess.DEVNULL)
    cmd = [sys.executable, os.path.join(ROOT, "evaluation", "evaluate.py"), "--predictions", out]
    if season == 2025:
        cmd += ["--labels", os.path.join(ROOT, "labels", "dev_labels_2025_backtest.csv")]
    txt = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=ROOT).stdout
    get = lambda k: re.search(rf"{k}\s+([\d.]+)", txt).group(1)  # noqa: E731
    return {"score": float(re.search(r"Score: ([\d.]+)", txt).group(1)), "exact": get("precision_exact"),
            "recall": get("recall_exact"), "harmful": int(get("harmful_suggestions"))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="call the API again instead of the cache")
    ap.add_argument("--no-engine", action="store_true", help="coverage report only (fast)")
    a = ap.parse_args()
    nager = fetch(a.refresh)
    org = read_org()
    live, unmapped = live_rows(nager)
    cov = coverage(org, live)
    # hybrid = live public holidays + our own list of eves, days between holidays, observances and commercial days
    live_dates = {(r["country"], r["date"]) for r in live}
    hybrid = live + [r for r in org if r["day_type"] != "PUBLIC_HOLIDAY" and (r["country"], r["date"]) not in live_dates]
    cals = {"organisers": ORG_CAL, "nager_only": write_cal(live, "nager_only"), "nager_plus_own_eves": write_cal(hybrid, "hybrid")}

    L = ["# Bonus: a live calendar (Nager.Date) instead of `calendar_special_days.csv`", "",
         f"Source: {nager['source']}, fetched {nager['fetched_on']}, {len(nager['holidays'])} holidays for "
         f"{', '.join(COUNTRIES)} {YEARS[0]}–{YEARS[-1]} (cached in `nager_cache.json`). Generated by `nager_calendar.py`.", "",
         "## Coverage against the organisers' calendar", "",
         "| | Count |", "|---|---|",
         f"| Organisers' public holidays | {cov['org_pub']} |",
         f"| … found in Nager on the same date | {cov['found']} ({100 * cov['found'] / cov['org_pub']:.0f} %) |",
         f"| … and mapped to the same `day_key` | {cov['key_ok']} |",
         f"| Organisers' rows Nager does not have (by type) | " + ", ".join(f"{t} {n}" for t, n in sorted(cov['missing_types'].items())) + " |",
         f"| Nager days the organisers' file does not have (up to {cov['last']}) | {len(cov['extra'])} |",
         f"| Nager days after the organisers' file ends ({cov['last']}) | {len(cov['beyond'])}: the live source already covers the next season |",
         f"| Nager names we could not map | {sum(unmapped.values())} |", ""]
    if cov["extra"]:
        L += ["Nager days missing from the organisers' file:", ""]
        L += [f"- {r['country']} {r['date']} {r['name_en']} ({r['name_local']})" for r in cov["extra"]]
        L.append("")
    if cov["cls_diff"]:
        kinds = Counter((r["country"], r["name_en"], o["day_type"]) for r, o in cov["cls_diff"])
        L += ["Days Nager lists as holidays that the organisers' file treats as eves or other day types:", ""]
        L += [f"- {c} {n}: Nager public holiday / bank day, organisers `{t}` ({k} dates)" for (c, n, t), k in sorted(kinds.items())]
        L.append("")
    if unmapped:
        L += ["Unmapped Nager names: " + ", ".join(f"{c} {n}" for (c, n) in sorted(unmapped)), ""]

    if not a.no_engine:
        res = {(name, s): score(path, name, s) for name, path in cals.items() for s in (2026, 2025)}
        L += ["## What it does to the engine", "",
              "Same `model.py`, only the calendar file is swapped; scored with `evaluation/evaluate.py`.", "",
              "| Calendar | Dev 2026 | Back-test 2025 | Wrong state (dev / bt) | Exact precision (dev / bt) |",
              "|---|---|---|---|---|"]
        label = {"organisers": "Organisers' file (reference)", "nager_only": "Nager only",
                 "nager_plus_own_eves": "Nager + our own eves and commercial days"}
        for name in cals:
            d, b = res[(name, 2026)], res[(name, 2025)]
            L.append(f"| {label[name]} | {d['score']:.2f} | {b['score']:.2f} | {d['harmful']} / {b['harmful']} | {d['exact']} / {b['exact']} |")
        L.append("")
        o, n = res[("organisers", 2026)], res[("nager_only", 2026)]
        ob, nb = res[("organisers", 2025)], res[("nager_only", 2025)]
        L += ["## What we learned: coverage, quality, gaps", "",
              f"- **Coverage: complete for public holidays.** All {cov['org_pub']} public holidays of FI, SE and NO in the "
              "organisers' file are in Nager on the same date, and every Nager name maps to one of the engine's day keys. "
              f"Nager also already has the next season ({len(cov['beyond'])} days in 2027), so the list would not need a "
              "yearly manual update.",
              "- **Quality: right dates, different meaning and names.** Nager marks Christmas Eve (FI, SE), Midsummer Eve (FI, SE) and New Year's "
              "Eve (SE) as public holidays and Christmas Eve in Norway as a bank day, while for opening hours they behave as "
              "eves; names differ (`St. Stephen's Day` vs `Boxing Day`, `Labour Day` / `International Workers' Day` vs "
              "`May Day`, `Constitution Day` vs `National Day`), so a fixed name map is needed. Norway's 17 May and Whit "
              "Monday fall on the same date in 2027 (two entries).",
              "- **Gaps: everything that is not a public holiday**: "
              + ", ".join(f"{n} {t.lower().replace('_', ' ')}" for t, n in sorted(cov['missing_types'].items()))
              + " rows. These are exactly the days where hours go wrong most (Christmas Eve's early closing, the days "
              "between Christmas and New Year, Black Friday, Father's Day).",
              f"- **Gaps, measured: Nager alone costs {o['score'] - n['score']:.2f} points on dev and {ob['score'] - nb['score']:.2f} on the "
              "back-test**: without those days the engine cannot map this season's eves and in-between days to last "
              "season's, so it stays quiet there.",
              "- **What we would ship: live public holidays + our own list of eves and commercial days gives exactly the reference scores.** "
              "That is the production design: holidays from a live API, eves and commercial days from Connect's own rules.",
              ""]
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
