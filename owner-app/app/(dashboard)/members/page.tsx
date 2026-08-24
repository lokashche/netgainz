import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { Member, MemberStatus } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Active", value: "Active" },
  { label: "Inactive", value: "Inactive" },
  { label: "Frozen", value: "Frozen" },
];

function statusBadge(status: MemberStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Active":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Inactive":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Frozen":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

export default async function MembersPage({
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
  // A query with a digit in it is a member ID (KE1105, or just 1105); anything
  // else is a name. IDs always carry digits and people's names never do.
  if (q) {
    filters.push(
      /\d/.test(q) ? ["name", "like", `%${q}%`] : ["full_name", "like", `%${q}%`]
    );
  }

  const requested = readPageParams(sp);
  const {
    rows: members,
    total,
    page,
    pageSize,
  } = await fetchListPage<Member>({
    doctype: "Member",
    fields: ["name", "full_name", "phone", "email", "status"],
    filters,
    orderBy: "full_name asc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Members</h1>
        <div className="flex items-center gap-3">
          <a
            href={buildHref("/api/members/export", {}, { status: status || undefined, q: q || undefined })}
            download
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg border border-[#1E2D45] text-[#8A97B2] hover:text-[#E6EDF7] hover:border-[#22D38C] transition-colors"
          >
            Download CSV
          </a>
          <a
            href="/members/new"
            className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
          >
            Add Member
          </a>
        </div>
      </div>

      {/* Filters row */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        {/* Status tabs */}
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg overflow-x-auto ng-noscrollbar">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.value;
            // Changing the filter changes the result set, so drop the page number.
            const href = buildHref("/members", sp, {
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
            placeholder="Search by name or ID…"
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
        {members.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No members found</p>
            <p className="text-sm mt-1">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Member ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Full Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Phone
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {members.map((member) => (
                  <tr
                    key={member.name}
                    className="hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/members/${member.name}`}
                        className="block w-full h-full text-sm font-mono text-[#5EEAD4]"
                      >
                        {member.name}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/members/${member.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {member.full_name}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/members/${member.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {member.phone ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/members/${member.name}`} className="block w-full h-full">
                        <span className={statusBadge(member.status)}>{member.status}</span>
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
            basePath="/members"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={members.length}
            noun="members"
          />
        )}
      </div>
    </div>
  );
}
