# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Tests for Profit First scheduling + dashboard (Stage 5c).

Run: bench --site <site> run-tests --module netgainz.net_gainz.profit_first.test_schedule
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from netgainz.net_gainz.profit_first import accounts, dashboard, schedule
from netgainz.net_gainz.profit_first.seed import seed_profit_first_defaults


class TestPFSchedule(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("PF Sweep")
		frappe.db.delete("Membership")

		seed_profit_first_defaults()
		company = accounts.default_company()
		s = frappe.get_single("Profit First Settings")
		s.pf_enabled = 1
		s.sweep_auto_create = 1
		s.allocation_days = "10, 25"
		s.assessment_window = "This Month"
		# Pin ONE company + clear stale account links so the sweep stays internally
		# consistent regardless of which fixture company the runner left as the
		# ambient default (see test_sweep.setUp for the full rationale).
		s.company = company
		for row in s.accounts:
			row.account_link = None
			row.cost_center = None
		s.save(ignore_permissions=True)
		accounts.setup_pf_accounts(company)

	def _income(self, fee):
		frappe.get_doc({"doctype": "Membership", "tariff": fee, "fee_collected": fee}).insert(
			ignore_permissions=True
		)

	# ---- pure logic ------------------------------------------------------ #
	def test_parse_allocation_days(self):
		self.assertEqual(schedule.parse_allocation_days("10, 25"), [10, 25])
		self.assertEqual(schedule.parse_allocation_days("25,10,10,5"), [5, 10, 25])
		self.assertEqual(schedule.parse_allocation_days("1 15 28"), [1, 15, 28])
		# all invalid / out of range -> default
		self.assertEqual(schedule.parse_allocation_days("abc, 40, 0, -3"), [10, 25])
		self.assertEqual(schedule.parse_allocation_days(""), [10, 25])

	def test_month_end_clamp(self):
		# Day 31 clamps to the last day; Feb 2026 = 28 days, Apr = 30.
		self.assertTrue(schedule.is_allocation_day("2026-02-28", [31]))
		self.assertFalse(schedule.is_allocation_day("2026-02-27", [31]))
		self.assertTrue(schedule.is_allocation_day("2026-04-30", [31]))

	def test_next_sweep_date(self):
		self.assertEqual(str(schedule.next_sweep_date("2026-06-21", [10, 25])), "2026-06-25")
		self.assertEqual(str(schedule.next_sweep_date("2026-06-26", [10, 25])), "2026-07-10")
		# today itself counts as the next allocation day
		self.assertEqual(str(schedule.next_sweep_date("2026-06-10", [10, 25])), "2026-06-10")

	# ---- scheduler job --------------------------------------------------- #
	def test_no_create_off_allocation_day(self):
		# allocation_days are 10/25; running on a non-allocation day does nothing
		s = frappe.get_single("Profit First Settings")
		other = 11 if getdate(today()).day != 11 else 12
		s.allocation_days = str(other)
		s.save(ignore_permissions=True)
		self.assertIsNone(schedule.create_scheduled_sweeps())
		self.assertEqual(frappe.db.count("PF Sweep"), 0)

	def test_no_create_when_toggle_off(self):
		s = frappe.get_single("Profit First Settings")
		s.allocation_days = str(getdate(today()).day)  # make today a sweep day
		s.sweep_auto_create = 0
		s.save(ignore_permissions=True)
		self.assertIsNone(schedule.create_scheduled_sweeps())
		self.assertEqual(frappe.db.count("PF Sweep"), 0)

	def test_auto_create_idempotent_on_allocation_day(self):
		self._income(100000)
		s = frappe.get_single("Profit First Settings")
		s.allocation_days = str(getdate(today()).day)
		s.save(ignore_permissions=True)

		name = schedule.create_scheduled_sweeps()
		self.assertTrue(name)
		self.assertEqual(frappe.db.count("PF Sweep"), 1)
		# a draft only — nothing posted
		self.assertEqual(frappe.db.get_value("PF Sweep", name, "docstatus"), 0)
		# second run the same day creates no duplicate
		self.assertIsNone(schedule.create_scheduled_sweeps())
		self.assertEqual(frappe.db.count("PF Sweep"), 1)

	# ---- dashboard ------------------------------------------------------- #
	def test_dashboard_basics(self):
		d = dashboard.get_pf_dashboard()
		self.assertTrue(d["enabled"])
		self.assertTrue(d["accounts_ready"])
		self.assertEqual(len(d["reserves"]), 4)
		self.assertIsNotNone(d["next_sweep_date"])

	def test_dashboard_reserve_balance_after_post(self):
		self._income(100000)
		sweep = frappe.get_doc(
			{"doctype": "PF Sweep", "sweep_date": today(), "assessment_window": "This Month"}
		).insert(ignore_permissions=True)
		sweep.submit()

		d = dashboard.get_pf_dashboard()
		balances = {r["role"]: r["balance"] for r in d["reserves"]}
		self.assertGreater(balances["Tax"], 0)  # tax reserve funded by the sweep
		self.assertGreater(balances["Operating Expenses"], 0)
		self.assertIsNotNone(d["last_sweep"])

	def test_dashboard_lists_pending_draft(self):
		self._income(100000)
		s = frappe.get_single("Profit First Settings")
		s.allocation_days = str(getdate(today()).day)
		s.save(ignore_permissions=True)
		schedule.create_scheduled_sweeps()
		d = dashboard.get_pf_dashboard()
		self.assertEqual(len(d["pending_sweeps"]), 1)
