# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Unit tests for the duration_in_days -> (billing_interval, count) map.

Pure logic, no site/frappe needed -- plain unittest.TestCase.
"""

import unittest

from netgainz.net_gainz.accounting.billing_intervals import duration_to_billing_interval


class TestBillingIntervals(unittest.TestCase):
	def test_largest_natural_interval_wins(self):
		cases = {
			1: ("Day", 1),
			6: ("Day", 6),
			7: ("Week", 1),
			14: ("Week", 2),
			21: ("Week", 3),
			30: ("Month", 1),
			60: ("Month", 2),
			180: ("Month", 6),
			360: ("Month", 12),
			365: ("Year", 1),
			730: ("Year", 2),
		}
		for days, expected in cases.items():
			with self.subTest(days=days):
				self.assertEqual(duration_to_billing_interval(days), expected)

	def test_quarterly_is_three_months_not_a_fraction_of_a_year(self):
		# The documented reject-non-divisible example: 90 days is not 90/365 of a
		# Year, so Year is rejected and the plan becomes Month x 3.
		self.assertEqual(duration_to_billing_interval(90), ("Month", 3))

	def test_non_divisible_durations_fall_back_to_days(self):
		# No clean Week/Month/Year multiple -> Day x N (Day divides everything).
		self.assertEqual(duration_to_billing_interval(31), ("Day", 31))
		self.assertEqual(duration_to_billing_interval(45), ("Day", 45))

	def test_week_preferred_over_day_but_below_month(self):
		# 28 is a multiple of both 7 and ... not 30; Week wins over Day.
		self.assertEqual(duration_to_billing_interval(28), ("Week", 4))

	def test_non_positive_duration_raises(self):
		for bad in (0, -1, -30):
			with self.subTest(bad=bad):
				with self.assertRaises(ValueError):
					duration_to_billing_interval(bad)

	def test_string_digits_are_coerced(self):
		# Int-like input (e.g. a stored field) is coerced via int().
		self.assertEqual(duration_to_billing_interval("30"), ("Month", 1))
