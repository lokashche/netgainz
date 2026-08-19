import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { fetchListPage, readPageParams, type SearchParamsObj } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { ExpenseCategory } from "@/lib/types";

type SearchParams = Promise<SearchParamsObj>;

export default async function ExpenseCategoriesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const requested = readPageParams(sp);
  const {
    rows: categories,
    total,
    page,
    pageSize,
  } = await fetchListPage<ExpenseCategory>({
    doctype: "Expense Category",
    fields: ["name", "category_name", "description"],
    orderBy: "category_name asc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Expense Categories</h1>
        <a
          href="/expense-categories/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Category
        </a>
      </div>

      {/* Table */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {categories.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No expense categories yet</p>
            <p className="text-sm mt-1">Add your first category to start tracking expenses.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Category Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Description
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {categories.map((cat) => (
                  <tr
                    key={cat.name}
                    className="border-b border-[#1E2D45] hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/expense-categories/${encodeURIComponent(cat.name)}`}
                        className="block w-full h-full text-sm font-medium text-[#22D38C] hover:text-[#5EEAD4] transition-colors"
                      >
                        {cat.category_name}
                      </a>
                    </td>
                    <td className="px-6 py-4">
                      <a
                        href={`/expense-categories/${encodeURIComponent(cat.name)}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {cat.description ?? "—"}
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
            basePath="/expense-categories"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={categories.length}
            noun="categories"
          />
        )}
      </div>
    </div>
  );
}
