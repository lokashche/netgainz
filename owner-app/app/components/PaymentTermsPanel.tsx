"use client";

import { useCallback, useEffect, useState } from "react";
import type { MembershipTerms } from "@/lib/types";
import PaymentTermsFields, {
  EMPTY_TERMS,
  type TermsDraft,
} from "@/app/components/PaymentTermsFields";

// Change one member's payment terms after they have joined.
//
// The honest limitation, stated on screen rather than buried: this applies to the
// NEXT invoice. ERPNext marks a submitted invoice's payment schedule read-only, and
// that is the right call — money may already be allocated against those rows.

export default function PaymentTermsPanel({
  membershipId,
  inputClass,
  labelClass,
}: {
  membershipId: string;
  inputClass: string;
  labelClass: string;
}) {
  const [terms, setTerms] = useState<MembershipTerms | null>(null);
  const [draft, setDraft] = useState<TermsDraft>(EMPTY_TERMS);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const path = `/api/subscriptions/${encodeURIComponent(membershipId)}/payment-terms`;

  const load = useCallback(async () => {
    try {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`Could not read the payment terms (${res.status}).`);
      const body = (await res.json()) as MembershipTerms | null;
      setTerms(body);
      if (body) {
        setDraft(
          body.uses_own_terms
            ? {
                payment_due_rule: body.payment_due_rule,
                installment_count: body.installment_count,
                installment_gap_days: body.installment_gap_days,
              }
            : EMPTY_TERMS
        );
      }
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read the payment terms.");
    }
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    setError("");
    setSaved("");
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payment_due_rule: draft.payment_due_rule || "",
          installment_count: draft.installment_count === "" ? 0 : Number(draft.installment_count),
          installment_gap_days:
            draft.installment_gap_days === "" ? 0 : Number(draft.installment_gap_days),
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { message?: string };
        throw new Error(body.message ?? `That did not save (${res.status}).`);
      }
      const body = (await res.json()) as MembershipTerms;
      setTerms(body);
      setEditing(false);
      setSaved("Saved. This applies from their next invoice.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not save.");
    } finally {
      setSaving(false);
    }
  };

  if (!terms && !error) return null;

  return (
    <div className="rounded-lg border border-[#1E2D45] p-4 space-y-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-[#E5EDF7]">How they pay</h3>
        {!editing && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="text-xs text-[#22D38C] hover:underline"
          >
            Change →
          </button>
        )}
      </div>

      {terms && !editing && (
        <div>
          <p className="text-[#E6EDF7] text-sm">{terms.summary}</p>
          <p className="text-[#8A97B2] text-xs mt-1">
            {terms.uses_own_terms
              ? `This member only. The ${terms.plan ?? "plan"} plan says: ${terms.plan_summary}.`
              : `Following the ${terms.plan ?? "plan"} plan.`}
          </p>
        </div>
      )}

      {terms && editing && (
        <div className="space-y-3">
          <PaymentTermsFields
            value={draft}
            onChange={setDraft}
            planSummary={terms.plan_summary}
            maxInstallments={terms.max_installments}
            inputClass={inputClass}
            labelClass={labelClass}
          />
          <p className="text-xs text-[#FBBF24]">
            This applies to their next invoice. An invoice already raised keeps the
            instalments it was issued with.
          </p>
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-[#22D38C] text-[#0B1220] hover:bg-[#1CB877] disabled:opacity-40"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => {
                setEditing(false);
                setError("");
                setDraft(
                  terms.uses_own_terms
                    ? {
                        payment_due_rule: terms.payment_due_rule,
                        installment_count: terms.installment_count,
                        installment_gap_days: terms.installment_gap_days,
                      }
                    : EMPTY_TERMS
                );
              }}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-[#1E2D45] text-[#E6EDF7] hover:bg-[#26364F]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {saved && <p className="text-xs text-[#22D38C]">{saved}</p>}
      {error && <p className="text-xs text-[#F87171]">{error}</p>}
    </div>
  );
}
