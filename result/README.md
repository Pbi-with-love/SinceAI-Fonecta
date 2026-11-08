# result/ — our solution

| Folder | Part | Status |
|---|---|---|
| [`A_prediction_engine/`](A_prediction_engine/) | A. Prediction engine: SUGGEST / NO_ACTION / FLAG per (business, date), with basis, evidence and confidence | ✅ Closed at tag `part-a-final` (65.92 / 62.73) |
| [`B_contact_decide/`](B_contact_decide/) | B. Bundles per owner, Telegram texts, Supabase loader, owner links, all customer messages; [`owner_app/`](B_contact_decide/owner_app/) is the no-login web app | ✅ Live |
| [`C_apply_yext/`](C_apply_yext/) | C. Sandbox reset for the Yext entity; the write itself is the n8n workflow `Connect · Apply to Yext` | ✅ Verified on the sandbox |
| [`D_learning_permission/`](D_learning_permission/) | D. Standing permission (on / off) and where it is enforced; learning from decisions | ✅ Permission · ⏳ Learning |
| [`E_demo_submission/`](E_demo_submission/) | E. Demo material, screenshots | ⏳ Video and deck to come |
| [`n8n/`](n8n/) | The eight n8n workflow exports (contact, reply, router, parse edit, apply, scheduler, web action, eval) and [`WEB_ACTION.md`](n8n/WEB_ACTION.md) | ✅ |
| [`DATASET_ANALYSIS.md`](DATASET_ANALYSIS.md) | What each dataset file is and what it is for | reference |

Organisers' files (`data/`, `evaluation/`, `labels/`, `examples/`, `mock_api/`, `docs/`) stay read-only.
