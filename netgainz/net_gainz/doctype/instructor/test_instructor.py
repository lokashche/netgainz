# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def _new_coach(**kwargs):
	doc = frappe.new_doc("Instructor")
	doc.coach_name = kwargs.pop("coach_name", "Test Coach")
	for key, value in kwargs.items():
		setattr(doc, key, value)
	return doc


class TestCoach(FrappeTestCase):
	def test_status_default_is_active(self):
		"""A new Coach defaults to Active status."""
		self.assertEqual(frappe.get_meta("Instructor").get_field("status").default, "Active")

	def test_status_options(self):
		"""Coach status is limited to Active / Inactive."""
		options = frappe.get_meta("Instructor").get_field("status").options
		self.assertEqual(options, "Active\nInactive")

	def test_commission_type_options(self):
		"""Commission type offers None / Fixed / Per Member / Percentage."""
		options = frappe.get_meta("Instructor").get_field("commission_type").options
		self.assertEqual(options.split("\n"), ["None", "Fixed", "Per Member", "Percentage"])

	def test_amount_cleared_when_type_none(self):
		"""Commission Amount is wiped when the commission type is None."""
		doc = _new_coach(commission_type="None", commission_amount=500)
		doc.validate()
		self.assertEqual(doc.commission_amount, 0)

	def test_amount_cleared_when_type_unset(self):
		"""Commission Amount is wiped when no commission type is chosen."""
		doc = _new_coach(commission_amount=500)
		doc.validate()
		self.assertEqual(doc.commission_amount, 0)

	def test_negative_amount_rejected(self):
		"""A negative commission amount is rejected."""
		doc = _new_coach(commission_type="Fixed", commission_amount=-1)
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_percentage_over_100_rejected(self):
		"""A percentage commission above 100% is rejected."""
		doc = _new_coach(commission_type="Percentage", commission_amount=120)
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_valid_percentage_passes(self):
		"""A 10% commission validates and is preserved."""
		doc = _new_coach(commission_type="Percentage", commission_amount=10)
		doc.validate()
		self.assertEqual(doc.commission_amount, 10)
