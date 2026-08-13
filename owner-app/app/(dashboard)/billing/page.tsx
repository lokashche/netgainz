import { redirect } from "next/navigation";
import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { assertFrappeSession, getSession } from "@/lib/session";
import type { BillingReadiness } from "@/lib/types";
import StartBillingPanel from "./StartBillingPanel";

/**
 * Start Billing — the go-live screen.
 *
 * Members loaded from the gym's own records are created without billing, so the
 * load cannot invoice periods the gym already collected in cash. Nothing turns
 * them back on; that is what this page is for. Preview who is ready, fix the ones
 * that are not, then commit.
 *
 * The readiness list is fetched on the SERVER (Next 16 steers client components to
 * the `use` API or SWR rather than useEffect + setState, and the other list pages
 * here already read this way). Only the preview/commit interaction is a client
 * component.
 */
export default async function StartBillingPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const { data, status } = await frappeRequest<{ message: BillingReadiness }>(
    "api/method/netgainz.net_gainz.accounting.go_live.billing_readiness",
    { sessionCookie: session.frappeCookies }
  );
  await assertFrappeSession(status);
  const readiness = data?.message;

  // Say what actually went wrong. A bare "could not load" on a finance screen
  // costs whoever reads it an afternoon; 401/403 in particular almost always
  // means the Frappe login behind the app session has gone, which looks
  // identical to "no data" everywhere else in the app.
  const failure = readiness
    ? null
    : status === 401 || status === 403
      ? "Your session with the backend has expired. Sign out and sign in again."
      : (extractFrappeError(data) ?? `The backend returned ${status}.`);

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-[#E6EDF7] mb-2">Start Billing</h1>
      <p className="text-sm text-[#8A97B2] mb-6">
        Members you loaded from your own records are not being billed yet. This page
        turns automatic billing on for them.
      </p>

      {readiness ? (
        <StartBillingPanel readiness={readiness} />
      ) : (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
          <p className="font-semibold">Could not load the billing preview.</p>
          <p className="mt-1">{failure}</p>
        </div>
      )}
    </div>
  );
}
