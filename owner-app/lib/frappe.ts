import type { AccountingMethod, GymSettings } from "./types";

const FRAPPE_URL = process.env.FRAPPE_URL!;

type FrappeResponse<T = unknown> = {
  data?: T;
  error?: string;
  status: number;
};

export function toIntlPhone(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 10) return `+91 ${digits}`;
  return raw.trim();
}

export function extractFrappeError(body: unknown): string | undefined {
  if (!body || typeof body !== "object") return undefined;
  const b = body as Record<string, unknown>;

  // Try top-level message first
  if (typeof b.message === "string" && b.message) return b.message;

  // Frappe validation errors live in _server_messages (a JSON-encoded array)
  if (typeof b._server_messages === "string") {
    try {
      const msgs = JSON.parse(b._server_messages) as Array<{ message?: string }>;
      const first = msgs[0]?.message;
      if (first) return first;
    } catch {
      // ignore
    }
  }

  // Fallback to the raw exception string
  if (typeof b.exception === "string") {
    const match = b.exception.match(/:\s*(.+)$/);
    if (match) return match[1];
  }

  return undefined;
}

export async function frappeRequest<T = unknown>(
  path: string,
  options: RequestInit & { sessionCookie?: string } = {}
): Promise<FrappeResponse<T>> {
  const { sessionCookie, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (sessionCookie) {
    headers["Cookie"] = sessionCookie;
  }

  const res = await fetch(`${FRAPPE_URL}/${path}`, {
    ...fetchOptions,
    headers,
  });

  const text = await res.text();
  let data: T | undefined;

  try {
    data = JSON.parse(text);
  } catch {
    // non-JSON response
  }

  return { data, status: res.status };
}

export async function getGymSettings(
  sessionCookie: string
): Promise<GymSettings> {
  const { data } = await frappeRequest<{ data: GymSettings }>(
    "api/resource/Gym Settings/Gym Settings",
    { sessionCookie }
  );
  const settings = data?.data;
  return {
    accounting_method: (settings?.accounting_method ?? "Cash") as AccountingMethod,
    member_id_prefix: settings?.member_id_prefix ?? "MEM-",
  };
}

export async function frappeLogin(
  usr: string,
  pwd: string
): Promise<{ ok: boolean; cookies: string; fullName: string }> {
  const res = await fetch(`${FRAPPE_URL}/api/method/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usr, pwd }),
  });

  if (!res.ok) {
    return { ok: false, cookies: "", fullName: "" };
  }

  // Only store name=value pairs — strip Set-Cookie attributes (Path, HttpOnly, etc.)
  const cookies = res.headers
    .getSetCookie()
    .map((c) => c.split(";")[0])
    .join("; ");
  const body = await res.json().catch(() => ({}));
  const fullName: string = body?.full_name ?? usr;

  return { ok: true, cookies, fullName };
}
