# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Business Branch — the NetGainz branch dimension (Stage 7 WP-3, Stage 10.1).

A tenant runs on ONE ERPNext Company; its physical locations are modelled as
Business Branches, each mapped to a Cost Center so revenue/expenses can be
reported per branch without minting separate companies. Every NetGainz financial
doc carries a ``branch`` link, and the GL builders post against the branch's
``cost_center`` (falling back to the Company default). A separate Company is used
only for a separate PAN (franchise/subsidiary); multi-GSTIN within one PAN is a
later, address-driven refinement.

Stage 10.1 rules, enforced here so every path (owner-app, import, Desk) obeys them:

* **Every branch gets its own Cost Center, silently.** A branch without one posts
  to the company default — i.e. into the first branch's figures — so per-branch
  profit would be quietly wrong.
* **Exactly one default branch,** found by the ``is_default`` flag, never by name.
  The first branch is created as "Main"; the owner renames it to the real location.
* **The default branch cannot be switched off.** Something must receive the
  records that name no branch.
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
		if self.is_default and self.disabled:
			frappe.throw("The default branch cannot be switched off. Make another branch the default first.")
		if not self.is_default and not self.is_new() and self._was_default():
			frappe.throw("Make another branch the default instead — there must always be one.")

	def before_insert(self):
		if not self.cost_center and self.company:
			self.cost_center = _provision_cost_center(self.branch_name, self.company)

	def on_update(self):
		if self.is_default:
			# One default: taking the flag moves it here.
			frappe.db.sql(
				"UPDATE `tabBusiness Branch` SET is_default = 0 WHERE name != %s AND is_default = 1",
				self.name,
			)

	def _was_default(self) -> bool:
		return bool(frappe.db.get_value("Business Branch", self.name, "is_default"))


def _provision_cost_center(branch_name: str, company: str) -> str | None:
	"""Find or create a leaf Cost Center named after the branch, under the company's
	root. Idempotent: a re-created or imported branch reuses its old cost center."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	existing = frappe.db.get_value(
		"Cost Center", {"name": f"{branch_name} - {abbr}", "company": company, "is_group": 0}, "name"
	)
	if existing:
		return existing
	root = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 1, "parent_cost_center": ["in", ["", None]]},
		"name",
	) or frappe.db.get_value("Cost Center", {"company": company, "is_group": 1}, "name")
	if not root:
		return None
	return (
		frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": branch_name,
				"parent_cost_center": root,
				"company": company,
				"is_group": 0,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)
