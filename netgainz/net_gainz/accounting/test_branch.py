# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Tests for the Stage 7 WP-3 branch dimension: the branch helper (Main seeding,
cost-center resolution) and branch stamping on the financial doctypes."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from netgainz.net_gainz.accounting import branch
from netgainz.net_gainz.profit_first import accounts as pf_accounts


def _root_cost_center(company):
	return frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 1, "parent_cost_center": ["in", ["", None]]},
		"name",
	) or frappe.db.get_value("Cost Center", {"company": company, "is_group": 1}, "name")


class TestBranch(FrappeTestCase):
	def setUp(self):
		self.company = pf_accounts.default_company()

	def _make_leaf_cost_center(self, name, company=None):
		company = company or self.company
		cc = frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": name,
				"company": company,
				"parent_cost_center": _root_cost_center(company),
				"is_group": 0,
			}
		)
		cc.insert(ignore_permissions=True)
		return cc.name

	# ---- helper ---------------------------------------------------------- #
	def test_ensure_main_branch_idempotent(self):
		first = branch.ensure_main_branch(self.company)
		self.assertEqual(first, "Main")
		before = frappe.db.count("Business Branch", {"branch_name": "Main"})
		again = branch.ensure_main_branch(self.company)
		self.assertEqual(again, "Main")
		self.assertEqual(frappe.db.count("Business Branch", {"branch_name": "Main"}), before)

	def test_cost_center_falls_back_to_company_default(self):
		company_cc = frappe.get_cached_value("Company", self.company, "cost_center")
		self.assertEqual(branch.branch_cost_center(None, self.company), company_cc)

	def test_cost_center_uses_branch_own_cost_center(self):
		cc = self._make_leaf_cost_center("WP3 Branch CC")
		b = frappe.get_doc(
			{"doctype": "Business Branch", "branch_name": "WP3 CC Branch", "cost_center": cc}
		)
		b.insert(ignore_permissions=True)
		self.assertEqual(branch.branch_cost_center(b.name, self.company), cc)

	def test_cost_center_from_foreign_company_falls_back(self):
		other = frappe.db.get_value("Company", {"name": ["!=", self.company]}, "name")
		other_cc = frappe.db.get_value(
			"Cost Center", {"company": other, "is_group": 0}, "name"
		) if other else None
		if not other_cc:
			self.skipTest("no second company with a cost center on this site")
		b = frappe.get_doc(
			{"doctype": "Business Branch", "branch_name": "WP3 Foreign", "company": other, "cost_center": other_cc}
		)
		b.insert(ignore_permissions=True)
		# Posting for self.company must NOT borrow the other company's cost center.
		company_cc = frappe.get_cached_value("Company", self.company, "cost_center")
		self.assertEqual(branch.branch_cost_center(b.name, self.company), company_cc)

	# ---- stamping on financial doctypes ---------------------------------- #
	def test_member_defaults_to_main_branch(self):
		m = frappe.get_doc({"doctype": "Member", "full_name": "WP3 Branch Member"})
		m.insert(ignore_permissions=True)
		self.assertEqual(m.branch, "Main")

	def test_membership_inherits_member_branch(self):
		cc = self._make_leaf_cost_center("WP3 Studio CC")
		b = frappe.get_doc(
			{"doctype": "Business Branch", "branch_name": "WP3 Studio B", "cost_center": cc}
		)
		b.insert(ignore_permissions=True)
		member = frappe.get_doc(
			{"doctype": "Member", "full_name": "WP3 Studio Member", "branch": b.name}
		)
		member.insert(ignore_permissions=True)
		self.assertEqual(member.branch, "WP3 Studio B")
		ms = frappe.get_doc({"doctype": "Membership", "member": member.name, "month": "January"})
		ms.insert(ignore_permissions=True)
		self.assertEqual(ms.branch, "WP3 Studio B")

	def test_check_in_inherits_member_branch(self):
		# OP-1: the resolver is generic — any member-bearing doc inherits the
		# member's home branch, so a check-in lands at the member's own branch.
		cc = self._make_leaf_cost_center("OP1 Desk CC")
		b = frappe.get_doc(
			{"doctype": "Business Branch", "branch_name": "OP1 Desk B", "cost_center": cc}
		)
		b.insert(ignore_permissions=True)
		member = frappe.get_doc(
			{"doctype": "Member", "full_name": "OP1 Desk Member", "branch": b.name}
		)
		member.insert(ignore_permissions=True)
		chk = frappe.get_doc({"doctype": "Member Check-in", "member": member.name})
		chk.insert(ignore_permissions=True)
		self.assertEqual(chk.branch, "OP1 Desk B")

	def test_expense_defaults_to_main_branch(self):
		cat = frappe.db.get_value("Expense Category", {}, "name")
		if not cat:
			self.skipTest("no Expense Category on this site")
		e = frappe.get_doc(
			{"doctype": "Expense", "date": today(), "category": cat, "amount": 100}
		)
		e.insert(ignore_permissions=True)
		self.assertEqual(e.branch, "Main")
