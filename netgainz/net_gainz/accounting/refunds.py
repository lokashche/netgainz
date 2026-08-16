# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-8: refunds and credit notes.

A gym gives money back for two quite different reasons, and the books must tell
them apart:

* **Waive a charge** — the member never paid and never will be asked to (a billing
  mistake, a goodwill gesture, a plan changed mid-period). Revenue is reversed and
  the receivable disappears. **No cash moves**, so Profit First is untouched.
* **Refund cash** — the member already paid and the gym hands the money back. The
  credit note reverses the revenue AND a Payment Entry sends the cash out.
  **Profit First must fall by exactly the refunded amount** (the WP-8 cash-impact
  rule): a rupee that left the bank cannot stay in the owner's allocation base.

Both are the same ERPNext object — a Sales Invoice with ``is_return = 1`` pointing
at the original via ``return_against`` (a credit note) — and ERPNext itself picks
which of the two it is:

    accounts_controller.validate_return_against (v15) forces
    ``update_outstanding_for_self = 1`` whenever the credit exceeds the original
    invoice's REMAINING outstanding.

So a credit against an unpaid invoice nets it down (the member simply owes less),
while a credit against a settled invoice stands on its own with a NEGATIVE
outstanding — money the gym owes the member — which a ``Pay`` Payment Entry then
discharges. We ask for ``update_outstanding_for_self = 0`` and let ERPNext promote
it; nothing here second-guesses the ledger.

Traced mechanics (2026-08-08, live on the dev site — do not re-derive):

1. ``make_return_doc`` copies ``subscription`` onto the credit note (the field is
   not ``no_copy``). That is USEFUL — it is what lets the Profit First cash read
   find refunds — but it also means every subscription-keyed read in billing.py
   must exclude ``is_return`` rows or the credit note masquerades as the current
   period's invoice. See ``billing.NOT_A_CREDIT_NOTE``.
2. A partial credit CANNOT be expressed as a fractional qty — the ``Nos`` UOM is
   whole-number, so ``qty = -0.5`` throws ``UOMMustBeIntegerError``. Partial
   credits keep ``qty = -1`` and scale the RATE instead.
3. The refund Payment Entry comes back as ``payment_type = "Pay"`` with a
   **negative** ``allocated_amount`` on its reference row. That sign is what makes
   ``billing.collected_paise`` net refunds out with no special-casing.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowtime, today

from netgainz.net_gainz.accounting import branch, currency, payment_modes, period_lock
from netgainz.net_gainz.profit_first import accounts as pf_accounts

CREDIT_NOTE_REASONS = (
	"Cancelled Membership",
	"Downgrade / Proration",
	"Service Not Delivered",
	"Billing Error",
	"Goodwill",
	"Other",
)


def _company(company=None):
	return company or pf_accounts.default_company()


def _invoice(name, fields):
	return frappe.db.get_value("Sales Invoice", name, fields, as_dict=isinstance(fields, list))


# --------------------------------------------------------------------------- #
# credit notes
# --------------------------------------------------------------------------- #
def refundable_amount(sales_invoice) -> float:
	"""How much of ``sales_invoice`` is still creditable (gross, tax-inclusive).

	The invoice total less whatever has already been credited against it, so two
	successive refunds can never exceed the original charge.
	"""
	si = _invoice(sales_invoice, ["grand_total", "rounded_total"])
	if not si:
		return 0.0
	total = flt(si.rounded_total) or flt(si.grand_total)
	credited = abs(
		flt(
			frappe.db.get_value(
				"Sales Invoice",
				{"return_against": sales_invoice, "docstatus": 1},
				"sum(grand_total)",
			)
		)
	)
	return max(0.0, flt(total) - credited)


def credited_against(sales_invoice) -> float:
	"""Total credited against ``sales_invoice`` so far (positive rupees)."""
	return abs(
		flt(
			frappe.db.get_value(
				"Sales Invoice", {"return_against": sales_invoice, "docstatus": 1}, "sum(grand_total)"
			)
		)
	)


def _is_bank_account(account) -> bool:
	"""ERPNext demands a reference number for money moving through a bank account."""
	if not account:
		return False
	return frappe.db.get_value("Account", account, "account_type") == "Bank"


def _credit_note_time(posting_date, src) -> str:
	"""A time for the credit note that is never earlier than the invoice it credits.

	ERPNext compares the two timestamps and refuses a return that lands before its
	original. Same day is the interesting case: "now" is normally after the invoice,
	but an invoice raised by the daily scheduler at 03:00 and refunded at 09:00 is
	fine while one raised at 09:05 and refunded at 09:04 is not -- so on the same
	day take whichever is later.
	"""
	invoice_date = getdate(src.get("posting_date")) if src.get("posting_date") else None
	invoice_time = str(src.get("posting_time") or "00:00:00")
	now = nowtime()

	if invoice_date and getdate(posting_date) < invoice_date:
		frappe.throw(
			_("A refund cannot be dated {0}, before the invoice it credits ({1}).").format(
				frappe.utils.formatdate(posting_date), frappe.utils.formatdate(invoice_date)
			)
		)
	if invoice_date and getdate(posting_date) == invoice_date:
		return max(now, invoice_time)
	return now


def create_credit_note(sales_invoice, amount=None, reason=None, posting_date=None, company=None) -> str:
	"""Raise and submit a credit note for ``amount`` (gross) against an invoice.

	``amount`` is what the OWNER means by a refund — the money figure, tax
	included. The line rate is grossed down by the original invoice's own
	``net_total / grand_total`` ratio so the tax component is credited in exactly
	the proportion it was charged (a no-op ratio of 1 for a non-GST tenant).

	Returns the credit note's name.
	"""
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	src = _invoice(
		sales_invoice,
		[
			"net_total",
			"grand_total",
			"rounded_total",
			"currency",
			"docstatus",
			"is_return",
			"posting_date",
			"posting_time",
		],
	)
	if not src:
		frappe.throw(f"Sales Invoice {sales_invoice} does not exist.")
	if src.docstatus != 1:
		frappe.throw("Only a submitted invoice can be credited.")
	if src.is_return:
		frappe.throw("A credit note cannot itself be credited.")
	currency.assert_company_currency(src.currency, company, what="invoice")

	gross = flt(amount) if amount is not None else refundable_amount(sales_invoice)
	if gross <= 0:
		frappe.throw("The credit amount must be greater than zero.")
	remaining = refundable_amount(sales_invoice)
	if gross > remaining + 0.005:
		frappe.throw(
			f"This invoice has only {remaining:.2f} left to credit "
			f"(some of it has already been refunded)."
		)

	posting_date = getdate(posting_date or today())
	period_lock.assert_postable(posting_date, company)

	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	# `get_mapped_doc` refuses unless the SESSION user could create a Sales Invoice
	# by hand — which no gym user can, and should not be able to: the product
	# decides which documents exist, the role only authorises the product action
	# (already checked by require_role at the entry point). Handing the mapper a
	# target that carries the flag keeps the grant off the role.
	target = frappe.new_doc("Sales Invoice")
	target.flags.ignore_permissions = True
	cn = make_return_doc("Sales Invoice", sales_invoice, target)
	# Gross -> net: credit the tax in the same proportion the invoice charged it.
	scale = (flt(src.net_total) / flt(src.grand_total)) if flt(src.grand_total) else 1.0
	target_net = gross * scale
	line_total = sum(abs(flt(i.qty) * flt(i.rate)) for i in cn.items) or 1.0
	for item in cn.items:
		share = abs(flt(item.qty) * flt(item.rate)) / line_total
		# qty stays a whole -1: the `Nos` UOM rejects fractions, so a partial
		# credit is expressed in the RATE (traced 2026-08-08).
		item.qty = -1
		item.rate = target_net * share
	# Ask to net against the original; ERPNext promotes this to 1 by itself when
	# the credit exceeds what is still outstanding (i.e. the invoice was paid, so
	# the money is genuinely owed back).
	cn.update_outstanding_for_self = 0
	cn.set_posting_time = 1
	cn.posting_date = posting_date
	# Setting `set_posting_time` tells ERPNext to keep whatever time is on the doc
	# rather than stamping "now" -- so the TIME has to be set too, or the credit
	# note inherits midnight and ERPNext's own return guard
	# (`validate_return_against`) refuses it: "Posting timestamp must be after ...".
	# It bit only when crediting on the same day as the invoice, which is exactly
	# what a mistake-at-the-desk refund is.
	cn.posting_time = _credit_note_time(posting_date, src)
	cn.cost_center = cn.get("cost_center") or branch.branch_cost_center(None, company)
	if reason:
		cn.remarks = f"NetGainz refund: {reason}"
	cn.insert(ignore_permissions=True)
	cn.submit()
	return cn.name


# --------------------------------------------------------------------------- #
# the cash leg
# --------------------------------------------------------------------------- #
def _refundable_document(sales_invoice, credit_note) -> tuple[str, float] | tuple[None, float]:
	"""Which document carries the money owed back, and how much.

	ERPNext parks the negative outstanding either on the credit note (it stood on
	its own) or on the original invoice (the credit was netted into it).
	"""
	for name in (credit_note, sales_invoice):
		if not name:
			continue
		outstanding = flt(_invoice(name, "outstanding_amount"))
		if outstanding < 0:
			return name, abs(outstanding)
	return None, 0.0


def pay_refund(document, amount, payment_mode=None, posting_date=None, company=None, reference_no=None) -> str:
	"""Send ``amount`` back to the member as a submitted ``Pay`` Payment Entry.

	``document`` is whichever Sales Invoice carries the negative outstanding (the
	credit note, or the original invoice when the credit was netted into it).
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	company = _company(company)
	posting_date = getdate(posting_date or today())
	period_lock.assert_postable(posting_date, company)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw("The refund amount must be greater than zero.")
	owed = abs(flt(_invoice(document, "outstanding_amount")))
	if amount > owed + 0.005:
		frappe.throw(f"Only {owed:.2f} is owed back on {document}.")

	pe = get_payment_entry("Sales Invoice", document)
	if pe.payment_type != "Pay":
		frappe.throw(f"{document} does not owe the member anything to refund.")
	pe.posting_date = posting_date
	pe.reference_date = posting_date
	if payment_mode:
		pe.mode_of_payment = payment_mode
		# Money LEAVES this account on a refund, so it is paid_from, not paid_to.
		pe.paid_from = payment_modes.paid_to_account(company, payment_mode)
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.cost_center = pe.get("cost_center") or branch.branch_cost_center(None, company)
	# ERPNext makes Reference No mandatory whenever the money moves through a BANK
	# account, and refuses the Payment Entry without it. The owner refunding cash
	# has nothing to type, and should not be handed
	# "Reference No and Reference Date is mandatory for Bank transaction" -- which
	# names a field the refund screen does not even show. Fall back to the document
	# being refunded: it is traceable, and it is what a bank statement gets
	# reconciled against anyway.
	pe.reference_no = reference_no or (
		document if _is_bank_account(pe.get("paid_from")) else pe.get("reference_no")
	)
	# One reference, one negative allocation: ERPNext's own sign convention, and
	# what makes billing.collected_paise net the refund out.
	for row in pe.references:
		row.allocated_amount = -amount if row.reference_name == document else 0
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


# --------------------------------------------------------------------------- #
# the owner-facing action
# --------------------------------------------------------------------------- #
def refund_membership(
	membership,
	amount=None,
	reason=None,
	posting_date=None,
	payment_mode=None,
	return_cash=True,
	sales_invoice=None,
	company=None,
) -> dict:
	"""Credit a membership charge, and (optionally) hand the cash back.

	``return_cash=False`` is the *waive* case: the charge is reversed, the member
	owes less, no money moves and Profit First does not change. ``return_cash=True``
	additionally pays out whatever the credit note leaves owing — which is nothing
	at all when the invoice was never paid, so a waive stays a waive even if the
	owner leaves the box ticked.
	"""
	from netgainz.net_gainz.accounting import billing

	membership = billing._as_doc("Membership", membership)
	company = _company(company)
	si_name = sales_invoice or billing.current_invoice(membership)
	if not si_name:
		frappe.throw("This membership has no invoice to refund.")

	credit_note = create_credit_note(si_name, amount, reason, posting_date, company)
	payable_doc, owed = _refundable_document(si_name, credit_note)

	payment_entry = None
	if return_cash and owed > 0:
		payment_entry = pay_refund(payable_doc, owed, payment_mode, posting_date, company)

	billing.sync_derived_fields(membership)
	return {
		"credit_note": credit_note,
		"payment_entry": payment_entry,
		"cash_refunded": owed if payment_entry else 0.0,
		"credit_applied": 0.0 if payment_entry else flt(amount or 0),
		"warnings": _sweep_warnings(posting_date),
	}


def _sweep_warnings(posting_date) -> list[str]:
	"""Warn when the cash moves on or before a period the owner already allocated.

	Profit First reads cash by Payment Entry posting date, so a backdated refund
	silently changes an assessment that may already have been swept. A PF Sweep
	records only its ``sweep_date`` and a period label, so the test is the
	conservative one: any posted sweep dated on/after this posting date looked at
	this cash. Not a block — the books must record what actually happened — but the
	owner is told now instead of discovering it at the next sweep.
	"""
	posting_date = getdate(posting_date or today())
	sweeps = frappe.get_all(
		"PF Sweep",
		filters={"docstatus": 1, "sweep_date": [">=", posting_date]},
		fields=["name", "period_label"],
		order_by="sweep_date asc",
		limit=3,
	)
	if not sweeps:
		return []
	labels = ", ".join(f"{s.name} ({s.period_label})" for s in sweeps)
	return [
		f"This date is covered by an already-posted Profit First sweep — {labels}. "
		"The allocation figures for that period will now read differently."
	]


# --------------------------------------------------------------------------- #
# whitelisted owner / BFF entry points
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def refund_membership_payment(
	membership, amount=None, reason=None, posting_date=None, payment_mode=None, return_cash=1
) -> dict:
	"""Owner/BFF: refund (or waive) part of a membership charge."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return refund_membership(
		membership,
		amount=flt(amount) if amount not in (None, "") else None,
		reason=reason,
		posting_date=posting_date,
		payment_mode=payment_mode,
		return_cash=bool(int(return_cash or 0)),
	)


@frappe.whitelist()
def get_refund_context(membership) -> dict:
	"""Owner/BFF: what this membership can be refunded, and what already was."""
	from netgainz.net_gainz.accounting import billing

	si_name = billing.current_invoice(membership)
	if not si_name:
		return {"sales_invoice": None, "refundable": 0.0, "credited": 0.0, "collected": 0.0, "reasons": list(CREDIT_NOTE_REASONS)}
	si = _invoice(si_name, ["grand_total", "rounded_total", "outstanding_amount"])
	total = flt(si.rounded_total) or flt(si.grand_total)
	return {
		"sales_invoice": si_name,
		"invoice_total": total,
		"refundable": refundable_amount(si_name),
		"credited": credited_against(si_name),
		"collected": max(0.0, total - flt(si.outstanding_amount) - credited_against(si_name)),
		"reasons": list(CREDIT_NOTE_REASONS),
	}
