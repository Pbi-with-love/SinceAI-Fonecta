# Part D — Standing permission (and learning)

## Standing permission: built

An owner can let Porchlight update holiday hours without asking. Where it lives:

| Piece | Where |
|---|---|
| Initial value | `data/customer_contacts.csv` `standing_permission_holidays` → `bundles.has_permission` (`build_bundles.py`) |
| Who may be auto-applied | `build_bundles.py`: route `AUTO_APPLY` only when the owner has permission **and every item is HIGH confidence** (the business's own history or its shopping centre). Peer-only and old-season suggestions are always asked |
| Granting in Telegram | After the first approved update the bot offers "Shall we handle holidays for you from now on?" (`Connect · Step 4 Telegram router`, `Set has_permission`) |
| Granting and revoking in the web app | The "Automatic" switch: `PERMISSION` turns it on after a confirmation sheet, `REVOKE` turns it off (`Connect · Web action`, all bundles of the business) |
| Applying | `Connect · Step 3 Contact`, lane AUTO_APPLY: final = proposed, write to Yext, then tell the owner with an Undo button |
| Opt-out | `opted_out_of_suggestions` → the n8n Route Guard skips the owner entirely |

## Learning from decisions: 

Every decision is stored (`decisions`: approve / edit / decline / undo, parser, time; `apply_log`: hours before and
after), and `data/pilot_decision_log_2025.csv` holds the 2025 pilot. A next step would read them per basis and
confidence (for example, move a basis that owners often decline from SUGGEST to ASK) and invite owners who approve
everything to grant permission. The owner's own answers already feed back next season: an approved or edited date
becomes the business's history, so a new customer is asked once and then gets HIGH-confidence suggestions.
