"use client";

import { useEffect, useState } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type { AvailableOffer, RedeemedCoupon } from "@/lib/types";

const describe = (offer: AvailableOffer) => {
  const amount =
    offer.discount_type === "Percentage"
      ? `${offer.discount_value}% off`
      : `₹${offer.discount_value.toLocaleString("en-IN")} off`;
  const left = offer.uses_left === null ? "" : ` · ${offer.uses_left} left`;
  return `${offer.offer_name} — ${amount}, ${offer.discount_duration.toLowerCase()}${left}`;
};

interface OfferPickerProps {
  value: string;
  onChange: (offer: string) => void;
  /** Only offers that run on this plan are shown. */
  membershipPlan?: string;
  branch?: string;
  /** The member being enrolled, so a per-member coupon limit is checked here too. */
  member?: string;
  inputClassName: string;
  labelClassName: string;
}

/**
 * DS-2 / DS-3: give a member one of the gym's running offers, or apply a coupon code.
 *
 * Both lists of rules live on the server. The dropdown only ever shows offers that may
 * be given right now — an offer that has ended, has not started, is out of scope for the
 * plan or is used up never appears. Coupon offers appear in neither list on purpose:
 * knowing the code is the gate, so a code is typed and checked. Either way the identical
 * checks run again when the membership is saved.
 */
export default function OfferPicker({
  value,
  onChange,
  membershipPlan,
  branch,
  member,
  inputClassName,
  labelClassName,
}: OfferPickerProps) {
  const [offers, setOffers] = useState<AvailableOffer[]>([]);
  const [code, setCode] = useState("");
  const [checking, setChecking] = useState(false);
  const [redeemed, setRedeemed] = useState<RedeemedCoupon | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      const args = new URLSearchParams();
      if (membershipPlan) args.set("membership_plan", membershipPlan);
      if (branch) args.set("branch", branch);
      try {
        const res = await fetch(`/api/offers/available?${args.toString()}`);
        if (!res.ok) return;
        const body = (await res.json()) as { message?: AvailableOffer[] };
        if (live && body.message) setOffers(body.message);
      } catch {
        // The picker is an aid; a failed fetch just leaves it empty.
      }
    })();
    return () => {
      live = false;
    };
  }, [membershipPlan, branch]);

  async function applyCode() {
    const typed = code.trim();
    if (!typed) return;
    setChecking(true);
    setCodeError(null);
    setRedeemed(null);
    try {
      const res = await fetch("/api/offers/redeem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: typed,
          membership_plan: membershipPlan ?? null,
          branch: branch ?? null,
          member: member ?? null,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // The backend's message is the useful one — "used up", "expired", "wrong plan".
        setCodeError(extractFrappeError(body) ?? `Error ${res.status}`);
        setChecking(false);
        return;
      }
      const coupon = (body as { message?: RedeemedCoupon }).message;
      if (coupon) {
        setRedeemed(coupon);
        onChange(coupon.offer);
      }
    } catch (err) {
      setCodeError(err instanceof Error ? err.message : "Unexpected error");
    }
    setChecking(false);
  }

  // An offer already given may have since ended, so keep it selectable/visible.
  const known = offers.some((o) => o.name === value);

  return (
    <div className="space-y-3">
      {(offers.length > 0 || value) && (
        <div>
          <label className={labelClassName}>Offer</label>
          <select
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setRedeemed(null);
            }}
            className={inputClassName}
          >
            <option value="">No offer</option>
            {!known && value && <option value={value}>{value}</option>}
            {offers.map((offer) => (
              <option key={offer.name} value={offer.name}>
                {describe(offer)}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-[#8A97B2]">
            Choosing an offer fills in the discount below. What a member was given never
            changes afterwards, even if the offer is edited or ended.
          </p>
        </div>
      )}

      <div>
        <label className={labelClassName}>Coupon code</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                // This box sits inside the membership form; Enter must check the code,
                // not save a half-filled membership.
                e.preventDefault();
                applyCode();
              }
            }}
            placeholder="FIT50"
            className={inputClassName}
          />
          <button
            type="button"
            onClick={applyCode}
            disabled={checking || !code.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-[#1A2540] text-[#E6EDF7] border border-[#1E2D45] hover:bg-[#22D38C] hover:text-[#0B1220] disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {checking ? "Checking…" : "Apply"}
          </button>
        </div>
        {codeError && <p className="mt-1 text-xs text-[#F87171]">{codeError}</p>}
        {redeemed && (
          <p className="mt-1 text-xs text-[#22D38C]">
            {redeemed.coupon_code} applied — {redeemed.offer_name}:{" "}
            {redeemed.discount_type === "Percentage"
              ? `${redeemed.discount_value}% off`
              : `₹${redeemed.discount_value.toLocaleString("en-IN")} off`}
            , {redeemed.discount_duration.toLowerCase()}.
          </p>
        )}
      </div>
    </div>
  );
}
