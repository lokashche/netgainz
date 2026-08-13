"use client";

import { useEffect, useState, use } from "react";
import { decodeId, extractFrappeError } from "@/lib/frappe";
import OfferForm, { toFormValues, type OfferFormValues } from "../OfferForm";
import type { Offer } from "@/lib/types";

type Params = Promise<{ id: string }>;

type Usage = {
  times_used: number;
  uses_left: number | null;
  live: boolean;
  memberships: { name: string; member_name?: string; membership_plan?: string }[];
};

export default function OfferDetailPage({ params }: { params: Params }) {
  // Offers are named after themselves ("New Year 20%"), so the route param comes
  // back URL-encoded and has to be decoded before it is used as a docname.
  const { id: rawId } = use(params);
  const id = decodeId(rawId);

  const [initial, setInitial] = useState<OfferFormValues | null>(null);
  const [offer, setOffer] = useState<Offer | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);

  useEffect(() => {
    (async () => {
      const res = await fetch(`/api/offers/${encodeURIComponent(id)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      const body = (await res.json()) as { data?: Offer };
      if (body.data) {
        setOffer(body.data);
        setInitial(toFormValues(body.data));
      }
    })();
  }, [id]);

  useEffect(() => {
    (async () => {
      const res = await fetch(`/api/offers/${encodeURIComponent(id)}/usage`);
      if (!res.ok) return;
      const body = (await res.json()) as { message?: Usage };
      if (body.message) setUsage(body.message);
    })();
  }, [id]);

  async function endNow() {
    if (!confirm("End this offer now? Members already on it keep the rate they were given.")) {
      return;
    }
    setEnding(true);
    setError(null);
    const res = await fetch(`/api/offers/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disabled: 1 }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(extractFrappeError(body) ?? `Error ${res.status}`);
      setEnding(false);
      return;
    }
    window.location.reload();
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/offers" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Offers
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">{offer?.offer_name ?? id}</h1>
        {offer?.disabled === 1 && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[rgba(138,151,178,0.15)] text-[#8A97B2]">
            Ended
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
          {error}
        </div>
      )}

      {usage && (
        <div className="mb-4 rounded-xl border border-[#1E2D45] bg-[#111A2E] p-4 text-sm">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-[#8FA3BF]">
            <span>
              Given to <span className="text-[#E6EDF7]">{usage.times_used}</span>{" "}
              {usage.times_used === 1 ? "member" : "members"}
            </span>
            <span>
              {usage.uses_left === null
                ? "No limit"
                : `${usage.uses_left} left before the limit is reached`}
            </span>
          </div>
          {usage.memberships.length > 0 && (
            <p className="mt-2 text-xs text-[#8A97B2]">
              Most recent: {usage.memberships.slice(0, 3).map((m) => m.member_name || m.name).join(", ")}
            </p>
          )}
        </div>
      )}

      {initial ? (
        <OfferForm offerName={id} initial={initial}>
          {offer?.disabled !== 1 && (
            <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-4 flex items-center justify-between gap-4">
              <p className="text-sm text-[#8FA3BF]">
                Stop giving this offer out. Members already on it are not re-priced.
              </p>
              <button
                type="button"
                onClick={endNow}
                disabled={ending}
                className="px-4 py-2 text-sm rounded-lg border border-[#F87171] text-[#F87171] hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {ending ? "Ending…" : "End now"}
              </button>
            </div>
          )}
        </OfferForm>
      ) : (
        !error && <p className="text-sm text-[#8A97B2]">Loading…</p>
      )}
    </div>
  );
}
