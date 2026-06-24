# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BusinessSettings(Document):
	def validate(self):
		self._guard_billing_cutover_date()

	def _guard_billing_cutover_date(self):
		"""The billing cut-over date is one-way once real billing exists. Moving or
		clearing it after memberships have been billed through ERPNext would orphan
		already-collected Payment-Entry revenue (the cash read keys off subscription
		presence, so a moved date can't retroactively re-home it). Block the change;
		historical migration is WP-7's job, not a settings edit."""
		if not self.has_value_changed("billing_cutover_date"):
			return
		if frappe.db.exists("Sales Invoice", {"subscription": ["is", "set"], "docstatus": 1}):
			frappe.throw(
				"Billing Cut-over Date can't be changed once memberships have been billed "
				"through ERPNext — it would orphan already-collected revenue."
			)
