import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { Subscription, SubscriptionStatus } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Pending", value: "Pending" },
  { label: "Paid", value: "Paid" },
  { label: "Overdue", value: "Overdue" },
  { label: "Partial", value: "Partial" },
  { label: "Written Off", value: "Written Off" },
];

function statusBadge(status: SubscriptionStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Paid":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Pending":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Overdue":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    case "Partial":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    case "Written Off":
      // WP-8: settled as uncollectable, not collected.
      return `${base} bg-[rgba(251,191,36,0.15)] text-[#FBBF24]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

function tabClass(isActive: boolean, value: string): string {
  const base = "px-3 py-1.5 text-sm font-medium rounded-md transition-colors";
  if (!isActive) return `${base} text-[#8A97B2] hover:text-[#E6EDF7]`;
  switch (value) {
    case "Paid":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C] font-semibold`;
    case "Overdue":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171] font-semibold`;
    case "Partial":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4] font-semibold`;
    case "Written Off":
      return `${base} bg-[rgba(251,191,36,0.15)] text-[#FBBF24] font-semibold`;
    default:
      return `${base} bg-[#22D38C] text-[#0B1220] font-semibold`;
  }
}

function formatCurrency(value?: number): string {
  if (value === undefined || value === null) return "—";
  return Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default async function SubscriptionsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const statusFilter = typeof sp.status === "string" ? sp.status : "";
  const memberFilter = typeof sp.member === "string" ? sp.member : "";

  const filters: string[][] = [];
  if (statusFilter) filters.push(["status", "=", statusFilter]);
  if (memberFilter) filters.push(["member", "=", memberFilter]);

  const requested = readPageParams(sp);
  const {
    rows: subscriptions,
    total,
    page,
    pageSize,
  } = await fetchListPage<Subscription>({
    doctype: "Membership",
    fields: [
      "name",
      "member",
      "member_name",
      "membership_plan",
      "month",
      "tariff",
      "fee_collected",
      "balance_due",
      "status",
      "due_date",
    ],
    filters,
    orderBy: "due_date desc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Subscriptions</h1>
        <a
          href="/subscriptions/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Subscription
        </a>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg mb-6 flex-wrap">
        {STATUS_TABS.map((tab) => {
          const isActive = statusFilter === tab.value;
          // Changing the filter changes the result set, so drop the page number.
          const href = buildHref("/subscriptions", sp, {
            status: tab.value || undefined,
            page: undefined,
          });
          return (
            <a
              key={tab.value}
              href={href}
              className={tabClass(isActive, tab.value)}
            >
              {tab.label}
            </a>
          );
        })}
      </div>

      {/* Table */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {subscriptions.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No subscriptions found</p>
            <p className="text-sm mt-1">Try adjusting your filters or add a new subscription.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Sub ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Member Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Plan
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Month
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Tariff
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Collected
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Balance Due
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Status
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Due Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {subscriptions.map((sub) => (
                  <tr
                    key={sub.name}
                    className="border-b border-[#1E2D45] hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full font-mono text-[#5EEAD4] text-sm"
                      >
                        {sub.name}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {sub.member_name ?? sub.member}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {sub.membership_plan ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {sub.month ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {formatCurrency(sub.tariff)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {formatCurrency(sub.fee_collected)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm font-medium"
                      >
                        <span className={Number(sub.balance_due) > 0 ? "text-[#F87171]" : "text-[#22D38C]"}>
                          {formatCurrency(sub.balance_due)}
                        </span>
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/subscriptions/${sub.name}`} className="block w-full h-full">
                        <span className={statusBadge(sub.status)}>{sub.status}</span>
                      </a>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/subscriptions/${sub.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {sub.due_date ?? "—"}
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
            basePath="/subscriptions"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={subscriptions.length}
            noun="subscriptions"
          />
        )}
      </div>
    </div>
  );
}
