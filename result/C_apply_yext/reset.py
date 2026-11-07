#!/usr/bin/env python3
"""Reset a Yext entity to regular_hours.json and remove every holidayHours entry. Run before each video take.

    set -a; source .env; set +a
    python3 result/C_apply_yext/reset.py              # SinceAI13 on the sandbox
    python3 result/C_apply_yext/reset.py --dry-run    # show current and target hours, no PUT
"""
import argparse
import sys

from yext_common import config, errors, load_regular, request, show, weekly


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", help="entity id (default YEXT_ENTITY_ID or SinceAI13)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = config(a.entity)
    regular = load_regular()
    st, r = request(cfg, "GET")
    if st != 200 or errors(r):
        sys.exit(f"GET {cfg['entity']}: HTTP {st} {errors(r)}")
    print(f"GET {cfg['entity']}: current hours")
    show((r.get("response") or {}).get("hours") or {})
    body = {"hours": {**regular, "holidayHours": []}}
    if a.dry_run:
        print("DRY RUN: would PUT:")
        show(body["hours"])
        return
    st, r = request(cfg, "PUT", body)
    if st not in (200, 201) or errors(r):
        sys.exit(f"PUT {cfg['entity']}: HTTP {st} {errors(r)}")
    st, r = request(cfg, "GET")
    after = (r.get("response") or {}).get("hours") or {}
    ok = st == 200 and not errors(r) and weekly(after) == weekly(regular) and not after.get("holidayHours")
    print(f"Reset done. GET again: HTTP {st}, meta.errors {errors(r)}, weekday hours match: "
          f"{weekly(after) == weekly(regular)}, holidayHours left: {len(after.get('holidayHours', []))}")
    show(after)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
