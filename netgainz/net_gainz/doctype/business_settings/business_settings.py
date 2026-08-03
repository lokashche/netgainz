# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BusinessSettings(Document):
	def on_update(self):
		self._sync_accounting_method()

	def _sync_accounting_method(self):
		"""When the Cash/Accrual toggle changes, drive deferred revenue on every
		membership Item to match (Accrual -> defer income over the service period;
		Cash -> book on invoice). Enabling accrual also provisions the deferred
		account + scheduler config. Profit First is unaffected (always cash)."""
		if not self.has_value_changed("accounting_method"):
			return
		from netgainz.net_gainz.accounting import deferred

		deferred.sync_membership_items(accrual=(self.accounting_method == "Accrual"))
