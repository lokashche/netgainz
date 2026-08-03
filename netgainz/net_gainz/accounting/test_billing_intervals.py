# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Unit tests for the duration_in_days -> (billing_interval, count) map.

Pure logic, no site/frappe needed -- plain unittest.TestCase.
"""

import unittest
from datetime import date

from netgainz.net_gainz.accounting.billing_intervals import (
	duration_to_billing_interval,
	latest_cycle_start,
)


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


class TestLatestCycleStart(unittest.TestCase):
	"""WP-10.0: the billing cycle anchors on the member's JOINING day, and never
	back-bills elapsed periods."""

	def test_new_joiner_starts_today(self):
		d = date(2026, 8, 3)
		self.assertEqual(latest_cycle_start(d, "Month", 1, d), d)

	def test_future_joiner_starts_on_joining(self):
		self.assertEqual(
			latest_cycle_start(date(2026, 9, 1), "Month", 1, date(2026, 8, 3)),
			date(2026, 9, 1),
		)

	def test_monthly_keeps_the_joining_day_of_month(self):
		# Joined the 15th -> every period starts on the 15th, not on today's date.
		self.assertEqual(
			latest_cycle_start(date(2026, 1, 15), "Month", 1, date(2026, 8, 3)),
			date(2026, 7, 15),
		)

	def test_quarterly_lands_on_a_quarter_boundary(self):
		# 15 Jan -> 15 Apr -> 15 Jul (15 Oct is still in the future).
		self.assertEqual(
			latest_cycle_start(date(2026, 1, 15), "Month", 3, date(2026, 8, 3)),
			date(2026, 7, 15),
		)

	def test_half_yearly(self):
		self.assertEqual(
			latest_cycle_start(date(2026, 2, 10), "Month", 6, date(2026, 9, 1)),
			date(2026, 8, 10),
		)

	def test_yearly(self):
		self.assertEqual(
			latest_cycle_start(date(2024, 1, 15), "Year", 1, date(2026, 8, 3)),
			date(2026, 1, 15),
		)

	def test_month_end_joining_day_is_clamped(self):
		# Joined the 31st: February has no 31st, so the period start clamps.
		self.assertEqual(
			latest_cycle_start(date(2026, 1, 31), "Month", 1, date(2026, 2, 28)),
			date(2026, 2, 28),
		)

	def test_weekly_intervals(self):
		self.assertEqual(
			latest_cycle_start(date(2026, 1, 1), "Week", 2, date(2026, 8, 3)),
			date(2026, 7, 30),
		)

	def test_never_returns_a_future_period(self):
		"""The anchor is always on/before `on` — otherwise the first invoice would
		be raised for a period that has not started."""
		on = date(2026, 8, 3)
		for joining in (date(2020, 3, 31), date(2026, 1, 1), date(2026, 8, 2)):
			for interval, count in (("Month", 1), ("Month", 3), ("Year", 1), ("Week", 2)):
				self.assertLessEqual(latest_cycle_start(joining, interval, count, on), on)

	def test_unknown_interval_raises(self):
		with self.assertRaises(ValueError):
			latest_cycle_start(date(2026, 1, 1), "Fortnight", 1, date(2026, 8, 3))
