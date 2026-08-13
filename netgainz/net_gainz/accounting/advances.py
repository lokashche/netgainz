# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-8: partial payments, advances and on-account money.

Members do not pay in tidy invoice-sized amounts. Three cases, one rule:

* **Partial payment** — less than what is owed. Already handled: the Payment Entry
  allocates oldest-installment-first (``billing._allocate_oldest_first``) and the
  membership reads Partial/Overdue off what is left.
* **Overpayment** — more than this period's invoice. The excess is not revenue for
  a period that has not been billed yet; it sits on the member's account as
  ``unallocated_amount`` on the same Payment Entry.
* **Advance / on-account** — money handed over with no invoice at all ("here's
  three months up front", a joining deposit). A Payment Entry with a party and no
  references.

**The recognition rule (WP-8).** Profit First counts a rupee as membership revenue
when a Payment Entry *allocates* it to a membership invoice, and it counts on the
PAYMENT'S OWN posting date — the day the cash actually arrived. Unapplied money is
deliberately NOT revenue: it is a liability the gym could still have to hand back.
The consequence, verified on the dev site, is that applying an advance makes cash
appear in the period it was RECEIVED, not the period it was applied:

    advance of 5,000 received 8 Aug, applied 9 Aug to a 1,770 invoice
    -> Profit First for 8 Aug rises by 1,500 (the ex-GST slice), 9 Aug unchanged.

That is the honest answer — the owner banked the money on the 8th — but it means a
sweep already posted over that period now reads differently, so every entry point
here returns a warning when it happens rather than letting the owner find out at
the next sweep.

Mechanics are entirely native: ERPNext's **Payment Reconciliation** doctype is what
applies unallocated cash to an invoice (traced 2026-08-08: PE unallocated 5,000 ->
3,230, a 1,770 reference row appears, invoice outstanding -> 0).
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate, today

from netgainz.net_gainz.accounting import branch, currency, payment_modes, period_lock
from netgainz.net_gainz.profit_first import accounts as pf_accounts


def _company(company=None):
	return company or pf_accounts.default_company()


def _customer(member_or_membership) -> str | None:
	"""Resolve a Member or Membership name to its ERPNext Customer."""
	name = member_or_membership
	if frappe.db.exists("Membership", name):
		name = frappe.db.get_value("Membership", name, "member")
	return frappe.db.get_value("Member", name, "customer") if name else None


def _receivable_account(customer, company) -> str | None:
	return frappe.db.get_value(
		"Party Account", {"parent": customer, "parenttype": "Customer", "company": company}, "account"
	) or frappe.get_cached_value("Company", company, "default_receivable_account")


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
def advance_balance(member_or_membership, company=None) -> float:
	"""Money this member has paid that is not yet applied to any invoice."""
	customer = _customer(member_or_membership)
	if not customer:
		return 0.0
	company = _company(company)
	return flt(
		frappe.db.get_value(
			"Payment Entry",
			{
				"docstatus": 1,
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": customer,
				"company": company,
			},
			"sum(unallocated_amount)",
		)
	)


def open_advances(member_or_membership, company=None) -> list[dict]:
	"""The member's unapplied Payment Entries, oldest first."""
	customer = _customer(member_or_membership)
	if not customer:
		return []
	rows = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": customer,
			"company": _company(company),
			"unallocated_amount": [">", 0],
		},
		fields=["name", "posting_date", "paid_amount", "unallocated_amount", "mode_of_payment"],
		order_by="posting_date asc, creation asc",
		limit_page_length=0,
	)
	return [
		{
			"payment_entry": r.name,
			"posting_date": str(r.posting_date),
			"paid_amount": flt(r.paid_amount),
			"unapplied": flt(r.unallocated_amount),
			"payment_mode": r.mode_of_payment,
		}
		for r in rows
	]


# --------------------------------------------------------------------------- #
# taking money with no invoice to point it at
# --------------------------------------------------------------------------- #
def record_advance(
	member_or_membership, amount, payment_mode=None, posting_date=None, reference_no=None, company=None
) -> str:
	"""Take money on account: a submitted Receive Payment Entry with no references.

	Used when a member pays before their period is billed, pays for several periods
	at once, or leaves a deposit. The money is real (it is in the gym's bank) but it
	is not membership revenue until it is applied — see the module docstring.
	"""
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	currency.assert_paise_safe(company)

	customer = _customer(member_or_membership)
	if not customer:
		frappe.throw("This member has no billing account yet — save the member first.")
	currency.assert_membership_billing_currency(customer, company)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw("The amount must be greater than zero.")
	if not posting_date:
		frappe.throw("A posting date is required to record a payment.")
	posting_date = getdate(posting_date)
	period_lock.assert_postable(posting_date, company)

	receivable = _receivable_account(customer, company)
	if not receivable:
		frappe.throw(f"No receivable account is set for {company}.")

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = company
	pe.posting_date = posting_date
	pe.reference_date = posting_date
	pe.party_type = "Customer"
	pe.party = customer
	pe.paid_from = receivable
	pe.paid_to = payment_modes.paid_to_account(company, payment_mode) if payment_mode else None
	if not pe.paid_to:
		pe.paid_to = frappe.get_cached_value(
			"Company", company, "default_cash_account"
		) or frappe.get_cached_value("Company", company, "default_bank_account")
	if not pe.paid_to:
		frappe.throw(f"No cash or bank account is set for {company} to deposit this into.")
	if payment_mode:
		pe.mode_of_payment = payment_mode
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.cost_center = branch.branch_cost_center(None, company)
	if reference_no:
		pe.reference_no = reference_no
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


# --------------------------------------------------------------------------- #
# applying it
# --------------------------------------------------------------------------- #
def apply_advances(member_or_membership, company=None, limit_to_invoice=None) -> dict:
	"""Apply this member's unapplied cash to their open membership invoices.

	Oldest money to oldest invoice, via ERPNext's own Payment Reconciliation, so
	the resulting allocations are indistinguishable from a payment made against the
	invoice directly — which is exactly what Profit First then reads.

	Returns ``{applied, allocations, warnings}``; a no-op (``applied = 0``) when
	there is nothing on account or nothing open.
	"""
	company = _company(company)
	customer = _customer(member_or_membership)
	if not customer or not company:
		return {"applied": 0.0, "allocations": [], "warnings": []}

	if not open_advances(member_or_membership, company):
		return {"applied": 0.0, "allocations": [], "warnings": []}

	receivable = _receivable_account(customer, company)
	pr = frappe.new_doc("Payment Reconciliation")
	pr.flags.ignore_permissions = True
	pr.company = company
	pr.party_type = "Customer"
	pr.party = customer
	pr.receivable_payable_account = receivable
	pr.get_unreconciled_entries()
	if not pr.payments or not pr.invoices:
		return {"applied": 0.0, "allocations": [], "warnings": []}

	invoices = [
		inv
		for inv in pr.invoices
		if inv.invoice_type == "Sales Invoice"
		and (not limit_to_invoice or inv.invoice_number == limit_to_invoice)
		and _is_membership_invoice(inv.invoice_number)
	]
	if not invoices:
		return {"applied": 0.0, "allocations": [], "warnings": []}

	allocations = []
	remaining = {inv.invoice_number: flt(inv.outstanding_amount) for inv in invoices}
	for payment in pr.payments:
		available = flt(payment.amount)
		for inv in invoices:
			if available <= 0:
				break
			take = min(available, remaining.get(inv.invoice_number, 0))
			if take <= 0:
				continue
			pr.append(
				"allocation",
				{
					"reference_type": payment.reference_type,
					"reference_name": payment.reference_name,
					"invoice_type": inv.invoice_type,
					"invoice_number": inv.invoice_number,
					"allocated_amount": take,
					"unreconciled_amount": payment.amount,
					"amount": payment.amount,
				},
			)
			allocations.append(
				{
					"payment_entry": payment.reference_name,
					"sales_invoice": inv.invoice_number,
					"amount": take,
					"received_on": str(getdate(payment.posting_date)) if payment.get("posting_date") else None,
				}
			)
			remaining[inv.invoice_number] -= take
			available -= take

	if not allocations:
		return {"applied": 0.0, "allocations": [], "warnings": []}

	pr.reconcile()
	return {
		"applied": flt(sum(a["amount"] for a in allocations)),
		"allocations": allocations,
		"warnings": _recognition_warnings(allocations),
	}


def _is_membership_invoice(sales_invoice) -> bool:
	"""Only subscription-generated invoices are membership dues — an advance must
	not silently settle some unrelated receivable."""
	row = frappe.db.get_value("Sales Invoice", sales_invoice, ["subscription", "is_return"], as_dict=True)
	return bool(row and row.subscription and not row.is_return)


def _recognition_warnings(allocations) -> list[str]:
	"""Flag applications that move Profit First cash into an already-swept period."""
	from netgainz.net_gainz.accounting import refunds

	warnings: list[str] = []
	seen: set[str] = set()
	for allocation in allocations:
		received = allocation.get("received_on")
		if not received or received in seen:
			continue
		seen.add(received)
		for warning in refunds._sweep_warnings(received):
			warnings.append(
				f"Money received on {received} has now been recognised as revenue. {warning}"
			)
	return warnings


def on_membership_invoice_submitted(membership) -> None:
	"""Best-effort: settle a new period's invoice from money already on account.

	A member who paid three months up front should not read as Overdue the moment
	month two is billed. Failures are logged, never raised — billing must not break
	because reconciliation had a bad day.
	"""
	try:
		if advance_balance(membership) > 0:
			apply_advances(membership)
	except Exception:
		frappe.log_error(title=f"WP-8 advance auto-apply failed for membership {membership}")


# --------------------------------------------------------------------------- #
# whitelisted owner / BFF entry points
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def record_member_advance(member, amount, payment_mode=None, posting_date=None, reference_no=None) -> dict:
	"""Owner/BFF: take money on account from a member."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	pe = record_advance(
		member, amount, payment_mode=payment_mode, posting_date=posting_date or today(), reference_no=reference_no
	)
	return {"payment_entry": pe, "advance_balance": advance_balance(member)}


@frappe.whitelist()
def apply_member_advances(member) -> dict:
	"""Owner/BFF: apply a member's unapplied cash to their open dues."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	result = apply_advances(member)
	result["advance_balance"] = advance_balance(member)
	return result


@frappe.whitelist()
def get_advance_context(member) -> dict:
	"""Owner/BFF: what this member has on account and where it came from."""
	return {"balance": advance_balance(member), "advances": open_advances(member)}
