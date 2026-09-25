import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getSession } from "@/lib/session";
import { BRANCH_COOKIE, currentBranch } from "@/lib/branchScope";

// Stage 10.3: which branch the owner-app is showing ("" = all branches).
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return NextResponse.json({ branch: await currentBranch() });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.json().catch(() => ({}));
  const branch = typeof body?.branch === "string" ? body.branch.trim() : "";
  const store = await cookies();
  if (branch) {
    store.set(BRANCH_COOKIE, encodeURIComponent(branch), {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      httpOnly: true,
    });
  } else {
    store.delete(BRANCH_COOKIE);
  }
  return NextResponse.json({ branch });
}
