import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { ClassBooking, ClassBookingStatus } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Booked", value: "Booked" },
  { label: "Attended", value: "Attended" },
  { label: "No Show", value: "No Show" },
  { label: "Cancelled", value: "Cancelled" },
];

function fmtDateTime(value?: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function statusBadge(status: ClassBookingStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Booked":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Attended":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "No Show":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    case "Cancelled":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

export default async function AttendancePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const status = typeof sp.status === "string" ? sp.status : "";
  const q = typeof sp.q === "string" ? sp.q : "";

  const filters: string[][] = [];
  if (status) filters.push(["status", "=", status]);
  if (q) filters.push(["member_name", "like", `%${q}%`]);

  const requested = readPageParams(sp);
  const {
    rows: bookings,
    total,
    page,
    pageSize,
  } = await fetchListPage<ClassBooking>({
    doctype: "Session Booking",
    fields: [
      "name",
      "class_session",
      "member",
      "member_name",
      "coach",
      "start_time",
      "status",
      "check_in_time",
    ],
    filters,
    orderBy: "start_time desc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Attendance</h1>
      </div>

      {/* Filters row */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        {/* Status tabs */}
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.value;
            // Changing the filter changes the result set, so drop the page number.
            const href = buildHref("/attendance", sp, {
              status: tab.value || undefined,
              page: undefined,
            });
            return (
              <a
                key={tab.value}
                href={href}
                className={
                  isActive
                    ? "px-3 py-1.5 text-sm font-semibold rounded-md bg-[#22D38C] text-[#0B1220]"
                    : "px-3 py-1.5 text-sm font-medium rounded-md text-[#8A97B2] hover:text-[#E6EDF7]"
                }
              >
                {tab.label}
              </a>
            );
          })}
        </div>

        {/* Search */}
        <form method="GET" className="flex gap-2 flex-1 max-w-sm">
          {status && <input type="hidden" name="status" value={status} />}
          <input type="hidden" name="size" value={pageSize} />
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder="Search by member…"
            className="flex-1 px-3 py-2 text-sm rounded-lg focus:outline-none focus:ring-2 bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C]"
          />
          <button
            type="submit"
            className="px-3 py-2 text-sm bg-[#1A2540] text-[#E6EDF7] border border-[#1E2D45] hover:bg-[#22D38C] hover:text-[#0B1220] rounded-lg transition-colors"
          >
            Search
          </button>
        </form>
      </div>

      {/* Table */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {bookings.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No attendance records</p>
            <p className="text-sm mt-1">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Member
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Class
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Coach
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Start Time
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Status
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Check-in
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {bookings.map((booking) => (
                  <tr
                    key={booking.name}
                    className="hover:bg-[#1A2540] transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/members/${booking.member}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {booking.member_name ?? booking.member}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/classes/${booking.class_session}`}
                        className="block w-full h-full text-sm font-mono text-[#5EEAD4]"
                      >
                        {booking.class_session}
                      </a>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap text-sm text-[#8A97B2]">
                      {booking.coach ?? "—"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-[#8A97B2]">
                      {fmtDateTime(booking.start_time)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={statusBadge(booking.status)}>{booking.status}</span>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap text-sm text-[#8A97B2]">
                      {fmtDateTime(booking.check_in_time)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && (
          <Pagination
            basePath="/attendance"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={bookings.length}
            noun="records"
          />
        )}
      </div>
    </div>
  );
}
