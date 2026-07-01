# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Expense — a gym operating cost that can post to the ledger (Stage 7 WP-5).

An Expense is submittable, mirroring PF Sweep / Instructor Commission Run: on
submit it posts ONE balanced Journal Entry *iff* ledger posting is enabled in
Business Settings AND the category maps to an expense account — debit the
category's Expense Account (P&L), credit the payment-mode cash/bank account
(money out). Otherwise a submitted Expense is a reference-only record. Cancelling
reverses any JE it posted. This is the "JE-only" first cut (no Supplier / AP
subledger); accrual + bills are a later stage.

Profit First keeps reading the Expense doctype (not the GL) for its bucketing;
the JE is the accounting representation of a submitted expense. See ADR-0006.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from netgainz.net_gainz.accounting import branch, payment_modes, period_lock
from netgainz.net_gainz.profit_first import accounts as pf_accounts


class Expense(Document):
	def validate(self):
		if self.amount is not None and self.amount <= 0:
			frappe.throw("Amount must be greater than zero.")
		if not self.is_recurring:
			self.frequency = ""
		if not self.company:
			self.company = pf_accounts.default_company()

	def before_submit(self):
		# Only guard the posting date when this submit will actually post a JE.
		if self._should_post():
			period_lock.assert_postable(self.date, self.company)

	def on_submit(self):
		if self._should_post():
			self.db_set("journal_entry", self._post_journal_entry())

	def on_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
		self.db_set("journal_entry", None)

	def _expense_account(self):
		return (
			frappe.db.get_value("Expense Category", self.category, "expense_account")
			if self.category
			else None
		)

	def _should_post(self) -> bool:
		"""Post a JE only when the tenant enabled ledger posting AND the category
		maps to an expense account. Flag read directly (a Single's scalar can be
		served stale from the singles cache within the request it changed in)."""
		if not frappe.db.get_single_value("Business Settings", "expense_post_to_ledger"):
			return False
		return bool(self._expense_account())

	def _post_journal_entry(self) -> str:
		"""Post the balanced expense JE: debit the category's expense account,
		credit the payment-mode cash/bank account. Balances by construction."""
		amount = flt(self.amount, 2)
		expense_account = self._expense_account()
		credit_account = payment_modes.paid_to_account(self.company, self.payment_mode or "Cash")
		cc = branch.branch_cost_center(self.branch, self.company)

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = self.company
		je.posting_date = self.date
		remark = f"Expense {self.name} — {self.category}"
		if self.vendor:
			remark += f" ({self.vendor})"
		je.user_remark = remark
		je.append(
			"accounts",
			{"account": expense_account, "debit_in_account_currency": amount, "cost_center": cc},
		)
		je.append(
			"accounts",
			{"account": credit_account, "credit_in_account_currency": amount, "cost_center": cc},
		)
		je.insert(ignore_permissions=True)
		je.submit()
		return je.name
