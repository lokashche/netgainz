# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""WP-8: multi-currency guards.

``calc.to_paise`` hard-codes 100 minor units. That is exact for INR and wrong by
an order of magnitude for JPY (0 decimals) or KWD (3), so the tenant's currency is
checked at the edges rather than making the pure maths currency-aware. Separately,
a membership must bill in the company's own currency — the product shows one
unlabelled money column and Profit First sums a single scalar.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz.accounting import billing, currency
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.profit_first import accounts as pf_accounts


class TestCurrencyGuards(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		self.company = pf_accounts.default_company()

	# ---- minor units ------------------------------------------------------ #
	def test_inr_is_paise_safe(self):
		self.assertEqual(currency.company_currency(self.company), "INR")
		self.assertEqual(currency.minor_units("INR"), 100)
		self.assertTrue(currency.is_paise_safe(self.company))
		currency.assert_paise_safe(self.company)  # must not raise

	def test_a_zero_decimal_currency_is_rejected(self):
		"""JPY has no minor unit at all — quantising it as paise would be 100x off."""
		frappe.db.set_value("Currency", "JPY", "fraction_units", 1)
		frappe.db.set_value("Company", self.company, "default_currency", "JPY")
		frappe.clear_cache()
		try:
			self.assertEqual(currency.minor_units("JPY"), 1)
			self.assertFalse(currency.is_paise_safe(self.company))
			with self.assertRaises(frappe.ValidationError):
				currency.assert_paise_safe(self.company)
		finally:
			frappe.db.set_value("Company", self.company, "default_currency", "INR")
			frappe.clear_cache()

	def test_unknown_currency_falls_back_to_paise(self):
		self.assertEqual(currency.minor_units("XYZ"), 100)
		self.assertEqual(currency.minor_units(None), 100)

	# ---- one transaction currency per tenant ------------------------------ #
	def test_company_currency_documents_pass(self):
		currency.assert_company_currency("INR", self.company)  # must not raise
		currency.assert_company_currency(None, self.company)  # unset is fine

	def test_foreign_currency_document_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			currency.assert_company_currency("USD", self.company, what="invoice")

	def test_member_with_a_foreign_billing_currency_cannot_be_subscribed(self):
		"""ERPNext would happily raise the invoice in USD; the product would then be
		adding dollars to rupees in the owner's totals."""
		ms = fx.enrol("CUR Foreign", amount=1000.0)
		customer = frappe.db.get_value("Member", ms.member, "customer")
		frappe.db.set_value("Customer", customer, "default_currency", "USD")

		with self.assertRaises(frappe.ValidationError):
			currency.assert_membership_billing_currency(customer, self.company)

		frappe.db.set_value("Customer", customer, "default_currency", None)
		currency.assert_membership_billing_currency(customer, self.company)  # must not raise

	# ---- the cash read converts to company currency ----------------------- #
	def test_cash_read_uses_the_reference_exchange_rate(self):
		"""Payment Entry Reference stores no base amount — only `allocated_amount`
		and its own `exchange_rate` — so the read must multiply, or a foreign-currency
		allocation is summed into the base total at face value."""
		ms = fx.enrol_and_collect("CUR Rate", amount=1000.0)
		customer = frappe.db.get_value("Member", ms.member, "customer")
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 100000)

		# Simulate a document booked at 2:1 against the company currency: the base
		# value of that same allocation must double.
		reference = frappe.db.get_value(
			"Payment Entry Reference", {"reference_doctype": "Sales Invoice"}, "name"
		)
		frappe.db.set_value("Payment Entry Reference", reference, "exchange_rate", 2)
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 200000)

	def test_zero_exchange_rate_is_treated_as_one(self):
		"""Older rows can carry 0; that must not silently zero the tenant's revenue."""
		ms = fx.enrol_and_collect("CUR Zero", amount=1000.0)
		customer = frappe.db.get_value("Member", ms.member, "customer")
		reference = frappe.db.get_value(
			"Payment Entry Reference", {"reference_doctype": "Sales Invoice"}, "name"
		)
		frappe.db.set_value("Payment Entry Reference", reference, "exchange_rate", 0)
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 100000)

	def test_recording_a_payment_on_a_foreign_invoice_is_blocked(self):
		ms = fx.enrol("CUR Pay", amount=1000.0)
		si = ms.current_sales_invoice
		outstanding = flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))
		frappe.db.set_value("Sales Invoice", si, "currency", "USD")
		with self.assertRaises(frappe.ValidationError):
			billing.record_payment(ms.name, outstanding, "Cash", today())
