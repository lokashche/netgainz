# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import now_datetime


class PackSessionUse(Document):
	def validate(self):
		if not self.used_on:
			self.used_on = now_datetime()
