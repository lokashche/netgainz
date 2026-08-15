import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { AssessmentMetric } from "@/lib/types";

// The metric library itself, for the owner to manage. The form-facing read is
// /api/assessments/metrics (whitelisted, member-narrowed, built-ins hidden);
// this one is the whole library including built-ins, so it can be curated
// without anyone opening Frappe Desk.

const FIELDS = JSON.stringify([
  "name",
  "unit",
  "direction",
  "metric_group",
  "applies_to",
  "description",
  "is_active",
  "is_builtin",
]);

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const path = `api/resource/Assessment%20Metric?fields=${encodeURIComponent(
    FIELDS
  )}&limit=200&order_by=${encodeURIComponent("metric_group asc, name asc")}`;

  const { data, status } = await frappeRequest<{ data: AssessmentMetric[] }>(path, {
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
  const { data, status } = await frappeRequest<{ data: AssessmentMetric }>(
    "api/resource/Assessment%20Metric",
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data ?? null, { status });
}
