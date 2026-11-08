# Dataset & Use-Case Analysis — Fonecta "Connect Suggests, Customer Approves"

Since AI Hackathon 2026 × Fonecta · Turku, 6–8 Nov 2026. **All data is synthetic.**

---

## 1. The use case in one paragraph

Fonecta Connect manages local businesses' listings (Google, Apple Maps, Bing, Facebook, Finder.fi, Hitta.se, Gule Sider…) through the **Yext** platform. Owners forget to enter **holiday / special-day opening hours**, so Google shows "open" when the door is locked. That causes angry customers and lost visibility in "open now" searches. Holidays are exactly when search demand peaks. The challenge is to turn Connect from a dashboard owners must remember to visit into a **proactive assistant**:

```
1. DETECT     which business × special day will show wrong hours
2. SUGGEST    the most likely correct hours (with an explanation)
3. CONTACT    the owner on their preferred channel, language and time
4. DECIDE     owner approves / edits / declines in seconds — NO LOGIN
5. APPLY      write back via the Yext API and confirm where the new hours are live
```

**Scenario clock:** today is **Fri 6 Nov 2026**. You know everything up to 5 Nov. Predict for **7 Nov 2026 → 6 Jan 2027** (Father's Day, Black Friday, Independence Day, Lucia, Christmas, NYE, Epiphany, plus event nights and school breaks).

For each `(business, date)` pick one of three actions:

| Action | Meaning |
|---|---|
| `SUGGEST` + hours | What Google shows will be wrong → send the owner a ready-made fix |
| `NO_ACTION` | What Google shows is already right → stay quiet (don't spam) |
| `FLAG` | Needs a human (e.g. the business looks closed for good) |

---

## 2. Dataset at a glance (measured)

| Item | Count |
|---|---|
| Businesses + shopping centres | **3,032** (FI 1,821 · SE 806 · NO 405) |
| Business types | 33 + `shopping_centre` |
| Cities | 28 (3 capitals, 10 large cities, 11 towns, 4 ski resorts) |
| Splits | test 2,198 · dev 802 · demo 17 · reference (centres) 15 |
| Prediction rows 2026 | **41,755** (test 30,398 · dev 11,100 · demo 257) |
| Holiday-hours history entries | 58,167 (2,970 businesses) |
| Reviews | 59,856 (18,327 have empty text) |
| Publisher suggestions | 5,843 |
| Listings | 30,320 (10 publishers per business) |
| 2025 pilot suggestions | 3,031 |

---

## 3. File-by-file: what it is and what it's for

### 3.1 Core business state — "what is published now"

#### `data/entities.json` — the master list
- **What:** 3,032 entities in Yext *Entities: List* shape: name, address, coordinates, category, regular weekly hours (`hours.monday…sunday`), holiday exceptions already entered (`hours.holidayHours[]`), `reopenDate` for seasonal closures, `closed` flag, segment, shopping-centre link, and the Connect product.
- **Facts:** 283 businesses sit inside a shopping centre. Only **206** have any holiday hours entered for the coming season. 28 have a `reopenDate`. 24 are already published as closed.
- **Used for:**
  - **Step 1 (Detect):** "what Google will show" = regular hours for that weekday unless a `holidayHours` entry overrides it. Every target date without an entry is a candidate problem.
  - The shopping-centre link (`c_shoppingCenterEntityId`) lets a store inherit its centre's published holiday hours.
  - `c_segment` and the city drive peer lookups.
- **Production source:** Yext Knowledge Graph *Entities* API (also in the mock and the sandbox).

#### `data/regular_hours_history.jsonl` — weekly hours versions
- **What:** 3,358 *published* versions of weekly schedules, each with `effective_from` (`before-2024` or a date).
- **Shape:** 2,935 businesses (97%) have **one row only** (`before-2024`, never edited). 57 have 2 rows (one published change). 40 have 7–8 rows: **seasonal businesses** alternating "closed all week" ↔ "open" every year (e.g. ski rental `FI-D0005`, summer terraces).
- **Used for:** finding **seasonal businesses** (winter breaks) and computing the hours Google shows as of the snapshot.
- **Limit:** this file holds only *published* versions. A business that changed its real hours but never updated the listing (demo `SE-D0016`) has just one `before-2024` row here. Stale regular hours have to be detected from **reviews** ("öppettiderna har ändrats") and **publisher suggestions**, not from this file. This is a detection signal, not a scored target.

#### `data/listings.json` — where each business is live
- **What:** 10 rows per business: publisher, status, `typicalUpdateSpeedSeconds`, URL.
- **Publishers:** Google, Apple Maps, Bing, Facebook, Tripadvisor, Foursquare, Waze, "AI assistants". Country-specific publishers: Finder.fi / Fonecta Caller (FI), Hitta.se / Eniro (SE), Gule Sider / 1881.no (NO).
- **Used for:** **Step 5 (Confirm).** After the write, tell the owner "live on Google in ~X min, Apple in ~Y h". It also helps with priority: if a holiday is close and a publisher is slow, act now.

### 3.2 Historical behaviour — "what did this business do before" (the strongest signal)

#### `data/holiday_hours_history.jsonl` — the audit log
- **What:** every exception ever entered since Dec 2023: `entity_id, date, day_key, holidayHours, entered_at, source`.
- **Sources:** `OWNER_UI` 53,437 · `FONECTA_SUPPORT` 2,544 · `CONNECT_SUGGESTION` 1,329 (the 2025 pilot) · `API_INTEGRATION` 857 (shopping centres).
- **Rules:** if a date has several rows, the later one wins. An entry made **on or after** the date didn't help that day (it was too late).
- **Used for:**
  - **Step 2 (Suggest):** "last year you were closed on Boxing Day → suggest closed again". This is the core of the baseline.
  - **Owner profiling:** how early and how reliably the owner enters exceptions. A diligent owner who always enters by mid-December might not need a nudge yet. A late owner does.
  - **Back-testing:** `entered_at` lets you replay the world as of 6 Nov 2025 honestly.

#### `data/pilot_decision_log_2025.csv` — how owners reacted to suggestions (FI only)
- **What:** 3,031 suggestion rows (one per business × date) sent in **761 messages to 761 businesses** in a 2025 pilot: what was shown, what was suggested, the basis, channel, language, timestamps, decision, final hours, owner comment, and whether standing permission was granted.
- **Outcomes (per suggestion row):** NO_RESPONSE **1,610 (53%)** · ACCEPTED 1,253 (41%) · REJECTED 92 · EDITED 76. Per message, **395 of 761 (52%) got no reply at all**. Bases: LAST_YEAR_EXCEPTION 1,614 · PEER_MAJORITY 1,256 · SHOPPING_CENTRE_HOURS 161. **57 businesses** granted standing permission (251 rows).
- **Used for:**
  - **Step 3 (Contact):** which channel and time actually gets replies. More than half the owners never answered, so channel choice matters.
  - **Step 2 accuracy:** which basis gets accepted vs. edited. **Edits and rejections** tell you the true hours, a free correction signal.
  - **Message design:** bundle several dates into one message (`message_id`).
  - **Standing permission:** some owners said "just do it", so apply then inform.

#### `data/customer_contacts.csv` — CRM
- **What:** per business: first name, preferred channel (EMAIL 1,273 · SMS 943 · WHATSAPP 537 · APP_PUSH 279), language (fi 1,661 · sv 795 · nb 373 · en 203), best contact window, standing permission (57), opted out (6). Emails and phones are fake.
- **Used for:** **Steps 3–4.** Message the owner in their language, on their channel, in their window. **Respect opt-outs** (never message). **Standing permission** means auto-apply and then notify (demo `FI-D0012`). The scorer ignores this, but judges will check it in the demo.

### 3.3 Crowd & customer signals — "is something already wrong?"

#### `data/reviews.json` — 59,856 reviews (fi / sv / nb / en)
- **What:** Yext review shape: rating, text, date, publisher, owner replies.
- **Ratings:** mostly 4–5 stars. 2,231 one-star and 3,789 two-star. 18,327 have no text.
- **Signal inside:** complaints like *"Tultiin uudenvuodenpäivänä… ovi oli kiinni"* or *"stängt på nyårsdagen, trots att Google sa öppet"*. These are evidence the business was **closed on a holiday last year while listed open**, or is **closed for good**.
- **Used for:** **Detect + Suggest** in the no-history case. It's a multilingual text-classification job, a good fit for an LLM. Watch out: some reviews are deliberately misleading.

#### `data/publisher_suggestions.json` — user edits from Google / Apple / Bing / Facebook
- **What:** 5,843 edits proposed by the public ("closed on 26 Dec"). Google accounts for 4,223 of them. Statuses: EXPIRED 3,689 · REJECTED 1,985 · WAITING 160 · ACCEPTED 9. 20 concern `closed` (permanently closed).
- **Note:** **roughly half are noise.** Treat them as a weak vote, never as truth.
- **Used for:** a supporting signal for a holiday closure, and especially for **permanent closure**, which should trigger `FLAG` (demo `FI-D0011`).

#### `data/analytics_daily.parquet` — search demand (18 MB, needs `pandas` + `pyarrow`)
- **What:** daily per business: Google search queries, search views, map views, customer actions, phone calls, profile views. Covers 2024-01-01 → 2026-11-03 (2-day lag, some gaps).
- **Used for:**
  - **Prioritisation / impact:** holiday search spikes show which suggestions matter most. The scorer reports `search_views_protected_pct`, so fixing high-traffic businesses first earns credit.
  - **Weak detection signal:** extra phone calls around a holiday can mean confused customers ("are you open?").
  - **Pitch metric:** "we protected X at-risk views".
- *Not profiled here: pyarrow isn't installed in this environment.*

### 3.4 Peer and context data — "what would a similar business do?"

#### `data/peer_benchmarks.csv` — what similar businesses entered
- **What:** 7,114 cells by `country × city_tier × segment × day_key`, for example the share entering closed, special hours or regular hours, plus median special open and close times. Each cell has ≥10 businesses.
- **Bias:** this reflects only businesses that **entered** something, so it skews towards diligent owners.
- **Used for:** **Step 2 fallback** when the business has **no history** (about 40% of the needed changes). Real example: Finnish cafés in large cities on Christmas Day have `closed_share_among_entered` = 0.858, but `share_entered_closed` is only 0.379. Most cafés that entered something were closed, yet many entered nothing at all. That gap is why the baseline needs both thresholds (≥ 0.7 and ≥ 0.15). This is the key to the new-customer case (`FI-D0017`).

#### `data/calendar_special_days.csv` — 244 special days (FI/SE/NO, 2024–2027, real)
- **Types:** PUBLIC_HOLIDAY 116 · EVE 62 · BETWEEN_HOLIDAYS 27 · OBSERVANCE 21 · COMMERCIAL 18.
- **Used for:** knowing which dates to check per country. Countries differ: Christmas Eve is an official holiday in FI but not in SE, and Lucia is Swedish. Also used to map last year's date to this year's (`day_key`, e.g. Easter moves).

#### `data/school_breaks.csv` — 24 rows, approximate per country
- **Used for:** family venues (play parks like `FI-D0014`) and ski rentals open longer or earlier during breaks. These days are targets too (`day_key = SCHOOL_BREAK`).

#### `data/local_events.json` — 2,010 synthetic events
- **Types:** ice hockey 641, concerts 460, shows 440, Christmas markets 234, football 162, city festivals 73. Each has coordinates and expected attendance.
- **Used for:** bars and restaurants **within 1 km** of an arena may open later on event nights (`day_key = EVENT`, demo `FI-D0010` Pub Kulma). Match by geo-distance.

#### `data/weather_daily.csv` + `weather_normals.csv`
- **What:** daily weather per city (6–15 Nov 2026 is a noisy forecast) plus climatology, including the probability of ≥10 cm snow depth.
- **Used for:** **snow-dependent businesses.** A ski rental's season opening depends on snow (demo `FI-D0005`, Levi).

#### Lookups: `cities.csv` (28), `categories.csv` (34, names in 4 languages + archetype), `splits.csv`
- `city_tier` connects a business to the right peer cell.
- `categories.csv` gives localised category names for messages.
- `splits.csv` says whether each business is dev, test, demo or reference.

### 3.5 Labels & evaluation — "how you are scored"

| File | Rows | Purpose |
|---|---|---|
| `evaluation/targets_2026.csv` | 41,755 | Rows you must predict. Only **test** rows are scored by the organisers. |
| `evaluation/targets_2025_backtest.csv` | 11,118 | The same task one year earlier (dev only, snapshot 6 Nov 2025) for honest back-testing |
| `labels/dev_labels_2026.csv` | 11,100 | Answers for dev: `truth_hours`, `displayed_hours_at_snapshot`, `expected_action`, `mismatch_type`, `expected_search_views` |
| `labels/dev_labels_2025_backtest.csv` | 11,118 | Answers for the back-test |
| `labels/dev_truth_history.csv` | 58,711 | True hours on **every** special day 2024 → Nov 2026 for dev businesses. Use it for training and checking hypotheses. |
| `labels/dev_regular_hours_truth.csv` | 802 | True weekly hours; 22 listings are outdated, 7 businesses are permanently closed |

**Shape of the problem (dev 2026):** of 11,100 rows, **5,376 need SUGGEST** (48%), 22 need FLAG, and 5,702 are NO_ACTION.
Among the 5,376 SUGGEST rows: **SHOWN_OPEN_ACTUALLY_CLOSED 3,391 (63%)** (the "locked door", the most damaging case) · DIFFERENT_HOURS 1,925 · SHOWN_CLOSED_ACTUALLY_OPEN 60. 19 of the 22 FLAG rows are also "shown open, actually closed" (closed for good).

Target day types 2026: Father's Day, Black Friday, Independence Day (FI), Lucia (SE only), DEC23, Christmas Eve/Day, Boxing Day, INTERDAY (days between Christmas and New Year, 9,051 rows), NYE, New Year's Day, Epiphany Eve/Day, plus EVENT (519) and SCHOOL_BREAK (204).

**Scoring** (`evaluation/evaluate.py`), per row:

| Truth | Your action | Points |
|---|---|---|
| Needs change | exact hours | **+1** |
| | same state, both ends within ±30 min | +0.6 |
| | same state, further off | +0.2 |
| | wrong open/closed state | **−1** |
| | FLAG | +0.05 |
| Already correct | stay quiet | 0 |
| | suggest the same as shown | −0.1 |
| | suggest other hours | −0.5 |
| | suggest the wrong state | −1 |
| | FLAG | −0.1 |
| Closed for good | FLAG | **+1** |
| | suggest closed | +0.3 |
| | suggest open | −1 |
| | stay quiet | 0 |

**Implication:** precision matters more than volume. A wrong open/closed guess cancels a perfect one. When unsure, staying silent (0) beats guessing. The baseline (copy last year → shopping centre → peers) scores **54.5** on dev with 0.90 precision and 0.59 recall. The headroom is in **recall on the ~40% of cases with no history**.

### 3.6 Mock API & simulator (`mock_api/`)
- A local Yext-compatible server (`python mock_api/server.py` → `localhost:8787`) with entities GET/PUT, reviews, publisher suggestions, listings (`expectedLiveBy` after a write), and analytics.
- **`POST /sim/v1/owner-response`** simulates the owner (ACCEPTED / EDITED / REJECTED / NO_RESPONSE) for dev and demo businesses. That's how you demo step 4 without real customers.
- You can swap to the real **Yext sandbox** by changing the base URL. The sandbox has no history, so use it only to demo the write path.

---

## 4. Which data feeds which step

| Step | Primary data | Supporting data |
|---|---|---|
| 1. Detect | `entities.json` (shown hours), `calendar_special_days.csv`, `targets_2026.csv` | `regular_hours_history`, reviews, publisher suggestions, analytics (prioritise) |
| 2. Suggest | `holiday_hours_history.jsonl` (last year), centre hours in `entities.json` | `peer_benchmarks`, `pilot_decision_log` (edits = truth), events, school breaks, weather |
| 3. Contact | `customer_contacts.csv` | `pilot_decision_log` (what channel/time gets replies), `categories.csv` (localised names) |
| 4. Owner decides | mock `/sim/v1/owner-response` | standing permission / opt-out from contacts |
| 5. Apply & confirm | mock / sandbox `PUT entities`, `listings.json` | `analytics` (impact: views protected) |

---

## 5. Suggested decision cascade (from the data)

1. **Permanently closed?** Closure-type publisher suggestions or "closed for good" reviews (what the baseline uses) → `FLAG`. Untested idea: analytics dropping to near zero.
2. **Already entered correctly** for the date → `NO_ACTION`.
3. **In a shopping centre** that has published hours → follow the centre.
4. **Has last year's exception** for the same `day_key` → copy it, adjusted for weekday. This is the highest-precision rule.
5. **Pilot log** shows the owner edited or rejected last year → use their `final_hours`.
6. **No history:** use the peer benchmark if the cell is decisive (e.g. >80% closed), plus review complaints, plus event or weather or school-break rules for the relevant segments.
7. **Otherwise** → `NO_ACTION`, because silence costs nothing while a wrong guess costs −1.

---

## 6. Demo businesses (17, not scored — use them in the pitch)

| ID | Story | Correct behaviour |
|---|---|---|
| FI-D0001 Kahvila Aurora | Partial history, nothing entered this year | Classic suggest |
| FI-D0002 Ravintola Kanerva | Closed Sundays, opens for Father's Day lunch | Suggest *open* on a normally closed day |
| FI-D0003 Kukkakauppa Kide | Florist, Father's Day + longer pre-Christmas hours | Segment-aware suggest |
| FI-D0004 Muoti Lyhty | Inside a shopping centre | Follow the centre's hours |
| FI-D0005 Suksivuokraamo Kuura | Ski rental, snow-dependent | Weather signal |
| FI-D0006 Kesäravintola Ranta | Summer terrace, forgot winter closure | Seasonal-closure suggest |
| FI-D0007 Parturi-Kampaamo Helmi | Closes between Christmas and New Year | Multi-date bundled message |
| SE-D0008 Kafé Linnea | Closed Julafton, early Lucia opening | Swedish calendar |
| NO-D0009 Bakeri Fjord | No history to copy | Peers only |
| FI-D0010 Pub Kulma | Next to the arena | Event-night later closing |
| FI-D0011 Pizzeria Torni | Closed for good, still listed | **FLAG, don't suggest** |
| FI-D0012 Tilitoimisto Otso | Standing permission | Apply, then inform |
| FI-D0013 Hammasklinikka Kallio | Already correct | **Stay quiet** |
| FI-D0014 Leikkimaa Onni | Play park, school holidays | School-break signal |
| NO-D0015 Trening Nordlys 24/7 | 24/7 gym | Nothing to change |
| SE-D0016 Restaurang Fyren | Regular hours outdated | Regular-hours fix |
| FI-D0017 Kahvila Kipinä | **New customer, no history** | Required no-history showcase |

---

## 7. What the submission must contain

- A working demo of the **5 steps** (live or a 2–3 min video) plus a short pitch deck.
- A README based on `docs/README_TEMPLATE.md`: how to run it, the **3–5 most important data sources** and their production origin, what didn't work, and licences (no GPL/AGPL).
- **Final customer messages as text**, in each supported language, plus approve / edit / decline follow-ups.
- The behaviour for a **customer with no history** (`FI-D0017`).
- Optional: `predictions_2026.csv` in the repo root (scored on test).
- Bonus: replace one file with a **live source** (`docs/LIVE_SOURCES.md`): Nager.Date or `holidays`, Helsinki LinkedEvents, FMI / SMHI / MET weather, the Yext sandbox.
- Rules: synthetic data only, no keys in the repo, honest back-testing (use only data timestamped before the snapshot).

---

## 8. Key takeaways for the team

1. **History is king, peers are the fallback.** Copying last year gives 0.90 precision. The other 40% is where you win.
2. **"Shown open, actually closed" is 63% of problems** and the most harmful. Prioritise it in detection and in the pitch.
3. **Silence is a valid answer.** The scoring punishes spam and wrong states harder than it rewards guesses.
4. **52% of pilot messages in 2025 got no reply at all.** Channel, timing, bundling and one-tap approval are as important as the prediction itself.
5. **Signals are noisy on purpose.** About 50% of publisher suggestions are wrong, and some reviews mislead. Combine signals and never trust one alone.
6. **Human in control:** respect opt-outs (6) and standing permissions (57), and FLAG closures instead of guessing.
