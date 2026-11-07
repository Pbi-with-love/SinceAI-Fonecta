#!/usr/bin/env python3
"""Part B bundle builder (dry run): Part A's explain_full() -> Supabase rows `bundles` and `bundle_items`.

Reads Part A read-only (imports model.py, calls explain_full() only). Writes JSON files; never calls a service.
Standard library only. Deterministic: same inputs -> byte-identical output.

    python result/B_contact_decide/build_bundles.py                       # the 17 demo businesses
    python result/B_contact_decide/build_bundles.py --entities FI-D0001,FI-D0011
    python result/B_contact_decide/build_bundles.py --validate-only FILE  # re-check an existing JSON file
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date

sys.dont_write_bytecode = True  # do not leave __pycache__ inside the frozen Part A folder

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "result", "A_prediction_engine"))
import model  # noqa: E402  (read-only: only Baseline.explain_full() is called)

SEASON = 2026
ROUTES = ("SKIP", "STAFF", "AUTO_APPLY", "SUGGEST", "ASK")  # the n8n Route Guard's allowed set
ROUTE_ORDER = {"STAFF": 0, "AUTO_APPLY": 1, "SUGGEST": 2, "ASK": 3}
LANGS = ("fi", "sv", "nb", "en")
COUNTRY_LANG = {"FI": "fi", "SE": "sv", "NO": "nb"}
HOURS_RE = re.compile(r"^(closed|\d\d:\d\d-\d\d:\d\d(,\d\d:\d\d-\d\d:\d\d)*)$")  # the evaluator's day_str() format
MAX_ITEM_LINES = 8  # intro_text stays within ~12 lines

# Columns the builder fills, per table (the schema columns minus database defaults)
DB_DEFAULT_COLS = {"bundles": {"created_at", "updated_at"}, "bundle_items": {"id"}}


# --------------------------------------------------------------------------------------------- templates
CLOSED = {"fi": "suljettu", "sv": "stängt", "nb": "stengt", "en": "closed"}
AND = {"fi": "ja", "sv": "och", "nb": "og", "en": "and"}
WEEKDAY = {
    "fi": ["ma", "ti", "ke", "to", "pe", "la", "su"],
    "sv": ["mån", "tis", "ons", "tors", "fre", "lör", "sön"],
    "nb": ["man", "tir", "ons", "tor", "fre", "lør", "søn"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
REASON = {  # one short reason per basis (AGENTS.md section 2.4: LOW = peers only = asked, not proposed)
    "fi": {"LAST_YEAR": "omat tietosi viime vuodelta", "TWO_YEARS_AGO": "omat tietosi kahden vuoden takaa",
           "OLDER_SEASON": "omat tietosi aiemmalta kaudelta", "OWNER_PATTERN": "muiden pyhäpäivien perusteella",
           "SHOPPING_CENTRE": "kauppakeskus on ilmoittanut aukioloaikansa", "PEERS": "samankaltaisten yritysten tapa",
           "CLOSED_SIGNALS": "arvostelut tai muokkaukset kertovat lopettamisesta"},
    "sv": {"LAST_YEAR": "dina egna uppgifter från förra året", "TWO_YEARS_AGO": "dina egna uppgifter från för två år sedan",
           "OLDER_SEASON": "dina egna uppgifter från en tidigare säsong", "OWNER_PATTERN": "utifrån dina andra helgdagar",
           "SHOPPING_CENTRE": "köpcentret har meddelat sina tider", "PEERS": "så gör liknande företag",
           "CLOSED_SIGNALS": "recensioner eller ändringar tyder på nedläggning"},
    "nb": {"LAST_YEAR": "dine egne opplysninger fra i fjor", "TWO_YEARS_AGO": "dine egne opplysninger fra for to år siden",
           "OLDER_SEASON": "dine egne opplysninger fra en tidligere sesong", "OWNER_PATTERN": "basert på dine andre helligdager",
           "SHOPPING_CENTRE": "kjøpesenteret har meldt inn sine tider", "PEERS": "slik gjør lignende bedrifter",
           "CLOSED_SIGNALS": "anmeldelser eller endringer tyder på nedleggelse"},
    "en": {"LAST_YEAR": "your own entry last year", "TWO_YEARS_AGO": "your own entry two years ago",
           "OLDER_SEASON": "your own entry in an earlier season", "OWNER_PATTERN": "based on your other holidays",
           "SHOPPING_CENTRE": "the shopping centre has published its hours", "PEERS": "what similar businesses do",
           "CLOSED_SIGNALS": "reviews or edits suggest it has closed"},
}
TEXT = {  # route -> language -> (greeting, intro, closing); {name} owner, {biz} business
    "SUGGEST": {
        "fi": ("Hei {name}!", "{biz}: aukioloaikasi saattavat olla väärin tulevina pyhinä. Ehdotamme näitä muutoksia (nyt → ehdotus):",
               "Hyväksytkö muutokset? Voit myös muokata tai hylätä ne."),
        "sv": ("Hej {name}!", "{biz}: dina öppettider kan vara fel under kommande helgdagar. Vi föreslår dessa ändringar (nu → förslag):",
               "Godkänner du ändringarna? Du kan också ändra eller avstå."),
        "nb": ("Hei {name}!", "{biz}: åpningstidene dine kan være feil de kommende helligdagene. Vi foreslår disse endringene (nå → forslag):",
               "Godkjenner du endringene? Du kan også endre eller avslå dem."),
        "en": ("Hi {name}!", "{biz}: your opening hours may be wrong on the coming holidays. We suggest these changes (now → proposed):",
               "Do you approve? You can also edit or decline them."),
    },
    "ASK": {
        "fi": ("Hei {name}!", "{biz}: emme ole varmoja, milloin olette auki tulevina pyhinä. Näytämme nyt → arvaus:",
               "Kerro meille: suljettu, auki kuten tavallisesti vai muokkaa?"),
        "sv": ("Hej {name}!", "{biz}: vi är osäkra på era öppettider under kommande helgdagar. Vi visar nu → gissning:",
               "Berätta för oss: stängt, öppet som vanligt eller ändra?"),
        "nb": ("Hei {name}!", "{biz}: vi er usikre på åpningstidene deres de kommende helligdagene. Vi viser nå → gjetning:",
               "Si fra: stengt, åpent som vanlig eller endre?"),
        "en": ("Hi {name}!", "{biz}: we are not sure about your hours on the coming holidays. Showing now → our guess:",
               "Please tell us: closed, open as usual, or edit?"),
    },
    "AUTO_APPLY": {
        "fi": ("Hei {name}!", "{biz}: luvallasi olemme päivittäneet aukioloaikasi (ennen → nyt):",
               "Voit perua muutokset 24 tunnin kuluessa."),
        "sv": ("Hej {name}!", "{biz}: enligt ditt tillstånd har vi uppdaterat dina öppettider (före → nu):",
               "Du kan ångra ändringarna inom 24 timmar."),
        "nb": ("Hei {name}!", "{biz}: i tråd med din tillatelse har vi oppdatert åpningstidene dine (før → nå):",
               "Du kan angre endringene innen 24 timer."),
        "en": ("Hi {name}!", "{biz}: with your standing permission we have updated your opening hours (before → now):",
               "You can undo the changes within 24 hours."),
    },
}
MORE = {"fi": "… ja {n} muuta päivää", "sv": "… och {n} dagar till", "nb": "… og {n} dager til", "en": "… and {n} more days"}


def hours_label(h, lang):
    """'closed' / '09:00-17:00,18:00-20:00' -> readable text in the owner's language."""
    if h == "closed":
        return CLOSED[lang]
    return ", ".join(iv.replace("-", "–") for iv in h.split(","))


def date_label(iso, lang):
    d = date.fromisoformat(iso)
    sep = "/" if lang == "sv" else "."
    tail = "" if lang == "sv" else "."
    if lang == "en":
        return f"{WEEKDAY['en'][d.weekday()]} {d.day} {d.strftime('%b')}"
    return f"{WEEKDAY[lang][d.weekday()]} {d.day}{sep}{d.month}{tail}"


# --------------------------------------------------------------------------------------------- data
def read_csv(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_reference():
    ents = {e["meta"]["id"]: e for e in json.load(open(os.path.join(ROOT, "data", "entities.json"), encoding="utf-8"))
            ["response"]["entities"]}
    contacts = {r["entity_id"]: r for r in read_csv("data", "customer_contacts.csv")}
    listings = defaultdict(list)
    for r in json.load(open(os.path.join(ROOT, "data", "listings.json"), encoding="utf-8"))["listings"]:
        listings[r["entityId"]].append({"publisherId": r["publisherId"], "publisherName": r["publisherName"],
                                        "typicalUpdateSpeedSeconds": r["typicalUpdateSpeedSeconds"]})
    for v in listings.values():
        v.sort(key=lambda p: p["publisherId"])
    names = {(r["country"], r["date"]): (r["name_local"], r["name_en"]) for r in read_csv("data", "calendar_special_days.csv")}
    targets = defaultdict(list)
    for r in read_csv("evaluation", "targets_2026.csv"):
        targets[r["entity_id"]].append(r)
    demo = sorted(r["entity_id"] for r in read_csv("data", "splits.csv") if r["split"] == "demo")
    return ents, contacts, listings, names, targets, demo


SPECIAL_NAMES = {  # day_keys that are not in the calendar (events, school breaks)
    "EVENT": {"fi": "Tapahtumailta lähellä", "sv": "Evenemangskväll i närheten", "nb": "Arrangementskveld i nærheten",
              "en": "Event night nearby"},
    "SCHOOL_BREAK": {"fi": "Koulujen loma", "sv": "Skollov", "nb": "Skolefri", "en": "School break"},
}


def holiday_name(names, country, iso, day_key, day_name_en, lang):
    """Local name in the owner's language when it is the country's own; 'local (English)' when it is not."""
    loc = names.get((country, iso))
    if not loc:
        sp = SPECIAL_NAMES.get(day_key)
        return sp[lang] if sp else day_name_en
    if lang == COUNTRY_LANG.get(country):
        return loc[0]
    if lang == "en":
        return loc[1]
    return f"{loc[0]} ({loc[1]})"


# --------------------------------------------------------------------------------------------- intro text
def build_intro(route, owner, biz, lang, items, names, country, eid):
    """Fixed templates only (no LLM). `items` are bundle_items dicts (with `day_key`, `_name_en` helpers)."""
    if route == "STAFF":
        dates = [i["date"] for i in items]
        lines = [f"STAFF: {biz} ({eid}) looks closed for good. Do not publish suggestions; check the listing.",
                 f"Affected dates: {len(dates)} special days, {dates[0]} to {dates[-1]}.",
                 f"Evidence: {items[0]['evidence'][0]}"]
        return "\n".join(lines)
    greeting, intro, closing = TEXT[route][lang]
    # group consecutive dates that share holiday name, hours and basis into one line
    groups, order = defaultdict(list), []
    for it in items:
        nm = holiday_name(names, country, it["date"], it["_day_key"], it["day_name"], lang)
        key = (nm, it["shown_hours"], it["proposed_hours"], it["basis"])
        if key not in groups:
            order.append(key)
        groups[key].append(it["date"])
    lines = [greeting.format(name=owner), intro.format(biz=biz)]
    shown_lines = 0
    for key in order:
        nm, shown, prop, basis = key
        if shown_lines >= MAX_ITEM_LINES:
            break
        ds = ", ".join(date_label(d, lang) for d in groups[key])
        lines.append(f"• {nm}, {ds}: {hours_label(shown, lang)} → {hours_label(prop, lang)} ({REASON[lang][basis]})")
        shown_lines += 1
    left = sum(len(groups[k]) for k in order[shown_lines:])
    if left:
        lines.append(MORE[lang].format(n=left))
    lines.append(closing)
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------- builder
def build(entity_ids):
    ents, contacts, listings, names, targets, demo = load_reference()
    bl = model.Baseline(SEASON)
    bundles, all_items = [], []
    for eid in entity_ids:
        ent, ct = ents[eid], contacts[eid]
        country = ent["meta"]["countryCode"]
        lang = ct["preferred_language"] if ct["preferred_language"] in LANGS else "en"
        rows = []
        for t in sorted(targets[eid], key=lambda r: (r["date"], r["day_key"])):
            x = bl.explain_full(eid, date.fromisoformat(t["date"]), t["day_key"])
            if x["action"] in ("SUGGEST", "FLAG"):
                rows.append({"date": x["date"], "day_name": x["day_name"], "shown_hours": x["shown_hours"],
                             "proposed_hours": x["hours"], "final_hours": None, "basis": x["basis"],
                             "evidence": x["evidence"], "confidence": x["confidence"],
                             "_action": x["action"], "_day_key": x["day_key"]})
        has_perm = ct["standing_permission_holidays"] == "1"
        opted_out = ct["opted_out_of_suggestions"] == "1"
        flag = [r for r in rows if r["_action"] == "FLAG"]
        sugg = [r for r in rows if r["_action"] == "SUGGEST"]
        high_med = [r for r in sugg if r["confidence"] in ("HIGH", "MEDIUM")]
        low = [r for r in sugg if r["confidence"] == "LOW"]
        planned = []
        if flag:
            planned.append(("STAFF", flag))
        if high_med:
            auto = has_perm and all(r["confidence"] == "HIGH" for r in high_med)
            planned.append(("AUTO_APPLY" if auto else "SUGGEST", high_med))
        if low:
            planned.append(("ASK", low))
        for route, items in planned:
            bid = f"B-{eid}-{route}"
            intro = build_intro(route, ct["contact_first_name"], ent["name"], "en" if route == "STAFF" else lang,
                                items, names, country, eid)
            bundles.append({
                "bundle_id": bid, "entity_id": eid, "business_name": ent["name"],
                "yext_entity_id": eid,  # organisers' mock: the Yext entity id equals our entity id
                "owner_name": ct["contact_first_name"], "language": lang, "telegram_chat_id": f"FAKE-{eid}",
                "opted_out": opted_out, "has_permission": has_perm, "route": route, "status": "QUEUED",
                "intro_text": intro, "publishers": listings[eid], "telegram_message_id": None})
            for it in items:
                all_items.append({"bundle_id": bid, "date": it["date"], "day_name": it["day_name"],
                                  "shown_hours": it["shown_hours"], "proposed_hours": it["proposed_hours"],
                                  "final_hours": None, "basis": it["basis"], "evidence": it["evidence"],
                                  "confidence": it["confidence"]})
    bundles.sort(key=lambda b: (b["entity_id"], ROUTE_ORDER[b["route"]]))
    all_items.sort(key=lambda i: (i["bundle_id"], i["date"]))
    return {"bundles": bundles, "bundle_items": all_items}


# --------------------------------------------------------------------------------------------- validator
def schema_columns():
    cols = defaultdict(list)
    for line in open(os.path.join(HERE, "supabase_schema.md"), encoding="utf-8"):
        m = re.match(r"\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*([\w ]+?)\s*\|\s*$", line)
        if m and m.group(1) not in ("table_name",):
            cols[m.group(1)].append((m.group(2), m.group(3)))
    return cols


TYPE_OK = {"text": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
           "jsonb": lambda v: isinstance(v, (list, dict)), "date": lambda v: isinstance(v, str)}


def validate(data):
    """Return a list of problems (empty = valid)."""
    errs, cols = [], schema_columns()
    for table, rows in (("bundles", data["bundles"]), ("bundle_items", data["bundle_items"])):
        want = {c: t for c, t in cols[table] if c not in DB_DEFAULT_COLS[table]}
        for r in rows:
            tag = r.get("bundle_id", "?") + (f" {r['date']}" if table == "bundle_items" else "")
            if set(r) != set(want):
                errs.append(f"{table} {tag}: columns differ (missing {sorted(set(want) - set(r))}, extra {sorted(set(r) - set(want))})")
                continue
            for c, t in want.items():
                v = r[c]
                if v is not None and t in TYPE_OK and not TYPE_OK[t](v):
                    errs.append(f"{table} {tag}.{c}: expected {t}, got {type(v).__name__}")
    ids = [b["bundle_id"] for b in data["bundles"]]
    if len(ids) != len(set(ids)):
        errs.append("duplicate bundle_id")
    by_id = {b["bundle_id"]: b for b in data["bundles"]}
    seen_items = set()
    for b in data["bundles"]:
        if b["route"] not in ROUTES:
            errs.append(f"{b['bundle_id']}: route {b['route']} not allowed")
        if b["status"] != "QUEUED" or b["telegram_message_id"] is not None:
            errs.append(f"{b['bundle_id']}: status must be QUEUED and telegram_message_id null")
        if b["language"] not in LANGS:
            errs.append(f"{b['bundle_id']}: language {b['language']}")
        if not b["telegram_chat_id"].startswith("FAKE-"):
            errs.append(f"{b['bundle_id']}: telegram_chat_id must be a FAKE- placeholder")
        if b["intro_text"].count("\n") + 1 > 12:
            errs.append(f"{b['bundle_id']}: intro_text longer than 12 lines")
        if not any(i["bundle_id"] == b["bundle_id"] for i in data["bundle_items"]):
            errs.append(f"{b['bundle_id']}: bundle has no items")
    for i in data["bundle_items"]:
        tag = f"{i['bundle_id']} {i['date']}"
        b = by_id.get(i["bundle_id"])
        if b is None:
            errs.append(f"item {tag}: no bundle")
            continue
        if (i["bundle_id"], i["date"]) in seen_items:
            errs.append(f"item {tag}: duplicate")
        seen_items.add((i["bundle_id"], i["date"]))
        if not HOURS_RE.match(i["shown_hours"] or ""):
            errs.append(f"item {tag}: shown_hours {i['shown_hours']!r} not in evaluator format")
        if b["route"] == "STAFF":
            if i["proposed_hours"] is not None:
                errs.append(f"item {tag}: FLAG item must have null proposed_hours")
        else:
            if not HOURS_RE.match(i["proposed_hours"] or ""):
                errs.append(f"item {tag}: proposed_hours {i['proposed_hours']!r} not in evaluator format")
            if i["proposed_hours"] == i["shown_hours"]:
                errs.append(f"item {tag}: proposed equals shown")
        if i["final_hours"] is not None:
            errs.append(f"item {tag}: final_hours must be null")
        if i["confidence"] not in ("HIGH", "MEDIUM", "LOW"):
            errs.append(f"item {tag}: confidence {i['confidence']}")
        if not i["evidence"] or not all(isinstance(s, str) and s for s in i["evidence"]):
            errs.append(f"item {tag}: evidence must be a non-empty list of strings")
        # routing rules
        if b["route"] == "ASK" and i["confidence"] != "LOW":
            errs.append(f"item {tag}: ASK bundle holds only LOW items")
        if b["route"] in ("SUGGEST", "AUTO_APPLY") and i["confidence"] == "LOW":
            errs.append(f"item {tag}: LOW item in {b['route']} bundle")
        if b["route"] == "AUTO_APPLY" and (i["confidence"] != "HIGH" or not b["has_permission"]):
            errs.append(f"item {tag}: AUTO_APPLY needs permission and HIGH")
    # the numbers in intro_text must match the items (route STAFF text is internal English, checked for dates only)
    items_by = defaultdict(list)
    for i in data["bundle_items"]:
        items_by[i["bundle_id"]].append(i)
    for b in data["bundles"]:
        lines = b["intro_text"].split("\n")
        lang = "en" if b["route"] == "STAFF" else b["language"]
        its = items_by[b["bundle_id"]]
        if b["route"] == "STAFF":
            if f"{len(its)} special days" not in b["intro_text"] or b["entity_id"] not in b["intro_text"]:
                errs.append(f"{b['bundle_id']}: STAFF text does not match item count")
            continue
        more = re.search(r"(\d+)", lines[-2]) if lines[-2].startswith("…") else None
        listed = 0
        for i in its:
            want = (date_label(i["date"], lang), hours_label(i["shown_hours"], lang) + " → " + hours_label(i["proposed_hours"], lang))
            if any(l.startswith("•") and want[0] in l and want[1] in l for l in lines):
                listed += 1
        expected_hidden = int(more.group(1)) if more else 0
        if listed + expected_hidden != len(its):
            errs.append(f"{b['bundle_id']}: intro_text lists {listed} of {len(its)} items (+{expected_hidden} hidden)")
        for l in lines:  # every time in the text must belong to some item of the bundle
            if l.startswith("•"):
                nums = set(re.findall(r"\d\d:\d\d", l))
                ok = {t for i in its for t in re.findall(r"\d\d:\d\d", (i["shown_hours"] or "") + (i["proposed_hours"] or ""))}
                if not nums <= ok:
                    errs.append(f"{b['bundle_id']}: line has times not in items: {l}")
    return errs


# --------------------------------------------------------------------------------------------- summary
def summary_md(data):
    by_ent = defaultdict(list)
    for b in data["bundles"]:
        by_ent[b["entity_id"]].append(b)
    items_by = defaultdict(list)
    for i in data["bundle_items"]:
        items_by[i["bundle_id"]].append(i)
    out = ["# Part B bundles: demo dry run (generated by `build_bundles.py`, do not edit by hand)", "",
           "Season 2026, snapshot 2026-11-06. All Telegram ids are fake placeholders. Nothing was sent.", "",
           "| Business | Bundle | Route | Items | Confidence | Language | Permission |", "|---|---|---|---|---|---|---|"]
    for eid in sorted(by_ent):
        for b in by_ent[eid]:
            its = items_by[b["bundle_id"]]
            conf = ", ".join(f"{c} {sum(1 for i in its if i['confidence'] == c)}" for c in ("HIGH", "MEDIUM", "LOW")
                             if any(i["confidence"] == c for i in its))
            out.append(f"| {b['entity_id']} {b['business_name']} | {b['bundle_id']} | {b['route']} | {len(its)} | {conf} "
                       f"| {b['language']} | {'yes' if b['has_permission'] else 'no'} |")
    out += ["", "## Intro texts", ""]
    for eid in sorted(by_ent):
        for b in by_ent[eid]:
            its = items_by[b["bundle_id"]]
            bases = ", ".join(f"{k} {v}" for k, v in sorted({i['basis']: sum(1 for j in its if j['basis'] == i['basis']) for i in its}.items()))
            out += [f"### {b['bundle_id']} ({b['business_name']}, {b['route']}, {b['language']})", "",
                    f"Items: {len(its)}. Basis: {bases}.", "", "```", b["intro_text"], "```", ""]
    return "\n".join(out)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", help="comma-separated entity ids (default: the 17 demo businesses)")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "samples"))
    ap.add_argument("--name", default="bundles_demo")
    ap.add_argument("--validate-only", metavar="FILE")
    a = ap.parse_args()
    if a.validate_only:
        errs = validate(json.load(open(a.validate_only, encoding="utf-8")))
        print("\n".join(errs) if errs else "valid")
        sys.exit(1 if errs else 0)
    demo = load_reference()[-1]
    ids = [e.strip() for e in a.entities.split(",") if e.strip()] if a.entities else demo
    data = build(ids)
    errs = validate(data)
    if errs:
        print("VALIDATION FAILED:\n" + "\n".join(errs))
        sys.exit(1)
    dump(os.path.join(a.out_dir, a.name + ".json"), data)
    dump(os.path.join(a.out_dir, a.name + "_summary.md"), summary_md(data) + "\n")
    print(f"validator passed: {len(data['bundles'])} bundles, {len(data['bundle_items'])} items -> {a.out_dir}")


if __name__ == "__main__":
    main()
