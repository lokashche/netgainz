import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { DiscountGroup, DiscountsGiven } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const money = (n: number) =>
  `₹${(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

function monthRange(offset: number) {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const last = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return {
    start: iso(first),
    end: iso(last),
    label: first.toLocaleDateString("en-IN", { month: "long", year: "numeric" }),
  };
}

function Breakdown({ title, rows, empty }: { title: string; rows: DiscountGroup[]; empty: string }) {
  return (
    <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-[#1E2D45]">
        <h2 className="text-sm font-semibold text-[#E6EDF7]">{title}</h2>
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-[#8A97B2]">{empty}</p>
      ) : (
        <table className="w-full text-sm">
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-[#1A2540] last:border-0">
                <td className="px-4 py-3 text-[#E6EDF7]">{row.label}</td>
                <td className="px-4 py-3 text-right text-[#8A97B2] whitespace-nowrap">
                  {row.invoices} {row.invoices === 1 ? "invoice" : "invoices"}
                </td>
                <td className="px-4 py-3 text-right text-[#F87171] whitespace-nowrap">
                  −{money(row.given)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default async function DiscountsPage({ searchParams }: { searchParams: SearchParams }) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const offset = Number(typeof sp.month === "string" ? sp.month : 0) || 0;
  const period = monthRange(offset);

  const res = await frappeRequest<{ message: DiscountsGiven }>(
    `api/method/netgainz.net_gainz.accounting.discount_report.discounts_given?start=${period.start}&end=${period.end}`,
    { sessionCookie: session.frappeCookies }
  );
  const report = res.data?.message;

  if (!report) {
    return (
      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-8 text-center">
        <p className="text-lg font-medium text-[#E6EDF7]">Discounts are the owner&rsquo;s report</p>
        <p className="text-sm text-[#8A97B2] mt-1">
          Sign in as the gym owner to see what has been given away.
        </p>
      </div>
    );
  }

  const impact = report.profit_impact;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Discounts</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            What the gym gave away in {period.label} — and what it cost.
          </p>
        </div>
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg">
          {[
            { label: "This month", value: 0 },
            { label: "Last month", value: -1 },
            { label: "2 months ago", value: -2 },
          ].map((tab) => (
            <Link
              key={tab.value}
              href={tab.value ? `/discounts?month=${tab.value}` : "/discounts"}
              className={
                offset === tab.value
                  ? "px-3 py-1.5 text-sm font-semibold rounded-md bg-[#22D38C] text-[#0B1220]"
                  : "px-3 py-1.5 text-sm font-medium rounded-md text-[#8A97B2] hover:text-[#E6EDF7]"
              }
            >
              {tab.label}
            </Link>
          ))}
        </div>
      </div>

      {/* Headline */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-xs uppercase tracking-wider text-[#8A97B2]">Given away</p>
          <p className="text-3xl font-bold text-[#F87171] mt-1">{money(report.given)}</p>
          <p className="text-xs text-[#8A97B2] mt-1">
            {report.given_percent}% of {money(report.gross)} in fees · {report.members}{" "}
            {report.members === 1 ? "member" : "members"}
          </p>
        </div>
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-xs uppercase tracking-wider text-[#8A97B2]">Actually billed</p>
          <p className="text-3xl font-bold text-[#E6EDF7] mt-1">{money(report.net)}</p>
          <p className="text-xs text-[#8A97B2] mt-1">
            across {report.invoices} discounted {report.invoices === 1 ? "invoice" : "invoices"}
          </p>
        </div>
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
          <p className="text-xs uppercase tracking-wider text-[#8A97B2]">What it cost you</p>
          {impact?.applicable ? (
            <ul className="mt-2 space-y-1 text-sm text-[#8FA3BF]">
              {Object.entries(impact.buckets).map(([bucket, value]) => (
                <li key={bucket} className="flex justify-between gap-3">
                  <span>{bucket}</span>
                  <span className="text-[#E6EDF7]">−{money(value)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[#8A97B2] mt-2">
              The Profit First split appears once the gym has enough cash history for a tier.
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Breakdown
          title="By offer"
          rows={report.by_offer}
          empty="No discounts given this month."
        />
        <Breakdown title="By reason" rows={report.by_reason} empty="Nothing to show yet." />
        <Breakdown title="By who gave it" rows={report.by_staff} empty="Nothing to show yet." />
        <Breakdown title="By plan" rows={report.by_plan} empty="Nothing to show yet." />
      </div>

      {/* The individual giveaways */}
      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1E2D45]">
          <h2 className="text-sm font-semibold text-[#E6EDF7]">Biggest discounts</h2>
        </div>
        {report.biggest.length === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">
            No discounts were given in {period.label}.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Member</th>
                  <th className="text-left font-medium px-4 py-3">Plan</th>
                  <th className="text-left font-medium px-4 py-3">Reason</th>
                  <th className="text-left font-medium px-4 py-3">Given by</th>
                  <th className="text-right font-medium px-4 py-3">Fee</th>
                  <th className="text-right font-medium px-4 py-3">Off</th>
                </tr>
              </thead>
              <tbody>
                {report.biggest.map((row) => (
                  <tr
                    key={row.sales_invoice}
                    className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/subscriptions/${encodeURIComponent(row.membership)}`}
                        className="text-[#22D38C] hover:underline font-medium"
                      >
                        {row.member_name || row.membership}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">{row.membership_plan || "—"}</td>
                    <td className="px-4 py-3 text-[#8A97B2]">
                      {row.offer ? `Offer: ${row.offer}` : row.discount_reason || "—"}
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">{row.discount_granted_by || "—"}</td>
                    <td className="px-4 py-3 text-right text-[#8A97B2]">{money(row.gross)}</td>
                    <td className="px-4 py-3 text-right text-[#F87171]">−{money(row.given)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="text-xs text-[#8A97B2]">
        Counted from submitted invoices, so this is money actually given up — refunds and
        unbilled trials are not discounts and are not included. Profit First still allocates
        from the cash you collect; a discount simply means there is less of it.
      </p>
    </div>
  );
}
