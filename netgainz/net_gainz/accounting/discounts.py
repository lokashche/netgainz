# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 8 DS-1: per-membership negotiated discounts.

The 80% case at a gym desk is "I gave him Rs.500 off". This module is where that
decision becomes money, and it holds to the stage's product principle: a discount is
a **visible, controlled profit decision**, never silent price erosion.

**Where the money changes (DS-0 traced, 2026-08-11).** The discount is applied to the
generated Sales Invoice inside ``billing.on_sales_invoice_before_validate`` — the same
WP-10.3 seam that already prices the invoice at what this member pays. Two mechanisms
were traced and rejected in favour of it:

* **The native Subscription's own** ``additional_discount_percentage`` /
  ``additional_discount_amount`` *do* flow onto every generated invoice — but onto
  EVERY invoice, forever. They cannot express R18's explicit end ("this cycle only" /
  "until a date"), so a desk discount granted once would quietly become the member's
  permanent rate. That is precisely the leak Stage 8 exists to stop.
* **A per-customer Pricing Rule** works (traced: Rs.150 off, customer-scoped) but hides
  the grant inside an ERPNext master, away from the membership the owner is looking at,
  and still needs our duration logic on top.

Deciding per generated invoice keeps one rule in one place: the membership carries the
grant, this module answers "does it apply to THIS invoice?", and ERPNext does the rest.

**R20 — always applied on the NET total.** ERPNext defaults ``apply_discount_on`` to
"Grand Total", which discounts what the member pays but still charges GST on the
pre-discount value: a Rs.1,062 invoice carrying Rs.180 of GST on Rs.1,000 (DS-0 T1).
The taxable value and the tax must agree, so every discount here sets "Net Total".
Traced consequences, all free: deferred revenue defers the NET (R16), installment
terms split the NET and still balance (R13), and Profit First — which reads collected
cash from Payment Entries — needs no code change at all (R15).

Nothing here edits an Item Price (R14). The plan's rate stays the single price of
record; the discount lives on the invoice, where it can be seen and reported.
"""

import frappe
from frappe.utils import flt, getdate, now_datetime, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.profit_first import calc

# Discount kinds (stored values; the owner app renders "% off" / "Rs. off").
PERCENTAGE = "Percentage"
AMOUNT = "Amount"

# R18 — every discount has an explicit end, chosen at grant time.
#
# "Every invoice" IS the plan's "lifetime rate": a Membership is continuous here (one
# membership drives one native Subscription that keeps renewing), so there is no
# separate renewal record for a lifetime rate to survive into. Collapsing the two
# avoids a distinction with no behavioural difference. The default is deliberately the
# stingiest one — a desk discount stops after the cycle it was granted for unless the
# grantor says otherwise.
FIRST_INVOICE = "First invoice only"
EVERY_INVOICE = "Every invoice"
UNTIL_DATE = "Until a date"
DEFAULT_DURATION = FIRST_INVOICE

# R20: never "Grand Total", never blank.
APPLY_DISCOUNT_ON = "Net Total"

# A discount can never exceed the price: 100% is free, and there is no "more free".
MAX_PERCENTAGE = 100.0

# DS-5 policy defaults, used when the tenant has not set Business Settings yet.
DEFAULT_MAX_STAFF_PERCENT = 10.0
# How long an owner's PIN approval stays usable at the desk. Long enough for the
# owner to walk away and the member to finish signing up; short enough that a
# forgotten approval cannot be spent on a different discount tomorrow.
APPROVAL_TTL_SECONDS = 15 * 60
APPROVAL_CACHE_KEY = "netgainz:discount-approval"


def _raw_setting(field) -> str | None:
	"""A Business Settings value exactly as stored, or None if it was never set.

	``get_single_value`` casts to the field type, so an unset Float comes back as 0.0 —
	indistinguishable from a deliberate zero. That distinction matters here: no setting at
	all means "use the default limit", while an explicit 0 means "the desk gives nothing
	without me". Reading the stored row is the only way to tell them apart.
	"""
	# `order_by=None` is required: the Singles table has no `modified` column, and
	# get_value orders by it unless told otherwise.
	value = frappe.db.get_value(
		"Singles", {"doctype": "Business Settings", "field": field}, "value", order_by=None
	)
	return None if value is None or value == "" else value


def policy() -> dict:
	"""The tenant's discount policy (direct DB reads — the singles cache can be stale)."""
	max_percent = _raw_setting("max_discount_percent")
	comp_owner_only = _raw_setting("complimentary_requires_owner")
	return {
		"max_staff_percent": flt(DEFAULT_MAX_STAFF_PERCENT if max_percent is None else max_percent),
		"complimentary_requires_owner": bool(1 if comp_owner_only is None else int(flt(comp_owner_only))),
	}


# --------------------------------------------------------------------------- #
# reading the grant
# --------------------------------------------------------------------------- #
def membership_discount(membership) -> dict | None:
	"""The normalised discount grant on ``membership``, or None if there isn't one.

	Accepts a Membership doc or dict (the doctype's own validate passes ``self``;
	the invoice seam passes the loaded doc).
	"""
	kind = (membership.get("discount_type") or "").strip()
	value = flt(membership.get("discount_value"))
	if not kind or value <= 0:
		return None
	return {
		"type": kind,
		"value": value,
		"duration": (membership.get("discount_duration") or DEFAULT_DURATION).strip(),
		"until": membership.get("discount_until"),
		"reason": membership.get("discount_reason"),
	}


def discount_rupees(price, discount) -> float:
	"""What ``discount`` takes off a period priced at ``price`` (ex-GST rupees).

	Capped at the price itself: a 100% or over-the-price grant makes the period free
	(the complimentary-membership case — the invoice is still raised), never negative.
	"""
	price = flt(price)
	if price <= 0 or not discount:
		return 0.0
	if discount["type"] == PERCENTAGE:
		off = price * min(flt(discount["value"]), MAX_PERCENTAGE) / 100.0
	else:
		off = flt(discount["value"])
	return min(flt(off), price)


# --------------------------------------------------------------------------- #
# does it apply to THIS invoice? (R18)
# --------------------------------------------------------------------------- #
def _is_first_invoice(doc, membership) -> bool:
	"""True when no other invoice exists yet for this membership's subscription.

	Cancelled invoices (docstatus 2) are ignored deliberately: an invoice cancelled
	in error must not silently burn the member's first-cycle discount.
	"""
	subscription = membership.get("subscription")
	if not subscription:
		return True
	filters = {"subscription": subscription, "docstatus": ["<", 2]}
	if doc.get("name"):
		filters["name"] = ["!=", doc.name]
	return not frappe.db.exists("Sales Invoice", filters)


def applies_to_invoice(doc, membership, discount=None) -> bool:
	"""Whether the membership's grant covers the invoice being generated."""
	discount = discount or membership_discount(membership)
	if not discount:
		return False
	duration = discount["duration"]
	if duration == EVERY_INVOICE:
		return True
	if duration == UNTIL_DATE:
		if not discount["until"]:
			return False
		return getdate(doc.get("posting_date") or today()) <= getdate(discount["until"])
	return _is_first_invoice(doc, membership)


# --------------------------------------------------------------------------- #
# applying it (called from the billing seam, before validate)
# --------------------------------------------------------------------------- #
def apply_to_invoice(doc, membership) -> float:
	"""Put the membership's discount on the generated invoice. Returns rupees off.

	Runs after ``billing._apply_membership_price``, so the item already carries THIS
	member's rate and a percentage discount comes off the negotiated price rather
	than the plan's. Percentages are handed to ERPNext as a percentage (so the
	invoice reads "10% off" rather than a derived figure); flat amounts are capped
	at the line total so an invoice can never go negative.
	"""
	discount = membership_discount(membership)
	if not discount or not applies_to_invoice(doc, membership, discount):
		return 0.0

	items = doc.get("items") or []
	if len(items) != 1:
		# Same guard as the pricing seam: a membership invoice is always one line.
		return 0.0
	line_total = flt(items[0].rate) * flt(items[0].qty or 1)
	off = discount_rupees(line_total, discount)
	if off <= 0:
		return 0.0

	doc.apply_discount_on = APPLY_DISCOUNT_ON  # R20
	if discount["type"] == PERCENTAGE:
		doc.additional_discount_percentage = min(flt(discount["value"]), MAX_PERCENTAGE)
		doc.discount_amount = 0
	else:
		doc.additional_discount_percentage = 0
		doc.discount_amount = off
	return off


# --------------------------------------------------------------------------- #
# guardrails (R17 — server-side, never UI-only)
# --------------------------------------------------------------------------- #
def validate_membership_discount(membership) -> None:
	"""Reject an incoherent or out-of-policy grant when the Membership is saved.

	DS-1 enforces coherence + R18's explicit end + a mandatory reason. DS-5 adds the
	policy ceilings (max % per role, owner-only comps, approval above a threshold) in
	:func:`assert_within_policy`, which is already called from here so the wiring
	never has to be revisited.
	"""
	kind = (membership.get("discount_type") or "").strip()
	value = flt(membership.get("discount_value"))

	if not kind:
		# Clearing the type IS how a discount is removed, so that must never error —
		# but a value typed with no type at all is a half-made grant and would
		# silently charge the member full price, so that is refused.
		half_made = value and (membership.is_new() or not membership.has_value_changed("discount_type"))
		if half_made:
			frappe.throw("Choose whether the discount is a percentage or an amount.")
		# Removed: clear the trailing fields so nothing is left behind to puzzle over.
		membership.discount_value = 0
		membership.discount_until = None
		membership.discount_duration = None
		membership.discount_approval = None
		membership.discount_approved_on = None
		return

	if value <= 0:
		frappe.throw("A discount needs a value above zero — or clear the discount type.")
	if kind == PERCENTAGE and value > MAX_PERCENTAGE:
		frappe.throw("A discount cannot be more than 100%.")

	price = flt(membership.get("tariff")) or _plan_price(membership)
	if kind == AMOUNT and price and value > price:
		frappe.throw(
			f"A discount of {frappe.format_value(value, {'fieldtype': 'Currency'})} is more than "
			f"this member's price of {frappe.format_value(price, {'fieldtype': 'Currency'})}."
		)

	# R18: an explicit end, always.
	duration = (membership.get("discount_duration") or "").strip()
	if not duration:
		membership.discount_duration = duration = DEFAULT_DURATION
	if duration == UNTIL_DATE and not membership.get("discount_until"):
		frappe.throw("Set the date this discount runs until.")
	if duration != UNTIL_DATE:
		membership.discount_until = None

	# R17: a discount without a reason is unreportable, so it is not allowed.
	if not (membership.get("discount_reason") or "").strip():
		frappe.throw("Say why this discount was given — it appears on the discounts report.")

	assert_within_policy(membership, kind, value)

	# Who granted it, stamped server-side (never trusted from the client).
	if not membership.get("discount_granted_by") or membership.has_value_changed("discount_value"):
		membership.discount_granted_by = frappe.session.user


# --------------------------------------------------------------------------- #
# DS-5: how big a discount may this person give, and how the owner approves more
# --------------------------------------------------------------------------- #
def effective_percent(membership, kind, value) -> float:
	"""What this grant costs as a percentage of the member's price.

	A flat amount is measured against the price so it cannot be used to walk around a
	percentage ceiling: Rs.900 off a Rs.1,000 membership is 90%, however it was typed.
	With no price resolvable yet, a flat amount cannot be judged — treated as within
	policy rather than guessed at, since the DS-1 rules already refuse a discount larger
	than the price.
	"""
	value = flt(value)
	if kind == PERCENTAGE:
		return value
	price = flt(membership.get("tariff")) or _plan_price(membership)
	if price <= 0:
		return 0.0
	return value * 100.0 / price


def _approval_fingerprint(membership, kind, value) -> str:
	"""What an approval is FOR. Changing any of it invalidates the approval.

	Keyed on the member rather than the membership so an approval given while enrolling
	someone (the membership does not exist yet) still matches when it is saved — but a
	staff member cannot reuse it for a different member, a different size, or a
	different kind of discount.
	"""
	return f"{membership.get('member') or ''}|{kind}|{flt(value)}"


@frappe.whitelist()
def authorise_discount(
	member=None, membership=None, discount_type=None, discount_value=None, pin=None
) -> dict:
	"""Owner approves a bigger discount at the desk, with the gym's owner PIN.

	Returns a one-time approval to send with the membership save. The PIN itself never
	touches the membership: it is checked here, and what travels back is a random key
	that only matches THIS member, kind and size, for 15 minutes.

	Chosen over a submittable approval document deliberately (the plan left it open):
	an approval that needs a second screen and a later visit does not fit a front desk
	with a member standing at it — the owner walks over, types the PIN, and the sign-up
	continues.
	"""
	stored = frappe.utils.password.get_decrypted_password(
		"Business Settings", "Business Settings", "owner_approval_pin", raise_exception=False
	)
	if not stored:
		frappe.throw(
			"No owner PIN is set, so a discount above the limit cannot be approved at the desk. "
			"The owner can set one in Settings, or give the discount themselves."
		)
	if not pin or str(pin).strip() != str(stored).strip():
		frappe.throw("That PIN is not right.", frappe.AuthenticationError)

	if not member and membership:
		member = frappe.db.get_value("Membership", membership, "member")
	fingerprint = _approval_fingerprint({"member": member}, discount_type, discount_value)
	token = frappe.generate_hash(length=32)
	frappe.cache().set_value(
		f"{APPROVAL_CACHE_KEY}:{token}",
		{"fingerprint": fingerprint, "user": frappe.session.user},
		expires_in_sec=APPROVAL_TTL_SECONDS,
	)
	return {"approval": token, "expires_in_seconds": APPROVAL_TTL_SECONDS}


def _consume_approval(membership, kind, value) -> bool:
	"""Spend the approval on the membership, if it is real and for THIS discount."""
	token = (membership.get("discount_approval") or "").strip()
	if not token:
		return False
	key = f"{APPROVAL_CACHE_KEY}:{token}"
	held = frappe.cache().get_value(key)
	if not held or held.get("fingerprint") != _approval_fingerprint(membership, kind, value):
		return False
	# One-time: an approval cannot be replayed on the next member.
	frappe.cache().delete_value(key)
	return True


def assert_within_policy(membership, kind, value) -> None:
	"""R17: what the front desk may give away on its own — enforced server-side.

	The rules, all of them the owner's to change in Settings:

	* a **Gym Owner** is not capped (they own the money being given away);
	* a **complimentary membership** (100% off) is owner-only by default, whatever the
	  percentage limit says — giving a membership away is a different decision from
	  discounting one;
	* anyone else is capped at the tenant's percentage, measured on the member's price so
	  a flat amount cannot dodge it;
	* over the cap, the owner can approve it on the spot with the gym PIN
	  (:func:`authorise_discount`) — otherwise it is refused with the actual number.

	A discount that came from an **Offer** is exempt: the owner defined the campaign, and
	staff can only give out offers that are already running (only owners can create them).
	Making the desk re-approve the owner's own campaign would be theatre.
	"""
	# Spend (and always clear) the approval first: it is one-time, and it must never be
	# left sitting on the record for a later save to reuse.
	approved = _consume_approval(membership, kind, value)
	membership.discount_approval = None

	if membership.get("offer"):
		return
	if permissions.has_role(permissions.GYM_OWNER):
		return

	rules = policy()
	percent = effective_percent(membership, kind, value)

	if percent >= MAX_PERCENTAGE and rules["complimentary_requires_owner"] and not approved:
		frappe.throw(
			"A free membership can only be given by the owner. Ask them to approve it, "
			"or to add it themselves.",
			frappe.PermissionError,
		)

	cap = rules["max_staff_percent"]
	if percent > cap and not approved:
		frappe.throw(
			f"That is {percent:.0f}% off, and the front desk can give up to {cap:.0f}%. "
			"Ask the owner to approve it.",
			frappe.PermissionError,
		)

	if approved:
		membership.discount_approved_on = now_datetime()


def _plan_price(membership) -> float:
	plan = membership.get("membership_plan")
	return flt(frappe.db.get_value("Membership Plan", plan, "amount")) if plan else 0.0


# --------------------------------------------------------------------------- #
# DS-5: the audit trail
# --------------------------------------------------------------------------- #
def _grant_fields(doc) -> tuple:
	return (
		(doc.get("discount_type") or ""),
		flt(doc.get("discount_value")),
		(doc.get("discount_duration") or ""),
		str(doc.get("discount_until") or ""),
		(doc.get("offer") or ""),
		(doc.get("discount_reason") or ""),
	)


def log_discount_change(membership) -> str | None:
	"""Write a Discount Log row when a membership's discount actually changed.

	Called after the save, so nothing is logged for a grant that was refused. The
	membership only ever shows the discount a member has NOW; this is what lets the owner
	see that a 10% rate quietly became 30% last month, who did it and why.

	Frappe's own version tracking was considered and rejected for this: it would record
	every billing-sync touch (status, balance due) on the busiest doctype in the app, and
	still leave the discounts report joining against free text.
	"""
	# On an insert there is nothing before, and `get_doc_before_save` is not a reliable
	# stand-in: by the time `on_update` runs, the billing hooks have touched the document
	# and it can hand back a copy of the row that was just written — which would compare
	# equal and log nothing at all. `flags.in_insert` is the honest signal.
	before = None if membership.flags.in_insert else membership.get_doc_before_save()
	after = _grant_fields(membership)
	previous = _grant_fields(before) if before else _grant_fields({})
	if after == previous:
		return None

	had, has = bool(previous[0]), bool(after[0])
	if not has and not had:
		return None
	action = "Given" if not had else ("Removed" if not has else "Changed")

	row = frappe.get_doc(
		{
			"doctype": "Discount Log",
			"membership": membership.name,
			"member": membership.get("member"),
			"member_name": membership.get("member_name"),
			"branch": membership.get("branch"),
			"action": action,
			"granted_by": frappe.session.user,
			"approved": 1 if membership.get("discount_approved_on") else 0,
			"discount_type": after[0],
			"discount_value": after[1],
			"discount_duration": after[2],
			"discount_until": membership.get("discount_until"),
			"offer": membership.get("offer"),
			"previous_type": previous[0],
			"previous_value": previous[1],
			"previous_duration": previous[2],
			"reason": after[5] or previous[5],
		}
	).insert(ignore_permissions=True)
	return row.name


@frappe.whitelist()
def discount_history(membership=None, member=None, limit=50) -> list[dict]:
	"""Every discount decision on a membership (or a member), newest first.

	Owner-only: this is the review tool, not something the desk needs while enrolling
	(what the member has NOW is on the membership itself).
	"""
	permissions.require_role(permissions.GYM_OWNER)
	filters = {}
	if membership:
		filters["membership"] = membership
	if member:
		filters["member"] = member
	if not filters:
		frappe.throw("Ask for a membership or a member.")
	return frappe.get_all(
		"Discount Log",
		filters=filters,
		fields=[
			"name",
			"creation",
			"action",
			"granted_by",
			"approved",
			"discount_type",
			"discount_value",
			"discount_duration",
			"discount_until",
			"offer",
			"previous_type",
			"previous_value",
			"reason",
		],
		order_by="creation desc",
		limit_page_length=int(limit or 50),
	)


# --------------------------------------------------------------------------- #
# profit-impact preview (DS-6's calc, minimal form — pure read-model, R15)
# --------------------------------------------------------------------------- #
def profit_impact(amount) -> dict:
	"""What giving away ``amount`` (ex-GST rupees) costs, split at the CURRENT TAPs.

	Profit First allocates a percentage of every rupee COLLECTED, so a rupee not
	collected is a rupee not allocated: the loss lands on the owner's buckets in
	exactly the tier's proportions. Read-only — it computes nothing that is stored and
	touches no PF write path (R15).
	"""
	from netgainz.net_gainz.profit_first import instant_assessment

	amount = flt(amount)
	result = {
		"amount": amount,
		"applicable": False,
		"tier_code": None,
		"buckets": {},
	}
	if amount <= 0:
		return result

	allocation = instant_assessment.get_target_allocation()
	if not allocation.get("applicable"):
		# No tier yet (a brand-new gym with no cash history) — the discount still
		# costs the full amount; we just cannot split it.
		return result

	taps = allocation["taps"]
	split = calc.largest_remainder_allocate(
		calc.to_paise(amount),
		[(bucket, taps[bucket]) for bucket in calc.ALLOCATION_BUCKETS],
	)
	result.update(
		{
			"applicable": True,
			"tier_code": allocation.get("tier_code"),
			"taps": taps,
			"buckets": {bucket: calc.to_rupees(paise) for bucket, paise in split.items()},
		}
	)
	return result


@frappe.whitelist()
def preview_discount(membership=None, price=None, discount_type=None, discount_value=None) -> dict:
	"""Grant-time preview for the owner app: gross -> discount -> net, plus the
	profit impact at the current TAPs.

	Called before the grant is saved, so the proposed figures are passed in; an
	existing ``membership`` supplies the price (and its own grant) when they are not.
	"""
	doc = frappe.get_doc("Membership", membership) if membership else None
	if doc:
		doc.check_permission("read")

	gross = flt(price)
	if not gross and doc:
		from netgainz.net_gainz.accounting import billing

		gross = flt(billing.membership_price(doc))

	if discount_type is None and doc:
		discount = membership_discount(doc)
	else:
		discount = membership_discount({"discount_type": discount_type, "discount_value": discount_value})

	off = discount_rupees(gross, discount)
	return {
		"gross": gross,
		"discount": off,
		"net": flt(gross - off),
		"profit_impact": profit_impact(off),
	}
