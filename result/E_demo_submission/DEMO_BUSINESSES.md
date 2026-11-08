# The 17 demo businesses: what Porchlight does

The organisers' storylines are in `docs/DEMO_SCENARIOS.md`. The right column is what our system produces today: the
bundles built by `result/B_contact_decide/build_bundles.py` from the frozen engine (`samples/bundles_demo.json`,
readable version `samples/bundles_demo_summary.md`). Routes: `SUGGEST` proposes hours, `ASK` asks a question,
`AUTO_APPLY` applies with standing permission and informs, `STAFF` goes to Fonecta staff only.

| Business | Storyline (organisers) | What Porchlight does | Verdict |
|---|---|---|---|
| FI-D0001 Kahvila Aurora | Last year's exceptions only partly entered, nothing for this year | `SUGGEST` 4 days from its own last-year and two-seasons-ago entries (Christmas Eve 07:30–13:00, Christmas Day and New Year closed, Epiphany 10–16) | ✅ |
| FI-D0002 Ravintola Kanerva | Closed on Sundays, opens for Father's Day lunch | `SUGGEST` 5 Christmas / New Year days; `ASK` 2 (New Year's Day from peers, Epiphany Eve from 2024). Father's Day lunch is **not** caught | ⚠️ |
| FI-D0003 Kukkakauppa Kide | Florist: Father's Day Sunday opening, longer hours before Christmas | `AUTO_APPLY` 6 days (the contacts file gives this owner standing permission), incl. 23 Dec 09–20; `ASK` 2 peer-only days. Father's Day is **not** caught | ⚠️ |
| FI-D0004 Muoti Lyhty | Store in a shopping centre that has published its hours | `SUGGEST` 7 days, 4 of them following the centre's hours; `ASK` 1 old-season day | ✅ |
| FI-D0005 Suksivuokraamo Kuura | Season opening depends on snow | `SUGGEST` Father's Day closed; `ASK` 4 school-break and New Year days. Snow is not modelled | ⚠️ |
| FI-D0006 Kesäravintola Ranta | Summer terrace that forgot its winter closure | No bundle. Seasonal closures are a signal, not a scored target (`docs/ASSUMPTIONS_AND_LIMITATIONS.md`); not covered | ❌ |
| FI-D0007 Parturi-Kampaamo Helmi | Closes between Christmas and New Year | `SUGGEST` 7 days incl. 29–30 Dec closed (last year) and New Year's Day (owner's own pattern) | ✅ |
| SE-D0008 Kafé Linnea | Closed on Julafton, early opening on Lucia | `SUGGEST` Lucia 07:00–18:00, Julafton and Juldagen closed | ✅ |
| NO-D0009 Bakeri Fjord | Longer hours on lille julaften, early close on julaften, no history to copy | `SUGGEST` Christmas Day and New Year's Day closed; `ASK` Boxing Day. 23 and 24 Dec are **missed** (no history, peers not decisive) | ⚠️ |
| FI-D0010 Pub Kulma | Next to the arena, open later on event nights | `SUGGEST` 16 days, mostly event nights to 03:00 (two seasons ago); the message shows 8 lines + "… and 2 more days" | ✅ |
| FI-D0011 Pizzeria Torni | Closed for good; flag, don't suggest | `STAFF` note to Fonecta (15 dates, closure reviews); the owner gets nothing | ✅ |
| FI-D0012 Tilitoimisto Otso | Standing permission since 2025: apply, then inform | `AUTO_APPLY` 5 days (all HIGH, last year), owner informed with Undo | ✅ |
| FI-D0013 Hammasklinikka Kallio | Already entered correct hours: stay quiet | `ASK` 3 days between Christmas and New Year, from a single 2023 entry. It is a question with the real year, never a proposal, but the right move is silence | ⚠️ |
| FI-D0014 Leikkimaa Onni | Opens earlier during school holidays | `ASK` 10–21 on the days between Christmas and New Year (old season); `SUGGEST` 24–25 Dec closed | ✅ partly |
| NO-D0015 Trening Nordlys 24/7 | 24/7 gym, nothing to change | No bundle (peer closures are never applied to round-the-clock businesses) | ✅ |
| SE-D0016 Restaurang Fyren | Changed regular hours in 2026, never updated the listing | `ASK` 3 peer-only holidays. Outdated regular hours are a signal, not a scored target; not detected | ❌ |
| FI-D0017 Kahvila Kipinä | New customer, no history | `SUGGEST` Christmas Day (86 % of peers closed, MEDIUM); `ASK` Boxing Day and New Year's Day (LOW). See the README section on customers with no history | ✅ |

**10 ✅ · 5 ⚠️ · 2 ❌.** The two ❌ are the non-hours cases the organisers list as signals only. The ⚠️ rows share one
cause: a special opening (Father's Day lunch, lille julaften) or an old single entry that the engine cannot confirm.
The product sends those as questions or stays quiet, so the owner, not the engine, makes the call.
