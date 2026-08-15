# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 9 OP-4: session packs & day passes.

Pinned:

* a pack sale is REAL money in one action — a submitted Sales Invoice (taxed
  like every other invoice, R19 cost center from the member's branch) plus a
  Payment Entry that settles it, so PF sees the cash with no PF code changes;
* the pack always carries a tax code (HSN defaulted like plans) — no code, no
  billing, never silently;
* the balance is counted from the use log and cannot drift; exhausted and
  expired packs refuse another session with a plain message;
* expiry / low-balance alerts follow the renewals pattern (opt-out, idempotent
  per user per day);
* a day pass sells to one provisioned Walk-in customer; who came is on the
  pass record itself;
* the desk can sell and burn sessions; products are the owner's (staff hold
  read-only on Session Pack); role-less sessions are refused.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.operations import packs

STAFF_USER = "op4-frontdesk@example.com"


def _pack(name, sessions=10, validity_days=60, price=5000.0, **fields):
	if frappe.db.exists("Session Pack", name):
		return frappe.get_doc("Session Pack", name)
	return frappe.get_doc(
		{
			"doctype": "Session Pack",
			"pack_name": name,
			"sessions": sessions,
			"validity_days": validity_days,
			"price": price,
			**fields,
		}
	).insert(ignore_permissions=True)


class TestPacks(FrappeTestCase):
	def setUp(self):
		fx.ensure_cash_account()
		permissions.ensure_roles()
		self._user(STAFF_USER, permissions.GYM_STAFF)
		self.addCleanup(frappe.set_user, "Administrator")
		self.member = fx.make_member(f"OP4 Member {frappe.generate_hash(length=5)}")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _user(self, email, role):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@")[0],
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		if role:
			user = frappe.get_doc("User", email)
			if role not in [r.role for r in user.roles]:
				user.append("roles", {"role": role})
				user.save(ignore_permissions=True)

	# ---- the product ---------------------------------------------------------- #
	def test_pack_defaults_hsn_and_provisions_item(self):
		pack = _pack("OP4 Ten Pack")
		self.assertTrue(pack.gst_hsn_code, "HSN is defaulted — a pack can never be unsellable")
		self.assertTrue(pack.item)
		self.assertEqual(frappe.db.get_value("Item", pack.item, "gst_hsn_code"), pack.gst_hsn_code)

	def test_pack_validations(self):
		with self.assertRaises(frappe.ValidationError):
			_pack("OP4 Zero Sessions", sessions=0)
		with self.assertRaises(frappe.ValidationError):
			_pack("OP4 Free Pack", price=0)

	# ---- the sale -------------------------------------------------------------- #
	def test_sell_pack_is_real_money_in_one_action(self):
		pack = _pack("OP4 Sale Pack", sessions=10, validity_days=60, price=5000.0)
		result = packs.sell_pack(self.member.name, pack.name, payment_mode="Cash")

		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertEqual(si.docstatus, 1)
		self.assertEqual(flt(si.net_total), 5000.0)
		self.assertEqual(flt(si.outstanding_amount), 0.0, "the payment settled it")
		if si.taxes_and_charges:
			self.assertTrue(si.get("taxes"), "GST rows expanded, not just named")

		pe = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(pe.docstatus, 1)
		self.assertEqual(flt(pe.paid_amount), flt(si.grand_total))

		purchase = frappe.get_doc("Pack Purchase", result["pack_purchase"])
		self.assertEqual(purchase.status, "Active")
		self.assertEqual(purchase.sessions_total, 10)
		self.assertEqual(purchase.sessions_used, 0)
		self.assertEqual(str(purchase.expires_on), add_days(today(), 59))
		self.assertEqual(purchase.branch, self.member.branch, "R19: the member's branch")

	def test_sell_pack_price_override(self):
		pack = _pack("OP4 Nego Pack", price=5000.0)
		result = packs.sell_pack(self.member.name, pack.name, price=4200.0)
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice", result["sales_invoice"], "net_total")),
			4200.0,
		)

	def test_inactive_pack_refuses_sale(self):
		pack = _pack("OP4 Retired Pack")
		pack.db_set("is_active", 0)
		with self.assertRaises(frappe.ValidationError):
			packs.sell_pack(self.member.name, pack.name)

	# ---- burn-down -------------------------------------------------------------- #
	def test_use_session_counts_from_the_log(self):
		pack = _pack("OP4 Burn Pack", sessions=2)
		sale = packs.sell_pack(self.member.name, pack.name)

		first = packs.use_session(sale["pack_purchase"])
		self.assertEqual(first["remaining"], 1)
		self.assertEqual(first["status"], "Active")

		second = packs.use_session(sale["pack_purchase"])
		self.assertEqual(second["remaining"], 0)
		self.assertEqual(second["status"], "Exhausted")
		self.assertEqual(frappe.db.count("Pack Session Use", {"pack_purchase": sale["pack_purchase"]}), 2)

		with self.assertRaises(frappe.ValidationError):
			packs.use_session(sale["pack_purchase"])

	def test_expired_pack_refuses_a_session(self):
		pack = _pack("OP4 Expiry Pack", validity_days=30)
		sale = packs.sell_pack(self.member.name, pack.name)
		frappe.db.set_value("Pack Purchase", sale["pack_purchase"], "expires_on", add_days(today(), -1))
		with self.assertRaises(frappe.ValidationError):
			packs.use_session(sale["pack_purchase"])
		self.assertEqual(frappe.db.get_value("Pack Purchase", sale["pack_purchase"], "status"), "Expired")

	def test_use_log_inherits_member_branch(self):
		pack = _pack("OP4 Branchy Pack")
		sale = packs.sell_pack(self.member.name, pack.name)
		packs.use_session(sale["pack_purchase"])
		use = frappe.get_all(
			"Pack Session Use", filters={"pack_purchase": sale["pack_purchase"]}, fields=["branch"]
		)[0]
		self.assertEqual(use.branch, self.member.branch)

	# ---- alerts ------------------------------------------------------------------ #
	def test_alerts_flag_expiring_and_low_balance(self):
		pack = _pack("OP4 Alert Pack", sessions=5, validity_days=60)
		expiring = packs.sell_pack(self.member.name, pack.name)
		frappe.db.set_value("Pack Purchase", expiring["pack_purchase"], "expires_on", add_days(today(), 3))

		low_member = fx.make_member(f"OP4 Low Member {frappe.generate_hash(length=5)}")
		low_pack = _pack("OP4 Low Pack", sessions=1, validity_days=60)
		low = packs.sell_pack(low_member.name, low_pack.name)

		data = packs.get_pack_alerts()
		by_name = {r["pack_purchase"]: r for r in data["alerts"]}
		self.assertIn(expiring["pack_purchase"], by_name)
		self.assertTrue(by_name[expiring["pack_purchase"]]["expiring"])
		self.assertIn(low["pack_purchase"], by_name)
		self.assertTrue(by_name[low["pack_purchase"]]["low_balance"])

	def test_pack_alert_digest_disabled_and_idempotent(self):
		frappe.db.set_single_value("Business Settings", "pack_alerts_enabled", 0)
		self.assertIsNone(packs.notify_pack_alerts())

		frappe.db.set_single_value("Business Settings", "pack_alerts_enabled", 1)
		pack = _pack("OP4 Digest Pack", sessions=1)
		packs.sell_pack(self.member.name, pack.name)
		first = packs.notify_pack_alerts()
		self.assertIsNotNone(first)
		second = packs.notify_pack_alerts()
		self.assertEqual(second["notified"], 0)

	# ---- day passes ---------------------------------------------------------------- #
	def test_day_pass_is_real_money_for_a_walk_in(self):
		result = packs.sell_day_pass("OP4 Walkin Guest", 300.0, phone="+91 90000 00001")

		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertEqual(si.docstatus, 1)
		self.assertEqual(flt(si.net_total), 300.0)
		self.assertEqual(flt(si.outstanding_amount), 0.0)
		self.assertEqual(
			frappe.db.get_value("Customer", si.customer, "customer_name"),
			packs.WALKIN_CUSTOMER_NAME,
		)

		day_pass = frappe.get_doc("Day Pass", result["day_pass"])
		self.assertEqual(day_pass.guest_name, "OP4 Walkin Guest")
		self.assertEqual(str(day_pass.visited_on), today())

		listing = packs.todays_day_passes()
		self.assertIn(result["day_pass"], {p.name for p in listing["passes"]})
		self.assertGreaterEqual(listing["total"], 300.0)

	def test_day_pass_requires_name_and_amount(self):
		with self.assertRaises(frappe.ValidationError):
			packs.sell_day_pass("", 300.0)
		with self.assertRaises(frappe.ValidationError):
			packs.sell_day_pass("OP4 Freebie", 0)

	# ---- who may do what -------------------------------------------------------------- #
	def test_staff_can_sell_and_burn_but_not_define_products(self):
		pack = _pack("OP4 Staff Pack")
		frappe.set_user(STAFF_USER)
		sale = packs.sell_pack(self.member.name, pack.name)
		self.assertTrue(sale["pack_purchase"])
		used = packs.use_session(sale["pack_purchase"])
		self.assertEqual(used["remaining"], pack.sessions - 1)
		day = packs.sell_day_pass("OP4 Staff Guest", 250.0)
		self.assertTrue(day["day_pass"])

		# Products are the owner's: a plain insert as staff has no create right.
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Session Pack",
					"pack_name": "OP4 Staff Product",
					"sessions": 5,
					"validity_days": 30,
					"price": 1000.0,
				}
			).insert()

	def test_role_less_session_is_refused(self):
		pack = _pack("OP4 Locked Pack")
		self._user("op4-visitor@example.com", None)
		frappe.set_user("op4-visitor@example.com")
		with self.assertRaises(frappe.PermissionError):
			packs.sell_pack(self.member.name, pack.name)
		with self.assertRaises(frappe.PermissionError):
			packs.sell_day_pass("OP4 Locked Guest", 300.0)
