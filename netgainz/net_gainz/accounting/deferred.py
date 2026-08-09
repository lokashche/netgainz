# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-6: cash/accrual toggle -> deferred revenue on membership billing.

`Business Settings.accounting_method` is the tenant's Cash/Accrual switch. Under
**Accrual**, a prepaid membership's revenue is recognised over the period it is
earned rather than booked in full on invoice; under **Cash** it books on invoice
(and Profit First — always cash, reading Payment Entries — is unaffected either
way, so nothing here touches PF/commissions).

The mechanism is pure ERPNext config, driven by the toggle:
  * enabling deferred revenue on the membership **Item** makes the native
    Subscription stamp ``enable_deferred_revenue`` + ``service_start/​end_date``
    (= the billing period) on every generated Sales Invoice item automatically;
  * the SI then credits the **Deferred Revenue** liability instead of income on
    submit, and ERPNext's monthly ``process_deferred_accounting`` scheduler
    recognises each period's slice into income over the service window.

So WP-6 just: (a) resolves/creates the Company's Deferred Revenue account +
switches on the Accounts Settings scheduler, and (b) keeps every membership
Item's ``enable_deferred_revenue`` in lockstep with the toggle. Note ERPNext's
recognition uses the SI **service dates**, never ``Item.no_of_months`` — so we
never set ``no_of_months`` (the Subscription supplies the exact period).
"""

import frappe

from netgainz.net_gainz.profit_first import accounts as pf_accounts

DEFERRED_REVENUE_ACCOUNT_NAME = "Deferred Revenue"
# Flat per-(calendar-)month recognition (with partial-month proration) reads more
# naturally for memberships than per-day; owner-adjustable in Accounts Settings.
BOOK_DEFERRED_BASED_ON = "Months"


def accounting_method() -> str:
	"""The tenant's Cash/Accrual setting (direct DB read — stale-singles-cache
	caution, as elsewhere). Defaults to Cash."""
	return frappe.db.get_single_value("Business Settings", "accounting_method") or "Cash"


def is_accrual() -> bool:
	return accounting_method() == "Accrual"


# --------------------------------------------------------------------------- #
# config (Company account + Accounts Settings scheduler)
# --------------------------------------------------------------------------- #
def default_deferred_revenue_account(company: str) -> str:
	"""Find or create the company's Deferred Revenue liability account (under
	Current Liabilities). Idempotent."""
	existing = frappe.db.get_value(
		"Account", {"company": company, "account_name": DEFERRED_REVENUE_ACCOUNT_NAME}, "name"
	)
	if existing:
		return existing
	parent = pf_accounts._find_group(company, "Current Liabilities", "Liability")
	return pf_accounts._ensure_account(DEFERRED_REVENUE_ACCOUNT_NAME, parent, company)


def setup_deferred_revenue(company=None) -> dict:
	"""Idempotently make deferred revenue postable: set the Company's default
	Deferred Revenue account and switch on the Accounts Settings recognition
	scheduler. Required before any deferred Sales Invoice can submit (ERPNext
	throws on a deferred item with no resolvable account)."""
	company = company or pf_accounts.default_company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	account = default_deferred_revenue_account(company)
	if frappe.db.get_value("Company", company, "default_deferred_revenue_account") != account:
		frappe.db.set_value("Company", company, "default_deferred_revenue_account", account)

	settings = frappe.get_single("Accounts Settings")
	changed = False
	if not settings.automatically_process_deferred_accounting_entry:
		settings.automatically_process_deferred_accounting_entry = 1
		changed = True
	if settings.book_deferred_entries_based_on != BOOK_DEFERRED_BASED_ON:
		settings.book_deferred_entries_based_on = BOOK_DEFERRED_BASED_ON
		changed = True
	if changed:
		settings.save(ignore_permissions=True)

	return {"company": company, "deferred_revenue_account": account}


# --------------------------------------------------------------------------- #
# keep membership Items in lockstep with the toggle
# --------------------------------------------------------------------------- #
def sync_item_deferred_revenue(item_code, accrual: bool) -> None:
	"""Set a membership Item's ``enable_deferred_revenue`` to match the toggle."""
	if not item_code or not frappe.db.exists("Item", item_code):
		return
	current = bool(frappe.db.get_value("Item", item_code, "enable_deferred_revenue"))
	if current != bool(accrual):
		frappe.db.set_value("Item", item_code, "enable_deferred_revenue", 1 if accrual else 0)


def sync_membership_items(accrual=None, company=None) -> int:
	"""Re-sync ``enable_deferred_revenue`` on every membership Item to the accrual
	toggle. When enabling accrual, ensure the deferred config exists first (so the
	next invoice can actually post). Returns the count synced."""
	if accrual is None:
		accrual = is_accrual()
	if accrual:
		setup_deferred_revenue(company)
	items = frappe.get_all("Membership Plan", filters={"item": ["is", "set"]}, pluck="item")
	for item in items:
		sync_item_deferred_revenue(item, accrual)
	return len(items)


@frappe.whitelist()
def resync_deferred_revenue(company=None) -> dict:
	"""Owner: re-apply the current accounting_method to deferred-revenue config +
	all membership Items (mirrors the other setup_* entry points)."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	accrual = is_accrual()
	count = sync_membership_items(accrual, company)
	return {"accounting_method": accounting_method(), "items_synced": count}
