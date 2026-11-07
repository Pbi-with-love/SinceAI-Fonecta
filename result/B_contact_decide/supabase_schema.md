# Supabase schema used by the n8n workflows (Part B)

Pasted by the team on 2026-11-07 from the project's `information_schema.columns`. The n8n workflow
`Connect · Step 3 Contact` reads `bundles` and `bundle_items` (status `QUEUED`) and writes `decisions`.
Workflows 4 and 5 (not in the repo yet) use `chat_sessions` and `apply_log`.

| table_name    | column_name         | data_type                |
| ------------- | ------------------- | ------------------------ |
| apply_log     | id                  | bigint                   |
| apply_log     | bundle_id           | text                     |
| apply_log     | yext_entity_id      | text                     |
| apply_log     | mode                | text                     |
| apply_log     | hours_before        | jsonb                    |
| apply_log     | hours_after         | jsonb                    |
| apply_log     | status              | text                     |
| apply_log     | error               | text                     |
| apply_log     | created_at          | timestamp with time zone |
| bundle_items  | id                  | bigint                   |
| bundle_items  | bundle_id           | text                     |
| bundle_items  | date                | date                     |
| bundle_items  | day_name            | text                     |
| bundle_items  | shown_hours         | text                     |
| bundle_items  | proposed_hours      | text                     |
| bundle_items  | final_hours         | text                     |
| bundle_items  | basis               | text                     |
| bundle_items  | evidence            | jsonb                    |
| bundle_items  | confidence          | text                     |
| bundles       | bundle_id           | text                     |
| bundles       | entity_id           | text                     |
| bundles       | business_name       | text                     |
| bundles       | yext_entity_id      | text                     |
| bundles       | owner_name          | text                     |
| bundles       | language            | text                     |
| bundles       | telegram_chat_id    | text                     |
| bundles       | opted_out           | boolean                  |
| bundles       | has_permission      | boolean                  |
| bundles       | route               | text                     |
| bundles       | status              | text                     |
| bundles       | intro_text          | text                     |
| bundles       | publishers          | jsonb                    |
| bundles       | telegram_message_id | text                     |
| bundles       | created_at          | timestamp with time zone |
| bundles       | updated_at          | timestamp with time zone |
| chat_sessions | telegram_chat_id    | text                     |
| chat_sessions | bundle_id           | text                     |
| chat_sessions | state               | text                     |
| chat_sessions | pending_changes     | jsonb                    |
| chat_sessions | expires_at          | timestamp with time zone |
| chat_sessions | updated_at          | timestamp with time zone |
| decisions     | id                  | bigint                   |
| decisions     | bundle_id           | text                     |
| decisions     | action              | text                     |
| decisions     | raw_text            | text                     |
| decisions     | parsed              | jsonb                    |
| decisions     | parser              | text                     |
| decisions     | created_at          | timestamp with time zone |
