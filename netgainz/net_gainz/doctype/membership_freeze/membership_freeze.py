# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class MembershipFreeze(Document):
	def validate(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw("Frozen To cannot be before Frozen From.")
		# Filled here (not fetch_from) so the branch stamp's member-inheritance
		# sees a member even when the caller only supplied the membership.
		if self.membership and not self.member:
			self.member = frappe.db.get_value("Membership", self.membership, "member")
		if self.member and not self.member_name:
			self.member_name = frappe.db.get_value("Member", self.member, "full_name")
