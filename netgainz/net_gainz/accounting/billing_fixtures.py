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
	# WP-8: a write-off is a submitted Journal Entry, which likewise survives the
	# per-test rollback. Only OUR voucher type is cleared, so PF sweep / commission
	# journals in other suites are left alone.
	writeoffs = frappe.get_all("Journal Entry", filters={"voucher_type": "Write Off Entry"}, pluck="name")
	if writeoffs:
		frappe.db.delete("Journal Entry Account", {"parent": ["in", writeoffs]})
		frappe.db.delete("Journal Entry", {"name": ["in", writeoffs]})


def ensure_cash_account(company=None) -> str | None:
	"""``record_payment`` needs a deposit account for the Cash mode. Idempotent."""
	company = company or pf_accounts.default_company()
	if not company:
		return None
	existing = frappe.db.get_value("Company", company, "default_cash_account")
	if existing:
		return existing
	cash = frappe.db.get_value("Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name")
	if cash:
		frappe.db.set_value("Company", company, "default_cash_account", cash)
	return cash


def make_plan(
	name,
	amount=1000.0,
	duration=30,
	plan_type="Monthly",
	billing_mode="Commitment",
	due_rule="On joining",
	parts=1,
	gap_days=30,
	gap_unit="Days",
):
	"""A Membership Plan (auto-provisions Item + Item Price + Subscription Plan).

	``plan_type`` drives ``duration_in_days`` via the controller; pass ``"Custom"``
	with an explicit ``duration`` for a non-standard cadence. If the plan already
	exists its ``amount`` is re-synced, so a caller can never silently bill at some
	other test's price."""
	if frappe.db.exists("Membership Plan", name):
		plan = frappe.get_doc("Membership Plan", name)
		plan.amount = amount
		# Always re-save, even when the amount already matches: the save is what
		# re-runs provisioning, and ERPNext's own before_tests DELETES every Item
		# Price. A plan left over from an earlier run would otherwise resolve at
		# rate 0 through "Based On Price List" and quietly bill nothing, so every
		# assertion downstream would measure an empty invoice.
		plan.save(ignore_permissions=True)
		return plan
	doc = {
		"doctype": "Membership Plan",
		"plan_name": name,
		"plan_type": plan_type,
		"billing_mode": billing_mode,
		"amount": amount,
		"gst_hsn_code": SAC,
		"payment_due_rule": due_rule,
		"installment_count": parts,
		"installment_gap_days": gap_days,
		"installment_gap_unit": gap_unit,
	}
	# Mirror the owner app: the day count is set BY the cadence, and is only
	# supplied directly for a Custom plan. Sending both would make the controller
	# infer the cadence from the duration and override the plan_type asked for.
	if plan_type == "Custom":
		doc["duration_in_days"] = duration
	return frappe.get_doc(doc).insert(ignore_permissions=True)


def make_member(name, plan=None, date_of_joining=None):
	"""A Member (auto-provisions the ERPNext Customer)."""
	doc = {"doctype": "Member", "full_name": name, "membership_plan": plan}
	if date_of_joining:
		doc["date_of_joining"] = date_of_joining
	return frappe.get_doc(doc).insert(ignore_permissions=True)


def enrol(tag, amount=1000.0, duration=30, date_of_joining=None, **plan_kwargs):
	"""Enrol a fresh member on a fresh plan; returns the reloaded Membership.

	``after_insert`` provisions the Subscription and bills the first prepaid period,
	so the returned membership already carries ``subscription`` +
	``current_sales_invoice``. ``tag`` is suffixed with a process-unique sequence so
	repeated calls can never collide on a master's name. Extra keyword arguments
	(``plan_type``, ``billing_mode``, ``due_rule``, ``parts``, ``gap_days``,
	``gap_unit``) go straight to :func:`make_plan`.
	"""
	tag = f"{tag}-{next(_SEQ)}"
	plan = make_plan(f"{tag} Plan", amount=amount, duration=duration, **plan_kwargs)
	member = make_member(f"{tag} Member", plan.name, date_of_joining=date_of_joining)
	ms = frappe.get_doc(
		{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
	).insert(ignore_permissions=True)
	ms.reload()
	assert_billing_provisioned(ms)
	return ms


def assert_billing_provisioned(membership) -> None:
	"""Fail HERE, with the reason, when enrolment produced no invoice.

	Enrolment is deliberately best-effort in production: `on_membership_insert`
	swallows exceptions into the Error Log, and `ensure_subscription` returns None
	on a missing prerequisite without raising at all. A billing hiccup must never
	block a gym signing someone up.

	In a test that same silence is poison. A membership with no invoice makes every
	later assertion measure an empty invoice — and several of them still pass, so
	the suite reports green while proving nothing. The three CI failures that
	prompted this raised "payment must be greater than zero" and "no invoice to
	write off" from three frames away, naming neither the missing prerequisite nor
	the module that was actually broken.

	So each prerequisite is re-checked in the same order `ensure_subscription` uses,
	and the swallowed Error Log is quoted if one was written.
	"""
	membership.reload()
	if membership.get("current_sales_invoice"):
		return

	company = pf_accounts.default_company()
	plan = membership.get("membership_plan")
	reasons = []
	if not company:
		reasons.append("no default Company (Global Defaults / Business Settings)")
	if not frappe.db.get_value("Member", membership.member, "customer"):
		reasons.append("the Member has no ERPNext Customer")
	if plan:
		if not frappe.db.get_value("Membership Plan", plan, "item"):
			reasons.append("the plan has no Item (a missing HSN/SAC code skips provisioning)")
		if not frappe.db.get_value("Membership Plan", plan, "subscription_plan"):
			reasons.append("the plan has no Subscription Plan")
	if not billing.is_billable(membership):
		reasons.append("no price resolves for this membership")
	if not membership.get("subscription"):
		reasons.append("no Subscription was created")

	logged = frappe.get_all(
		"Error Log",
		filters={"method": ["like", f"%{membership.name}%"]},
		fields=["error"],
		order_by="creation desc",
		limit=1,
	)
	detail = f"\n\nSwallowed error:\n{logged[0].error}" if logged else ""
	raise AssertionError(
		f"Membership {membership.name} enrolled but was never billed — "
		f"every assertion after this would measure an empty invoice.\n"
		f"Prerequisites missing: {'; '.join(reasons) or 'none found (see the log below)'}"
		f"{detail}"
	)


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


def enrol_and_collect(tag, amount=1000.0, posting_date=None, duration=30, **plan_kwargs):
	"""The one-liner most tests want: a member who has PAID ``amount`` (ex-GST).

	Returns the reloaded Membership. Contributes exactly ``amount`` to
	``billing.membership_collected_paise`` for a window containing ``posting_date``.
	"""
	ms = enrol(tag, amount=amount, duration=duration, **plan_kwargs)
	collect(ms, posting_date=posting_date)
	ms.reload()
	return ms
