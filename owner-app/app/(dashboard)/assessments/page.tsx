import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { AssessmentsDue, AssessmentDueRow, AssessmentNeverRow } from "@/lib/types";

// OP-5: who is due to be measured again, and who has never been measured at all.
// Only a member's LATEST assessment decides whether they are due, so a member
// re-measured yesterday never lingers here because of an older visit.

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function DueTable({
  rows,
  accent,
  title,
}: {
  rows: AssessmentDueRow[];
  accent: string;
  title: string;
}) {
  return (
    <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden mb-6">
      <div className="px-4 py-3 border-b border-[#1E2D45]" style={{ backgroundColor: `${accent}1F` }}>
        <h2 className="text-sm font-semibold" style={{ color: accent }}>
          {title} ({rows.length})
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
              <th className="text-left font-medium px-4 py-3">Member</th>
              <th className="text-left font-medium px-4 py-3">Goal</th>
              <th className="text-left font-medium px-4 py-3">Coach</th>
              <th className="text-left font-medium px-4 py-3">Last Measured</th>
              <th className="text-left font-medium px-4 py-3">Due</th>
              <th className="text-right font-medium px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.member}
                className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/members/${r.member}`}
                    className="text-[#22D38C] hover:underline font-medium"
                  >
                    {r.member_name || r.member}
                  </Link>
                  {r.phone ? <span className="text-[#8A97B2] text-xs"> · {r.phone}</span> : null}
                </td>
                <td className="px-4 py-3 text-[#8A97B2]">{r.sport_goal || "—"}</td>
                <td className="px-4 py-3 text-[#8A97B2]">{r.coach || "—"}</td>
                <td className="px-4 py-3 text-[#E6EDF7]">{fmtDate(r.last_assessment)}</td>
                <td className="px-4 py-3 tabular-nums" style={{ color: accent }}>
                  {fmtDate(r.next_due_date)}
                  <span className="text-xs">
                    {r.days_until < 0
                      ? ` · ${Math.abs(r.days_until)}d late`
                      : r.days_until === 0
                        ? " · today"
                        : ` · in ${r.days_until}d`}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/members/${r.member}`}
                    className="text-[#5EEAD4] hover:underline text-xs whitespace-nowrap"
                  >
                    Measure →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default async function AssessmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const within = typeof sp.within_days === "string" ? sp.within_days : "";
  const qs = within ? `?within_days=${encodeURIComponent(within)}` : "";

  const res = await frappeRequest<{ message: AssessmentsDue }>(
    `api/method/netgainz.net_gainz.operations.assessments.get_assessments_due${qs}`,
    { sessionCookie: session.frappeCookies }
  );
  const data = res.data?.message;
  // A failed call must not read as "everyone is up to date" — an empty list and a
  // broken backend look identical once the payload is gone.
  const failed = !res.data || res.status >= 400;

  const overdue: AssessmentDueRow[] = data?.overdue ?? [];
  const dueSoon: AssessmentDueRow[] = data?.due_soon ?? [];
  const never: AssessmentNeverRow[] = data?.never_assessed ?? [];
  const windowDays = data?.within_days ?? 7;

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Assessments</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            A member who can see themselves improving renews. These are the ones due to be
            measured again — the window and the interval are set in Settings.
          </p>
        </div>
        <Link
          href="/assessments/metrics"
          className="text-xs border border-[#1E2D45] text-[#8A97B2] rounded-lg py-1.5 px-3 hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors whitespace-nowrap"
        >
          What we measure →
        </Link>
      </div>

      {failed && (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171] mb-4">
          Could not load assessments just now. This is not the same as nobody being due —
          reload in a moment.
        </div>
      )}

      {!failed && overdue.length === 0 && dueSoon.length === 0 && never.length === 0 && (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-8 text-center text-[#8A97B2]">
          <p className="text-lg font-medium text-[#E6EDF7]">Everyone is up to date.</p>
          <p className="text-sm mt-1">
            No active member is due for re-assessment in the next {windowDays} days.
          </p>
        </div>
      )}

      {overdue.length > 0 && <DueTable rows={overdue} accent="#F87171" title="Overdue" />}
      {dueSoon.length > 0 && (
        <DueTable rows={dueSoon} accent="#FBBF24" title={`Due within ${windowDays} days`} />
      )}

      {never.length > 0 && (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1E2D45] bg-[rgba(94,234,212,0.12)]">
            <h2 className="text-sm font-semibold text-[#5EEAD4]">
              Never measured ({never.length})
            </h2>
            <p className="text-xs text-[#8A97B2] mt-0.5">
              Not overdue — there is simply no baseline yet. The first assessment is what
              every later one is read against.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Member</th>
                  <th className="text-left font-medium px-4 py-3">Goal</th>
                  <th className="text-left font-medium px-4 py-3">Category</th>
                  <th className="text-left font-medium px-4 py-3">Coach</th>
                  <th className="text-right font-medium px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {never.map((r) => (
                  <tr
                    key={r.member}
                    className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/members/${r.member}`}
                        className="text-[#22D38C] hover:underline font-medium"
                      >
                        {r.member_name || r.member}
                      </Link>
                      {r.phone ? <span className="text-[#8A97B2] text-xs"> · {r.phone}</span> : null}
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">{r.sport_goal || "—"}</td>
                    <td className="px-4 py-3 text-[#8A97B2]">{r.category || "—"}</td>
                    <td className="px-4 py-3 text-[#8A97B2]">{r.coach || "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/members/${r.member}`}
                        className="text-[#5EEAD4] hover:underline text-xs whitespace-nowrap"
                      >
                        Measure →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
