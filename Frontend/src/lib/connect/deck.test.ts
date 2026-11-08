import { describe, expect, it } from "vitest";
import {
  buildDeck,
  dateLabel,
  holidayName,
  hoursLabel,
  peerShare,
  publisherChips,
  type Bundle,
  type Deck,
  type Item,
} from "./deck";

const bundle = (route: Bundle["route"], status = "SENT", extra: Partial<Bundle> = {}): Bundle => ({
  bundle_id: `B-FI-D0017-${route}`,
  entity_id: "FI-D0017",
  business_name: "Kahvila Kipinä",
  owner_name: "Aino",
  language: "fi",
  route,
  status,
  has_permission: false,
  opted_out: false,
  intro_text: "Hei Aino!",
  publishers: [],
  ...extra,
});
const item = (route: Bundle["route"], date: string, extra: Partial<Item> = {}): Item => ({
  bundle_id: `B-FI-D0017-${route}`,
  date,
  day_name: "Christmas Day",
  shown_hours: "08:00-17:00",
  proposed_hours: "closed",
  final_hours: null,
  basis: "PEERS",
  evidence: [
    "86% of similar businesses (cafe, large_city, FI) that entered XMAS_DAY hours were closed; 38% of all of them entered closed.",
  ],
  confidence: "MEDIUM",
  ...extra,
});
const deck = (bundles: Bundle[], items: Item[], decisions: Deck["decisions"] = []): Deck => ({
  mode: "demo",
  entity_id: "FI-D0017",
  bundles,
  items,
  decisions,
  applies: [],
});

describe("buildDeck", () => {
  it("makes one card per undecided date of SUGGEST and ASK bundles, in date order", () => {
    const { cards, history } = buildDeck(
      deck(
        [bundle("SUGGEST"), bundle("ASK")],
        [item("ASK", "2027-01-01"), item("SUGGEST", "2026-12-25"), item("ASK", "2026-12-26")],
      ),
    );
    expect(cards.map((c) => [c.route, c.item.date])).toEqual([
      ["SUGGEST", "2026-12-25"],
      ["ASK", "2026-12-26"],
      ["ASK", "2027-01-01"],
    ]);
    expect(history).toEqual([]);
  });
  it("never shows STAFF or SKIP bundles, nor opted-out owners", () => {
    const { cards } = buildDeck(
      deck(
        [bundle("STAFF"), bundle("SUGGEST", "SENT", { opted_out: true })],
        [item("STAFF", "2026-12-25"), item("SUGGEST", "2026-12-24")],
      ),
    );
    expect(cards).toEqual([]);
  });
  it("moves decided dates to the history: final_hours, or a web decision for that date", () => {
    const { cards, history } = buildDeck(
      deck(
        [bundle("SUGGEST")],
        [
          item("SUGGEST", "2026-12-24", { final_hours: "10:00-14:00" }),
          item("SUGGEST", "2026-12-25"),
        ],
        [
          {
            bundle_id: "B-FI-D0017-SUGGEST",
            action: "DECLINE",
            parsed: { date: "2026-12-25" },
            parser: "WEB",
            created_at: "2026-11-08T10:00:00Z",
          },
        ],
      ),
    );
    expect(cards).toEqual([]);
    expect(history.map((h) => [h.item.date, h.outcome])).toEqual([
      ["2026-12-25", "declined"],
      ["2026-12-24", "edited"],
    ]);
  });
  it("puts a date back in the deck when its latest decision is an UNDO", () => {
    const { cards } = buildDeck(
      deck(
        [bundle("ASK")],
        [item("ASK", "2027-01-01")],
        [
          {
            bundle_id: "B-FI-D0017-ASK",
            action: "UNDO",
            parsed: { date: "2027-01-01" },
            parser: "WEB",
            created_at: "2026-11-08T10:05:00Z",
          },
          {
            bundle_id: "B-FI-D0017-ASK",
            action: "EDIT",
            parsed: { date: "2027-01-01", hours: "10:00-14:00" },
            parser: "WEB",
            created_at: "2026-11-08T10:00:00Z",
          },
        ],
      ),
    );
    expect(cards.map((c) => c.item.date)).toEqual(["2027-01-01"]);
  });
  it("shows AUTO_APPLY items only in the history, as auto", () => {
    const { cards, history } = buildDeck(
      deck(
        [bundle("AUTO_APPLY", "APPLIED")],
        [item("AUTO_APPLY", "2026-12-24", { final_hours: "closed", confidence: "HIGH" })],
      ),
    );
    expect(cards).toEqual([]);
    expect(history[0]?.outcome).toBe("auto");
  });
  it("keeps the other dates of a bundle after one date was applied from the web", () => {
    const { cards } = buildDeck(
      deck(
        [bundle("ASK", "APPLIED")],
        [item("ASK", "2026-12-26", { final_hours: "regular" }), item("ASK", "2027-01-01")],
      ),
    );
    expect(cards.map((c) => c.item.date)).toEqual(["2027-01-01"]);
  });
  it("hides the cards of a bundle the owner already handled in Telegram", () => {
    const { cards } = buildDeck(
      deck([bundle("SUGGEST", "DECLINED")], [item("SUGGEST", "2026-12-25")]),
    );
    expect(cards).toEqual([]);
  });
});

describe("display helpers", () => {
  const t = { closed: "Suljettu", regular: "Auki kuten tavallisesti" };
  it("formats the database hours", () => {
    expect(hoursLabel("closed", t)).toBe("Suljettu");
    expect(hoursLabel("10:00-14:00,17:00-22:00", t)).toBe("10:00 – 14:00, 17:00 – 22:00");
    expect(hoursLabel(null, t)).toBe("–");
  });
  it("names holidays from the calendar and dates in the owner's language", () => {
    expect(holidayName("Christmas Day", "fi")).toBe("Joulupäivä");
    expect(holidayName("Boxing Day", "sv")).toBe("Annandag jul");
    expect(dateLabel("2026-12-25", "fi")).toBe("pe 25.12.");
    expect(dateLabel("2027-01-01", "en")).toBe("Fri 1 Jan");
  });
  it("reads the peer share from the evidence", () => {
    expect(peerShare(item("SUGGEST", "2026-12-25"))).toBe(86);
    expect(peerShare(item("SUGGEST", "2026-12-25", { basis: "LAST_YEAR" }))).toBeNull();
  });
  it("lists the fastest channels first", () => {
    const chips = publisherChips([
      { publisherId: "APPLE", publisherName: "Apple Maps", typicalUpdateSpeedSeconds: 172800 },
      { publisherId: "G", publisherName: "Google", typicalUpdateSpeedSeconds: 120 },
    ]);
    expect(chips).toEqual([
      { name: "Google", eta: "~2 min" },
      { name: "Apple Maps", eta: "~2 d" },
    ]);
  });
});
