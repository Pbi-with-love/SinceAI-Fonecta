# `Connect · Web action` — spec for the owner app's webhook

The owner app (`result/B_contact_decide/owner_app/`, no login) sends each decision to this n8n workflow. It must reuse the existing
`Connect · Apply to Yext` sub-workflow, so a decision made in the app and one made in Telegram end in the same
tables, the same Yext write, the same `apply_log` and the same Undo.

The app's server function (`result/B_contact_decide/owner_app/src/lib/connect/api.ts`) has already checked the signed link and that the
bundle belongs to the entity before it calls this webhook. The webhook URL itself is a secret (it lives only in the
app's server environment as `N8N_WEB_ACTION_URL`).

## Request

`POST <webhook>` with `Content-Type: application/json`:

```json
{ "source": "web", "entity_id": "FI-D0017", "bundle_id": "B-FI-D0017-SUGGEST",
  "action": "APPROVE", "date": "2026-12-25", "hours": "closed" }
```

| Field | Values |
|---|---|
| `action` | `APPROVE`, `EDIT`, `DECLINE`, `REGULAR`, `UNDO`, `PERMISSION`, `REVOKE` |
| `date` | `YYYY-MM-DD`, one `bundle_items.date` of the bundle. Null for `PERMISSION` and `REVOKE` |
| `hours` | `closed`, `regular` or `HH:MM-HH:MM[,HH:MM-HH:MM]`. Null for `DECLINE`, `UNDO`, `PERMISSION`, `REVOKE` |
| `undo_of` | `"DECLINE"` when the app undoes a decline, otherwise null |

One request = one date (one swipe). The app sends `APPROVE` with `hours = proposed_hours`, `REGULAR` with
`hours = "regular"` (left swipe on an ASK card, "open as usual") and `EDIT` with the hours the owner typed.

## What each action does

Validate first: the bundle exists, `route` is `SUGGEST`, `ASK` or `AUTO_APPLY`, `date` belongs to the bundle and
`hours` matches the format. On failure answer `{ "ok": false, "error": "<CODE>" }` and change nothing.

| Action | Writes | Then |
|---|---|---|
| `APPROVE`, `EDIT`, `REGULAR` | `bundle_items.final_hours = hours` for that date; `bundles.status = APPROVED`, `updated_at = now` | Execute `Connect · Apply to Yext` with `{ bundle_id, mode: "APPLY", notify: "NONE", YEXT_BASE_URL, YEXT_VERSION, TELEGRAM_STAFF_CHAT_ID, UNDO_WINDOW_HOURS }` (same inputs as the router's `Run Apply`) |
| `DECLINE` | nothing on the item (`final_hours` stays null) | no Yext call |
| `UNDO` | Execute `Apply to Yext` with `mode: "UNDO"`; on success set `bundle_items.final_hours = null` for that date | the date returns to the app's deck |
| `UNDO` with `undo_of = "DECLINE"` | nothing (a decline never reached Yext); only the `UNDO` decisions row | the date returns to the app's deck. Calling Apply UNDO here would restore the hours before the latest write, which belongs to another date |
| `PERMISSION` | `bundles.has_permission = true` for every bundle of `entity_id` (same as the router's `Set has_permission`) | no Yext call |
| `REVOKE` | `bundles.has_permission = false` for every bundle of `entity_id` (same node, opposite value) | no Yext call; the app's switch turns off |

Every action inserts one `decisions` row, which is how the app knows a date was decided after a reload:

```json
{ "bundle_id": "...", "action": "<action>", "raw_text": "web:<action>:<date>",
  "parsed": { "date": "2026-12-25", "hours": "closed" }, "parser": "WEB" }
```

`parsed.date` is required for the per-date actions (the app reads it); `UNDO` rows are logged too, because the
latest decision for a date wins and an `UNDO` puts the date back in the deck.

## Response

`200` with `{ "ok": true }` when the write (and, for APPLY / UNDO, the Yext read-back in `Apply to Yext`) succeeded;
otherwise `{ "ok": false, "error": "<CODE>" }` (`APPLY_FAILED`, `UNDO_WINDOW_EXPIRED`, `STATUS_<status>`, `BAD_DATE`,
`BAD_HOURS`, ...). The app shows "Could not save" and puts the card back when `ok` is false. Use a `Respond to
Webhook` node at the end, after `Apply to Yext` returns.

## How the app sends (one request at a time)

`Apply to Yext` takes a few seconds and the workflow answers `BUSY` while a write for the bundle runs. The app removes
the card at once but sends its requests **one after another, in swipe order**, shows "Saving n…", and retries a
`BUSY` (a write started from Telegram) up to 3 times, 2.5 s apart. Only a failed save puts the card back. Undo is
offered once, for the latest decision of the session, because Apply can only undo its own last write.

## Why per date works with the existing Apply

- `Apply to Yext` only runs `APPLY` when the bundle is `APPROVED`, and it writes every item that has a `final_hours`
  (only the holiday dates of this bundle). Setting the status back to `APPROVED` before each call lets the owner swipe
  the dates one by one; earlier dates are written again with the same hours (no change).
- A declined date keeps `final_hours = null`, so Apply never writes it.
- `UNDO` restores `hours_before` of the bundle's latest successful `APPLY` row, i.e. the last swipe. The app only offers
  Undo on the last decision of the session, so the two agree. Clearing `final_hours` afterwards keeps the next APPLY
  from writing the undone date again.

## Known gaps (MVP)

- A web `DECLINE` does not change the bundle status. A bundle whose dates were all declined in the app stays
  `QUEUED` / `SENT`, so `Connect · Scheduler` may still send the first message or the reminder. Turn the Scheduler
  off during the demo, or set `status = DECLINED` once every date of the bundle has a decision.
- After the first applied date the bundle is `APPLIED`, so the Scheduler stops reminding about the dates still open.
- No header auth on the webhook (decided for the MVP).

## One change in `Connect · Apply to Yext`

With `notify: "NONE"` the owner is already looking at the app, so the Telegram "updated" message is not needed. In
`Build Replies`, return no owner message when `$('Apply Input').first().json.notify === "NONE"` (staff error
messages stay). Telegram calls keep `notify: "OWNER"` / `"AUTO"` and are unaffected.

## The link in the Telegram message

The app's link is `https://<app>/o/<entity_id>?t=<token>`, with `token` = the first 32 hex characters of
`HMAC-SHA256(entity_id, LINK_SECRET)`. `result/B_contact_decide/owner_link.py` prints it; in n8n the Crypto node
(HMAC, SHA256, hex) gives the same value. Add it as a URL button ("Open Connect Suggests") to the intro message in
`Connect · Reply` if you want the owner to choose between the buttons and the app.
