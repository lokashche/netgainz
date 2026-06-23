import { frappeRequest, getGymSettings } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import type { ClassSession, ClassSessionStatus } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const STATUS_TABS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Scheduled", value: "Scheduled" },
  { label: "Completed", value: "Completed" },
  { label: "Cancelled", value: "Cancelled" },
];

function formatStartTime(v: string | undefined): string {
  if (!v) return "—";
  return new Date(v).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function statusBadge(status: ClassSessionStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Scheduled":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Completed":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Cancelled":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

export default async function ClassesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const status = typeof sp.status === "string" ? sp.status : "";
  const q = typeof sp.q === "string" ? sp.q : "";

  const settings = await getGymSettings(session.frappeCookies);
  const singular = settings.class_term_singular ?? "Class";
  const plural = settings.class_term_plural ?? "Classes";

  const fields = JSON.stringify([
    "name",
    "title",
    "program",
    "coach",
    "start_time",
    "duration_mins",
    "capacity",
    "status",
  ]);
  const filters: string[][] = [];
  if (status) filters.push(["status", "=", status]);
  if (q) filters.push(["title", "like", `%${q}%`]);

  let path = `api/resource/Session?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("start_time desc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data } = await frappeRequest<{ data: ClassSession[] }>(path, {
    sessionCookie: session.frappeCookies,
  });

  const sessions: ClassSession[] = data?.data ?? [];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">{plural}</h1>
        <a
          href="/classes/new"
          className="inline-flex items-center px-4 py-2 bg-[#22D38C] text-[#0B1220] text-sm font-semibold rounded-lg hover:bg-[#5EEAD4] transition-colors"
        >
          Schedule {singular}
        </a>
      </div>

      {/* Filters row */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        {/* Status tabs */}
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.value;
            const href =
              tab.value
                ? `/classes?status=${tab.value}${q ? `&q=${encodeURIComponent(q)}` : ""}`
                : `/classes${q ? `?q=${encodeURIComponent(q)}` : ""}`;
            return (
              <a
                key={tab.value}
                href={href}
                className={
                  isActive
                    ? "px-3 py-1.5 text-sm font-semibold rounded-md bg-[#22D38C] text-[#0B1220]"
                    : "px-3 py-1.5 text-sm font-medium rounded-md text-[#8A97B2] hover:text-[#E6EDF7]"
                }
              >
                {tab.label}
              </a>
            );
          })}
        </div>

        {/* Search */}
        <form method="GET" className="flex gap-2 flex-1 max-w-sm">
          {status && <input type="hidden" name="status" value={status} />}
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
      </div>

      {/* Table */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        {sessions.length === 0 ? (
          <div className="text-center py-16 text-[#8A97B2]">
            <p className="text-lg font-medium">No classes found</p>
            <p className="text-sm mt-1">Try adjusting your search or filters.</p>
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
                    Start Time
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Coach
                  </th>
                  <th className="hidden sm:table-cell px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Program
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Capacity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-[#8A97B2] uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E2D45]">
                {sessions.map((s) => (
                  <tr
                    key={s.name}
                    className="hover:bg-[#1A2540] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/classes/${s.name}`}
                        className="block w-full h-full text-sm text-[#E6EDF7]"
                      >
                        {s.title}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/classes/${s.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {formatStartTime(s.start_time)}
                      </a>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/classes/${s.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {s.coach ?? "—"}
                      </a>
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/classes/${s.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {s.program ?? "—"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/classes/${s.name}`}
                        className="block w-full h-full text-sm text-[#8A97B2]"
                      >
                        {s.capacity ? s.capacity : "∞"}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a href={`/classes/${s.name}`} className="block w-full h-full">
                        <span className={statusBadge(s.status)}>{s.status}</span>
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
