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


def _hours_text(h):
    """'closed' / '09:00-17:00' / '10:00-14:00,17:00-22:00' / '00:00-23:59' → words for a customer message."""
    if h in (None, "", "closed"):
        return "closed"
    if h == "REGULAR":
        return "its regular hours"
    if h == "00:00-23:59":
        return "open 24 hours"
    return "open " + " and ".join(iv.replace("-", "–") for iv in h.split(" (")[0].split(","))


def _nice_date(d):
    return d.strftime("%a %d %b %Y")


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
        if cand is None and not (self.KNN_SOURCE and self.KNN_REPLACES_OWNER):
            op = self._owner_pattern(eid, d, key)
            if op:
                cand, basis, ev = op[0], "OWNER_PATTERN", op[1]
        if cand is None and self.KNN_SOURCE:  # experiment hyp/knn-behavior: businesses with similar holiday habits
            kn = self._knn_candidate(eid, d, key)
            if kn:
                cand, basis, ev = kn[0], "KNN_BEHAVIOR", kn[1]
        if cand is None:
            cand, basis, ev = self._peer_candidate(ent, d, key, shown)
        if cand and cand != shown:
            return "SUGGEST", cand, basis, ev
        return "NO_ACTION", "", basis, ev

    # ---- Part B helper, added after tag part-a-freeze. It only reads explain(); no prediction changes. ----
    # How often each basis was right on the dev labels, both seasons pooled (dev 2026 + back-test 2025), measured with
    # analysis/error_report.py at part-a-freeze and add-one smoothed: (right + 1) / (n + 2). "Right" means exact hours
    # for SUGGEST, a correct flag for FLAG, a correct silence for NO_ACTION. One constant per rule, never per business
    # (AGENTS.md rule 3). Used for ranking and messages only; explain() and the predictions never read it.
    CONFIDENCE = {
        "CLOSED_SIGNALS": 0.92,           # 11 / 11
        "LAST_YEAR": 0.92,                # 3,963 / 4,288
        "SHOPPING_CENTRE": 0.85,          # 700 / 822
        "TWO_YEARS_AGO": 0.84,            # 1,480 / 1,771
        "OLDER_SEASON": 0.70,             # 351 / 500 (dev 2026 only: the back-test has no older season)
        "OWNER_PATTERN": 0.88,            # 587 / 666
        "PEERS": 0.77,                    # 846 / 1,098 (all peer suggestions)
        "PEERS:MEDIUM": 0.93,             # 353 / 379, wrong state 26 (7 %): the peer cell is very sure (see below)
        "PEERS:LOW": 0.69,                # 494 / 719, wrong state 225 (31 %): every other peer suggestion
        "NO_ACTION:MATCHES_SHOWN": 0.96,  # 749 / 776: a rule's candidate equals what is shown
        "NO_ACTION:NONE": 0.80,           # 9,845 / 12,286: no rule had a candidate
    }

    # Confidence levels for Part B (human decision, 2026-11-07). The peer rule is the main source of wrong-state
    # suggestions, so in the product a peer-only suggestion is sent to the owner as a question (ASK), not a proposal.
    #   HIGH:   the business's own history (LAST_YEAR, TWO_YEARS_AGO, OLDER_SEASON, OWNER_PATTERN), and the shopping
    #           centre's own published hours (85 % exact, 6 % wrong state).
    #   MEDIUM: PEERS when the peer cell is very sure (closed_share_among_entered >= 0.85 and share_entered_closed
    #           >= 0.25: 93 % exact / 7 % wrong state on dev, both seasons; 2026 92 % / 8 %, 2025 93 % / 7 %), and
    #           CLOSED_SIGNALS (a FLAG goes to a person anyway; only 11 measured cases).
    #   LOW:    every other PEERS suggestion (69 % exact / 31 % wrong state; 225 of the 251 peer wrong-state rows).
    # Measured wrong-state rates of the HIGH bases: LAST_YEAR 4 %, SHOPPING_CENTRE 6 %, TWO_YEARS_AGO 8 %,
    # OWNER_PATTERN 12 %, OLDER_SEASON 16 %. NO_ACTION has no level: nothing is sent.
    OWN_HISTORY = ("LAST_YEAR", "TWO_YEARS_AGO", "OLDER_SEASON", "OWNER_PATTERN")
    PEER_MEDIUM_CLOSED_AMONG_ENTERED = 0.85
    PEER_MEDIUM_SHARE_ENTERED_CLOSED = 0.25

    def _confidence_level(self, eid, day_key: str, action: str, basis):
        if action == "NO_ACTION":
            return None
        if basis in self.OWN_HISTORY or basis == "SHOPPING_CENTRE":
            return "HIGH"
        if basis == "PEERS":
            ent = self.ents[eid]
            b = self.bench.get((ent["meta"]["countryCode"], self.tiers[ent["address"]["city"]], ent["c_segment"], day_key))
            sure = (b is not None and b["closed_share_among_entered"] and
                    float(b["closed_share_among_entered"]) >= self.PEER_MEDIUM_CLOSED_AMONG_ENTERED and
                    float(b["share_entered_closed"]) >= self.PEER_MEDIUM_SHARE_ENTERED_CLOSED)
            return "MEDIUM" if sure else "LOW"
        return "MEDIUM"  # CLOSED_SIGNALS, and any future basis until it is measured

    def explain_full(self, eid, d: date, day_key: str) -> dict:
        """Everything Part B needs to write a message about one (business, date). Calls explain() unchanged.

        Returns a dict: entity_id, date, day_key, day_name, action, hours (None unless SUGGEST), shown_hours, basis,
        evidence (list of readable sentences), confidence (HIGH | MEDIUM | LOW, None when we stay quiet; see the levels
        above: LOW means ask the owner rather than propose), confidence_score (0–1, measured, see CONFIDENCE), mismatch
        (inferred from what is shown vs what we suggest: SHOWN_OPEN_ACTUALLY_CLOSED | SHOWN_CLOSED_ACTUALLY_OPEN |
        DIFFERENT_HOURS | CLOSED_FOR_GOOD for a FLAG | None when we stay quiet)."""
        action, hours, basis, ev = self.explain(eid, d, day_key)
        shown = self.displayed(eid, d)
        cand = hours if action == "SUGGEST" else shown
        name = self._day_name(eid, d, day_key)
        evidence = self._evidence_lines(basis, ev, action, cand, name)
        evidence.append(f"The channels currently show {_hours_text(shown)} for {name}, {_nice_date(d)}.")
        level = self._confidence_level(eid, day_key, action, basis)
        if action == "SUGGEST":
            score = self.CONFIDENCE.get(f"PEERS:{level}" if basis == "PEERS" else basis)
            mismatch = ("SHOWN_OPEN_ACTUALLY_CLOSED" if hours == "closed" and shown != "closed" else
                        "SHOWN_CLOSED_ACTUALLY_OPEN" if shown == "closed" and hours != "closed" else "DIFFERENT_HOURS")
        elif action == "FLAG":
            score, mismatch = self.CONFIDENCE.get(basis), "CLOSED_FOR_GOOD"
        else:
            score, mismatch = self.CONFIDENCE["NO_ACTION:MATCHES_SHOWN" if basis else "NO_ACTION:NONE"], None
        return {"entity_id": eid, "date": d.isoformat(), "day_key": day_key, "day_name": name, "action": action,
                "hours": hours if action == "SUGGEST" else None, "shown_hours": shown, "basis": basis,
                "evidence": evidence, "confidence": level, "confidence_score": score, "mismatch": mismatch}

    def _day_name(self, eid, d: date, day_key: str) -> str:
        if getattr(self, "_day_names", None) is None:
            self._day_names = {(r["country"], r["date"]): r["name_en"] for r in self.cal}
        name = self._day_names.get((self.ents[eid]["meta"]["countryCode"], d.isoformat()))
        if name:
            return name
        return {"EVENT": "an event night nearby", "SCHOOL_BREAK": "a school-break day"}.get(
            day_key, day_key.replace("_", " ").title())

    def _evidence_lines(self, basis, ev, action, cand, name) -> list:
        """Readable sentences for one explain() result (the evidence formats differ by basis)."""
        if basis is None:
            return ["No rule found reliable evidence for this date, so we do not suggest a change."]
        if basis == "CLOSED_SIGNALS":
            return ["Recent reviews or edits on Google and other channels say the business has closed for good. "
                    "A person should check before anything is published."]
        if basis == "SHOPPING_CENTRE":
            lines = [f"{ev}, the shopping centre the business is in, has entered {_hours_text(cand)} for {name}."]
        elif basis == "LAST_YEAR":
            p, last = ev
            what = "its regular hours" if last == "REGULAR" else _hours_text(last)
            lines = [f"Last season the owner entered {what} for {name} ({_nice_date(date.fromisoformat(p))})."]
        elif basis in ("TWO_YEARS_AGO", "OLDER_SEASON"):
            p, what = ev
            when = "Two seasons ago" if basis == "TWO_YEARS_AGO" else "In an earlier season"
            lines = [f"{when} the owner entered {_hours_text(what)} for {name} ({_nice_date(date.fromisoformat(p))}); "
                     f"nothing was entered for it last season."]
            if "(opened as usual" in what:
                lines.append(f"We keep that closing time and use today's regular opening: {_hours_text(cand)}.")
        elif basis == "OWNER_PATTERN":
            if str(ev).startswith("already entered"):  # a same-season sibling date, e.g. another day between holidays
                lines = [f"The owner {ev}, so we use the same for {name}."]
            else:                                      # closed on every other major holiday it entered
                lines = [f"The owner has never entered {name}, but was {ev}."]
        elif basis == "KNN_BEHAVIOR":
            n_win, k, state, close, share, shared = ev
            did = {"CLOSED": "were closed", "REGULAR": "kept their regular hours",
                   "SHORT_CLOSE": f"opened as usual and closed at {close}"}[state]
            lines = [f"{n_win} of the {k} businesses whose holiday habits are most like yours {did} on {name} "
                     f"(compared on {shared} other holidays on average; similarity-weighted vote {share:.0%})."]
        else:  # PEERS and anything newer: the evidence is already a sentence
            text = str(ev)
            lines = [text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")]
        if action == "NO_ACTION":
            lines.append("That matches what the channels show, so no change is needed.")
        return lines

    _older_idx = None  # (entity_id, history day_key) -> dates with an entry before the snapshot; built on first use

    def _two_seasons_ago(self, eid, d: date, key: str):
        """Hypothesis #2. If last season has no entry for this day_key, use the business's own newest entry for it from
        two or more seasons back: returns (cand, basis, (date, what was entered)) or (None, None, None).
        basis: TWO_YEARS_AGO (two seasons back) or OLDER_SEASON (three or more).
        Seasons are matched through the history's own day_key, not the calendar: the calendar starts 2024-01-01, so
        it cannot reach the Dec 2023 entries that "two seasons back" means for the 2025 back-test. Only entries made
        before the snapshot count. No candidate for an old "regular hours" entry (weak evidence), nor for old opening
        hours from a weekday the business normally opened when d is now one of its regular days off."""
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
        basis = "TWO_YEARS_AGO" if cycle(p) == cycle(d) - 2 else "OLDER_SEASON"
        if e == "REGULAR":
            return None, None, None  # "regular hours" two or more seasons ago: too weak to overrule the next blocks
        if e == "closed":
            return e, basis, (p.isoformat(), e)
        reg_then, reg_now = self._regular_on(eid, p), self.regular(eid, d)
        if reg_now == "closed" and reg_then not in (None, "closed"):
            return None, None, None  # opened on a weekday it normally opened; d falls on a regular day off
        cand = self._align_to_regular(e, reg_then, reg_now)
        if cand != e:
            return cand, basis, (p.isoformat(), f"{e} (opened as usual, closed at {e[-5:]})")
        return cand, basis, (p.isoformat(), e)

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

    # Peer block (hyp-peer-tuning, AGENTS.md section 5 #3 + #4). Only reached when nothing above gave a candidate.
    # peer_benchmarks.csv describes what similar businesses (country, city tier, segment) *entered* for a day_key.
    # PEER_MIN_CLOSED_AMONG_ENTERED: most peers who entered something entered "closed".
    # PEER_MIN_SHARE_ENTERED_CLOSED: enough of *all* peers entered "closed" (peers who entered nothing mostly
    # stay open, so the share among enterers alone overstates closures).
    # PEER_CLOSED_DAY_CLASSES: calendar day classes on which peers' closures carry over to a business that entered
    # nothing: public holidays (MAJOR, SOFT) and the major eves (Christmas Eve, Midsummer Eve). Minor eves, days
    # between holidays, commercial days and observances are normal working days for most businesses.
    PEER_MIN_CLOSED_AMONG_ENTERED = 0.5
    PEER_MIN_SHARE_ENTERED_CLOSED = 0.15
    PEER_CLOSED_DAY_CLASSES = ("MAJOR", "EVE_MAJOR", "SOFT")

    def _day_class(self, cc, d):
        if not hasattr(self, "_day_classes"):
            self._day_classes = {(r["country"], r["date"]): r["day_class"] for r in self.cal}
        return self._day_classes.get((cc, d.isoformat()))

    def _peer_candidate(self, ent, d, key, shown):
        """(candidate hours, basis, evidence) from peer benchmarks, or (None, None, None)."""
        cc, tier, seg = ent["meta"]["countryCode"], self.tiers[ent["address"]["city"]], ent["c_segment"]
        b = self.bench.get((cc, tier, seg, key))
        if not b or not b["closed_share_among_entered"]:
            return None, None, None
        if self._day_class(cc, d) not in self.PEER_CLOSED_DAY_CLASSES:
            return None, None, None
        if shown == "00:00-23:59":  # round-the-clock businesses (24/7 gyms, emergency vets) do not follow peer closures
            return None, None, None
        closed_among_entered = float(b["closed_share_among_entered"])
        entered_closed = float(b["share_entered_closed"])
        if shown != "closed" and closed_among_entered >= self.PEER_MIN_CLOSED_AMONG_ENTERED and \
                entered_closed >= self.PEER_MIN_SHARE_ENTERED_CLOSED:
            return "closed", "PEERS", (f"{closed_among_entered:.0%} of similar businesses ({seg}, {tier}, {cc}) "
                                       f"that entered {key} hours were closed; {entered_closed:.0%} of all of them "
                                       f"entered closed")
        return None, None, None

    def predict(self, eid, d: date, key: str):
        a, h, _, _ = self.explain(eid, d, key)
        return a, h

    # ---- Owner's own pattern (hypothesis #5, basis OWNER_PATTERN) -------------------------------------------------
    # A business that never entered this day_key, but was closed on every *other* holiday it entered, is likely closed on
    # this one too. "Holiday" = public holidays and major eves (day_class MAJOR, SOFT, EVE_MAJOR), both for the target and
    # for the entries used as evidence. Fires only when the peer cell shows that closing on this day is common for the
    # business type (OWNER_PEER_MIN): below 0.3, such owners were mostly open (dev labels: 2 of 13 closed in 2026, 0 of 20
    # in the 2025 back-test).
    OWNER_CLASSES = ("MAJOR", "SOFT", "EVE_MAJOR")
    OWNER_MIN_HOLIDAYS = 2       # distinct other day_keys entered, all closed (latest entry per day_key)
    OWNER_PEER_MIN = 0.3         # peer closed_share_among_entered for this day_key (flat 0.2-0.35, see log)

    def _owner_index(self):
        """entity -> {day_key: [(date, value), …]} of its own holiday entries entered before the snapshot (latest
        entry per date wins), sorted by date."""
        if getattr(self, "_own", None) is None:
            snap = self.snap.isoformat()
            self._own_class = {(r["country"], r["day_key"]): r["day_class"] for r in self.cal}
            own = defaultdict(lambda: defaultdict(list))
            for (eid, ds), rows in sorted(self.hol.items()):
                rows = [r for r in rows if r["entered_at"] < snap]
                if not rows:
                    continue
                r = max(rows, key=lambda r: r["entered_at"])
                h = r["holidayHours"]
                own[eid][r["day_key"]].append((ds, "REGULAR" if h.get("isRegularHours") else day_str(h)))
            self._own = own
        return self._own

    def _owner_pattern(self, eid, d: date, key: str):
        """(hours, evidence) from the owner's own entries for this season or other holidays, else None."""
        own = self._owner_index()
        ent = self.ents[eid]
        cc = ent["meta"]["countryCode"]
        if self._own_class.get((cc, key)) is None or self.entry(eid, d, self.snap) is not None:
            return None  # not a calendar day_key (EVENT, SCHOOL_BREAK), or the owner already entered this date
        mine = own.get(eid, {})
        if key in mine:
            # Same day_key on other dates: only same-season siblings (e.g. INTERDAY 28 Dec entered, 29 Dec not).
            # Earlier seasons belong to the last-year / two-year rules.
            sib = mine[key]
            if any(cycle(date.fromisoformat(ds)) != cycle(d) for ds, _ in sib) or len({v for _, v in sib}) != 1:
                return None
            v = sib[0][1]
            return (self.regular(eid, d) if v == "REGULAR" else v), \
                f"already entered {'regular hours' if v == 'REGULAR' else v} for {key} " + \
                ", ".join(ds for ds, _ in sib) + " this season"
        if self._own_class.get((cc, key)) not in self.OWNER_CLASSES:
            return None
        rel = sorted((s[-1][0], k, s[-1][1]) for k, s in mine.items() if self._own_class.get((cc, k)) in self.OWNER_CLASSES)
        if len(rel) < self.OWNER_MIN_HOLIDAYS or any(v != "closed" for _, _, v in rel):
            return None
        b = self.bench.get((cc, self.tiers[ent["address"]["city"]], ent["c_segment"], key))
        if not b or not b["closed_share_among_entered"] or float(b["closed_share_among_entered"]) < self.OWNER_PEER_MIN:
            return None
        share = float(b["closed_share_among_entered"])
        days = ", ".join(f"{k} {ds}" for ds, k, _ in rel)
        return "closed", (f"closed on all {len(rel)} holidays it entered ({days}); "
                          f"{share:.0%} of peers who entered hours for {key} were closed")

    # ---- KNN on holiday behaviour (experiment hyp/knn-behavior, basis KNN_BEHAVIOR) ---------------------------------
    # For a business X with no own entry for this day_key: find the K businesses whose holiday BEHAVIOUR is most like
    # X's (state per day_key relative to the regular hours of that weekday, see knn_state()), and use what they did on
    # this day_key if a similarity-weighted vote is decisive. X's own vector always comes from its holiday history
    # (entered before the snapshot). The neighbours' vectors come from
    #   source "A": the holiday history of every other business (entered before the snapshot), or
    #   source "B": tables/knn_truth_<season>.json, built by build/build_knn_truth.py from the dev businesses' true
    #               hours before the snapshot. A dev business only uses neighbours outside its own fold (5 fixed folds);
    #               test and demo businesses use every dev business. model.py never opens labels/.
    KNN_SOURCE = None            # None = block off (main's behaviour) | "A" | "B"
    KNN_REPLACES_OWNER = False   # True: the block takes OWNER_PATTERN's place in the cascade
    KNN_MIN_SHARED = 3           # day_keys both businesses know (the target day_key never counts: X does not know it)
    KNN_K = 10
    KNN_THRESHOLD = 0.8          # weighted share the winning state needs
    KNN_REGULAR_BLOCKS = True    # a decisive "kept regular hours" vote is a candidate (= shown -> stay quiet, no peers)
    KNN_IN_SAMPLE = False        # source B, in-sample comparison only: every business may use every dev business
    KNN_ATTR_WEIGHT = 0.1        # small weight for the same archetype and the same country
    KNN_CLOSE_TOL = 120          # minutes: two SHORT_CLOSE days match fully at equal closing, half at >= this apart
    KNN_TABLES = os.path.join(ROOT, "result", "A_prediction_engine", "tables")

    def _knn_hist_vectors(self):
        """entity -> behaviour vector from its holiday history (entries made before the snapshot). Shopping centres
        are left out of the neighbour pool."""
        if getattr(self, "_knn_hist", None) is None:
            snap = self.snap.isoformat()
            days = defaultdict(lambda: defaultdict(list))
            for (eid, ds), rows in sorted(self.hol.items()):
                rows = [r for r in rows if r["entered_at"] < snap]
                if not rows:
                    continue
                r = max(rows, key=lambda r: r["entered_at"])
                h = r["holidayHours"]
                days[eid][r["day_key"]].append(
                    (ds, "REGULAR" if h.get("isRegularHours") else day_str(h), regular_in_force(self.reg[eid], ds, snap)))
            self._knn_hist = {eid: knn_vector(v) for eid, v in days.items()}
        return self._knn_hist

    def _knn_meta(self):
        """Lookups for the attribute part of the similarity, and the split of every business."""
        if getattr(self, "_knn_attr", None) is None:
            arch = {r["segment"]: r["archetype"] for r in csv.DictReader(open(D("categories.csv"), encoding="utf-8"))}
            self._knn_attr = {eid: (arch.get(e.get("c_segment")), e["meta"]["countryCode"]) for eid, e in self.ents.items()}
            self._knn_split = {r["entity_id"]: r["split"] for r in csv.DictReader(open(D("splits.csv"), encoding="utf-8"))}
        return self._knn_attr, self._knn_split

    def _knn_truth(self):
        """Source B table of this season (built by build/build_knn_truth.py). Checks it was cut at this snapshot."""
        if getattr(self, "_knn_tb", None) is None:
            path = os.path.join(self.KNN_TABLES, f"knn_truth_{self.season}.json")
            t = json.load(open(path, encoding="utf-8"))
            m = t["meta"]
            assert m["season"] == self.season and m["snapshot"] == self.snap.isoformat(), f"{path}: wrong season"
            assert m["newest_truth_date"] < self.snap.isoformat(), f"{path}: truth dated on/after the snapshot"
            t["vectors"] = {eid: {k: tuple(v) for k, v in vec.items()} for eid, vec in t["vectors"].items()}
            self._knn_tb = t
        return self._knn_tb

    def _knn_pool(self, eid):
        """(pool name, {neighbour: vector}) the business may draw neighbours from."""
        if self.KNN_SOURCE == "A":
            return "A", self._knn_hist_vectors()
        t = self._knn_truth()
        _, split = self._knn_meta()
        if self.KNN_IN_SAMPLE or split.get(eid) != "dev":
            name = "B:all"
        else:
            name = f"B:fold{t['folds'][eid]}"
        if getattr(self, "_knn_pools", None) is None:
            self._knn_pools = {}
        if name not in self._knn_pools:
            held = None if name == "B:all" else int(name[6:])
            self._knn_pools[name] = {o: v for o, v in t["vectors"].items() if held is None or t["folds"][o] != held}
        return name, self._knn_pools[name]

    def _knn_index(self, name, pool):
        """day_key -> [(neighbour, state, closing)] for one pool, built once."""
        if getattr(self, "_knn_idx", None) is None:
            self._knn_idx = {}
        if name not in self._knn_idx:
            idx = defaultdict(list)
            for o in sorted(pool):
                if self.ents.get(o, {}).get("c_entityRole") == "SHOPPING_CENTRE":
                    continue
                for k, (s, c) in pool[o].items():
                    idx[k].append((o, s, c))
            self._knn_idx[name] = idx
        return self._knn_idx[name]

    def _knn_ranked(self, eid):
        """Every pool business that shares a known day_key with eid, most similar first: [(neighbour, score, shared)].
        score = (1 - w) * behaviour match share over the shared day_keys + w * attribute match (archetype, country)."""
        name, pool = self._knn_pool(eid)
        ck = (name, eid)
        if getattr(self, "_knn_rank", None) is None:
            self._knn_rank = {}
        if ck in self._knn_rank:
            return self._knn_rank[ck], pool
        own = self._knn_hist_vectors().get(eid, {})
        idx = self._knn_index(name, pool)
        match, shared = defaultdict(float), defaultdict(int)
        for k, (s, c) in own.items():
            for o, so, co in idx.get(k, ()):
                shared[o] += 1
                if so == s:
                    match[o] += 1.0 if s != "SHORT_CLOSE" else 1.0 - 0.5 * min(1.0, abs(c - co) / self.KNN_CLOSE_TOL)
        attr, _ = self._knn_meta()
        ax, w = attr.get(eid), self.KNN_ATTR_WEIGHT
        ranked = []
        for o, n in shared.items():
            if o == eid and self.KNN_SOURCE == "A":
                continue
            ao = attr.get(o)
            a = ((ax[0] == ao[0]) + (ax[1] == ao[1])) / 2 if ax and ao else 0.0
            ranked.append((-((1 - w) * match[o] / n + w * a), -n, o))
        ranked.sort()
        self._knn_rank[ck] = [(o, -s, -n) for s, n, o in ranked]
        return self._knn_rank[ck], pool

    def _knn_candidate(self, eid, d: date, key: str):
        """(hours, evidence) from the K most similar businesses that know this day_key, else None.
        evidence = (neighbours with the winning state, K, state, closing time or None, weighted share, mean shared)."""
        if key in self._owner_index().get(eid, {}):
            return None  # the business has its own history for this day_key: the history rules decide
        reg_now = self.regular(eid, d)
        if reg_now == "closed":
            return None
        ranked, pool = self._knn_ranked(eid)
        picked = []
        for o, sc, n in ranked:
            if n < self.KNN_MIN_SHARED or sc <= 0:
                continue
            st = pool[o].get(key)
            if st is None:
                continue
            picked.append((sc, n, st))
            if len(picked) == self.KNN_K:
                break
        if len(picked) < self.KNN_K:
            return None
        votes = defaultdict(float)
        for sc, _, (s, _) in picked:
            votes[s] += sc
        best = max(sorted(votes), key=lambda s: votes[s])
        share = votes[best] / sum(votes.values())
        if share < self.KNN_THRESHOLD:
            return None
        n_win = sum(1 for _, _, (s, _) in picked if s == best)
        mean_shared = round(sum(n for _, n, _ in picked) / len(picked))
        close = None
        if best == "CLOSED":
            cand = "closed"
        elif best == "REGULAR":
            if not self.KNN_REGULAR_BLOCKS:
                return None
            cand = reg_now
        elif best == "SHORT_CLOSE":
            cl = sorted(c for _, _, (s, c) in picked if s == "SHORT_CLOSE")
            c = cl[(len(cl) - 1) // 2]  # lower median: a closing time some neighbour really used
            o, rc = _span(reg_now)
            if not o < c < rc:
                return None  # the neighbours' early closing is not earlier than this business's regular closing
            close = _hhmm(c)
            cand = f"{_hhmm(o)}-{close}"
        else:
            return None  # OTHER_HOURS: the neighbours' hours do not transfer to this business's own regular hours
        return cand, (n_win, len(picked), best, close, share, mean_shared)


# ---- helpers for the KNN block, shared with build/build_knn_truth.py (so both sources use the same states) ----------
def _span(h):
    """First opening and last closing of an hours string, in minutes (a closing past midnight is > 1440)."""
    iv = h.split(",")
    o, c = iv[0].split("-")[0], iv[-1].split("-")[1]
    om, cm = int(o[:2]) * 60 + int(o[3:]), int(c[:2]) * 60 + int(c[3:])
    if cm <= om and not (o == "00:00" and c == "23:59"):
        cm += 1440
    return om, cm


def _hhmm(m):
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def regular_in_force(versions, ds: str, snap: str):
    """Published regular hours for the weekday of ISO date ds, from the newest version effective on ds and published
    before the snapshot (None if there is none)."""
    then = [r for r in versions if r["effective_from"] == "before-2024" or
            (r["effective_from"] <= ds and r["effective_from"] < snap)]
    if not then:
        return None
    best = max(then, key=lambda r: "0000" if r["effective_from"] == "before-2024" else r["effective_from"])
    return day_str(best["hours"][DAYS[date.fromisoformat(ds).weekday()]])


def knn_state(h, reg_then):
    """Behaviour on one special day relative to the regular hours of that weekday: (state, closing minute or None).
    state: CLOSED | REGULAR | SHORT_CLOSE (same opening, earlier closing) | OTHER_HOURS. None = the day says nothing
    (regular hours unknown, or a regular day off on which the business stayed closed)."""
    if reg_then is None:
        return None
    if h == "REGULAR":
        h = reg_then
    if reg_then == "closed":
        return None if h == "closed" else ("OTHER_HOURS", _span(h)[1])
    if h == "closed":
        return "CLOSED", None
    if h == reg_then:
        return "REGULAR", None
    (ho, hc), (ro, rc) = _span(h), _span(reg_then)
    if ho == ro and hc < rc:
        return "SHORT_CLOSE", hc
    return "OTHER_HOURS", hc


def knn_vector(days):
    """{day_key: [(ISO date, hours, regular hours that weekday then)]} -> {day_key: (state, closing)}. Per day_key:
    the newest season with an informative day; in it the majority state (tie: the state of the latest date), and for
    SHORT_CLOSE the lower median closing time of its short days."""
    vec = {}
    for key in sorted(days):
        seasons = defaultdict(list)
        for ds, h, reg_then in days[key]:
            st = knn_state(h, reg_then)
            if st:
                seasons[cycle(date.fromisoformat(ds))].append((ds, st))
        if not seasons:
            continue
        obs = sorted(seasons[max(seasons)])
        cnt = defaultdict(int)
        for _, (s, _) in obs:
            cnt[s] += 1
        top = max(cnt.values())
        state = next(s for _, (s, _) in reversed(obs) if cnt[s] == top)
        close = None
        if state == "SHORT_CLOSE":
            cl = sorted(c for _, (s, c) in obs if s == "SHORT_CLOSE")
            close = cl[(len(cl) - 1) // 2]
        vec[key] = (state, close)
    return vec


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
