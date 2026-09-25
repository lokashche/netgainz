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

Stage 11.0: the owner-app never submits an Expense, so no JE was ever posted and
the official books held no expenses at all. The JE now follows the SAVED record —
posted on save, re-posted when a money field changes, reversed on delete — so every
path that creates one (the form, repeating expenses, the loader) lands in the books.
A category's account is provisioned silently from its Profit First bucket.
"""

import frappe
from erpnext.accounts.utils import FiscalYearError
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
		if self._should_post() and not self.journal_entry:
			self._post_or_wait()

	def on_update(self):
		"""Keep the draft's JE in step with it (Stage 11.0)."""
		if self.docstatus != 0 or not self._should_post():
			return
		if self.journal_entry and not any(self.has_value_changed(f) for f in _POSTED_FIELDS):
			return
		period_lock.assert_postable(self.date, self.company)
		self._cancel_journal_entry()
		self.db_set("journal_entry", None)
		self._post_or_wait()

	def _post_or_wait(self):
		try:
			self.db_set("journal_entry", self._post_journal_entry())
		except FiscalYearError:
			# The books have no financial year for this date yet. Keep the expense
			# (entering it must never be blocked); it waits in the "not in the books"
			# count until the year exists and the owner puts it in.
			frappe.clear_messages()
			frappe.msgprint(
				f"Saved, but not in your books yet: there is no financial year for {self.date}.",
				alert=True,
			)

	def on_trash(self):
		self._cancel_journal_entry()

	def _cancel_journal_entry(self):
		if self.journal_entry and frappe.db.get_value("Journal Entry", self.journal_entry, "docstatus") == 1:
			frappe.get_doc("Journal Entry", self.journal_entry).cancel()

	def on_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
		self.db_set("journal_entry", None)

	def _expense_account(self):
		if not self.category:
			return None
		return frappe.db.get_value("Expense Category", self.category, "expense_account") or (
			_provision_category_account(self.category, self.company)
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


# A change to any of these moves money differently, so the JE is re-posted.
_POSTED_FIELDS = ("amount", "date", "category", "payment_mode", "branch")

# Profit First bucket -> the account group a category's ledger sits under.
# ponytail: Owner's Pay / Tax post as owner's drawings (equity), the proprietorship
# treatment; a partnership (partner drawings) or company (director salary expense,
# tax expense) needs this map keyed by constitution — add with the Stage 12 setting.
_BUCKET_GROUP = {
	"Pass-Through": ("Direct Expenses", "Expense"),
	"Owner's Pay": ("Equity", "Equity"),
	"Tax": ("Equity", "Equity"),
}
_DEFAULT_GROUP = ("Indirect Expenses", "Expense")
_DRAWINGS = "Owner's Drawings"


def _provision_category_account(category, company):
	"""Find or create the ledger a category posts to and remember it on the category.
	Idempotent; returns None when the company's chart has no suitable group."""
	company = company or pf_accounts.default_company()
	bucket = frappe.db.get_value("Expense Category", category, "pf_bucket") or "Operating Expenses"
	group_name, root_type = _BUCKET_GROUP.get(bucket, _DEFAULT_GROUP)
	parent = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": group_name, "is_group": 1, "root_type": root_type},
		"name",
	) or frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": root_type}, "name")
	if not parent:
		return None
	leaf = _DRAWINGS if root_type == "Equity" else category
	account = frappe.db.get_value(
		"Account", {"company": company, "account_name": leaf, "is_group": 0}, "name"
	)
	if not account:
		account = (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": leaf,
					"parent_account": parent,
					"company": company,
					"is_group": 0,
					"account_currency": frappe.get_cached_value("Company", company, "default_currency"),
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	if root_type == "Equity":
		# Cash Flow finds equity movements by account type; without it, drawings
		# vanish from "Cash Flow from Financing" and net change in cash is overstated.
		frappe.db.set_value("Account", account, "account_type", "Equity")
	frappe.db.set_value("Expense Category", category, "expense_account", account)
	return account


@frappe.whitelist()
def post_past_expenses() -> dict:
	"""Owner: put expenses saved before Stage 11.0 into the books, once. One the
	books cannot take (a closed period, a date before the first financial year) is
	skipped and named, not allowed to stop the rest."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	posted, skipped = 0, []
	for name in frappe.get_all(
		"Expense", filters={"docstatus": 0, "journal_entry": ["is", "not set"]}, pluck="name"
	):
		doc = frappe.get_doc("Expense", name)
		if not doc._should_post():
			continue
		try:
			period_lock.assert_postable(doc.date, doc.company)
			doc.db_set("journal_entry", doc._post_journal_entry())
			posted += 1
		except frappe.ValidationError as e:
			frappe.clear_messages()
			skipped.append(
				{"expense": name, "date": str(doc.date), "reason": frappe.utils.strip_html(str(e))}
			)
	return {"posted": posted, "skipped": skipped}


@frappe.whitelist()
def unposted_expense_count() -> int:
	"""How many saved expenses are not in the books yet (for the Expenses banner)."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return frappe.db.count("Expense", {"docstatus": 0, "journal_entry": ["is", "not set"]})
