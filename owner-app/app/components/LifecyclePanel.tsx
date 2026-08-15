"use client";

// OP-3 (ADR-0008): freeze / change plan / cancel / transfer, from the desk.
// Every rule lives server-side — the date-shift, the credit arithmetic, the
// tenant's refund policy, the owner-only gate on cash out. This panel only
// collects inputs and shows what the backend says happened.

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type {
  CancelResult,
  ChangePlanResult,
  FreezeResult,
  FreezeRow,
  Member,
  MembershipPlan,
  SubscriptionStatus,
  TransferResult,
} from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const actionBtn =
  "text-xs border border-[#1E2D45] text-[#8A97B2] rounded-lg py-1.5 px-3 hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors";

async function fetchPlans(q: string): Promise<LinkFieldOption[]> {
  const params = new URLSearchParams({ active_only: "1" });
  if (q) params.set("q", q);
  const res = await fetch(`/api/plans?${params.toString()}`);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: MembershipPlan[] };
  return (body.data ?? []).map((p) => ({
    id: p.name,
    label: p.plan_name,
    sub: p.amount !== undefined ? `₹${p.amount}` : undefined,
  }));
}

async function fetchMembers(q: string): Promise<LinkFieldOption[]> {
  const url = q ? `/api/members?q=${encodeURIComponent(q)}` : "/api/members";
  const res = await fetch(url);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Member[] };
  return (body.data ?? []).map((m) => ({
    id: m.name,
    label: m.full_name,
    sub: m.phone || m.email || undefined,
  }));
}

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtMoney(v: number): string {
  return v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type Mode = null | "freeze" | "change-plan" | "cancel" | "transfer";

export default function LifecyclePanel({
  membershipId,
  status,
  currentPlan,
  onChanged,
}: {
  membershipId: string;
  status: SubscriptionStatus;
  currentPlan?: string;
  onChanged: () => Promise<void> | void;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [freezes, setFreezes] = useState<FreezeRow[]>([]);

  const [freezeFrom, setFreezeFrom] = useState("");
  const [freezeTo, setFreezeTo] = useState("");
  const [freezeReason, setFreezeReason] = useState("");

  const [newPlan, setNewPlan] = useState("");
  const [newPlanLabel, setNewPlanLabel] = useState("");
  const [newPrice, setNewPrice] = useState("");

  const [cancelReason, setCancelReason] = useState("");

  const [toMember, setToMember] = useState("");
  const [toMemberLabel, setToMemberLabel] = useState("");

  const loadFreezes = useCallback(async () => {
    const res = await fetch(
      `/api/subscriptions/${encodeURIComponent(membershipId)}/lifecycle`
    );
    if (!res.ok) return;
    const body = (await res.json()) as { data?: FreezeRow[] };
    setFreezes(body.data ?? []);
  }, [membershipId]);

  useEffect(() => {
    (async () => {
      await loadFreezes();
    })();
  }, [loadFreezes]);

  async function post(payload: Record<string, unknown>): Promise<unknown | null> {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(
        `/api/subscriptions/${encodeURIComponent(membershipId)}/lifecycle`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return null;
      }
      return body;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function doFreeze() {
    const result = (await post({
      action: "freeze",
      from_date: freezeFrom,
      to_date: freezeTo,
      reason: freezeReason || null,
    })) as FreezeResult | null;
    if (!result) return;
    setNotice(
      `Frozen for ${result.days} day(s)` +
        (result.next_bill_moved_to
          ? ` — next bill moves to ${fmtDate(result.next_bill_moved_to)}.`
          : ".")
    );
    setMode(null);
    setFreezeFrom("");
    setFreezeTo("");
    setFreezeReason("");
    await loadFreezes();
    await onChanged();
  }

  async function doUnfreeze(freeze: FreezeRow) {
    const result = (await post({ action: "unfreeze", freeze: freeze.name })) as {
      days_returned: number;
    } | null;
    if (!result) return;
    setNotice(
      result.days_returned > 0
        ? `Welcome back — the next bill moves ${result.days_returned} day(s) earlier.`
        : "Freeze closed."
    );
    await loadFreezes();
    await onChanged();
  }

  async function doChangePlan() {
    const payload: Record<string, unknown> = { action: "change-plan", new_plan: newPlan };
    if (newPrice !== "" && Number.isFinite(Number(newPrice))) {
      payload.new_price = Number(newPrice);
    }
    const result = (await post(payload)) as ChangePlanResult | null;
    if (!result) return;
    setNotice(
      `Moved to ${result.new_plan}.` +
        (result.credit > 0
          ? ` ₹${fmtMoney(result.credit)} for ${result.unused_days} unused day(s) came off the new invoice.`
          : "")
    );
    setMode(null);
    setNewPlan("");
    setNewPlanLabel("");
    setNewPrice("");
    await onChanged();
  }

  async function doCancel() {
    if (!confirm("Cancel this membership? Billing stops today; this cannot be undone.")) return;
    const result = (await post({
      action: "cancel",
      reason: cancelReason || null,
    })) as CancelResult | null;
    if (!result) return;
    setNotice(
      result.refund_amount > 0
        ? `Cancelled. ₹${fmtMoney(result.refund_amount)} refunded per the "${result.refund_policy}" policy.`
        : `Cancelled. No refund (policy: ${result.refund_policy}).`
    );
    setMode(null);
    await onChanged();
  }

  async function doTransfer() {
    const result = (await post({
      action: "transfer",
      to_member: toMember,
    })) as TransferResult | null;
    if (!result) return;
    router.push(`/subscriptions/${encodeURIComponent(result.new_membership)}`);
  }

  const today = new Date().toISOString().slice(0, 10);
  const activeFreeze = freezes.find((f) => f.from_date <= today && today <= f.to_date);
  const cancelled = status === "Cancelled";

  return (
    <div className="mt-6 bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8">
      <h2 className="text-lg font-bold text-[#E6EDF7] mb-1">Lifecycle</h2>
      <p className="text-xs text-[#8A97B2] mb-4">
        Freeze for a holiday or injury, move to another plan (unused days come back as
        credit), transfer to a family member, or cancel — refunds follow your policy in
        Settings.
      </p>

      {error && (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171] mb-4">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C] mb-4">
          {notice}
        </div>
      )}

      {cancelled ? (
        <p className="text-sm text-[#8A97B2]">
          This membership is cancelled — billing has stopped and nothing renews.
        </p>
      ) : (
        <>
          {activeFreeze && (
            <div className="rounded-lg bg-[rgba(94,234,212,0.08)] border border-[rgba(94,234,212,0.3)] px-4 py-3 text-sm text-[#5EEAD4] mb-4 flex items-center justify-between flex-wrap gap-2">
              <span>
                Frozen {fmtDate(activeFreeze.from_date)} → {fmtDate(activeFreeze.to_date)}
                {activeFreeze.reason ? ` · ${activeFreeze.reason}` : ""}
              </span>
              <button
                type="button"
                onClick={() => doUnfreeze(activeFreeze)}
                disabled={busy}
                className="text-xs border border-[#5EEAD4] text-[#5EEAD4] rounded-lg py-1.5 px-3 hover:bg-[rgba(94,234,212,0.1)] disabled:opacity-50 transition-colors"
              >
                Back early — unfreeze
              </button>
            </div>
          )}

          <div className="flex items-center gap-2 flex-wrap">
            <button type="button" className={actionBtn} onClick={() => setMode(mode === "freeze" ? null : "freeze")} disabled={busy || !!activeFreeze}>
              Freeze
            </button>
            <button type="button" className={actionBtn} onClick={() => setMode(mode === "change-plan" ? null : "change-plan")} disabled={busy}>
              Change plan
            </button>
            <button type="button" className={actionBtn} onClick={() => setMode(mode === "transfer" ? null : "transfer")} disabled={busy}>
              Transfer
            </button>
            <button
              type="button"
              onClick={() => setMode(mode === "cancel" ? null : "cancel")}
              disabled={busy}
              className="text-xs border border-[#F87171] text-[#F87171] rounded-lg py-1.5 px-3 hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors"
            >
              Cancel membership
            </button>
          </div>

          {mode === "freeze" && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Frozen From</label>
                  <input type="date" value={freezeFrom} onChange={(e) => setFreezeFrom(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Frozen To</label>
                  <input type="date" value={freezeTo} onChange={(e) => setFreezeTo(e.target.value)} className={inputClass} />
                </div>
              </div>
              <div>
                <label className={labelClass}>Reason</label>
                <input type="text" value={freezeReason} onChange={(e) => setFreezeReason(e.target.value)} placeholder="Vacation, injury…" className={inputClass} />
              </div>
              <button
                type="button"
                onClick={doFreeze}
                disabled={busy || !freezeFrom || !freezeTo}
                className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
              >
                {busy ? "Freezing…" : "Freeze membership"}
              </button>
              <p className="text-xs text-[#8A97B2]">
                The next bill moves out by the frozen days. Nothing is cancelled.
              </p>
            </div>
          )}

          {mode === "change-plan" && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>New Plan</label>
                  <LinkFieldPicker
                    value={newPlan}
                    displayLabel={newPlanLabel}
                    onChange={(pid, label) => {
                      setNewPlan(pid);
                      setNewPlanLabel(label);
                    }}
                    fetchOptions={fetchPlans}
                    placeholder="Search plans…"
                    emptyHint="No plans found"
                    inputClassName={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass}>Price (optional)</label>
                  <input
                    type="number"
                    min="0"
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    placeholder="Blank = plan price"
                    className={inputClass}
                  />
                </div>
              </div>
              <button
                type="button"
                onClick={doChangePlan}
                disabled={busy || !newPlan || newPlan === currentPlan}
                className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
              >
                {busy ? "Changing…" : "Change plan"}
              </button>
              <p className="text-xs text-[#8A97B2]">
                A fresh cycle of the new plan starts today; the unused, already-paid days
                come off the new invoice automatically.
              </p>
            </div>
          )}

          {mode === "transfer" && (
            <div className="mt-4 space-y-3">
              <div>
                <label className={labelClass}>Transfer To</label>
                <LinkFieldPicker
                  value={toMember}
                  displayLabel={toMemberLabel}
                  onChange={(mid, label) => {
                    setToMember(mid);
                    setToMemberLabel(label);
                  }}
                  fetchOptions={fetchMembers}
                  placeholder="Search members…"
                  emptyHint="No members found"
                  inputClassName={inputClass}
                />
              </div>
              <button
                type="button"
                onClick={doTransfer}
                disabled={busy || !toMember}
                className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
              >
                {busy ? "Transferring…" : "Transfer membership"}
              </button>
              <p className="text-xs text-[#8A97B2]">
                This membership is cancelled and a new one starts for the family member —
                the remaining paid value carries across as credit.
              </p>
            </div>
          )}

          {mode === "cancel" && (
            <div className="mt-4 space-y-3">
              <div>
                <label className={labelClass}>Reason</label>
                <input
                  type="text"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="Moving away, injury, price…"
                  className={inputClass}
                />
              </div>
              <button
                type="button"
                onClick={doCancel}
                disabled={busy}
                className="border border-[#F87171] text-[#F87171] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors"
              >
                {busy ? "Cancelling…" : "Cancel membership"}
              </button>
              <p className="text-xs text-[#8A97B2]">
                Billing stops today. Whether unused days are refunded follows the policy in
                Settings; a cash refund needs the owner.
              </p>
            </div>
          )}

          {freezes.length > 0 && (
            <div className="mt-5 pt-4 border-t border-[#1E2D45]">
              <h3 className="text-sm font-semibold text-[#E6EDF7] mb-2">Freeze history</h3>
              <ul className="space-y-1">
                {freezes.map((f) => (
                  <li key={f.name} className="text-xs text-[#8A97B2]">
                    {fmtDate(f.from_date)} → {fmtDate(f.to_date)} · {f.days_shifted} day(s)
                    {f.reason ? ` · ${f.reason}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
