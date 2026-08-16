# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-8: writing off uncollectable membership dues.

A write-off is **not** a refund and not a credit note. The gym earned the money,
billed for it, and will never see it — the member stopped coming, changed their
number, moved city. The revenue stays on the books (it was genuinely earned); what
changes is that the receivable becomes a **bad-debt expense**.

    Dr  Write Off (expense)          the loss the gym takes
    Cr  Debtors  (party = member)    the receivable that will never be collected

ERPNext models exactly this as a Journal Entry with
``voucher_type = "Write Off Entry"``. Referencing the Sales Invoice on the Debtors
row is what makes ERPNext re-derive the invoice's ``outstanding_amount`` down to
zero (traced 2026-08-08: outstanding 2360 -> 0, invoice status -> Paid).

Two consequences that WP-8 has to handle, both verified on the dev site:

* **The invoice's payment schedule is NOT updated.** Only Payment Entries touch
  ``Payment Schedule.outstanding``. So a written-off installment invoice still
  showed its full amount owing in ``billing.open_obligations``. That is fixed in
  billing.py by reconciling the schedule against the invoice's own scalar
  outstanding, which covers write-offs, credit notes and anything else that
  settles a receivable without cash.
* **ERPNext calls the invoice "Paid".** For the owner that is a lie, so a
  membership settled this way reports its own ``Written Off`` status rather than
  inheriting the invoice's.

Profit First is untouched by design: no cash moved, and the cash read only ever
looks at Payment Entries.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate, today

from netgainz.net_gainz.accounting import branch, currency, period_lock
from netgainz.net_gainz.profit_first import accounts as pf_accounts

WRITE_OFF_VOUCHER_TYPE = "Write Off Entry"
WRITE_OFF_ACCOUNT_NAME = "Bad Debts Written Off"

WRITE_OFF_REASONS = (
	"Member Unreachable",
	"Member Left",
	"Disputed / Not Recoverable",
	"Small Balance",
	"Other",
)


def _company(company=None):
	return company or pf_accounts.default_company()


# --------------------------------------------------------------------------- #
# the expense account the loss lands in
# --------------------------------------------------------------------------- #
def write_off_account(company=None) -> str | None:
	"""The tenant's bad-debt expense account, created on first use.

	Prefers the Company's own ``write_off_account`` — ERPNext's standard charts
	already ship one, and a tenant that has picked a different account must keep
	it. Falls back to creating a NetGainz-named account under Expenses, mirroring
	``profit_first.accounts`` / ``commissions.setup_commission_accounts`` so the
	owner never has to open Desk to make it exist.
	"""
	company = _company(company)
	if not company:
		return None
	configured = frappe.get_cached_value("Company", company, "write_off_account")
	if configured and frappe.db.exists("Account", configured):
		return configured

	parent = pf_accounts._find_group(company, "Expenses", "Expense")
	account = pf_accounts._ensure_account(WRITE_OFF_ACCOUNT_NAME, parent, company)
	if account:
		frappe.db.set_value("Company", company, "write_off_account", account)
	return account


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
def written_off_against(sales_invoice) -> float:
	"""How much of ``sales_invoice`` has been written off (positive rupees).

	Reads the Journal Entry Account rows that credit the receivable and reference
	this invoice, so it stays true no matter how many partial write-offs happened
	and drops back to zero if one is cancelled.
	"""
	if not sales_invoice:
		return 0.0
	return flt(
		frappe.db.sql(
			"""
			SELECT SUM(jea.credit_in_account_currency - jea.debit_in_account_currency)
			FROM `tabJournal Entry Account` jea
			INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
			WHERE je.docstatus = 1
			  AND je.voucher_type = %(voucher_type)s
			  AND jea.reference_type = 'Sales Invoice'
			  AND jea.reference_name = %(invoice)s
			""",
			{"voucher_type": WRITE_OFF_VOUCHER_TYPE, "invoice": sales_invoice},
		)[0][0]
	)


def is_written_off(sales_invoice) -> bool:
	return written_off_against(sales_invoice) > 0


# --------------------------------------------------------------------------- #
# the posting
# --------------------------------------------------------------------------- #
def write_off_invoice(sales_invoice, amount=None, reason=None, posting_date=None, company=None) -> str:
	"""Post a Write Off Entry for an uncollectable invoice. Returns the JE name.

	``amount`` defaults to everything still outstanding. A partial write-off is
	allowed (the gym recovers part of a debt and gives up on the rest).
	"""
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	currency.assert_paise_safe(company)

	si = frappe.db.get_value(
		"Sales Invoice",
		sales_invoice,
		["customer", "debit_to", "outstanding_amount", "currency", "docstatus", "cost_center"],
		as_dict=True,
	)
	if not si:
		frappe.throw(f"Sales Invoice {sales_invoice} does not exist.")
	if si.docstatus != 1:
		frappe.throw("Only a submitted invoice can be written off.")
	currency.assert_company_currency(si.currency, company, what="invoice")

	outstanding = flt(si.outstanding_amount)
	if outstanding <= 0:
		frappe.throw("There is nothing outstanding on this invoice to write off.")
	amount = flt(amount) if amount not in (None, "") else outstanding
	if amount <= 0:
		frappe.throw("The write-off amount must be greater than zero.")
	if amount > outstanding + 0.005:
		frappe.throw(f"Only {outstanding:.2f} is outstanding on this invoice.")

	posting_date = getdate(posting_date or today())
	period_lock.assert_postable(posting_date, company)

	expense_account = write_off_account(company)
	if not expense_account:
		frappe.throw("No write-off account could be resolved for this company.")
	cost_center = si.cost_center or branch.branch_cost_center(None, company)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = WRITE_OFF_VOUCHER_TYPE
	je.company = company
	je.posting_date = posting_date
	je.user_remark = f"NetGainz write-off: {reason}" if reason else "NetGainz write-off"
	je.append(
		"accounts",
		{
			"account": expense_account,
			"debit_in_account_currency": amount,
			"cost_center": cost_center,
		},
	)
	je.append(
		"accounts",
		{
			"account": si.debit_to,
			"party_type": "Customer",
			"party": si.customer,
			"credit_in_account_currency": amount,
			# The reference is what re-derives the invoice's outstanding amount.
			"reference_type": "Sales Invoice",
			"reference_name": sales_invoice,
			"cost_center": cost_center,
		},
	)
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def write_off_membership(membership, amount=None, reason=None, posting_date=None, company=None) -> dict:
	"""Write off what a member owes on their current membership invoice."""
	from netgainz.net_gainz.accounting import billing

	membership = billing._as_doc("Membership", membership)
	si_name = billing.current_invoice(membership)
	if not si_name:
		frappe.throw("This membership has no invoice to write off.")

	journal_entry = write_off_invoice(si_name, amount, reason, posting_date, company)
	billing.sync_derived_fields(membership)
	return {
		"journal_entry": journal_entry,
		"sales_invoice": si_name,
		"written_off": written_off_against(si_name),
	}


def reverse_write_off(journal_entry) -> str:
	"""Cancel a write-off (the member turned up and paid after all).

	Cancelling the Journal Entry restores the invoice's outstanding, so the debt
	is collectable again through the ordinary payment path.
	"""
	je = frappe.get_doc("Journal Entry", journal_entry)
	if je.voucher_type != WRITE_OFF_VOUCHER_TYPE:
		frappe.throw(f"{journal_entry} is not a write-off.")
	if je.docstatus != 1:
		frappe.throw("Only a submitted write-off can be reversed.")
	je.flags.ignore_permissions = True
	je.cancel()
	return je.name


# --------------------------------------------------------------------------- #
# whitelisted owner / BFF entry points
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def write_off_membership_dues(membership, amount=None, reason=None, posting_date=None) -> dict:
	"""Owner/BFF: write off uncollectable dues on a membership."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return write_off_membership(membership, amount=amount, reason=reason, posting_date=posting_date)


@frappe.whitelist()
def get_write_off_context(membership) -> dict:
	"""Owner/BFF: what could be written off here, and what already was."""
	from netgainz.net_gainz.accounting import billing

	si_name = billing.current_invoice(membership)
	if not si_name:
		return {
			"sales_invoice": None,
			"outstanding": 0.0,
			"written_off": 0.0,
			"reasons": list(WRITE_OFF_REASONS),
		}
	return {
		"sales_invoice": si_name,
		"outstanding": flt(frappe.db.get_value("Sales Invoice", si_name, "outstanding_amount")),
		"written_off": written_off_against(si_name),
		"reasons": list(WRITE_OFF_REASONS),
	}
