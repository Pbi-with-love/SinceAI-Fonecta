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
| `SUGGEST` with confidence HIGH or MEDIUM | one bundle | `AUTO_APPLY` if `has_permission` **and every item is HIGH**, else `SUGGEST` |
| `SUGGEST` with confidence LOW (peer-only) | one separate bundle | `ASK` |

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

## Fit with the n8n workflow `Connect · Step 3 Contact` (read-only check)

- Reads `bundles` where `status = QUEUED`, then `bundle_items` by `bundle_id`; uses `route`, `opted_out`, `telegram_chat_id`,
  `language`, `intro_text`, `entity_id`, `business_name`, `bundle_id`, and item `id`, `proposed_hours`. All present. `id` is
  assigned by the database on insert (we do not send it).
- Writes back `status` (`SENT`, `SKIPPED`, `APPROVED`), `telegram_message_id`, `updated_at`, item `final_hours`, and `decisions`.
- Route Guard sends a bundle to SKIP when `telegram_chat_id` is empty, so the fake placeholder is non-empty on purpose.
- `Intro Payload` only accepts `language` in fi/sv/nb/en. All our bundles comply.

## Open questions

1. **STAFF bundles stay `QUEUED`** (workflow sticky note). Every webhook run re-posts the same flag to the staff chat. Does the human want a status such as `STAFF_NOTIFIED` set after posting?
2. **AUTO_APPLY `intro_text` is not sent** by this workflow (the AUTO lane goes straight to "Apply to Yext", which tells the owner with an Undo button). Our AUTO text is written for that follow-up message; confirm that workflow uses it or ignore it.
3. The STAFF payload uses key `msg_staff_flag` with `params.text = intro_text`; that template lives in the `Connect · Reply` workflow, which we have not seen.
4. FI-D0013 (marked "already correct" in the demo notes) still gets one SUGGEST bundle: 3 INTERDAY dates (28–30 Dec) from an OLDER_SEASON entry (Dec 2023, `closed`), confidence HIGH. That is Part A's prediction, passed through unchanged. Worth a human look before the demo.
5. FI-D0010 has 16 items (event nights dominate); the message shows 8 lines and "… and 2 more days". Should event nights be a separate bundle, or limited to the next N days?
6. A permission holder (FI-D0003) gets an AUTO_APPLY bundle for its HIGH items and a separate ASK bundle for LOW ones, so the owner receives two messages. Acceptable?
7. Reasons are generated per basis, not per item; a business-specific explanation (e.g. "you closed on every other public holiday") is not in the text (it is in `evidence`).
8. Finnish/Swedish/Norwegian wording was written by the agent, not reviewed by a native speaker.
