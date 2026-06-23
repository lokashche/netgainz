# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestClassSchedule(FrappeTestCase):
	def _new(self, **kwargs):
		doc = frappe.new_doc("Session Schedule")
		doc.title = kwargs.pop("title", "Morning Batch")
		doc.start_time = kwargs.pop("start_time", "07:30:00")
		for key, value in kwargs.items():
			setattr(doc, key, value)
		return doc

	def tearDown(self):
		for sched in frappe.get_all(
			"Session Schedule", filters={"title": "Morning Batch"}, pluck="name"
		):
			for sess in frappe.get_all(
				"Session", filters={"class_schedule": sched}, pluck="name"
			):
				frappe.delete_doc("Session", sess, ignore_permissions=True, force=True)
			frappe.delete_doc("Session Schedule", sched, ignore_permissions=True, force=True)

	def test_requires_a_weekday(self):
		"""A schedule with no weekday selected is rejected."""
		doc = self._new()  # no on_* set
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_weekday_set(self):
		"""weekday_set reflects the checked days (Mon=0, Wed=2)."""
		doc = self._new(on_monday=1, on_wednesday=1)
		self.assertEqual(doc.weekday_set(), {0, 2})

	def test_generate_is_idempotent(self):
		"""Generating sessions creates the Mondays in the window, and a second run
		creates none (no duplicates)."""
		doc = self._new(on_monday=1)
		doc.insert(ignore_permissions=True)  # after_insert generates once

		first = frappe.db.count("Session", {"class_schedule": doc.name})
		self.assertGreaterEqual(first, 1)
		# Every generated session must be a Monday.
		for s in frappe.get_all(
			"Session", filters={"class_schedule": doc.name}, fields=["start_time"]
		):
			self.assertEqual(frappe.utils.getdate(s.start_time).weekday(), 0)

		again = doc.generate()
		self.assertEqual(again, 0)
		self.assertEqual(frappe.db.count("Session", {"class_schedule": doc.name}), first)
