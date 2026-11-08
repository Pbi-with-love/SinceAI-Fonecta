// The owner's no-login app: one swipe deck of the holiday hours we suggest, built from the real bundles
// (Supabase, or the bundled demo sample). Every decision goes to the server function sendAction, which
// forwards it to the n8n workflow "Connect · Web action" (the same Apply to Yext as the Telegram flow).
import { useMemo, useRef, useState } from "react";
import { Check, Pencil, Undo2, X, type LucideIcon } from "lucide-react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useTransform,
  animate,
  type PanInfo,
} from "framer-motion";
import { parseHours } from "@/lib/parse-hours";
import { DICTS, LANGS, isLang, type Dict, type Lang } from "@/lib/i18n";
import {
  buildDeck,
  dateLabel,
  holidayName,
  hoursLabel,
  peerShare,
  publisherChips,
  reasonText,
  toDbHours,
  type Card,
  type Deck,
  type HistoryEntry,
  type Outcome,
} from "@/lib/connect/deck";
import { sendAction, type WebAction } from "@/lib/connect/api";

type Swipe = "left" | "right" | "up";
type Local = HistoryEntry & { card: Card; local: true };

export function OwnerApp({
  deck,
  token,
  onChanged,
}: {
  deck: Deck;
  token?: string | undefined;
  onChanged: () => void;
}) {
  const built = useMemo(() => buildDeck(deck), [deck]);
  const first = deck.bundles[0];
  const [lang, setLang] = useState<Lang>(isLang(first?.language) ? first.language : "en");
  const t = DICTS[lang];
  const [done, setDone] = useState<Set<string>>(new Set());
  const [local, setLocal] = useState<Local[]>([]);
  const [tab, setTab] = useState<"review" | "activity">("review");
  const [editing, setEditing] = useState<Card | null>(null);
  const [askStanding, setAskStanding] = useState(false);
  const [standing, setStanding] = useState(deck.bundles.some((b) => b.has_permission));
  const [phone, setPhone] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [exitDir, setExitDir] = useState<Swipe>("right");

  // Dates undone in this session: back in the deck at once, before the server data catches up.
  const [reopened, setReopened] = useState<Map<string, Card>>(new Map());
  const queue = [
    ...built.cards,
    ...[...reopened.values()].filter((r) => !built.cards.some((c) => c.key === r.key)),
  ]
    .filter((c) => !done.has(c.key))
    .sort((a, b) => a.item.date.localeCompare(b.item.date) || a.key.localeCompare(b.key));
  const history = [
    ...local,
    ...built.history.filter((h) => !local.some((l) => l.key === h.key) && !reopened.has(h.key)),
  ];
  const top = queue[0];
  const owner = first?.owner_name ?? "";
  const business = first?.business_name ?? deck.entity_id;

  const flash = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(null), 2400);
  };

  // One request at a time, in swipe order: Apply to Yext takes a few seconds per call and n8n answers BUSY while a
  // write for the bundle is running. The card leaves the deck at once; only a failed save puts it back.
  const chain = useRef<Promise<unknown>>(Promise.resolve());
  const [pending, setPending] = useState(0);
  const enqueue = <T,>(job: () => Promise<T>): Promise<T> => {
    setPending((n) => n + 1);
    const run = chain.current.then(job, job);
    chain.current = run.catch(() => undefined);
    return run.finally(() =>
      setPending((n) => {
        if (n === 1) setTimeout(onChanged, 0); // refresh from the server once the queue is empty
        return n - 1;
      }),
    );
  };

  type Sent = "ok" | "demo" | "fail";
  const post = (
    bundle_id: string,
    action: WebAction,
    date?: string,
    hours?: string,
    undo_of?: string,
  ): Promise<Sent> =>
    enqueue(async () => {
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const r = await sendAction({
            data: { entity: deck.entity_id, t: token, bundle_id, action, date, hours, undo_of },
          });
          if (r.ok) return r.demo ? "demo" : "ok";
          if (r.error !== "BUSY") return "fail";
        } catch {
          return "fail";
        }
        await new Promise((res) => setTimeout(res, 2500)); // another write (e.g. from Telegram) is running
      }
      return "fail";
    });

  const restore = (key: string) =>
    setDone((s) => {
      const n = new Set(s);
      n.delete(key);
      return n;
    });

  // Undo is offered once, for the latest decision of this session (Apply can only undo its last write).
  const [undoUsed, setUndoUsed] = useState(false);

  /** right = approve (SUGGEST) or closed (ASK); left = decline (SUGGEST) or open as usual (ASK); edit = typed hours. */
  const decide = async (c: Card, how: "right" | "left" | "edit", typed?: string) => {
    const ask = c.route === "ASK";
    setExitDir(how === "left" ? "left" : how === "edit" ? "up" : "right");
    const action: WebAction =
      how === "edit" ? "EDIT" : how === "right" ? "APPROVE" : ask ? "REGULAR" : "DECLINE";
    const hours =
      how === "edit"
        ? typed!
        : how === "right"
          ? (c.item.proposed_hours ?? undefined)
          : ask
            ? "regular"
            : undefined;
    const outcome: Outcome =
      how === "edit" ? "edited" : how === "right" ? "approved" : ask ? "regular" : "declined";
    setDone((s) => new Set(s).add(c.key));
    setUndoUsed(false);
    setLocal((h) => [
      {
        key: c.key,
        bundle: c.bundle,
        item: c.item,
        outcome,
        hours: hours ?? null,
        at: new Date().toISOString(),
        card: c,
        local: true,
      },
      ...h.filter((x) => x.key !== c.key),
    ]);
    const yes = (o: Outcome) => o === "approved" || o === "edited";
    if (yes(outcome) && !standing && !local.some((x) => yes(x.outcome))) setAskStanding(true);
    const res = await post(c.bundle.bundle_id, action, c.item.date, hours);
    const name = holidayName(c.item.day_name, lang);
    if (res === "fail") {
      restore(c.key);
      setLocal((h) => h.filter((x) => x.key !== c.key));
      return flash(`${name}: ${t.failed}`);
    }
    flash(
      outcome === "declined"
        ? `${name}: ${t.skipped}`
        : `${name} → ${hoursLabel(hours, t)} · ${res === "demo" ? t.demoSent : t.sent}`,
    );
  };

  const lastLocal = undoUsed ? undefined : local[0];
  const undo = async () => {
    const last = lastLocal;
    if (!last) return;
    setUndoUsed(true);
    // a decline never reached Yext: n8n only logs the undo; every other decision is undone in Yext
    const res = await post(
      last.bundle.bundle_id,
      "UNDO",
      last.item.date,
      undefined,
      last.outcome === "declined" ? "DECLINE" : undefined,
    );
    if (res === "fail") {
      setUndoUsed(false);
      return flash(t.failed);
    }
    setLocal((h) => h.filter((x) => x.key !== last.key));
    setReopened((m) => new Map(m).set(last.key, last.card));
    restore(last.key);
    flash(`${t.restored}: ${hoursLabel(last.item.shown_hours, t)}`);
  };

  /** Standing permission for the whole business: PERMISSION turns it on (after the sheet), REVOKE turns it off. */
  const setPermission = async (on: boolean) => {
    if (!first || on === standing) return;
    setStanding(on); // show the new state at once; put it back if the save fails
    const res = await post(first.bundle_id, on ? "PERMISSION" : "REVOKE");
    if (res === "fail") {
      setStanding(!on);
      return flash(t.failed);
    }
    flash(on ? t.autoOn : t.autoOff);
  };
  const grantStanding = async (on: boolean) => {
    setAskStanding(false);
    if (on) await setPermission(true);
  };

  return (
    <div className="mx-auto flex min-h-[100dvh] max-w-md flex-col px-5 pb-6 pt-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex rounded-full bg-secondary p-0.5 text-xs font-bold">
          {LANGS.map((l) => (
            <button
              key={l.id}
              title={l.label}
              onClick={() => setLang(l.id)}
              className="relative rounded-full px-2.5 py-1"
            >
              {lang === l.id && (
                <motion.span layoutId="lang" className="absolute inset-0 rounded-full bg-card" />
              )}
              <span className="relative">{l.id.toUpperCase()}</span>
            </button>
          ))}
        </div>
        {top && (
          <motion.button
            whileTap={{ scale: 0.92 }}
            onClick={() => setPhone(true)}
            className="rounded-full border bg-card px-3 py-1.5 text-xs font-semibold"
          >
            {t.telegram}
          </motion.button>
        )}
      </div>

      <header className="mt-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-muted-foreground">Porchlight</p>
          <h1 className="font-display text-2xl font-semibold">{t.hello(owner)}</h1>
          <p className="truncate text-sm text-muted-foreground">{business}</p>
        </div>
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-primary text-base font-bold text-primary-foreground">
          {initials(business)}
        </div>
      </header>

      {deck.mode === "demo" && (
        <p className="mt-3 rounded-xl bg-secondary px-3 py-2 text-xs font-semibold">{t.demo}</p>
      )}

      <nav className="mt-3 grid grid-cols-2 rounded-full bg-secondary p-1 text-sm font-semibold">
        {(["review", "activity"] as const).map((x) => (
          <button key={x} onClick={() => setTab(x)} className="relative rounded-full py-2">
            {tab === x && (
              <motion.span
                layoutId="tab"
                className="absolute inset-0 rounded-full bg-card"
                transition={{ type: "spring", stiffness: 500, damping: 35 }}
              />
            )}
            <span className="relative">
              {x === "review"
                ? `${t.review} · ${queue.length}`
                : `${t.activity} · ${history.length}`}
            </span>
          </button>
        ))}
      </nav>

      {tab === "review" ? (
        <>
          <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span aria-live="polite">
              {pending > 0 ? t.saving(pending) : top?.route === "ASK" ? t.hintAsk : t.hint}
            </span>
            <button
              onClick={() => (standing ? void setPermission(false) : setAskStanding(true))}
              className="flex shrink-0 items-center gap-1.5"
              aria-pressed={standing}
            >
              {t.auto} <Toggle on={standing} />
            </button>
          </div>
          <div className="relative mt-3 h-[456px]">
            <AnimatePresence>
              {queue
                .slice(0, 3)
                .reverse()
                .map((c) => (
                  <SwipeCard
                    key={c.key}
                    c={c}
                    depth={queue.indexOf(c)}
                    exitDir={exitDir}
                    lang={lang}
                    t={t}
                    onSwipe={(d) =>
                      d === "up" ? setEditing(c) : decide(c, d === "right" ? "right" : "left")
                    }
                  />
                ))}
            </AnimatePresence>
            {!top && <Empty t={t} count={history.length} />}
          </div>
          <div className="mt-5 grid grid-cols-4 gap-3">
            <ActionBtn
              label={t.undo}
              icon={Undo2}
              onClick={undo}
              disabled={!lastLocal}
              tone="muted"
            />
            <ActionBtn
              label={top?.route === "ASK" ? t.regularShort : t.no}
              icon={X}
              onClick={() => top && decide(top, "left")}
              disabled={!top}
              tone="destructive"
            />
            <ActionBtn
              label={t.edit}
              icon={Pencil}
              onClick={() => top && setEditing(top)}
              disabled={!top}
              tone="accent"
            />
            <ActionBtn
              label={top?.route === "ASK" ? t.closed : t.approve}
              icon={Check}
              onClick={() => top && decide(top, "right")}
              disabled={!top}
              tone="success"
            />
          </div>
        </>
      ) : (
        <Activity
          history={history}
          onUndo={undo}
          canUndoKey={lastLocal?.key}
          t={t}
          lang={lang}
          deck={deck}
        />
      )}

      <AnimatePresence>
        {editing && (
          <EditSheet
            key="edit"
            c={editing}
            t={t}
            lang={lang}
            onClose={() => setEditing(null)}
            onConfirm={(h) => {
              void decide(editing, "edit", h);
              setEditing(null);
            }}
          />
        )}
        {askStanding && <StandingSheet key="standing" t={t} onChoose={grantStanding} />}
        {phone && top && (
          <PhoneSheet
            key="phone"
            t={t}
            text={top.bundle.intro_text}
            onClose={() => setPhone(false)}
          />
        )}
        {toast && (
          <motion.div
            key="toast"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            role="status"
            className="fixed inset-x-0 bottom-6 z-[60] mx-auto w-fit max-w-[90%] rounded-full bg-foreground px-4 py-2.5 text-sm font-medium text-background"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

function SwipeCard({
  c,
  depth,
  exitDir,
  lang,
  t,
  onSwipe,
}: {
  c: Card;
  depth: number;
  exitDir: Swipe;
  lang: Lang;
  t: Dict;
  onSwipe: (d: Swipe) => void;
}) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-220, 220], [-12, 12]);
  const approveO = useTransform(x, [20, 110], [0, 1]);
  const approveS = useTransform(x, [20, 110], [1.4, 1]);
  const declineO = useTransform(x, [-110, -20], [1, 0]);
  const declineS = useTransform(x, [-110, -20], [1, 1.4]);
  const editO = useTransform(y, [-110, -20], [1, 0]);
  const tintA = useTransform(x, [0, 140], [0, 0.12]);
  const tintD = useTransform(x, [-140, 0], [0.12, 0]);
  const isTop = depth === 0;
  const ask = c.route === "ASK";
  const { item, bundle } = c;
  const proposed = item.proposed_hours;
  const reason = reasonText(item.basis, lang);
  const share = peerShare(item);
  const chips = publisherChips(bundle.publishers);
  const level = item.confidence;

  const onEnd = (_: unknown, { offset, velocity }: PanInfo) => {
    if (offset.x > 110 || velocity.x > 600) return onSwipe("right");
    if (offset.x < -110 || velocity.x < -600) return onSwipe("left");
    const spring = { type: "spring" as const, stiffness: 420, damping: 30 };
    animate(x, 0, spring);
    animate(y, 0, spring);
    if (offset.y < -110 || velocity.y < -600) onSwipe("up");
  };
  const exit =
    exitDir === "left"
      ? { x: -520, rotate: -24 }
      : exitDir === "up"
        ? { y: -650 }
        : { x: 520, rotate: 24 };

  return (
    <motion.article
      className="absolute inset-0 cursor-grab touch-none select-none overflow-hidden rounded-[28px] border bg-card shadow-card active:cursor-grabbing"
      style={{ x, y, rotate, zIndex: 10 - depth }}
      initial={{ scale: 0.9, y: 30, opacity: 0 }}
      animate={{ scale: 1 - depth * 0.045, y: depth * 12, opacity: 1 }}
      exit={{ ...exit, opacity: 0, transition: { duration: 0.32, ease: "easeIn" } }}
      transition={{ type: "spring", stiffness: 260, damping: 26 }}
      drag={isTop}
      dragElastic={0.75}
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      onDragEnd={onEnd}
      aria-hidden={!isTop}
    >
      <motion.div
        className="pointer-events-none absolute inset-0 bg-success"
        style={{ opacity: tintA }}
      />
      <motion.div
        className="pointer-events-none absolute inset-0 bg-destructive"
        style={{ opacity: tintD }}
      />
      <Stamp
        style={{ opacity: approveO, scale: approveS, rotate: -14 }}
        className="left-5 top-8 border-success text-foreground"
      >
        {ask ? t.closedStamp : t.approvedStamp}
      </Stamp>
      <Stamp
        style={{ opacity: declineO, scale: declineS, rotate: 14 }}
        className="right-5 top-8 border-destructive text-foreground"
      >
        {ask ? t.regularStamp : t.skipStamp}
      </Stamp>
      <Stamp
        style={{ opacity: editO }}
        className="inset-x-0 top-1/3 mx-auto w-fit border-accent text-foreground"
      >
        {t.editStamp}
      </Stamp>

      <div className="relative flex h-full flex-col p-5">
        <p className="text-sm font-semibold text-muted-foreground">{dateLabel(item.date, lang)}</p>
        <h2 className="mt-0.5 font-display text-[28px] font-semibold leading-tight">
          {holidayName(item.day_name, lang)}
        </h2>
        {ask && <p className="mt-1 text-base font-semibold">{t.askTitle}</p>}

        <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <div className="rounded-2xl bg-muted p-3">
            <p className="text-[13px] font-semibold text-muted-foreground">{t.mapsNow}</p>
            <p className="mt-1 text-lg font-bold line-through decoration-destructive/60">
              {hoursLabel(item.shown_hours, t)}
            </p>
          </div>
          <span className="text-muted-foreground">→</span>
          <div className="rounded-2xl bg-primary p-3 text-primary-foreground">
            <p className="text-[13px] font-semibold opacity-85">{t.suggested}</p>
            <p className="mt-1 text-lg font-bold">{hoursLabel(proposed, t)}</p>
            <p className="text-[13px] opacity-85">
              {proposed === "closed" ? t.closedAllDay : t.special}
            </p>
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between text-[13px] font-semibold">
            <span className="text-muted-foreground">{t.why}</span>
            <span className="text-primary">{t.conf[level]}</span>
          </div>
          <div className="mt-1.5 grid grid-cols-3 gap-1" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full ${i < (level === "HIGH" ? 3 : level === "MEDIUM" ? 2 : 1) ? "bg-primary" : "bg-muted"}`}
              />
            ))}
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {(item.basis === "PEERS" ? [t.noHistory] : reason ? [reason] : [])
              .concat(share != null ? [t.peerShare(share)] : [])
              .map((r) => (
                <li key={r} className="flex gap-2">
                  <span className="text-accent">◆</span>
                  {r}
                </li>
              ))}
          </ul>
        </div>

        <div className="mt-auto pt-3">
          <p className="text-[13px] font-semibold text-muted-foreground">{t.channels}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5 text-[13px] font-semibold">
            {chips.slice(0, 2).map((p) => (
              <span key={p.name} className="rounded-full bg-secondary px-2.5 py-1">
                {p.name} {p.eta}
              </span>
            ))}
            {chips.length > 2 && (
              <span className="rounded-full bg-secondary px-2.5 py-1">
                {t.more(chips.length - 2)}
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.article>
  );
}

function Stamp({
  children,
  className,
  style,
}: {
  children: string;
  className: string;
  style: object;
}) {
  return (
    <motion.div
      style={style}
      className={`pointer-events-none absolute z-20 rounded-xl border-[3px] bg-card px-3 py-1 text-lg font-black tracking-[0.15em] ${className}`}
    >
      {children}
    </motion.div>
  );
}

function ActionBtn({
  label,
  icon: Icon,
  onClick,
  disabled,
  tone,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  tone: "muted" | "destructive" | "accent" | "success";
}) {
  const tones = {
    muted: "bg-card text-muted-foreground",
    destructive: "bg-card text-destructive",
    accent: "bg-card text-accent",
    success: "bg-success text-success-foreground",
  };
  return (
    <motion.button
      whileTap={{ scale: 0.88 }}
      whileHover={{ y: -2 }}
      onClick={onClick}
      disabled={disabled}
      className="flex flex-col items-center gap-1.5 disabled:opacity-35"
    >
      <span className={`grid h-14 w-14 place-items-center rounded-full border ${tones[tone]}`}>
        <Icon aria-hidden className="h-6 w-6" strokeWidth={2.4} />
      </span>
      <span className="text-center text-[13px] font-semibold">{label}</span>
    </motion.button>
  );
}

function Toggle({ on }: { on: boolean }) {
  return (
    <span
      className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${on ? "bg-primary" : "bg-border"}`}
    >
      <motion.span
        layout
        transition={{ type: "spring", stiffness: 600, damping: 30 }}
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-card ${on ? "right-0.5" : "left-0.5"}`}
      />
    </span>
  );
}

function Sheet({ children, onClose }: { children: React.ReactNode; onClose?: () => void }) {
  return (
    <motion.div
      className="fixed inset-0 z-40 flex items-end justify-center bg-foreground/40"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        onClick={(e) => e.stopPropagation()}
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={{ type: "spring", stiffness: 340, damping: 32 }}
        className="w-full max-w-md rounded-t-3xl bg-card p-6 pb-8 shadow-card"
      >
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-border" />
        {children}
      </motion.div>
    </motion.div>
  );
}

function EditSheet({
  c,
  t,
  lang,
  onClose,
  onConfirm,
}: {
  c: Card;
  t: Dict;
  lang: Lang;
  onClose: () => void;
  onConfirm: (dbHours: string) => void;
}) {
  const [text, setText] = useState("");
  const parsed = useMemo(() => parseHours(text), [text]);
  return (
    <Sheet onClose={onClose}>
      <h3 className="font-display text-2xl font-semibold">
        {t.editTitle}: {holidayName(c.item.day_name, lang)}
      </h3>
      <p className="text-sm text-muted-foreground">{t.editHint}</p>
      <input
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t.placeholder}
        className="mt-4 w-full rounded-2xl border bg-background px-4 py-3.5 text-lg outline-none focus:ring-2 focus:ring-ring"
      />
      <div className="mt-3 flex flex-wrap gap-2">
        {["10 – 14", "9:00 - 13:00", t.closed].map((x) => (
          <button
            key={x}
            onClick={() => setText(x)}
            className="rounded-full bg-secondary px-3 py-1.5 text-xs font-semibold"
          >
            {x}
          </button>
        ))}
      </div>
      <div className="mt-4 rounded-2xl bg-muted p-4">
        <p className="text-xs font-semibold text-muted-foreground">{t.preview}</p>
        <p className="mt-1 text-xl font-bold">
          {parsed ? hoursLabel(toDbHours(parsed), t) : text ? t.noParse : "–"}
        </p>
      </div>
      <button
        disabled={!parsed}
        onClick={() => parsed && onConfirm(toDbHours(parsed))}
        className="mt-5 w-full rounded-full bg-primary py-4 font-semibold text-primary-foreground disabled:opacity-40"
      >
        {t.confirm}
      </button>
    </Sheet>
  );
}

function StandingSheet({ t, onChoose }: { t: Dict; onChoose: (on: boolean) => void }) {
  const [on, setOn] = useState(true);
  return (
    <Sheet>
      <h3 className="font-display text-2xl font-semibold">{t.standingQ}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{t.standingBody}</p>
      <button
        onClick={() => setOn(!on)}
        className="mt-5 flex w-full items-center justify-between gap-3 rounded-2xl bg-muted p-4 text-left font-semibold"
      >
        {t.standingToggle} <Toggle on={on} />
      </button>
      <button
        onClick={() => onChoose(on)}
        className="mt-4 w-full rounded-full bg-primary py-4 font-semibold text-primary-foreground"
      >
        {t.save}
      </button>
      <button
        onClick={() => onChoose(false)}
        className="mt-2 w-full py-2 text-sm font-semibold text-muted-foreground"
      >
        {t.keepAsking}
      </button>
    </Sheet>
  );
}

/** The real intro_text of the bundle on top of the deck, as the owner received it. */
function PhoneSheet({ t, text, onClose }: { t: Dict; text: string; onClose: () => void }) {
  return (
    <motion.div
      className="fixed inset-0 z-50 grid place-items-center bg-foreground/50 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        onClick={(e) => e.stopPropagation()}
        initial={{ scale: 0.85, y: 30 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
        className="w-full max-w-[340px]"
      >
        <div className="mb-3 flex flex-wrap justify-center gap-1 text-xs font-bold">
          {t.steps.map((s, i) => (
            <span
              key={s}
              className={`rounded-full px-2 py-1 ${i === 2 ? "bg-accent text-accent-foreground" : "bg-card text-muted-foreground"}`}
            >
              {s}
            </span>
          ))}
        </div>
        <div className="overflow-hidden rounded-[40px] border-[10px] border-foreground bg-secondary shadow-card">
          <div className="bg-primary px-4 pb-3 pt-5 text-primary-foreground">
            <p className="text-sm font-bold">Porchlight</p>
            <p className="text-xs opacity-80">Telegram</p>
          </div>
          <div className="max-h-[60dvh] space-y-2 overflow-y-auto p-3">
            <div className="whitespace-pre-line rounded-2xl rounded-tl-sm bg-card p-3 text-sm">
              {text}
            </div>
            <button
              onClick={onClose}
              className="w-full rounded-xl bg-card py-2 text-xs font-bold text-primary"
            >
              {t.tgLink}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

function Activity({
  history,
  onUndo,
  canUndoKey,
  t,
  lang,
  deck,
}: {
  history: HistoryEntry[];
  onUndo: () => void;
  canUndoKey?: string | undefined;
  t: Dict;
  lang: Lang;
  deck: Deck;
}) {
  if (!history.length)
    return <p className="mt-16 text-center text-muted-foreground">{t.nothing}</p>;
  const label = (o: Outcome) =>
    ({
      approved: t.approve,
      edited: t.edit,
      declined: t.no,
      regular: t.regularShort,
      auto: t.autoLabel,
    })[o];
  return (
    <ul className="mt-4 space-y-3">
      {history.map((h) => {
        const changed = h.outcome !== "declined";
        const apply = deck.applies.find((a) => a.bundle_id === h.bundle.bundle_id);
        const chips = publisherChips(h.bundle.publishers).slice(0, 4);
        return (
          <li key={h.key} className="rounded-2xl border bg-card p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-semibold">
                  {holidayName(h.item.day_name, lang)} · {dateLabel(h.item.date, lang)}
                </p>
                <p className="truncate text-sm text-muted-foreground">
                  {changed ? (
                    <>
                      <span className="line-through">{hoursLabel(h.item.shown_hours, t)}</span> →{" "}
                      <b className="text-foreground">{hoursLabel(h.hours, t)}</b>
                    </>
                  ) : (
                    `${t.kept} ${hoursLabel(h.item.shown_hours, t)}`
                  )}
                </p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${changed ? "bg-success/15 text-success" : "bg-muted text-muted-foreground"}`}
              >
                {label(h.outcome)}
              </span>
            </div>
            {changed && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
                <span className="rounded-full bg-secondary px-2 py-1 font-semibold">
                  {apply?.status === "SUCCESS" ? t.applied : t.pending}
                </span>
                {chips.map((p) => (
                  <span key={p.name} className="rounded-full bg-secondary px-2 py-1 font-semibold">
                    {p.name} {p.eta}
                  </span>
                ))}
              </div>
            )}
            {h.key === canUndoKey && (
              <button
                onClick={onUndo}
                className="mt-2 text-xs font-semibold text-primary underline"
              >
                {t.undo}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Empty({ t, count }: { t: Dict; count: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="absolute inset-0 grid place-items-center rounded-[28px] border border-dashed text-center"
    >
      <div className="px-6">
        <p className="font-display text-2xl font-semibold">{t.empty}</p>
        <p className="text-sm text-muted-foreground">{count ? t.emptySub(count) : t.emptyNone}</p>
      </div>
    </motion.div>
  );
}
