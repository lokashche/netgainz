# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""The dashboard's "Income this month" figure, read from the real books.

The owner-app used to sum ``Membership.fee_collected`` (cash) or ``Membership.tariff``
(accrual) itself. Both are deprecated display fields that WP-11 stopped writing, so
every payment recorded the Stage 7 way — a Payment Entry against the membership's
Sales Invoice — showed as ₹0 income while expenses still showed in full.

This reads the two figures from where the money actually lives:

* **collected** — cash received, via :func:`billing.membership_collected_paise`, the
  SAME read Profit First and commissions use: ex-GST, net of refunds, advances only
  once applied. The dashboard and the Profit First page can therefore never disagree.
* **billed** — ex-GST value of submitted membership invoices posted in the window,
  net of credit notes, in company currency.

``income`` is whichever one the gym's Cash/Accrual setting points at, so the owner-app
does no arithmetic of its own.
"""

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing, deferred
from netgainz.net_gainz.accounting import branch as branch_mod
from netgainz.net_gainz.profit_first import calc


def _period(start=None, end=None):
	"""An explicit range, else the current calendar month."""
	if start and end:
		return getdate(start), getdate(end)
	now = getdate(today())
	return get_first_day(now), get_last_day(now)


def billed_paise(start, end, cost_centers=None) -> int:
	"""Ex-GST value of submitted membership invoices posted in [start, end], in
	integer paise. A credit note's totals are negative, so a refund billed back
	reduces the figure without special-casing — the same shape as the cash read.
	``cost_centers`` limits it to those branches (Stage 10.3)."""
	if cost_centers is not None and not cost_centers:
		return 0
	params = {"start": getdate(start), "end": getdate(end)}
	cc_clause = ""
	if cost_centers is not None:
		cc_clause = "AND si.cost_center IN %(cost_centers)s"
		params["cost_centers"] = tuple(cost_centers)
	rows = frappe.db.sql(
		f"""
		SELECT si.base_net_total AS amt
		FROM `tabSales Invoice` si
		WHERE si.docstatus = 1
		  AND si.posting_date BETWEEN %(start)s AND %(end)s
		  AND {billing.MEMBERSHIP_INVOICE}
		  {cc_clause}
		""",
		params,
		as_dict=True,
	)
	return sum(calc.to_paise(r.amt) for r in rows)


def income_for_period(start=None, end=None, branches=None) -> dict:
	start, end = _period(start, end)
	basis = deferred.accounting_method()
	ccs = branch_mod.scope_cost_centers(branches)
	collected = calc.to_rupees(billing.membership_collected_paise(start, end, cost_centers=ccs))
	billed = calc.to_rupees(billed_paise(start, end, ccs))
	return {
		"start": str(start),
		"end": str(end),
		"basis": basis,
		"collected": collected,
		"billed": billed,
		"income": billed if basis == "Accrual" else collected,
	}


@frappe.whitelist()
def get_income(start=None, end=None, branch=None) -> dict:
	"""Owner/BFF: the dashboard's income figure for a month (default: this month).

	Open to the front desk as well as the owner — the dashboard showed staff this
	figure before, and this only corrects where it is read from."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	return income_for_period(start, end, branches=branch_mod.scope(branch))


@frappe.whitelist()
def get_branch_profit(start=None, end=None) -> dict:
	"""Stage 10.5: earned, spent and profit per branch for a period.

	Earned is GL income by cost center, so memberships, packs, day passes, refunds
	and discounts all count, invoiced (the dashboard shows cash received). Spent is
	Expense records by branch — the rule the dashboard and Profit First use, since
	expenses only reach the ledger when the owner switches that on. A branch-limited
	login gets only its own branches."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	start, end = _period(start, end)
	branches = branch_mod.scope()
	names = branches or frappe.get_all("Business Branch", order_by="is_default desc, name asc", pluck="name")
	by_cc = {branch_mod.branch_cost_center(b): b for b in names}
	totals = {b: {"branch": b, "earned": 0.0, "spent": 0.0} for b in names}
	unassigned = {"branch": None, "earned": 0.0, "spent": 0.0}

	for r in frappe.db.sql(
		"""
		SELECT gle.cost_center, SUM(gle.credit - gle.debit) AS net
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.is_cancelled = 0
		  AND gle.company = %(company)s
		  AND gle.posting_date BETWEEN %(start)s AND %(end)s
		  AND acc.root_type = 'Income'
		GROUP BY gle.cost_center
		""",
		{"start": start, "end": end, "company": branch_mod._company()},
		as_dict=True,
	):
		b = by_cc.get(r.cost_center)
		if b is None and branches is not None:
			continue  # not a branch this login may see
		(totals[b] if b else unassigned)["earned"] += flt(r.net)

	for e in frappe.get_all(
		"Expense",
		filters=branch_mod.filter_by_branch(
			{"docstatus": ["<", 2], "date": ["between", [start, end]]}, branches
		),
		fields=["branch", "sum(amount) as amount"],
		group_by="branch",
	):
		(totals.get(e.branch) or unassigned)["spent"] += flt(e.amount)

	out = list(totals.values()) + ([unassigned] if unassigned["earned"] or unassigned["spent"] else [])
	for t in out:
		t["earned"], t["spent"] = flt(t["earned"], 2), flt(t["spent"], 2)
		t["profit"] = flt(t["earned"] - t["spent"], 2)
	return {"start": str(start), "end": str(end), "branches": out}


def _month_keys(start, end):
	"""'YYYY-MM' for every month from start to end, inclusive."""
	keys, m = [], get_first_day(start)
	while m <= getdate(end):
		keys.append(m.strftime("%Y-%m"))
		m = get_first_day(frappe.utils.add_months(m, 1))
	return keys


@frappe.whitelist()
def get_member_report(months=12, branch=None) -> dict:
	"""Stage 11.1: members month by month — active, joined, left, kept %, cash per
	member — and lifetime value, for members homed in the branches in scope.

	"Active in a month" = a submitted invoice's service period touches that month
	(from_date..to_date; its posting month when it has none). Member status carries
	no leave date, so billing is the only honest record of who stayed.
	ponytail: scans every invoice of the members in scope; fine for a gym's volume,
	pre-aggregate per month if a tenant reaches tens of thousands of invoices."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	branches = branch_mod.scope(branch)
	months = max(1, min(int(months), 36))
	this_month = get_first_day(today())
	first = get_first_day(frappe.utils.add_months(this_month, -(months - 1)))
	window = _month_keys(first, this_month)
	before = get_first_day(frappe.utils.add_months(first, -1)).strftime("%Y-%m")

	customers = dict(
		(m.customer, m.name)
		for m in frappe.get_all(
			"Member",
			filters=branch_mod.filter_by_branch({"customer": ["is", "set"]}, branches),
			fields=["name", "customer"],
		)
	)
	covered: dict[str, set] = {}
	if customers:
		for si in frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "is_return": 0, "customer": ["in", list(customers)]},
			fields=["customer", "from_date", "to_date", "posting_date"],
		):
			span = (
				_month_keys(si.from_date, si.to_date)
				if si.from_date and si.to_date
				else [si.posting_date.strftime("%Y-%m")]
			)
			covered.setdefault(customers[si.customer], set()).update(span)

	first_month = {m: min(ks) for m, ks in covered.items()}
	ccs = branch_mod.scope_cost_centers(branches)
	rows, prev = [], {m for m, ks in covered.items() if before in ks}
	for key in window:
		active = {m for m, ks in covered.items() if key in ks}
		start = getdate(f"{key}-01")
		cash = calc.to_rupees(
			billing.membership_collected_paise(start, get_last_day(start), cost_centers=ccs)
		)
		rows.append(
			{
				"month": start.strftime("%b %Y"),
				"active": len(active),
				"joined": sum(1 for m in active if first_month[m] == key),
				"left": len(prev - active),
				"kept_pct": round(100 * len(prev & active) / len(prev), 1) if prev else None,
				"cash": cash,
				"per_member": round(cash / len(active), 2) if active else None,
			}
		)
		prev = active

	# Total money over total member-months: each month weighs by its size, so a
	# small month with a late payer does not drag the average.
	member_months = sum(r["active"] for r in rows)
	avg_per_member = round(sum(r["cash"] for r in rows) / member_months, 2) if member_months else None
	# Months paid SO FAR: a yearly plan's future months are not yet a stay.
	now_key = this_month.strftime("%Y-%m")
	stays = [sum(1 for k in ks if k <= now_key) for ks in covered.values()]
	stays = [n for n in stays if n]
	avg_months = round(sum(stays) / len(stays), 1) if stays else None
	return {
		"rows": rows,
		"avg_per_member_month": avg_per_member,
		"avg_months_paid": avg_months,
		"lifetime_value": round(avg_per_member * avg_months, 2) if avg_per_member and avg_months else None,
	}
