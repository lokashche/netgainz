# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Switching billing on for a gym whose members were loaded, not enrolled.

Memberships imported from the gym's own records carry ``is_backfill = 1`` so the
load does not raise invoices. Nothing un-sets that, so they never bill. These tests
cover the switch that fixes it — and, above all, the thing it must never do:
invoice a member for a period the gym already collected in cash.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import go_live


class TestGoLive(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	# ---- fixtures --------------------------------------------------------- #
	def _loaded(self, tag, price=2000.0, joined_days_ago=200, plan_amount=0.0, **plan_kwargs):
		"""A membership the way the tenant loader creates one: priced, backfilled,
		and therefore with no Subscription."""
		plan = fx.make_plan(f"{tag} Plan", amount=plan_amount, **plan_kwargs)
		member = fx.make_member(
			f"{tag} Member", plan.name, date_of_joining=add_days(today(), -joined_days_ago)
		)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"tariff": price or None,
				"is_backfill": 1,
			}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _invoice_count(self, membership):
		sub = frappe.db.get_value("Membership", membership, "subscription")
		return frappe.db.count("Sales Invoice", {"subscription": sub}) if sub else 0

	# ---- the starting position -------------------------------------------- #
	def test_a_loaded_membership_does_not_bill_on_its_own(self):
		ms = self._loaded("GL Idle")
		self.assertIsNone(ms.subscription, "the loader must not raise invoices")
		self.assertIsNone(ms.current_sales_invoice)

	# ---- readiness -------------------------------------------------------- #
	def test_readiness_separates_ready_from_blocked(self):
		self._loaded("GL Ready", price=2000.0)
		self._loaded("GL NoPrice", price=0.0, plan_amount=0.0)

		report = go_live.billing_readiness()

		ready = {r["member_name"] for r in report["ready"]}
		blocked = {r["member_name"]: r["blocked_reason"] for r in report["blocked"]}
		self.assertIn("GL Ready Member", ready)
		self.assertIn("GL NoPrice Member", blocked)
		self.assertIn("No price", blocked["GL NoPrice Member"])
		self.assertEqual(report["total"], report["ready_count"] + report["blocked_count"])

	def test_readiness_warns_when_a_member_has_no_joining_date(self):
		"""21 imported members have no joining date. `Member.date_of_joining`
		defaults to Today, so this state only arises through a bulk import that
		writes the column blank — reproduce it the same way."""
		plan = fx.make_plan("GL NoJoin Plan", amount=1500.0)
		member = fx.make_member("GL NoJoin Member", plan.name)
		frappe.db.set_value("Member", member.name, "date_of_joining", None)
		frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				"is_backfill": 1,
			}
		).insert(ignore_permissions=True)

		report = go_live.billing_readiness()
		row = next(r for r in report["ready"] if r["member_name"] == "GL NoJoin Member")
		self.assertTrue(row["ready"], "a missing joining date is a warning, not a blocker")
		self.assertTrue(any("joining date" in w for w in row["warnings"]))

	def test_readiness_changes_nothing(self):
		ms = self._loaded("GL ReadOnly")
		go_live.billing_readiness()
		ms.reload()
		self.assertIsNone(ms.subscription)
		self.assertEqual(frappe.db.count("Sales Invoice", {"customer": ["like", "GL ReadOnly%"]}), 0)

	# ---- the dry run ------------------------------------------------------- #
	def test_dry_run_reports_but_creates_nothing(self):
		ms = self._loaded("GL Dry")
		result = go_live.start_billing(dry_run=1)

		self.assertTrue(result["dry_run"])
		self.assertGreaterEqual(result["started_count"], 1)
		row = next(r for r in result["started"] if r["membership"] == ms.name)
		self.assertEqual(row["price"], 2000.0)
		self.assertTrue(row["first_invoice_on"])
		ms.reload()
		self.assertIsNone(ms.subscription, "a dry run must not provision anything")

	# ---- the switch itself -------------------------------------------------- #
	def test_starting_billing_provisions_the_subscription(self):
		ms = self._loaded("GL Go")
		result = go_live.start_billing(dry_run=0)

		self.assertFalse(result["dry_run"])
		ms.reload()
		self.assertTrue(ms.subscription)
		self.assertEqual(
			frappe.db.get_value("Subscription", ms.subscription, "docstatus"), 0
		)
		self.assertFalse(ms.is_backfill, "the load flag is cleared once billing starts")

	def test_next_period_never_bills_a_period_the_gym_already_collected(self):
		"""THE guard. A member who joined on the 15th has a current period that
		started last month — starting there would invoice a month the gym has
		already taken in cash."""
		ms = self._loaded("GL Safe", joined_days_ago=200)
		row = go_live.assess(ms.name)
		self.assertLess(
			getdate(row["current_period_start"]), getdate(today()),
			"precondition: the current period started in the past",
		)

		# Default mode.
		go_live.start_billing(dry_run=0)

		ms.reload()
		start = getdate(frappe.db.get_value("Subscription", ms.subscription, "start_date"))
		self.assertEqual(start, getdate(row["next_period_start"]))
		self.assertGreater(start, getdate(today()), "billing starts in the future")
		self.assertEqual(self._invoice_count(ms.name), 0, "nothing is invoiced retroactively")

	def test_current_period_mode_bills_the_period_in_progress(self):
		"""Offered for a gym that has NOT collected the current period yet."""
		ms = self._loaded("GL Now", joined_days_ago=200)
		row = go_live.assess(ms.name)

		go_live.start_billing(start_mode=go_live.CURRENT_PERIOD, dry_run=0)

		ms.reload()
		start = getdate(frappe.db.get_value("Subscription", ms.subscription, "start_date"))
		self.assertEqual(start, getdate(row["current_period_start"]))

	def test_the_billing_day_keeps_the_members_anniversary(self):
		joined = add_days(today(), -200)
		ms = self._loaded("GL Anniversary", joined_days_ago=200)
		go_live.start_billing(dry_run=0)
		ms.reload()
		start = getdate(frappe.db.get_value("Subscription", ms.subscription, "start_date"))
		self.assertEqual(start.day, getdate(joined).day)

	# ---- safety ------------------------------------------------------------- #
	def test_running_twice_changes_nothing_the_second_time(self):
		self._loaded("GL Twice")
		first = go_live.start_billing(dry_run=0)
		self.assertGreaterEqual(first["started_count"], 1)

		second = go_live.start_billing(dry_run=0)
		self.assertEqual(second["started_count"], 0)
		self.assertTrue(
			any("Already billing" == s["reason"] for s in second["skipped"])
		)

	def test_unpriced_memberships_are_skipped_not_billed_at_zero(self):
		ms = self._loaded("GL Zero", price=0.0, plan_amount=0.0)
		result = go_live.start_billing(dry_run=0)
		ms.reload()
		self.assertIsNone(ms.subscription)
		self.assertTrue(any(s["membership"] == ms.name for s in result["skipped"]))

	def test_can_be_limited_to_named_memberships(self):
		first = self._loaded("GL Subset A")
		second = self._loaded("GL Subset B")

		go_live.start_billing(dry_run=0, memberships=[first.name])

		first.reload()
		second.reload()
		self.assertTrue(first.subscription)
		self.assertIsNone(second.subscription, "only the named membership was switched on")

	def test_a_membership_enrolled_normally_is_left_alone(self):
		"""Anything already billing must not be touched or double-provisioned."""
		ms = fx.enrol("GL Normal", amount=1000.0)
		subscription = ms.subscription
		self.assertTrue(subscription)

		go_live.start_billing(dry_run=0)

		ms.reload()
		self.assertEqual(ms.subscription, subscription)

	# ---- calendar-month alignment (some gyms bill 1st to month end) --------- #
	def test_calendar_month_starts_everyone_on_the_first(self):
		"""Not every gym wants joining-day billing; many want the month to close
		cleanly, so everyone bills 1st-to-month-end."""
		a = self._loaded("GL Cal A", price=3000.0, joined_days_ago=200)
		b = self._loaded("GL Cal B", price=1000.0, joined_days_ago=17)

		go_live.start_billing(start_mode=go_live.CALENDAR_MONTH, dry_run=0)

		first_of_next = get_first_day(add_days(get_last_day(today()), 1))
		for ms in (a, b):
			ms.reload()
			start = getdate(frappe.db.get_value("Subscription", ms.subscription, "start_date"))
			self.assertEqual(start, getdate(first_of_next))
			self.assertEqual(start.day, 1)

	def test_calendar_month_charges_the_rest_of_this_month_pro_rata(self):
		ms = self._loaded("GL Cal Part", price=3100.0)
		row = go_live.assess(ms.name)

		month_end = get_last_day(today())
		days_left = (getdate(month_end) - getdate(today())).days + 1
		self.assertEqual(row["part_month_days"], days_left)
		self.assertAlmostEqual(
			row["part_month_amount"], 3100.0 * days_left / getdate(month_end).day, places=2
		)

		go_live.start_billing(start_mode=go_live.CALENDAR_MONTH, dry_run=0)

		ms.reload()
		invoices = frappe.get_all(
			"Sales Invoice",
			filters={"subscription": ms.subscription, "docstatus": 1},
			fields=["name", "net_total"],
		)
		self.assertEqual(len(invoices), 1, "exactly one part-month invoice")
		self.assertAlmostEqual(flt(invoices[0].net_total), row["part_month_amount"], places=2)

	def test_the_part_month_invoice_counts_as_profit_first_cash(self):
		"""It is stamped with the subscription on purpose — Profit First reads cash
		from allocations against subscription-linked invoices, so an unstamped stub
		would take the member's money out of the owner's revenue."""
		from netgainz.net_gainz.accounting import billing

		ms = self._loaded("GL Cal Cash", price=3100.0)
		go_live.start_billing(start_mode=go_live.CALENDAR_MONTH, dry_run=0)
		ms.reload()

		si = billing.current_invoice(ms.name)
		outstanding = flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))
		self.assertGreater(outstanding, 0)
		billing.record_payment(ms.name, outstanding, "Cash", today())

		customer = frappe.db.get_value("Member", ms.member, "customer")
		expected = go_live.assess(ms.name)
		self.assertGreater(billing.collected_paise(today(), today(), [customer]), 0)
		self.assertIsNotNone(expected)

	def test_part_month_can_be_waived(self):
		ms = self._loaded("GL Cal NoPart", price=3100.0)
		go_live.start_billing(
			start_mode=go_live.CALENDAR_MONTH, dry_run=0, bill_part_month=0
		)
		ms.reload()
		self.assertTrue(ms.subscription)
		self.assertEqual(
			frappe.db.count("Sales Invoice", {"subscription": ms.subscription}), 0,
			"no stub invoice when the gym waives the part month",
		)

	def test_dry_run_shows_the_part_month_before_charging_it(self):
		self._loaded("GL Cal Dry", price=3100.0)
		result = go_live.start_billing(start_mode=go_live.CALENDAR_MONTH, dry_run=1)
		row = result["started"][0]
		self.assertGreater(row["part_month_amount"], 0)
		self.assertGreater(row["part_month_days"], 0)
		self.assertGreater(result["part_month_total"], 0)
		self.assertEqual(frappe.db.count("Sales Invoice"), 0, "a dry run charges nothing")

	def test_the_part_month_invoice_is_taxed_like_any_other(self):
		"""Regression: the stub came out with a GST template resolved but its tax
		ROWS never expanded — 500 -> 500 while a generated invoice went 1000 -> 1180.
		Invisible for a non-GST tenant, an under-charge for a registered one."""
		normal = fx.enrol("GL Tax Normal", amount=1000.0)
		generated = frappe.get_doc("Sales Invoice", normal.current_sales_invoice)
		tax_rate = sum(flt(t.rate) for t in generated.taxes)

		ms = self._loaded("GL Tax Part", price=1000.0)
		go_live.start_billing(start_mode=go_live.CALENDAR_MONTH, dry_run=0, memberships=[ms.name])
		ms.reload()
		stub = frappe.get_doc(
			"Sales Invoice",
			frappe.db.get_value("Sales Invoice", {"subscription": ms.subscription, "docstatus": 1}, "name"),
		)

		self.assertEqual(stub.taxes_and_charges, generated.taxes_and_charges)
		self.assertEqual(sum(flt(t.rate) for t in stub.taxes), tax_rate)
		# ...and the tax is actually charged, proportionally to the pro-rata net.
		self.assertAlmostEqual(
			flt(stub.grand_total), flt(stub.net_total) * (1 + tax_rate / 100), places=2
		)
