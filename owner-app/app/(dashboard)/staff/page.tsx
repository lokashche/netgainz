"use client";

import { useEffect, useState, SyntheticEvent } from "react";
import { extractFrappeError } from "@/lib/frappe";
import { useBranches } from "@/lib/useBranches";
import type { StaffLogin } from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const smallButton =
  "text-xs font-medium rounded-lg px-3 py-2 border border-[#1E2D45] text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors disabled:opacity-50";

/** Tick-boxes for "which branches may this login see". None ticked = every branch. */
function BranchChecks({
  value,
  onChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const { branches } = useBranches();
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2">
      {branches.map((b) => (
        <label key={b.name} className="flex items-center gap-2 text-sm text-[#E6EDF7] min-h-[32px]">
          <input
            type="checkbox"
            checked={value.includes(b.name)}
            onChange={(e) =>
              onChange(e.target.checked ? [...value, b.name] : value.filter((v) => v !== b.name))
            }
            className="w-4 h-4 accent-[#22D38C]"
          />
          {b.branch_name}
        </label>
      ))}
    </div>
  );
}

/**
 * Stage 10.4 — the gym's logins.
 *
 * The owner adds a login, chooses owner or front-desk, and can limit front-desk
 * staff to some branches: a limited login sees only those branches' members,
 * money and lists, and is kept out of the whole-gym money screens. Nothing here
 * needs Frappe Desk.
 */
export default function StaffPage() {
  const { multi } = useBranches();
  const [staff, setStaff] = useState<StaffLogin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);

  const [editing, setEditing] = useState<string | null>(null);
  const [editBranches, setEditBranches] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"Gym Staff" | "Gym Owner">("Gym Staff");
  const [newBranches, setNewBranches] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/staff");
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          setError(extractFrappeError(body) ?? `Could not load logins (${res.status})`);
          return;
        }
        setStaff((body as { message?: StaffLogin[] }).message ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [version]);

  async function send(url: string, method: string, payload: unknown, done: string) {
    setError(null);
    setSuccess(null);
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(extractFrappeError(body) ?? `Error ${res.status}`);
      return false;
    }
    setSuccess(done);
    reload();
    return true;
  }

  async function handleAdd(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setAdding(true);
    try {
      const ok = await send(
        "/api/staff",
        "POST",
        {
          full_name: fullName.trim(),
          email: email.trim(),
          password,
          role,
          branches: role === "Gym Staff" ? newBranches : [],
        },
        `${fullName.trim()} can now sign in with ${email.trim()}.`
      );
      if (ok) {
        setFullName("");
        setEmail("");
        setPassword("");
        setRole("Gym Staff");
        setNewBranches([]);
      }
    } finally {
      setAdding(false);
    }
  }

  function branchSummary(s: StaffLogin): string {
    if (s.role === "Gym Owner") return "Every branch (owner)";
    return s.branches.length ? s.branches.join(", ") : "Every branch";
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Staff</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Who can sign in to NetGainz, and what they can see.
          {multi && " Limit front-desk staff to their own branch so they see only its members and money."}
        </p>
      </div>

      {error && (
        <div className="mb-4 bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 bg-[rgba(34,211,140,0.1)] border border-[#22D38C] text-[#22D38C] rounded-lg p-3 text-sm">
          {success}
        </div>
      )}

      {loading ? (
        <p className="text-[#8A97B2] text-sm">Loading…</p>
      ) : (
        <ul className="space-y-3 mb-8">
          {staff.map((s) => (
            <li
              key={s.user}
              className={`bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4 sm:p-5 ${s.enabled ? "" : "opacity-60"}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[#E6EDF7] font-semibold">{s.full_name}</span>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        s.role === "Gym Owner"
                          ? "bg-[rgba(34,211,140,0.15)] text-[#22D38C]"
                          : "bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]"
                      }`}
                    >
                      {s.role === "Gym Owner" ? "Owner" : "Front desk"}
                    </span>
                    {!s.enabled && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[rgba(138,151,178,0.15)] text-[#8A97B2]">
                        Switched off
                      </span>
                    )}
                    {s.is_me && <span className="text-xs text-[#8A97B2]">(you)</span>}
                  </div>
                  <p className="text-[#8A97B2] text-xs mt-1 break-all">{s.user}</p>
                  {multi && <p className="text-[#8A97B2] text-xs mt-1">Sees: {branchSummary(s)}</p>}
                </div>

                {!s.is_me && (
                  <div className="flex flex-wrap gap-2">
                    {multi && s.role === "Gym Staff" && s.enabled === 1 && (
                      <button
                        type="button"
                        className={smallButton}
                        disabled={busy !== null}
                        onClick={() => {
                          setEditing(s.user);
                          setEditBranches(s.branches);
                        }}
                      >
                        Branches
                      </button>
                    )}
                    <button
                      type="button"
                      className={smallButton}
                      disabled={busy !== null}
                      onClick={async () => {
                        setBusy(s.user);
                        await send(
                          `/api/staff/${encodeURIComponent(s.user)}`,
                          "PUT",
                          { enabled: s.enabled !== 1 },
                          s.enabled === 1
                            ? `${s.full_name} is switched off and signed out.`
                            : `${s.full_name} can sign in again.`
                        );
                        setBusy(null);
                      }}
                    >
                      {s.enabled === 1 ? "Switch off" : "Switch on"}
                    </button>
                  </div>
                )}
              </div>

              {editing === s.user && (
                <div className="mt-4 space-y-3">
                  <p className={labelClass}>Can see</p>
                  <BranchChecks value={editBranches} onChange={setEditBranches} />
                  <p className="text-[#8A97B2] text-xs">Tick none to let them see every branch.</p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={async () => {
                        setBusy(s.user);
                        const ok = await send(
                          `/api/staff/${encodeURIComponent(s.user)}`,
                          "PUT",
                          { branches: editBranches },
                          editBranches.length
                            ? `${s.full_name} now sees ${editBranches.join(", ")} only.`
                            : `${s.full_name} now sees every branch.`
                        );
                        setBusy(null);
                        if (ok) setEditing(null);
                      }}
                      className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
                    >
                      {busy === s.user ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(null)}
                      className="px-3 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7]"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <form
        onSubmit={handleAdd}
        className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-5 sm:p-6 space-y-4"
      >
        <h2 className="text-[#E6EDF7] font-semibold">Add a login</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Email (they sign in with this)</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>First password</label>
            <input
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              className={inputClass}
            />
            <p className="text-[#8A97B2] text-xs mt-1">Tell them privately. Use at least 8 characters.</p>
          </div>
          <div>
            <label className={labelClass}>Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "Gym Staff" | "Gym Owner")}
              className={inputClass}
            >
              <option value="Gym Staff">Front desk</option>
              <option value="Gym Owner">Owner</option>
            </select>
          </div>
        </div>
        {multi && role === "Gym Staff" && (
          <div className="space-y-2">
            <p className={labelClass}>Can see</p>
            <BranchChecks value={newBranches} onChange={setNewBranches} />
            <p className="text-[#8A97B2] text-xs">Tick none to let them see every branch.</p>
          </div>
        )}
        <button
          type="submit"
          disabled={adding || !fullName.trim() || !email.trim() || !password}
          className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
        >
          {adding ? "Adding…" : "Add login"}
        </button>
      </form>
    </div>
  );
}
