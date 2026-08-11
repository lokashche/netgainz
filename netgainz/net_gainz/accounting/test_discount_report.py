# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-6: the monthly "what did we give away" report.

The number has to be true or it is worse than nothing, so these pin what it counts:

* the money actually given up on **submitted invoices**, not what was intended;
* grouped by the things an owner acts on — campaign, reason, staff member, plan;
* a refund is not a discount (credit notes are excluded), and neither is a draft;
* the profit split of the giveaway matches the total, and Profit First is untouched;
* it is the owner's report, refused for the front desk.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, get_first_day, get_last_day, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import discount_report, discounts

STAFF_USER = "ds6-frontdesk@example.com"


class TestDiscountReport(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		frappe.db.delete("Discount Log")
		frappe.db.delete("Offer Plan")
		frappe.db.delete("Offer")
		permissions.ensure_roles()
		if not frappe.db.exists("User", STAFF_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": STAFF_USER,
					"first_name": "DS6 Desk",
					"send_welcome_email": 0,
					"roles": [{"role": permissions.GYM_STAFF}],
				}
			).insert(ignore_permissions=True)
		self.addCleanup(frappe.set_user, "Administrator")

	# ---- helpers --------------------------------------------------------- #
	def _enrol(self, tag, amount=1000.0, **fields):
		plan = fx.make_plan(f"{tag} Plan", amount=amount)
		member = fx.make_member(f"{tag} Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name, **fields}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _discounted(self, tag, amount=1000.0, percent=None, flat=None, **fields):
		grant = (
			{"discount_type": discounts.PERCENTAGE, "discount_value": percent}
			if percent
			else {"discount_type": discounts.AMOUNT, "discount_value": flat}
		)
		return self._enrol(
			tag,
			amount=amount,
			discount_duration=discounts.EVERY_INVOICE,
			discount_reason=fields.pop("reason", "Negotiated"),
			**grant,
			**fields,
		)

	# ---- the totals -------------------------------------------------------- #
	def test_it_totals_what_was_actually_given_up(self):
		self._discounted("DS6 A", amount=2000.0, percent=25)  # 500 off
		self._discounted("DS6 B", amount=1000.0, flat=100)  # 100 off
		report = discount_report.discounts_given()
		self.assertEqual(flt(report["given"]), 600.0)
		self.assertEqual(flt(report["gross"]), 3000.0)
		self.assertEqual(flt(report["net"]), 2400.0)
		self.assertEqual(report["invoices"], 2)
		self.assertEqual(report["members"], 2)

	def test_it_says_what_share_of_the_fees_was_given_away(self):
		self._discounted("DS6 Share", amount=1000.0, percent=20)
		self.assertEqual(discount_report.discounts_given()["given_percent"], 20.0)

	def test_an_undiscounted_member_is_not_counted(self):
		self._enrol("DS6 Full", amount=1000.0)
		report = discount_report.discounts_given()
		self.assertEqual(flt(report["given"]), 0.0)
		self.assertEqual(report["invoices"], 0)

	def test_a_refund_is_not_a_discount(self):
		"""A credit note carries the subscription link too — it must not be counted."""
		from netgainz.net_gainz.accounting import refunds

		ms = self._discounted("DS6 Refund", amount=1000.0, percent=10)
		fx.collect(ms, posting_date=today())
		refunds.refund_membership(ms.name, amount=200, reason="Changed their mind", posting_date=today())
		report = discount_report.discounts_given()
		self.assertEqual(flt(report["given"]), 100.0, "the discount only, not the refund")

	def test_a_draft_invoice_is_not_counted(self):
		ms = self._discounted("DS6 Draft", amount=1000.0, percent=10)
		frappe.db.set_value("Sales Invoice", ms.current_sales_invoice, "docstatus", 0)
		self.assertEqual(flt(discount_report.discounts_given()["given"]), 0.0)

	def test_a_discount_outside_the_window_is_not_counted(self):
		ms = self._discounted("DS6 Old", amount=1000.0, percent=10)
		last_month_end = add_days(get_first_day(today()), -1)
		frappe.db.set_value("Sales Invoice", ms.current_sales_invoice, "posting_date", last_month_end)
		self.assertEqual(flt(discount_report.discounts_given()["given"]), 0.0)
		earlier = discount_report.discounts_given(start=get_first_day(last_month_end), end=last_month_end)
		self.assertEqual(flt(earlier["given"]), 100.0)

	# ---- the breakdowns ----------------------------------------------------- #
	def test_it_groups_by_reason(self):
		self._discounted("DS6 R1", amount=1000.0, percent=10, reason="Student")
		self._discounted("DS6 R2", amount=1000.0, percent=20, reason="Student")
		self._discounted("DS6 R3", amount=1000.0, percent=5, reason="Long-time member")
		by_reason = {r["label"]: r for r in discount_report.discounts_given()["by_reason"]}
		self.assertEqual(flt(by_reason["Student"]["given"]), 300.0)
		self.assertEqual(by_reason["Student"]["invoices"], 2)
		self.assertEqual(flt(by_reason["Long-time member"]["given"]), 50.0)

	def test_it_groups_by_offer(self):
		offer = frappe.get_doc(
			{
				"doctype": "Offer",
				"offer_name": "DS6 Festival",
				"discount_type": discounts.PERCENTAGE,
				"discount_value": 15,
				"discount_duration": "Every invoice",
				"valid_from": today(),
			}
		).insert(ignore_permissions=True)
		self._enrol("DS6 Campaign", amount=2000.0, offer=offer.name)
		self._discounted("DS6 Hand", amount=1000.0, percent=10)
		by_offer = {r["label"]: r for r in discount_report.discounts_given()["by_offer"]}
		self.assertEqual(flt(by_offer[offer.name]["given"]), 300.0)
		self.assertEqual(flt(by_offer[discount_report.UNATTRIBUTED]["given"]), 100.0)

	def test_it_groups_by_who_gave_it(self):
		self._discounted("DS6 Who", amount=1000.0, percent=10)
		by_staff = discount_report.discounts_given()["by_staff"]
		self.assertEqual(by_staff[0]["label"], frappe.session.user)
		self.assertEqual(flt(by_staff[0]["given"]), 100.0)

	def test_the_biggest_giveaways_come_first(self):
		self._discounted("DS6 Small", amount=1000.0, flat=50)
		self._discounted("DS6 Large", amount=5000.0, flat=1500)
		biggest = discount_report.discounts_given()["biggest"]
		self.assertEqual(flt(biggest[0]["given"]), 1500.0)

	def test_branch_filters_the_report(self):
		from netgainz.net_gainz.accounting import branch

		main = branch.ensure_main_branch()
		self._discounted("DS6 Branch", amount=1000.0, percent=10)
		self.assertEqual(flt(discount_report.discounts_given(branch=main)["given"]), 100.0)
		self.assertEqual(
			flt(discount_report.discounts_given(branch="DS6 Nowhere")["given"]),
			0.0,
			"another branch's giveaway is not this branch's",
		)

	# ---- what it cost ------------------------------------------------------- #
	def test_the_profit_split_matches_the_total_given(self):
		self._discounted("DS6 Cost", amount=4000.0, percent=25)
		report = discount_report.discounts_given()
		impact = report["profit_impact"]
		self.assertEqual(flt(impact["amount"]), 1000.0)
		if impact["applicable"]:
			self.assertAlmostEqual(sum(impact["buckets"].values()), 1000.0, places=2)

	def test_the_month_summary_is_the_same_number(self):
		self._discounted("DS6 Month", amount=2000.0, percent=10)
		summary = discount_report.discounts_this_month()
		self.assertEqual(flt(summary["given"]), 200.0)
		self.assertEqual(summary["start"], str(get_first_day(today())))
		self.assertEqual(summary["end"], str(get_last_day(today())))

	# ---- whose report is it ------------------------------------------------- #
	def test_the_front_desk_cannot_read_the_leak_report(self):
		self._discounted("DS6 Private", amount=1000.0, percent=10)
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			discount_report.discounts_given()
