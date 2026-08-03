import { frappeRequest } from "./frappe";

export const PAGE_SIZES = [20, 50, 100, 200] as const;
export const DEFAULT_PAGE_SIZE = 50;

export type SearchParamsObj = { [key: string]: string | string[] | undefined };

// Frappe filters are `[fieldname, operator, value]` triples; values may be
// numbers or arrays (for "in"/"between"), so the row type stays loose.
export type ListFilters = unknown[][];

export type PageParams = { page: number; pageSize: number };

export type ListResult<T> = {
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
};

/** Read `?page=` / `?size=` off a list page's search params, with sane fallbacks. */
export function readPageParams(
  sp: SearchParamsObj,
  defaultPageSize: number = DEFAULT_PAGE_SIZE
): PageParams {
  const rawSize = typeof sp.size === "string" ? Number.parseInt(sp.size, 10) : NaN;
  const pageSize = (PAGE_SIZES as readonly number[]).includes(rawSize)
    ? rawSize
    : defaultPageSize;

  const rawPage = typeof sp.page === "string" ? Number.parseInt(sp.page, 10) : NaN;
  const page = Number.isFinite(rawPage) && rawPage > 0 ? rawPage : 1;

  return { page, pageSize };
}

/**
 * Rebuild the current URL with some params replaced. Passing `undefined` (or an
 * empty string) for a key drops it, which keeps default-valued params — page 1,
 * the "All" tab — out of the URL.
 */
export function buildHref(
  basePath: string,
  sp: SearchParamsObj,
  overrides: Record<string, string | number | undefined> = {}
): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(sp)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else params.set(key, value);
  }

  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined || value === "") params.delete(key);
    else params.set(key, String(value));
  }

  const qs = params.toString();
  return qs ? `${basePath}?${qs}` : basePath;
}

function listPath(
  doctype: string,
  fields: string[],
  filters: ListFilters | undefined,
  orderBy: string | undefined,
  start: number,
  pageSize: number
): string {
  const params = new URLSearchParams();
  params.set("fields", JSON.stringify(fields));
  if (filters && filters.length > 0) params.set("filters", JSON.stringify(filters));
  if (orderBy) params.set("order_by", orderBy);
  params.set("limit_start", String(start));
  params.set("limit_page_length", String(pageSize));
  return `api/resource/${encodeURIComponent(doctype)}?${params.toString()}`;
}

function countPath(doctype: string, filters: ListFilters | undefined): string {
  const params = new URLSearchParams();
  params.set("doctype", doctype);
  if (filters && filters.length > 0) params.set("filters", JSON.stringify(filters));
  return `api/method/frappe.client.get_count?${params.toString()}`;
}

/**
 * Fetch one page of a doctype list plus the total row count for the same
 * filters, so the table can say how many records exist — not just how many
 * happened to fit under the limit.
 */
export async function fetchListPage<T>({
  doctype,
  fields,
  filters,
  orderBy,
  sessionCookie,
  page,
  pageSize,
}: {
  doctype: string;
  fields: string[];
  filters?: ListFilters;
  orderBy?: string;
  sessionCookie: string;
  page: number;
  pageSize: number;
}): Promise<ListResult<T>> {
  const [listRes, countRes] = await Promise.all([
    frappeRequest<{ data: T[] }>(
      listPath(doctype, fields, filters, orderBy, (page - 1) * pageSize, pageSize),
      { sessionCookie }
    ),
    frappeRequest<{ message: number }>(countPath(doctype, filters), { sessionCookie }),
  ]);

  let rows = listRes.data?.data ?? [];
  const rawTotal = countRes.data?.message;
  const total =
    typeof rawTotal === "number" ? rawTotal : (page - 1) * pageSize + rows.length;

  // A stale link (or rows deleted since it was built) can point past the end of
  // the list, which would render an empty table on a non-empty result set.
  // Snap back to the last real page and report that page number to the caller.
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  if (page > lastPage && total > 0) {
    const retry = await frappeRequest<{ data: T[] }>(
      listPath(doctype, fields, filters, orderBy, (lastPage - 1) * pageSize, pageSize),
      { sessionCookie }
    );
    rows = retry.data?.data ?? [];
    return { rows, total, page: lastPage, pageSize };
  }

  return { rows, total, page, pageSize };
}

/** Total rows matching `filters`, for headline counts outside a paged table. */
export async function fetchCount(
  doctype: string,
  filters: ListFilters | undefined,
  sessionCookie: string
): Promise<number> {
  const { data } = await frappeRequest<{ message: number }>(
    countPath(doctype, filters),
    { sessionCookie }
  );
  return typeof data?.message === "number" ? data.message : 0;
}
