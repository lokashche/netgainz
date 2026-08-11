import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { ChurnRisk, ChurnRiskRow } from "@/lib/types";

// OP-1: active members not seen at the gym within the absence window. A visit is
// a desk check-in OR an attended class; absence is only measured from the day the
// gym started recording visits, so the list is empty until check-in is in use.

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

export default async function ChurnRiskPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const res = await frappeRequest<{ message: ChurnRisk }>(
    `api/method/netgainz.net_gainz.operations.checkin.get_churn_risk`,
    { sessionCookie: session.frappeCookies }
  );
  const data = res.data?.message;

  const absent: ChurnRiskRow[] = data?.absent ?? [];
  const threshold = data?.threshold_days ?? 14;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Churn Risk</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Active members not seen in {threshold}+ days — a call now is cheaper than a
          cancellation next month. The window is configurable in Settings.
        </p>
      </div>

      {absent.length === 0 ? (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-8 text-center text-[#8A97B2]">
          <p className="text-lg font-medium text-[#E6EDF7]">
            Everyone has been in recently.
          </p>
          <p className="text-sm mt-1">
            No active member has stayed away for {threshold}+ days.
          </p>
        </div>
      ) : (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1E2D45] bg-[rgba(251,191,36,0.12)]">
            <h2 className="text-sm font-semibold text-[#FBBF24]">
              Not seen in {threshold}+ days ({absent.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Member</th>
                  <th className="text-left font-medium px-4 py-3">Phone</th>
                  <th className="text-left font-medium px-4 py-3">Last Visit</th>
                  <th className="text-left font-medium px-4 py-3">Away For</th>
                  <th className="text-right font-medium px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {absent.map((r) => (
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
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">{r.phone || "—"}</td>
                    <td className="px-4 py-3 text-[#E6EDF7]">
                      {r.never_visited ? (
                        <span className="text-[#8A97B2]">
                          Never checked in
                        </span>
                      ) : (
                        fmtDate(r.last_visit)
                      )}
                    </td>
                    <td className="px-4 py-3 text-[#FBBF24]">{r.days_absent} days</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/members/${r.member}`}
                        className="text-[#5EEAD4] hover:underline text-xs whitespace-nowrap"
                      >
                        Open member →
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
