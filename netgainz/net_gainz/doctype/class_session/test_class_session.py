# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def _new_session(**kwargs):
	doc = frappe.new_doc("Class Session")
	doc.title = kwargs.pop("title", "Morning Strength")
	doc.start_time = kwargs.pop("start_time", "2026-07-01 07:00:00")
	for key, value in kwargs.items():
		setattr(doc, key, value)
	return doc


class TestClassSession(FrappeTestCase):
	def test_status_default_is_scheduled(self):
		"""A new Class Session defaults to Scheduled."""
		self.assertEqual(frappe.get_meta("Class Session").get_field("status").default, "Scheduled")

	def test_status_options(self):
		"""Class Session status offers Scheduled / Completed / Cancelled."""
		options = frappe.get_meta("Class Session").get_field("status").options
		self.assertEqual(options.split("\n"), ["Scheduled", "Completed", "Cancelled"])

	def test_zero_duration_rejected(self):
		"""A non-positive duration is rejected."""
		doc = _new_session(duration_mins=0)
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_negative_capacity_rejected(self):
		"""A negative capacity is rejected."""
		doc = _new_session(capacity=-5)
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_valid_session_passes(self):
		"""A well-formed session validates."""
		doc = _new_session(duration_mins=45, capacity=12)
		doc.validate()
		self.assertEqual(doc.duration_mins, 45)
