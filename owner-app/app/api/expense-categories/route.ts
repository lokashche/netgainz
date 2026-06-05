import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ExpenseCategory } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const q = searchParams.get("q");

  const fields = JSON.stringify(["name", "category_name", "description"]);

  const filters: string[][] = [];
  if (q) filters.push(["category_name", "like", `%${q}%`]);

  let path = `api/resource/Expense%20Category?fields=${encodeURIComponent(fields)}&limit=50&order_by=${encodeURIComponent("category_name asc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

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
