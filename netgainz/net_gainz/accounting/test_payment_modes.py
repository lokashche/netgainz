# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Tests for the payment-mode -> Mode of Payment -> paid-to account mapping."""

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.accounting import payment_modes
from netgainz.net_gainz.profit_first import accounts as pf_accounts


class TestPaymentModes(FrappeTestCase):
	def test_modes_mirror_subscription_options(self):
		"""PAYMENT_MODES must stay in sync with Subscription.payment_mode options —
		the value set is duplicated on the frontend too, so guard against drift."""
		field = frappe.get_meta("Membership").get_field("payment_mode")
		options = tuple(o for o in (field.options or "").split("\n") if o)
		self.assertEqual(set(payment_modes.PAYMENT_MODES), set(options))

	def test_cash_vs_bank_classification(self):
		self.assertEqual(payment_modes._mode_type("Cash"), "Cash")
		self.assertEqual(payment_modes._mode_type("UPI"), "Bank")
		self.assertEqual(payment_modes._mode_type("Online"), "Bank")

	def test_setup_provisions_modes_and_resolves_accounts(self):
		company = pf_accounts.default_company()
		# Reuse the company cash account for both legs so the test needs no separate
		# bank account; we only assert the wiring, not the cash-vs-bank choice.
		cash = frappe.get_cached_value("Company", company, "default_cash_account")
		result = payment_modes.setup_payment_modes(company, cash_account=cash, bank_account=cash)

		self.assertEqual(set(result["accounts"]), set(payment_modes.PAYMENT_MODES))
		for mode in payment_modes.PAYMENT_MODES:
			self.assertTrue(frappe.db.exists("Mode of Payment", mode))
			self.assertEqual(payment_modes.paid_to_account(company, mode), cash)
