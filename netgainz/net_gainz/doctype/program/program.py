# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Program(Document):
	def validate(self):
		# program_name is the autoname source, so a blank name would fail naming
		# with a cryptic error — guard it here with a clear message.
		if self.program_name:
			self.program_name = self.program_name.strip()
		if not self.program_name:
			frappe.throw("Program Name is required.")
