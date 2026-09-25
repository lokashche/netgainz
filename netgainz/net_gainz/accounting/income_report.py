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
		  AND si.subscription IS NOT NULL AND si.subscription != ''
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
