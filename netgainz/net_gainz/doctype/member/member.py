# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class Member(Document):
	def autoname(self):
		# Preserve an explicitly supplied member code (e.g. the gym's existing
		# KE#### register imported from their spreadsheet) as the record ID.
		# Otherwise generate the next ID from the owner-configurable prefix and
		# mirror it back onto member_code so the two always match.
		if self.member_code:
			self.name = self.member_code
			return
		prefix = frappe.db.get_single_value("Business Settings", "member_id_prefix") or "MEM-"
		self.name = make_autoname(f"{prefix}.####")
		self.member_code = self.name
