# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestProgram(FrappeTestCase):
	def test_is_active_default_on(self):
		"""A new Program is active by default."""
		self.assertEqual(frappe.get_meta("Program").get_field("is_active").default, "1")

	def test_blank_name_rejected(self):
		"""A Program with no name is rejected with a clear message."""
		doc = frappe.new_doc("Program")
		doc.program_name = "   "
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_autonames_to_program_name(self):
		"""A Program's id is its (trimmed) program name."""
		doc = frappe.new_doc("Program")
		doc.program_name = "  Strength 101  "
		doc.insert(ignore_permissions=True)
		try:
			self.assertEqual(doc.name, "Strength 101")
		finally:
			doc.delete(ignore_permissions=True)
