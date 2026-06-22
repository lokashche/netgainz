# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ClassSession(Document):
	def validate(self):
		if self.duration_mins is not None and self.duration_mins <= 0:
			frappe.throw("Duration must be greater than zero.")
		if self.capacity is not None and self.capacity < 0:
			frappe.throw("Capacity cannot be negative.")

	def booked_count(self) -> int:
		"""Number of members currently holding a slot (anything not cancelled)."""
		return frappe.db.count(
			"Class Booking",
			{"class_session": self.name, "status": ["!=", "Cancelled"]},
		)
