import { SessionOptions, getIronSession } from "iron-session";
import { cookies } from "next/headers";

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
