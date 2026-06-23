# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Payment-mode -> Mode of Payment -> paid-to account mapping (Stage 7 WP-0).

A member's collection carries a ``payment_mode`` (Subscription.payment_mode, one
of CASH_MODES + BANK_MODES). WP-4 turns each collection into an ERPNext Payment
Entry whose paid-to account must reflect HOW the money arrived — the gym's cash
drawer for Cash, the gym's bank account for digital modes. ERPNext models this
natively as a ``Mode of Payment`` with a per-company default account, so this
module just:

  (a) declares the mode set (mirrors the Subscription.payment_mode options),
  (b) provisions the Mode of Payment records + company account mappings
      (owner-triggered, touches config — mirrors PF / commission account setup),
  (c) resolves a payment_mode to its paid-to account for the Payment Entry creator.

The paid-to account is the TENANT's own ledger and is owner-configurable: Cash ->
the company default cash account; digital modes -> the company default bank
account (or an explicit override). Nothing here hard-codes a tenant account.
"""

import frappe

from netgainz.net_gainz.profit_first import accounts as pf_accounts

# Mirrors Subscription.payment_mode Select options EXACTLY (subscription.json).
# A regression test asserts this stays in sync with the doctype.
CASH_MODES = ("Cash",)
BANK_MODES = ("UPI", "Card", "Bank Transfer", "Online")
PAYMENT_MODES = CASH_MODES + BANK_MODES


def _mode_type(mode: str) -> str:
	"""ERPNext Mode of Payment.type for a payment_mode: Cash drawer vs Bank."""
	return "Cash" if mode in CASH_MODES else "Bank"


def _ensure_mode_of_payment(mode: str) -> str:
	"""Create the Mode of Payment record if missing. Idempotent. Returns its name."""
	if not frappe.db.exists("Mode of Payment", mode):
		doc = frappe.new_doc("Mode of Payment")
		doc.mode_of_payment = mode
		doc.type = _mode_type(mode)
		doc.enabled = 1
		doc.insert(ignore_permissions=True)
	return mode


def _resolve_account(company: str, mode: str, cash_account=None, bank_account=None) -> str:
	"""The tenant ledger a mode settles into: cash drawer for Cash, bank otherwise."""
	if mode in CASH_MODES:
		acc = cash_account or frappe.get_cached_value("Company", company, "default_cash_account")
		if not acc:
			frappe.throw(f"No default Cash account is set for {company}.")
		return acc
	acc = bank_account or frappe.get_cached_value("Company", company, "default_bank_account")
	if not acc:
		frappe.throw(
			f"No default Bank account is set for {company}. Set the company's Default "
			"Bank Account (or pass bank_account) so digital payment modes can post."
		)
	return acc


def _set_company_account(mode: str, company: str, account: str) -> None:
	"""Ensure the Mode of Payment carries a default `account` for `company`. Idempotent."""
	mop = frappe.get_doc("Mode of Payment", mode)
	for row in mop.accounts:
		if row.company == company:
			if row.default_account != account:
				row.default_account = account
				mop.save(ignore_permissions=True)
			return
	mop.append("accounts", {"company": company, "default_account": account})
	mop.save(ignore_permissions=True)


def setup_payment_modes(company=None, cash_account=None, bank_account=None) -> dict:
	"""Provision the five payment modes + their company paid-to accounts. Idempotent.

	Owner-triggered (touches config), mirroring PF / commission account setup.
	Cash -> company default cash account; digital modes -> company default bank
	account (override either explicitly). Returns {company, accounts: {mode: acc}}.
	"""
	company = company or pf_accounts.default_company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	mapping = {}
	for mode in PAYMENT_MODES:
		_ensure_mode_of_payment(mode)
		account = _resolve_account(company, mode, cash_account, bank_account)
		_set_company_account(mode, company, account)
		mapping[mode] = account
	return {"company": company, "accounts": mapping}


@frappe.whitelist()
def setup_payment_mode_accounts(company=None, cash_account=None, bank_account=None) -> dict:
	"""Whitelisted entry point for the owner to provision payment-mode accounts."""
	return setup_payment_modes(company, cash_account, bank_account)


def paid_to_account(company: str, payment_mode: str) -> str:
	"""Resolve the paid-to ledger account for a payment_mode (WP-4 Payment Entry).

	Prefers the Mode of Payment's configured company account; falls back to the
	company default cash/bank account by classification.
	"""
	if payment_mode and frappe.db.exists("Mode of Payment", payment_mode):
		acc = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": payment_mode, "company": company},
			"default_account",
		)
		if acc:
			return acc
	return _resolve_account(company, payment_mode if payment_mode in PAYMENT_MODES else "Cash")
