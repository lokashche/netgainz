# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-8: multi-currency guards for the money maths.

Every rupee figure in NetGainz is quantised to **integer paise** by
``profit_first.calc.to_paise`` — a hard-coded 1/100 minor unit. That is exact for
INR and for the ~150 other two-decimal currencies, and silently WRONG for the
rest: JPY and KRW have no minor unit at all (¥100 is ¥100, not ¥1.00), KWD/BHD/OMR
have three. A Profit First allocation computed on a 0- or 3-decimal currency would
be off by a factor of 100 or 10, and the largest-remainder split would hand out
"paise" that do not exist.

Rather than make ``to_paise`` currency-aware (it is a pure, frappe-free function
that the whole cent-sensitive core depends on), this module guards the EDGES:

* :func:`assert_paise_safe` — the tenant's company currency must have exactly 100
  minor units. Called before anything quantises money.
* :func:`assert_company_currency` — a membership's billing documents must be
  denominated in the company's own currency. NetGainz shows one unlabelled money
  column per screen and Profit First sums a single scalar, so a membership billed
  in a second currency would add USD to INR in the owner's face. ERPNext itself is
  perfectly happy multi-currency; the *product* is single-currency per tenant, and
  this is where that decision is enforced instead of being assumed.

The cash read itself (``billing.collected_paise``) is written base-currency-safe
regardless — it multiplies each allocation by the reference row's exchange rate —
so a stray foreign-currency document can never inflate Profit First even if it
somehow gets past these guards.
"""

from __future__ import annotations

import frappe

from netgainz.net_gainz.profit_first import accounts as pf_accounts

# The minor-unit divisor baked into calc.to_paise / calc.to_rupees.
PAISE_PER_UNIT = 100


def company_currency(company: str | None = None) -> str | None:
	"""The tenant's book currency (Company default), or None if unconfigured."""
	company = company or pf_accounts.default_company()
	if not company:
		return None
	return frappe.get_cached_value("Company", company, "default_currency")


def minor_units(currency: str | None) -> int:
	"""How many minor units make one unit of ``currency`` (INR -> 100, JPY -> 1).

	Read from frappe's own Currency master so a tenant can correct it without a
	code change. Defaults to 100 when the currency is unknown or the master leaves
	``fraction_units`` blank — the overwhelmingly common case, and the same
	assumption ``to_paise`` already makes.
	"""
	if not currency:
		return PAISE_PER_UNIT
	units = frappe.db.get_value("Currency", currency, "fraction_units")
	return int(units) if units else PAISE_PER_UNIT


def is_paise_safe(company: str | None = None) -> bool:
	"""True when this tenant's currency quantises cleanly to 1/100 units."""
	currency = company_currency(company)
	if not currency:
		return True  # nothing configured yet -> nothing to mis-round
	return minor_units(currency) == PAISE_PER_UNIT


def assert_paise_safe(company: str | None = None) -> None:
	"""Throw unless the tenant's currency has exactly 100 minor units.

	Fails loudly and early rather than letting a 0- or 3-decimal currency produce
	allocations that are wrong by an order of magnitude.
	"""
	if is_paise_safe(company):
		return
	currency = company_currency(company)
	frappe.throw(
		f"NetGainz money handling assumes a currency with 100 minor units, but this "
		f"company's currency is {currency} ({minor_units(currency)} minor units). "
		"Profit First allocations and commissions cannot be computed safely — "
		"set a two-decimal company currency, or correct the Currency master.",
		title="Unsupported Currency",
	)


def assert_company_currency(doc_currency: str | None, company: str | None = None, *, what="document") -> None:
	"""Throw when a membership billing document is not in the company currency.

	``doc_currency`` empty is fine — ERPNext fills it from the company default.
	"""
	if not doc_currency:
		return
	base = company_currency(company)
	if not base or doc_currency == base:
		return
	frappe.throw(
		f"This {what} is in {doc_currency} but the books are kept in {base}. "
		"NetGainz bills every membership in the company's own currency — clear the "
		"member's billing currency override, or change the company currency.",
		title="Currency Mismatch",
	)


def pin_to_company_currency(doc, company: str | None = None) -> None:
	"""Raise ``doc`` in the tenant's OWN currency, explicitly — never by inference.

	WP-8's rule is one transaction currency per tenant, but a document that simply
	does not say so inherits whatever the default Selling price list happens to be.
	ERPNext seeds "Standard Selling" in **USD** at install and only the setup wizard
	re-denominates it, so on any tenant where that never happened, an invoice built
	from the price list comes out in USD against an INR ledger and ERPNext refuses
	it outright:

	    Party Account Debtors - X currency (INR) and document currency (USD)
	    should be same

	Membership invoices escape this because the Subscription carries the company's
	currency down. Anything that builds a Sales Invoice by hand does not, which is
	how a PT pack sale and the go-live part-month invoice ended up exposed.

	Call AFTER ``set_missing_values``: that is what fills the currency in from the
	party and the price list, so setting it earlier is simply overwritten. The rate
	is 1 because both sides are the same currency by construction.
	"""
	base = company_currency(company or doc.get("company"))
	if not base:
		return
	doc.currency = base
	doc.conversion_rate = 1.0
	# The price list side is validated separately; leaving it foreign would demand a
	# plc_conversion_rate for prices this document never reads (every rate is
	# passed in explicitly).
	doc.price_list_currency = base
	doc.plc_conversion_rate = 1.0


def assert_membership_billing_currency(customer: str | None, company: str | None = None) -> None:
	"""Guard the party side: a Customer with a foreign default currency would make
	ERPNext raise the membership's Sales Invoice in that currency."""
	if not customer:
		return
	assert_company_currency(
		frappe.db.get_value("Customer", customer, "default_currency"),
		company,
		what="member's billing currency",
	)
