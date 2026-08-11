# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-3: a coupon is an offer you have to know the code for.

What these pin:

* a code is matched however it is typed (case, spaces) and no two offers share one;
* a coupon offer is **hidden** from the enrolment list — knowing the code IS the gate;
* :func:`redeem_code` is the single entry point for a code (owner app now, member app
  and marketing site later) and refuses everything the save would refuse — expired,
  ended, wrong plan, used up, used too often by this member;
* redeeming actually prices the invoice, through the same one seam as everything else.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import discounts, offers


class TestCoupons(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		frappe.db.delete("Offer Plan")
		frappe.db.delete("Offer")

	# ---- helpers --------------------------------------------------------- #
	def _coupon(self, name, code, **kwargs):
		doc = {
			"doctype": "Offer",
			"offer_name": name,
			"coupon_code": code,
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 50,
			"discount_duration": offers.FIRST_INVOICE,
			"valid_from": today(),
		}
		plans = kwargs.pop("plans", None)
		doc.update(kwargs)
		if plans:
			doc["plans"] = [{"membership_plan": p} for p in plans]
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	def _enrol(self, tag, offer=None, amount=1000.0, plan=None, member=None):
		plan = plan or fx.make_plan(f"{tag} Plan", amount=amount).name
		member = member or fx.make_member(f"{tag} Member", plan).name
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member, "membership_plan": plan, "offer": offer}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	# ---- the code itself -------------------------------------------------- #
	def test_a_code_is_stored_in_capitals_without_spaces(self):
		coupon = self._coupon("DS3 Insta", " fit 50 ")
		self.assertEqual(coupon.coupon_code, "FIT50")

	def test_a_code_is_matched_however_it_is_typed(self):
		self._coupon("DS3 Match", "FIT50")
		for typed in ("fit50", " FIT 50 ", "Fit50"):
			self.assertIsNotNone(offers.offer_for_code(typed), f"{typed!r} should match")

	def test_two_offers_cannot_share_a_code(self):
		self._coupon("DS3 One", "FIT50")
		with self.assertRaises(frappe.ValidationError):
			self._coupon("DS3 Two", "fit50")

	# ---- knowing the code is the gate -------------------------------------- #
	def test_a_coupon_offer_is_not_in_the_enrolment_list(self):
		plan = fx.make_plan("DS3 Hidden Plan", amount=1000.0).name
		self._coupon("DS3 Hidden", "SECRET20", discount_value=20)
		self.assertEqual(offers.available_offers(membership_plan=plan), [])

	def test_an_offer_without_a_code_still_shows_in_the_list(self):
		plan = fx.make_plan("DS3 Open Plan", amount=1000.0).name
		frappe.get_doc(
			{
				"doctype": "Offer",
				"offer_name": "DS3 Open",
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 10,
				"valid_from": today(),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(len(offers.available_offers(membership_plan=plan)), 1)

	# ---- redeeming --------------------------------------------------------- #
	def test_redeeming_a_code_returns_what_it_is_worth(self):
		self._coupon("DS3 Worth", "HALF", discount_value=50)
		result = offers.redeem_code("half")
		self.assertEqual(result["offer_name"], "DS3 Worth")
		self.assertEqual(flt(result["discount_value"]), 50.0)
		self.assertEqual(result["coupon_code"], "HALF")

	def test_an_unknown_code_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			offers.redeem_code("NOPE")

	def test_an_expired_code_is_refused(self):
		self._coupon("DS3 Old", "OLD10", valid_from=add_days(today(), -30), valid_upto=add_days(today(), -1))
		with self.assertRaises(frappe.ValidationError):
			offers.redeem_code("OLD10")

	def test_a_code_for_other_plans_is_refused(self):
		other = fx.make_plan("DS3 Other Plan", amount=1000.0).name
		mine = fx.make_plan("DS3 Mine Plan", amount=1000.0).name
		self._coupon("DS3 Annual", "ANNUAL", plans=[other])
		with self.assertRaises(frappe.ValidationError):
			offers.redeem_code("ANNUAL", membership_plan=mine)

	def test_a_used_up_code_is_refused(self):
		plan = fx.make_plan("DS3 Gone Plan", amount=1000.0).name
		coupon = self._coupon("DS3 Gone", "ONCE", max_total_uses=1)
		self._enrol("DS3 G1", offer=coupon.name, plan=plan)
		with self.assertRaises(frappe.ValidationError):
			offers.redeem_code("ONCE", membership_plan=plan)

	def test_redeeming_prices_the_invoice(self):
		coupon = self._coupon("DS3 Bill", "FIT50", discount_value=50)
		ms = self._enrol("DS3 Bill", offer=coupon.name, amount=2000.0)
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "net_total")), 1000.0
		)
		self.assertEqual(ms.discount_reason, "Offer: DS3 Bill")

	# ---- per-member limit --------------------------------------------------- #
	def test_a_member_cannot_use_a_one_per_member_code_twice(self):
		plan = fx.make_plan("DS3 PM Plan", amount=1000.0).name
		coupon = self._coupon("DS3 PerMember", "ONEEACH", max_uses_per_member=1)
		member = fx.make_member("DS3 PM Member", plan).name
		self._enrol("DS3 PM1", offer=coupon.name, plan=plan, member=member)
		with self.assertRaises(frappe.ValidationError):
			self._enrol("DS3 PM2", offer=coupon.name, plan=plan, member=member)

	def test_the_per_member_limit_does_not_block_a_different_member(self):
		plan = fx.make_plan("DS3 PM2 Plan", amount=1000.0).name
		coupon = self._coupon("DS3 PerMember2", "ONEEACH2", max_uses_per_member=1)
		first = fx.make_member("DS3 PM2 First", plan).name
		self._enrol("DS3 PM2a", offer=coupon.name, plan=plan, member=first)
		second = self._enrol("DS3 PM2b", offer=coupon.name, plan=plan)
		self.assertEqual(second.discount_reason, "Offer: DS3 PerMember2")

	def test_redeem_checks_the_per_member_limit_before_enrolling(self):
		plan = fx.make_plan("DS3 PM3 Plan", amount=1000.0).name
		coupon = self._coupon("DS3 PerMember3", "ONEEACH3", max_uses_per_member=1)
		member = fx.make_member("DS3 PM3 Member", plan).name
		self._enrol("DS3 PM3", offer=coupon.name, plan=plan, member=member)
		with self.assertRaises(frappe.ValidationError):
			offers.redeem_code("ONEEACH3", membership_plan=plan, member=member)

	def test_resaving_a_membership_does_not_count_as_a_second_use(self):
		plan = fx.make_plan("DS3 Resave Plan", amount=1000.0).name
		coupon = self._coupon("DS3 Resave", "RESAVE", max_uses_per_member=1)
		ms = self._enrol("DS3 Resave", offer=coupon.name, plan=plan)
		ms.comments = "saved again"
		ms.save(ignore_permissions=True)
		self.assertEqual(offers.times_used_by_member(coupon.name, ms.member), 1)

	def test_a_negative_per_member_limit_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._coupon("DS3 Negative", "NEG", max_uses_per_member=-1)
