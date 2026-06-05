# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMembershipPlan(FrappeTestCase):
	def test_plan_name_is_document_name(self):
		"""autoname=field:plan_name means doc.name equals the plan_name value."""
		doc = frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": "Test Plan 30 Day",
				"duration_in_days": 30,
				"amount": 1000.0,
			}
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.name, "Test Plan 30 Day")
		doc.delete()

	def test_amount_required_to_be_set(self):
		"""A plan inserted with a specific amount stores that amount correctly."""
		doc = frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": "Test Plan Amount Check",
				"duration_in_days": 30,
				"amount": 1500.0,
			}
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.amount, 1500.0)
		doc.delete()
