# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase


class TestGymExpense(FrappeTestCase):
	def _new_exp(self):
		doc = frappe.new_doc("Gym Expense")
		doc.date = date.today().isoformat()
		return doc

	def test_validate_clears_frequency_when_not_recurring(self):
		doc = self._new_exp()
		doc.amount = 500
		doc.is_recurring = 0
		doc.frequency = "Monthly"
		doc.validate()
		self.assertEqual(doc.frequency, "")

	def test_validate_keeps_frequency_when_recurring(self):
		doc = self._new_exp()
		doc.amount = 500
		doc.is_recurring = 1
		doc.frequency = "Monthly"
		doc.validate()
		self.assertEqual(doc.frequency, "Monthly")

	def test_validate_rejects_zero_amount(self):
		doc = self._new_exp()
		doc.amount = 0
		doc.is_recurring = 0
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_validate_rejects_negative_amount(self):
		doc = self._new_exp()
		doc.amount = -100
		doc.is_recurring = 0
		self.assertRaises(frappe.ValidationError, doc.validate)
