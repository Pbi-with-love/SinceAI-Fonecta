"""Shared helpers for the Part C Yext scripts. Standard library only.

Environment: YEXT_API_KEY (never printed), YEXT_BASE_URL (e.g. https://sbx-api.yextapis.com, or
http://localhost:8787 for the organisers' mock), optional YEXT_VERSION (default 20261106 for the sandbox),
optional YEXT_ENTITY_ID (default SinceAI13). The key is sent in the `api-key` header, never in the URL.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def config(entity_arg=None):
    key = os.environ.get("YEXT_API_KEY", "")
    base = os.environ.get("YEXT_BASE_URL", "").rstrip("/")
    if not key or not base:
        sys.exit("Set YEXT_API_KEY and YEXT_BASE_URL (e.g. `set -a; source .env; set +a`).")
    if base.endswith("/v2/accounts/me"):
        base = base[: -len("/v2/accounts/me")]
    return {"key": key, "base": base, "v": os.environ.get("YEXT_VERSION", "20261106"),
            "entity": entity_arg or os.environ.get("YEXT_ENTITY_ID", "SinceAI13")}


def request(cfg, method, body=None):
    url = f"{cfg['base']}/v2/accounts/me/entities/{urllib.parse.quote(cfg['entity'])}?v={cfg['v']}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"api-key": cfg["key"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {"meta": {"errors": [{"message": "non-JSON error body"}]}}


def errors(resp):
    return (resp.get("meta") or {}).get("errors") or []


def load_regular():
    with open(os.path.join(HERE, "regular_hours.json"), encoding="utf-8") as f:
        return json.load(f)


def weekly(hours):
    """Only the seven weekday entries, for comparing."""
    return {d: (hours or {}).get(d) for d in DAYS}


def show(hours):
    for d in DAYS:
        v = (hours or {}).get(d)
        txt = "closed" if (v or {}).get("isClosed") else ", ".join(f"{i['start']}-{i['end']}" for i in (v or {}).get("openIntervals", [])) or "-"
        print(f"    {d:<10}{txt}")
    print(f"    holidayHours: {len((hours or {}).get('holidayHours', []))}")
