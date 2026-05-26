# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestExpenseCategory(FrappeTestCase):
	def test_category_name_is_document_name(self):
		doc = frappe.new_doc("Expense Category")
		doc.category_name = "Test Utilities Stage3"
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.name, "Test Utilities Stage3")
		doc.delete()

	def test_description_is_optional(self):
		doc = frappe.new_doc("Expense Category")
		doc.category_name = "Test Rent Stage3"
		doc.insert(ignore_permissions=True)
		self.assertIsNone(doc.description or None)
		doc.delete()
