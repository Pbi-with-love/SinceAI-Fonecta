# Part E — Demo and submission

| Item | Status |
|---|---|
| README following `docs/README_TEMPLATE.md` | ✅ repo root `README.md` |
| Final customer messages as text | ✅ [`../B_contact_decide/MESSAGES.md`](../B_contact_decide/MESSAGES.md) |
| Customer with no history (FI-D0017) | ✅ README section, screenshot in [`media/`](media/) |
| `predictions_2026.csv` | ✅ repo root |
| Owner app online | ✅ https://since-ai-porchlight.vercel.app (signed links from `owner_link.py`) |
| Demo video (2–3 min) | ⏳ |
| Pitch deck | ⏳ |
| Bonus: live source | not done |

## Demo storyline (FI-D0017 Kahvila Kipinä, a new customer with no history)

1. Reset: `result/C_apply_yext/reset.py` and `load_to_supabase.py --reset ... --only FI-D0017` (turn the n8n Scheduler off while recording).
2. Telegram: the SUGGEST message (Christmas Day → closed, 86 % of similar cafés closed) → Approve → "Updated! Your new
   hours will show on: Google ~2 min …".
3. Owner app from the signed link: the two ASK cards; Boxing Day → Closed; New Year's Day → Edit "10-14" → confirm → Undo.
4. Yext sandbox: the holiday hours written, read back and logged.

`media/owner_app_ask_card_fi.png`: the owner app's ASK card for Boxing Day (demo mode).
