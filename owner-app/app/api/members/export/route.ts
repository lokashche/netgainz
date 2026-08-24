import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

// The register as a spreadsheet. The columns are the ones the Load Records
// screen understands (member_code is the key there), so a corrected file can go
// straight back in — plus the descriptive fields worth checking in one place.
const COLUMNS = [
  "member_code",
  "full_name",
  "phone",
  "email",
  "date_of_birth",
  "blood_group",
  "occupation",
  "address",
  "emergency_contact",
  "date_of_joining",
  "coach",
  "category",
  "sport_goal",
  "academy",
  "membership_plan",
  "gym_program",
  "branch",
  "source_of_reference",
  "referred_by",
  "status",
  "inactive_reason",
] as const;

function csvCell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  // Quote anything a spreadsheet could misread; double internal quotes.
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const status = searchParams.get("status");
  const q = searchParams.get("q");

  const filters: string[][] = [];
  if (status) filters.push(["status", "=", status]);
  // Same rule as the Members screen: a query with a digit is an ID search.
  if (q) {
    filters.push(
      /\d/.test(q) ? ["name", "like", `%${q}%`] : ["full_name", "like", `%${q}%`]
    );
  }

  const params = new URLSearchParams();
  params.set("fields", JSON.stringify(COLUMNS));
  if (filters.length > 0) params.set("filters", JSON.stringify(filters));
  params.set("order_by", "name asc");
  // 0 = no page limit: the whole register, not the first page of it.
  params.set("limit_page_length", "0");

  const { data, status: httpStatus } = await frappeRequest<{
    data: Record<string, unknown>[];
  }>(`api/resource/Member?${params.toString()}`, {
    sessionCookie: session.frappeCookies,
  });

  if (httpStatus !== 200 || !data?.data) {
    return NextResponse.json(data ?? { error: "Export failed" }, { status: httpStatus });
  }

  const lines = [
    COLUMNS.join(","),
    ...data.data.map((row) => COLUMNS.map((c) => csvCell(row[c])).join(",")),
  ];
  // BOM so Excel opens it as UTF-8; CRLF because Excel expects it.
  const csv = "\uFEFF" + lines.join("\r\n") + "\r\n";

  const today = new Date().toISOString().slice(0, 10);
  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="members-${today}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
