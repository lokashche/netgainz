# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Tests for the Stage 7 WP-6 cash/accrual toggle -> deferred revenue wiring."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from netgainz.net_gainz.accounting import billing, deferred
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.profit_first import accounts as pf_accounts

SAC = "999723"


class TestDeferred(FrappeTestCase):
	def setUp(self):
		self.company = pf_accounts.default_company()
		cash = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Cash", "is_group": 0}, "name"
		)
		if cash and not frappe.db.get_value("Company", self.company, "default_cash_account"):
			frappe.db.set_value("Company", self.company, "default_cash_account", cash)
		# Singles + their cache can survive the per-test rollback; reset explicitly.
		frappe.db.set_single_value("Business Settings", "accounting_method", "Cash")
		frappe.db.set_single_value("Business Settings", "billing_cutover_date", None)

	def _set_method(self, method):
		bs = frappe.get_single("Business Settings")
		bs.accounting_method = method
		bs.save(ignore_permissions=True)

	def _plan(self, name, amount=12000.0, duration=365):
		return frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": name,
				"duration_in_days": duration,
				"amount": amount,
				"gst_hsn_code": SAC,
			}
		).insert(ignore_permissions=True)

	# ---- toggle + config ------------------------------------------------- #
	def test_defaults_to_cash(self):
		self.assertEqual(deferred.accounting_method(), "Cash")
		self.assertFalse(deferred.is_accrual())

	def test_setup_creates_account_and_scheduler_config(self):
		result = deferred.setup_deferred_revenue(self.company)
		account = result["deferred_revenue_account"]
		self.assertTrue(frappe.db.exists("Account", account))
		self.assertEqual(
			frappe.db.get_value("Account", account, "root_type"),
			"Liability",
			"deferred revenue is a liability",
		)
		self.assertEqual(
			frappe.db.get_value("Company", self.company, "default_deferred_revenue_account"), account
		)
		self.assertTrue(
			frappe.db.get_single_value("Accounts Settings", "automatically_process_deferred_accounting_entry")
		)
		self.assertEqual(
			frappe.db.get_single_value("Accounts Settings", "book_deferred_entries_based_on"), "Months"
		)

	def test_accounting_basis_field_removed(self):
		self.assertIsNone(
			frappe.get_meta("Profit First Settings").get_field("accounting_basis"),
			"the stale accounting_basis field must be gone",
		)

	# ---- toggle drives Item.enable_deferred_revenue ---------------------- #
	def test_toggle_accrual_enables_then_disables_item_deferral(self):
		plan = self._plan("WP6 Toggle Plan")
		plan.reload()
		self.assertTrue(plan.item)
		self.assertFalse(
			frappe.db.get_value("Item", plan.item, "enable_deferred_revenue"), "cash default -> not deferred"
		)

		self._set_method("Accrual")
		self.assertTrue(
			frappe.db.get_value("Item", plan.item, "enable_deferred_revenue"), "accrual -> Item deferred"
		)
		self.assertTrue(
			frappe.db.get_value("Company", self.company, "default_deferred_revenue_account"),
			"enabling accrual provisions the Company deferred account",
		)

		self._set_method("Cash")
		self.assertFalse(
			frappe.db.get_value("Item", plan.item, "enable_deferred_revenue"), "back to cash -> not deferred"
		)

	def test_plan_provisioned_under_accrual_is_deferred(self):
		self._set_method("Accrual")
		plan = self._plan("WP6 Accrual-born Plan")
		plan.reload()
		self.assertTrue(
			frappe.db.get_value("Item", plan.item, "enable_deferred_revenue"),
			"a plan created while accrual is on gets a deferred Item",
		)

	# ---- end to end: an accrual membership invoice defers revenue -------- #
	def test_accrual_membership_invoice_defers_to_liability(self):
		self._set_method("Accrual")
		frappe.db.set_single_value("Business Settings", "billing_cutover_date", today())
		deferred_account = frappe.db.get_value("Company", self.company, "default_deferred_revenue_account")

		plan = self._plan("WP6 Annual Plan")  # 365 days -> Year x1
		member = frappe.get_doc(
			{"doctype": "Member", "full_name": "WP6 Member", "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms = frappe.get_doc({"doctype": "Membership", "member": member.name}).insert(ignore_permissions=True)
		ms.reload()
		self.assertTrue(ms.current_sales_invoice, "cut-over membership should be billed")

		item = frappe.db.get_value(
			"Sales Invoice Item",
			{"parent": ms.current_sales_invoice},
			["enable_deferred_revenue", "service_start_date", "service_end_date"],
			as_dict=True,
		)
		self.assertTrue(item.enable_deferred_revenue, "SI item deferred (native propagation from the Item)")
		self.assertTrue(
			item.service_start_date and item.service_end_date, "service period set from the subscription"
		)

		# The submitted invoice credits the Deferred Revenue liability, not income.
		deferred_credit = frappe.db.get_value(
			"GL Entry",
			{"voucher_no": ms.current_sales_invoice, "account": deferred_account, "is_cancelled": 0},
			"credit",
		)
		self.assertTrue(deferred_credit and deferred_credit > 0, "revenue booked to the deferred liability")


class TestDeferredServicePeriod(FrappeTestCase):
	"""The recognition WINDOW, not just the amount (found by the Stage 8 DS-7 pass).

	ERPNext's ``set_missing_values`` overwrites the Subscription's service dates with
	``add_months(start, Item.no_of_months)`` — and WP-6 deliberately never sets
	``no_of_months``, so the window used to collapse onto a single day and a month's
	membership was recognised entirely on day one.
	"""

	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		self._original = deferred.accounting_method()
		frappe.db.set_single_value("Business Settings", "accounting_method", "Accrual")
		deferred.setup_deferred_revenue(pf_accounts.default_company())
		self.addCleanup(frappe.db.set_single_value, "Business Settings", "accounting_method", self._original)

	def test_the_service_window_is_the_period_billed(self):
		plan = fx.make_plan("Deferred Window Plan", amount=3000.0)
		deferred.sync_item_deferred_revenue(frappe.db.get_value("Membership Plan", plan.name, "item"), True)
		member = fx.make_member("Deferred Window Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()

		invoice = frappe.get_doc("Sales Invoice", ms.current_sales_invoice)
		item = invoice.items[0]
		self.assertTrue(item.enable_deferred_revenue)
		self.assertEqual(getdate(item.service_start_date), getdate(invoice.from_date))
		self.assertEqual(getdate(item.service_end_date), getdate(invoice.to_date))
		self.assertGreater(
			getdate(item.service_end_date),
			getdate(item.service_start_date),
			"a month of membership is not earned in a single day",
		)
