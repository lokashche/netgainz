import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { RenewalsDue, RenewalRow, TrialsEnding, TrialRow } from "@/lib/types";

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default async function RenewalsPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const res = await frappeRequest<{ message: RenewalsDue }>(
    `api/method/netgainz.net_gainz.operations.renewals.get_renewals_due`,
    { sessionCookie: session.frappeCookies }
  );
  const data = res.data?.message;

  // DS-4: a trial ending is the most useful follow-up a gym has — the member is in the
  // building today and starts paying tomorrow. It belongs on the same "who needs a word
  // today" page as renewals; Stage 9's pipeline turns it into a proper task.
  const trialRes = await frappeRequest<{ message: TrialsEnding }>(
    `api/method/netgainz.net_gainz.accounting.trials.trials_ending`,
    { sessionCookie: session.frappeCookies }
  );
  const trials = trialRes.data?.message;
  const trialsEnding: TrialRow[] = trials?.ending_soon ?? [];

  const overdue: RenewalRow[] = data?.overdue ?? [];
  const dueSoon: RenewalRow[] = data?.due_soon ?? [];
  const withinDays = data?.within_days ?? 0;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Renewals</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Memberships due for renewal within {withinDays} days. In-app only — no
          emails are sent.
        </p>
      </div>

      {trialsEnding.length > 0 && (
        <div className="mb-6 bg-[#111A2E] border border-[#5EEAD4] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1E2D45] bg-[rgba(94,234,212,0.12)]">
            <h2 className="text-sm font-semibold text-[#5EEAD4]">
              Free trials ending ({trialsEnding.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Member</th>
                  <th className="hidden md:table-cell text-left font-medium px-4 py-3">Plan</th>
                  <th className="text-left font-medium px-4 py-3">Trial Ends</th>
                  <th className="text-left font-medium px-4 py-3">First Invoice</th>
                  <th className="text-right font-medium px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {trialsEnding.map((t) => (
                  <tr
                    key={t.name}
                    className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/members/${t.member}`}
                        className="text-[#22D38C] hover:underline font-medium"
                      >
                        {t.member_name || t.member}
                      </Link>
                    </td>
                    <td className="hidden md:table-cell px-4 py-3 text-[#8A97B2]">{t.membership_plan || "—"}</td>
                    <td className="px-4 py-3 text-[#E6EDF7]">{fmtDate(t.trial_ends_on)}</td>
                    <td className="px-4 py-3 text-[#8A97B2]">
                      {fmtDate(
                        new Date(new Date(t.trial_ends_on).getTime() + 86400000)
                          .toISOString()
                          .slice(0, 10)
                      )}{" "}
                      · automatic
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/subscriptions/${t.name}`}
                        className="text-[#5EEAD4] hover:underline text-xs whitespace-nowrap"
                      >
                        Open membership →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {overdue.length === 0 && dueSoon.length === 0 ? (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-8 text-center text-[#8A97B2]">
          <p className="text-lg font-medium text-[#E6EDF7]">
            No memberships are due for renewal.
          </p>
          <p className="text-sm mt-1">
            You&apos;re all caught up for the next {withinDays} days.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {overdue.length > 0 && (
            <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-[#1E2D45] bg-[rgba(248,113,113,0.15)]">
                <h2 className="text-sm font-semibold text-[#F87171]">
                  Overdue ({overdue.length})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                      <th className="text-left font-medium px-4 py-3">Member</th>
                      <th className="hidden md:table-cell text-left font-medium px-4 py-3">Plan</th>
                      <th className="text-left font-medium px-4 py-3">
                        Next Renewal
                      </th>
                      <th className="text-left font-medium px-4 py-3">
                        Overdue by
                      </th>
                      <th className="text-left font-medium px-4 py-3">Phone</th>
                      <th className="text-right font-medium px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {overdue.map((r) => (
                      <tr
                        key={r.subscription}
                        className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/members/${r.member}`}
                            className="text-[#22D38C] hover:underline font-medium"
                          >
                            {r.member_name || r.member}
                          </Link>
                        </td>
                        <td className="hidden md:table-cell px-4 py-3 text-[#8A97B2]">
                          {r.membership_plan || "—"}
                        </td>
                        <td className="px-4 py-3 text-[#E6EDF7]">
                          {fmtDate(r.next_renewal)}
                        </td>
                        <td className="px-4 py-3 text-[#F87171]">
                          {Math.abs(r.days_until) + " days"}
                        </td>
                        <td className="px-4 py-3 text-[#8A97B2]">
                          {r.phone || "—"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            href="/subscriptions/new"
                            className="text-[#5EEAD4] hover:underline text-xs whitespace-nowrap"
                          >
                            Record renewal →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-[#1E2D45]">
              <h2 className="text-sm font-semibold text-[#E6EDF7]">
                Due Soon ({dueSoon.length})
              </h2>
            </div>
            {dueSoon.length === 0 ? (
              <div className="p-8 text-center text-[#8A97B2]">
                <p className="text-sm">No upcoming renewals in this window.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                      <th className="text-left font-medium px-4 py-3">Member</th>
                      <th className="hidden md:table-cell text-left font-medium px-4 py-3">Plan</th>
                      <th className="text-left font-medium px-4 py-3">
                        Next Renewal
                      </th>
                      <th className="text-left font-medium px-4 py-3">In</th>
                      <th className="text-left font-medium px-4 py-3">Phone</th>
                      <th className="text-right font-medium px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {dueSoon.map((r) => (
                      <tr
                        key={r.subscription}
                        className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/members/${r.member}`}
                            className="text-[#22D38C] hover:underline font-medium"
                          >
                            {r.member_name || r.member}
                          </Link>
                        </td>
                        <td className="hidden md:table-cell px-4 py-3 text-[#8A97B2]">
                          {r.membership_plan || "—"}
                        </td>
                        <td className="px-4 py-3 text-[#E6EDF7]">
                          {fmtDate(r.next_renewal)}
                        </td>
                        <td className="px-4 py-3 text-[#8A97B2]">
                          {r.days_until + " days"}
                        </td>
                        <td className="px-4 py-3 text-[#8A97B2]">
                          {r.phone || "—"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            href="/subscriptions/new"
                            className="text-[#5EEAD4] hover:underline text-xs whitespace-nowrap"
                          >
                            Record renewal →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
