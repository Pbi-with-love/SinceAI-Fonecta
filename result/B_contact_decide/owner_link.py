#!/usr/bin/env python3
"""Print the no-login owner-app link for one or more businesses (standard library only).

token = first 32 hex chars of HMAC-SHA256(entity_id, LINK_SECRET), the same as Frontend/src/lib/connect/api.ts.
LINK_SECRET comes from the environment and is never printed.

    set -a && . ./.env && set +a
    python3 result/B_contact_decide/owner_link.py FI-D0017 --base https://<your-app-domain>
"""
import argparse
import hashlib
import hmac
import os
import sys


def token(entity_id, secret):
    return hmac.new(secret.encode(), entity_id.encode(), hashlib.sha256).hexdigest()[:32]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entities", nargs="+")
    ap.add_argument("--base", default=os.environ.get("OWNER_APP_URL", "http://localhost:5180"))
    a = ap.parse_args()
    secret = os.environ.get("LINK_SECRET")
    if not secret:
        sys.exit("error: set LINK_SECRET in the environment")
    for e in a.entities:
        print(f"{a.base.rstrip('/')}/o/{e}?t={token(e, secret)}")


if __name__ == "__main__":
    main()
