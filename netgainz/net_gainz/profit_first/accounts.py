# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Profit First — ERPNext Chart of Accounts setup (Stage 5b).

Idempotently creates the five Profit First ledger accounts in the gym's company
and maps them onto Profit First Settings, so the bi-monthly sweep can post a
balanced Journal Entry against them.

Per the agreed design (the owner can open real bank accounts later):
- The four allocation roles (Profit, Owner's Pay, Tax, Operating Expenses) become
  plain ASSET "reserve" ledger accounts under a "Profit First Allocations" group.
  They hold cash earmarked for each purpose; the sweep DEBITS them.
- The Income role becomes an INCOME (P&L) account; the sweep CREDITS it with the
  period's Real Revenue (recognise + allocate in one entry).

Creating accounts touches the books, so this is an explicit owner action
(whitelisted), never run automatically.
"""

import frappe

from netgainz.net_gainz.profit_first import calc

# (account_role, account_name, kind)
ROLE_ACCOUNTS = [
	("Income", "PF Income", "income"),
	(calc.PROFIT, "PF Profit", "asset"),
	(calc.OWNERS_PAY, "PF Owner's Pay", "asset"),
	(calc.TAX, "PF Tax", "asset"),
	(calc.OPEX, "PF Operating Expenses", "asset"),
]

ALLOCATION_GROUP = "Profit First Allocations"


def default_company():
	return (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)


def _find_group(company: str, account_name: str, root_type: str) -> str:
	"""Locate a group account to parent under, falling back to the root of the
	given root_type."""
	name = frappe.db.get_value(
		"Account", {"company": company, "account_name": account_name, "is_group": 1}, "name"
	)
	if not name:
		name = frappe.db.get_value(
			"Account",
			{"company": company, "root_type": root_type, "is_group": 1, "parent_account": ["in", ["", None]]},
			"name",
		)
	if not name:
		frappe.throw(f"Could not find a parent {root_type} group in company {company}.")
	return name


def _ensure_account(account_name: str, parent_account: str, company: str, is_group: int = 0) -> str:
	"""Create the account if it doesn't already exist; return its name. Idempotent."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	expected = f"{account_name} - {abbr}"
	if frappe.db.exists("Account", expected):
		return expected

	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.parent_account = parent_account
	acc.company = company
	acc.is_group = is_group
	# root_type / account_currency are inherited from the parent; account_type is
	# left blank so the allocation accounts are generic asset reserves.
	acc.insert(ignore_permissions=True)
	return acc.name


def _map_account(settings, role: str, account: str, cost_center: str | None):
	for row in settings.accounts:
		if row.account_role == role:
			row.account_link = account
			if cost_center and not row.cost_center:
				row.cost_center = cost_center
			return
	settings.append("accounts", {"account_role": role, "account_link": account, "cost_center": cost_center})


def setup_pf_accounts(company: str | None = None) -> dict:
	"""Create + map the five Profit First accounts. Idempotent."""
	company = company or default_company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	asset_parent = _find_group(company, "Current Assets", "Asset")
	income_parent = _find_group(company, "Income", "Income")
	alloc_group = _ensure_account(ALLOCATION_GROUP, asset_parent, company, is_group=1)

	mapping = {}
	for role, acc_name, kind in ROLE_ACCOUNTS:
		parent = income_parent if kind == "income" else alloc_group
		mapping[role] = _ensure_account(acc_name, parent, company)

	settings = frappe.get_single("Profit First Settings")
	if not settings.company:
		settings.company = company
	for role, account in mapping.items():
		_map_account(settings, role, account, cost_center)
	settings.save(ignore_permissions=True)

	return {"company": company, "accounts": mapping}


@frappe.whitelist()
def setup_profit_first_accounts(company: str | None = None) -> dict:
	"""Whitelisted entry point for the owner to provision PF accounts."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return setup_pf_accounts(company)
