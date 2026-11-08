// Server functions: the only code that sees the keys. The browser never talks to Supabase or n8n directly.
//
// Environment (server only; set them in Lovable Secrets or the host's env, never in the repo):
//   SUPABASE_URL, SUPABASE_SERVICE_KEY   read bundles / bundle_items / decisions / apply_log
//   N8N_WEB_ACTION_URL                   the webhook of the n8n workflow "Connect · Web action"
//   LINK_SECRET                          signs the no-login owner links (/o/<entity_id>?t=<token>)
// Without SUPABASE_URL the app runs in demo mode on the bundled sample data and sends nothing.
import { createServerFn } from "@tanstack/react-start";
import type { ApplyRow, Bundle, Deck, DecisionRow, Item } from "./deck";
import { DEMO } from "./demo.generated";

const env = (k: string): string | undefined => {
  const v = typeof process !== "undefined" ? process.env[k] : undefined;
  return v && v.trim() ? v.trim() : undefined;
};

const ENTITY_RE = /^[A-Z]{2}-[A-Z0-9]{3,8}$/;
const HOURS_RE = /^(closed|regular|\d\d:\d\d-\d\d:\d\d(,\d\d:\d\d-\d\d:\d\d)*)$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** First 32 hex chars of HMAC-SHA256(entity_id, LINK_SECRET). Web Crypto, so it runs on Node and on edge hosts. */
export async function linkToken(entityId: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(entityId)),
  );
  return Array.from(sig, (b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

async function checkLink(entityId: string, token: string | undefined): Promise<"live" | "demo"> {
  if (!ENTITY_RE.test(entityId)) throw new Error("BAD_LINK");
  if (!env("SUPABASE_URL")) return "demo";
  const secret = env("LINK_SECRET");
  if (!secret) throw new Error("NOT_CONFIGURED");
  const expected = await linkToken(entityId, secret);
  if (!token || token.length !== expected.length) throw new Error("BAD_LINK");
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ token.charCodeAt(i);
  if (diff !== 0) throw new Error("BAD_LINK");
  return "live";
}

async function rest<T>(path: string): Promise<T> {
  const url = env("SUPABASE_URL")!.replace(/\/$/, "");
  const key = env("SUPABASE_SERVICE_KEY");
  if (!key) throw new Error("NOT_CONFIGURED");
  const r = await fetch(`${url}/rest/v1/${path}`, {
    headers: { apikey: key, Authorization: `Bearer ${key}` },
  });
  if (!r.ok) throw new Error(`SUPABASE_${r.status}`);
  return (await r.json()) as T;
}

const BUNDLE_COLS =
  "bundle_id,entity_id,business_name,owner_name,language,route,status,has_permission,opted_out,intro_text,publishers";
const ITEM_COLS =
  "id,bundle_id,date,day_name,shown_hours,proposed_hours,final_hours,basis,evidence,confidence";

function demoDeck(entityId: string): Deck {
  const bundles = (DEMO.bundles as unknown as Bundle[]).filter((b) => b.entity_id === entityId);
  const ids = new Set(bundles.map((b) => b.bundle_id));
  const items = (DEMO.bundle_items as unknown as Item[]).filter((i) => ids.has(i.bundle_id));
  return { mode: "demo", entity_id: entityId, bundles, items, decisions: [], applies: [] };
}

export const getDeck = createServerFn({ method: "GET" })
  .validator((d: { entity: string; t?: string | undefined }) => ({
    entity: String(d.entity),
    t: d.t ? String(d.t) : undefined,
  }))
  .handler(async ({ data }): Promise<Deck> => {
    const mode = await checkLink(data.entity, data.t);
    if (mode === "demo") return demoDeck(data.entity);
    const bundles = await rest<Bundle[]>(
      `bundles?select=${BUNDLE_COLS}&entity_id=eq.${encodeURIComponent(data.entity)}&route=in.(SUGGEST,ASK,AUTO_APPLY)`,
    );
    if (!bundles.length)
      return { mode, entity_id: data.entity, bundles, items: [], decisions: [], applies: [] };
    const inList = `in.(${bundles.map((b) => `"${b.bundle_id}"`).join(",")})`;
    const [items, decisions, applies] = await Promise.all([
      rest<Item[]>(
        `bundle_items?select=${ITEM_COLS}&bundle_id=${encodeURIComponent(inList)}&order=date`,
      ),
      rest<DecisionRow[]>(
        `decisions?select=bundle_id,action,parsed,parser,created_at&bundle_id=${encodeURIComponent(inList)}&order=created_at.desc`,
      ),
      rest<ApplyRow[]>(
        `apply_log?select=bundle_id,mode,status,created_at&bundle_id=${encodeURIComponent(inList)}&order=created_at.desc`,
      ),
    ]);
    return { mode, entity_id: data.entity, bundles, items, decisions, applies };
  });

export type WebAction = "APPROVE" | "EDIT" | "DECLINE" | "REGULAR" | "UNDO" | "PERMISSION";
export type ActionInput = {
  entity: string;
  t?: string | undefined;
  bundle_id: string;
  action: WebAction;
  date?: string | undefined;
  hours?: string | undefined;
  undo_of?: string | undefined;
};

export const sendAction = createServerFn({ method: "POST" })
  .validator((d: ActionInput): ActionInput => {
    const actions: WebAction[] = ["APPROVE", "EDIT", "DECLINE", "REGULAR", "UNDO", "PERMISSION"];
    if (!actions.includes(d.action)) throw new Error("BAD_ACTION");
    if (d.date !== undefined && !DATE_RE.test(d.date)) throw new Error("BAD_DATE");
    if (d.hours !== undefined && !HOURS_RE.test(d.hours)) throw new Error("BAD_HOURS");
    if (["APPROVE", "EDIT", "DECLINE", "REGULAR"].includes(d.action) && !d.date)
      throw new Error("BAD_DATE");
    if (d.action === "EDIT" && !d.hours) throw new Error("BAD_HOURS");
    return {
      entity: String(d.entity),
      t: d.t,
      bundle_id: String(d.bundle_id),
      action: d.action,
      date: d.date,
      hours: d.hours,
      undo_of: d.action === "UNDO" && d.undo_of === "DECLINE" ? "DECLINE" : undefined,
    };
  })
  .handler(async ({ data }): Promise<{ ok: boolean; demo?: boolean; error?: string }> => {
    const mode = await checkLink(data.entity, data.t);
    if (mode === "demo") return { ok: true, demo: true };
    // the bundle must belong to the entity of the signed link
    const owned = await rest<{ bundle_id: string }[]>(
      `bundles?select=bundle_id&bundle_id=eq.${encodeURIComponent(data.bundle_id)}&entity_id=eq.${encodeURIComponent(data.entity)}`,
    );
    if (!owned.length) throw new Error("BAD_LINK");
    const hook = env("N8N_WEB_ACTION_URL");
    if (!hook) throw new Error("NOT_CONFIGURED");
    const r = await fetch(hook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "web",
        entity_id: data.entity,
        bundle_id: data.bundle_id,
        action: data.action,
        date: data.date ?? null,
        hours: data.hours ?? null,
        undo_of: data.undo_of ?? null,
      }),
    });
    let body: { ok?: boolean; error?: string } = {};
    try {
      body = (await r.json()) as typeof body;
    } catch {
      body = {};
    }
    return r.ok && body.ok !== false
      ? { ok: true }
      : { ok: false, error: body.error ?? `N8N_${r.status}` };
  });
