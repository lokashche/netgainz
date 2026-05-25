import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import LogoutButton from "./LogoutButton";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="font-bold text-gray-900">NetGainz</span>
            <a href="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
              Dashboard
            </a>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">{session.fullName}</span>
            <LogoutButton />
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
    </div>
  );
}
