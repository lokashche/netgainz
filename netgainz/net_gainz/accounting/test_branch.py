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
		b = frappe.get_doc({"doctype": "Business Branch", "branch_name": "WP3 CC Branch", "cost_center": cc})
		b.insert(ignore_permissions=True)
		self.assertEqual(branch.branch_cost_center(b.name, self.company), cc)

	def test_cost_center_from_foreign_company_falls_back(self):
		other = frappe.db.get_value("Company", {"name": ["!=", self.company]}, "name")
		other_cc = (
			frappe.db.get_value("Cost Center", {"company": other, "is_group": 0}, "name") if other else None
		)
		if not other_cc:
			self.skipTest("no second company with a cost center on this site")
		b = frappe.get_doc(
			{
				"doctype": "Business Branch",
				"branch_name": "WP3 Foreign",
				"company": other,
				"cost_center": other_cc,
			}
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
		b = frappe.get_doc({"doctype": "Business Branch", "branch_name": "WP3 Studio B", "cost_center": cc})
		b.insert(ignore_permissions=True)
		member = frappe.get_doc({"doctype": "Member", "full_name": "WP3 Studio Member", "branch": b.name})
		member.insert(ignore_permissions=True)
		self.assertEqual(member.branch, "WP3 Studio B")
		ms = frappe.get_doc({"doctype": "Membership", "member": member.name, "month": "January"})
		ms.insert(ignore_permissions=True)
		self.assertEqual(ms.branch, "WP3 Studio B")

	def test_check_in_inherits_member_branch(self):
		# OP-1: the resolver is generic — any member-bearing doc inherits the
		# member's home branch, so a check-in lands at the member's own branch.
		cc = self._make_leaf_cost_center("OP1 Desk CC")
		b = frappe.get_doc({"doctype": "Business Branch", "branch_name": "OP1 Desk B", "cost_center": cc})
		b.insert(ignore_permissions=True)
		member = frappe.get_doc({"doctype": "Member", "full_name": "OP1 Desk Member", "branch": b.name})
		member.insert(ignore_permissions=True)
		chk = frappe.get_doc({"doctype": "Member Check-in", "member": member.name})
		chk.insert(ignore_permissions=True)
		self.assertEqual(chk.branch, "OP1 Desk B")

	def test_expense_defaults_to_main_branch(self):
		cat = frappe.db.get_value("Expense Category", {}, "name")
		if not cat:
			self.skipTest("no Expense Category on this site")
		e = frappe.get_doc({"doctype": "Expense", "date": today(), "category": cat, "amount": 100})
		e.insert(ignore_permissions=True)
		self.assertEqual(e.branch, "Main")


# --------------------------------------------------------------------------- #
# Stage 10.1: the Branches screen
# --------------------------------------------------------------------------- #
STAFF_USER = "branch-frontdesk@example.com"


class TestBranchScreen(FrappeTestCase):
	def setUp(self):
		from netgainz.net_gainz import permissions

		self.company = pf_accounts.default_company()
		branch.ensure_default_branch(self.company)
		# Tests that move the default flag put it back on the branch that had it.
		self.addCleanup(branch.update_branch, branch.ensure_default_branch(self.company), make_default=1)
		self.addCleanup(frappe.set_user, "Administrator")
		permissions.ensure_roles()
		if not frappe.db.exists("User", STAFF_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": STAFF_USER,
					"first_name": "Branch Desk",
					"send_welcome_email": 0,
					"roles": [{"role": permissions.GYM_STAFF}],
				}
			).insert(ignore_permissions=True)

	def _new_branch(self, name):
		return branch.create_branch(name)["name"]

	def test_a_new_branch_gets_its_own_cost_center(self):
		b = self._new_branch("B10 Anna Nagar")
		cc = frappe.db.get_value("Business Branch", b, "cost_center")
		self.assertTrue(cc)
		self.assertNotEqual(cc, frappe.get_cached_value("Company", self.company, "cost_center"))
		self.assertEqual(frappe.db.get_value("Cost Center", cc, ["company", "is_group"]), (self.company, 0))
		self.assertEqual(branch.branch_cost_center(b, self.company), cc)

	def test_a_new_branch_members_money_lands_in_its_cost_center(self):
		from netgainz.net_gainz.accounting import billing_fixtures as fx

		b = self._new_branch("B10 Velachery")
		cc = frappe.db.get_value("Business Branch", b, "cost_center")
		plan = fx.make_plan("B10 Velachery Plan", amount=900.0)
		member = frappe.get_doc(
			{
				"doctype": "Member",
				"full_name": "B10 Velachery Member",
				"membership_plan": plan.name,
				"branch": b,
			}
		).insert(ignore_permissions=True)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()
		self.assertEqual(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "cost_center"), cc)

	def test_the_default_is_found_by_its_flag_not_its_name(self):
		b = self._new_branch("B10 Adyar")
		branch.update_branch(b, make_default=1)
		self.assertEqual(branch.ensure_default_branch(self.company), b)
		self.assertEqual(frappe.db.count("Business Branch", {"is_default": 1}), 1)
		m = frappe.get_doc({"doctype": "Member", "full_name": "B10 Adyar Walk-up"}).insert(
			ignore_permissions=True
		)
		self.assertEqual(m.branch, b)

	def test_the_default_branch_cannot_be_switched_off(self):
		default = branch.ensure_default_branch(self.company)
		with self.assertRaises(frappe.ValidationError):
			branch.update_branch(default, disabled=1)

	def test_a_rename_carries_the_members_with_it(self):
		b = self._new_branch("B10 Old Name")
		cc = frappe.db.get_value("Business Branch", b, "cost_center")
		member = frappe.get_doc({"doctype": "Member", "full_name": "B10 Rename Member", "branch": b}).insert(
			ignore_permissions=True
		)

		renamed = branch.update_branch(b, new_name="B10 New Name")["name"]

		self.assertEqual(renamed, "B10 New Name")
		self.assertEqual(frappe.db.get_value("Business Branch", renamed, "branch_name"), "B10 New Name")
		self.assertEqual(frappe.db.get_value("Member", member.name, "branch"), "B10 New Name")
		self.assertEqual(frappe.db.get_value("Business Branch", renamed, "cost_center"), cc)
		self.assertFalse(frappe.db.exists("Business Branch", "B10 Old Name"))

	def test_the_front_desk_can_see_branches_but_not_open_one(self):
		self._new_branch("B10 Desk Visible")
		frappe.set_user(STAFF_USER)
		self.assertIn("B10 Desk Visible", [r.name for r in branch.get_branches()])
		with self.assertRaises(frappe.PermissionError):
			branch.create_branch("B10 Desk Sneaky")

	def test_a_day_pass_posts_to_the_branch_it_was_sold_at(self):
		from netgainz.net_gainz.accounting import billing_fixtures as fx
		from netgainz.net_gainz.operations import packs

		fx.ensure_cash_account()
		b = self._new_branch("B10 Walk-in Branch")
		result = packs.sell_day_pass("B10 Walk-in Guest", 300.0, branch_name=b)
		cc = frappe.db.get_value("Business Branch", b, "cost_center")
		self.assertEqual(frappe.db.get_value("Sales Invoice", result["sales_invoice"], "cost_center"), cc)
		self.assertEqual(frappe.db.get_value("Day Pass", result["day_pass"], "branch"), b)

	def test_a_upi_advance_posts_to_the_members_branch_without_a_reference(self):
		from netgainz.net_gainz.accounting import advances

		b = self._new_branch("B10 Advance Branch")
		member = frappe.get_doc({"doctype": "Member", "full_name": "B10 Advance Member", "branch": b}).insert(
			ignore_permissions=True
		)
		pe = advances.record_advance(member.name, 500.0, payment_mode="UPI", posting_date=today())
		posted = frappe.db.get_value(
			"Payment Entry", pe, ["cost_center", "reference_no", "docstatus"], as_dict=True
		)
		self.assertEqual(posted.docstatus, 1)
		self.assertEqual(posted.cost_center, frappe.db.get_value("Business Branch", b, "cost_center"))
		self.assertTrue(posted.reference_no)
