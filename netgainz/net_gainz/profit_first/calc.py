# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Pure Profit First allocation maths for the Stage 5a Instant Assessment.

This module deliberately imports NOTHING from frappe so the cent-sensitive
core can be unit-tested standalone (`python test_calc.py`). All money is moved
around as integer **paise** internally; rupees are only produced at the edges.

Vocabulary
----------
- Real Revenue (RR) = Top-Line income - Pass-Through costs. The 100% base.
- CAP = Current Allocation %  (measured from actual data).
- TAP = Target Allocation %   (read from the gym's Real-Revenue tier).
- The four allocation buckets are Profit, Owner's Pay, Tax, Operating Expenses.
  Profit is the RESIDUAL of Real Revenue, never summed from expenses.

Read-only: this module computes and returns a payload. It moves no money.
"""

from __future__ import annotations

import math

# Canonical bucket order used everywhere the assessment is rendered.
PROFIT = "Profit"
OWNERS_PAY = "Owner's Pay"
TAX = "Tax"
OPEX = "Operating Expenses"
PASS_THROUGH = "Pass-Through"

# The four allocation buckets, in display order. Income is the 100% reference,
# not itself an allocation row, so it is not listed here.
ALLOCATION_BUCKETS = (PROFIT, OWNERS_PAY, TAX, OPEX)

# Expense buckets an Expense Category can be tagged with. Pass-Through is netted
# out of revenue and is NOT an allocation bucket.
EXPENSE_BUCKETS = (OWNERS_PAY, TAX, OPEX, PASS_THROUGH)


# --------------------------------------------------------------------------- #
# paise helpers                                                               #
# --------------------------------------------------------------------------- #
def to_paise(rupees) -> int:
	"""Quantise a rupee amount to integer paise. None -> 0.

	Uses round-half-away-from-zero so it agrees with en-IN toLocaleString on the
	frontend (which rounds half up for positive values) and is symmetric for
	negatives, rather than Python's bankers' round().
	"""
	if rupees is None:
		return 0
	value = float(rupees) * 100.0
	# round-half-away-from-zero
	return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


def to_rupees(paise: int) -> float:
	"""Integer paise -> rupee float with exactly 2 decimal places of meaning."""
	return round(paise / 100.0, 2)


# --------------------------------------------------------------------------- #
# largest-remainder (Hamilton) allocation                                     #
# --------------------------------------------------------------------------- #
def largest_remainder_allocate(total_paise: int, percents, priority=None) -> dict:
	"""Split ``total_paise`` across buckets by percentage with ZERO lost paise.

	``percents`` is an iterable of (bucket, pct) pairs whose pcts sum to 100.
	The rounded parts are guaranteed to sum EXACTLY to ``total_paise``.

	Only valid for ``total_paise >= 0`` (a negative Real Revenue has no
	meaningful allocation and the caller must not allocate against it).

	``priority`` is an optional bucket name that wins ties when handing out the
	leftover paise (e.g. the configured rounding sink); otherwise ties fall back
	to the bucket order in ``percents``.
	"""
	pairs = list(percents)
	if total_paise < 0:
		raise ValueError("largest_remainder_allocate requires total_paise >= 0")

	raw = {b: total_paise * (pct or 0) / 100.0 for b, pct in pairs}
	floors = {b: int(math.floor(raw[b])) for b, _ in pairs}
	remainder = total_paise - sum(floors.values())  # in [0, len(pairs)-1]

	order = [b for b, _ in pairs]
	priority_rank = {b: (0 if b == priority else 1) for b in order}
	# Hand out the leftover paise to the largest fractional remainders first;
	# break ties by priority bucket, then by declared order (both deterministic).
	ranked = sorted(
		order,
		key=lambda b: (-(raw[b] - floors[b]), priority_rank[b], order.index(b)),
	)
	result = dict(floors)
	for i in range(remainder):
		result[ranked[i]] += 1
	return result


# --------------------------------------------------------------------------- #
# tier lookup                                                                 #
# --------------------------------------------------------------------------- #
def select_tier(annual_rr_rupees: float, tier_bands):
	"""Pick the TAP tier row for an annual Real Revenue figure.

	Bands are lower-inclusive / upper-exclusive: a value exactly on a band edge
	belongs to the HIGHER tier. Implemented by storing ``rr_lower`` only and
	returning the last band whose ``rr_lower <= annual_rr``.

	``tier_bands`` is a list of dicts with keys: tier_code, rr_lower,
	tap_profit, tap_owners_pay, tap_tax, tap_opex. Returns the matching dict, or
	None if no band qualifies (empty table, or RR below the lowest lower-bound).
	"""
	if not tier_bands:
		return None
	ordered = sorted(tier_bands, key=lambda b: b["rr_lower"])
	match = None
	for band in ordered:
		if annual_rr_rupees >= band["rr_lower"]:
			match = band
		else:
			break
	return match


def taps_from_tier(tier) -> dict:
	"""Extract the {bucket: pct} TAP map from a tier band dict."""
	return {
		PROFIT: tier["tap_profit"],
		OWNERS_PAY: tier["tap_owners_pay"],
		TAX: tier["tap_tax"],
		OPEX: tier["tap_opex"],
	}


# --------------------------------------------------------------------------- #
# the assessment builder                                                      #
# --------------------------------------------------------------------------- #
def build_assessment(
	*,
	topline_paise: int,
	buckets_paise: dict,
	window: str,
	tier_bands,
	period_label: str,
	basis: str = "Cash",
	rounding_sink: str = OPEX,
	excluded_payments: dict | None = None,
	has_pf_bucket_field: bool = True,
):
	"""Compute the read-only Instant Assessment payload from pre-fetched totals.

	Parameters
	----------
	topline_paise : int
	    Cash top-line income for the period, in paise.
	buckets_paise : dict
	    Actual expense spend per bucket in paise, keyed by EXPENSE_BUCKETS.
	    Missing keys default to 0.
	window : str
	    "Trailing 12 Months" (annual RR == period RR) or "This Month"
	    (annualised x12, tier flagged provisional).
	tier_bands : list[dict]
	    The configurable TAP tier table.
	period_label : str
	    Human label for the period, e.g. "Jun 2025 - May 2026".
	excluded_payments : dict | None
	    {"count": int, "amount_paise": int} for cash payments dropped because
	    paid_date is NULL — surfaced so the cash total is never silently short.

	Returns a JSON-serialisable dict (rupee floats at the edges).
	"""
	b = {k: int(buckets_paise.get(k, 0) or 0) for k in EXPENSE_BUCKETS}
	passthrough_paise = b[PASS_THROUGH]
	rr_paise = topline_paise - passthrough_paise

	ownerspay_paise = b[OWNERS_PAY]
	tax_paise = b[TAX]
	opex_paise = b[OPEX]
	# Profit is the residual of Real Revenue — NOT summed from any expense.
	residual_paise = rr_paise - ownerspay_paise - tax_paise - opex_paise

	actual_paise = {
		PROFIT: residual_paise,
		OWNERS_PAY: ownerspay_paise,
		TAX: tax_paise,
		OPEX: opex_paise,
	}

	warnings: list[str] = []
	if not has_pf_bucket_field:
		warnings.append(
			"Expense categories are not yet PF-classified — pass-through costs "
			"are treated as ₹0, so Real Revenue equals Top-Line for now."
		)
	if excluded_payments and excluded_payments.get("count"):
		warnings.append(
			f"{excluded_payments['count']} payment(s) totalling "
			f"₹{to_rupees(excluded_payments.get('amount_paise', 0)):,.2f} were "
			"excluded from the cash total because they have no Paid Date."
		)

	applicable = rr_paise > 0 and bool(tier_bands)
	tier = select_tier(_annual_rr_rupees(rr_paise, window), tier_bands) if rr_paise > 0 else None
	if rr_paise > 0 and not tier_bands:
		warnings.append("No Profit First tier bands are configured — targets cannot be shown.")

	# ---- CAP %s (always sum to exactly 100.00 when RR > 0) ---------------- #
	caps = (
		_cap_percents(rr_paise, actual_paise, residual_paise)
		if rr_paise > 0
		else {k: None for k in ALLOCATION_BUCKETS}
	)

	# ---- TAP %s + target ₹ (largest-remainder, sums to RR) --------------- #
	if applicable and tier is not None:
		taps = taps_from_tier(tier)
		target_paise = largest_remainder_allocate(
			rr_paise, [(k, taps[k]) for k in ALLOCATION_BUCKETS], priority=rounding_sink
		)
	else:
		taps = {k: None for k in ALLOCATION_BUCKETS}
		target_paise = {k: None for k in ALLOCATION_BUCKETS}

	# Residual-overstates-profit banner (the honesty fix): if the owner records
	# no Owner's Pay or Tax expense, that cash silently inflates the Profit
	# residual. Warn whenever RR is positive and either bucket is empty.
	if rr_paise > 0 and (ownerspay_paise == 0 or tax_paise == 0):
		warnings.append(
			"No Owner's Pay and/or Tax spend is recorded, so the residual "
			"overstates true Profit. Treat the Profit row as an upper bound "
			"until you tag expense categories to Owner's Pay and Tax."
		)

	rows = []
	for bucket in ALLOCATION_BUCKETS:
		target = target_paise[bucket]
		gap_paise = (actual_paise[bucket] - target) if target is not None else None
		gap_pct = (
			round(caps[bucket] - taps[bucket], 2)
			if caps[bucket] is not None and taps[bucket] is not None
			else None
		)
		rows.append(
			{
				"bucket": bucket,
				"label": "Undistributed Cash (residual)" if bucket == PROFIT else bucket,
				"actual": to_rupees(actual_paise[bucket]),
				"cap_pct": caps[bucket],
				"tap_pct": taps[bucket],
				"target": to_rupees(target) if target is not None else None,
				"gap": to_rupees(gap_paise) if gap_paise is not None else None,
				"gap_pct": gap_pct,
			}
		)

	if rr_paise == 0:
		notice = "No Real Revenue in this period — the assessment is not applicable."
	elif rr_paise < 0:
		notice = (
			"Pass-through costs exceed top-line revenue this period, so Real "
			"Revenue is negative — the assessment is not applicable."
		)
	elif not tier_bands:
		notice = "Configure Profit First tier bands to see targets."
	else:
		notice = None

	return {
		"applicable": applicable,
		"basis": basis,
		"window": window,
		"period_label": period_label,
		"topline": to_rupees(topline_paise),
		"passthrough": to_rupees(passthrough_paise),
		"real_revenue": to_rupees(rr_paise),
		"tier_code": tier["tier_code"] if tier else None,
		"tier_provisional": window != "Trailing 12 Months",
		"rows": rows,
		"notice": notice,
		"warnings": warnings,
		"profit_is_residual": True,
	}


def _annual_rr_rupees(rr_paise: int, window: str) -> float:
	"""Annualise Real Revenue for tier selection. Trailing-12 is already annual;
	a single month is scaled x12 (and the tier is flagged provisional upstream)."""
	annual_paise = rr_paise if window == "Trailing 12 Months" else rr_paise * 12
	return annual_paise / 100.0


def _cap_percents(rr_paise: int, actual_paise: dict, residual_paise: int) -> dict:
	"""CAP %s that always sum to exactly 100.00.

	Owner's Pay / Tax / OpEx are rounded directly; the reconciliation delta is
	absorbed by the Profit cell (normal case). When Profit is exactly ₹0, the
	delta is moved to the largest expense bucket instead, so a true-zero Profit
	never shows a phantom ±0.01%.
	"""
	raw = {k: actual_paise[k] / rr_paise * 100.0 for k in ALLOCATION_BUCKETS}
	rounded = {k: round(raw[k], 2) for k in ALLOCATION_BUCKETS}

	if residual_paise == 0:
		reconcile = max((OWNERS_PAY, TAX, OPEX), key=lambda k: actual_paise[k])
		rounded[PROFIT] = 0.0
	else:
		reconcile = PROFIT

	others = [k for k in ALLOCATION_BUCKETS if k != reconcile]
	rounded[reconcile] = round(100.0 - sum(rounded[o] for o in others), 2)
	return rounded
