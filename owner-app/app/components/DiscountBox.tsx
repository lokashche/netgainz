"use client";

import { useEffect, useRef, useState } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type { Capabilities, DiscountDuration, DiscountPreview, DiscountType } from "@/lib/types";

export type DiscountDraft = {
  discount_type: DiscountType;
  discount_value: string;
  discount_duration: DiscountDuration;
  discount_until: string;
  discount_reason: string;
  /** DS-5: a one-time approval from the owner, when the discount is over the limit. */
  discount_approval?: string;
};

export const EMPTY_DISCOUNT: DiscountDraft = {
  discount_type: "",
  discount_value: "",
  discount_duration: "First invoice only",
  discount_until: "",
  discount_reason: "",
};

/** The fields the backend expects, or nothing at all when no discount is given. */
export function discountPayload(d: DiscountDraft): Record<string, string | number | null> {
  if (!d.discount_type) {
    return { discount_type: "", discount_value: 0, discount_until: null, discount_reason: "" };
  }
  return {
    discount_type: d.discount_type,
    discount_value: Number(d.discount_value) || 0,
    discount_duration: d.discount_duration,
    discount_until: d.discount_duration === "Until a date" ? d.discount_until || null : null,
    discount_reason: d.discount_reason,
    ...(d.discount_approval ? { discount_approval: d.discount_approval } : {}),
  };
}

const DURATIONS: { value: DiscountDuration; label: string; hint: string }[] = [
  {
    value: "First invoice only",
    label: "First invoice only",
    hint: "A joining offer. The next invoice bills the full rate.",
  },
  {
    value: "Every invoice",
    label: "Every invoice (lifetime rate)",
    hint: "This member keeps the discounted rate for as long as they stay.",
  },
  {
    value: "Until a date",
    label: "Until a date",
    hint: "Expires by itself — no one has to remember to end it.",
  },
];

const money = (n: number) =>
  `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

interface DiscountBoxProps {
  value: DiscountDraft;
  onChange: (next: DiscountDraft) => void;
  /** This member's price for the period. Used only for the preview. */
  price?: number;
  /** Existing membership, so the backend can read the price when none is typed. */
  membership?: string;
  /** The member being discounted — an owner approval is tied to them. */
  member?: string;
  /** What this user may give away. Absent = no approval prompt is shown. */
  capabilities?: Capabilities | null;
  inputClassName: string;
  labelClassName: string;
}

/**
 * Stage 8 DS-1: grant a discount, and see what it costs before granting it.
 *
 * Every figure shown here — the net price and the profit impact — is computed by
 * the backend from the live Profit First percentages, so the preview is the same
 * arithmetic that will run on the invoice and on the next allocation.
 */
export default function DiscountBox({
  value,
  onChange,
  price,
  membership,
  member,
  capabilities,
  inputClassName,
  labelClassName,
}: DiscountBoxProps) {
  const [preview, setPreview] = useState<DiscountPreview | null>(null);
  const requestSeq = useRef(0);
  const [pin, setPin] = useState("");
  const [approving, setApproving] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  const amount = Number(value.discount_value);
  const hasGrant = Boolean(value.discount_type) && Number.isFinite(amount) && amount > 0;

  useEffect(() => {
    // No grant: drop any answer still in flight and let the render gate below hide
    // whatever was last shown, rather than clearing state from inside the effect.
    const seq = ++requestSeq.current;
    if (!hasGrant) return;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch("/api/discount-preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            membership: membership ?? null,
            price: price ?? null,
            discount_type: value.discount_type,
            discount_value: amount,
          }),
        });
        if (!res.ok) return;
        const body = (await res.json()) as { message?: DiscountPreview };
        // A slower earlier request must never overwrite a newer answer.
        if (seq === requestSeq.current && body.message) setPreview(body.message);
      } catch {
        // The preview is an aid, never a blocker — a failed fetch just shows nothing.
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [hasGrant, amount, value.discount_type, price, membership]);

  // Changing the discount invalidates any approval already given — it was approved for a
  // specific member at a specific size, and the server checks exactly that, so drop it
  // here rather than let the save fail.
  const set = (patch: Partial<DiscountDraft>) => {
    const invalidates = "discount_type" in patch || "discount_value" in patch;
    onChange({ ...value, ...patch, ...(invalidates ? { discount_approval: "" } : {}) });
    if (invalidates) setApprovalError(null);
  };

  // What this discount is worth as a percentage of the price — the same measure the
  // server applies, so a flat amount cannot look small here and be refused there.
  const percentOff =
    value.discount_type === "Percentage"
      ? amount
      : preview && preview.gross > 0
        ? (preview.discount / preview.gross) * 100
        : 0;
  const cap = capabilities?.max_discount_percent ?? 100;
  const freeMembership =
    percentOff >= 100 && (capabilities?.complimentary_requires_owner ?? false);
  const needsApproval =
    Boolean(capabilities) &&
    !capabilities?.can_discount_freely &&
    hasGrant &&
    (percentOff > cap || freeMembership);

  async function approve() {
    setApproving(true);
    setApprovalError(null);
    try {
      const res = await fetch("/api/discounts/authorise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          member: member ?? null,
          membership: membership ?? null,
          discount_type: value.discount_type,
          discount_value: amount,
          pin,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setApprovalError(extractFrappeError(body) ?? `Error ${res.status}`);
        setApproving(false);
        return;
      }
      const approval = (body as { message?: { approval?: string } }).message?.approval;
      if (approval) {
        onChange({ ...value, discount_approval: approval });
        setPin("");
      }
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : "Unexpected error");
    }
    setApproving(false);
  }

  const durationHint = DURATIONS.find((d) => d.value === value.discount_duration)?.hint;

  return (
    <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-4 space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-[#E6EDF7]">Discount</h3>
        <span className="text-xs text-[#8A97B2]">
          Changes this member&rsquo;s invoice — never the plan&rsquo;s price
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className={labelClassName}>Give a discount</label>
          <select
            value={value.discount_type}
            onChange={(e) => {
              const next = e.target.value as DiscountType;
              set(next ? { discount_type: next } : EMPTY_DISCOUNT);
            }}
            className={inputClassName}
          >
            <option value="">No discount</option>
            <option value="Percentage">Percentage off (%)</option>
            <option value="Amount">Amount off (₹)</option>
          </select>
        </div>
        {value.discount_type && (
          <div>
            <label className={labelClassName}>
              {value.discount_type === "Percentage" ? "Percent off" : "Amount off"}{" "}
              <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="number"
              min="0"
              step={value.discount_type === "Percentage" ? "1" : "0.01"}
              max={value.discount_type === "Percentage" ? "100" : undefined}
              value={value.discount_value}
              onChange={(e) => set({ discount_value: e.target.value })}
              placeholder={value.discount_type === "Percentage" ? "10" : "500"}
              className={inputClassName}
            />
          </div>
        )}
      </div>

      {value.discount_type && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClassName}>
                Applies to <span className="text-[#F87171]">*</span>
              </label>
              <select
                value={value.discount_duration}
                onChange={(e) => set({ discount_duration: e.target.value as DiscountDuration })}
                className={inputClassName}
              >
                {DURATIONS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
              {durationHint && <p className="mt-1 text-xs text-[#8A97B2]">{durationHint}</p>}
            </div>
            {value.discount_duration === "Until a date" && (
              <div>
                <label className={labelClassName}>
                  Until <span className="text-[#F87171]">*</span>
                </label>
                <input
                  type="date"
                  value={value.discount_until}
                  onChange={(e) => set({ discount_until: e.target.value })}
                  className={inputClassName}
                />
              </div>
            )}
          </div>

          <div>
            <label className={labelClassName}>
              Reason <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="text"
              value={value.discount_reason}
              onChange={(e) => set({ discount_reason: e.target.value })}
              placeholder="Student rate, long-time member, referral…"
              className={inputClassName}
            />
            <p className="mt-1 text-xs text-[#8A97B2]">
              Required. It is what makes the monthly discounts report worth reading.
            </p>
          </div>
        </>
      )}

      {needsApproval && (
        <div className="rounded-lg border border-[#FBBF24] bg-[rgba(251,191,36,0.08)] p-4 space-y-3">
          <p className="text-sm text-[#FBBF24]">
            {freeMembership
              ? "A free membership needs the owner."
              : `That is ${percentOff.toFixed(0)}% off, and the front desk can give up to ${cap.toFixed(0)}%.`}{" "}
            {value.discount_approval
              ? "Approved."
              : "Ask the owner to type their PIN to approve it."}
          </p>
          {!value.discount_approval && (
            <div className="flex gap-2">
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    approve();
                  }
                }}
                placeholder="Owner PIN"
                autoComplete="off"
                className={inputClassName}
              />
              <button
                type="button"
                onClick={approve}
                disabled={approving || !pin.trim()}
                className="px-4 py-2 text-sm rounded-lg bg-[#1A2540] text-[#E6EDF7] border border-[#1E2D45] hover:bg-[#FBBF24] hover:text-[#0B1220] disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {approving ? "Checking…" : "Approve"}
              </button>
            </div>
          )}
          {approvalError && <p className="text-xs text-[#F87171]">{approvalError}</p>}
        </div>
      )}

      {hasGrant && preview && preview.discount > 0 && (
        <div className="rounded-lg border border-[#1E2D45] bg-[#111A2E] p-4 space-y-3">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
            <span className="text-[#8A97B2]">Per period:</span>
            <span className="text-[#8FA3BF] line-through">{money(preview.gross)}</span>
            <span className="text-[#8A97B2]">→</span>
            <span className="font-semibold text-[#E6EDF7]">{money(preview.net)}</span>
            <span className="text-[#F87171]">({money(preview.discount)} off)</span>
          </div>

          {preview.profit_impact.applicable ? (
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-wider text-[#8A97B2]">
                What it costs you this cycle
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[#8FA3BF]">
                {Object.entries(preview.profit_impact.buckets).map(([bucket, value]) => (
                  <span key={bucket}>
                    {bucket}: <span className="text-[#E6EDF7]">−{money(value)}</span>
                  </span>
                ))}
              </div>
              <p className="text-xs text-[#8A97B2]">
                Profit First allocates a share of every rupee you collect, so a rupee not
                collected is a rupee not allocated.
              </p>
            </div>
          ) : (
            <p className="text-xs text-[#8A97B2]">
              {money(preview.discount)} less collected each period. The profit split appears
              once the gym has enough cash history for a Profit First tier.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
