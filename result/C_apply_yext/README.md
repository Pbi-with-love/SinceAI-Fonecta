# Part C — Apply to Yext

The real write to Yext is done by the n8n workflow `Connect · Apply to Yext` (`result/n8n/`): GET the entity, replace only
the bundle's holiday dates, PUT, GET again and compare, log in `apply_log`, Undo restores the exact previous hours.

This folder only prepares the team's sandbox entity **`SinceAI13`** ("Screwdriver Hardware", Pori) for a demo. Standard library only.

| File | What it does |
|---|---|
| `reset.py` | PUT `regular_hours.json` with **no holidayHours**, then GET again and verify. Run before every video take |
| `regular_hours.json` | The regular hours `reset.py` writes: those of the demo business **FI-D0017 Kahvila Kipinä** (Mon–Fri 08:00–17:00, Sat 10:00–16:00, Sun closed, from `data/regular_hours_history.jsonl`), so the "shown now" hours in its Telegram messages match the sandbox |
| `yext_common.py` | Shared helpers (config from the environment, HTTP calls, hour comparison) |

Environment (from the git-ignored `.env`): `YEXT_API_KEY` (sent in the `api-key` header, never printed or put in a URL),
`YEXT_BASE_URL` (`https://sbx-api.yextapis.com`), `YEXT_VERSION` (default `20261106`; the organisers' mock uses `20261101`),
`YEXT_ENTITY_ID` (default `SinceAI13`). Options: `--dry-run` (GET only, no PUT) and `--entity`.

```bash
set -a; . ./.env; set +a
python3 result/C_apply_yext/reset.py --dry-run
python3 result/C_apply_yext/reset.py
```

Tested only against the organisers' mock (`python mock_api/server.py`, entity `FI-D0001`, then `POST /mock/reset`).
Never run against the sandbox by an agent; the human runs the real PUTs.
