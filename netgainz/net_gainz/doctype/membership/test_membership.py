# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Membership controller tests (WP-11: one invoice-driven path).

The legacy `fee_collected`-vs-`tariff` unit tests are gone with the math they
covered — status, balance_due, due_date and next_renewal now all derive from the
membership's Sales Invoice, so these are integration tests against real billing.
`overdue_days` stays a pure controller calculation and is still unit-tested.
"""

from datetime import date, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestMembership(FrappeTestCase):
	def setUp(self):
		fx.ensure_cash_account()

	# ---- overdue_days: pure controller maths ----------------------------- #
	def test_overdue_days_zero_when_paid(self):
		doc = frappe.new_doc("Membership")
		doc.due_date = date.today() - timedelta(days=5)
		doc.status = "Paid"
		doc.calculate_overdue_days()
		self.assertEqual(doc.overdue_days, 0)

	def test_overdue_days_counts_past_due(self):
		doc = frappe.new_doc("Membership")
		doc.due_date = date.today() - timedelta(days=5)
		doc.status = "Pending"
		doc.calculate_overdue_days()
		self.assertEqual(doc.overdue_days, 5)

	def test_overdue_days_zero_before_due(self):
		doc = frappe.new_doc("Membership")
		doc.due_date = date.today() + timedelta(days=5)
		doc.status = "Pending"
		doc.calculate_overdue_days()
		self.assertEqual(doc.overdue_days, 0)

	def test_overdue_days_zero_without_due_date(self):
		doc = frappe.new_doc("Membership")
		doc.status = "Pending"
		doc.calculate_overdue_days()
		self.assertEqual(doc.overdue_days, 0)

	# ---- status / balance derive from the invoice (R4) ------------------- #
	def test_new_membership_is_pending_with_full_balance(self):
		ms = fx.enrol("MS Pending", amount=1000.0)
		self.assertTrue(ms.subscription, "billing is provisioned for every membership")
		self.assertEqual(ms.status, "Pending")
		grand = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		self.assertEqual(flt(ms.balance_due), grand)

	def test_status_paid_once_invoice_settled(self):
		ms = fx.enrol("MS Paid", amount=1000.0)
		fx.collect(ms)
		ms.reload()
		ms.save(ignore_permissions=True)  # re-derive from the now-settled invoice
		self.assertEqual(ms.status, "Paid")
		self.assertEqual(flt(ms.balance_due), 0.0)

	def test_status_partial_on_part_payment(self):
		ms = fx.enrol("MS Partial", amount=1000.0)
		outstanding = flt(
			frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount")
		)
		fx.collect(ms, amount=outstanding / 2)
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(ms.status, "Partial")
		self.assertGreater(flt(ms.balance_due), 0.0)

	def test_due_date_is_invoice_derived_not_typed(self):
		"""WP-11: a hand-typed due_date is overwritten by the invoice's."""
		ms = fx.enrol("MS DueDate", amount=1000.0)
		si_due = frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "due_date")
		ms.due_date = add_days(today(), 999)
		ms.save(ignore_permissions=True)
		self.assertEqual(str(ms.due_date), str(si_due))

	def test_next_renewal_follows_subscription_period(self):
		ms = fx.enrol("MS Renewal", amount=1000.0)
		start = frappe.db.get_value("Subscription", ms.subscription, "current_invoice_start")
		self.assertEqual(str(ms.next_renewal), str(start))
