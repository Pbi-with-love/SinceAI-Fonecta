# Part C — Apply to Yext

Demo setup scripts for the team's Yext sandbox entity **`SinceAI13`** ("Screwdriver Hardware", Pori). Standard library only.

| File | What it does |
|---|---|
| `regular_hours.json` | Regular hours for a hardware store in Pori: Mon–Fri 08:00–18:00, Sat 09:00–15:00, Sun closed |
| `set_regular_hours.py` | GET the entity → if it has no weekday hours (or `--force`), PUT `regular_hours.json` (keeps holidayHours) → GET again and check `meta.errors` is empty and the hours match |
| `reset.py` | PUT `regular_hours.json` with **no holidayHours**, then verify. Run before every video take |
| `yext_common.py` | Shared helpers |

Environment (from the git-ignored `.env`): `YEXT_API_KEY` (sent in the `api-key` header, never printed or put in a URL),
`YEXT_BASE_URL` (`https://sbx-api.yextapis.com`), `YEXT_VERSION` (default **`20261106`** for the sandbox; the organisers'
mock uses `20261101`), `YEXT_ENTITY_ID` (default `SinceAI13`). Every script has `--dry-run` (GET only, no PUT) and `--entity`.

```bash
set -a; source .env; set +a
python3 result/C_apply_yext/set_regular_hours.py --dry-run
python3 result/C_apply_yext/set_regular_hours.py
python3 result/C_apply_yext/reset.py
```

Tested only against the organisers' mock (`python mock_api/server.py`, entity `FI-D0001`, then `POST /mock/reset`).
Never run against the sandbox by an agent; the human runs the real PUTs.
