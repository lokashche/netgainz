# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class Member(Document):
	def autoname(self):
		prefix = frappe.db.get_single_value("Business Settings", "member_id_prefix") or "MEM-"
		self.name = make_autoname(f"{prefix}.####")
