# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""WP-8: the role & permission matrix.

Before this, every NetGainz doctype granted only **System Manager** — so running a
gym meant being a full Frappe administrator — and every whitelisted money method
was callable by any logged-in user, because ``@frappe.whitelist()`` only checks
that you are signed in.

Two things are asserted here: the matrix produces the right grants, and the
runtime guard actually stops the wrong user posting money.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import advances, billing, refunds, writeoff
from netgainz.net_gainz.accounting import billing_fixtures as fx


def _make_user(email, roles):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		user.set("roles", [])
	else:
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
	for role in roles:
		user.append("roles", {"role": role})
	user.flags.ignore_permissions = True
	user.save(ignore_permissions=True)
	return user.name


class TestPermissionMatrix(FrappeTestCase):
	def setUp(self):
		permissions.apply_permission_matrix()
		self.addCleanup(frappe.set_user, "Administrator")

	def _perms(self, doctype, role):
		return frappe.db.get_value(
			"Custom DocPerm",
			{"parent": doctype, "role": role, "permlevel": 0},
			["read", "write", "create", "delete", "submit"],
			as_dict=True,
		) or frappe.db.get_value(
			"DocPerm",
			{"parent": doctype, "role": role, "permlevel": 0},
			["read", "write", "create", "delete", "submit"],
			as_dict=True,
		)

	# ---- roles ------------------------------------------------------------ #
	def test_both_product_roles_exist(self):
		for role in permissions.NETGAINZ_ROLES:
			self.assertTrue(frappe.db.exists("Role", role), f"{role} must exist")

	def test_applying_the_matrix_twice_changes_nothing(self):
		permissions.apply_permission_matrix()
		second = permissions.apply_permission_matrix()
		self.assertEqual(second["permissions_written"], 0, "the matrix must be idempotent")

	# ---- the grants -------------------------------------------------------- #
	def test_owner_runs_the_whole_product(self):
		for doctype in ("Member", "Membership", "Membership Plan", "Expense", "PF Sweep"):
			perms = self._perms(doctype, permissions.GYM_OWNER)
			self.assertTrue(perms and perms.read and perms.write, f"owner needs {doctype}")
		self.assertTrue(self._perms("PF Sweep", permissions.GYM_OWNER).submit)

	def test_staff_can_run_the_front_desk_but_not_the_finances(self):
		member = self._perms("Member", permissions.GYM_STAFF)
		self.assertTrue(member.read and member.write and member.create)
		self.assertFalse(member.delete, "the front desk does not delete members")

		plan = self._perms("Membership Plan", permissions.GYM_STAFF)
		self.assertTrue(plan.read)
		self.assertFalse(plan.write, "pricing is the owner's call")

		for doctype in ("Expense", "Expense Category", "PF Sweep", "Profit First Settings",
		                "Instructor Commission Run"):
			self.assertIsNone(
				self._perms(doctype, permissions.GYM_STAFF), f"staff must not see {doctype}"
			)

	def test_owner_can_read_the_erpnext_documents_the_engine_creates(self):
		for doctype in ("Sales Invoice", "Payment Entry", "Journal Entry", "Subscription"):
			perms = self._perms(doctype, permissions.GYM_OWNER)
			self.assertTrue(perms and perms.read, f"owner should be able to read {doctype}")
			self.assertFalse(perms.write, f"{doctype} is written by the engine, never by hand")
			self.assertFalse(perms.delete)

	# ---- the runtime guard -------------------------------------------------- #
	def test_a_signed_in_stranger_cannot_post_money(self):
		"""The real hole this closes: @frappe.whitelist() gates on being logged in,
		nothing more."""
		user = _make_user("wp8-stranger@example.com", ["Blogger"])
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	def test_staff_can_take_payments_but_not_refund(self):
		user = _make_user("wp8-staff@example.com", [permissions.GYM_STAFF])
		frappe.set_user(user)
		# taking money: allowed
		permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
		# giving it back: not
		with self.assertRaises(frappe.PermissionError):
			permissions.require_role(permissions.GYM_OWNER)

	def test_owner_may_do_both(self):
		user = _make_user("wp8-owner@example.com", [permissions.GYM_OWNER])
		frappe.set_user(user)
		permissions.require_role(permissions.GYM_OWNER)
		permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	def test_system_manager_is_never_locked_out(self):
		user = _make_user("wp8-sysman@example.com", ["System Manager"])
		frappe.set_user(user)
		permissions.require_role(permissions.GYM_OWNER)

	def test_capabilities_describe_what_the_user_may_do(self):
		user = _make_user("wp8-staff2@example.com", [permissions.GYM_STAFF])
		frappe.set_user(user)
		caps = permissions.get_my_capabilities()
		self.assertEqual(caps["roles"], [permissions.GYM_STAFF])
		self.assertTrue(caps["can_record_payment"])
		self.assertFalse(caps["can_refund"])
		self.assertFalse(caps["can_write_off"])

	# ---- the guard is wired to the money endpoints -------------------------- #
	def test_refund_and_write_off_endpoints_reject_staff(self):
		from netgainz.net_gainz.accounting import refunds, writeoff

		user = _make_user("wp8-staff3@example.com", [permissions.GYM_STAFF])
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			refunds.refund_membership_payment("SUB-0000", amount=1)
		with self.assertRaises(frappe.PermissionError):
			writeoff.write_off_membership_dues("SUB-0000")

	def test_ledger_setup_endpoints_reject_staff(self):
		from netgainz.net_gainz.doctype.pf_sweep.pf_sweep import create_sweep
		from netgainz.net_gainz.profit_first.accounts import setup_profit_first_accounts

		user = _make_user("wp8-staff4@example.com", [permissions.GYM_STAFF])
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			setup_profit_first_accounts()
		with self.assertRaises(frappe.PermissionError):
			create_sweep()


class TestRolesCanActuallyWork(FrappeTestCase):
	"""The other half of a permission matrix: the permitted user must be able to
	FINISH the job.

	ERPNext's helpers read as the session user even when the document they build is
	inserted with permissions ignored, so a role can pass ``require_role`` and still
	hit a wall three frames down. Two such walls were found by driving the flows as
	a real gym user (the unit tests above run as Administrator and cannot see them):

	* ``get_payment_entry`` -> ``get_bank_cash_account`` -> ``get_balance_on``
	  checks **Account** read — without it the front desk cannot take a payment;
	* ``make_return_doc`` -> ``get_mapped_doc`` checks **Sales Invoice create** —
	  which no gym role has, and should not have, so the credit note is mapped onto
	  a target that carries the flag instead.

	These tests re-run the real flows as the real roles so neither can regress.
	"""

	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		permissions.apply_permission_matrix()
		# No frappe.db.commit() here: FrappeTestCase rolls the class back, and a
		# commit would leak these plans / members / Customers into the next run —
		# where ERPNext's own before_tests wipes Item Prices, leaving a reused plan
		# priced at zero and every assertion measuring nothing.
		self.addCleanup(frappe.set_user, "Administrator")

	def _outstanding(self, si):
		return flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))

	def test_staff_can_take_a_payment_end_to_end(self):
		ms = fx.enrol("PERM Pay", amount=1000.0)
		owed = self._outstanding(ms.current_sales_invoice)
		frappe.set_user(_make_user("wp8-staff-e2e@example.com", [permissions.GYM_STAFF]))

		result = billing.record_membership_payment(ms.name, owed, "Cash", today())

		self.assertTrue(result["payment_entry"])
		self.assertEqual(self._outstanding(ms.current_sales_invoice), 0.0)

	def test_staff_can_take_and_apply_money_on_account(self):
		ms = fx.enrol("PERM Adv", amount=1000.0)
		owed = self._outstanding(ms.current_sales_invoice)
		frappe.set_user(_make_user("wp8-staff-adv@example.com", [permissions.GYM_STAFF]))

		advances.record_member_advance(ms.member, owed + 500, "Cash", today())
		applied = advances.apply_member_advances(ms.member)

		self.assertAlmostEqual(applied["applied"], owed, places=2)
		self.assertAlmostEqual(applied["advance_balance"], 500.0, places=2)

	def test_owner_can_refund_end_to_end(self):
		ms = fx.enrol_and_collect("PERM Refund", amount=1000.0)
		frappe.set_user(_make_user("wp8-owner-refund@example.com", [permissions.GYM_OWNER]))

		context = refunds.get_refund_context(ms.name)
		result = refunds.refund_membership_payment(
			ms.name, amount=context["refundable"], reason="Goodwill", posting_date=today(),
			payment_mode="Cash",
		)

		self.assertTrue(result["credit_note"])
		self.assertTrue(result["payment_entry"])

	def test_owner_can_write_off_end_to_end(self):
		ms = fx.enrol("PERM WriteOff", amount=2000.0)
		frappe.set_user(_make_user("wp8-owner-wo@example.com", [permissions.GYM_OWNER]))

		result = writeoff.write_off_membership_dues(ms.name, reason="Member Left")

		self.assertTrue(result["journal_entry"])
		self.assertEqual(self._outstanding(result["sales_invoice"]), 0.0)
