# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 10.4: branch managers.

The owner adds a staff login and limits it to a branch, from the owner-app. These
pin that such a login:

* sees only its branch's members, memberships, invoices and payments — the
  invoice / payment leak found in the Stage 10 trace (F6) is closed;
* is refused the gym-wide money screens (Profit First, commissions, go-live);
* cannot open another branch's member by name;
* files what it creates under its own branch;

and that only the owner manages logins, an owner is never limited, and nobody
changes their own login here.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz import permissions, staff_access
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import branch

OWNER = "b104-owner@example.com"
DESK = "b104-desk@example.com"
MANAGER = "b104-manager@example.com"
PASSWORD = "Gym!Branch#2026-Strong"


class TestStaffAccess(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		permissions.ensure_roles()
		self.addCleanup(frappe.set_user, "Administrator")
		for email, role in ((OWNER, permissions.GYM_OWNER), (DESK, permissions.GYM_STAFF)):
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": email.split("@")[0],
						"send_welcome_email": 0,
						"roles": [{"role": role}],
					}
				).insert(ignore_permissions=True)
		if frappe.db.exists("User", MANAGER):
			frappe.db.delete("User Permission", {"user": MANAGER})
			frappe.delete_doc("User", MANAGER, force=True, ignore_permissions=True)

		self.home = branch.ensure_default_branch()
		self.other = branch.create_branch(f"B104 Other {frappe.generate_hash(length=5)}")["name"]

		# One paid member at each branch.
		self.home_member, self.home_ms = self._enrol_at(self.home, "B104 Home")
		self.other_member, self.other_ms = self._enrol_at(self.other, "B104 Other")

		frappe.set_user(OWNER)
		staff_access.create_staff(MANAGER, "B104 Manager", PASSWORD, permissions.GYM_STAFF, [self.other])
		frappe.set_user("Administrator")

	def _enrol_at(self, at_branch, tag):
		plan = fx.make_plan(f"{tag} Plan {frappe.generate_hash(length=4)}", amount=1000.0)
		member = frappe.get_doc(
			{
				"doctype": "Member",
				"full_name": f"{tag} Member",
				"membership_plan": plan.name,
				"branch": at_branch,
			}
		).insert(ignore_permissions=True)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()
		fx.collect(ms)
		ms.reload()
		return member, ms

	# ---- the owner adds a branch manager ----------------------------------- #
	def test_the_owner_adds_a_login_limited_to_a_branch(self):
		self.assertEqual(frappe.db.get_value("User", MANAGER, "enabled"), 1)
		self.assertIn(permissions.GYM_STAFF, frappe.get_roles(MANAGER))
		self.assertEqual(branch.allowed_branches(MANAGER), [self.other])
		limits = frappe.get_all(
			"User Permission", filters={"user": MANAGER, "allow": "Cost Center"}, pluck="for_value"
		)
		self.assertEqual(limits, [branch.branch_cost_center(self.other)])

		frappe.set_user(OWNER)
		row = next(r for r in staff_access.get_staff() if r["user"] == MANAGER)
		self.assertEqual(row["branches"], [self.other])

	# ---- what the branch manager can see ----------------------------------- #
	def test_a_branch_manager_sees_only_their_branch_records(self):
		frappe.set_user(MANAGER)
		self.assertEqual(frappe.get_list("Member", pluck="name"), [self.other_member.name])
		self.assertEqual(frappe.get_list("Membership", pluck="name"), [self.other_ms.name])
		from netgainz.net_gainz.accounting import income_report

		self.assertEqual([r["branch"] for r in income_report.get_branch_profit()["branches"]], [self.other])

	def test_a_branch_manager_never_sees_another_branchs_invoices_or_payments(self):
		frappe.set_user(MANAGER)
		invoices = frappe.get_list("Sales Invoice", pluck="name")
		self.assertIn(self.other_ms.current_sales_invoice, invoices)
		self.assertNotIn(self.home_ms.current_sales_invoice, invoices)
		home_payments = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_name": self.home_ms.current_sales_invoice},
			pluck="parent",
		)
		self.assertTrue(home_payments)
		self.assertFalse(set(home_payments) & set(frappe.get_list("Payment Entry", pluck="name")))

	def test_a_branch_manager_is_refused_the_gym_wide_money_screens(self):
		from netgainz.net_gainz.accounting import billing, go_live
		from netgainz.net_gainz.operations import commissions
		from netgainz.net_gainz.profit_first import dashboard, instant_assessment

		frappe.set_user(MANAGER)
		for read in (
			instant_assessment.get_instant_assessment,
			dashboard.get_pf_dashboard,
			commissions.preview_commissions,
			billing.unbillable_memberships,
			go_live.billing_readiness,
		):
			with self.subTest(read=read.__name__), self.assertRaises(frappe.PermissionError):
				read()

	def test_a_branch_manager_cannot_open_another_branchs_member(self):
		from netgainz.net_gainz.accounting import billing

		frappe.set_user(MANAGER)
		billing.get_membership_obligations(self.other_ms.name)  # their own: fine
		with self.assertRaises(frappe.PermissionError):
			billing.get_membership_obligations(self.home_ms.name)
		with self.assertRaises(frappe.PermissionError):
			billing.record_membership_payment(self.home_ms.name, 100, payment_mode="Cash")

	def test_what_a_branch_manager_adds_lands_in_their_branch(self):
		frappe.set_user(MANAGER)
		member = frappe.get_doc({"doctype": "Member", "full_name": "B104 Walk-up"}).insert()
		self.assertEqual(member.branch, self.other)

	def test_an_unlimited_desk_login_still_sees_every_branch(self):
		frappe.set_user(DESK)
		self.assertIsNone(branch.scope())
		names = set(frappe.get_list("Member", pluck="name", limit_page_length=0))
		self.assertTrue({self.home_member.name, self.other_member.name} <= names)

	def test_clearing_the_branches_opens_every_branch(self):
		frappe.set_user(OWNER)
		staff_access.set_staff_branches(MANAGER, [])
		self.assertIsNone(branch.allowed_branches(MANAGER))
		self.assertFalse(frappe.db.exists("User Permission", {"user": MANAGER}))

	# ---- who may manage logins -------------------------------------------- #
	def test_only_the_owner_manages_logins(self):
		frappe.set_user(DESK)
		with self.assertRaises(frappe.PermissionError):
			staff_access.create_staff("b104-sneaky@example.com", "Sneaky", PASSWORD)
		with self.assertRaises(frappe.PermissionError):
			staff_access.set_staff_branches(MANAGER, [])

	def test_an_owner_login_is_never_limited(self):
		frappe.set_user(OWNER)
		other_owner = "b104-coowner@example.com"
		if not frappe.db.exists("User", other_owner):
			staff_access.create_staff(other_owner, "Co Owner", PASSWORD, permissions.GYM_OWNER)
		with self.assertRaises(frappe.ValidationError):
			staff_access.set_staff_branches(other_owner, [self.other])

	def test_nobody_changes_their_own_login_here(self):
		frappe.set_user(OWNER)
		with self.assertRaises(frappe.PermissionError):
			staff_access.set_staff_enabled(OWNER, 0)

	def test_switching_a_login_off(self):
		frappe.set_user(OWNER)
		staff_access.set_staff_enabled(MANAGER, 0)
		self.assertEqual(frappe.db.get_value("User", MANAGER, "enabled"), 0)
