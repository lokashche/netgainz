import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import RepeatingExpensesBanner from "@/app/components/RepeatingExpensesBanner";
import type { GymExpense, ExpenseCategory } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

// One row per is_recurring value, so the summary cards can cover every matching
// expense without pulling them all down.
type ExpenseSummaryRow = { is_recurring: 0 | 1; cnt: number; amt: number | null };

function formatDate(dateStr?: string): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatAmount(amount?: number): string {
  if (amount === undefined || amount === null) return "—";
  return Number(amount).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default async function ExpensesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const categoryFilter = typeof sp.category === "string" ? sp.category : "";
  const recurringFilter = typeof sp.recurring === "string" ? sp.recurring : "";

  const filters: string[][] = [];
  if (categoryFilter) filters.push(["category", "=", categoryFilter]);
  if (recurringFilter === "1") filters.push(["is_recurring", "=", "1"]);
  else if (recurringFilter === "0") filters.push(["is_recurring", "=", "0"]);

  // Roll the summary up in the database so the cards describe every matching
  // expense rather than only the page on screen.
  const summaryParams = new URLSearchParams();
  summaryParams.set(
    "fields",
    JSON.stringify(["is_recurring", "count(name) as cnt", "sum(amount) as amt"])
  );
  if (filters.length > 0) summaryParams.set("filters", JSON.stringify(filters));
  summaryParams.set("group_by", "is_recurring");
  summaryParams.set("limit_page_length", "0");

  const requested = readPageParams(sp);

  const [listResult, categoriesRes, summaryRes] = await Promise.all([
    fetchListPage<GymExpense>({
      doctype: "Expense",
      fields: ["name", "date", "category", "amount", "vendor", "is_recurring", "frequency"],
      filters,
      orderBy: "date desc",
      sessionCookie: session.frappeCookies,
      ...requested,
    }),
    frappeRequest<{ data: ExpenseCategory[] }>(
      `api/resource/Expense%20Category?fields=${encodeURIComponent(JSON.stringify(["name", "category_name"]))}&order_by=${encodeURIComponent("category_name asc")}&limit_page_length=0`,
      { sessionCookie: session.frappeCookies }
    ),
    frappeRequest<{ data: ExpenseSummaryRow[] }>(
      `api/resource/Expense?${summaryParams.toString()}`,
      { sessionCookie: session.frappeCookies }
    ),
  ]);

  const { rows: expenses, total, page, pageSize } = listResult;
  const categories: ExpenseCategory[] = categoriesRes.data?.data ?? [];

  // Summary stats, across all expenses matching the current filters
  const summary: ExpenseSummaryRow[] = summaryRes.data?.data ?? [];
  const totalAmount = summary.reduce((sum, r) => sum + (Number(r.amt) || 0), 0);
  const recurringCount =
    summary.find((r) => Number(r.is_recurring) === 1)?.cnt ?? 0;
  const oneTimeCount = summary.find((r) => Number(r.is_recurring) === 0)?.cnt ?? 0;

  const hasFilters = Boolean(categoryFilter || recurringFilter);

  // Changing the filter changes the result set, so drop the page number.
  function recurringTabHref(val: string): string {
    return buildHref("/expenses", sp, { recurring: val || undefined, page: undefined });
  }

  // Build clear filters href
  const clearHref = "/expenses";

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Expenses</h1>
        <a
          href="/expenses/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Expense
        </a>
      </div>

      {/* Repeating expenses the app is behind on, raised as drafts */}
      <RepeatingExpensesBanner />

      {/* Summary stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">Total Expenses</p>
          <p className="text-[#E6EDF7] text-xl font-bold">
            ₹{formatAmount(totalAmount)}
          </p>
        </div>
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">Recurring</p>
          <p className="text-[#E6EDF7] text-xl font-bold">{recurringCount}</p>
        </div>
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">One-time</p>
          <p className="text-[#E6EDF7] text-xl font-bold">{oneTimeCount}</p>
        </div>
      </div>

      {/* Filter controls */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6 items-start sm:items-center">
        {/* Recurring tabs */}
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg">
          {[
            { label: "All", value: "" },
            { label: "Recurring", value: "1" },
            { label: "One-time", value: "0" },
          ].map((tab) => {
            const isActive = recurringFilter === tab.value;
            return (
              <a
                key={tab.value}
                href={recurringTabHref(tab.value)}
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

        {/* Category filter form */}
        <form method="GET" className="flex gap-2 items-center">
          {recurringFilter && <input type="hidden" name="recurring" value={recurringFilter} />}
          <input type="hidden" name="size" value={pageSize} />
          <select
            name="category"
            defaultValue={categoryFilter}
            className="px-3 py-2 text-sm rounded-lg focus:outline-none focus:ring-2 bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] focus:ring-[#22D38C] appearance-none"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat.name} value={cat.name}>
                {cat.category_name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="px-3 py-2 text-sm bg-[#1A2540] text-[#E6EDF7] border border-[#1E2D45] hover:bg-[#22D38C] hover:text-[#0B1220] rounded-lg transition-colors"
          >
            Filter
          </button>
        </form>

        {/* Clear filters */}
        {hasFilters && (
          <a
            href={clearHref}
            className="text-[#8A97B2] hover:text-[#22D38C] text-sm transition-colors"
          >
            Clear filters
          </a>
        )}
      </div>

      {/* Table */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {expenses.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No expenses found</p>
            <p className="text-sm mt-1">Try adjusting your filters or add a new expense.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Category
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Vendor
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Type
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Frequency
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {expenses.map((exp) => (
                  <tr
                    key={exp.name}
                    className="border-b border-[#1E2D45] hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/expenses/${exp.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {formatDate(exp.date)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/expenses/${exp.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {exp.category ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/expenses/${exp.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {exp.vendor ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <a
                        href={`/expenses/${exp.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        ₹{formatAmount(exp.amount)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/expenses/${exp.name}`} className="block w-full h-full">
                        {exp.is_recurring === 1 ? (
                          <span className="bg-[rgba(94,234,212,0.15)] text-[#5EEAD4] text-xs font-medium px-2.5 py-0.5 rounded-full">
                            Recurring
                          </span>
                        ) : (
                          <span className="bg-[rgba(138,151,178,0.15)] text-[#8A97B2] text-xs font-medium px-2.5 py-0.5 rounded-full">
                            One-time
                          </span>
                        )}
                      </a>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/expenses/${exp.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {exp.is_recurring === 1 ? (exp.frequency ?? "—") : "—"}
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
            basePath="/expenses"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={expenses.length}
            noun="expenses"
          />
        )}
      </div>
    </div>
  );
}
