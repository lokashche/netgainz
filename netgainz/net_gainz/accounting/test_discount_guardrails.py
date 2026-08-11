# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-5: what the front desk may give away, and the record of who gave it.

A guardrail that only exists in the UI is not a guardrail, so every rule here is
exercised against a real Gym Staff session (``frappe.set_user``) — tests otherwise run
as Administrator and would pass vacuously.

Pinned:

* staff are capped at the tenant's percentage, and a flat amount is measured against the
  member's price so it cannot walk around the cap;
* a complimentary (100%) membership is owner-only;
* the owner is not capped;
* the owner's PIN approves ONE discount, for THAT member, at THAT size — it cannot be
  replayed, resized or reused;
* every grant, change and removal lands in the Discount Log with who, why and old→new.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import discounts, offers

STAFF_USER = "ds5-frontdesk@example.com"
OWNER_USER = "ds5-owner@example.com"
PIN = "4821"


class TestDiscountGuardrails(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		frappe.db.delete("Discount Log")
		frappe.db.delete("Offer Plan")
		frappe.db.delete("Offer")
		permissions.ensure_roles()
		self._user(STAFF_USER, permissions.GYM_STAFF)
		self._user(OWNER_USER, permissions.GYM_OWNER)
		frappe.db.set_single_value("Business Settings", "max_discount_percent", 10)
		frappe.db.set_single_value("Business Settings", "complimentary_requires_owner", 1)
		self._set_pin(PIN)
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	# ---- helpers --------------------------------------------------------- #
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
		user = frappe.get_doc("User", email)
		if role not in [r.role for r in user.roles]:
			user.append("roles", {"role": role})
			user.save(ignore_permissions=True)

	def _set_pin(self, pin):
		settings = frappe.get_single("Business Settings")
		settings.owner_approval_pin = pin
		settings.save(ignore_permissions=True)

	def _plan_and_member(self, tag, amount=1000.0):
		plan = fx.make_plan(f"{tag} Plan", amount=amount)
		member = fx.make_member(f"{tag} Member", plan.name)
		return plan.name, member.name

	def _enrol(self, plan, member, **fields):
		return frappe.get_doc(
			{"doctype": "Membership", "member": member, "membership_plan": plan, **fields}
		).insert(ignore_permissions=True)

	# ---- the cap ---------------------------------------------------------- #
	def test_staff_may_give_up_to_the_limit(self):
		plan, member = self._plan_and_member("DS5 Under")
		frappe.set_user(STAFF_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=10,
			discount_reason="Student",
		)
		self.assertEqual(flt(ms.discount_value), 10.0)

	def test_staff_cannot_go_over_the_limit(self):
		plan, member = self._plan_and_member("DS5 Over")
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			self._enrol(
				plan,
				member,
				discount_type=discounts.PERCENTAGE,
				discount_value=30,
				discount_reason="Friend of a friend",
			)

	def test_a_flat_amount_cannot_walk_around_the_limit(self):
		"""Rs.400 off a Rs.1,000 membership is 40%, however it was typed."""
		plan, member = self._plan_and_member("DS5 Flat", amount=1000.0)
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			self._enrol(
				plan,
				member,
				discount_type=discounts.AMOUNT,
				discount_value=400,
				discount_reason="Negotiated",
			)

	def test_a_small_flat_amount_is_still_allowed(self):
		plan, member = self._plan_and_member("DS5 SmallFlat", amount=2000.0)
		frappe.set_user(STAFF_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.AMOUNT,
			discount_value=150,
			discount_reason="Rounded the fee",
		)
		self.assertEqual(flt(ms.discount_value), 150.0)

	def test_a_free_membership_is_owner_only(self):
		plan, member = self._plan_and_member("DS5 Comp")
		frappe.db.set_single_value("Business Settings", "max_discount_percent", 100)
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			self._enrol(
				plan,
				member,
				discount_type=discounts.PERCENTAGE,
				discount_value=100,
				discount_reason="Scholarship",
			)

	def test_the_owner_is_not_capped(self):
		plan, member = self._plan_and_member("DS5 Owner")
		frappe.set_user(OWNER_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=100,
			discount_reason="Complimentary — founder's friend",
		)
		self.assertEqual(flt(ms.discount_value), 100.0)

	def test_an_offer_is_exempt_from_the_desk_cap(self):
		"""The owner defined the campaign; staff can only hand out what is running."""
		plan, member = self._plan_and_member("DS5 Offer")
		offer = frappe.get_doc(
			{
				"doctype": "Offer",
				"offer_name": "DS5 Big Campaign",
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 40,
				"valid_from": today(),
			}
		).insert(ignore_permissions=True)
		frappe.set_user(STAFF_USER)
		ms = self._enrol(plan, member, offer=offer.name)
		self.assertEqual(flt(ms.discount_value), 40.0)
		self.assertEqual(ms.discount_reason, "Offer: DS5 Big Campaign")

	# ---- the owner's PIN ---------------------------------------------------- #
	def test_the_owner_pin_approves_a_bigger_discount(self):
		plan, member = self._plan_and_member("DS5 Pin")
		frappe.set_user(STAFF_USER)
		approval = discounts.authorise_discount(
			member=member, discount_type=discounts.PERCENTAGE, discount_value=30, pin=PIN
		)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=30,
			discount_reason="Owner said yes",
			discount_approval=approval["approval"],
		)
		self.assertEqual(flt(ms.discount_value), 30.0)
		self.assertTrue(ms.discount_approved_on)
		self.assertFalse(ms.discount_approval, "the approval is spent, never stored")

	def test_a_wrong_pin_approves_nothing(self):
		_, member = self._plan_and_member("DS5 WrongPin")
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.AuthenticationError):
			discounts.authorise_discount(
				member=member, discount_type=discounts.PERCENTAGE, discount_value=30, pin="0000"
			)

	def test_an_approval_cannot_be_resized(self):
		"""Approved for 30%, saved as 60% — refused."""
		plan, member = self._plan_and_member("DS5 Resize")
		frappe.set_user(STAFF_USER)
		approval = discounts.authorise_discount(
			member=member, discount_type=discounts.PERCENTAGE, discount_value=30, pin=PIN
		)
		with self.assertRaises(frappe.PermissionError):
			self._enrol(
				plan,
				member,
				discount_type=discounts.PERCENTAGE,
				discount_value=60,
				discount_reason="Sneaky",
				discount_approval=approval["approval"],
			)

	def test_an_approval_cannot_be_spent_on_another_member(self):
		plan_a, member_a = self._plan_and_member("DS5 MemberA")
		plan_b, member_b = self._plan_and_member("DS5 MemberB")
		frappe.set_user(STAFF_USER)
		approval = discounts.authorise_discount(
			member=member_a, discount_type=discounts.PERCENTAGE, discount_value=30, pin=PIN
		)
		with self.assertRaises(frappe.PermissionError):
			self._enrol(
				plan_b,
				member_b,
				discount_type=discounts.PERCENTAGE,
				discount_value=30,
				discount_reason="Same deal for his friend",
				discount_approval=approval["approval"],
			)

	def test_an_approval_is_single_use(self):
		plan, member = self._plan_and_member("DS5 Replay")
		frappe.set_user(STAFF_USER)
		approval = discounts.authorise_discount(
			member=member, discount_type=discounts.PERCENTAGE, discount_value=30, pin=PIN
		)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=30,
			discount_reason="Owner said yes",
			discount_approval=approval["approval"],
		)
		# Take it off and try to put the same one back with the spent approval.
		ms.discount_type = ""
		ms.save()
		ms.discount_type = discounts.PERCENTAGE
		ms.discount_value = 30
		ms.discount_reason = "Again"
		ms.discount_approval = approval["approval"]
		with self.assertRaises(frappe.PermissionError):
			ms.save()

	def test_without_a_pin_set_nothing_can_be_approved(self):
		self._set_pin("")
		_, member = self._plan_and_member("DS5 NoPin")
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.ValidationError):
			discounts.authorise_discount(
				member=member, discount_type=discounts.PERCENTAGE, discount_value=30, pin="1234"
			)

	# ---- the audit trail ----------------------------------------------------- #
	def test_giving_a_discount_is_logged_with_who_and_why(self):
		plan, member = self._plan_and_member("DS5 Log")
		frappe.set_user(STAFF_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=10,
			discount_reason="Student rate",
		)
		frappe.set_user(OWNER_USER)
		history = discounts.discount_history(membership=ms.name)
		self.assertEqual(len(history), 1)
		self.assertEqual(history[0]["action"], "Given")
		self.assertEqual(history[0]["granted_by"], STAFF_USER)
		self.assertEqual(history[0]["reason"], "Student rate")

	def test_changing_a_discount_records_what_it_was(self):
		plan, member = self._plan_and_member("DS5 Changed")
		frappe.set_user(OWNER_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=10,
			discount_reason="Student rate",
		)
		ms.discount_value = 30
		ms.discount_reason = "Renegotiated"
		ms.save()
		frappe.set_user(OWNER_USER)
		history = discounts.discount_history(membership=ms.name)
		self.assertEqual([h["action"] for h in history], ["Changed", "Given"])
		self.assertEqual(flt(history[0]["previous_value"]), 10.0)
		self.assertEqual(flt(history[0]["discount_value"]), 30.0)

	def test_removing_a_discount_is_logged_too(self):
		plan, member = self._plan_and_member("DS5 Removed")
		frappe.set_user(OWNER_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.AMOUNT,
			discount_value=100,
			discount_reason="Goodwill",
		)
		ms.discount_type = ""
		ms.save()
		frappe.set_user(OWNER_USER)
		history = discounts.discount_history(membership=ms.name)
		self.assertEqual(history[0]["action"], "Removed")
		self.assertEqual(flt(history[0]["previous_value"]), 100.0)

	def test_a_refused_discount_leaves_no_trace(self):
		plan, member = self._plan_and_member("DS5 Refused")
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			self._enrol(
				plan,
				member,
				discount_type=discounts.PERCENTAGE,
				discount_value=50,
				discount_reason="Nope",
			)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count("Discount Log"), 0)

	def test_an_offer_grant_is_logged_against_the_offer(self):
		plan, member = self._plan_and_member("DS5 OfferLog")
		offer = frappe.get_doc(
			{
				"doctype": "Offer",
				"offer_name": "DS5 Logged Campaign",
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 15,
				"valid_from": today(),
			}
		).insert(ignore_permissions=True)
		frappe.set_user(STAFF_USER)
		ms = self._enrol(plan, member, offer=offer.name)
		frappe.set_user(OWNER_USER)
		history = discounts.discount_history(membership=ms.name)
		self.assertEqual(history[0]["offer"], offer.name)
		self.assertEqual(history[0]["action"], "Given")

	def test_an_ordinary_save_does_not_log_anything_new(self):
		plan, member = self._plan_and_member("DS5 Quiet")
		frappe.set_user(OWNER_USER)
		ms = self._enrol(
			plan, member, discount_type=discounts.AMOUNT, discount_value=50, discount_reason="Ok"
		)
		ms.comments = "touched"
		ms.save()
		self.assertEqual(len(discounts.discount_history(membership=ms.name)), 1)

	# ---- the policy is the owner's ------------------------------------------- #
	def test_raising_the_limit_lets_staff_give_more(self):
		frappe.db.set_single_value("Business Settings", "max_discount_percent", 25)
		plan, member = self._plan_and_member("DS5 Raised")
		frappe.set_user(STAFF_USER)
		ms = self._enrol(
			plan,
			member,
			discount_type=discounts.PERCENTAGE,
			discount_value=25,
			discount_reason="Within the new limit",
		)
		self.assertEqual(flt(ms.discount_value), 25.0)

	def test_the_default_limit_applies_when_settings_are_empty(self):
		frappe.db.set_single_value("Business Settings", "max_discount_percent", None)
		self.assertEqual(discounts.policy()["max_staff_percent"], discounts.DEFAULT_MAX_STAFF_PERCENT)
