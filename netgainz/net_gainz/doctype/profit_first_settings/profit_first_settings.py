# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ProfitFirstSettings(Document):
	def validate(self):
		self.validate_tier_bands()
		self.validate_accounts()
		self.normalise_allocation_days()

	def normalise_allocation_days(self):
		"""Clean the allocation-days list to a sorted, de-duplicated, in-range form."""
		from netgainz.net_gainz.profit_first.schedule import parse_allocation_days

		days = parse_allocation_days(self.allocation_days)
		self.allocation_days = ", ".join(str(d) for d in days)

	def validate_tier_bands(self):
		"""Each tier row's four target percentages must sum to exactly 100."""
		for row in self.tiers:
			total = flt(row.tap_profit) + flt(row.tap_owners_pay) + flt(row.tap_tax) + flt(row.tap_opex)
			if round(total, 2) != 100.0:
				frappe.throw(
					f"Tier {row.tier_code or row.idx}: the four target percentages must sum to 100 "
					f"(currently {round(total, 2)})."
				)

	def validate_accounts(self):
		"""Account roles must be unique across the table."""
		seen = set()
		for row in self.accounts:
			if row.account_role in seen:
				frappe.throw(f"Account role '{row.account_role}' is listed more than once.")
			seen.add(row.account_role)
