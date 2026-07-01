# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-5: seed a default Expense Account on existing Expense Categories.

post_model_sync (the `expense_account` column must be synced first). Gives every
pre-existing category a sensible starting expense account so that, once a tenant
turns on `Business Settings.expense_post_to_ledger`, submitted Expenses can post a
JE without per-category setup. It is a STARTING default (a generic misc/indirect
expense leaf) the owner refines per category — expense posting is opt-in and off
by default, so this is inert until enabled. Idempotent: only fills categories
whose expense_account is empty.
"""

import frappe


def _default_expense_account(company: str) -> str | None:
	"""A conventional misc/indirect expense leaf for the company, else any
	non-group Expense account."""
	for account_name in ("Miscellaneous Expenses", "Indirect Expenses", "Administrative Expenses"):
		acc = frappe.db.get_value(
			"Account", {"company": company, "account_name": account_name, "is_group": 0}, "name"
		)
		if acc:
			return acc
	return frappe.db.get_value(
		"Account", {"company": company, "root_type": "Expense", "is_group": 0}, "name"
	)


def execute():
	if not frappe.db.table_exists("Expense Category"):
		return
	if "expense_account" not in frappe.db.get_table_columns("Expense Category"):
		return  # column not synced yet (defensive)

	from netgainz.net_gainz.profit_first import accounts as pf_accounts

	company = pf_accounts.default_company()
	if not company:
		return
	default_account = _default_expense_account(company)
	if not default_account:
		return

	for name in frappe.get_all(
		"Expense Category", filters={"expense_account": ["in", [None, ""]]}, pluck="name"
	):
		frappe.db.set_value("Expense Category", name, "expense_account", default_account, update_modified=False)
