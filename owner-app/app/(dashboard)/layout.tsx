import { getSession } from "@/lib/session";
import { getGymSettings } from "@/lib/frappe";
import { redirect } from "next/navigation";
import NavBar from "./NavBar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const settings = await getGymSettings(session.frappeCookies);

  return (
    <div className="min-h-screen bg-[#0B1220]">
      <NavBar
        fullName={session.fullName}
        classTermSingular={settings.class_term_singular ?? "Class"}
        classTermPlural={settings.class_term_plural ?? "Classes"}
      />
      <main className="bg-[#0B1220] min-h-screen px-4 sm:px-6 lg:px-8 pt-6 pb-[calc(5rem+env(safe-area-inset-bottom))] md:pb-6 max-w-7xl mx-auto">
        {children}
      </main>
    </div>
  );
}
