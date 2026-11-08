# Part B — Contact & decide: bundle builder (dry run)

`build_bundles.py` turns Part A's `explain_full()` output (season 2026, snapshot 2026-11-06) into rows for the Supabase
tables `bundles` and `bundle_items` (columns exactly as in `supabase_schema.md`). It writes JSON files only. No Supabase,
Telegram or Yext call. Python standard library only; Part A is imported read-only (`model.Baseline(2026).explain_full()`).

## Run

```bash
python result/B_contact_decide/build_bundles.py                      # the 17 demo businesses (data/splits.csv split "demo")
python result/B_contact_decide/build_bundles.py --entities FI-D0001,FI-D0011
python result/B_contact_decide/build_bundles.py --validate-only result/B_contact_decide/samples/bundles_demo.json
```

Outputs (committed): `samples/bundles_demo.json` (`{"bundles": [...], "bundle_items": [...]}`, sorted, no `id`,
no `created_at`/`updated_at`) and `samples/bundles_demo_summary.md` (table + every intro text, for human review).
The validator runs on every build and the script exits non-zero (writing nothing) if it fails. Two runs give byte-identical files.

## Rows and routes

Every target row of `evaluation/targets_2026.csv` whose `explain_full()` action is `SUGGEST` or `FLAG` becomes one
`bundle_items` row. `NO_ACTION` rows produce nothing. The n8n workflow handles one route per bundle, so per business:

| Items | Bundle | Route |
|---|---|---|
| any `FLAG` | all FLAG items, `proposed_hours` null | `STAFF` |
| `SUGGEST` with confidence HIGH or MEDIUM, basis not `OLDER_SEASON` | one bundle | `AUTO_APPLY` if `has_permission` **and every item is HIGH**, else `SUGGEST` |
| `SUGGEST` with confidence LOW (peer-only) **or basis `OLDER_SEASON`** | one separate bundle | `ASK` |

`OLDER_SEASON` items rest on one entry from three or more seasons back (70 % exact, 16 % wrong state on dev), so they are
asked, never proposed and never auto-applied (human decision, 2026-11-07). Their line quotes the real evidence, e.g.
`Välipäivä, ma 28.12., …: 08:00–16:00 → suljettu? Vuonna 2023 olitte kiinni tänä päivänä. Entä tänä vuonna?`
("In 2023 you were closed on this day. What about this year?"). Part A's `model.py` is unchanged.

`bundle_id` = `B-<entity_id>-<route>`. `opted_out` / `has_permission` come from `data/customer_contacts.csv`
(`opted_out_of_suggestions`, `standing_permission_holidays`) and are set honestly; the route is still computed
(the workflow's Route Guard turns an opted-out owner into SKIP; we do not duplicate that). No demo owner has opted out.

## Field sources

| Column | Source |
|---|---|
| `business_name` | `data/entities.json` `name` |
| `owner_name`, `language` | `customer_contacts.csv` `contact_first_name`, `preferred_language` (the owner's choice, not the country: FI-D0010 is a Finnish pub whose owner prefers `sv`) |
| `publishers` | `data/listings.json` for the entity: `publisherId`, `publisherName`, `typicalUpdateSpeedSeconds`, sorted by id |
| items `shown_hours`, `proposed_hours`, `basis`, `confidence`, `evidence`, `day_name` | `explain_full()` (evidence and `day_name` stay English: staff/audit trail) |
| `final_hours` | null (the workflow fills it) |
| `status` | `QUEUED`; `telegram_message_id` null |
| `intro_text` | fixed templates in fi / sv / nb / en (no LLM). STAFF text is always an internal English note |

`intro_text` lists each item as `<holiday name>, <weekday date>: <shown> → <proposed> (<reason from basis>)`. Dates with the
same name, hours and basis are grouped on one line, at most 8 item lines are shown and the rest become a "… and N more days"
line (all items are still in `bundle_items`). Holiday names come from `calendar_special_days.csv` `name_local` when the owner's
language is the country's own; otherwise `name_local (name_en)`. Event nights and school breaks are not in the calendar, so they
use fixed localised phrases.

## What is fake

- `telegram_chat_id` = `FAKE-<entity_id>`. Real chat ids come from the human. The validator insists on the `FAKE-` prefix.
- `yext_entity_id` = `entity_id` (the organisers' mock uses the same id). A real Yext account needs the real id.
- All owner names and languages are synthetic data.

## Validator (inside `build_bundles.py`)

Checks: columns equal the schema columns of each table minus database defaults (no extra, none missing) and value types;
unique `bundle_id`; every bundle has items and every item a bundle; routes in `SKIP/STAFF/AUTO_APPLY/SUGGEST/ASK`;
`ASK` only LOW, `SUGGEST`/`AUTO_APPLY` never LOW, `AUTO_APPLY` only HIGH with permission; hours match `closed` or
`HH:MM-HH:MM[,HH:MM-HH:MM]`; `final_hours` null; `proposed_hours` null only for STAFF; intro text ≤ 12 lines and every item's
date, shown and proposed hours appear in a matching line (no time in the text that is not in an item).

## The n8n workflows (`result/n8n/`, final version)

The bundles are consumed by seven n8n workflows (exports, inactive; credentials stay in n8n, not in the files):

| Workflow | What it does with the bundles |
|---|---|
| `Connect · Scheduler` | Daily 10:00 Helsinki (or webhook with `as_of` for the demo). Per bundle: deadline = next holiday − slowest main channel − 1 day; first message from deadline − 14 days (via Step 3); STAFF at once, once; one reminder 4 days after sending, at the latest deadline − 2 days (logged as `REMIND_1` in `decisions`) |
| `Connect · Step 3 Contact` | Sends `QUEUED` bundles: SKIP (opt-out / no chat), STAFF (posted once, `STAFF_FLAGGED` in `decisions`), AUTO_APPLY (final = proposed, `APPROVED`, Apply to Yext), SUGGEST / ASK (`intro_text` + 3 buttons, `SENT` when Telegram confirms) |
| `Connect · Step 4 Telegram router` | Every button press and reply; only the bundle's own chat counts; state guard; free text → Parse edit → confirm card; writes `final_hours`, `decisions`, `chat_sessions`, can grant `has_permission` |
| `Connect · Parse edit` | Gemini 2.5 Flash (temperature 0, structured output) reads the owner's free text, then a validator keeps only dates of the bundle and valid hours; otherwise `UNCLEAR` |
| `Connect · Apply to Yext` | GET entity → replace only this bundle's holiday dates → PUT → GET and compare; `apply_log` with hours before/after; Undo writes back the exact previous hours; tells the owner where the new hours show from `publishers` (`typicalUpdateSpeedSeconds`) |
| `Connect · Reply` | All bot texts (fi/sv/nb/en), send or edit a Telegram message with 1–3 buttons |
| `Connect · Eval harness` | Tests the parser and guards without Yext or Telegram |

### Columns used by `Connect · Step 3 Contact`

- Reads `bundles` where `status = QUEUED`, then `bundle_items` by `bundle_id`; uses `route`, `opted_out`, `telegram_chat_id`,
  `language`, `intro_text`, `entity_id`, `business_name`, `bundle_id`, and item `id`, `proposed_hours`. All present. `id` is
  assigned by the database on insert (we do not send it).
- Writes back `status` (`SENT`, `SKIPPED`, `APPROVED`), `telegram_message_id`, `updated_at`, item `final_hours`, and `decisions`.
- Route Guard sends a bundle to SKIP when `telegram_chat_id` is empty, so the fake placeholder is non-empty on purpose.
- `Intro Payload` only accepts `language` in fi/sv/nb/en. All our bundles comply.

## Loading into Supabase (`load_to_supabase.py`)

Standard library only, Supabase REST API. Reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from the environment; the key is
only sent as a header, never printed or written. Loads `bundles`, then `bundle_items`, then prints a summary.

| Option | Effect |
|---|---|
| `--chat-id <id>` | overrides `telegram_chat_id` of every bundle (otherwise `FAKE-<entity_id>`, with a warning) |
| `--yext-entity SinceAI13` | overrides `yext_entity_id` of every bundle |
| `--only FI-D0007,FI-D0017` | loads only these businesses |
| `--reset` | first deletes ALL rows of `decisions`, `apply_log`, `chat_sessions`, `bundle_items`, `bundles` |
| `--dry-run` | no network call |

Without `--reset`, loading a `bundle_id` that already exists fails (HTTP 409). Tested only with `--dry-run` and a local fake server.

## Owner app helpers

- `export_frontend_data.py` writes `Frontend/src/lib/connect/reference.generated.ts` (holiday names per language from the
  calendar, the `REASON` texts) and `demo.generated.ts` (this folder's `samples/bundles_demo.json`, used in demo mode).
  Re-run it after `build_bundles.py`.
- `owner_link.py FI-D0017 --base https://<app>` prints the no-login link `/o/<entity_id>?t=<token>` (HMAC with
  `LINK_SECRET` from the environment, never printed).

## Known limitations

- **Seasonal closures are not covered.** `FI-D0006` (summer terrace that forgot its winter closure) gets no bundle: Part A
  has no rule for seasonal closures, and the organisers list them as signals, not scored targets
  (`docs/ASSUMPTIONS_AND_LIMITATIONS.md`). A separate "reopen date" message would be needed.
- **AUTO_APPLY `intro_text` is not sent as such.** After applying, n8n tells the owner with its own `msg_auto_applied`
  template (in `Connect · Reply`) plus the item lines and an Undo button. Our AUTO text stays in the row for staff review.

## Wording for a native-speaker check

Fixed on 2026-11-07: sv `från för två år sedan` → `för två år sedan`; nb `fra for to år siden` → `for to år siden`.
The ASK opening was changed from a "guess" to "we'd like to double-check" (fi/sv/nb/en). Still to check (all strings are in `build_bundles.py`, constants `REASON`, `TEXT`, `OLDER_QUESTION`, `MORE`):

| Lang | Text | Doubt |
|---|---|---|
| sv | `så gör liknande företag` | as a reason in brackets it may read oddly; maybe `liknande företag brukar göra så` |
| sv | `recensioner eller ändringar tyder på nedläggning` | register (staff only in practice) |
| sv | `År {y} hade ni stängt den här dagen. Hur blir det i år?` | natural? |
| nb | `slik gjør lignende bedrifter` | word order / naturalness |
| nb | `I {y} holdt dere stengt denne dagen. Hva gjelder i år?` | natural? |
| nb | `i tråd med din tillatelse har vi oppdatert …` | formal enough / too formal? |
| fi | `Vuonna {y} olitte kiinni tänä päivänä. Entä tänä vuonna?` | natural? |
| fi | `muiden pyhäpäivien perusteella` | reason for OWNER_PATTERN; clear enough? |

## Open questions

1. ~~STAFF bundles are re-posted~~: resolved in n8n. STAFF stays `QUEUED`, and a `STAFF_FLAGGED` row in `decisions` stops repeat alerts.
2. ~~AUTO_APPLY `intro_text`~~: resolved, n8n uses its own `msg_auto_applied` template (see Known limitations).
3. ~~`msg_staff_flag` template not seen~~: it lives in `Connect · Reply` (`result/n8n/`).
4. ~~FI-D0013 gets a SUGGEST bundle~~: resolved, OLDER_SEASON items are now asked; FI-D0013 gets one ASK bundle (3 INTERDAY dates).
5. FI-D0010 has 16 items (event nights dominate); the message shows 8 lines and "… and 2 more days". Should event nights be a separate bundle, or limited to the next N days?
6. A permission holder (FI-D0003) gets an AUTO_APPLY bundle for its HIGH items and a separate ASK bundle for LOW ones, so the owner receives two messages. Acceptable?
7. Reasons are generated per basis, not per item; a business-specific explanation (e.g. "you closed on every other public holiday") is not in the text (it is in `evidence`).
8. Finnish/Swedish/Norwegian wording was written by the agent, not reviewed by a native speaker (see the table above).
