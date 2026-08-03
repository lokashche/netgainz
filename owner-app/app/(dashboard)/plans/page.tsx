import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { fetchListPage, readPageParams, type SearchParamsObj } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { MembershipPlan } from "@/lib/types";

type SearchParams = Promise<SearchParamsObj>;

function activeBadge(isActive: 0 | 1): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  if (isActive === 1) {
    return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
  }
  return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
}

function formatCurrency(value?: number): string {
  if (value === undefined || value === null) return "—";
  return Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default async function PlansPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const requested = readPageParams(sp);
  const {
    rows: plans,
    total,
    page,
    pageSize,
  } = await fetchListPage<MembershipPlan>({
    doctype: "Membership Plan",
    fields: ["name", "plan_name", "duration_in_days", "amount", "is_active"],
    orderBy: "plan_name asc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Membership Plans</h1>
        <a
          href="/plans/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Plan
        </a>
      </div>

      {/* Table */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {plans.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No membership plans found</p>
            <p className="text-sm mt-1">Add your first plan to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Plan Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Duration (Days)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {plans.map((plan) => (
                  <tr
                    key={plan.name}
                    className="border-b border-[#1E2D45] hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/plans/${encodeURIComponent(plan.name)}`}
                        className="block w-full h-full text-sm text-[#E6EDF7] font-medium"
                      >
                        {plan.plan_name}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/plans/${encodeURIComponent(plan.name)}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {plan.duration_in_days ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/plans/${encodeURIComponent(plan.name)}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {formatCurrency(plan.amount)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/plans/${encodeURIComponent(plan.name)}`} className="block w-full h-full">
                        <span className={activeBadge(plan.is_active)}>
                          {plan.is_active === 1 ? "Active" : "Inactive"}
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
            basePath="/plans"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={plans.length}
            noun="plans"
          />
        )}
      </div>
    </div>
  );
}
