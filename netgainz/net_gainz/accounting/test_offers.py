# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-2: an Offer is a campaign, and giving it out is a controlled act.

What these pin:

* giving an offer prices the member's invoice — through the SAME single seam a
  hand-typed discount uses, so there is only ever one discount on an invoice;
* an offer that has ended, has not started, is out of scope, or is used up cannot be
  given — server-side (R17), whatever the UI does;
* **ending or editing an offer never re-prices a member already on it** (the grant is
  copied when given, not read back later) — this is what "founding member rate" means;
* scope: no plans listed = every plan, no branch = every branch (R19).
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import discounts, offers


class TestOffers(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		frappe.db.delete("Offer Plan")
		frappe.db.delete("Offer")

	# ---- helpers --------------------------------------------------------- #
	def _offer(self, name, **kwargs):
		doc = {
			"doctype": "Offer",
			"offer_name": name,
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 20,
			"discount_duration": offers.FIRST_INVOICE,
			"valid_from": today(),
		}
		plans = kwargs.pop("plans", None)
		doc.update(kwargs)
		if plans:
			doc["plans"] = [{"membership_plan": p} for p in plans]
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	def _enrol_on_offer(self, tag, offer, amount=1000.0, **kwargs):
		plan = kwargs.pop("plan", None) or fx.make_plan(f"{tag} Plan", amount=amount).name
		member = fx.make_member(f"{tag} Member", plan)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan,
				"offer": offer,
				**kwargs,
			}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _net(self, membership):
		return flt(frappe.db.get_value("Sales Invoice", membership.current_sales_invoice, "net_total"))

	# ---- an offer reaches the invoice ------------------------------------- #
	def test_giving_an_offer_discounts_the_members_invoice(self):
		offer = self._offer("DS2 New Year 20", discount_value=20)
		ms = self._enrol_on_offer("DS2 NY", offer.name, amount=2000.0)
		self.assertEqual(self._net(ms), 1600.0)

	def test_the_offer_fills_the_membership_grant_and_names_itself(self):
		"""One discount on the membership, whoever put it there — the report reads it."""
		offer = self._offer("DS2 Diwali 500", discount_type=discounts.AMOUNT, discount_value=500)
		ms = self._enrol_on_offer("DS2 Diw", offer.name, amount=2000.0)
		self.assertEqual(ms.discount_type, discounts.AMOUNT)
		self.assertEqual(flt(ms.discount_value), 500.0)
		self.assertEqual(ms.discount_reason, "Offer: DS2 Diwali 500")
		self.assertEqual(self._net(ms), 1500.0)

	def test_a_joining_offer_ends_after_the_first_invoice(self):
		offer = self._offer("DS2 Joining", discount_value=50, discount_duration=offers.FIRST_INVOICE)
		ms = self._enrol_on_offer("DS2 Join", offer.name, amount=1000.0)
		self.assertEqual(self._net(ms), 500.0)
		nxt = frappe.get_doc("Subscription", ms.subscription).create_invoice()
		self.assertEqual(flt(nxt.net_total), 1000.0)

	def test_a_founding_rate_is_kept_every_invoice(self):
		offer = self._offer("DS2 Founding", discount_value=30, discount_duration=offers.EVERY_INVOICE)
		ms = self._enrol_on_offer("DS2 Found", offer.name, amount=1000.0)
		self.assertEqual(self._net(ms), 700.0)
		nxt = frappe.get_doc("Subscription", ms.subscription).create_invoice()
		self.assertEqual(flt(nxt.net_total), 700.0)

	def test_until_the_offer_ends_becomes_a_dated_discount(self):
		ends = add_days(today(), 45)
		offer = self._offer(
			"DS2 Season", discount_value=10, discount_duration=offers.UNTIL_OFFER_ENDS, valid_upto=ends
		)
		ms = self._enrol_on_offer("DS2 Seas", offer.name, amount=1000.0)
		self.assertEqual(ms.discount_duration, discounts.UNTIL_DATE)
		self.assertEqual(str(ms.discount_until), str(ends))

	# ---- ending/editing an offer never re-prices anyone -------------------- #
	def test_ending_an_offer_leaves_members_already_on_it_alone(self):
		offer = self._offer("DS2 Ending", discount_value=25, discount_duration=offers.EVERY_INVOICE)
		ms = self._enrol_on_offer("DS2 End", offer.name, amount=1000.0)
		offer.disabled = 1
		offer.save(ignore_permissions=True)
		ms.reload()
		ms.comments = "touched after the offer ended"
		ms.save(ignore_permissions=True)
		self.assertEqual(flt(ms.discount_value), 25.0, "the grant survives the campaign")
		self.assertEqual(
			flt(frappe.get_doc("Subscription", ms.subscription).create_invoice().net_total), 750.0
		)

	def test_editing_an_offer_does_not_change_an_existing_members_rate(self):
		offer = self._offer("DS2 Edited", discount_value=20, discount_duration=offers.EVERY_INVOICE)
		ms = self._enrol_on_offer("DS2 Edit", offer.name, amount=1000.0)
		offer.discount_value = 5
		offer.save(ignore_permissions=True)
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(flt(ms.discount_value), 20.0)

	def test_taking_the_offer_off_removes_its_discount(self):
		offer = self._offer("DS2 Removed", discount_value=20, discount_duration=offers.EVERY_INVOICE)
		ms = self._enrol_on_offer("DS2 Rem", offer.name, amount=1000.0)
		ms.offer = None
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertFalse(ms.discount_type)
		self.assertEqual(
			flt(frappe.get_doc("Subscription", ms.subscription).create_invoice().net_total), 1000.0
		)

	def test_a_hand_typed_discount_is_not_wiped_by_clearing_an_offer(self):
		plan = fx.make_plan("DS2 Manual Plan", amount=1000.0)
		member = fx.make_member("DS2 Manual Member", plan.name)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"discount_type": discounts.AMOUNT,
				"discount_value": 100,
				"discount_reason": "Long-time member",
			}
		).insert(ignore_permissions=True)
		ms.offer = None
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertEqual(flt(ms.discount_value), 100.0)

	# ---- an offer can only be given while it is available ------------------ #
	def test_an_ended_offer_cannot_be_given(self):
		offer = self._offer("DS2 Over", disabled=1)
		with self.assertRaises(frappe.ValidationError):
			self._enrol_on_offer("DS2 Ovr", offer.name)

	def test_an_expired_offer_cannot_be_given(self):
		offer = self._offer(
			"DS2 Expired", valid_from=add_days(today(), -30), valid_upto=add_days(today(), -1)
		)
		with self.assertRaises(frappe.ValidationError):
			self._enrol_on_offer("DS2 Exp", offer.name)

	def test_an_offer_that_has_not_started_cannot_be_given(self):
		offer = self._offer("DS2 Future", valid_from=add_days(today(), 7))
		with self.assertRaises(frappe.ValidationError):
			self._enrol_on_offer("DS2 Fut", offer.name)

	def test_an_offer_scoped_to_other_plans_cannot_be_given(self):
		other = fx.make_plan("DS2 Other Plan", amount=1000.0)
		offer = self._offer("DS2 Annual Only", plans=[other.name])
		with self.assertRaises(frappe.ValidationError):
			self._enrol_on_offer("DS2 Scope", offer.name)

	def test_an_offer_with_no_plans_runs_on_every_plan(self):
		offer = self._offer("DS2 All Plans", discount_value=10)
		ms = self._enrol_on_offer("DS2 AllP", offer.name, amount=1000.0)
		self.assertEqual(self._net(ms), 900.0)

	def test_an_offer_is_used_up_at_its_limit(self):
		offer = self._offer("DS2 First Two", discount_value=10, max_total_uses=2)
		plan = fx.make_plan("DS2 Limit Plan", amount=1000.0).name
		self._enrol_on_offer("DS2 L1", offer.name, plan=plan)
		self._enrol_on_offer("DS2 L2", offer.name, plan=plan)
		self.assertEqual(offers.times_used(offer.name), 2)
		with self.assertRaises(frappe.ValidationError):
			self._enrol_on_offer("DS2 L3", offer.name, plan=plan)

	def test_resaving_a_membership_does_not_burn_another_use(self):
		offer = self._offer("DS2 One Only", discount_value=10, max_total_uses=1)
		ms = self._enrol_on_offer("DS2 Once", offer.name)
		ms.comments = "saved again"
		ms.save(ignore_permissions=True)
		self.assertEqual(offers.times_used(offer.name), 1)

	# ---- the offer itself is coherent -------------------------------------- #
	def test_an_offer_cannot_end_before_it_starts(self):
		with self.assertRaises(frappe.ValidationError):
			self._offer("DS2 Backwards", valid_from=today(), valid_upto=add_days(today(), -5))

	def test_until_the_offer_ends_needs_an_end_date(self):
		with self.assertRaises(frappe.ValidationError):
			self._offer("DS2 NoEnd", discount_duration=offers.UNTIL_OFFER_ENDS)

	def test_an_offer_over_a_hundred_percent_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._offer("DS2 TooMuch", discount_value=150)

	def test_the_limit_cannot_be_cut_below_what_was_already_given(self):
		offer = self._offer("DS2 Shrink", discount_value=10, max_total_uses=5)
		plan = fx.make_plan("DS2 Shrink Plan", amount=1000.0).name
		self._enrol_on_offer("DS2 S1", offer.name, plan=plan)
		self._enrol_on_offer("DS2 S2", offer.name, plan=plan)
		offer.reload()
		offer.max_total_uses = 1
		with self.assertRaises(frappe.ValidationError):
			offer.save(ignore_permissions=True)

	# ---- what the desk is shown -------------------------------------------- #
	def test_available_offers_hides_what_cannot_be_given(self):
		plan = fx.make_plan("DS2 Desk Plan", amount=1000.0).name
		live = self._offer("DS2 Live", discount_value=15)
		self._offer("DS2 Dead", discount_value=15, disabled=1)
		self._offer("DS2 Elsewhere", discount_value=15, plans=[fx.make_plan("DS2 Elsewhere Plan").name])
		names = [o["name"] for o in offers.available_offers(membership_plan=plan)]
		self.assertIn(live.name, names)
		self.assertEqual(len(names), 1)

	def test_available_offers_drops_an_exhausted_one(self):
		plan = fx.make_plan("DS2 Gone Plan", amount=1000.0).name
		offer = self._offer("DS2 Gone", discount_value=15, max_total_uses=1)
		self._enrol_on_offer("DS2 G1", offer.name, plan=plan)
		self.assertEqual(offers.available_offers(membership_plan=plan), [])

	def test_offer_usage_reports_who_was_given_it(self):
		offer = self._offer("DS2 Usage", discount_value=15)
		ms = self._enrol_on_offer("DS2 Use", offer.name)
		usage = offers.offer_usage(offer.name)
		self.assertEqual(usage["times_used"], 1)
		self.assertIsNone(usage["uses_left"], "no limit set")
		self.assertEqual(usage["memberships"][0]["name"], ms.name)
