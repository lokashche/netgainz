# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-2: map a Membership Plan's ``duration_in_days`` to a native ERPNext
Subscription Plan ``(billing_interval, billing_interval_count)``.

ERPNext's native Subscription bills only on **Day / Week / Month / Year** period
boundaries (``Subscription Plan.billing_interval``), never by an arbitrary day
count. So a plan's ``duration_in_days`` has to be expressed as an interval and a
count.

We pick the **largest natural interval that divides the duration exactly**,
trying Year (365 d) -> Month (30 d) -> Week (7 d) -> Day (1 d). A candidate
interval is **rejected** when the duration is not an exact multiple of its day
length -- e.g. 90 days is not ``90/365`` of a Year, so Year is rejected and the
plan becomes Month x 3. Day has length 1 and divides every positive integer, so
every positive duration maps; a non-positive duration has no representable
interval and raises :class:`ValueError`.

These are *nominal* calendar lengths: ERPNext treats Month / Year as the
**calendar** month / year at period boundaries (a "Month x 1" plan started on the
15th next bills on the 15th), so 30 / 365 are conventional divisors for picking
the interval, not literal day arithmetic. This deliberately matches gym-industry
monthly / quarterly / annual billing.

Pure module -- imports nothing from frappe, so it is unit-testable standalone.
"""

from __future__ import annotations

# (interval label, nominal days), ordered LARGEST first so the first exact
# divisor wins: 90 -> Month x 3 (Year rejected), 365 -> Year x 1, 14 -> Week x 2.
_INTERVALS: tuple[tuple[str, int], ...] = (
	("Year", 365),
	("Month", 30),
	("Week", 7),
	("Day", 1),
)


def duration_to_billing_interval(duration_in_days: int) -> tuple[str, int]:
	"""Return ``(billing_interval, billing_interval_count)`` for a plan duration.

	``billing_interval`` is one of ``"Day" | "Week" | "Month" | "Year"`` (a valid
	``Subscription Plan.billing_interval`` option) and ``billing_interval_count``
	is a positive int. Raises :class:`ValueError` for a non-positive duration,
	which has no representable billing interval.
	"""
	days = int(duration_in_days)
	if days < 1:
		raise ValueError(
			f"duration_in_days must be a positive integer to map to a billing "
			f"interval; got {duration_in_days!r}."
		)
	for interval, length in _INTERVALS:
		if days % length == 0:
			return interval, days // length
	# Unreachable: Day has length 1 and divides every positive integer.
	raise ValueError(f"No billing interval divides {days} days evenly.")
