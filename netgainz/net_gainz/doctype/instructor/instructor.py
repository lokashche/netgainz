# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Instructor(Document):
	def validate(self):
		self.normalize_commission()

	def normalize_commission(self):
		"""Keep the commission fields internally consistent.

		Commission Amount is meaningless without a commission type, so it is
		cleared when the type is "None" (or unset). For a "Percentage" coach the
		amount is a percent and must sit between 0 and 100; for "Fixed" / "Per
		Member" it is a rupee figure and simply may not be negative.
		"""
		if not self.commission_type or self.commission_type == "None":
			self.commission_amount = 0
			return

		amount = self.commission_amount or 0
		if amount < 0:
			frappe.throw("Commission Amount cannot be negative.")
		if self.commission_type == "Percentage" and amount > 100:
			frappe.throw("A percentage commission cannot exceed 100%.")
