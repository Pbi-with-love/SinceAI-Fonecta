// Shared pieces of the two owner routes: "/" (demo business) and "/o/$entity?t=<token>" (signed link).
import { useRouter } from "@tanstack/react-router";
import { DICTS } from "@/lib/i18n";

export const OWNER_HEAD = {
  meta: [
    { title: "Porchlight — Holiday hours in one swipe" },
    {
      name: "description",
      content:
        "Porchlight: approve the suggested holiday hours with a swipe, no login.",
    },
    { property: "og:title", content: "Porchlight — Holiday hours in one swipe" },
    {
      property: "og:description",
      content:
        "Approve suggested holiday hours, published via Yext to Google, Apple Maps and Bing.",
    },
    { property: "og:type", content: "website" },
  ],
};

/** A failed load says what failed inside the app frame, with a retry (or the bad-link note). */
export function OwnerError({ error }: { error: unknown }) {
  const router = useRouter();
  const t = DICTS.en;
  const bad = error instanceof Error && error.message.includes("BAD_LINK");
  return (
    <div className="mx-auto flex min-h-[100dvh] max-w-md flex-col justify-center px-5">
      <p className="text-sm font-semibold text-muted-foreground">Porchlight</p>
      <h1 className="mt-1 font-display text-2xl font-semibold">{bad ? t.badLink : t.loadError}</h1>
      {!bad && (
        <button
          onClick={() => router.invalidate()}
          className="mt-4 w-fit rounded-full bg-primary px-5 py-3 font-semibold text-primary-foreground"
        >
          {t.retry}
        </button>
      )}
    </div>
  );
}
