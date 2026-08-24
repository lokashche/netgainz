import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { buildHref, fetchListPage, readPageParams } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { Offer } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Running", value: "running" },
  { label: "Ended", value: "ended" },
];

function offerAmount(offer: Offer): string {
  return offer.discount_type === "Percentage"
    ? `${offer.discount_value}% off`
    : `₹${offer.discount_value.toLocaleString("en-IN")} off`;
}

function runsFor(offer: Offer): string {
  if (offer.disabled === 1) return "Ended";
  return offer.valid_upto ? `Until ${offer.valid_upto}` : "No end date";
}

function statusBadge(offer: Offer): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  const ended = offer.disabled === 1 || (offer.valid_upto ? offer.valid_upto < new Date().toISOString().slice(0, 10) : false);
  return ended
    ? `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`
    : `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
}

export default async function OffersPage({ searchParams }: { searchParams: SearchParams }) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const status = typeof sp.status === "string" ? sp.status : "";
  const q = typeof sp.q === "string" ? sp.q : "";

  const filters: string[][] = [];
  if (status === "running") filters.push(["disabled", "=", "0"]);
  if (status === "ended") filters.push(["disabled", "=", "1"]);
  if (q) filters.push(["offer_name", "like", `%${q}%`]);

  const requested = readPageParams(sp);
  const { rows: offers, total, page, pageSize } = await fetchListPage<Offer>({
    doctype: "Offer",
    fields: [
      "name",
      "offer_name",
      "coupon_code",
      "description",
      "discount_type",
      "discount_value",
      "discount_duration",
      "valid_from",
      "valid_upto",
      "max_total_uses",
      "disabled",
    ],
    filters,
    orderBy: "modified desc",
    sessionCookie: session.frappeCookies,
    ...requested,
  });

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Offers</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            Campaigns you can give a member when they join or renew.
          </p>
        </div>
        <a
          href="/offers/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Add Offer
        </a>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg overflow-x-auto ng-noscrollbar">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.value;
            const href = buildHref("/offers", sp, {
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

        <form method="GET" className="flex gap-2 flex-1 max-w-sm">
          {status && <input type="hidden" name="status" value={status} />}
          <input type="hidden" name="size" value={pageSize} />
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder="Search offers…"
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

      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {offers.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No offers yet</p>
            <p className="text-sm mt-1">
              A joining offer, a festival campaign, a founding-member rate — add one and it
              appears at the desk when you enrol a member.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  {["Offer", "Code", "Discount", "Applies To", "Runs", "Limit", "Status"].map((h) => (
                    <th
                      key={h}
                      className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {offers.map((offer) => {
                  const href = `/offers/${encodeURIComponent(offer.name)}`;
                  return (
                    <tr key={offer.name} className="hover:bg-[#1A2540] transition-colors">
                      <td className="px-6 py-4">
                        <a href={href} className="block text-sm text-[#E6EDF7]">
                          {offer.offer_name}
                        </a>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a href={href} className="block text-sm font-mono text-[#8FA3BF]">
                          {offer.coupon_code || "—"}
                        </a>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a href={href} className="block text-sm text-[#E6EDF7]">
                          {offerAmount(offer)}
                        </a>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a href={href} className="block text-sm text-[#8A97B2]">
                          {offer.discount_duration}
                        </a>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a href={href} className="block text-sm text-[#8A97B2]">
                          {runsFor(offer)}
                        </a>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a href={href} className="block text-sm text-[#8A97B2]">
                          {offer.max_total_uses ? `${offer.max_total_uses} members` : "No limit"}
                        </a>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a href={href} className="block">
                          <span className={statusBadge(offer)}>
                            {offer.disabled === 1 ? "Ended" : "Running"}
                          </span>
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && (
          <Pagination
            basePath="/offers"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={offers.length}
            noun="offers"
          />
        )}
      </div>
    </div>
  );
}
