// Pure mapping from the Supabase rows (tables bundles, bundle_items, decisions, apply_log; see
// result/B_contact_decide/supabase_schema.md) to what the owner app shows. No network here.
import type { Hours } from "@/lib/parse-hours";
import type { Lang } from "@/lib/i18n";
import { HOLIDAY_NAMES, REASONS } from "./reference.generated";

export type Route = "SKIP" | "STAFF" | "AUTO_APPLY" | "SUGGEST" | "ASK";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";
export type Publisher = {
  publisherId: string;
  publisherName: string;
  typicalUpdateSpeedSeconds: number;
};

export type Bundle = {
  bundle_id: string;
  entity_id: string;
  business_name: string;
  owner_name: string;
  language: string;
  route: Route;
  status: string;
  has_permission: boolean;
  opted_out: boolean;
  intro_text: string;
  publishers: Publisher[];
};
export type Item = {
  id?: number;
  bundle_id: string;
  date: string;
  day_name: string;
  shown_hours: string;
  proposed_hours: string | null;
  final_hours: string | null;
  basis: string;
  evidence: string[];
  confidence: Confidence;
};
export type Json = string | number | boolean | null | Json[] | { [k: string]: Json };
export type DecisionRow = {
  bundle_id: string;
  action: string;
  parsed: Json;
  parser: string | null;
  created_at: string;
};
export type ApplyRow = { bundle_id: string; mode: string; status: string; created_at: string };

export type Deck = {
  mode: "live" | "demo";
  entity_id: string;
  bundles: Bundle[];
  items: Item[];
  decisions: DecisionRow[];
  applies: ApplyRow[];
};

/** One swipe card = one date of a SUGGEST or ASK bundle that the owner has not decided yet. */
export type Card = { key: string; route: "SUGGEST" | "ASK"; bundle: Bundle; item: Item };
export type Outcome = "approved" | "edited" | "declined" | "regular" | "auto";
export type HistoryEntry = {
  key: string;
  bundle: Bundle;
  item: Item;
  outcome: Outcome;
  hours: string | null;
  at: string | null;
};

/** Bundle statuses after which nothing in the bundle is waiting for the owner. */
const DONE = new Set([
  "DECLINED",
  "APPROVED",
  "APPLYING",
  "APPLIED",
  "UNDONE",
  "APPLY_FAILED",
  "SKIPPED",
  "EXPIRED",
]);
const OWNER_ROUTES = new Set<Route>(["SUGGEST", "ASK", "AUTO_APPLY"]);

const dateOf = (parsed: unknown): string | null => {
  const p = typeof parsed === "string" ? safeJson(parsed) : parsed;
  return p &&
    typeof p === "object" &&
    "date" in p &&
    typeof (p as { date: unknown }).date === "string"
    ? (p as { date: string }).date
    : null;
};
function safeJson(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

/** Decisions logged by the web app carry parsed.date; Telegram decisions are bundle-wide. Rows come newest first. */
function decisionFor(deck: Deck, item: Item): DecisionRow | undefined {
  return deck.decisions.find(
    (d) => d.bundle_id === item.bundle_id && dateOf(d.parsed) === item.date,
  );
}

export function buildDeck(deck: Deck): { cards: Card[]; history: HistoryEntry[] } {
  const byId = new Map(
    deck.bundles
      .filter((b) => OWNER_ROUTES.has(b.route) && !b.opted_out)
      .map((b) => [b.bundle_id, b]),
  );
  const cards: Card[] = [];
  const history: HistoryEntry[] = [];
  const items = [...deck.items].sort(
    (a, b) => a.date.localeCompare(b.date) || a.bundle_id.localeCompare(b.bundle_id),
  );
  for (const item of items) {
    const bundle = byId.get(item.bundle_id);
    if (!bundle) continue;
    const key = `${item.bundle_id}|${item.date}`;
    const decision = decisionFor(deck, item);
    // the latest decision for the date wins; an UNDO puts the date back in the deck (n8n clears final_hours)
    const decided = item.final_hours != null || (decision != null && decision.action !== "UNDO");
    if (bundle.route === "AUTO_APPLY") {
      if (item.final_hours != null)
        history.push({
          key,
          bundle,
          item,
          outcome: "auto",
          hours: item.final_hours,
          at: decision?.created_at ?? null,
        });
      continue;
    }
    if (!decided && !DONE.has(bundle.status)) {
      cards.push({ key, route: bundle.route as "SUGGEST" | "ASK", bundle, item });
      continue;
    }
    history.push({
      key,
      bundle,
      item,
      ...outcomeOf(item, decision),
      at: decision?.created_at ?? null,
    });
  }
  history.sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""));
  return { cards, history };
}

function outcomeOf(
  item: Item,
  d: DecisionRow | undefined,
): { outcome: Outcome; hours: string | null } {
  const f = item.final_hours;
  if (f === "regular" || d?.action === "REGULAR") return { outcome: "regular", hours: "regular" };
  if (f == null || d?.action === "DECLINE") return { outcome: "declined", hours: null };
  return { outcome: f === item.proposed_hours ? "approved" : "edited", hours: f };
}

// ------------------------------------------------------------------ display helpers

/** "closed" | "regular" | "HH:MM-HH:MM[,HH:MM-HH:MM]" -> words, in the owner's language. */
export function hoursLabel(
  h: string | null | undefined,
  t: { closed: string; regular: string },
): string {
  if (h == null || h === "") return "–";
  if (h === "closed") return t.closed;
  if (h === "regular") return t.regular;
  return h
    .split(",")
    .map((x) => x.trim().replace("-", " – "))
    .join(", ");
}

/** The editor's parsed hours in the database format (the n8n validator accepts the same). */
export function toDbHours(h: Hours): string {
  return h.closed ? "closed" : `${h.open}-${h.close}`;
}

export function holidayName(dayName: string, lang: Lang): string {
  const n = (HOLIDAY_NAMES as Record<string, Partial<Record<Lang, string>>>)[dayName];
  return n?.[lang] ?? n?.en ?? dayName;
}

const WEEKDAY: Record<Lang, string[]> = {
  fi: ["su", "ma", "ti", "ke", "to", "pe", "la"],
  sv: ["sön", "mån", "tis", "ons", "tors", "fre", "lör"],
  nb: ["søn", "man", "tir", "ons", "tor", "fre", "lør"],
  en: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
};
const MONTH_EN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** 2026-12-25 -> "pe 25.12." (fi), "fre 25.12" (sv/nb), "Fri 25 Dec" (en). Calendar date, no timezone. */
export function dateLabel(iso: string, lang: Lang): string {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  const wd = WEEKDAY[lang][new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  if (lang === "en") return `${wd} ${d} ${MONTH_EN[m - 1]}`;
  return lang === "fi" ? `${wd} ${d}.${m}.` : `${wd} ${d}.${m}`;
}

export function reasonText(basis: string, lang: Lang): string | null {
  const r = (REASONS as Record<string, Record<string, string>>)[lang]?.[basis];
  return r ? r.charAt(0).toUpperCase() + r.slice(1) : null;
}

/** The share of closed peers, read from the PEERS evidence sentence written by Part A. */
export function peerShare(item: Item): number | null {
  if (item.basis !== "PEERS" && item.basis !== "OWNER_PATTERN") return null;
  for (const e of item.evidence) {
    const m = /(\d{1,3})% of (?:similar businesses|peers)/.exec(e);
    if (m) return Number(m[1]);
  }
  return null;
}

/** Fastest publishers first, with a short "~2 min" / "~3 h" / "~2 d" label. */
export function publisherChips(ps: Publisher[]): { name: string; eta: string }[] {
  return [...ps]
    .sort((a, b) => a.typicalUpdateSpeedSeconds - b.typicalUpdateSpeedSeconds)
    .map((p) => ({ name: p.publisherName, eta: eta(p.typicalUpdateSpeedSeconds) }));
}
function eta(s: number): string {
  if (s < 3600) return `~${Math.max(1, Math.round(s / 60))} min`;
  if (s < 86400) return `~${Math.round(s / 3600)} h`;
  return `~${Math.round(s / 86400)} d`;
}
