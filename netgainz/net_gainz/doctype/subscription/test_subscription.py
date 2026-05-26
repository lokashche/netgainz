# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

from datetime import date, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSubscription(FrappeTestCase):
	def _new_sub(self):
		"""Return an unsaved Subscription doc for unit-level controller tests."""
		return frappe.new_doc("Subscription")

	def test_balance_due_calculation(self):
		"""balance_due = tariff - fee_collected."""
		doc = self._new_sub()
		doc.tariff = 1000
		doc.fee_collected = 400
		doc.calculate_balance_due()
		self.assertEqual(doc.balance_due, 600)

	def test_status_paid_when_full_amount_collected(self):
		"""Status becomes Paid when fee_collected >= tariff and due_date is in the future."""
		doc = self._new_sub()
		doc.tariff = 1000
		doc.fee_collected = 1000
		doc.due_date = date.today() + timedelta(days=30)
		doc.auto_update_status()
		self.assertEqual(doc.status, "Paid")

	def test_status_overdue_when_past_due(self):
		"""Status becomes Overdue when due_date has passed and nothing was collected."""
		doc = self._new_sub()
		doc.tariff = 1000
		doc.fee_collected = 0
		doc.due_date = date.today() - timedelta(days=5)
		doc.auto_update_status()
		self.assertEqual(doc.status, "Overdue")

	def test_status_partial_when_partial_amount(self):
		"""Status is Partial when some (but not all) fees are collected and due_date is future."""
		doc = self._new_sub()
		doc.tariff = 1000
		doc.fee_collected = 500
		doc.due_date = date.today() + timedelta(days=10)
		doc.auto_update_status()
		self.assertEqual(doc.status, "Partial")
