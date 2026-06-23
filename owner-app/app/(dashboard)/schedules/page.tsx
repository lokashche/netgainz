import { frappeRequest, getGymSettings } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import type { ClassSchedule } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const WEEKDAYS: [keyof ClassSchedule, string][] = [
  ["on_monday", "Mon"],
  ["on_tuesday", "Tue"],
  ["on_wednesday", "Wed"],
  ["on_thursday", "Thu"],
  ["on_friday", "Fri"],
  ["on_saturday", "Sat"],
  ["on_sunday", "Sun"],
];

function daysSummary(s: ClassSchedule): string {
  const on = WEEKDAYS.filter(([f]) => s[f] === 1).map(([, l]) => l);
  if (on.length === 7) return "Every day";
  return on.join(", ") || "—";
}

function fmtTime(t?: string): string {
  if (!t) return "—";
  const [h, m] = t.split(":");
  const hh = Number(h);
  const ap = hh >= 12 ? "PM" : "AM";
  const h12 = ((hh + 11) % 12) + 1;
  return `${h12}:${m ?? "00"} ${ap}`;
}

function activeBadge(active: 0 | 1): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  return active === 1
    ? `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`
    : `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
}

export default async function SchedulesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q : "";

  const settings = await getGymSettings(session.frappeCookies);
  const singular = settings.class_term_singular ?? "Class";

  const fields = JSON.stringify([
    "name",
    "title",
    "program",
    "coach",
    "start_time",
    "capacity",
    "on_monday",
    "on_tuesday",
    "on_wednesday",
    "on_thursday",
    "on_friday",
    "on_saturday",
    "on_sunday",
    "is_active",
  ]);
  const filters: string[][] = [];
  if (q) filters.push(["title", "like", `%${q}%`]);

  let path = `api/resource/Session%20Schedule?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("title asc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data } = await frappeRequest<{ data: ClassSchedule[] }>(path, {
    sessionCookie: session.frappeCookies,
  });
  const schedules: ClassSchedule[] = data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">{singular} Schedules</h1>
        <a
          href="/schedules/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          New Schedule
        </a>
      </div>
      <p className="text-sm text-[#8A97B2] mb-6">
        Define a recurring {singular.toLowerCase()} once — the upcoming sessions are created
        automatically.
      </p>

      <form method="GET" className="flex gap-2 max-w-sm mb-6">
        <input
          type="search"
          name="q"
          defaultValue={q}
          placeholder="Search by title…"
          className="flex-1 px-3 py-2 text-sm rounded-lg focus:outline-none focus:ring-2 bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C]"
        />
        <button
          type="submit"
          className="px-3 py-2 text-sm bg-[#1A2540] text-[#E6EDF7] border border-[#1E2D45] hover:bg-[#22D38C] hover:text-[#0B1220] rounded-lg transition-colors"
        >
          Search
        </button>
      </form>

      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {schedules.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No schedules yet</p>
            <p className="text-sm mt-1">
              Create one to auto-generate recurring {singular.toLowerCase()} sessions.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[#1E2D45]">
              <thead className="bg-[#1A2540]">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Title
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Coach
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Time
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Days
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Active
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {schedules.map((s) => (
                  <tr key={s.name} className="hover:bg-[#1A2540] transition-colors cursor-pointer">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/schedules/${s.name}`} className="block w-full h-full text-sm text-[#E6EDF7]">
                        {s.title}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/schedules/${s.name}`} className="block w-full h-full text-sm text-[#8A97B2]">
                        {s.coach ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/schedules/${s.name}`} className="block w-full h-full text-sm text-[#E6EDF7]">
                        {fmtTime(s.start_time)}
                      </a>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a href={`/schedules/${s.name}`} className="block w-full h-full text-sm text-[#8A97B2]">
                        {daysSummary(s)}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/schedules/${s.name}`} className="block w-full h-full">
                        <span className={activeBadge(s.is_active)}>
                          {s.is_active === 1 ? "Active" : "Inactive"}
                        </span>
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
