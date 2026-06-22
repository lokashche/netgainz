# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestClassBooking(FrappeTestCase):
	def setUp(self):
		self.member = frappe.get_doc(
			{"doctype": "Member", "full_name": "Booking Test Member One"}
		).insert(ignore_permissions=True)
		self.member2 = frappe.get_doc(
			{"doctype": "Member", "full_name": "Booking Test Member Two"}
		).insert(ignore_permissions=True)
		self.session = frappe.get_doc(
			{
				"doctype": "Class Session",
				"title": "Capacity Test Class",
				"start_time": "2026-07-01 07:00:00",
				"capacity": 1,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		for name in frappe.get_all(
			"Class Booking", filters={"class_session": self.session.name}, pluck="name"
		):
			frappe.delete_doc("Class Booking", name, ignore_permissions=True, force=True)
		frappe.delete_doc("Class Session", self.session.name, ignore_permissions=True, force=True)
		frappe.delete_doc("Member", self.member.name, ignore_permissions=True, force=True)
		frappe.delete_doc("Member", self.member2.name, ignore_permissions=True, force=True)

	def _book(self, member, status="Booked"):
		return frappe.get_doc(
			{
				"doctype": "Class Booking",
				"class_session": self.session.name,
				"member": member,
				"status": status,
			}
		).insert(ignore_permissions=True)

	def test_check_in_stamped_on_attended(self):
		"""Marking a booking Attended stamps the check-in time."""
		doc = frappe.new_doc("Class Booking")
		doc.status = "Attended"
		doc.stamp_check_in()
		self.assertTrue(doc.check_in_time)

	def test_check_in_cleared_when_not_attended(self):
		"""A non-Attended status clears any check-in time."""
		doc = frappe.new_doc("Class Booking")
		doc.status = "Booked"
		doc.check_in_time = "2026-07-01 07:05:00"
		doc.stamp_check_in()
		self.assertIsNone(doc.check_in_time)

	def test_double_booking_rejected(self):
		"""A member cannot be booked twice into the same class."""
		self._book(self.member.name)
		dup = frappe.get_doc(
			{
				"doctype": "Class Booking",
				"class_session": self.session.name,
				"member": self.member.name,
			}
		)
		self.assertRaises(frappe.ValidationError, dup.insert, ignore_permissions=True)

	def test_capacity_enforced(self):
		"""Booking past the class capacity is rejected."""
		self._book(self.member.name)  # fills the single slot
		over = frappe.get_doc(
			{
				"doctype": "Class Booking",
				"class_session": self.session.name,
				"member": self.member2.name,
			}
		)
		self.assertRaises(frappe.ValidationError, over.insert, ignore_permissions=True)

	def test_cancelled_booking_frees_capacity(self):
		"""A cancelled booking does not count against capacity."""
		first = self._book(self.member.name)
		first.status = "Cancelled"
		first.save(ignore_permissions=True)
		# The freed slot now lets a second member book.
		second = self._book(self.member2.name)
		self.assertEqual(second.status, "Booked")
