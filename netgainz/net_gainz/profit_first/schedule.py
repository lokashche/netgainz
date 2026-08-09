# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Profit First — sweep scheduling (Stage 5c).

Allocation days are owner-configurable (Profit First suggests the 10th & 25th,
but any days are allowed). A daily scheduler auto-creates a DRAFT sweep proposal
on each allocation day; posting still requires manual approval, so no money ever
moves on a schedule.

A configured day past the month's length (e.g. the 31st in a 30-day month) falls
on the last day of that month, so a schedule is never silently skipped.
"""

import frappe
from frappe.utils import add_to_date, get_last_day, getdate, today

DEFAULT_DAYS = [10, 25]


def parse_allocation_days(raw) -> list:
	"""Parse a comma/space-separated list of month-days into a sorted, unique list
	of ints in 1..31. Empty or all-invalid input falls back to the 10 & 25 default."""
	if not raw:
		return list(DEFAULT_DAYS)
	days = set()
	for part in str(raw).replace(";", ",").replace(" ", ",").split(","):
		part = part.strip()
		if not part:
			continue
		try:
			d = int(part)
		except ValueError:
			continue
		if 1 <= d <= 31:
			days.add(d)
	return sorted(days) if days else list(DEFAULT_DAYS)


def _effective_days_in_month(days, ref_date) -> set:
	"""Map configured days onto actual days in ref_date's month, clamping any day
	past the month length to the last day."""
	last = get_last_day(ref_date).day
	return {min(d, last) for d in days}


def is_allocation_day(ref_date, days) -> bool:
	ref_date = getdate(ref_date)
	return ref_date.day in _effective_days_in_month(days, ref_date)


def next_sweep_date(from_date=None, days=None):
	"""The next allocation date on or after ``from_date`` (default today)."""
	ref = getdate(from_date or today())
	if days is None:
		days = parse_allocation_days(frappe.db.get_single_value("Profit First Settings", "allocation_days"))
	if not days:
		return None
	cur = ref
	for _ in range(70):  # always finds one within two months
		if cur.day in _effective_days_in_month(days, cur):
			return cur
		cur = getdate(add_to_date(cur, days=1))
	return None


def create_scheduled_sweeps():
	"""Daily scheduler hook: on an allocation day, auto-create a draft sweep
	proposal. Idempotent (one per day), opt-out via sweep_auto_create, and only
	when Profit First is enabled. Never posts — approval stays manual."""
	if not frappe.db.get_single_value("Profit First Settings", "pf_enabled"):
		return None
	if not frappe.db.get_single_value("Profit First Settings", "sweep_auto_create"):
		return None

	days = parse_allocation_days(frappe.db.get_single_value("Profit First Settings", "allocation_days"))
	td = getdate(today())
	if not is_allocation_day(td, days):
		return None
	if frappe.db.exists("PF Sweep", {"sweep_date": td}):
		return None  # already created/posted for today

	from netgainz.net_gainz.doctype.pf_sweep.pf_sweep import create_sweep

	name = create_sweep(sweep_date=str(td))
	frappe.logger("profit_first").info(f"Auto-created draft sweep {name} for {td}")
	return name


@frappe.whitelist()
def update_pf_schedule(allocation_days=None, sweep_auto_create=None) -> dict:
	"""Owner-facing schedule editor: set the allocation days and auto-create toggle."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	settings = frappe.get_single("Profit First Settings")
	if allocation_days is not None:
		settings.allocation_days = ", ".join(str(d) for d in parse_allocation_days(allocation_days))
	if sweep_auto_create is not None:
		settings.sweep_auto_create = 1 if str(sweep_auto_create).lower() in ("1", "true", "on", "yes") else 0
	settings.save(ignore_permissions=True)
	return {
		"allocation_days": settings.allocation_days,
		"sweep_auto_create": settings.sweep_auto_create,
		"next_sweep_date": str(next_sweep_date()),
	}
