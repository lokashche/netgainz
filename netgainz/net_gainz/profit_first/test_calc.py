# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Standalone unit tests for the pure Profit First maths (no frappe needed).

Run directly:   python net_gainz/profit_first/test_calc.py
or via unittest: python -m unittest netgainz.net_gainz.profit_first.test_calc
"""

import unittest

try:
	from netgainz.net_gainz.profit_first import calc
except ImportError:  # allow running the file directly from its own folder
	import os
	import sys

	sys.path.insert(0, os.path.dirname(__file__))
	import calc  # type: ignore


# Canonical ₹ tier table (placeholder bands, lower-inclusive).
TIERS = [
	{"tier_code": "A", "rr_lower": 0, "tap_profit": 5, "tap_owners_pay": 50, "tap_tax": 15, "tap_opex": 30},
	{
		"tier_code": "B",
		"rr_lower": 250000,
		"tap_profit": 10,
		"tap_owners_pay": 35,
		"tap_tax": 15,
		"tap_opex": 40,
	},
	{
		"tier_code": "C",
		"rr_lower": 500000,
		"tap_profit": 15,
		"tap_owners_pay": 20,
		"tap_tax": 15,
		"tap_opex": 50,
	},
	{
		"tier_code": "D",
		"rr_lower": 1000000,
		"tap_profit": 10,
		"tap_owners_pay": 10,
		"tap_tax": 15,
		"tap_opex": 65,
	},
	{
		"tier_code": "E",
		"rr_lower": 5000000,
		"tap_profit": 15,
		"tap_owners_pay": 5,
		"tap_tax": 15,
		"tap_opex": 65,
	},
	{
		"tier_code": "F",
		"rr_lower": 10000000,
		"tap_profit": 20,
		"tap_owners_pay": 0,
		"tap_tax": 15,
		"tap_opex": 65,
	},
]


class TestPaise(unittest.TestCase):
	def test_round_trip(self):
		self.assertEqual(calc.to_paise(1234.56), 123456)
		self.assertEqual(calc.to_paise(0), 0)
		self.assertEqual(calc.to_paise(None), 0)
		self.assertEqual(calc.to_rupees(123456), 1234.56)

	def test_half_away_from_zero(self):
		# 0.125 -> 12.5 paise -> 13 (half up), matches en-IN toLocaleString
		self.assertEqual(calc.to_paise(0.125), 13)
		self.assertEqual(calc.to_paise(-0.125), -13)
		# Float dust must not drop a paise.
		self.assertEqual(calc.to_paise(100000.1 - 0.3 + 0.2), 10000000)


class TestLargestRemainder(unittest.TestCase):
	def test_sums_exactly_simple(self):
		out = calc.largest_remainder_allocate(
			35000000, [("Profit", 5), ("Owner's Pay", 50), ("Tax", 15), ("Operating Expenses", 30)]
		)
		self.assertEqual(sum(out.values()), 35000000)

	def test_never_loses_a_paise_over_many_amounts(self):
		pairs = [("Profit", 5), ("Owner's Pay", 50), ("Tax", 15), ("Operating Expenses", 30)]
		# Stress every paise value across a wide range incl. nasty remainders.
		for total in [*range(5000), 99999999, 100000001, 333, 12345679]:
			out = calc.largest_remainder_allocate(total, pairs)
			self.assertEqual(sum(out.values()), total, f"lost paise at {total}")
			self.assertTrue(all(v >= 0 for v in out.values()))

	def test_zero_percent_bucket_gets_nothing_when_clean(self):
		# Tier F: Owner's Pay 0%. With a clean total it should allocate 0.
		out = calc.largest_remainder_allocate(
			20000000, [("Profit", 20), ("Owner's Pay", 0), ("Tax", 15), ("Operating Expenses", 65)]
		)
		self.assertEqual(out["Owner's Pay"], 0)
		self.assertEqual(sum(out.values()), 20000000)

	def test_priority_wins_ties(self):
		# 100 paise split 4 ways at 25% each -> exact, no remainder; force a tie case.
		# 102 paise at 25/25/25/25 -> floors 25 each (100), remainder 2 paise, all fracs equal (.5).
		out = calc.largest_remainder_allocate(
			102,
			[("Profit", 25), ("Owner's Pay", 25), ("Tax", 25), ("Operating Expenses", 25)],
			priority="Operating Expenses",
		)
		self.assertEqual(sum(out.values()), 102)
		# Operating Expenses (priority) must receive one of the two leftover paise.
		self.assertEqual(out["Operating Expenses"], 26)

	def test_negative_total_rejected(self):
		with self.assertRaises(ValueError):
			calc.largest_remainder_allocate(-100, [("Profit", 100)])


class TestSelectTier(unittest.TestCase):
	def test_lower_inclusive_upper_exclusive(self):
		self.assertEqual(calc.select_tier(0, TIERS)["tier_code"], "A")
		self.assertEqual(calc.select_tier(249999.99, TIERS)["tier_code"], "A")
		self.assertEqual(calc.select_tier(250000, TIERS)["tier_code"], "B")  # edge -> higher tier
		self.assertEqual(calc.select_tier(500000, TIERS)["tier_code"], "C")
		self.assertEqual(calc.select_tier(9999999.99, TIERS)["tier_code"], "E")
		self.assertEqual(calc.select_tier(10000000, TIERS)["tier_code"], "F")
		self.assertEqual(calc.select_tier(99999999, TIERS)["tier_code"], "F")

	def test_empty_table(self):
		self.assertIsNone(calc.select_tier(100000, []))


class TestBuildAssessment(unittest.TestCase):
	def _assess(self, topline, buckets, window="This Month"):
		return calc.build_assessment(
			topline_paise=calc.to_paise(topline),
			buckets_paise={k: calc.to_paise(v) for k, v in buckets.items()},
			window=window,
			tier_bands=TIERS,
			period_label="Test period",
		)

	def test_real_revenue_excludes_passthrough(self):
		out = self._assess(400000.50, {"Pass-Through": 50000.50, "Operating Expenses": 95000})
		self.assertEqual(out["real_revenue"], 350000.00)
		self.assertEqual(out["passthrough"], 50000.50)

	def test_cap_percents_sum_to_100(self):
		out = self._assess(350000, {"Owner's Pay": 180000, "Operating Expenses": 95000})
		caps = [r["cap_pct"] for r in out["rows"]]
		self.assertAlmostEqual(sum(caps), 100.00, places=2)

	def test_targets_sum_to_real_revenue(self):
		out = self._assess(350000, {"Operating Expenses": 95000})
		targets = [calc.to_paise(r["target"]) for r in out["rows"]]
		self.assertEqual(sum(targets), calc.to_paise(out["real_revenue"]))

	def test_gaps_do_not_sum_to_real_revenue(self):
		# Gaps legitimately sum to (RR - total recorded spend), NOT to RR.
		out = self._assess(100000, {"Operating Expenses": 40000})
		gaps = sum(calc.to_paise(r["gap"]) for r in out["rows"])
		self.assertNotEqual(gaps, calc.to_paise(out["real_revenue"]))

	def test_residual_is_profit_and_labelled_honestly(self):
		out = self._assess(350000, {"Owner's Pay": 180000, "Operating Expenses": 95000})
		profit_row = out["rows"][0]
		self.assertEqual(profit_row["bucket"], "Profit")
		self.assertEqual(profit_row["actual"], 75000.00)  # 350000 - 180000 - 95000 - 0(tax)
		self.assertIn("residual", profit_row["label"].lower())

	def test_unrecorded_owner_pay_triggers_warning(self):
		out = self._assess(350000, {"Operating Expenses": 95000})  # no owner pay / tax
		self.assertTrue(any("overstates true Profit" in w for w in out["warnings"]))

	def test_rr_zero_not_applicable(self):
		out = self._assess(0, {})
		self.assertFalse(out["applicable"])
		self.assertEqual(out["real_revenue"], 0.0)
		self.assertIn("not applicable", out["notice"])

	def test_rr_negative_is_rendered_not_clamped(self):
		out = self._assess(10000, {"Pass-Through": 25000})
		self.assertEqual(out["real_revenue"], -15000.00)  # NOT clamped to 0
		self.assertFalse(out["applicable"])
		self.assertIn("negative", out["notice"])

	def test_negative_residual_unprofitable_gym(self):
		# Spends more than it makes: residual Profit goes negative, not clamped.
		out = self._assess(100000, {"Owner's Pay": 80000, "Operating Expenses": 60000})
		profit_row = out["rows"][0]
		self.assertEqual(profit_row["actual"], -40000.00)

	def test_trailing12_tier_not_provisional(self):
		out = self._assess(600000, {"Operating Expenses": 100000}, window="Trailing 12 Months")
		self.assertEqual(out["tier_code"], "C")  # 600000 annual -> Tier C
		self.assertFalse(out["tier_provisional"])

	def test_this_month_annualises_x12_and_flags_provisional(self):
		out = self._assess(50000, {"Operating Expenses": 10000}, window="This Month")
		# 50000/month * 12 = 600000 annual -> Tier C
		self.assertEqual(out["tier_code"], "C")
		self.assertTrue(out["tier_provisional"])

	def test_missing_pf_field_degrades_gracefully(self):
		out = calc.build_assessment(
			topline_paise=calc.to_paise(200000),
			buckets_paise={},
			window="This Month",
			tier_bands=TIERS,
			period_label="x",
			has_pf_bucket_field=False,
		)
		self.assertEqual(out["real_revenue"], 200000.00)
		self.assertTrue(any("not yet PF-classified" in w for w in out["warnings"]))

	def test_excluded_payments_surfaced(self):
		out = calc.build_assessment(
			topline_paise=calc.to_paise(200000),
			buckets_paise={"Operating Expenses": calc.to_paise(50000)},
			window="This Month",
			tier_bands=TIERS,
			period_label="x",
			excluded_payments={"count": 3, "amount_paise": calc.to_paise(12000)},
		)
		self.assertTrue(any("no Paid Date" in w for w in out["warnings"]))

	def test_zero_profit_no_phantom_cap(self):
		# RR exactly consumed by expenses -> Profit ₹0 must show CAP 0.00, not ±0.01.
		out = self._assess(3.00, {"Owner's Pay": 1.00, "Tax": 1.00, "Operating Expenses": 1.00})
		profit_row = out["rows"][0]
		self.assertEqual(profit_row["actual"], 0.0)
		self.assertEqual(profit_row["cap_pct"], 0.0)
		self.assertAlmostEqual(sum(r["cap_pct"] for r in out["rows"]), 100.00, places=2)


if __name__ == "__main__":
	unittest.main(verbosity=2)
