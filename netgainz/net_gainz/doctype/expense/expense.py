# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Expense(Document):
	def validate(self):
		if self.amount is not None and self.amount <= 0:
			frappe.throw("Amount must be greater than zero.")
		if not self.is_recurring:
			self.frequency = ""
