# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 8 DS-6: what the gym gave away, and what it cost in profit.

The stage's promise is that a discount is a *visible* decision. DS-1 shows the owner what
one discount costs before granting it; this is the other half — the monthly total, broken
down by the things an owner would actually act on: which campaign, which reason, which
staff member, which plan.

**Read from the invoices, not from the decisions.** A Discount Log row says a discount was
granted; an invoice says money was actually given up. Only the second is reportable, and
only the second stays right when a membership is discounted for one cycle and then bills
at full rate. So every figure here comes from submitted Sales Invoices:

    gross  = invoice ``total``          (the fee before the discount)
    given  = invoice ``discount_amount``
    net    = invoice ``net_total``      (what the member was actually billed, ex-GST)

Credit notes are excluded — a refund is not a discount, and WP-8 copies the subscription
link onto them, so anything reading invoices by subscription must filter them out.

**Attribution caveat (deliberate).** Which offer, reason and staff member a discount is
credited to comes from the membership's grant as it stands *now*. Editing a reason
re-labels that member's past invoices. The alternative — matching each invoice to the
Discount Log row in force on its posting date — buys precision no gym has asked for and
costs a join per invoice; the log itself remains the exact history of who changed what
(:func:`discounts.discount_history`).

Nothing here writes. Profit First is untouched (R15): the "what it cost you" split is the
same read-model preview DS-1 uses, applied to the month's total.
"""

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import discounts

UNATTRIBUTED = "Not given a reason"


def _period(start=None, end=None):
	"""The window to report on: an explicit range, else the current calendar month."""
	if start and end:
		return getdate(start), getdate(end)
	now = getdate(today())
	return get_first_day(now), get_last_day(now)


def _rows(start, end, branch=None) -> list[dict]:
	"""Every discounted membership invoice in the window, with who it belongs to."""
	conditions = ["si.docstatus = 1", "si.is_return = 0", "si.posting_date BETWEEN %(start)s AND %(end)s"]
	values = {"start": start, "end": end}
	if branch:
		conditions.append("ms.branch = %(branch)s")
		values["branch"] = branch

	return frappe.db.sql(
		f"""
		SELECT
			si.name AS sales_invoice,
			si.posting_date,
			si.total AS gross,
			si.net_total AS net,
			si.discount_amount AS given,
			ms.name AS membership,
			ms.member,
			ms.member_name,
			ms.membership_plan,
			ms.branch,
			ms.offer,
			ms.discount_reason,
			ms.discount_granted_by
		FROM `tabSales Invoice` si
		INNER JOIN `tabMembership` ms ON ms.subscription = si.subscription
		WHERE {" AND ".join(conditions)}
		  AND si.discount_amount > 0
		ORDER BY si.discount_amount DESC
		""",
		values,
		as_dict=True,
	)


def _group(rows, key, label_of=None) -> list[dict]:
	"""Sum gross / given / net per key, biggest giveaway first."""
	buckets = {}
	for row in rows:
		bucket = row.get(key) or UNATTRIBUTED
		entry = buckets.setdefault(
			bucket,
			{
				"label": label_of(row) if label_of else bucket,
				"gross": 0.0,
				"given": 0.0,
				"net": 0.0,
				"invoices": 0,
			},
		)
		entry["gross"] += flt(row["gross"])
		entry["given"] += flt(row["given"])
		entry["net"] += flt(row["net"])
		entry["invoices"] += 1
	return sorted(buckets.values(), key=lambda e: e["given"], reverse=True)


@frappe.whitelist()
def discounts_given(start=None, end=None, branch=None, top=10) -> dict:
	"""What was given away in the window, and what it cost at the current TAPs.

	Owner-only: this is the leak report. The front desk sees the discount on the member
	they are serving; how much the gym gave away in total is the owner's business.
	"""
	permissions.require_role(permissions.GYM_OWNER)
	start, end = _period(start, end)
	rows = _rows(start, end, branch)

	given = sum(flt(r["given"]) for r in rows)
	gross = sum(flt(r["gross"]) for r in rows)
	net = sum(flt(r["net"]) for r in rows)

	return {
		"start": str(start),
		"end": str(end),
		"branch": branch,
		"gross": gross,
		"given": given,
		"net": net,
		# The share of what the gym could have billed that it chose not to.
		"given_percent": round(given * 100.0 / gross, 1) if gross else 0.0,
		"invoices": len(rows),
		"members": len({r["member"] for r in rows if r["member"]}),
		"by_offer": _group(rows, "offer"),
		"by_reason": _group(rows, "discount_reason"),
		"by_staff": _group(rows, "discount_granted_by"),
		"by_plan": _group(rows, "membership_plan"),
		"by_branch": _group(rows, "branch"),
		"biggest": rows[: int(top or 10)],
		# R15: a pure read-model. What this month's giveaway would have become had it
		# been collected, split at the gym's current Profit First percentages.
		"profit_impact": discounts.profit_impact(given),
	}


@frappe.whitelist()
def discounts_this_month(branch=None) -> dict:
	"""The dashboard's one-liner: what has been given away so far this month."""
	report = discounts_given(branch=branch)
	return {
		"start": report["start"],
		"end": report["end"],
		"given": report["given"],
		"gross": report["gross"],
		"given_percent": report["given_percent"],
		"members": report["members"],
		"profit_impact": report["profit_impact"],
	}
