# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Fitness / gym services SAC — the same constant the Membership Plan uses.
DEFAULT_HSN_SAC = "999723"


class SessionPack(Document):
	def validate(self):
		if (self.sessions or 0) <= 0:
			frappe.throw("A pack needs at least one session.")
		if (self.validity_days or 0) <= 0:
			frappe.throw("Validity must be at least one day.")
		if (self.price or 0) <= 0:
			frappe.throw("A pack needs a price.")
		# HSN/SAC is mandatory to bill at all (india_compliance requires it on a
		# sales Item) — default it the same way plans do, so a pack can never be
		# silently unsellable.
		if not self.gst_hsn_code:
			self.gst_hsn_code = (
				frappe.db.get_single_value("Business Settings", "default_hsn_sac") or DEFAULT_HSN_SAC
			)
