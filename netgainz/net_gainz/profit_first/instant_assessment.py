# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Profit First — Stage 5a Instant Assessment (READ-ONLY).

Fetches the gym's actual data and the PF config, then delegates all of the
cent-sensitive maths to ``calc.build_assessment``. This module does the frappe
I/O; ``calc`` does the arithmetic and has no frappe dependency so it can be
tested standalone.

Cash basis only (Stage 5a decision): income is recognised when collected, scoped
by Subscription.paid_date; expenses are scoped by Gym Expense.date. Moves no
money, posts no ledger entries.
"""

import frappe
from frappe.utils import add_months, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.profit_first import calc

EXPENSE_CATEGORY = "Expense Category"
DEFAULT_BUCKET = calc.OPEX


@frappe.whitelist()
def get_instant_assessment(window: str | None = None):
	"""Return the read-only Instant Assessment payload for the current gym.

	``window`` optionally overrides the configured Assessment Window
	("Trailing 12 Months" or "This Month").
	"""
	settings = frappe.get_single("Profit First Settings")
	if not settings.pf_enabled:
		return {"enabled": False}

	window = window or settings.assessment_window or "Trailing 12 Months"
	start, end, period_label = _period(window)

	topline_paise = _cash_topline_paise(start, end)
	excluded = _excluded_payments(start, end)
	has_field = frappe.get_meta(EXPENSE_CATEGORY).has_field("pf_bucket")
	buckets_paise, passthrough_breakdown = _expense_buckets_paise(start, end, has_field)
	tier_bands = _tier_bands(settings)

	result = calc.build_assessment(
		topline_paise=topline_paise,
		buckets_paise=buckets_paise,
		window=window,
		tier_bands=tier_bands,
		period_label=period_label,
		basis="Cash",
		rounding_sink=settings.rounding_sink or calc.OPEX,
		excluded_payments=excluded,
		has_pf_bucket_field=has_field,
	)
	result["enabled"] = True
	result["passthrough_breakdown"] = passthrough_breakdown
	return result


def get_target_allocation(window: str | None = None) -> dict:
	"""Compute the TAP target split for a sweep (5b), reusing the SAME cash-basis
	fetch + cent-exact largest-remainder split as the Instant Assessment so the
	two can never disagree. All amounts are integer paise.

	Returns: {real_revenue_paise, window, period_label, tier_code,
	allocations_paise: {role: paise} for the 4 allocation buckets, applicable}.
	"""
	settings = frappe.get_single("Profit First Settings")
	window = window or settings.assessment_window or "Trailing 12 Months"
	start, end, period_label = _period(window)

	topline = _cash_topline_paise(start, end)
	has_field = frappe.get_meta(EXPENSE_CATEGORY).has_field("pf_bucket")
	buckets, _ = _expense_buckets_paise(start, end, has_field)
	rr = topline - buckets[calc.PASS_THROUGH]

	result = {
		"real_revenue_paise": rr,
		"window": window,
		"period_label": period_label,
		"tier_code": None,
		"allocations_paise": {},
		"taps": {},
		"applicable": False,
	}

	tiers = _tier_bands(settings)
	if rr <= 0 or not tiers:
		return result

	annual = rr if window == "Trailing 12 Months" else rr * 12
	tier = calc.select_tier(annual / 100.0, tiers)
	if not tier:
		return result

	taps = calc.taps_from_tier(tier)
	alloc = calc.largest_remainder_allocate(
		rr,
		[(k, taps[k]) for k in calc.ALLOCATION_BUCKETS],
		priority=settings.rounding_sink or calc.OPEX,
	)
	result.update(
		{"tier_code": tier["tier_code"], "allocations_paise": alloc, "taps": taps, "applicable": True}
	)
	return result


# --------------------------------------------------------------------------- #
# period                                                                      #
# --------------------------------------------------------------------------- #
def _period(window: str):
	"""Return (start_date, end_date, label) for the cash-basis window.

	"This Month": the current calendar month.
	"Trailing 12 Months": the 12 full months ending with the last COMPLETED
	month (today's partial month is excluded so the figure is a stable annual
	number for tier selection).
	"""
	now = getdate(today())
	if window == "This Month":
		start = get_first_day(now)
		end = get_last_day(now)
		return start, end, start.strftime("%b %Y")

	end = get_last_day(add_months(now, -1))
	start = get_first_day(add_months(end, -11))
	return start, end, f"{start.strftime('%b %Y')} to {end.strftime('%b %Y')}"


# --------------------------------------------------------------------------- #
# income                                                                      #
# --------------------------------------------------------------------------- #
def _cash_topline_paise(start, end) -> int:
	# WP-4: collected cash now comes from Payment Entries on/after the billing
	# cut-over date and from legacy fee_collected before it (date-split inside
	# the shared helper). Re-pointed together with commissions._collected_between.
	return billing.membership_collected_paise(start, end)


def _excluded_payments(start, end) -> dict:
	"""Payments with money collected but no paid_date — unplaceable in time and
	therefore excluded from the cash total. Surfaced so the total is never
	silently short. (The v0_2 backfill patch + controller fix shrink this to
	zero going forward.)

	WP-4 leaves this on the legacy fee_collected read on purpose: it reports
	pre-cut-over dateless cash, and the new Payment-Entry path can never create a
	null-posting_date collection (PE.posting_date is mandatory — R3), so there is
	nothing new to surface here post-cut-over."""
	rows = frappe.get_all(
		"Membership",
		filters=[
			["fee_collected", ">", 0],
			["paid_date", "is", "not set"],
			["subscription", "is", "not set"],
		],
		fields=["fee_collected"],
		limit_page_length=0,
	)
	return {
		"count": len(rows),
		"amount_paise": sum(calc.to_paise(r.fee_collected) for r in rows),
	}


# --------------------------------------------------------------------------- #
# expenses -> PF buckets                                                       #
# --------------------------------------------------------------------------- #
def _expense_buckets_paise(start, end, has_field: bool):
	"""Aggregate period expenses into PF buckets (in paise), resolving each
	Gym Expense to its category's pf_bucket. Returns (buckets, breakdown)."""
	buckets = {b: 0 for b in calc.EXPENSE_BUCKETS}

	category_bucket = {}
	if has_field:
		for cat in frappe.get_all(EXPENSE_CATEGORY, fields=["name", "pf_bucket"]):
			category_bucket[cat.name] = cat.pf_bucket or DEFAULT_BUCKET

	rows = frappe.get_all(
		"Expense",
		filters=[["date", "between", [start, end]]],
		fields=["amount", "category"],
		limit_page_length=0,
	)

	passthrough_by_cat: dict[str, int] = {}
	for r in rows:
		bucket = category_bucket.get(r.category, DEFAULT_BUCKET) if has_field else DEFAULT_BUCKET
		paise = calc.to_paise(r.amount)
		buckets[bucket] = buckets.get(bucket, 0) + paise
		if bucket == calc.PASS_THROUGH:
			passthrough_by_cat[r.category] = passthrough_by_cat.get(r.category, 0) + paise

	breakdown = [
		{"category": cat, "amount": calc.to_rupees(amt)}
		for cat, amt in sorted(passthrough_by_cat.items(), key=lambda kv: -kv[1])
	]
	return buckets, breakdown


# --------------------------------------------------------------------------- #
# config                                                                      #
# --------------------------------------------------------------------------- #
def _tier_bands(settings) -> list:
	return [
		{
			"tier_code": row.tier_code,
			"rr_lower": row.rr_lower or 0,
			"tap_profit": row.tap_profit or 0,
			"tap_owners_pay": row.tap_owners_pay or 0,
			"tap_tax": row.tap_tax or 0,
			"tap_opex": row.tap_opex or 0,
		}
		for row in settings.tiers
	]
