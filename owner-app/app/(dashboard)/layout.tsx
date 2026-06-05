import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import NavBar from "./NavBar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  return (
    <div className="min-h-screen bg-[#0B1220]">
      <NavBar fullName={session.fullName} />
      <main className="bg-[#0B1220] min-h-screen px-4 sm:px-6 lg:px-8 py-6 max-w-7xl mx-auto">
        {children}
      </main>
    </div>
  );
}
