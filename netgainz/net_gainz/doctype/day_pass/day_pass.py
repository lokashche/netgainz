# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import today


class DayPass(Document):
	def validate(self):
		if not self.visited_on:
			self.visited_on = today()
