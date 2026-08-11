import { SessionOptions, getIronSession } from "iron-session";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export type SessionData = {
  frappeCookies: string;
  fullName: string;
  user: string;
};

const sessionOptions: SessionOptions = {
  password: process.env.SESSION_SECRET!,
  cookieName: "ng_session",
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
  },
};

export async function getSession() {
  return getIronSession<SessionData>(await cookies(), sessionOptions);
}

/**
 * The app session and the Frappe session are two different things, and the app's
 * outlives the backend's. When that happens every call comes back 401/403 and the
 * app used to render *empty* — the nav still saying "Administrator" while a finance
 * screen quietly showed zero income. On this product that is worse than an error:
 * an owner can read "Rs.0.00" and believe it.
 *
 * Server components call this with the status of any Frappe response. A dead login
 * clears the stale app session and sends the user to sign in again; everything else
 * passes straight through.
 */
export async function assertFrappeSession(status: number): Promise<void> {
  if (status !== 401 && status !== 403) return;
  const session = await getSession();
  session.destroy();
  redirect("/login?reason=session-expired");
}
