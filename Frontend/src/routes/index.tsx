import { createFileRoute, useRouter } from "@tanstack/react-router";
import { OwnerApp } from "@/components/owner-app";
import { OWNER_HEAD, OwnerError } from "@/components/owner-route";
import { getDeck } from "@/lib/connect/api";

/** The demo business: FI-D0017 Kahvila Kipinä (new customer, no history), the one set up on the Yext sandbox. */
const DEMO_ENTITY = "FI-D0017";

export const Route = createFileRoute("/")({
  head: () => OWNER_HEAD,
  loader: () => getDeck({ data: { entity: DEMO_ENTITY } }),
  errorComponent: OwnerError,
  component: Home,
});

function Home() {
  const deck = Route.useLoaderData();
  const router = useRouter();
  return <OwnerApp deck={deck} onChanged={() => router.invalidate()} />;
}
