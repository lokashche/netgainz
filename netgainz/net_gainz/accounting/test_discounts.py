# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-1: a negotiated discount is a controlled, ending, visible decision.

These pin the four things a gym's discount has to get right:

* the money lands on the **invoice** (never the plan's price — R14), on the **net**
  total so GST is charged on what the member actually pays (R20);
* it **ends** when the grantor said it would (R18) — the classic front-desk fight;
* it cannot be granted incoherently or silently (R17 — server-side, reason required);
* Profit First keeps working untouched, because it reads collected cash (R15).

The full catalogue x billing-modes x cadences matrix belongs to DS-7; this module
covers the DS-1 slice.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz.accounting import billing, discounts
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestMembershipDiscounts(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	# ---- helpers --------------------------------------------------------- #
	def _enrol_with_discount(self, tag, amount=1000.0, price=None, **grant):
		"""Enrol a member whose membership carries a discount grant from the start."""
		plan = fx.make_plan(f"{tag} Plan", amount=amount)
		member = fx.make_member(f"{tag} Member", plan.name)
		doc = {
			"doctype": "Membership",
			"member": member.name,
			"membership_plan": plan.name,
			"discount_reason": "Traced in DS-1 tests",
		}
		if price is not None:
			doc["tariff"] = price
		doc.update(grant)
		ms = frappe.get_doc(doc).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _si(self, name):
		return frappe.get_doc("Sales Invoice", name)

	def _next_invoice(self, membership):
		"""The membership's following period, billed by the same Subscription."""
		return frappe.get_doc("Subscription", membership.subscription).create_invoice()

	# ---- the money lands on the invoice ---------------------------------- #
	def test_percentage_discount_reaches_the_invoice_net_of_gst(self):
		ms = self._enrol_with_discount(
			"DS1 Pct", amount=1000.0, discount_type=discounts.PERCENTAGE, discount_value=10
		)
		si = self._si(ms.current_sales_invoice)
		self.assertEqual(flt(si.items[0].rate), 1000.0, "the plan's price of record is untouched")
		self.assertEqual(flt(si.net_total), 900.0)
		self.assertEqual(si.apply_discount_on, "Net Total", "R20 — GST follows the discount")
		# 18% GST on the DISCOUNTED value, not on 1000.
		self.assertEqual(flt(si.grand_total), 1062.0)

	def test_flat_amount_discount_reaches_the_invoice(self):
		ms = self._enrol_with_discount(
			"DS1 Amt", amount=2000.0, discount_type=discounts.AMOUNT, discount_value=500
		)
		si = self._si(ms.current_sales_invoice)
		self.assertEqual(flt(si.discount_amount), 500.0)
		self.assertEqual(flt(si.net_total), 1500.0)

	def test_discount_comes_off_the_members_own_price_not_the_plans(self):
		"""Per-member pricing and discounts compose: 10% off HIS 2,500, not the plan's 1,000."""
		ms = self._enrol_with_discount(
			"DS1 Own",
			amount=1000.0,
			price=2500.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=10,
		)
		self.assertEqual(flt(self._si(ms.current_sales_invoice).net_total), 2250.0)

	def test_complimentary_membership_still_gets_an_invoice(self):
		"""100% off: revenue zero, but the member stays operationally real."""
		ms = self._enrol_with_discount(
			"DS1 Comp", amount=1500.0, discount_type=discounts.PERCENTAGE, discount_value=100
		)
		si = self._si(ms.current_sales_invoice)
		self.assertTrue(si.name)
		self.assertEqual(flt(si.net_total), 0.0)
		self.assertEqual(flt(si.grand_total), 0.0)

	def test_a_flat_discount_can_never_make_an_invoice_negative(self):
		ms = self._enrol_with_discount(
			"DS1 Cap", amount=800.0, discount_type=discounts.AMOUNT, discount_value=800
		)
		self.assertEqual(flt(self._si(ms.current_sales_invoice).grand_total), 0.0)

	# ---- R18: every discount ends when it was said to end ----------------- #
	def test_first_invoice_only_stops_after_the_joining_cycle(self):
		ms = self._enrol_with_discount(
			"DS1 First",
			amount=1000.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=20,
			discount_duration=discounts.FIRST_INVOICE,
		)
		self.assertEqual(flt(self._si(ms.current_sales_invoice).net_total), 800.0)
		self.assertEqual(flt(self._next_invoice(ms).net_total), 1000.0, "renewal bills full rate")

	def test_every_invoice_is_a_lifetime_rate(self):
		ms = self._enrol_with_discount(
			"DS1 Every",
			amount=1000.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=20,
			discount_duration=discounts.EVERY_INVOICE,
		)
		self.assertEqual(flt(self._si(ms.current_sales_invoice).net_total), 800.0)
		self.assertEqual(flt(self._next_invoice(ms).net_total), 800.0)

	def test_until_a_date_expires_on_its_own(self):
		ms = self._enrol_with_discount(
			"DS1 Until",
			amount=1000.0,
			discount_type=discounts.AMOUNT,
			discount_value=200,
			discount_duration=discounts.UNTIL_DATE,
			discount_until=add_days(today(), 30),
		)
		self.assertEqual(flt(self._si(ms.current_sales_invoice).net_total), 800.0)

		ms.db_set("discount_until", add_days(today(), -1))
		ms.reload()
		self.assertEqual(flt(self._next_invoice(ms).net_total), 1000.0)

	def test_removing_the_discount_restores_the_full_rate(self):
		ms = self._enrol_with_discount(
			"DS1 Removed",
			amount=1000.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=25,
			discount_duration=discounts.EVERY_INVOICE,
		)
		self.assertEqual(flt(self._si(ms.current_sales_invoice).net_total), 750.0)
		ms.discount_type = ""
		ms.save(ignore_permissions=True)
		self.assertEqual(flt(self._next_invoice(ms).net_total), 1000.0)

	# ---- R17: guardrails hold server-side --------------------------------- #
	def test_a_discount_without_a_reason_is_rejected(self):
		plan = fx.make_plan("DS1 Guard Plan", amount=1000.0)
		member = fx.make_member("DS1 Guard Member", plan.name)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Membership",
					"member": member.name,
					"membership_plan": plan.name,
					"discount_type": discounts.PERCENTAGE,
					"discount_value": 10,
				}
			).insert(ignore_permissions=True)

	def test_more_than_a_hundred_percent_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._enrol_with_discount(
				"DS1 Over", amount=1000.0, discount_type=discounts.PERCENTAGE, discount_value=120
			)

	def test_an_amount_above_the_price_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._enrol_with_discount(
				"DS1 Above", amount=1000.0, discount_type=discounts.AMOUNT, discount_value=1500
			)

	def test_until_a_date_needs_the_date(self):
		with self.assertRaises(frappe.ValidationError):
			self._enrol_with_discount(
				"DS1 NoDate",
				amount=1000.0,
				discount_type=discounts.AMOUNT,
				discount_value=100,
				discount_duration=discounts.UNTIL_DATE,
			)

	def test_a_value_without_a_type_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._enrol_with_discount("DS1 NoType", amount=1000.0, discount_value=100)

	def test_the_grantor_is_stamped_server_side(self):
		ms = self._enrol_with_discount(
			"DS1 Who", amount=1000.0, discount_type=discounts.AMOUNT, discount_value=100
		)
		self.assertEqual(ms.discount_granted_by, frappe.session.user)

	# ---- R15: Profit First needs no code change --------------------------- #
	def test_collected_cash_follows_the_discount_with_no_pf_change(self):
		"""A discounted member simply contributes less cash; the allocation math
		takes care of itself because PF reads Payment Entries, not invoices."""
		ms = self._enrol_with_discount(
			"DS1 Cash",
			amount=2000.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=25,
			discount_duration=discounts.EVERY_INVOICE,
		)
		fx.collect(ms, posting_date=today())
		collected = billing.membership_collected_paise(today(), today(), members=[ms.member])
		self.assertEqual(collected, 150_000, "Rs.1,500 ex-GST — 2,000 less 25%")

	# ---- the grant-time preview ------------------------------------------- #
	def test_preview_shows_gross_discount_and_net(self):
		preview = discounts.preview_discount(
			price=2000, discount_type=discounts.PERCENTAGE, discount_value=10
		)
		self.assertEqual(flt(preview["gross"]), 2000.0)
		self.assertEqual(flt(preview["discount"]), 200.0)
		self.assertEqual(flt(preview["net"]), 1800.0)

	def test_preview_reads_an_existing_membership(self):
		ms = self._enrol_with_discount(
			"DS1 Preview", amount=1200.0, discount_type=discounts.AMOUNT, discount_value=300
		)
		preview = discounts.preview_discount(membership=ms.name)
		self.assertEqual(flt(preview["gross"]), 1200.0)
		self.assertEqual(flt(preview["discount"]), 300.0)
		self.assertEqual(flt(preview["net"]), 900.0)

	def test_profit_impact_splits_the_giveaway_across_the_buckets(self):
		"""Whatever the tier, the preview never invents or loses money."""
		impact = discounts.profit_impact(1000)
		self.assertEqual(flt(impact["amount"]), 1000.0)
		if impact["applicable"]:
			self.assertAlmostEqual(sum(impact["buckets"].values()), 1000.0, places=2)
