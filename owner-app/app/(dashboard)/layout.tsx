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
    <div className="min-h-screen bg-[#0B1220]">
      <nav className="bg-[#111A2E] border-b border-[#1E2D45] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex flex-wrap items-center gap-x-6 gap-y-2 py-2 sm:py-0 sm:flex-nowrap justify-between">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
            <span className="font-bold tracking-wide text-[#E6EDF7]">
              NetGain<span className="text-[#22D38C]">Z</span>
            </span>
            <a
              href="/dashboard"
              className="text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
            >
              Dashboard
            </a>
            <a
              href="/members"
              className="text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
            >
              Members
            </a>
            <a
              href="/plans"
              className="text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
            >
              Plans
            </a>
            <a
              href="/subscriptions"
              className="text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
            >
              Subscriptions
            </a>
            <a
              href="/expenses"
              className="text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
            >
              Expenses
            </a>
            <a
              href="/expense-categories"
              className="text-sm font-medium px-3 py-2 rounded-lg text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors"
            >
              Categories
            </a>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#8A97B2] hidden sm:inline">
              {session.fullName}
            </span>
            <LogoutButton />
          </div>
        </div>
      </nav>
      <main className="bg-[#0B1220] min-h-screen px-4 sm:px-6 lg:px-8 py-6 max-w-7xl mx-auto">
        {children}
      </main>
    </div>
  );
}
