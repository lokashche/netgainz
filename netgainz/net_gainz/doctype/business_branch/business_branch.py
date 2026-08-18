# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Business Branch — the NetGainz branch dimension (Stage 7 WP-3).

A tenant runs on ONE ERPNext Company; its physical locations are modelled as
Business Branches, each mapped to a Cost Center so revenue/expenses can be
reported per branch without minting separate companies. Every NetGainz financial
doc carries a ``branch`` link, and the GL builders post against the branch's
``cost_center`` (falling back to the Company default). A separate Company is used
only for a separate PAN (franchise/subsidiary); multi-GSTIN within one PAN is a
later, address-driven refinement.
"""

import frappe
from frappe.model.document import Document


class BusinessBranch(Document):
	def validate(self):
		if not self.company:
			from netgainz.net_gainz.profit_first import accounts as pf_accounts

			self.company = pf_accounts.default_company()
		if self.cost_center and self.company:
			cc_company = frappe.db.get_value("Cost Center", self.cost_center, "company")
			if cc_company and cc_company != self.company:
				frappe.throw(f"Cost Center {self.cost_center} belongs to {cc_company}, not {self.company}.")
