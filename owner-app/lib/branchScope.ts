import { cookies } from "next/headers";

/**
 * Stage 10.3 — the branch picked in the switcher, for server code only (server
 * pages and BFF routes). An empty string means "All branches".
 *
 * The backend enforces the real limit (a branch manager can never widen their
 * view by editing this cookie); this only carries the owner's choice.
 */
export const BRANCH_COOKIE = "ng_branch";

export async function currentBranch(): Promise<string> {
  const raw = (await cookies()).get(BRANCH_COOKIE)?.value;
  return raw ? decodeURIComponent(raw) : "";
}

/** `&branch=…` for an `api/method/…?…` path, or "" for all branches. */
export function branchParam(branch: string, sep: "&" | "?" = "&"): string {
  return branch ? `${sep}branch=${encodeURIComponent(branch)}` : "";
}

/** A `["branch", "=", …]` filter for `api/resource/…` lists, or none. */
export function branchFilters(branch: string, field = "branch"): string[][] {
  return branch ? [[field, "=", branch]] : [];
}
