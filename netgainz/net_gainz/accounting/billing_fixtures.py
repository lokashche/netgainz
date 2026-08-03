# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Shared TEST fixtures for building real billing data (WP-11).

Not imported by production code — this exists so every test module creates revenue
the way the application actually does: Member -> Membership -> native Subscription
-> Sales Invoice -> Payment Entry.

Before WP-11 the Profit First / commission tests fabricated revenue by setting
``Membership.fee_collected`` directly. That field now feeds no calculation (cash is
read from Payment Entries only), so those fixtures would silently produce ZERO
revenue and the tests would assert against nothing. Use :func:`enrol_and_collect`.

**Amounts are ex-GST.** The plan's ``amount`` becomes the invoice ``net_total``;
any GST rides on top in ``grand_total``. ``billing.collected_paise`` scales each
allocation by ``net_total / grand_total``, so collecting a full invoice contributes
exactly the plan amount to the cash read — which is what the assertions expect.

The module name deliberately avoids the ``test_*`` prefix so Frappe's test runner
does not collect it as a test module.
"""

import itertools

import frappe
from frappe.utils import flt, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.profit_first import accounts as pf_accounts

# Fitness SAC — exists as a GST HSN Code; india_compliance makes it mandatory on a
# sellable Item, so every test plan needs one.
SAC = "999723"

# Monotonic across the whole test process. Masters (Membership Plan, Member, Item)
# are NOT cleared between tests — only billing artefacts are — and `make_plan` is
# idempotent by name, so a reused tag would silently return an EARLIER test's plan
# at ITS amount and the assertion would measure the wrong revenue. Unique names per
# call remove that class of bug entirely.
_SEQ = itertools.count(1)


def clear_billing_data() -> None:
	"""Delete every billing artefact so a test starts from a known-zero slate.

	Needed because a **submitted** Payment Entry survives FrappeTestCase's per-test
	rollback, so revenue created by one test would leak into the next — and the
	Profit First reads are global (``get_instant_assessment`` cannot be scoped to a
	member). Mirrors the existing ``frappe.db.delete("Membership")`` slate-clearing.
	Child tables first, then parents.
	"""
	for doctype in (
		"Payment Entry Reference",
		"Payment Entry",
		"Sales Invoice Item",
		"Sales Invoice",
		"Subscription Plan Detail",
		"Subscription",
		"Membership",
	):
		frappe.db.delete(doctype)


def ensure_cash_account(company=None) -> str | None:
	"""``record_payment`` needs a deposit account for the Cash mode. Idempotent."""
	company = company or pf_accounts.default_company()
	if not company:
		return None
	existing = frappe.db.get_value("Company", company, "default_cash_account")
	if existing:
		return existing
	cash = frappe.db.get_value(
		"Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name"
	)
	if cash:
		frappe.db.set_value("Company", company, "default_cash_account", cash)
	return cash


def make_plan(name, amount=1000.0, duration=30):
	"""A Membership Plan (auto-provisions Item + Item Price + Subscription Plan).

	If the plan already exists its ``amount`` is re-synced, so a caller can never
	silently bill at some other test's price."""
	if frappe.db.exists("Membership Plan", name):
		plan = frappe.get_doc("Membership Plan", name)
		if flt(plan.amount) != flt(amount):
			plan.amount = amount
			plan.save(ignore_permissions=True)  # re-syncs the Item Price
		return plan
	return frappe.get_doc(
		{
			"doctype": "Membership Plan",
			"plan_name": name,
			"duration_in_days": duration,
			"amount": amount,
			"gst_hsn_code": SAC,
		}
	).insert(ignore_permissions=True)


def make_member(name, plan=None):
	"""A Member (auto-provisions the ERPNext Customer)."""
	return frappe.get_doc(
		{"doctype": "Member", "full_name": name, "membership_plan": plan}
	).insert(ignore_permissions=True)


def enrol(tag, amount=1000.0, duration=30):
	"""Enrol a fresh member on a fresh plan; returns the reloaded Membership.

	``after_insert`` provisions the Subscription and bills the first prepaid period,
	so the returned membership already carries ``subscription`` +
	``current_sales_invoice``. ``tag`` is suffixed with a process-unique sequence so
	repeated calls can never collide on a master's name.
	"""
	tag = f"{tag}-{next(_SEQ)}"
	plan = make_plan(f"{tag} Plan", amount=amount, duration=duration)
	member = make_member(f"{tag} Member", plan.name)
	ms = frappe.get_doc(
		{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
	).insert(ignore_permissions=True)
	ms.reload()
	return ms


def collect(membership, amount=None, posting_date=None, payment_mode="Cash") -> str:
	"""Record a Payment Entry against the membership's open invoice.

	``amount`` defaults to the invoice's full outstanding (so the ex-GST cash
	recognised equals the plan amount).
	"""
	ensure_cash_account()
	if amount is None:
		amount = flt(
			frappe.db.get_value("Sales Invoice", membership.current_sales_invoice, "outstanding_amount")
		)
	return billing.record_membership_payment(
		membership.name, amount, payment_mode=payment_mode, posting_date=posting_date or today()
	)["payment_entry"]


def enrol_and_collect(tag, amount=1000.0, posting_date=None, duration=30):
	"""The one-liner most tests want: a member who has PAID ``amount`` (ex-GST).

	Returns the reloaded Membership. Contributes exactly ``amount`` to
	``billing.membership_collected_paise`` for a window containing ``posting_date``.
	"""
	ms = enrol(tag, amount=amount, duration=duration)
	collect(ms, posting_date=posting_date)
	ms.reload()
	return ms
