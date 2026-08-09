import { frappeRequest, getGymSettings } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import type { Member, Subscription, SubscriptionStatus, GymExpense, RenewalsDue } from "@/lib/types";

// ── helpers ─────────────────────────────────────────────────────────────────

function fmt(value: number): string {
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatShortDate(dateStr?: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function statusBadge(status: SubscriptionStatus): string {
  const base =
    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
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

// ── page ────────────────────────────────────────────────────────────────────

export default async function DashboardPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const settings = await getGymSettings(session.frappeCookies);
  const isCashBasis = settings.accounting_method === "Cash";

  // Current-month helpers
  const now = new Date();
  const currentMonthName = now.toLocaleString("en-US", { month: "long" }); // e.g. "May"
  const year = now.getFullYear();
  const monthIdx = now.getMonth(); // 0-indexed
  const mm = String(monthIdx + 1).padStart(2, "0");
  const monthStart = `${year}-${mm}-01`;
  const lastDay = new Date(year, monthIdx + 1, 0).getDate();
  const monthEnd = `${year}-${mm}-${String(lastDay).padStart(2, "0")}`;

  // ── Build query paths ────────────────────────────────────────────────────

  // 1. Active members
  const membersPath = `api/resource/Member?fields=${encodeURIComponent(
    JSON.stringify(["name"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["status", "=", "Active"]])
  )}&limit=500`;

  // 2. Income this month (subscriptions)
  //    - Cash basis: subscriptions paid this month → sum fee_collected
  //    - Accrual basis: subscriptions FOR this month → sum tariff (earned, not necessarily received)
  const incomeFilters = isCashBasis
    ? [["paid_date", "between", [monthStart, monthEnd]]]
    : [["month", "=", currentMonthName]];
  const incomeFields = isCashBasis
    ? ["name", "fee_collected", "status"]
    : ["name", "tariff", "status"];
  const incomeSubsPath = `api/resource/Membership?fields=${encodeURIComponent(
    JSON.stringify(incomeFields)
  )}&filters=${encodeURIComponent(JSON.stringify(incomeFilters))}&limit=500`;

  // 3. Expenses this month
  const expensesMonthPath = `api/resource/Expense?fields=${encodeURIComponent(
    JSON.stringify(["name", "amount", "date"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["date", "between", [monthStart, monthEnd]]])
  )}&limit=500`;

  // 4. Overdue subscriptions
  const overdueSubsPath = `api/resource/Membership?fields=${encodeURIComponent(
    JSON.stringify(["name", "member_name", "balance_due", "month", "membership_plan"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["status", "=", "Overdue"]])
  )}&order_by=${encodeURIComponent("due_date asc")}&limit=10`;

  // 5. Partial subscriptions
  const partialSubsPath = `api/resource/Membership?fields=${encodeURIComponent(
    JSON.stringify(["name", "member_name", "balance_due", "month", "membership_plan"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["status", "=", "Partial"]])
  )}&order_by=${encodeURIComponent("due_date asc")}&limit=10`;

  // 6. Recent subscriptions (last 5)
  const recentSubsPath = `api/resource/Membership?fields=${encodeURIComponent(
    JSON.stringify([
      "name",
      "member_name",
      "membership_plan",
      "month",
      "fee_collected",
      "status",
    ])
  )}&order_by=${encodeURIComponent("creation desc")}&limit=5`;

  // 7. Recent expenses (last 5)
  const recentExpensesPath = `api/resource/Expense?fields=${encodeURIComponent(
    JSON.stringify(["name", "date", "category", "amount", "vendor"])
  )}&order_by=${encodeURIComponent("date desc")}&limit=5`;

  // ── Parallel fetch ────────────────────────────────────────────────────────

  const [
    membersRes,
    incomeSubsRes,
    expensesMonthRes,
    overdueSubsRes,
    partialSubsRes,
    recentSubsRes,
    recentExpensesRes,
    renewalsRes,
  ] = await Promise.all([
    frappeRequest<{ data: Pick<Member, "name">[] }>(membersPath, {
      sessionCookie: session.frappeCookies,
    }),
    frappeRequest<{
      data: Array<
        { name: string; status: SubscriptionStatus; fee_collected?: number; tariff?: number }
      >;
    }>(incomeSubsPath, { sessionCookie: session.frappeCookies }),
    frappeRequest<{ data: Pick<GymExpense, "name" | "amount" | "date">[] }>(
      expensesMonthPath,
      { sessionCookie: session.frappeCookies }
    ),
    frappeRequest<{
      data: Pick<
        Subscription,
        "name" | "member_name" | "balance_due" | "month" | "membership_plan"
      >[];
    }>(overdueSubsPath, { sessionCookie: session.frappeCookies }),
    frappeRequest<{
      data: Pick<
        Subscription,
        "name" | "member_name" | "balance_due" | "month" | "membership_plan"
      >[];
    }>(partialSubsPath, { sessionCookie: session.frappeCookies }),
    frappeRequest<{
      data: Pick<
        Subscription,
        "name" | "member_name" | "membership_plan" | "month" | "fee_collected" | "status"
      >[];
    }>(recentSubsPath, { sessionCookie: session.frappeCookies }),
    frappeRequest<{ data: Pick<GymExpense, "name" | "date" | "category" | "amount" | "vendor">[] }>(
      recentExpensesPath,
      { sessionCookie: session.frappeCookies }
    ),
    frappeRequest<{ message: RenewalsDue }>(
      `api/method/netgainz.net_gainz.operations.renewals.get_renewals_due`,
      { sessionCookie: session.frappeCookies }
    ),
  ]);

  // ── Extract arrays ────────────────────────────────────────────────────────

  const members = membersRes.data?.data ?? [];
  const incomeSubsList = incomeSubsRes.data?.data ?? [];
  const expensesMonthList = expensesMonthRes.data?.data ?? [];
  const overdue = overdueSubsRes.data?.data ?? [];
  const partial = partialSubsRes.data?.data ?? [];
  const recentSubs = recentSubsRes.data?.data ?? [];
  const recentExpenses = recentExpensesRes.data?.data ?? [];

  const renewals = renewalsRes.data?.message;
  const renewalsDueSoon = renewals?.due_soon ?? [];
  const renewalsOverdue = renewals?.overdue ?? [];
  const renewalsWithin = renewals?.within_days ?? 7;
  const showRenewals = renewalsDueSoon.length > 0 || renewalsOverdue.length > 0;

  // ── Derived values ────────────────────────────────────────────────────────

  const activeMembersCount: number = members.length;

  const totalIncome: number = incomeSubsList.reduce(
    (sum, s) =>
      sum + (Number(isCashBasis ? s.fee_collected : s.tariff) || 0),
    0
  );

  const totalExpenses: number = expensesMonthList.reduce(
    (sum, e) => sum + (Number(e.amount) || 0),
    0
  );

  const netPosition: number = totalIncome - totalExpenses;

  const totalOverdue: number = overdue.reduce(
    (sum, s) => sum + (Number(s.balance_due) || 0),
    0
  );

  const totalPartial: number = partial.reduce(
    (sum, s) => sum + (Number(s.balance_due) || 0),
    0
  );

  const showAlertRow: boolean = overdue.length > 0 || partial.length > 0;

  // ── Net position styling ──────────────────────────────────────────────────

  const netColor: string =
    netPosition > 0
      ? "text-[#22D38C]"
      : netPosition < 0
      ? "text-[#F87171]"
      : "text-[#8A97B2]";

  const netFormatted: string =
    netPosition > 0
      ? `+₹${fmt(netPosition)}`
      : netPosition < 0
      ? `-₹${fmt(Math.abs(netPosition))}`
      : `₹${fmt(0)}`;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Page header */}
      <div className="mb-6 flex items-end justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Dashboard</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            {isCashBasis ? "Cash basis" : "Accrual basis"} · {currentMonthName} {year}
          </p>
        </div>
        <a
          href="/settings"
          className="text-xs text-[#8A97B2] hover:text-[#22D38C] transition-colors"
        >
          Change basis →
        </a>
      </div>

      {/* ── KPI Row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Card 1 — Active Members */}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">
            Active Members
          </p>
          <p className="text-[#E6EDF7] text-3xl font-bold">{activeMembersCount}</p>
          <p className="text-[#8A97B2] text-xs mt-1">registered</p>
        </div>

        {/* Card 2 — Income This Month */}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">
            Income This Month
          </p>
          <p className="text-[#22D38C] text-3xl font-bold">₹{fmt(totalIncome)}</p>
          <p className="text-[#8A97B2] text-xs mt-1">
            {isCashBasis ? "received in " : "earned for "}
            {currentMonthName}
          </p>
        </div>

        {/* Card 3 — Expenses This Month */}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">
            Expenses This Month
          </p>
          <p className="text-[#F87171] text-3xl font-bold">₹{fmt(totalExpenses)}</p>
          <p className="text-[#8A97B2] text-xs mt-1">{currentMonthName} expenses</p>
        </div>

        {/* Card 4 — Net Cash Position */}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">
            Net Cash Position
          </p>
          <p className={`${netColor} text-3xl font-bold`}>{netFormatted}</p>
          <p className="text-[#8A97B2] text-xs mt-1">income − expenses</p>
        </div>
      </div>

      {/* ── Alert Row (only if there are overdue or partial records) ── */}
      {showAlertRow && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          {/* Overdue card */}
          {overdue.length > 0 && (
            <div className="bg-[rgba(248,113,113,0.05)] border border-[rgba(248,113,113,0.3)] rounded-xl p-5">
              <p className="text-[#F87171] font-semibold text-sm uppercase tracking-wider mb-3">
                ⚠ Overdue
              </p>
              <div className="flex items-baseline gap-2">
                <span className="text-[#E6EDF7] text-2xl font-bold">{overdue.length}</span>
                <span className="text-[#8A97B2] text-sm">subscriptions</span>
              </div>
              <p className="text-[#F87171] text-sm mt-1">₹{fmt(totalOverdue)} outstanding</p>

              {/* Mini list */}
              <ul className="mt-3 space-y-1.5">
                {overdue.slice(0, 5).map((sub) => (
                  <li
                    key={sub.name}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="text-[#E6EDF7] truncate mr-2">
                      {sub.member_name ?? sub.name}
                      {sub.month ? ` · ${sub.month}` : ""}
                    </span>
                    <span className="text-[#F87171] font-medium shrink-0">
                      ₹{fmt(Number(sub.balance_due) || 0)}
                    </span>
                  </li>
                ))}
              </ul>

              <a
                href="/subscriptions?status=Overdue"
                className="text-[#F87171] text-xs hover:underline mt-3 inline-block"
              >
                View all overdue →
              </a>
            </div>
          )}

          {/* Partial card */}
          {partial.length > 0 && (
            <div className="bg-[rgba(94,234,212,0.05)] border border-[rgba(94,234,212,0.3)] rounded-xl p-5">
              <p className="text-[#5EEAD4] font-semibold text-sm uppercase tracking-wider mb-3">
                ◑ Partial
              </p>
              <div className="flex items-baseline gap-2">
                <span className="text-[#E6EDF7] text-2xl font-bold">{partial.length}</span>
                <span className="text-[#8A97B2] text-sm">subscriptions</span>
              </div>
              <p className="text-[#5EEAD4] text-sm mt-1">₹{fmt(totalPartial)} balance due</p>

              {/* Mini list */}
              <ul className="mt-3 space-y-1.5">
                {partial.slice(0, 5).map((sub) => (
                  <li
                    key={sub.name}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="text-[#E6EDF7] truncate mr-2">
                      {sub.member_name ?? sub.name}
                      {sub.month ? ` · ${sub.month}` : ""}
                    </span>
                    <span className="text-[#5EEAD4] font-medium shrink-0">
                      ₹{fmt(Number(sub.balance_due) || 0)}
                    </span>
                  </li>
                ))}
              </ul>

              <a
                href="/subscriptions?status=Partial"
                className="text-[#5EEAD4] text-xs hover:underline mt-3 inline-block"
              >
                View all partial →
              </a>
            </div>
          )}
        </div>
      )}

      {/* ── Renewals Due ── */}
      {showRenewals && (
        <div className="bg-[rgba(94,234,212,0.05)] border border-[rgba(94,234,212,0.3)] rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[#5EEAD4] font-semibold text-sm uppercase tracking-wider">
              ⟳ Renewals Due
            </p>
            <a href="/renewals" className="text-[#5EEAD4] text-xs hover:underline">
              View all →
            </a>
          </div>
          <div className="flex items-baseline gap-6 mb-3">
            <div>
              <span className="text-[#E6EDF7] text-2xl font-bold">{renewalsDueSoon.length}</span>
              <span className="text-[#8A97B2] text-sm"> due in {renewalsWithin}d</span>
            </div>
            {renewalsOverdue.length > 0 && (
              <div>
                <span className="text-[#F87171] text-2xl font-bold">{renewalsOverdue.length}</span>
                <span className="text-[#8A97B2] text-sm"> overdue</span>
              </div>
            )}
          </div>
          <ul className="space-y-1.5">
            {[...renewalsOverdue, ...renewalsDueSoon].slice(0, 5).map((r) => (
              <li key={r.subscription} className="flex items-center justify-between text-xs">
                <a
                  href={`/members/${r.member}`}
                  className="text-[#E6EDF7] truncate mr-2 hover:text-[#5EEAD4]"
                >
                  {r.member_name ?? r.member}
                  {r.membership_plan ? ` · ${r.membership_plan}` : ""}
                </a>
                <span className={r.days_until < 0 ? "text-[#F87171] shrink-0" : "text-[#5EEAD4] shrink-0"}>
                  {r.days_until < 0 ? `${Math.abs(r.days_until)}d overdue` : `in ${r.days_until}d`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Two-column row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Subscriptions */}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#1E2D45] flex items-center justify-between">
            <span className="text-[#E6EDF7] font-semibold text-sm">
              Recent Subscriptions
            </span>
            <a
              href="/subscriptions"
              className="text-[#22D38C] text-xs hover:underline"
            >
              View all →
            </a>
          </div>

          {recentSubs.length === 0 ? (
            <div className="px-5 py-8 text-center text-[#8A97B2] text-sm">
              No subscriptions yet
            </div>
          ) : (
            <ul>
              {recentSubs.map((sub) => (
                <li
                  key={sub.name}
                  className="px-5 py-3 border-b border-[#1E2D45] hover:bg-[#1A2540] transition-colors flex items-center justify-between"
                >
                  <a href={`/subscriptions/${sub.name}`} className="min-w-0 flex-1 mr-3">
                    <p className="text-[#E6EDF7] text-sm truncate">
                      {sub.member_name ?? sub.name}
                    </p>
                    <p className="text-[#8A97B2] text-xs truncate">
                      {[sub.month, sub.membership_plan].filter(Boolean).join(" · ") || "—"}
                    </p>
                  </a>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[#E6EDF7] text-sm font-medium">
                      ₹{fmt(Number(sub.fee_collected) || 0)}
                    </span>
                    <span className={statusBadge(sub.status)}>{sub.status}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Recent Expenses */}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#1E2D45] flex items-center justify-between">
            <span className="text-[#E6EDF7] font-semibold text-sm">Recent Expenses</span>
            <a href="/expenses" className="text-[#22D38C] text-xs hover:underline">
              View all →
            </a>
          </div>

          {recentExpenses.length === 0 ? (
            <div className="px-5 py-8 text-center text-[#8A97B2] text-sm">
              No expenses yet
            </div>
          ) : (
            <ul>
              {recentExpenses.map((exp) => (
                <li
                  key={exp.name}
                  className="px-5 py-3 border-b border-[#1E2D45] hover:bg-[#1A2540] transition-colors flex items-center justify-between"
                >
                  <a href={`/expenses/${exp.name}`} className="min-w-0 flex-1 mr-3">
                    <p className="text-[#E6EDF7] text-sm truncate">
                      {exp.vendor ?? "—"}
                    </p>
                    <p className="text-[#8A97B2] text-xs truncate">
                      {exp.category ?? "—"}
                    </p>
                  </a>
                  <div className="flex items-center gap-2 shrink-0 text-right">
                    <span className="text-[#F87171] text-sm font-medium">
                      ₹{fmt(Number(exp.amount) || 0)}
                    </span>
                    <span className="text-[#8A97B2] text-xs">
                      {formatShortDate(exp.date)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
