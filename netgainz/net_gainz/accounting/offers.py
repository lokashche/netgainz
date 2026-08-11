# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 8 DS-2: Offers — the gym's campaigns, and how one reaches an invoice.

An **Offer** is the campaign ("New Year 20%", "Founding Member Rate", "first 50 get
Rs.1,000 off"). Giving it to a member writes that campaign's terms onto the
membership as an ordinary DS-1 discount grant, and from there the money moves through
the one seam that already exists. So the whole stage keeps a single answer to "where
does a discount become money?" — ``discounts.apply_to_invoice``.

**Why not an ERPNext Pricing Rule?** The original plan said to provision one silently.
The DS-0 trace changed that (recorded here rather than in a commit message, because the
next person will ask):

* A Pricing Rule matches on item + date window, so a live campaign discounts **every**
  invoice for those plans — including members who never asked for it, backfilled rows,
  and members who already negotiated their own rate. DS-0 confirmed a doc-level discount
  and a Pricing Rule **compound**, so those members would silently get both.
* The rule's discount is computed inside ERPNext, so the guardrails (DS-5), the
  redemption limit and the discounts report would each have to reverse-engineer a figure
  they did not calculate.
* Nothing is lost by resolving the offer onto the membership instead: a gym gives an
  offer to a member *at the desk*, when they join or renew, which is exactly the moment
  the membership is saved.

**Grandfathering.** The grant is copied at the moment the offer is given, and never
re-read. Editing or ending an offer therefore cannot re-price members who are already on
it — which is what "founding member rate" means, and what any member would expect.

**DS-3 — coupon codes.** A coupon is simply an offer with a code on it: the code hides
it from the enrolment list (you have to know it) and adds a per-member limit. ERPNext's
own Coupon Code doctype is not used — DS-0 found a Sales Invoice has no coupon field at
all and never counts redemptions (only Sales Orders and POS Invoices do), so the count
would have been fiction. Nor is there a separate redemption log: the **membership is the
redemption record** — it holds the offer, the member, the branch, the date and the exact
terms that were given — so a count taken from memberships can never drift from what was
actually granted (the same reasoning as the usage limit above).

Branch-aware from birth (R19): an offer with no branch runs everywhere; one with a
branch is only offerable to memberships at that branch.
"""

import frappe
from frappe.utils import flt, getdate, today

from netgainz.net_gainz.accounting import discounts

# An offer's own duration wording. The first two map straight onto the DS-1 grant;
# the third resolves to "until <the offer's end date>" at the moment it is given.
FIRST_INVOICE = discounts.FIRST_INVOICE
EVERY_INVOICE = discounts.EVERY_INVOICE
UNTIL_OFFER_ENDS = "Until the offer ends"


# --------------------------------------------------------------------------- #
# is this offer available to this membership?
# --------------------------------------------------------------------------- #
def is_live(offer, on_date=None) -> bool:
	"""Whether ``offer`` can be given out on ``on_date`` (default today)."""
	on_date = getdate(on_date or today())
	if offer.get("disabled"):
		return False
	if offer.get("valid_from") and on_date < getdate(offer.valid_from):
		return False
	if offer.get("valid_upto") and on_date > getdate(offer.valid_upto):
		return False
	return True


def covers_plan(offer, membership_plan) -> bool:
	"""An offer with no plans listed runs on every plan."""
	plans = [row.membership_plan for row in (offer.get("plans") or [])]
	return not plans or membership_plan in plans


def covers_branch(offer, branch) -> bool:
	"""An offer with no branch runs at every branch (R19)."""
	return not offer.get("branch") or offer.branch == branch


def normalise_code(code) -> str:
	"""Codes are quoted over a counter and typed on a phone: capitals, no spaces."""
	return "".join((code or "").split()).upper()


def offer_for_code(code) -> str | None:
	"""The offer a coupon code belongs to, or None. Case- and space-insensitive."""
	code = normalise_code(code)
	if not code:
		return None
	return frappe.db.get_value("Offer", {"coupon_code": code}, "name")


def times_used_by_member(offer_name, member, exclude_membership=None) -> int:
	"""How many times ONE member has been given this offer."""
	if not member:
		return 0
	filters = {"offer": offer_name, "member": member}
	if exclude_membership:
		filters["name"] = ["!=", exclude_membership]
	return frappe.db.count("Membership", filters)


def times_used(offer_name, exclude_membership=None) -> int:
	"""How many memberships have been given this offer.

	Counted from the memberships themselves rather than a stored tally, so the number
	can never drift from reality — and it is the same query the discounts report will
	group by.
	"""
	filters = {"offer": offer_name}
	if exclude_membership:
		filters["name"] = ["!=", exclude_membership]
	return frappe.db.count("Membership", filters)


def uses_left(offer) -> int | None:
	"""Remaining uses, or None when the offer has no limit."""
	limit = int(offer.get("max_total_uses") or 0)
	if not limit:
		return None
	return max(0, limit - times_used(offer.name))


def assert_available(offer, membership) -> None:
	"""Refuse an offer that is over, not started, out of scope, or used up.

	Server-side (R17): the owner app hides unavailable offers, but the rule lives here
	so it holds however the membership was saved.
	"""
	if not is_live(offer):
		frappe.throw(f"The offer '{offer.offer_name}' is not running — it has ended or has not started.")
	if not covers_plan(offer, membership.get("membership_plan")):
		frappe.throw(f"The offer '{offer.offer_name}' does not apply to this membership's plan.")
	if not covers_branch(offer, membership.get("branch")):
		frappe.throw(f"The offer '{offer.offer_name}' only runs at {offer.branch}.")
	limit = int(offer.get("max_total_uses") or 0)
	if limit and times_used(offer.name, exclude_membership=membership.get("name")) >= limit:
		frappe.throw(
			f"The offer '{offer.offer_name}' is used up — its limit of {limit} members has been reached."
		)
	per_member = int(offer.get("max_uses_per_member") or 0)
	if per_member:
		used = times_used_by_member(
			offer.name, membership.get("member"), exclude_membership=membership.get("name")
		)
		if used >= per_member:
			frappe.throw(
				f"This member has already used '{offer.offer_name}' "
				f"{used} {'time' if used == 1 else 'times'} — the limit is {per_member}."
			)


# --------------------------------------------------------------------------- #
# giving the offer: campaign -> this membership's grant
# --------------------------------------------------------------------------- #
def grant_from_offer(offer) -> dict:
	"""The DS-1 discount grant this offer becomes on a membership."""
	duration = offer.get("discount_duration") or FIRST_INVOICE
	until = None
	if duration == UNTIL_OFFER_ENDS:
		duration = discounts.UNTIL_DATE
		until = offer.valid_upto
	return {
		"discount_type": offer.discount_type,
		"discount_value": flt(offer.discount_value),
		"discount_duration": duration,
		"discount_until": until,
		"discount_reason": f"Offer: {offer.offer_name}",
	}


def apply_offer_to_membership(membership) -> None:
	"""Stamp the linked offer's terms onto the membership, once, when it is given.

	Runs before the DS-1 guardrails, so an offer's grant is checked by exactly the same
	rules a hand-typed discount is. Only acts when the ``offer`` link CHANGES: re-reading
	it on every later save would let an edited campaign silently re-price a member who
	was already given the old terms.
	"""
	changed = membership.is_new() or membership.has_value_changed("offer")
	if not changed:
		return

	if not membership.get("offer"):
		# The offer was taken off: clear the grant it put there, but leave a discount
		# the owner typed by hand alone.
		if (membership.get("discount_reason") or "").startswith("Offer: "):
			membership.discount_type = ""
			membership.discount_value = 0
			membership.discount_duration = None
			membership.discount_until = None
			membership.discount_reason = ""
		return

	offer = frappe.get_doc("Offer", membership.offer)
	assert_available(offer, membership)
	membership.update(grant_from_offer(offer))


# --------------------------------------------------------------------------- #
# owner-app reads
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def available_offers(membership_plan=None, branch=None) -> list[dict]:
	"""The offers the desk may give out right now, for this plan and branch.

	Read-only. Ordered so the plainly-labelled ones a gym runs most (the biggest
	discount first) are easy to spot.
	"""
	rows = frappe.get_all(
		"Offer",
		# A coupon offer is deliberately absent: the whole point of a code is that you
		# have to know it. It reaches a membership through :func:`redeem_code`.
		filters={"disabled": 0, "coupon_code": ("in", ("", None))},
		fields=[
			"name",
			"offer_name",
			"description",
			"discount_type",
			"discount_value",
			"discount_duration",
			"valid_from",
			"valid_upto",
			"max_total_uses",
			"branch",
			"coupon_code",
		],
		limit_page_length=0,
	)
	available = []
	for row in rows:
		offer = frappe.get_doc("Offer", row.name)
		if not is_live(offer):
			continue
		if membership_plan and not covers_plan(offer, membership_plan):
			continue
		if branch and not covers_branch(offer, branch):
			continue
		left = uses_left(offer)
		if left == 0:
			continue
		row["uses_left"] = left
		row["times_used"] = times_used(offer.name)
		available.append(row)
	return sorted(available, key=lambda r: flt(r["discount_value"]), reverse=True)


@frappe.whitelist()
def redeem_code(code, membership_plan=None, branch=None, member=None) -> dict:
	"""Check a coupon code and return the offer it unlocks, or say why it cannot be used.

	This is the single entry point for a code, wherever it is typed: the owner app today,
	the member app (Stage 13) and the marketing site (Stage 14) later. It only VALIDATES
	— the offer is actually given when the membership is saved with it, and the same
	checks run again there (R17), so nothing is decided by the caller.
	"""
	name = offer_for_code(code)
	if not name:
		frappe.throw(f"No offer found for the code '{normalise_code(code)}'.")

	offer = frappe.get_doc("Offer", name)
	# A dict stands in for the membership being enrolled, so one set of rules covers a
	# code typed before the membership exists and one saved on an existing membership.
	assert_available(
		offer,
		{"membership_plan": membership_plan, "branch": branch, "member": member, "name": None},
	)
	return {
		"offer": offer.name,
		"offer_name": offer.offer_name,
		"description": offer.description,
		"coupon_code": offer.coupon_code,
		"discount_type": offer.discount_type,
		"discount_value": flt(offer.discount_value),
		"discount_duration": offer.discount_duration,
		"valid_upto": offer.valid_upto,
		"uses_left": uses_left(offer),
	}


@frappe.whitelist()
def offer_usage(offer) -> dict:
	"""How an offer is doing: given out, left, and to whom."""
	doc = frappe.get_doc("Offer", offer)
	doc.check_permission("read")
	memberships = frappe.get_all(
		"Membership",
		filters={"offer": doc.name},
		fields=["name", "member", "member_name", "membership_plan", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	return {
		"offer": doc.name,
		"live": is_live(doc),
		"times_used": len(memberships),
		"uses_left": uses_left(doc),
		"memberships": memberships,
	}
