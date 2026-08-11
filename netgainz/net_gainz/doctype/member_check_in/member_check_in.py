# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import now_datetime


class MemberCheckin(Document):
	def validate(self):
		# Stamped server-side so a desk tap needs no clock; a Manual entry may
		# backdate a missed visit, so an explicit value is kept as given.
		if not self.timestamp:
			self.timestamp = now_datetime()
