# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-4: real billing on ERPNext Sales Invoices + Payment Entries.

Each membership drives ONE native ERPNext Subscription (prepaid: an invoice is
generated at the start of each period); each collection is a Payment Entry against
that period's Sales Invoice. Profit First and commissions then read COLLECTED CASH
from Payment Entries, never from the invoice (cash basis), via the single shared
read :func:`membership_collected_paise`.

**WP-11 (fresh-start): ERPNext billing is ON for every membership, always.** There
was never any production data — no tenant ever set a cut-over date, and no Sales
Invoice, Payment Entry or Subscription was ever created — so the date-gated
cut-over and its dual cash read (legacy ``fee_collected`` + Payment Entries) were
deleted rather than migrated. One path, one source of truth: cash is what a
submitted Payment Entry allocated to a subscription-generated Sales Invoice.
``Membership.fee_collected`` / ``tariff`` survive only as deprecated display
fields and feed NO calculation; payments post exclusively through
:func:`record_payment`.

Design conventions mirror provisioning.py / payment_modes.py: idempotent,
best-effort (skip — never block the save — when a prerequisite is missing),
``ignore_permissions=True``, and reuse of the existing helpers
(``pf_accounts.default_company``, ``branch.branch_cost_center``,
``payment_modes.paid_to_account``, ``period_lock.assert_postable``,
``calc.to_paise``/``to_rupees``).
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import branch, payment_modes, period_lock, provisioning
from netgainz.net_gainz.profit_first import accounts as pf_accounts
from netgainz.net_gainz.profit_first import calc

GENERATE_INVOICE_AT = "Beginning of the current subscription period"  # prepaid


# --------------------------------------------------------------------------- #
# config / helpers
# --------------------------------------------------------------------------- #
def _as_doc(doctype, ref) -> Document:
	return ref if isinstance(ref, Document) else frappe.get_doc(doctype, ref)


def _company(company=None):
	return company or pf_accounts.default_company()


# --------------------------------------------------------------------------- #
# Membership -> native Subscription -> Sales Invoice
# --------------------------------------------------------------------------- #
def ensure_subscription(membership, company=None) -> str | None:
	"""Idempotently create the native ERPNext Subscription for a membership and
	link it back. Returns its name, or None if a prerequisite is missing."""
	membership = _as_doc("Membership", membership)
	if membership.get("subscription") and frappe.db.exists("Subscription", membership.subscription):
		return membership.subscription

	company = _company(company)
	if not company or not membership.get("member") or not membership.get("membership_plan"):
		return None

	customer = frappe.db.get_value("Member", membership.member, "customer") or provisioning.provision_customer(
		membership.member, company
	)
	if not customer:
		return None
	sub_plan = frappe.db.get_value(
		"Membership Plan", membership.membership_plan, "subscription_plan"
	) or provisioning.provision_subscription_plan(membership.membership_plan, company)
	if not sub_plan:
		return None

	# WP-11: no cut-over to floor against — billing is on from day one. (WP-10.0
	# will re-anchor this to Member.date_of_joining.)
	start = getdate(today())

	sub = frappe.new_doc("Subscription")
	sub.party_type = "Customer"
	sub.party = customer
	sub.company = company
	sub.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	sub.start_date = start
	sub.generate_invoice_at = GENERATE_INVOICE_AT
	sub.submit_invoice = 1
	sub.days_until_due = frappe.db.get_single_value("Business Settings", "days_until_due") or 0
	sub.append("plans", {"plan": sub_plan, "qty": 1})
	sub.insert(ignore_permissions=True)

	membership.db_set("subscription", sub.name, update_modified=False)
	return sub.name


def _latest_invoice(subscription_name) -> str | None:
	return frappe.db.get_value(
		"Sales Invoice",
		{"subscription": subscription_name, "docstatus": ["!=", 2]},
		"name",
		order_by="creation desc",
	)


def force_generate_invoice(membership, posting_date=None) -> str | None:
	"""Generate the current period's Sales Invoice now (the prepaid first invoice,
	or an owner-triggered catch-up). Uses native ``Subscription.process`` so it
	dedupes per period; links the resulting invoice back to the membership."""
	membership = _as_doc("Membership", membership)
	sub_name = membership.get("subscription")
	if not sub_name or not frappe.db.exists("Subscription", sub_name):
		return None
	sub = frappe.get_doc("Subscription", sub_name)
	sub.process(getdate(posting_date) if posting_date else getdate(today()))
	invoice = _latest_invoice(sub_name)
	if invoice:
		membership.db_set("current_sales_invoice", invoice, update_modified=False)
	return invoice


def on_membership_insert(doc, method=None):
	"""``after_insert`` doc_event: stand up the Subscription and bill the first
	(prepaid) period. Best-effort — never blocks the membership save (a billing
	hiccup must not fail member enrolment; the owner can retry via
	generate_membership_invoice)."""
	if frappe.flags.in_install:
		return
	try:
		if ensure_subscription(doc):
			force_generate_invoice(doc)
			sync_derived_fields(doc)
	except Exception:
		frappe.log_error(title=f"WP-4 billing provisioning failed for membership {doc.name}")


def on_sales_invoice_submit(doc, method=None):
	"""``on_submit`` doc_event for Sales Invoice: when the native daily Process
	Subscription scheduler bills a new membership period, re-point the membership's
	``current_sales_invoice`` at the freshly generated invoice, so renewal payments
	collect against the right SI and status reflects the current period."""
	if frappe.flags.in_install or not doc.get("subscription"):
		return
	membership = frappe.db.get_value("Membership", {"subscription": doc.subscription}, "name")
	if membership:
		frappe.db.set_value("Membership", membership, "current_sales_invoice", doc.name, update_modified=False)


# --------------------------------------------------------------------------- #
# payments -> Payment Entry
# --------------------------------------------------------------------------- #
def record_payment(
	membership, amount, payment_mode, posting_date, sales_invoice=None, reference_no=None, company=None
) -> str:
	"""Record a member payment as a submitted Payment Entry against the membership's
	Sales Invoice. ``posting_date`` is REQUIRED (R3 — cash counts when collected)."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	membership = _as_doc("Membership", membership)
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	if not posting_date:
		frappe.throw("A posting date is required to record a payment.")
	posting_date = getdate(posting_date)
	period_lock.assert_postable(posting_date, company)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw("Payment amount must be greater than zero.")

	# Prefer the subscription's latest OPEN invoice over a (possibly stale)
	# current_sales_invoice — the scheduler bills later periods without re-pointing
	# it, so a paid period-1 SI must not shadow an open period-2 SI on renewal.
	si_name = sales_invoice
	if not si_name and membership.get("subscription"):
		si_name = frappe.db.get_value(
			"Sales Invoice",
			{"subscription": membership.subscription, "docstatus": 1, "outstanding_amount": [">", 0]},
			"name",
			order_by="posting_date desc",
		)
	si_name = si_name or membership.get("current_sales_invoice")
	if not si_name or not frappe.db.exists("Sales Invoice", si_name):
		frappe.throw("No open Sales Invoice to record this payment against — generate the invoice first.")

	outstanding = flt(frappe.db.get_value("Sales Invoice", si_name, "outstanding_amount"))
	if amount > outstanding:
		frappe.throw(
			f"Payment {amount} exceeds the invoice outstanding {outstanding}. "
			"Overpayments / advances are not supported yet."
		)

	pe = get_payment_entry("Sales Invoice", si_name)
	pe.payment_type = "Receive"
	pe.posting_date = posting_date
	pe.reference_date = posting_date
	if payment_mode:
		pe.mode_of_payment = payment_mode
		pe.paid_to = payment_modes.paid_to_account(company, payment_mode)
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	if reference_no:
		pe.reference_no = reference_no
	for ref in pe.references:
		ref.allocated_amount = amount if ref.reference_name == si_name else 0
	pe.insert(ignore_permissions=True)
	pe.submit()

	membership.db_set("current_sales_invoice", si_name, update_modified=False)
	return pe.name


# --------------------------------------------------------------------------- #
# derived membership state (R4: one source of truth = invoice outstanding)
# --------------------------------------------------------------------------- #
def sync_from_invoice(membership) -> None:
	"""Set status / balance_due / due_date / next_renewal on a membership from its
	current Sales Invoice's outstanding_amount + the Subscription period. Operates
	in-memory (controller calls it in before_save); never infers CASH from
	outstanding (write-offs zero outstanding without collecting).

	A no-op when billing has not been provisioned yet — provisioning is best-effort
	and must never block enrolment, so a membership can briefly exist without an
	invoice."""
	# Anchor to the CURRENT period's invoice (the subscription's latest), not a
	# stale current_sales_invoice — else a renewal period's open SI is missed and
	# the membership wrongly reports Paid.
	si_name = None
	if membership.get("subscription"):
		si_name = _latest_invoice(membership.subscription)
	si_name = si_name or membership.get("current_sales_invoice")
	if not si_name or not frappe.db.exists("Sales Invoice", si_name):
		return
	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		["outstanding_amount", "grand_total", "status", "due_date"],
		as_dict=True,
	)
	membership.current_sales_invoice = si_name
	membership.balance_due = si.outstanding_amount
	# WP-11: due_date is invoice-derived, never hand-typed (it also drives
	# overdue_days on the controller). WP-10 will re-derive it from the earliest
	# unpaid payment-schedule row once installments exist.
	if si.due_date:
		membership.due_date = getdate(si.due_date)
	if flt(si.outstanding_amount) <= 0:
		membership.status = "Paid"
	elif si.status == "Overdue" or (si.due_date and getdate(today()) > getdate(si.due_date)):
		membership.status = "Overdue"
	elif flt(si.outstanding_amount) < flt(si.grand_total):
		membership.status = "Partial"
	else:
		membership.status = "Pending"

	if membership.get("subscription") and frappe.db.exists("Subscription", membership.subscription):
		# Prepaid: the next charge falls on the next period's START, which the
		# Subscription has already advanced current_invoice_start to once the
		# current period's invoice was generated.
		start = frappe.db.get_value("Subscription", membership.subscription, "current_invoice_start")
		if start:
			membership.next_renewal = getdate(start)


def sync_derived_fields(membership) -> None:
	"""Re-derive AND persist status / balance_due / due_date / next_renewal.

	``sync_from_invoice`` runs from the controller's ``before_save``, but a
	membership's Subscription and first invoice are provisioned in ``after_insert``
	— i.e. after that hook has already run. Without this a freshly enrolled
	membership would keep empty derived fields until something saved it again.
	Writes with ``db_set`` rather than ``save()`` so the just-inserted document is
	not re-validated (and cannot trip a modified-timestamp conflict)."""
	membership = _as_doc("Membership", membership)
	sync_from_invoice(membership)
	membership.calculate_overdue_days()
	for field in (
		"current_sales_invoice",
		"status",
		"balance_due",
		"due_date",
		"next_renewal",
		"overdue_days",
	):
		value = membership.get(field)
		if value is not None:
			membership.db_set(field, value, update_modified=False)


# --------------------------------------------------------------------------- #
# the shared cash read (R1/R2): collected cash from Payment Entries
# --------------------------------------------------------------------------- #
def _members_to_customers(members):
	"""Translate Member names -> their ERPNext Customer names (drops members with
	no Customer yet). None in -> None out (no party scoping)."""
	if members is None:
		return None
	return [c for m in members if (c := frappe.db.get_value("Member", m, "customer"))]


def collected_paise(start, end, customers=None) -> int:
	"""Membership REVENUE collected in [start, end], from Payment Entries, in
	integer paise.

	Allocation-anchored: sums each Payment Entry Reference.allocated_amount for
	submitted Receive PEs whose Sales Invoice was subscription-generated (a
	membership invoice). This excludes advances/unallocated cash, non-membership
	income, capital injections, transfers and refunds by construction.

	Each allocation is scaled by ``net_total / grand_total`` so only the **ex-GST**
	portion counts — GST collected is a pass-through liability, not revenue, and PF
	must allocate real revenue. For a non-GST tenant grand_total == net_total, so the
	scale is 1 and it is a no-op. Single-currency (the SI document currency)."""
	if customers is not None and not customers:
		return 0
	params = {"start": getdate(start), "end": getdate(end)}
	party_clause = ""
	if customers is not None:
		party_clause = "AND pe.party IN %(customers)s"
		params["customers"] = tuple(customers)
	rows = frappe.db.sql(
		f"""
		SELECT per.allocated_amount * si.net_total / si.grand_total AS amt
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name
		WHERE pe.docstatus = 1
		  AND pe.payment_type = 'Receive'
		  AND pe.posting_date BETWEEN %(start)s AND %(end)s
		  AND per.reference_doctype = 'Sales Invoice'
		  AND si.subscription IS NOT NULL AND si.subscription != ''
		  AND si.grand_total > 0
		  {party_clause}
		""",
		params,
		as_dict=True,
	)
	return sum(calc.to_paise(r.amt) for r in rows)


def membership_collected_paise(start, end, members=None) -> int:
	"""THE shared cash read for Profit First + commissions (integer paise).

	WP-11: a single Payment-Entry read. Every membership bills through ERPNext, so
	collected cash is always the ex-GST allocation of a submitted Receive Payment
	Entry against a subscription-generated Sales Invoice — never
	``Membership.fee_collected``, which is a deprecated display field feeding no
	calculation. ``members`` (Member names) optionally scopes the total, translated
	to the members' Customers."""
	return collected_paise(start, end, _members_to_customers(members))


# --------------------------------------------------------------------------- #
# whitelisted owner / BFF entry points
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def record_membership_payment(membership, amount, payment_mode=None, posting_date=None, reference_no=None) -> dict:
	"""Owner/BFF: record a payment; returns the Payment Entry + remaining outstanding."""
	pe = record_payment(membership, amount, payment_mode, posting_date or today(), reference_no=reference_no)
	si = frappe.db.get_value("Membership", membership, "current_sales_invoice")
	outstanding = flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount")) if si else 0
	return {"payment_entry": pe, "outstanding": outstanding}


@frappe.whitelist()
def generate_membership_invoice(membership, posting_date=None) -> dict:
	"""Owner/BFF: bill the current period now. Provisions the Subscription first."""
	company = _company()
	ensure_subscription(membership, company)
	invoice = force_generate_invoice(membership, posting_date)
	return {"sales_invoice": invoice}


@frappe.whitelist()
def provision_membership_subscription(membership) -> dict:
	"""Owner: stand up the Subscription for an existing membership (pilot cut-over)."""
	return {"subscription": ensure_subscription(membership)}
