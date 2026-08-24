import Link from "next/link";
import { PAGE_SIZES, buildHref, type SearchParamsObj } from "@/lib/pagination";

const NAV = "inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium rounded-md border border-[#1E2D45] bg-[#1A2540] text-[#E6EDF7] hover:bg-[#22D38C] hover:text-[#0B1220] transition-colors";
const NAV_OFF = "inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium rounded-md border border-[#1E2D45] bg-[#141E33] text-[#4C5A73] cursor-not-allowed";

export default function Pagination({
  basePath,
  searchParams,
  page,
  pageSize,
  total,
  shown,
  noun = "records",
}: {
  basePath: string;
  searchParams: SearchParamsObj;
  page: number;
  pageSize: number;
  /** Total rows matching the current filters, across all pages. */
  total: number;
  /** Rows rendered on this page. */
  shown: number;
  noun?: string;
}) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = (page - 1) * pageSize + shown;

  // Page 1 is the default, so leave it out of the URL rather than write ?page=1.
  const pageHref = (n: number) =>
    buildHref(basePath, searchParams, { page: n === 1 ? undefined : n });

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 border-t border-[#1E2D45] bg-[#0F1728]">
      <p className="text-xs text-[#8A97B2]">
        Showing{" "}
        <span className="text-[#E6EDF7] font-medium">
          {from}–{to}
        </span>{" "}
        of <span className="text-[#E6EDF7] font-medium">{total}</span> {noun}
      </p>

      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[#8A97B2]">Rows</span>
          <div className="flex gap-0.5 bg-[#1A2540] p-0.5 rounded-md">
            {PAGE_SIZES.map((size) => (
              <Link
                key={size}
                href={buildHref(basePath, searchParams, { size, page: undefined })}
                className={
                  size === pageSize
                    ? "inline-flex items-center justify-center min-w-[2rem] px-2 py-1 text-xs font-semibold rounded bg-[#22D38C] text-[#0B1220]"
                    : "inline-flex items-center justify-center min-w-[2rem] px-2 py-1 text-xs font-medium rounded text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
                }
              >
                {size}
              </Link>
            ))}
          </div>
        </div>

        {lastPage > 1 && (
          <div className="flex items-center gap-1.5">
            {page > 1 ? (
              <Link href={pageHref(page - 1)} className={NAV} aria-label="Previous page">
                ‹ Prev
              </Link>
            ) : (
              <span className={NAV_OFF} aria-disabled="true">
                ‹ Prev
              </span>
            )}

            <span className="text-xs text-[#8A97B2] px-1 whitespace-nowrap">
              Page <span className="text-[#E6EDF7] font-medium">{page}</span> of{" "}
              <span className="text-[#E6EDF7] font-medium">{lastPage}</span>
            </span>

            {page < lastPage ? (
              <Link href={pageHref(page + 1)} className={NAV} aria-label="Next page">
                Next ›
              </Link>
            ) : (
              <span className={NAV_OFF} aria-disabled="true">
                Next ›
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
