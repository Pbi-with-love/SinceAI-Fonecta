#!/usr/bin/env python3
"""Load the bundle JSON from build_bundles.py into Supabase (REST API, standard library only).

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from the environment. The key is only sent as a request header:
it is never printed, logged or written to a file.

  python load_to_supabase.py --dry-run
  python load_to_supabase.py --chat-id 123456789 --yext-entity SinceAI13 --only FI-D0007,FI-D0017 --reset
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILE = os.path.join(HERE, "samples", "bundles_demo.json")
# Delete order for --reset: children first. (table, filter that matches every row)
RESET = [
    ("decisions", "id=gt.0"),
    ("apply_log", "id=gt.0"),
    ("chat_sessions", "telegram_chat_id=not.is.null"),
    ("bundle_items", "id=gt.0"),
    ("bundles", "bundle_id=not.is.null"),
]
BATCH = 200


def load_rows(path, only, chat_id, yext_entity):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    bundles, items = data["bundles"], data["bundle_items"]
    if only:
        unknown = only - {b["entity_id"] for b in bundles}
        if unknown:
            sys.exit("error: --only entities with no bundle: " + ", ".join(sorted(unknown)))
        bundles = [b for b in bundles if b["entity_id"] in only]
    keep = {b["bundle_id"] for b in bundles}
    items = [i for i in items if i["bundle_id"] in keep]
    for b in bundles:
        if chat_id:
            b["telegram_chat_id"] = chat_id
        if yext_entity:
            b["yext_entity_id"] = yext_entity
    return bundles, items


class Client:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.headers = {"apikey": key, "Authorization": "Bearer " + key,
                        "Content-Type": "application/json", "Prefer": "return=minimal"}

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url + "/rest/v1/" + path, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            sys.exit(f"error: {method} {path.split('?')[0]} -> HTTP {e.code}: {detail}")
        except urllib.error.URLError as e:
            sys.exit(f"error: {method} {path.split('?')[0]} failed: {e.reason}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=DEFAULT_FILE, help="bundles JSON (default: samples/bundles_demo.json)")
    ap.add_argument("--chat-id", help="override telegram_chat_id of every bundle")
    ap.add_argument("--yext-entity", help="override yext_entity_id of every bundle (e.g. SinceAI13)")
    ap.add_argument("--only", help="comma-separated entity ids, e.g. FI-D0007,FI-D0017")
    ap.add_argument("--reset", action="store_true",
                    help="delete decisions, apply_log, chat_sessions, bundle_items, bundles (ALL rows) before loading")
    ap.add_argument("--dry-run", action="store_true", help="no network call; show what would happen")
    a = ap.parse_args()

    only = {e.strip() for e in a.only.split(",") if e.strip()} if a.only else None
    bundles, items = load_rows(a.file, only, a.chat_id, a.yext_entity)
    if not bundles:
        sys.exit("error: nothing to load")
    if not a.chat_id:
        print("warning: no --chat-id, telegram_chat_id stays FAKE-<entity_id>; Telegram will not reach anyone", file=sys.stderr)

    tag = "[dry-run] " if a.dry_run else ""
    client = None
    if not a.dry_run:
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            sys.exit("error: set SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment")
        client = Client(url, key)

    if a.reset:
        for table, flt in RESET:
            print(f"{tag}DELETE all rows of {table}")
            if client:
                client.call("DELETE", f"{table}?{flt}")
    for table, rows in (("bundles", bundles), ("bundle_items", items)):
        print(f"{tag}INSERT {len(rows)} rows into {table}")
        if client:
            for i in range(0, len(rows), BATCH):
                client.call("POST", table, rows[i:i + BATCH])

    print(f"\n{tag}summary: {len(bundles)} bundles, {len(items)} bundle_items")
    for b in bundles:
        n = sum(1 for i in items if i["bundle_id"] == b["bundle_id"])
        print(f"  {b['bundle_id']:<26} route={b['route']:<10} lang={b['language']} items={n:<3} "
              f"chat={b['telegram_chat_id']} yext={b['yext_entity_id']}")


if __name__ == "__main__":
    main()
