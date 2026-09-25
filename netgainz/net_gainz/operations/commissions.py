# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Coach commissions — computing what each coach is owed for a period (Stage 6).

Each Coach carries a commission_type and commission_amount. This module turns
those settings, plus the gym's data for a period, into a list of commission
lines. The PER-MEMBER and PERCENTAGE bases are owner-configurable (Gym Settings
.commission_percentage_basis), per the agreed design:

- Fixed       -> a flat amount, regardless of members or revenue.
- Per Member  -> amount x number of ACTIVE members assigned to the coach.
- Percentage  -> amount% of a revenue base, where the base is EITHER the coach's
                 own assigned members' collected fees OR the whole gym's collected
                 revenue, for the period (cash basis, scoped by paid_date).

The arithmetic that turns a base into a commission is a pure function
(``commission_for``) with no frappe dependency, so it is unit-testable directly.
Computing a run never moves money: posting to the ledger is a separate, gated
owner action on the Coach Commission Run.
"""

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.accounting import branch as branch_mod
from netgainz.net_gainz.profit_first.calc import round_half_away, to_paise, to_rupees

DEFAULT_PERCENTAGE_BASIS = "Assigned Member Revenue"
COMMISSION_TYPES = ("Fixed", "Per Member", "Percentage")


def commission_for(commission_type: str, amount: float, member_count: int, revenue: float) -> float:
	"""Pure commission arithmetic for one coach. Returns rupees (2 dp).

	``amount`` is a rupee figure for Fixed / Per Member and a percent for
	Percentage. ``revenue`` is the already-resolved Percentage base. All money is
	quantised in integer paise, half-away-from-zero (the app's one rounding rule),
	so the result is exact and independent of System Settings.rounding_method.
	"""
	if commission_type == "Fixed":
		return to_rupees(to_paise(amount))
	if commission_type == "Per Member":
		return to_rupees(to_paise(amount) * (member_count or 0))
	if commission_type == "Percentage":
		base_paise = to_paise(revenue)
		return to_rupees(round_half_away(base_paise * flt(amount) / 100.0))
	return 0.0


def _period(period_start=None, period_end=None):
	"""Resolve the commission window, defaulting to the current calendar month."""
	if period_start and period_end:
		return getdate(period_start), getdate(period_end)
	now = getdate(today())
	return get_first_day(now), get_last_day(now)


def _collected_between(start, end, members=None) -> float:
	"""Member fees collected in [start, end] (cash basis), optionally restricted to
	a set of members. Returns rupees.

	WP-11: the shared billing read — ex-GST Payment-Entry cash against
	subscription-generated invoices, the same single source Profit First uses, so
	the two can never disagree. The per-member scope becomes a Payment Entry party
	filter on those members' Customers."""
	if members is not None and not members:
		return 0.0
	return to_rupees(billing.membership_collected_paise(start, end, members))


def _money(value) -> str:
	return f"Rs.{flt(value, 2):,.2f}"


def _pct(value) -> str:
	return f"{flt(value, 2):g}%"


def compute_commissions(period_start=None, period_end=None) -> dict:
	"""Compute commission lines for every eligible coach for the period.

	Returns {period_start, period_end, percentage_basis, total, lines}. Only
	coaches that are Active, carry a real commission_type, and earn a positive
	commission are included.
	"""
	start, end = _period(period_start, period_end)
	basis = (
		frappe.db.get_single_value("Business Settings", "commission_percentage_basis")
		or DEFAULT_PERCENTAGE_BASIS
	)

	gym_revenue = None  # resolved lazily, once, only if a Percentage/all-gym coach needs it

	coaches = frappe.get_all(
		"Instructor",
		filters={"status": "Active", "commission_type": ["in", COMMISSION_TYPES]},
		fields=["name", "coach_name", "commission_type", "commission_amount"],
		limit_page_length=0,
	)

	lines = []
	for c in coaches:
		amount = flt(c.commission_amount)
		if amount <= 0:
			continue

		member_count = 0
		revenue = 0.0

		if c.commission_type == "Per Member":
			member_count = frappe.db.count("Member", {"coach": c.name, "status": "Active"})
			basis_label = f"{member_count} active member(s) x {_money(amount)}"
		elif c.commission_type == "Percentage":
			if basis == "All Gym Revenue":
				if gym_revenue is None:
					gym_revenue = _collected_between(start, end)
				revenue = gym_revenue
				basis_label = f"{_pct(amount)} of {_money(revenue)} gym revenue"
			else:
				members = frappe.get_all("Member", filters={"coach": c.name}, pluck="name")
				revenue = _collected_between(start, end, members)
				basis_label = f"{_pct(amount)} of {_money(revenue)} assigned-member revenue"
		else:  # Fixed
			basis_label = f"Fixed {_money(amount)}"

		commission = commission_for(c.commission_type, amount, member_count, revenue)
		if commission <= 0:
			continue

		lines.append(
			{
				"coach": c.name,
				"commission_type": c.commission_type,
				"member_count": member_count,
				"base_amount": to_rupees(to_paise(revenue)),
				"rate": amount,
				"basis_label": basis_label,
				"commission_amount": commission,
			}
		)

	total = to_rupees(sum(to_paise(line["commission_amount"]) for line in lines))
	return {
		"period_start": str(start),
		"period_end": str(end),
		"percentage_basis": basis,
		"total": total,
		"lines": lines,
	}


@frappe.whitelist()
def preview_commissions(period_start=None, period_end=None) -> dict:
	"""Read-only preview of commission lines for a period — persists nothing."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	branch_mod.require_all_branches("The commission preview")
	return compute_commissions(period_start, period_end)


# ── ledger account setup (owner-triggered; touches the books) ───────────────
def setup_commission_accounts(company: str | None = None) -> dict:
	"""Create + map the two coach-commission ledger accounts. Idempotent.

	- "Coach Commission Expense" — an Expense (P&L) account, debited on posting.
	- "Coach Commissions Payable" — a Liability account, credited on posting
	  (what the gym owes its coaches until paid out).

	Creating accounts touches the books, so this is an explicit owner action,
	never run from a scheduler — mirroring Profit First account setup.
	"""
	from netgainz.net_gainz.profit_first import accounts as pf_accounts

	company = company or pf_accounts.default_company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	expense_parent = pf_accounts._find_group(company, "Expenses", "Expense")
	liability_parent = pf_accounts._find_group(company, "Current Liabilities", "Liability")

	expense = pf_accounts._ensure_account("Coach Commission Expense", expense_parent, company)
	payable = pf_accounts._ensure_account("Coach Commissions Payable", liability_parent, company)

	settings = frappe.get_single("Business Settings")
	settings.commission_expense_account = expense
	settings.commission_payable_account = payable
	settings.save(ignore_permissions=True)

	return {"company": company, "expense_account": expense, "payable_account": payable}


@frappe.whitelist()
def setup_coach_commission_accounts(company: str | None = None) -> dict:
	"""Whitelisted entry point for the owner to provision commission accounts."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return setup_commission_accounts(company)


@frappe.whitelist()
def get_coach_report(start=None, end=None, branch=None) -> dict:
	"""Stage 11.2: per coach for a period — active members assigned, classes run,
	class bookings, attendance %, and commission (the SAME compute_commissions the
	Commissions page uses). Members, classes and bookings follow the branch;
	commission is whole-gym, so a branch-limited login does not get it."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	branches = branch_mod.scope(branch)
	start = getdate(start) if start else get_first_day(today())
	end = getdate(end) if end else get_last_day(start)
	period = [f"{start} 00:00:00", f"{end} 23:59:59"]

	members = dict(
		frappe.get_all(
			"Member",
			filters=branch_mod.filter_by_branch({"status": "Active", "coach": ["is", "set"]}, branches),
			fields=["coach", "count(*)"],
			group_by="coach",
			as_list=True,
		)
	)
	classes = dict(
		frappe.get_all(
			"Session",
			filters=branch_mod.filter_by_branch(
				{"coach": ["is", "set"], "status": ["!=", "Cancelled"], "start_time": ["between", period]},
				branches,
			),
			fields=["coach", "count(*)"],
			group_by="coach",
			as_list=True,
		)
	)
	visits: dict[str, dict] = {}
	for coach, status, n in frappe.get_all(
		"Session Booking",
		filters=branch_mod.filter_by_branch(
			{"coach": ["is", "set"], "status": ["!=", "Cancelled"], "start_time": ["between", period]},
			branches,
		),
		fields=["coach", "status", "count(*)"],
		group_by="coach, status",
		as_list=True,
	):
		visits.setdefault(coach, {})[status] = n

	commission = None
	if not branch_mod.is_branch_limited():
		commission = {l["coach"]: l["commission_amount"] for l in compute_commissions(start, end)["lines"]}

	rows = []
	for coach in frappe.get_all(
		"Instructor", filters={"status": "Active"}, pluck="name", order_by="name asc"
	):
		v = visits.get(coach, {})
		booked = sum(v.values())
		rows.append(
			{
				"coach": coach,
				"members": members.get(coach, 0),
				"classes": classes.get(coach, 0),
				"bookings": booked,
				"attended": v.get("Attended", 0),
				# Of bookings with a known outcome: bookings still "Booked" were never marked.
				"attendance_pct": (
					round(100 * v.get("Attended", 0) / (v.get("Attended", 0) + v.get("No Show", 0)), 1)
					if v.get("Attended", 0) + v.get("No Show", 0)
					else None
				),
				"commission": commission.get(coach, 0.0) if commission is not None else None,
			}
		)
	return {"start": str(start), "end": str(end), "rows": rows, "commission_shown": commission is not None}
