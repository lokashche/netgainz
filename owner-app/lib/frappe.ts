const FRAPPE_URL = process.env.FRAPPE_URL!;

type FrappeResponse<T = unknown> = {
  data?: T;
  error?: string;
  status: number;
};

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

  const cookies = res.headers.getSetCookie().join("; ");
  const body = await res.json().catch(() => ({}));
  const fullName: string = body?.full_name ?? usr;

  return { ok: true, cookies, fullName };
}
