import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { branchParam, currentBranch } from "@/lib/branchScope";
import { redirect } from "next/navigation";
import Link from "next/link";

type Row = {
  coach: string;
  members: number;
  classes: number;
  bookings: number;
  attended: number;
  attendance_pct: number | null;
  commission: number | null;
};

const th = "px-4 py-2 font-medium text-right whitespace-nowrap";
const td = "px-4 py-2 text-right whitespace-nowrap text-[#E6EDF7]";

/**
 * Stage 11.2 — each coach's month: members, classes, bookings, attendance and
 * commission (the same figure as the Commissions page). Same ?month=<offset>
 * convention as the dashboard.
 */
export default async function CoachReportPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const offset = Number(typeof sp.month === "string" ? sp.month : 0) || 0;
  const now = new Date();
  const target = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const mm = String(target.getMonth() + 1).padStart(2, "0");
  const start = `${target.getFullYear()}-${mm}-01`;
  const end = `${target.getFullYear()}-${mm}-${new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()}`;
  const branch = await currentBranch();

  const { data, status } = await frappeRequest<{ message: { rows: Row[]; commission_shown: boolean } }>(
    `api/method/netgainz.net_gainz.operations.commissions.get_coach_report?start=${start}&end=${end}${branchParam(branch)}`,
    { sessionCookie: session.frappeCookies }
  );
  const r = data?.message;

  const tab = (text: string, value: number) => (
    <Link
      key={value}
      href={value ? `/coach-report?month=${value}` : "/coach-report"}
      className={
        offset === value
          ? "px-3 py-2.5 sm:py-1.5 text-sm font-semibold rounded-md whitespace-nowrap bg-[#22D38C] text-[#0B1220]"
          : "px-3 py-2.5 sm:py-1.5 text-sm font-medium rounded-md whitespace-nowrap text-[#8A97B2] hover:text-[#E6EDF7]"
      }
    >
      {text}
    </Link>
  );

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Coach Report</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            {target.toLocaleString("en-US", { month: "long", year: "numeric" })}
            {branch ? ` · ${branch}` : ""}. Attendance counts only visits the desk marked as attended or no-show.
            {branch && r?.commission_shown ? " Commission is for the whole gym." : ""}
          </p>
        </div>
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg">
          {tab("This month", 0)}
          {tab("Last month", -1)}
          {tab("2 months ago", -2)}
        </div>
      </div>

      {!r ? (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {extractFrappeError(data) ?? `Could not load (${status})`}
        </div>
      ) : (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                <th className="px-4 py-2 font-medium text-left">Coach</th>
                <th className={th}>Members</th>
                <th className={th}>Classes</th>
                <th className={th}>Bookings</th>
                <th className={th}>Attended</th>
                <th className={th}>Attendance</th>
                {r.commission_shown && <th className={th}>Commission</th>}
              </tr>
            </thead>
            <tbody>
              {r.rows.map((c) => (
                <tr key={c.coach} className="border-b border-[#1E2D45]">
                  <td className="px-4 py-2 text-[#E6EDF7] whitespace-nowrap">{c.coach}</td>
                  <td className={td}>{c.members}</td>
                  <td className={td}>{c.classes}</td>
                  <td className={td}>{c.bookings}</td>
                  <td className={td}>{c.attended}</td>
                  <td className={td}>{c.attendance_pct === null ? "—" : `${c.attendance_pct}%`}</td>
                  {r.commission_shown && (
                    <td className={td}>
                      ₹{(c.commission ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
