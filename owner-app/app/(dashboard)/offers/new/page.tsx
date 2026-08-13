import OfferForm, { toFormValues } from "../OfferForm";

export default function NewOfferPage() {
  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/offers" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Offers
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Offer</h1>
      </div>

      <p className="mb-4 text-sm text-[#8A97B2]">
        An offer is given to a member when you enrol them — it fills in their discount, and
        what they were given never changes afterwards, whatever happens to the offer.
      </p>

      <OfferForm initial={toFormValues()} />
    </div>
  );
}
