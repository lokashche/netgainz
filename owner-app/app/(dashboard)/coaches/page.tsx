import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { Coach, CoachStatus } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Active", value: "Active" },
  { label: "Inactive", value: "Inactive" },
];

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function commissionLabel(coach: Coach): string {
  const type = coach.commission_type ?? "None";
  if (type === "None") return "—";
  if (type === "Percentage") return `${type} · ${money(coach.commission_amount)}%`;
  return `${type} · ₹${money(coach.commission_amount)}`;
}

function statusBadge(status: CoachStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Active":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Inactive":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

export default async function CoachesPage({
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
  if (q) filters.push(["coach_name", "like", `%${q}%`]);

  const requested = readPageParams(sp);
  const {
    rows: coaches,
    total,
    page,
    pageSize,
  } = await fetchListPage<Coach>({
    doctype: "Instructor",
    fields: [
      "name",
      "coach_name",
      "phone",
      "email",
      "specialization",
      "commission_type",
      "commission_amount",
      "status",
    ],
    filters,
    orderBy: "coach_name asc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Coaches</h1>
        <a
          href="/coaches/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Coach
        </a>
      </div>

      {/* Filters row */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        {/* Status tabs */}
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg overflow-x-auto ng-noscrollbar">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.value;
            // Changing the filter changes the result set, so drop the page number.
            const href = buildHref("/coaches", sp, {
              status: tab.value || undefined,
              page: undefined,
            });
            return (
              <a
                key={tab.value}
                href={href}
                className={
                  isActive
                    ? "px-3 py-2.5 sm:py-1.5 text-sm font-semibold rounded-md whitespace-nowrap shrink-0 flex items-center bg-[#22D38C] text-[#0B1220]"
                    : "px-3 py-2.5 sm:py-1.5 text-sm font-medium rounded-md whitespace-nowrap shrink-0 flex items-center text-[#8A97B2] hover:text-[#E6EDF7]"
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
            placeholder="Search by name…"
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
        {coaches.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No coaches found</p>
            <p className="text-sm mt-1">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Coach Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Phone
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Specialization
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Commission
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {coaches.map((coach) => (
                  <tr
                    key={coach.name}
                    className="hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/coaches/${coach.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {coach.coach_name}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/coaches/${coach.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {coach.phone ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/coaches/${coach.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {coach.specialization ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/coaches/${coach.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {commissionLabel(coach)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/coaches/${coach.name}`} className="block w-full h-full">
                        <span className={statusBadge(coach.status)}>{coach.status}</span>
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && (
          <Pagination
            basePath="/coaches"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={coaches.length}
            noun="coaches"
          />
        )}
      </div>
    </div>
  );
}
