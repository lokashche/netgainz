# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Enquiry(Document):
	def validate(self):
		# Lost + reason is the cheapest marketing insight a gym ever gets — a bare
		# "Lost" tells the owner nothing next month.
		if self.status == "Lost" and not (self.lost_reason or "").strip():
			frappe.throw("Record why this enquiry was lost — pick or type a reason.")
		# Joined is the conversion's outcome, not a checkbox: without the member
		# link the pipeline would count a join that never produced a member.
		if self.status == "Joined" and not self.member:
			frappe.throw('Use "Convert to Member" — Joined is set by the conversion.')
