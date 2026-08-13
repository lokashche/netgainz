# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Coach Commission Run — compute, record, and optionally post coach commissions
for a period (Stage 6).

A run is BOTH the proposal and the audit record. On creation it snapshots each
eligible coach's commission for the period into frozen, read-only lines (no money
moves). On submit — the owner's explicit Approve — it posts ONE balanced Journal
Entry (debit Coach Commission Expense, credit Coach Commissions Payable) *iff*
posting to the ledger is enabled in Gym Settings; otherwise the run is a
reference-only record. Cancelling reverses any Journal Entry it posted.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from netgainz.net_gainz.accounting import branch
from netgainz.net_gainz.operations import commissions


class InstructorCommissionRun(Document):
	def before_insert(self):
		self.populate_lines()

	def populate_lines(self):
		"""Snapshot the period's commissions and the ledger config. Taken once at
		creation so the run is a stable audit record."""
		settings = frappe.get_single("Business Settings")
		result = commissions.compute_commissions(self.period_start, self.period_end)

		self.period_start = result["period_start"]
		self.period_end = result["period_end"]
		self.percentage_basis = result["percentage_basis"]
		self.total_commission = result["total"]

		# Read the toggle directly: a Single's scalar fields can be served stale
		# from the singles cache within the request they were last changed in.
		self.post_to_ledger = 1 if frappe.db.get_single_value("Business Settings", "commission_post_to_ledger") else 0
		self.commission_expense_account = settings.commission_expense_account
		self.commission_payable_account = settings.commission_payable_account
		if not self.company:
			from netgainz.net_gainz.profit_first import accounts as pf_accounts

			self.company = pf_accounts.default_company()
		# Branch dimension: a company-wide run sits on Main by default.
		self.branch = self.branch or branch.ensure_main_branch(self.company)

		self.set("lines", [])
		for line in result["lines"]:
			self.append(
				"lines",
				{
					"coach": line["coach"],
					"commission_type": line["commission_type"],
					"basis_label": line["basis_label"],
					"base_amount": line["base_amount"],
					"rate": line["rate"],
					"commission_amount": line["commission_amount"],
				},
			)

	def before_submit(self):
		# Idempotency: at most one posted run per exact period.
		dup = frappe.db.exists(
			"Instructor Commission Run",
			{
				"period_start": self.period_start,
				"period_end": self.period_end,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		)
		if dup:
			frappe.throw(
				f"A commission run for {self.period_start} to {self.period_end} "
				f"has already been posted ({dup})."
			)

		if self.post_to_ledger:
			if flt(self.total_commission) <= 0:
				frappe.throw("There is no commission to post for this period.")
			if not self.commission_expense_account or not self.commission_payable_account:
				frappe.throw(
					"Commission ledger accounts are not set. Run commission account setup first."
				)

	def on_submit(self):
		if self.post_to_ledger and flt(self.total_commission) > 0:
			self.db_set("journal_entry", self._post_journal_entry())

	def on_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
		self.db_set("journal_entry", None)

	def _post_journal_entry(self) -> str:
		"""Post the balanced commission accrual: debit Commission Expense, credit
		Commissions Payable, by the run's total. Balances by construction."""
		total = flt(self.total_commission, 2)
		cc = branch.branch_cost_center(self.branch, self.company)

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = self.company
		je.posting_date = self.period_end
		je.user_remark = f"Coach commissions {self.name} — {self.period_start} to {self.period_end}"
		je.append(
			"accounts",
			{
				"account": self.commission_expense_account,
				"debit_in_account_currency": total,
				"cost_center": cc,
			},
		)
		je.append(
			"accounts",
			{
				"account": self.commission_payable_account,
				"credit_in_account_currency": total,
				"cost_center": cc,
			},
		)
		je.insert(ignore_permissions=True)
		je.submit()
		return je.name


@frappe.whitelist()
def create_commission_run(period_start=None, period_end=None) -> str:
	"""Create a draft commission run (computes the lines; no money moves)."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	doc = frappe.new_doc("Instructor Commission Run")
	if period_start:
		doc.period_start = period_start
	if period_end:
		doc.period_end = period_end
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def approve_commission_run(name: str) -> str:
	"""Approve a draft run — posts the Journal Entry if posting is enabled."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	doc = frappe.get_doc("Instructor Commission Run", name)
	doc.submit()
	return doc.name


@frappe.whitelist()
def cancel_commission_run(name: str) -> str:
	"""Cancel a posted run — reverses its Journal Entry if it posted one."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	doc = frappe.get_doc("Instructor Commission Run", name)
	doc.cancel()
	return doc.name
