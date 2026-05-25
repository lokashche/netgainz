import { NextRequest, NextResponse } from "next/server";
import { frappeLogin } from "@/lib/frappe";
import { getSession } from "@/lib/session";

export async function POST(req: NextRequest) {
  const { usr, pwd } = await req.json();

  if (!usr || !pwd) {
    return NextResponse.json({ error: "Missing credentials" }, { status: 400 });
  }

  const { ok, cookies, fullName } = await frappeLogin(usr, pwd);

  if (!ok) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  }

  const session = await getSession();
  session.user = usr;
  session.fullName = fullName;
  session.frappeCookies = cookies;
  await session.save();

  return NextResponse.json({ ok: true });
}
