#!/usr/bin/env python3
"""Part A prediction engine. Started as a copy of examples/baseline.py
('copy last year → shopping centre → peers'). Standard library only.

    python result/A_prediction_engine/model.py --season 2026   # writes outputs/ours_2026.csv
    python result/A_prediction_engine/model.py --season 2025   # back-test, writes outputs/ours_2025.csv

Then score it:
    python evaluation/evaluate.py --predictions outputs/ours_2026.csv
    python evaluation/evaluate.py --predictions outputs/ours_2025.csv --labels labels/dev_labels_2025_backtest.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import date, datetime

# result/A_prediction_engine/model.py → repo root is three levels up
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = lambda *p: os.path.join(ROOT, "data", *p)  # noqa: E731
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SNAP = {2026: date(2026, 11, 6), 2025: date(2025, 11, 6)}
PERM_WORDS = ("lopettanut", "pysyvästi", "stängt för gott", "permanent", "lagt ned", "stengt for godt", "closed down")


def day_str(obj):
    if not obj or obj.get("isClosed"):
        return "closed"
    return ",".join(f"{i['start']}-{i['end']}" for i in obj.get("openIntervals", [])) or "closed"


def cycle(d):
    return d.year if d.month >= 2 else d.year - 1


def load():
    ents = {e["meta"]["id"]: e for e in json.load(open(D("entities.json"), encoding="utf-8"))["response"]["entities"]}
    hol = defaultdict(list)
    for line in open(D("holiday_hours_history.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        hol[(r["entity_id"], r["date"])].append(r)
    reg = defaultdict(list)
    for line in open(D("regular_hours_history.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        reg[r["entity_id"]].append(r)
    cal = list(csv.DictReader(open(D("calendar_special_days.csv"), encoding="utf-8")))
    bench = {(r["country"], r["city_tier"], r["segment"], r["day_key"]): r
             for r in csv.DictReader(open(D("peer_benchmarks.csv"), encoding="utf-8"))}
    tiers = {r["city"]: r["city_tier"] for r in csv.DictReader(open(D("cities.csv"), encoding="utf-8"))}
    reviews = json.load(open(D("reviews.json"), encoding="utf-8"))["response"]["reviews"]
    sugg = json.load(open(D("publisher_suggestions.json"), encoding="utf-8"))["response"]["suggestions"]
    return ents, hol, reg, cal, bench, tiers, reviews, sugg


class Baseline:
    def __init__(self, season):
        self.season, self.snap = season, SNAP[season]
        (self.ents, self.hol, self.reg, self.cal, self.bench, self.tiers, reviews, sugg) = load()
        cutoff = datetime(self.snap.year, self.snap.month, self.snap.day).timestamp() * 1000
        self.closed_signal = set()
        for r in reviews:
            if r["publisherDate"] < cutoff and r["publisherDate"] > cutoff - 150 * 86400000 and \
                    any(w in r["content"].lower() for w in PERM_WORDS):
                self.closed_signal.add(r["locationId"])
        for s in sugg:
            if s["fieldName"] == "closed" and s["dateCreated"] < self.snap.isoformat():
                self.closed_signal.add(s["locationId"])
        self.dates_by_key = defaultdict(list)
        for r in self.cal:
            self.dates_by_key[(r["country"], r["day_key"])].append(date.fromisoformat(r["date"]))

    def regular(self, eid, d: date):
        """Published regular hours as of the snapshot (handles seasonal closures)."""
        cands = [r for r in self.reg[eid] if r["effective_from"] == "before-2024" or
                 r["effective_from"] < self.snap.isoformat()]
        best = max(cands, key=lambda r: "0000" if r["effective_from"] == "before-2024" else r["effective_from"])
        return day_str(best["hours"][DAYS[d.weekday()]])

    def entry(self, eid, d: date, as_of: date):
        rows = [r for r in self.hol.get((eid, d.isoformat()), []) if r["entered_at"] < as_of.isoformat()]
        if not rows:
            return None
        h = max(rows, key=lambda r: r["entered_at"])["holidayHours"]
        return "REGULAR" if h.get("isRegularHours") else day_str(h)

    def displayed(self, eid, d):
        e = self.entry(eid, d, self.snap)
        if e is None or e == "REGULAR":
            return self.regular(eid, d)
        return e

    def explain(self, eid, d: date, key: str):
        """Return (action, hours, basis, evidence). basis: LAST_YEAR | SHOPPING_CENTRE | PEERS | CLOSED_SIGNALS | None"""
        ent = self.ents[eid]
        if eid in self.closed_signal and not ent.get("closed"):
            return "FLAG", "", "CLOSED_SIGNALS", "reviews or Google edits say the business has closed for good"
        shown = self.displayed(eid, d)
        cand, basis, ev = None, None, None
        mall = ent.get("c_shoppingCenterEntityId")
        if mall:
            m = self.entry(mall, d, self.snap)
            if m and m != "REGULAR":
                cand, basis, ev = m, "SHOPPING_CENTRE", self.ents[mall]["name"]
        if cand is None:
            prev = [x for x in self.dates_by_key[(ent["meta"]["countryCode"], key)] if cycle(x) == cycle(d) - 1]
            for p in prev:
                last = self.entry(eid, p, self.snap)
                if last is not None:
                    cand = self.regular(eid, d) if last == "REGULAR" else last
                    basis, ev = "LAST_YEAR", (p.isoformat(), last)
        if cand is None:  # hypothesis #2: same day_key two seasons ago
            cand, basis, ev = self._two_seasons_ago(eid, d, key)
        if cand is None:
            b = self.bench.get((ent["meta"]["countryCode"], self.tiers[ent["address"]["city"]], ent["c_segment"], key))
            if b and b["closed_share_among_entered"] and float(b["closed_share_among_entered"]) >= 0.7 and \
                    float(b["share_entered_closed"]) >= 0.15 and shown != "closed":
                cand, basis, ev = "closed", "PEERS", float(b["closed_share_among_entered"])
        if cand and cand != shown:
            return "SUGGEST", cand, basis, ev
        return "NO_ACTION", "", basis, ev

    _older_idx = None  # (entity_id, history day_key) -> dates with an entry before the snapshot; built on first use

    def _two_seasons_ago(self, eid, d: date, key: str):
        """(cand, "TWO_YEARS_AGO", (date, entry)) from the business's own entry for this day_key two seasons back,
        or (None, None, None). Seasons are matched through the history's own day_key, not the calendar: the calendar
        starts 2024-01-01, so it cannot reach the Dec 2023 entries that "two seasons back" means for the 2025
        back-test. Only entries made before the snapshot count."""
        if self._older_idx is None:
            snap, idx = self.snap.isoformat(), defaultdict(list)
            for (e, ds), rows in self.hol.items():
                if any(r["entered_at"] < snap for r in rows):
                    idx[(e, rows[0]["day_key"])].append(date.fromisoformat(ds))
            self._older_idx = idx
        old = sorted(x for x in self._older_idx.get((eid, key), ()) if cycle(x) <= cycle(d) - 2)
        if not old:
            return None, None, None
        p = old[-1]  # newest season two or more back; latest date in it
        e = self.entry(eid, p, self.snap)
        basis, ev = ("TWO_YEARS_AGO" if cycle(p) == cycle(d) - 2 else "OLDER_SEASON"), (p.isoformat(), e)
        if e == "REGULAR":
            return None, None, None  # "regular hours" two or more seasons ago: too weak to overrule the next blocks
        if e == "closed":
            return e, basis, ev
        reg_then, reg_now = self._regular_on(eid, p), self.regular(eid, d)
        if reg_now == "closed" and reg_then not in (None, "closed"):
            return None, None, None  # opened on a weekday it normally opened; d falls on a regular day off
        return self._align_to_regular(e, reg_then, reg_now), basis, ev

    def _regular_on(self, eid, p: date):
        """Published regular hours in force on the (past) date p for its weekday, or None if none was published."""
        then = [r for r in self.reg[eid] if r["effective_from"] == "before-2024" or r["effective_from"] <= p.isoformat()]
        if not then:
            return None
        best = max(then, key=lambda r: "0000" if r["effective_from"] == "before-2024" else r["effective_from"])
        return day_str(best["hours"][DAYS[p.weekday()]])

    @staticmethod
    def _align_to_regular(e, reg_then, reg_now):
        """An old special day that opened as usual and closed early ("open as usual, close at 15:00") opens at the
        regular opening of d and keeps the closing time as entered. (A day that kept only the regular closing is a
        fixed-hours day such as 12:00-18:00 and is copied as is.)"""
        if "," in e or reg_then in (None, "closed") or reg_now == "closed":
            return e
        o, c = e.split("-")
        if o == reg_then[:5] and c != reg_then[-5:] and reg_now[:5] < c:
            return f"{reg_now[:5]}-{c}"
        return e

    def predict(self, eid, d: date, key: str):
        a, h, _, _ = self.explain(eid, d, key)
        return a, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026, choices=[2025, 2026])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    bl = Baseline(a.season)
    tf = os.path.join(ROOT, "evaluation", "targets_2026.csv" if a.season == 2026 else "targets_2025_backtest.csv")
    out = a.out or os.path.join(ROOT, "outputs", f"ours_{a.season}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = 0
    with open(tf, encoding="utf-8") as f, open(out, "w", newline="", encoding="utf-8") as g:
        w = csv.writer(g)
        w.writerow(["entity_id", "date", "action", "hours", "confidence"])
        for r in csv.DictReader(f):
            act, h = bl.predict(r["entity_id"], date.fromisoformat(r["date"]), r["day_key"])
            if act != "NO_ACTION":
                w.writerow([r["entity_id"], r["date"], act, h, 0.6])
                n += 1
    print(f"wrote {n} actions -> {out}")


if __name__ == "__main__":
    main()
