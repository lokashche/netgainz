import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ExpenseCategory } from "@/lib/types";

export async function GET(_req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const fields = JSON.stringify(["name", "category_name", "description"]);
  const path = `api/resource/Expense%20Category?fields=${encodeURIComponent(fields)}&order_by=${encodeURIComponent("category_name asc")}`;

  const { data, status } = await frappeRequest<{ data: ExpenseCategory[] }>(path, {
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ data: ExpenseCategory }>(
    "api/resource/Expense%20Category",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
