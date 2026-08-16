# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Per-member pricing: a Membership Plan holds ONE price, a gym does not.

The pilot has 64 members on "Monthly" paying 18 different amounts, so the plan's
amount is the default and ``Membership.tariff`` is the truth. These tests pin the
seam that makes that work — the rate applied to the generated invoice — plus the
guard that stops an unpriced membership raising a submitted Rs.0 invoice.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestMemberPricing(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	# ---- helpers --------------------------------------------------------- #
	def _enrol_at(self, tag, price, plan_amount=1000.0, **kwargs):
		"""Enrol a member who has negotiated their own ``price``."""
		plan = fx.make_plan(f"{tag} Plan", amount=plan_amount, **kwargs)
		member = fx.make_member(f"{tag} Member", plan.name)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"tariff": price,
			}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _net(self, si):
		return flt(frappe.db.get_value("Sales Invoice", si, "net_total"))

	# ---- the price actually reaches the invoice --------------------------- #
	def test_member_price_beats_the_plan_price(self):
		ms = self._enrol_at("MP Own", price=2500.0, plan_amount=1000.0)
		self.assertEqual(self._net(ms.current_sales_invoice), 2500.0)

	def test_blank_price_falls_back_to_the_plan(self):
		"""`tariff` carries fetch_from/fetch_if_empty, so a blank price fills itself
		from the plan — the plan amount stays the default for everyone else."""
		ms = fx.enrol("MP Plan", amount=1400.0)
		self.assertEqual(flt(ms.tariff), 1400.0)
		self.assertEqual(self._net(ms.current_sales_invoice), 1400.0)

	def test_two_members_on_one_plan_bill_differently(self):
		"""The whole point: one plan, many negotiated prices."""
		plan = fx.make_plan("MP Shared Plan", amount=1000.0)
		prices = (900.0, 3200.0, 15000.0)
		invoiced = []
		for index, price in enumerate(prices):
			member = fx.make_member(f"MP Shared Member {index}", plan.name)
			ms = frappe.get_doc(
				{
					"doctype": "Membership",
					"member": member.name,
					"membership_plan": plan.name,
					"tariff": price,
				}
			).insert(ignore_permissions=True)
			ms.reload()
			invoiced.append(self._net(ms.current_sales_invoice))
		self.assertEqual(invoiced, list(prices))
		# ...and the shared plan's own price is untouched by any of them.
		self.assertEqual(flt(frappe.db.get_value("Membership Plan", plan.name, "amount")), 1000.0)

	def test_the_member_price_drives_cash_status_and_profit_first(self):
		ms = self._enrol_at("MP Flow", price=2500.0, plan_amount=1000.0)
		si = ms.current_sales_invoice
		outstanding = flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))

		billing.record_payment(ms.name, outstanding, "Cash", today())

		ms.reload()
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertEqual(ms.status, "Paid")
		customer = frappe.db.get_value("Member", ms.member, "customer")
		# Ex-GST, the member's own price is what Profit First sees.
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 250000)

	def test_installments_split_the_member_price_not_the_plan_price(self):
		ms = self._enrol_at(
			"MP Parts",
			price=9000.0,
			plan_amount=3000.0,
			plan_type="Quarterly",
			parts=3,
			gap_days=30,
		)
		self.assertEqual(self._net(ms.current_sales_invoice), 9000.0)
		obligations = billing.open_obligations(ms.name)
		self.assertEqual(len(obligations), 3)
		gross = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		self.assertAlmostEqual(sum(flt(o["amount"]) for o in obligations), gross, places=2)

	def test_pay_as_you_go_bills_one_part_of_the_member_price(self):
		"""PAYG raises an invoice per installment, so each is the member's price
		divided by the parts — not the plan's."""
		ms = self._enrol_at(
			"MP PAYG",
			price=12000.0,
			plan_amount=3000.0,
			plan_type="Quarterly",
			billing_mode="Pay-as-you-go",
			parts=3,
		)
		self.assertEqual(billing.installment_parts(ms), 3)
		self.assertEqual(billing.membership_price(ms), 4000.0)
		self.assertEqual(self._net(ms.current_sales_invoice), 4000.0)

	def test_renewal_periods_keep_the_member_price(self):
		ms = self._enrol_at("MP Renew", price=2500.0, plan_amount=1000.0)
		billing.record_payment(
			ms.name,
			flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount")),
			"Cash",
			today(),
		)
		sub = frappe.get_doc("Subscription", ms.subscription)
		period_two = sub.create_invoice()
		self.assertEqual(self._net(period_two.name), 2500.0)

	def test_changing_the_price_applies_to_the_next_period_only(self):
		ms = self._enrol_at("MP Change", price=2000.0, plan_amount=1000.0)
		first = ms.current_sales_invoice
		ms.tariff = 2600.0
		ms.save(ignore_permissions=True)

		self.assertEqual(self._net(first), 2000.0, "an issued invoice is not rewritten")
		sub = frappe.get_doc("Subscription", ms.subscription)
		self.assertEqual(self._net(sub.create_invoice().name), 2600.0)

	# ---- the zero-price guard --------------------------------------------- #
	def test_an_unpriced_membership_raises_no_invoice(self):
		"""A plan at 0 and no member price must not produce a submitted Rs.0
		invoice — that is silent revenue leakage and a mess to unwind."""
		plan = fx.make_plan("MP Zero Plan", amount=0.0)
		member = fx.make_member("MP Zero Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()

		self.assertFalse(billing.is_billable(ms))
		self.assertIsNone(ms.subscription, "no Subscription, so the scheduler cannot bill either")
		self.assertIsNone(ms.current_sales_invoice)
		self.assertEqual(
			frappe.db.count(
				"Sales Invoice", {"customer": frappe.db.get_value("Member", member.name, "customer")}
			),
			0,
		)

	def test_a_member_price_rescues_a_plan_priced_at_zero(self):
		"""The pilot's real shape: all four plans sit at 0 and every member carries
		their own figure."""
		ms = self._enrol_at("MP Rescue", price=1800.0, plan_amount=0.0)
		self.assertTrue(billing.is_billable(ms))
		self.assertEqual(self._net(ms.current_sales_invoice), 1800.0)

	def test_unbillable_report_lists_them_with_a_reason(self):
		plan = fx.make_plan("MP Report Plan", amount=0.0)
		member = fx.make_member("MP Report Member", plan.name)
		frappe.get_doc({"doctype": "Membership", "member": member.name, "membership_plan": plan.name}).insert(
			ignore_permissions=True
		)
		self._enrol_at("MP Report Priced", price=1200.0, plan_amount=0.0)

		report = billing.unbillable_memberships()
		names = {r["member_name"] for r in report["rows"]}
		self.assertIn("MP Report Member", names)
		self.assertNotIn("MP Report Priced Member", names)
		row = next(r for r in report["rows"] if r["member_name"] == "MP Report Member")
		self.assertFalse(row["has_subscription"])
		self.assertIn("no amount on the plan", row["reason"])

	def test_setting_a_price_later_starts_billing(self):
		"""The owner works the unbillable list, sets a price, and generates."""
		plan = fx.make_plan("MP Later Plan", amount=0.0)
		member = fx.make_member("MP Later Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()
		self.assertIsNone(ms.subscription)

		ms.tariff = 2200.0
		ms.save(ignore_permissions=True)
		result = billing.generate_membership_invoice(ms.name)

		self.assertTrue(result["sales_invoice"])
		self.assertEqual(self._net(result["sales_invoice"]), 2200.0)
		self.assertEqual(billing.unbillable_memberships()["count"], 0)
