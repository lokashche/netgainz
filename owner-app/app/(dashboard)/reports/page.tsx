import Link from "next/link";

// Stage 11.4 — every report in one place, grouped by the question it answers.
// All of them follow the branch switcher at the top.
const GROUPS: { title: string; reports: { href: string; name: string; what: string }[] }[] = [
  {
    title: "Money",
    reports: [
      { href: "/financial-reports", name: "Financial Reports", what: "Profit & Loss, Balance Sheet, Cash Flow, day / cash / bank books, who owes the gym — and the accountant pack." },
      { href: "/branch-profit", name: "Profit by Branch", what: "What each branch earned, spent and kept this month." },
      { href: "/discounts", name: "Discounts", what: "What was given away, to whom, and what it cost." },
      { href: "/collections", name: "Money to Collect", what: "Every unpaid part, oldest first." },
    ],
  },
  {
    title: "Members",
    reports: [
      { href: "/members-report", name: "Members Report", what: "Who stayed, joined and left each month; money per member and lifetime value." },
      { href: "/churn-risk", name: "Churn Risk", what: "Active members who have stopped coming." },
      { href: "/renewals", name: "Renewals", what: "Memberships due to renew, and trials ending." },
      { href: "/enquiries", name: "Enquiries", what: "Follow-ups due, and which sources turn into members." },
    ],
  },
  {
    title: "Operations",
    reports: [
      { href: "/coach-report", name: "Coach Report", what: "Each coach's members, classes, attendance and commission." },
      { href: "/pack-report", name: "Pack Usage", what: "Sessions used, and packs that expired with sessions left." },
      { href: "/assessments", name: "Assessments", what: "Members overdue to be measured again." },
    ],
  },
  {
    title: "Profit First",
    reports: [
      { href: "/profit-first", name: "Profit First", what: "Where your money goes vs. where it should — right now." },
      { href: "/profit-first/reports", name: "Profit First Reports", what: "Month by month against targets, sweeps, reserve balances, tax set aside vs paid." },
    ],
  },
];

export default function ReportsPage() {
  return (
    <div className="max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Reports</h1>
        <p className="text-sm text-[#8A97B2] mt-1">Every report, grouped by the question it answers. All follow the branch picked at the top.</p>
      </div>
      {GROUPS.map((g) => (
        <section key={g.title} className="mb-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#22D38C] mb-3">{g.title}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {g.reports.map((r) => (
              <Link
                key={r.href}
                href={r.href}
                className="block bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4 hover:border-[#22D38C] transition-colors"
              >
                <p className="text-[#E6EDF7] font-semibold">{r.name} →</p>
                <p className="text-[#8A97B2] text-xs mt-1">{r.what}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
