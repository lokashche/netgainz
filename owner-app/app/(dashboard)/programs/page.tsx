import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { Program } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Inactive", value: "inactive" },
];

function activeBadge(isActive: number): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  return isActive === 1
    ? `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`
    : `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
}

export default async function ProgramsPage({
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
  if (status === "active") filters.push(["is_active", "=", "1"]);
  if (status === "inactive") filters.push(["is_active", "=", "0"]);
  if (q) filters.push(["program_name", "like", `%${q}%`]);

  const requested = readPageParams(sp);
  const {
    rows: programs,
    total,
    page,
    pageSize,
  } = await fetchListPage<Program>({
    doctype: "Program",
    fields: ["name", "program_name", "description", "is_active"],
    filters,
    orderBy: "program_name asc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Programs</h1>
        <a
          href="/programs/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Program
        </a>
      </div>

      {/* Filters row */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        {/* Status tabs */}
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg overflow-x-auto ng-noscrollbar">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.value;
            // Changing the filter changes the result set, so drop the page number.
            const href = buildHref("/programs", sp, {
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
        {programs.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No programs found</p>
            <p className="text-sm mt-1">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Program Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Description
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Active
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {programs.map((program) => (
                  <tr
                    key={program.name}
                    className="hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/programs/${program.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {program.program_name}
                      </a>
                    </td>
                    <td className="px-6 py-4 max-w-xs">
                      <a
                        href={`/programs/${program.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2] truncate"
                      >
                        {program.description ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/programs/${program.name}`} className="block w-full h-full">
                        <span className={activeBadge(program.is_active)}>
                          {program.is_active === 1 ? "Active" : "Inactive"}
                        </span>
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
            basePath="/programs"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={programs.length}
            noun="programs"
          />
        )}
      </div>
    </div>
  );
}
