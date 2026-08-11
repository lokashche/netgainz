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
from frappe.utils import add_days, getdate, today

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
