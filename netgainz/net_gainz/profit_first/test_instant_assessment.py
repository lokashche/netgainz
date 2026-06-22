# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""DB-backed integration tests for the Profit First Instant Assessment engine.

Run with: bench --site <site> run-tests --module \
  netgainz.net_gainz.profit_first.test_instant_assessment

These complement the pure-maths coverage in test_calc.py by exercising the
frappe data-fetch (cash top-line by paid_date, expense bucketing, exclusion of
paid_date-less payments). FrappeTestCase wraps each test in a transaction and
rolls back, so the slate-clearing deletes and Single edits below are temporary.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from netgainz.net_gainz.profit_first import calc
from netgainz.net_gainz.profit_first.instant_assessment import get_instant_assessment
from netgainz.net_gainz.profit_first.seed import seed_profit_first_defaults


class TestInstantAssessment(FrappeTestCase):
	def setUp(self):
		# Deterministic slate (rolled back after the test).
		frappe.db.delete("Subscription")
		frappe.db.delete("Gym Expense")

		seed_profit_first_defaults()
		settings = frappe.get_single("Profit First Settings")
		settings.pf_enabled = 1
		settings.assessment_window = "This Month"
		settings.save(ignore_permissions=True)

	# ---- helpers --------------------------------------------------------- #
	def _sub(self, fee, with_paid_date=True):
		doc = frappe.get_doc({"doctype": "Subscription", "tariff": fee, "fee_collected": fee}).insert(
			ignore_permissions=True
		)
		if not with_paid_date:
			# Simulate legacy data: money collected but no paid_date.
			frappe.db.set_value("Subscription", doc.name, "paid_date", None, update_modified=False)
		return doc

	def _category(self, name, bucket):
		if not frappe.db.exists("Expense Category", name):
			frappe.get_doc(
				{"doctype": "Expense Category", "category_name": name, "pf_bucket": bucket}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Expense Category", name, "pf_bucket", bucket)
		return name

	def _expense(self, category, amount):
		frappe.get_doc(
			{"doctype": "Gym Expense", "date": today(), "category": category, "amount": amount}
		).insert(ignore_permissions=True)

	# ---- tests ----------------------------------------------------------- #
	def test_controller_stamps_paid_date(self):
		doc = self._sub(1000)
		self.assertEqual(str(doc.paid_date), today())

	def test_real_revenue_and_buckets(self):
		self._sub(200000)
		self._sub(150000)
		self._sub(50000, with_paid_date=False)  # excluded from cash total
		rent = self._category("ZZ Test Rent", "Operating Expenses")
		draw = self._category("ZZ Test Owner Draw", "Owner's Pay")
		supp = self._category("ZZ Test Supplements", "Pass-Through")
		self._expense(rent, 95000)
		self._expense(draw, 180000)
		self._expense(supp, 50000)

		out = get_instant_assessment()

		self.assertTrue(out["enabled"])
		self.assertTrue(out["applicable"])
		self.assertEqual(out["topline"], 350000.00)  # excludes the paid_date-less 50000
		self.assertEqual(out["passthrough"], 50000.00)
		self.assertEqual(out["real_revenue"], 300000.00)

		by_bucket = {r["bucket"]: r for r in out["rows"]}
		self.assertEqual(by_bucket["Owner's Pay"]["actual"], 180000.00)
		self.assertEqual(by_bucket["Operating Expenses"]["actual"], 95000.00)
		self.assertEqual(by_bucket["Tax"]["actual"], 0.00)
		# Profit is the residual: 300000 - 180000 - 0 - 95000 = 25000
		self.assertEqual(by_bucket["Profit"]["actual"], 25000.00)

	def test_invariants_hold(self):
		self._sub(500000)
		cat = self._category("ZZ Test OpEx", "Operating Expenses")
		self._expense(cat, 120000)

		out = get_instant_assessment()

		# CAP %s sum to 100; target ₹ sum to Real Revenue (no lost paise).
		self.assertAlmostEqual(sum(r["cap_pct"] for r in out["rows"]), 100.00, places=2)
		targets = sum(calc.to_paise(r["target"]) for r in out["rows"])
		self.assertEqual(targets, calc.to_paise(out["real_revenue"]))
		# Gaps must NOT sum to Real Revenue.
		gaps = sum(calc.to_paise(r["gap"]) for r in out["rows"])
		self.assertNotEqual(gaps, calc.to_paise(out["real_revenue"]))

	def test_excluded_payments_warning(self):
		self._sub(100000)
		self._sub(40000, with_paid_date=False)
		out = get_instant_assessment()
		self.assertTrue(any("no Paid Date" in w for w in out["warnings"]))

	def test_passthrough_breakdown_listed(self):
		self._sub(200000)
		supp = self._category("ZZ Test Supplements 2", "Pass-Through")
		self._expense(supp, 30000)
		out = get_instant_assessment()
		cats = [b["category"] for b in out["passthrough_breakdown"]]
		self.assertIn("ZZ Test Supplements 2", cats)

	def test_disabled_returns_flag(self):
		settings = frappe.get_single("Profit First Settings")
		settings.pf_enabled = 0
		settings.save(ignore_permissions=True)
		out = get_instant_assessment()
		self.assertEqual(out, {"enabled": False})
