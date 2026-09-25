# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Tests for the payment-mode -> Mode of Payment -> paid-to account mapping."""

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.accounting import billing, payment_modes
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.profit_first import accounts as pf_accounts


def _forget_mode(mode):
	"""Put the site back to a fresh install for one mode: ERPNext ships Cash, Cheque,
	Credit Card, Wire Transfer and Bank Draft, but no UPI / Card / Bank Transfer."""
	frappe.db.delete("Mode of Payment Account", {"parent": mode})
	frappe.db.delete("Mode of Payment", mode)


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

	# ---- a fresh site: nothing set up, nobody opens Desk ------------------- #
	def test_a_payment_mode_is_created_on_first_use(self):
		company = pf_accounts.default_company()
		_forget_mode("UPI")
		payment_modes.paid_to_account(company, "UPI")
		self.assertEqual(frappe.db.get_value("Mode of Payment", "UPI", "type"), "Bank")

	def test_a_missing_default_bank_account_is_created_and_remembered(self):
		company = pf_accounts.default_company()
		_forget_mode("Bank Transfer")
		frappe.db.set_value("Company", company, "default_bank_account", None)
		frappe.clear_document_cache("Company", company)

		account = payment_modes.paid_to_account(company, "Bank Transfer")

		self.assertEqual(frappe.db.get_value("Account", account, "account_type"), "Bank")
		self.assertEqual(frappe.db.get_value("Company", company, "default_bank_account"), account)
		# Idempotent: asking again lands in the same ledger, no second account.
		self.assertEqual(payment_modes.paid_to_account(company, "Bank Transfer"), account)

	def test_a_upi_payment_posts_on_a_fresh_site(self):
		"""The failure a new gym hit: "Could not find Mode of Payment: UPI" on its first
		digital payment, fixable only in Desk."""
		fx.clear_billing_data()
		company = pf_accounts.default_company()
		_forget_mode("UPI")
		frappe.db.set_value("Company", company, "default_bank_account", None)
		frappe.clear_document_cache("Company", company)

		ms = fx.enrol("PM Fresh UPI", amount=800.0)
		pe = fx.collect(ms, payment_mode="UPI")

		posted = frappe.db.get_value(
			"Payment Entry", pe, ["docstatus", "mode_of_payment", "paid_to"], as_dict=True
		)
		self.assertEqual(posted.docstatus, 1)
		self.assertEqual(posted.mode_of_payment, "UPI")
		self.assertEqual(frappe.db.get_value("Account", posted.paid_to, "account_type"), "Bank")

	def test_a_upi_payment_without_a_reference_uses_the_invoice(self):
		"""The payment screen has no reference box. ERPNext demands one for money into a
		bank account, so without this every UPI / card payment from the owner-app failed."""
		fx.clear_billing_data()
		ms = fx.enrol("PM No Ref", amount=800.0)
		pe = fx.collect(ms, payment_mode="UPI")
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "reference_no"), ms.current_sales_invoice)

	def test_a_reference_the_desk_typed_is_kept(self):
		fx.clear_billing_data()
		ms = fx.enrol("PM Typed Ref", amount=800.0)
		fx.ensure_cash_account()
		pe = billing.record_membership_payment(ms.name, 800.0, payment_mode="UPI", reference_no="UTR123456")[
			"payment_entry"
		]
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "reference_no"), "UTR123456")
