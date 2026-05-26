# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMember(FrappeTestCase):
	def test_default_status_is_active(self):
		doc = frappe.new_doc("Member")
		doc.full_name = "Test Member"
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.status, "Active")
		doc.delete()

	def test_status_options(self):
		meta = frappe.get_meta("Member")
		field = meta.get_field("status")
		self.assertIn("Active", field.options)
		self.assertIn("Inactive", field.options)
		self.assertIn("Frozen", field.options)

	def test_autoname_uses_gym_settings_prefix(self):
		with patch("frappe.db.get_single_value", return_value="TEST-") as mock_gsv:
			doc = frappe.new_doc("Member")
			doc.full_name = "Autoname Test Member"
			doc.autoname()
			mock_gsv.assert_called_once_with("Gym Settings", "member_id_prefix")
			self.assertTrue(doc.name.startswith("TEST-"))
