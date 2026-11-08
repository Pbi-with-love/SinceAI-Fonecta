import { createFileRoute, useRouter } from "@tanstack/react-router";
import { OwnerApp } from "@/components/owner-app";
import { OWNER_HEAD, OwnerError } from "@/components/owner-route";
import { getDeck } from "@/lib/connect/api";

/** The no-login owner link sent in the Telegram message: /o/<entity_id>?t=<HMAC token>. */
export const Route = createFileRoute("/o/$entity")({
  head: () => OWNER_HEAD,
  validateSearch: (s: Record<string, unknown>) => ({
    t: typeof s["t"] === "string" ? (s["t"] as string) : undefined,
  }),
  loaderDeps: ({ search }) => ({ t: search.t }),
  loader: ({ params, deps }) => getDeck({ data: { entity: params.entity, t: deps.t } }),
  errorComponent: OwnerError,
  component: OwnerLink,
});

function OwnerLink() {
  const deck = Route.useLoaderData();
  const { t } = Route.useSearch();
  const router = useRouter();
  return <OwnerApp deck={deck} token={t} onChanged={() => router.invalidate()} />;
}
