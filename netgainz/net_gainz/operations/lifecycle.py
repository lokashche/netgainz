# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Membership lifecycle — freeze, plan change, cancellation, transfer (Stage 9 OP-3).

Everything here is assembly of rails that already exist, per ADR-0008:

* **Freeze is a date-shift, never a cancel/re-create (R21).** Both stored period
  dates move — the end is computed here (`start + cycle`), because ERPNext anchors
  it to ``start_date`` and would bill a short window at the full cycle rate.
  Nothing is cancelled, so nothing needs the booby-trapped restart.
* **Value that stays in the gym is a DS-1 discount; money that leaves is a WP-8
  refund.** A plan change or transfer credits the unused, already-paid days as a
  first-invoice discount (system-computed — exempt from the staff cap, see
  ``discounts.assert_within_policy``). A cancellation refund, where the tenant's
  policy grants one, pays real cash out through ``refunds.refund_membership`` —
  and that path is owner-only, like every other way money leaves the business.
* **The refund policy is the tenant's, not ours.** ``cancellation_refund_policy``
  in Business Settings (default "No refund") — NetGainz is a software provider;
  every gym answers policy questions for itself.

Credits are computed from the CURRENT PAID invoice only (net total / period days
x unused days). An unpaid period grants no credit — the member has not paid for
anything unused — and the unpaid invoice itself stands (D3: obligations are
collected or written off, never silently forgiven).
"""

import frappe
from frappe.utils import add_days, add_to_date, flt, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing, provisioning, refunds, trials

REFUND_POLICY_NONE = "No refund"
REFUND_POLICY_PRORATED = "Prorated unused days"

LIVE_STATUSES = ("Trial", "Pending", "Paid", "Overdue", "Partial")


def _refund_policy() -> str:
	return frappe.db.get_single_value("Business Settings", "cancellation_refund_policy") or REFUND_POLICY_NONE


def _assert_not_cancelled(membership) -> None:
	if membership.get("cancelled_on"):
		frappe.throw(f"{membership.name} is cancelled — no further lifecycle changes.")


def _subscription(membership):
	if membership.get("subscription") and frappe.db.exists("Subscription", membership.subscription):
		return frappe.get_doc("Subscription", membership.subscription)
	return None


def _paid_window(membership) -> dict | None:
	"""The current invoice's period and value — the basis for every credit.

	Returns ``{invoice, from_date, to_date, net_total, days, paid}`` or ``None``
	when nothing has been invoiced yet.
	"""
	si_name = billing.current_invoice(membership)
	if not si_name:
		return None
	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		["name", "from_date", "to_date", "net_total", "outstanding_amount", "docstatus"],
		as_dict=True,
	)
	if not si or si.docstatus != 1 or not (si.from_date and si.to_date):
		return None
	days = (getdate(si.to_date) - getdate(si.from_date)).days + 1
	return {
		"invoice": si.name,
		"from_date": getdate(si.from_date),
		"to_date": getdate(si.to_date),
		"net_total": flt(si.net_total),
		"days": max(days, 1),
		"paid": flt(si.outstanding_amount) <= 0,
	}


def _unused_credit(membership, on_date) -> tuple[float, int]:
	"""(credit amount, unused days) for the current PAID period from ``on_date``."""
	window = _paid_window(membership)
	if not window or not window["paid"]:
		return 0.0, 0
	unused = (window["to_date"] - getdate(on_date)).days + 1
	unused = max(0, min(unused, window["days"]))
	if not unused:
		return 0.0, 0
	credit = flt(window["net_total"] * unused / window["days"], 2)
	return credit, unused


def _grant_system_credit(membership, amount, reason, until) -> None:
	"""Apply a DS-1 discount computed by the engine (cap-exempt).

	Granted as "Until a date" = the day the credited invoice posts: "First
	invoice only" would never fire — this membership's first invoice was already
	spent on the old plan — and anything longer would discount next cycle too.
	"""
	membership.discount_type = "Amount"
	membership.discount_value = amount
	membership.discount_duration = "Until a date"
	membership.discount_until = until
	membership.discount_reason = reason
	frappe.flags.netgainz_system_credit = True
	try:
		membership.save(ignore_permissions=True)
	finally:
		frappe.flags.netgainz_system_credit = False


# --------------------------------------------------------------------------- #
# freeze / unfreeze
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def freeze_membership(membership, from_date, to_date, reason=None) -> dict:
	"""Freeze: push the next bill out by the freeze length. R21: both period
	dates are set here, and nothing is cancelled.

	Obligations already invoiced stand (D3) — a freeze pauses FUTURE billing.
	A Pay-as-you-go membership has no auto-bill to pause; the freeze is recorded
	and the desk simply doesn't invoice a frozen member.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	ms = billing._as_doc("Membership", membership)
	_assert_not_cancelled(ms)
	if trials.is_on_trial(ms):
		frappe.throw("This membership is on a free trial — end or skip the trial first.")

	from_date, to_date = getdate(from_date), getdate(to_date)
	if to_date < from_date:
		frappe.throw("Frozen To cannot be before Frozen From.")

	overlap = frappe.db.exists(
		"Membership Freeze",
		{
			"membership": ms.name,
			"from_date": ["<=", str(to_date)],
			"to_date": [">=", str(from_date)],
		},
	)
	if overlap:
		frappe.throw(f"This membership is already frozen in that window ({overlap}).")

	days = (to_date - from_date).days + 1
	shifted = {"from": None, "to": None}
	sub = _subscription(ms)
	if sub:
		new_start = add_days(getdate(sub.current_invoice_start), days)
		new_end = getdate(add_to_date(new_start, **sub.get_billing_cycle_data()))
		shifted = {"from": str(sub.current_invoice_start), "to": str(new_start)}
		frappe.db.set_value(
			"Subscription",
			sub.name,
			{"current_invoice_start": new_start, "current_invoice_end": new_end},
			update_modified=False,
		)

	freeze = frappe.get_doc(
		{
			"doctype": "Membership Freeze",
			"membership": ms.name,
			"member": ms.member,
			"from_date": from_date,
			"to_date": to_date,
			"days_shifted": days if sub else 0,
			"reason": reason,
		}
	)
	freeze.insert()

	billing.sync_derived_fields(ms)
	return {
		"freeze": freeze.name,
		"days": days,
		"next_bill_moved_from": shifted["from"],
		"next_bill_moved_to": shifted["to"],
	}


@frappe.whitelist()
def unfreeze_membership(freeze, on_date=None) -> dict:
	"""The member is back early: shorten the freeze to end yesterday and shift
	the billing dates back by the days not actually taken."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	frz = frappe.get_doc("Membership Freeze", freeze)
	on_date = getdate(on_date or today())
	if on_date > getdate(frz.to_date):
		frappe.throw("This freeze has already ended.")

	# Days actually frozen: from_date up to the day before the return.
	taken = max(0, (on_date - getdate(frz.from_date)).days)
	give_back = (frz.days_shifted or 0) - taken
	if give_back <= 0:
		return {"freeze": frz.name, "days_returned": 0}

	ms = billing._as_doc("Membership", frz.membership)
	sub = _subscription(ms)
	if sub:
		new_start = add_days(getdate(sub.current_invoice_start), -give_back)
		new_end = getdate(add_to_date(new_start, **sub.get_billing_cycle_data()))
		frappe.db.set_value(
			"Subscription",
			sub.name,
			{"current_invoice_start": new_start, "current_invoice_end": new_end},
			update_modified=False,
		)

	frz.to_date = max(getdate(frz.from_date), add_days(on_date, -1))
	frz.days_shifted = taken
	frz.save(ignore_permissions=True)

	billing.sync_derived_fields(ms)
	return {"freeze": frz.name, "days_returned": give_back}


# --------------------------------------------------------------------------- #
# plan change
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def change_plan(membership, new_plan, new_price=None, change_date=None) -> dict:
	"""Move a membership to another plan, effective now.

	A fresh full cycle of the NEW plan starts on the change date, and the unused
	days of the old, already-paid period come back as a first-invoice credit
	(capped at the new price — a downgrade cannot mint money). One rule for
	upgrades and downgrades; no surcharge path exists or is needed.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	ms = billing._as_doc("Membership", membership)
	_assert_not_cancelled(ms)
	if not frappe.db.exists("Membership Plan", new_plan):
		frappe.throw(f"Membership Plan {new_plan} does not exist.")
	if new_plan == ms.membership_plan:
		frappe.throw("That is already this membership's plan.")

	change_date = getdate(change_date or today())
	on_trial = trials.is_on_trial(ms)
	credit, unused = (0.0, 0) if on_trial else _unused_credit(ms, change_date)

	new_price_val = flt(new_price) if new_price not in (None, "") else None
	effective_new = new_price_val or flt(frappe.db.get_value("Membership Plan", new_plan, "amount"))
	credit = min(credit, effective_new) if effective_new else credit

	old_plan = ms.membership_plan
	ms.membership_plan = new_plan
	ms.tariff = new_price_val
	if credit:
		_grant_system_credit(
			ms,
			credit,
			f"Unused days credit — plan change from {old_plan} ({unused} day(s))",
			until=change_date,
		)
	else:
		ms.save(ignore_permissions=True)

	invoice = None
	sub = _subscription(ms)
	if sub and not on_trial:
		new_sub_plan = frappe.db.get_value(
			"Membership Plan", new_plan, "subscription_plan"
		) or provisioning.provision_subscription_plan(new_plan, sub.company)
		if not new_sub_plan:
			frappe.throw(f"{new_plan} cannot bill yet (no price/tax code) — fix the plan first.")
		sub.plans[0].plan = new_sub_plan
		# The new cycle starts on the change date; the end is ours to set (R21).
		sub.current_invoice_start = change_date
		sub.current_invoice_end = getdate(add_to_date(change_date, **sub.get_billing_cycle_data()))
		sub.save(ignore_permissions=True)
		previous_invoice = billing.current_invoice(ms)
		invoice = billing.force_generate_invoice(ms, posting_date=change_date)
		# Same-day change: the OLD plan's invoice (posted today) sits inside the
		# re-anchored window, so process() dedupes and bills nothing. Generate the
		# new-plan invoice directly and advance the period the way process would.
		if not invoice or invoice == previous_invoice:
			with billing._as_engine():
				sub.reload()
				inv_doc = sub.create_invoice(posting_date=change_date)
				sub.update_subscription_period(add_days(sub.current_invoice_end, 1))
				sub.save(ignore_permissions=True)
			invoice = inv_doc.name
			ms.db_set("current_sales_invoice", invoice, update_modified=False)

	billing.sync_derived_fields(ms)
	return {
		"membership": ms.name,
		"old_plan": old_plan,
		"new_plan": new_plan,
		"credit": credit,
		"unused_days": unused,
		"invoice": invoice,
	}


# --------------------------------------------------------------------------- #
# cancellation
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def cancel_membership(membership, reason=None) -> dict:
	"""Cancel: billing stops today; the refund follows the TENANT's policy.

	"No refund": nothing moves. "Prorated unused days": the unused part of the
	current paid period goes back as real cash through the WP-8 rails — and
	because money leaves the business, that path is owner-only. Unpaid invoices
	stand either way (collect or write off — never silently forgiven).
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	ms = billing._as_doc("Membership", membership)
	_assert_not_cancelled(ms)

	td = getdate(today())
	refund_amount, unused = 0.0, 0
	if _refund_policy() == REFUND_POLICY_PRORATED and not trials.is_on_trial(ms):
		refund_amount, unused = _unused_credit(ms, td)
		if refund_amount > 0:
			permissions.require_role(permissions.GYM_OWNER)

	sub = _subscription(ms)
	if sub and sub.status != "Cancelled":
		with billing._as_engine():
			sub.cancel_subscription()

	ms.db_set("cancelled_on", td, update_modified=False)
	ms.db_set("next_renewal", None, update_modified=False)
	if reason:
		ms.db_set("cancellation_reason", reason, update_modified=False)

	refund_result = None
	if refund_amount > 0:
		refund_result = refunds.refund_membership(
			ms,
			amount=refund_amount,
			reason=f"Cancellation refund — {unused} unused day(s)",
			return_cash=True,
		)

	billing.sync_derived_fields(ms)
	return {
		"membership": ms.name,
		"cancelled_on": str(td),
		"refund_policy": _refund_policy(),
		"refund_amount": refund_amount,
		"refund": refund_result,
	}


# --------------------------------------------------------------------------- #
# transfer
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def transfer_membership(membership, to_member) -> dict:
	"""Move a membership to a family member: cancel the old one (no cash out)
	and start a new one for the receiver carrying the remaining paid value as a
	first-invoice credit. Branch transfer parks until Stage 11."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	ms = billing._as_doc("Membership", membership)
	_assert_not_cancelled(ms)
	if trials.is_on_trial(ms):
		frappe.throw("A trial has nothing to transfer — enrol the family member directly.")
	if not frappe.db.exists("Member", to_member):
		frappe.throw(f"Member {to_member} does not exist.")
	if to_member == ms.member:
		frappe.throw("That is already this membership's member.")
	live = frappe.db.get_value(
		"Membership",
		{
			"member": to_member,
			"status": ["in", list(LIVE_STATUSES)],
			"cancelled_on": ["is", "not set"],
		},
		"name",
	)
	if live:
		frappe.throw(
			f"{to_member} already has a live membership ({live}) — cancel or change that one instead."
		)

	td = getdate(today())
	credit, unused = _unused_credit(ms, td)

	from_name = ms.member_name or ms.member
	sub = _subscription(ms)
	if sub and sub.status != "Cancelled":
		with billing._as_engine():
			sub.cancel_subscription()
	ms.db_set("cancelled_on", td, update_modified=False)
	ms.db_set("next_renewal", None, update_modified=False)
	ms.db_set("cancellation_reason", f"Transferred to {to_member}", update_modified=False)
	billing.sync_derived_fields(ms)

	price = flt(frappe.db.get_value("Membership Plan", ms.membership_plan, "amount"))
	if ms.get("tariff"):
		price = flt(ms.tariff)
	credit = min(credit, price) if price else credit

	new_ms = frappe.new_doc("Membership")
	new_ms.member = to_member
	new_ms.membership_plan = ms.membership_plan
	new_ms.tariff = ms.get("tariff")
	if credit:
		new_ms.discount_type = "Amount"
		new_ms.discount_value = credit
		new_ms.discount_duration = "First invoice only"
		new_ms.discount_reason = f"Transfer credit from {ms.name} ({from_name}, {unused} day(s))"
	frappe.flags.netgainz_system_credit = True
	try:
		new_ms.insert(ignore_permissions=True)
	finally:
		frappe.flags.netgainz_system_credit = False

	return {
		"old_membership": ms.name,
		"new_membership": new_ms.name,
		"to_member": to_member,
		"credit": credit,
		"unused_days": unused,
	}
