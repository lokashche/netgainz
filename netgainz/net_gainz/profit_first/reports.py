# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 11.6 — Profit First over time.

* **trend** — each month's assessment (Real Revenue, tier, actual % vs target %
  per bucket) from the SAME ``instant_assessment.assess`` the Profit First page
  uses, so the two never disagree. Follows the branch when PF is per-branch.
* **sweeps** — every allocation proposed / approved, with what went where.
* **reserves** — each Profit First account's balance at every month end.
* **tax** — tax set aside by approved sweeps vs Tax-bucket expenses paid, per month.

Sweeps, reserves and tax are whole-gym money (one set of accounts), so a
branch-limited login gets the trend only.
"""

import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import branch as branch_mod
from netgainz.net_gainz.profit_first import calc
from netgainz.net_gainz.profit_first.instant_assessment import assess


def _months(n):
	first = get_first_day(today())
	return [get_first_day(add_months(first, -i)) for i in range(n - 1, -1, -1)]


def _trend(months, branches, settings):
	out = []
	for m in months:
		result, _ = assess(m, get_last_day(m), "This Month", m.strftime("%b %Y"), branches, settings)
		out.append(
			{
				"month": m.strftime("%b %Y"),
				"real_revenue": result["real_revenue"],
				"tier_code": result["tier_code"],
				"applicable": result["applicable"],
				"buckets": {
					r["bucket"]: {"cap_pct": r["cap_pct"], "tap_pct": r["tap_pct"], "actual": r["actual"]}
					for r in result["rows"]
				},
			}
		)
	return out


def _sweeps(since):
	sweeps = frappe.get_all(
		"PF Sweep",
		filters={"docstatus": ["<", 2], "sweep_date": [">=", since]},
		fields=["name", "sweep_date", "period_label", "real_revenue", "tier_code", "docstatus"],
		order_by="sweep_date desc",
	)
	for s in sweeps:
		s["status"] = "Approved" if s.pop("docstatus") == 1 else "Awaiting approval"
		s["amounts"] = {
			a.account_role: flt(a.amount)
			for a in frappe.get_all(
				"PF Sweep Allocation", filters={"parent": s.name}, fields=["account_role", "amount"]
			)
		}
	return sweeps


def _reserves(months, settings):
	accounts = {
		r.account_role: r.account_link
		for r in settings.accounts
		if r.account_link and r.account_role != "Income"
	}
	if not accounts:
		return []
	start = months[0]
	opening = dict(
		frappe.db.sql(
			"""SELECT account, SUM(debit - credit) FROM `tabGL Entry`
			WHERE is_cancelled = 0 AND account IN %(accs)s AND posting_date < %(start)s GROUP BY account""",
			{"accs": tuple(accounts.values()), "start": start},
		)
	)
	moves = {}
	for acc, ym, net in frappe.db.sql(
		"""SELECT account, DATE_FORMAT(posting_date, '%%Y-%%m'), SUM(debit - credit) FROM `tabGL Entry`
		WHERE is_cancelled = 0 AND account IN %(accs)s AND posting_date >= %(start)s GROUP BY account, 2""",
		{"accs": tuple(accounts.values()), "start": start},
	):
		moves[(acc, ym)] = flt(net)
	out = []
	running = {role: flt(opening.get(acc)) for role, acc in accounts.items()}
	for m in months:
		for role, acc in accounts.items():
			running[role] += moves.get((acc, m.strftime("%Y-%m")), 0.0)
		out.append({"month": m.strftime("%b %Y"), "balances": dict(running)})
	return out


def _tax(months, sweeps):
	saved = {}
	for s in sweeps:
		if s["status"] == "Approved":
			key = getdate(s["sweep_date"]).strftime("%b %Y")
			saved[key] = saved.get(key, 0.0) + flt(s["amounts"].get(calc.TAX))
	paid = dict(
		frappe.db.sql(
			"""SELECT DATE_FORMAT(e.date, '%%b %%Y'), SUM(e.amount) FROM `tabExpense` e
			INNER JOIN `tabExpense Category` c ON c.name = e.category
			WHERE e.docstatus < 2 AND c.pf_bucket = %(tax)s AND e.date >= %(start)s GROUP BY 1""",
			{"tax": calc.TAX, "start": months[0]},
		)
	)
	return [
		{"month": (k := m.strftime("%b %Y")), "set_aside": flt(saved.get(k)), "paid": flt(paid.get(k))}
		for m in months
	]


@frappe.whitelist()
def get_pf_reports(months=12, branch=None) -> dict:
	"""Owner / staff: Profit First over the last ``months`` months."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	per_branch = frappe.db.get_single_value("Business Settings", "pf_per_branch")
	branches = branch_mod.scope(branch) if per_branch else None
	if not branches:
		branch_mod.require_all_branches("Profit First")
	settings = frappe.get_single("Profit First Settings")
	if not settings.pf_enabled:
		return {"enabled": False}

	ms = _months(max(1, min(int(months), 24)))
	out = {"enabled": True, "branches": branches, "trend": _trend(ms, branches, settings)}
	if branch_mod.is_branch_limited():
		return out
	sweeps = _sweeps(ms[0])
	out.update({"sweeps": sweeps, "reserves": _reserves(ms, settings), "tax": _tax(ms, sweeps)})
	return out
