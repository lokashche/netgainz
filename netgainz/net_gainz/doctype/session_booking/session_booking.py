# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class SessionBooking(Document):
	def validate(self):
		self.stamp_check_in()
		if self.status != "Cancelled":
			self.prevent_double_booking()
			self.enforce_capacity()

	def stamp_check_in(self):
		"""Record when a member is checked in; clear it if they are no longer
		marked Attended."""
		if self.status == "Attended":
			if not self.check_in_time:
				self.check_in_time = now_datetime()
		else:
			self.check_in_time = None

	def prevent_double_booking(self):
		existing = frappe.db.exists(
			"Session Booking",
			{
				"class_session": self.class_session,
				"member": self.member,
				"status": ["!=", "Cancelled"],
				"name": ["!=", self.name or ""],
			},
		)
		if existing:
			frappe.throw(f"{self.member} is already booked for this class ({existing}).")

	def enforce_capacity(self):
		session = frappe.get_doc("Session", self.class_session)
		if session.status == "Cancelled":
			frappe.throw("This class has been cancelled — no new bookings.")

		capacity = session.capacity or 0
		if capacity <= 0:
			return  # 0 means unlimited

		taken = frappe.db.count(
			"Session Booking",
			{
				"class_session": self.class_session,
				"status": ["!=", "Cancelled"],
				"name": ["!=", self.name or ""],
			},
		)
		if taken >= capacity:
			frappe.throw(f"This class is full ({capacity} booked).")
