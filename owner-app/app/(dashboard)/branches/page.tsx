"use client";

import { useEffect, useState, SyntheticEvent } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type { Branch } from "@/lib/types";
import { forgetBranches } from "@/lib/useBranches";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const smallButton =
  "text-xs font-medium rounded-lg px-3 py-2 border border-[#1E2D45] text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors disabled:opacity-50";

/**
 * Stage 10.1 — the gym's locations.
 *
 * A branch here is what every member, payment and expense is filed under. Opening
 * one silently creates its accounting cost center on the backend, so profit can be
 * read per branch later; the owner never sees that. The first branch is called
 * "Main" — renaming it to the real location is the expected first step.
 */
export default function BranchesPage() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [adding, setAdding] = useState(false);

  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameTo, setRenameTo] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  // Bumped after every change to fetch the list again.
  const [version, setVersion] = useState(0);
  const reload = () => {
    // Other screens' branch pickers must see the change.
    forgetBranches();
    setVersion((v) => v + 1);
  };

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/branches");
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          setError(extractFrappeError(body) ?? `Could not load branches (${res.status})`);
          return;
        }
        setBranches((body as { message?: Branch[] }).message ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [version]);

  async function handleAdd(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!newName.trim()) return;
    setAdding(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch("/api/branches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ branch_name: newName.trim(), description: newDescription.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setSuccess(`${newName.trim()} is open.`);
      setNewName("");
      setNewDescription("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setAdding(false);
    }
  }

  async function update(
    b: Branch,
    change: { new_name?: string; disabled?: boolean; make_default?: boolean },
    done: string
  ) {
    setBusy(b.name);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch(`/api/branches/${encodeURIComponent(b.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(change),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setSuccess(done);
      setRenaming(null);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setBusy(null);
    }
  }

  const activeCount = branches.filter((b) => !b.disabled).length;

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Branches</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Your gym&apos;s locations. Every member, payment and expense is filed under one, so
          you can see how each location is doing.
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
        <>
          {activeCount <= 1 && (
            <p className="mb-4 text-sm text-[#8A97B2]">
              You have one branch, so everything is recorded there. Rename it to your
              location&apos;s real name, and add a branch when you open a second location.
            </p>
          )}

          <ul className="space-y-3 mb-8">
            {branches.map((b) => (
              <li
                key={b.name}
                className={`bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4 sm:p-5 ${
                  b.disabled ? "opacity-60" : ""
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[#E6EDF7] font-semibold">{b.branch_name}</span>
                      {b.is_default === 1 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[rgba(34,211,140,0.15)] text-[#22D38C]">
                          Default
                        </span>
                      )}
                      {b.disabled === 1 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[rgba(138,151,178,0.15)] text-[#8A97B2]">
                          Switched off
                        </span>
                      )}
                    </div>
                    <p className="text-[#8A97B2] text-xs mt-1">
                      {b.members} {b.members === 1 ? "member" : "members"}
                      {b.description ? ` · ${b.description}` : ""}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={smallButton}
                      disabled={busy !== null}
                      onClick={() => {
                        setRenaming(b.name);
                        setRenameTo(b.branch_name);
                      }}
                    >
                      Rename
                    </button>
                    {b.is_default !== 1 && b.disabled !== 1 && (
                      <button
                        type="button"
                        className={smallButton}
                        disabled={busy !== null}
                        onClick={() =>
                          update(b, { make_default: true }, `${b.branch_name} is now the default branch.`)
                        }
                      >
                        Make default
                      </button>
                    )}
                    {b.is_default !== 1 && (
                      <button
                        type="button"
                        className={smallButton}
                        disabled={busy !== null}
                        onClick={() =>
                          update(
                            b,
                            { disabled: b.disabled !== 1 },
                            b.disabled === 1
                              ? `${b.branch_name} is switched back on.`
                              : `${b.branch_name} is switched off. Its records are kept.`
                          )
                        }
                      >
                        {b.disabled === 1 ? "Switch on" : "Switch off"}
                      </button>
                    )}
                  </div>
                </div>

                {renaming === b.name && (
                  <form
                    className="mt-4 flex flex-wrap items-end gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!renameTo.trim() || renameTo.trim() === b.branch_name) {
                        setRenaming(null);
                        return;
                      }
                      update(b, { new_name: renameTo.trim() }, `Renamed to ${renameTo.trim()}.`);
                    }}
                  >
                    <div className="flex-1 min-w-[12rem]">
                      <label className={labelClass}>New name</label>
                      <input
                        autoFocus
                        value={renameTo}
                        onChange={(e) => setRenameTo(e.target.value)}
                        className={inputClass}
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={busy !== null}
                      className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
                    >
                      {busy === b.name ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setRenaming(null)}
                      className="px-3 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7]"
                    >
                      Cancel
                    </button>
                  </form>
                )}
              </li>
            ))}
          </ul>

          <form
            onSubmit={handleAdd}
            className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-5 sm:p-6 space-y-4"
          >
            <h2 className="text-[#E6EDF7] font-semibold">Add a branch</h2>
            <div>
              <label className={labelClass}>Branch name</label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Anna Nagar"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Note (optional)</label>
              <input
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Address or anything your staff should know"
                className={inputClass}
              />
            </div>
            <button
              type="submit"
              disabled={adding || !newName.trim()}
              className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
            >
              {adding ? "Adding…" : "Add branch"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
