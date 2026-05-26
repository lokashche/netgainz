import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { GymExpense } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const category = searchParams.get("category");
  const recurring = searchParams.get("recurring");

  const fields = JSON.stringify([
    "name",
    "date",
    "category",
    "amount",
    "vendor",
    "is_recurring",
    "frequency",
  ]);

  const filters: string[][] = [];
  if (category) filters.push(["category", "=", category]);
  if (recurring === "1") filters.push(["is_recurring", "=", "1"]);
  else if (recurring === "0") filters.push(["is_recurring", "=", "0"]);

  let path = `api/resource/Gym%20Expense?fields=${encodeURIComponent(fields)}&order_by=${encodeURIComponent("date desc")}&limit=100`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status } = await frappeRequest<{ data: GymExpense[] }>(path, {
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

  const { data, status } = await frappeRequest<{ data: GymExpense }>(
    "api/resource/Gym%20Expense",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
