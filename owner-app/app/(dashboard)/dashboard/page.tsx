import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import type { Member, Subscription, SubscriptionStatus, GymExpense } from "@/lib/types";

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

  // Current-month helpers
  const now = new Date();
  const currentMonthName = now.toLocaleString("en-US", { month: "long" }); // e.g. "May"
  const currentMonthPrefix = now.toISOString().slice(0, 7); // e.g. "2026-05"

  // ── Build query paths ────────────────────────────────────────────────────

  // 1. Active members
  const membersPath = `api/resource/Member?fields=${encodeURIComponent(
    JSON.stringify(["name"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["status", "=", "Active"]])
  )}&limit=500`;

  // 2. Income this month (subscriptions)
  const incomeSubsPath = `api/resource/Subscription?fields=${encodeURIComponent(
    JSON.stringify(["name", "fee_collected", "status"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["month", "=", currentMonthName]])
  )}&limit=500`;

  // 3. Expenses this month
  const expensesMonthPath = `api/resource/Gym%20Expense?fields=${encodeURIComponent(
    JSON.stringify(["name", "amount", "date"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["date", "like", `${currentMonthPrefix}%`]])
  )}&limit=500`;

  // 4. Overdue subscriptions
  const overdueSubsPath = `api/resource/Subscription?fields=${encodeURIComponent(
    JSON.stringify(["name", "member_name", "balance_due", "month", "membership_plan"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["status", "=", "Overdue"]])
  )}&order_by=${encodeURIComponent("due_date asc")}&limit=10`;

  // 5. Partial subscriptions
  const partialSubsPath = `api/resource/Subscription?fields=${encodeURIComponent(
    JSON.stringify(["name", "member_name", "balance_due", "month", "membership_plan"])
  )}&filters=${encodeURIComponent(
    JSON.stringify([["status", "=", "Partial"]])
  )}&order_by=${encodeURIComponent("due_date asc")}&limit=10`;

  // 6. Recent subscriptions (last 5)
  const recentSubsPath = `api/resource/Subscription?fields=${encodeURIComponent(
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
  const recentExpensesPath = `api/resource/Gym%20Expense?fields=${encodeURIComponent(
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
  ] = await Promise.all([
    frappeRequest<{ data: Pick<Member, "name">[] }>(membersPath, {
      sessionCookie: session.frappeCookies,
    }),
    frappeRequest<{ data: Pick<Subscription, "name" | "fee_collected" | "status">[] }>(
      incomeSubsPath,
      { sessionCookie: session.frappeCookies }
    ),
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
  ]);

  // ── Extract arrays ────────────────────────────────────────────────────────

  const members = membersRes.data?.data ?? [];
  const incomeSubsList = incomeSubsRes.data?.data ?? [];
  const expensesMonthList = expensesMonthRes.data?.data ?? [];
  const overdue = overdueSubsRes.data?.data ?? [];
  const partial = partialSubsRes.data?.data ?? [];
  const recentSubs = recentSubsRes.data?.data ?? [];
  const recentExpenses = recentExpensesRes.data?.data ?? [];

  // ── Derived values ────────────────────────────────────────────────────────

  const activeMembersCount: number = members.length;

  const totalIncome: number = incomeSubsList.reduce(
    (sum, s) => sum + (Number(s.fee_collected) || 0),
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
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Dashboard</h1>
        <p className="text-sm text-[#8A97B2] mt-1">Financial overview for {currentMonthName}</p>
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
          <p className="text-[#8A97B2] text-xs mt-1">{currentMonthName} subscriptions</p>
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
