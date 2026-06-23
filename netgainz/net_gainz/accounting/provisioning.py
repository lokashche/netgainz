# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-2: provision ERPNext masters from NetGainz domain records.

The accounting re-platform bills members through real ERPNext documents, so each
NetGainz master needs an ERPNext counterpart:

    Member          -> Customer            (the invoiced party)
    Membership Plan -> Item (+ Item Price) (the invoiced line + its selling rate)
                    -> Subscription Plan   (native recurring-billing definition)

This module creates those counterparts idempotently and stamps the link back
onto the NetGainz record (``Member.customer``, ``Membership Plan.item`` /
``.subscription_plan``). It runs two ways:

  * live, via ``doc_events`` (``on_update``) as members / plans are created or
    edited -- see ``hooks.py``;
  * in bulk, via the WP-2 backfill patch and the whitelisted owner trigger.

Design rules (mirrors profit_first/accounts.py + accounting/payment_modes.py):
  * **Idempotent** -- re-running never duplicates; an existing, still-present
    link is left untouched (a plan's Item Price is re-synced so a changed
    ``amount`` propagates).
  * **Best-effort on prerequisites** -- provisioning that cannot proceed yet is
    SKIPPED (returns ``None``), never fatal to the member / plan save:
      - no default Company        -> skip everything (nothing to scope to);
      - Plan has no HSN/SAC        -> skip the Item (india_compliance makes a SAC
        mandatory on a sellable Item) and therefore the Subscription Plan;
      - Plan duration not mappable -> skip the Subscription Plan only.
  * **Native pricing** -- the Item carries no rate; price lives on an Item Price
    row in the default Selling price list, and the Subscription Plan is
    ``"Based On Price List"`` so native Pricing Rules / Coupons apply later.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from netgainz.net_gainz.accounting.billing_intervals import duration_to_billing_interval
from netgainz.net_gainz.profit_first import accounts as pf_accounts

# Customer master defaults -- members are people, so an Individual party.
DEFAULT_CUSTOMER_TYPE = "Individual"
DEFAULT_CUSTOMER_GROUP = "Individual"
DEFAULT_TERRITORY = "All Territories"
# Service Item defaults -- a membership is a non-stock service.
DEFAULT_ITEM_GROUP = "Services"
DEFAULT_UOM = "Nos"
# Root tree nodes that always exist post-setup, used as last-resort fallbacks.
_ROOT_CUSTOMER_GROUP = "All Customer Groups"
_ROOT_ITEM_GROUP = "All Item Groups"

SUBSCRIPTION_PRICE_DETERMINATION = "Based On Price List"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _as_doc(doctype: str, ref) -> Document:
	"""Accept either a doc or its name; return the doc."""
	return ref if isinstance(ref, Document) else frappe.get_doc(doctype, ref)


def _company(company=None):
	return company or pf_accounts.default_company()


def _company_currency(company: str) -> str:
	return (
		frappe.get_cached_value("Company", company, "default_currency")
		or frappe.db.get_default("currency")
		or "INR"
	)


def _selling_price_list() -> str:
	return frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"


def _resolve(doctype: str, preferred: str, fallback) -> str | None:
	"""First of ``preferred`` / ``fallback`` that exists as ``doctype``."""
	for name in (preferred, fallback):
		if name and frappe.db.exists(doctype, name):
			return name
	return None


# --------------------------------------------------------------------------- #
# Member -> Customer
# --------------------------------------------------------------------------- #
def provision_customer(member, company=None) -> str | None:
	"""Ensure ``member`` has an ERPNext Customer; return its name (``None`` if skipped).

	Idempotent: an existing, still-present ``Member.customer`` is returned
	unchanged. Skipped only when no default Company is configured.
	"""
	member = _as_doc("Member", member)
	if member.get("customer") and frappe.db.exists("Customer", member.customer):
		return member.customer

	company = _company(company)
	if not company:
		return None

	customer = frappe.new_doc("Customer")
	customer.customer_name = member.full_name or member.name
	customer.customer_type = DEFAULT_CUSTOMER_TYPE
	# Set group / territory explicitly -- the setup wizard does not always pin
	# them in Selling Settings, and price resolution keys off customer_group.
	customer_group = _resolve("Customer Group", DEFAULT_CUSTOMER_GROUP, _ROOT_CUSTOMER_GROUP)
	if customer_group:
		customer.customer_group = customer_group
	territory = _resolve("Territory", DEFAULT_TERRITORY, None)
	if territory:
		customer.territory = territory
	customer.insert(ignore_permissions=True)

	member.db_set("customer", customer.name, update_modified=False)
	return customer.name


# --------------------------------------------------------------------------- #
# Membership Plan -> Item (+ Item Price)
# --------------------------------------------------------------------------- #
def _sync_item_price(item_code: str, amount) -> str | None:
	"""Upsert the plan's selling rate as an Item Price on the default Selling list.

	One canonical row per (item, price list); a changed plan ``amount`` updates
	the existing row rather than stacking a second price.
	"""
	price_list = _selling_price_list()
	if not frappe.db.exists("Price List", price_list):
		return None

	name = frappe.db.get_value(
		"Item Price", {"item_code": item_code, "price_list": price_list}, "name"
	)
	if name:
		if flt(frappe.db.get_value("Item Price", name, "price_list_rate")) != flt(amount):
			frappe.db.set_value("Item Price", name, "price_list_rate", flt(amount))
		return name

	item_price = frappe.new_doc("Item Price")
	item_price.item_code = item_code
	item_price.price_list = price_list
	item_price.price_list_rate = flt(amount)
	item_price.insert(ignore_permissions=True)
	return item_price.name


def provision_item(plan, company=None) -> str | None:
	"""Ensure ``plan`` has a sellable ERPNext Item (+ synced Item Price).

	Returns the Item name, or ``None`` when skipped. Skipped when the plan has no
	HSN/SAC code (india_compliance makes a SAC mandatory on a sales Item) or no
	default Company exists.
	"""
	plan = _as_doc("Membership Plan", plan)
	if plan.get("item") and frappe.db.exists("Item", plan.item):
		_sync_item_price(plan.item, plan.amount)
		return plan.item

	if not plan.get("gst_hsn_code"):
		return None  # cannot create a sellable Item without a SAC
	company = _company(company)
	if not company:
		return None

	# Membership Plan.name == plan_name (autoname field:plan_name, unique), so it
	# is a stable, human-readable item_code.
	item_code = plan.name
	if frappe.db.exists("Item", item_code):
		item_name = item_code
	else:
		item = frappe.new_doc("Item")
		item.item_code = item_code
		item.item_name = plan.plan_name
		item.item_group = _resolve("Item Group", DEFAULT_ITEM_GROUP, _ROOT_ITEM_GROUP)
		item.stock_uom = DEFAULT_UOM if frappe.db.exists("UOM", DEFAULT_UOM) else (
			frappe.db.get_single_value("Stock Settings", "stock_uom") or DEFAULT_UOM
		)
		item.is_stock_item = 0
		item.is_sales_item = 1
		item.is_purchase_item = 0
		item.include_item_in_manufacturing = 0
		item.gst_hsn_code = plan.gst_hsn_code
		if plan.get("description"):
			item.description = plan.description
		item.insert(ignore_permissions=True)
		item_name = item.name

	_sync_item_price(item_name, plan.amount)
	plan.db_set("item", item_name, update_modified=False)
	return item_name


# --------------------------------------------------------------------------- #
# Membership Plan -> Subscription Plan
# --------------------------------------------------------------------------- #
def _unique_subscription_plan_name(base: str) -> str:
	"""Subscription Plan is named by ``plan_name`` (unique); avoid colliding with
	an unrelated existing plan."""
	name = base
	suffix = 1
	while frappe.db.exists("Subscription Plan", name):
		name = f"{base} - {suffix}"
		suffix += 1
	return name


def provision_subscription_plan(plan, company=None) -> str | None:
	"""Ensure ``plan`` has a native ERPNext Subscription Plan; return its name
	(``None`` if skipped).

	Requires a sellable Item (so a SAC) and a duration that maps to a billing
	interval; otherwise skipped.
	"""
	plan = _as_doc("Membership Plan", plan)
	if plan.get("subscription_plan") and frappe.db.exists("Subscription Plan", plan.subscription_plan):
		return plan.subscription_plan

	company = _company(company)
	if not company:
		return None
	item = plan.get("item") or provision_item(plan, company)
	if not item:
		return None  # no sellable Item (no SAC) -> no Subscription Plan
	try:
		interval, count = duration_to_billing_interval(plan.duration_in_days)
	except (ValueError, TypeError):
		return None  # duration not mappable; skip until corrected

	subscription_plan = frappe.new_doc("Subscription Plan")
	subscription_plan.plan_name = _unique_subscription_plan_name(plan.plan_name)
	subscription_plan.currency = _company_currency(company)
	subscription_plan.item = item
	subscription_plan.price_determination = SUBSCRIPTION_PRICE_DETERMINATION
	subscription_plan.price_list = _selling_price_list()
	subscription_plan.billing_interval = interval
	subscription_plan.billing_interval_count = count
	subscription_plan.insert(ignore_permissions=True)

	plan.db_set("subscription_plan", subscription_plan.name, update_modified=False)
	return subscription_plan.name


def provision_plan(plan, company=None) -> dict:
	"""Provision both the Item and the Subscription Plan for ``plan``. Idempotent.

	Returns ``{"item": <name|None>, "subscription_plan": <name|None>}``.
	"""
	plan = _as_doc("Membership Plan", plan)
	company = _company(company)
	item = provision_item(plan, company)
	subscription_plan = provision_subscription_plan(plan, company) if item else None
	return {"item": item, "subscription_plan": subscription_plan}


# --------------------------------------------------------------------------- #
# doc_events handlers (hooks.py)
# --------------------------------------------------------------------------- #
def on_member_update(doc, method=None):
	"""``on_update`` hook for Member (fires on insert + every edit). Idempotent."""
	if frappe.flags.in_install:
		return
	provision_customer(doc)


def on_plan_update(doc, method=None):
	"""``on_update`` hook for Membership Plan (fires on insert + every edit).
	Idempotent; resyncs the Item Price when ``amount`` changes."""
	if frappe.flags.in_install:
		return
	provision_plan(doc)


# --------------------------------------------------------------------------- #
# owner-triggered bulk provisioning
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def provision_all_masters(company=None) -> dict:
	"""Idempotently provision Customers for all Members and Items / Subscription
	Plans for all Membership Plans. Owner-triggered; mirrors
	``payment_modes.setup_payment_mode_accounts``.

	Plans without a HSN/SAC are reported as ``items_skipped`` (their Item /
	Subscription Plan are deferred until a SAC is set on the plan).
	"""
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	members = frappe.get_all("Member", pluck="name")
	customers_linked = sum(1 for name in members if provision_customer(name, company))

	plans = frappe.get_all("Membership Plan", pluck="name")
	items = subscription_plans = 0
	for name in plans:
		result = provision_plan(name, company)
		items += 1 if result["item"] else 0
		subscription_plans += 1 if result["subscription_plan"] else 0

	return {
		"company": company,
		"members": len(members),
		"customers_linked": customers_linked,
		"plans": len(plans),
		"items": items,
		"items_skipped": len(plans) - items,
		"subscription_plans": subscription_plans,
	}
