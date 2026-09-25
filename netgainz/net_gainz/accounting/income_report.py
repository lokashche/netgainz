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
from frappe.utils import get_first_day, get_last_day, getdate, today

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
