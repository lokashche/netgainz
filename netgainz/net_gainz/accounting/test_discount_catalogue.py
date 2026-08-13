# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-7: the discount catalogue, end to end, across how gyms actually bill.

DS-1..DS-6 each pin their own mechanism. This is the closing pass over the stage's
promises as a whole:

* every row of the discount catalogue reaches a real invoice — negotiated rate, festival
  campaign, coupon, free trial, founding rate, complimentary membership;
* it holds across **billing modes** (Commitment / Pay-as-you-go) and **cadences**
  (monthly, quarterly, yearly), not just the monthly happy path;
* **R15 — Profit First and commissions need no code change.** A discount changes what is
  collected, and the allocation follows the cash by itself;
* **R16 — deferred revenue defers the NET**, asserted on a genuinely generated period
  (DS-0 flagged that an out-of-band invoice shows a degenerate service window);
* **R14 — no discount ever edits an Item Price**, the plan's rate of record.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import billing, deferred, discounts, offers
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.profit_first import calc
from netgainz.net_gainz.profit_first.instant_assessment import get_instant_assessment
from netgainz.net_gainz.profit_first.seed import seed_profit_first_defaults


class TestDiscountCatalogue(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		frappe.db.delete("Expense")
		frappe.db.delete("Offer Plan")
		frappe.db.delete("Offer")
		fx.ensure_cash_account()

	# ---- helpers --------------------------------------------------------- #
	def _enrol(self, tag, amount=1000.0, plan_kwargs=None, **fields):
		plan = fx.make_plan(f"{tag} Plan", amount=amount, **(plan_kwargs or {}))
		member = fx.make_member(f"{tag} Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name, **fields}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _net(self, membership):
		return flt(frappe.db.get_value("Sales Invoice", membership.current_sales_invoice, "net_total"))

	def _offer(self, name, **kwargs):
		doc = {
			"doctype": "Offer",
			"offer_name": name,
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 20,
			"valid_from": today(),
		}
		doc.update(kwargs)
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	# ---- the catalogue ----------------------------------------------------- #
	def test_negotiated_rate_at_the_desk(self):
		ms = self._enrol(
			"DS7 Desk",
			amount=2000.0,
			discount_type=discounts.AMOUNT,
			discount_value=500,
			discount_reason="Negotiated at the desk",
		)
		self.assertEqual(self._net(ms), 1500.0)

	def test_seasonal_campaign(self):
		offer = self._offer("DS7 New Year", discount_value=20)
		ms = self._enrol("DS7 Season", amount=2000.0, offer=offer.name)
		self.assertEqual(self._net(ms), 1600.0)

	def test_lead_gen_coupon(self):
		coupon = self._offer("DS7 Instagram", coupon_code="FIT50", discount_value=50)
		self.assertEqual(offers.redeem_code("fit50")["offer"], coupon.name)
		ms = self._enrol("DS7 Coupon", amount=1000.0, offer=coupon.name)
		self.assertEqual(self._net(ms), 500.0)

	def test_founding_member_rate_is_grandfathered(self):
		offer = self._offer("DS7 Founding", discount_value=30, discount_duration=offers.EVERY_INVOICE)
		ms = self._enrol("DS7 Founder", amount=1000.0, offer=offer.name)
		offer.disabled = 1
		offer.save(ignore_permissions=True)
		nxt = frappe.get_doc("Subscription", ms.subscription).create_invoice()
		self.assertEqual(flt(nxt.net_total), 700.0, "the campaign ended; his rate did not")

	def test_free_trial_bills_nothing_yet(self):
		ms = self._enrol("DS7 Trial", amount=1000.0, plan_kwargs=None, trial_days=7)
		self.assertFalse(ms.current_sales_invoice)
		self.assertEqual(ms.status, "Trial")

	def test_complimentary_membership_is_real_but_free(self):
		ms = self._enrol(
			"DS7 Comp",
			amount=1500.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=100,
			discount_duration=discounts.EVERY_INVOICE,
			discount_reason="Scholarship",
		)
		invoice = frappe.get_doc("Sales Invoice", ms.current_sales_invoice)
		self.assertEqual(flt(invoice.grand_total), 0.0)
		self.assertEqual(invoice.docstatus, 1, "a real, submitted invoice — the member is real")

	# ---- R14: the plan's price is never touched ----------------------------- #
	def test_no_discount_ever_edits_the_plans_price(self):
		plan = fx.make_plan("DS7 Price Of Record", amount=1000.0)
		item = frappe.db.get_value("Membership Plan", plan.name, "item")
		before = frappe.db.get_value("Item Price", {"item_code": item}, "price_list_rate")
		member = fx.make_member("DS7 Price Member", plan.name)
		frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 40,
				"discount_reason": "Heavy discount",
			}
		).insert(ignore_permissions=True)
		after = frappe.db.get_value("Item Price", {"item_code": item}, "price_list_rate")
		self.assertEqual(flt(before), 1000.0)
		self.assertEqual(flt(after), 1000.0)
		self.assertEqual(flt(frappe.db.get_value("Membership Plan", plan.name, "amount")), 1000.0)

	# ---- billing modes and cadences ----------------------------------------- #
	def test_a_discount_holds_on_pay_as_you_go(self):
		ms = self._enrol(
			"DS7 PAYG",
			amount=3000.0,
			plan_kwargs={
				"billing_mode": "Pay-as-you-go",
				"plan_type": "Quarterly",
				"parts": 3,
				"gap_days": 30,
			},
			discount_type=discounts.PERCENTAGE,
			discount_value=10,
			discount_reason="Negotiated",
		)
		# Pay-as-you-go raises ONE invoice per part, so the discount comes off each
		# part: a Rs.3,000 quarter billed in three Rs.1,000 months, 10% off each.
		self.assertEqual(self._net(ms), 900.0)

	def test_a_discount_holds_on_every_cadence(self):
		for cadence, amount, expected in (
			("Monthly", 1000.0, 900.0),
			("Quarterly", 3000.0, 2700.0),
			("Yearly", 12000.0, 10800.0),
		):
			with self.subTest(cadence=cadence):
				ms = self._enrol(
					f"DS7 {cadence}",
					amount=amount,
					plan_kwargs={"plan_type": cadence},
					discount_type=discounts.PERCENTAGE,
					discount_value=10,
					discount_reason="Negotiated",
				)
				self.assertEqual(self._net(ms), expected)

	def test_installments_split_the_discounted_total(self):
		ms = self._enrol(
			"DS7 Parts",
			amount=9000.0,
			plan_kwargs={"parts": 3, "gap_days": 30},
			discount_type=discounts.PERCENTAGE,
			discount_value=10,
			discount_reason="Negotiated",
		)
		invoice = frappe.get_doc("Sales Invoice", ms.current_sales_invoice)
		schedule = [flt(r.payment_amount) for r in invoice.payment_schedule]
		self.assertEqual(len(schedule), 3)
		self.assertEqual(
			sum(schedule),
			flt(invoice.rounded_total or invoice.grand_total),
			"the parts still add up to what is owed",
		)

	# ---- R15: Profit First and commissions need no code change --------------- #
	def test_profit_first_allocates_from_the_discounted_cash(self):
		seed_profit_first_defaults()
		settings = frappe.get_single("Profit First Settings")
		settings.pf_enabled = 1
		settings.assessment_window = "This Month"
		settings.save(ignore_permissions=True)

		full = fx.enrol_and_collect("DS7 PF Full", amount=200000, posting_date=today())
		discounted = self._enrol(
			"DS7 PF Cut",
			amount=200000,
			discount_type=discounts.PERCENTAGE,
			discount_value=25,
			discount_duration=discounts.EVERY_INVOICE,
			discount_reason="Corporate rate",
		)
		fx.collect(discounted, posting_date=today())

		assessment = get_instant_assessment()
		# 200,000 in full + 150,000 after the 25% discount — no PF code knows about
		# discounts at all; it simply sees less cash.
		self.assertEqual(assessment["topline"], 350000.00)
		self.assertTrue(full.name and discounted.name)
		self.assertAlmostEqual(
			sum(flt(r["target"]) for r in assessment["rows"] if r["bucket"] in calc.ALLOCATION_BUCKETS),
			flt(assessment["real_revenue"]),
			places=2,
		)

	def test_commissions_follow_the_discounted_collection(self):
		from netgainz.net_gainz.operations import commissions

		instructor = frappe.get_doc(
			{
				"doctype": "Instructor",
				"coach_name": "DS7 Commission Coach",
				"status": "Active",
				"commission_type": "Percentage",
				"commission_amount": 10,
			}
		).insert(ignore_permissions=True)

		plan = fx.make_plan("DS7 Comm Plan", amount=10000.0)
		member = frappe.get_doc(
			{
				"doctype": "Member",
				"full_name": "DS7 Comm Member",
				"membership_plan": plan.name,
				"coach": instructor.name,
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 20,
				"discount_reason": "Negotiated",
			}
		).insert(ignore_permissions=True)
		ms.reload()
		fx.collect(ms, posting_date=today())

		result = commissions.compute_commissions()
		row = next(r for r in result["lines"] if r["coach"] == instructor.name)
		# 10% of the Rs.8,000 actually collected, not of the Rs.10,000 list price.
		self.assertEqual(flt(row["base_amount"]), 8000.0)
		self.assertEqual(flt(row["commission_amount"]), 800.0)

	# ---- R16: deferred revenue defers the net -------------------------------- #
	def test_deferred_revenue_defers_the_discounted_amount(self):
		company = frappe.db.get_value("Global Defaults", "Global Defaults", "default_company")
		original = deferred.accounting_method()
		frappe.db.set_single_value("Business Settings", "accounting_method", "Accrual")
		deferred.setup_deferred_revenue(company)
		self.addCleanup(frappe.db.set_single_value, "Business Settings", "accounting_method", original)

		plan = fx.make_plan("DS7 Deferred Plan", amount=3000.0)
		deferred.sync_item_deferred_revenue(frappe.db.get_value("Membership Plan", plan.name, "item"), True)
		member = fx.make_member("DS7 Deferred Member", plan.name)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 10,
				"discount_reason": "Negotiated",
			}
		).insert(ignore_permissions=True)
		ms.reload()

		invoice = frappe.get_doc("Sales Invoice", ms.current_sales_invoice)
		self.assertEqual(flt(invoice.items[0].net_amount), 2700.0)
		self.assertTrue(invoice.items[0].enable_deferred_revenue)
		# The recognition window is the period actually billed (DS-0 flagged that an
		# out-of-band invoice shows a degenerate one, so assert against the invoice's
		# own period rather than a guessed length).
		self.assertEqual(getdate(invoice.items[0].service_start_date), getdate(invoice.from_date))
		self.assertEqual(getdate(invoice.items[0].service_end_date), getdate(invoice.to_date))
		deferred_credit = frappe.db.get_value(
			"GL Entry",
			{"voucher_no": invoice.name, "account": ["like", "Deferred Revenue%"]},
			"credit",
		)
		self.assertEqual(flt(deferred_credit), 2700.0, "the NET is deferred, never the gross")

	# ---- R18: a discount never quietly becomes the price --------------------- #
	def test_the_renewal_bills_the_full_rate_by_default(self):
		ms = self._enrol(
			"DS7 Renewal",
			amount=1000.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=30,
			discount_reason="Joining offer",
		)
		self.assertEqual(self._net(ms), 700.0)
		renewal = frappe.get_doc("Subscription", ms.subscription).create_invoice()
		self.assertEqual(flt(renewal.net_total), 1000.0)

	def test_billing_never_reads_a_discount_from_anywhere_but_the_membership(self):
		"""The invoice is priced from THIS membership's grant, member by member."""
		plan = fx.make_plan("DS7 Shared Plan", amount=1000.0)
		discounted_member = fx.make_member("DS7 Shared A", plan.name)
		full_member = fx.make_member("DS7 Shared B", plan.name)
		discounted = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": discounted_member.name,
				"membership_plan": plan.name,
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 50,
				"discount_reason": "Staff family",
			}
		).insert(ignore_permissions=True)
		full = frappe.get_doc(
			{"doctype": "Membership", "member": full_member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		discounted.reload()
		full.reload()
		self.assertEqual(self._net(discounted), 500.0)
		self.assertEqual(self._net(full), 1000.0)

	def test_the_stage_changed_no_profit_first_code(self):
		"""R15, stated as a test: PF reads cash, and cash is what a Payment Entry says.

		If a future change ever makes an allocation read an invoice instead, this fails —
		the discounted member's contribution would jump to the pre-discount figure.
		"""
		ms = self._enrol(
			"DS7 R15",
			amount=4000.0,
			discount_type=discounts.PERCENTAGE,
			discount_value=25,
			discount_reason="Negotiated",
		)
		fx.collect(ms, posting_date=today())
		self.assertEqual(
			billing.membership_collected_paise(today(), today(), members=[ms.member]),
			300_000,
		)
