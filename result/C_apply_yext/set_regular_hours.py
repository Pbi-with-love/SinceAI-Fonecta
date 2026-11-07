#!/usr/bin/env python3
"""Give a Yext entity its regular weekly hours if it has none (Part C demo setup).

    set -a; source .env; set +a
    python3 result/C_apply_yext/set_regular_hours.py              # SinceAI13 on the sandbox
    python3 result/C_apply_yext/set_regular_hours.py --dry-run    # show what would be sent, no PUT
    python3 result/C_apply_yext/set_regular_hours.py --force      # PUT even if the entity already has hours

Flow: GET the entity -> if it has no weekday hours (or --force), PUT regular_hours.json -> GET again and check
that meta.errors is empty and the weekday hours match. Existing holidayHours are kept.
"""
import argparse
import sys

from yext_common import config, errors, load_regular, request, show, weekly


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", help="entity id (default YEXT_ENTITY_ID or SinceAI13)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cfg = config(a.entity)
    regular = load_regular()
    st, r = request(cfg, "GET")
    if st != 200 or errors(r):
        sys.exit(f"GET {cfg['entity']}: HTTP {st} {errors(r)}")
    ent = r.get("response", {})
    hours = ent.get("hours") or {}
    print(f"GET {cfg['entity']} ({ent.get('name')!r}, {(ent.get('address') or {}).get('city')!r}): current hours")
    show(hours)
    has_weekly = any(hours.get(d) for d in weekly(hours))
    if has_weekly and not a.force:
        print("The entity already has weekday hours: nothing to do (use --force to overwrite them).")
        return
    body = {"hours": {**regular, "holidayHours": hours.get("holidayHours", [])}}
    if a.dry_run:
        print("DRY RUN: would PUT these hours:")
        show(body["hours"])
        return
    st, r = request(cfg, "PUT", body)
    if st not in (200, 201) or errors(r):
        sys.exit(f"PUT {cfg['entity']}: HTTP {st} {errors(r)}")
    st, r = request(cfg, "GET")
    after = (r.get("response") or {}).get("hours") or {}
    ok = st == 200 and not errors(r) and weekly(after) == weekly(regular)
    print(f"PUT done. GET again: HTTP {st}, meta.errors {errors(r)}, weekday hours match: {weekly(after) == weekly(regular)}")
    show(after)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
