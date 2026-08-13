# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 8 DS-4: free trials — "first week free", "first month free".

A trial is not a discount. Nothing is invoiced at all while it runs: the member is
enrolled, uses the gym, and their **first invoice is raised the day the trial ends**,
for the full period, by the same daily job that bills everyone else.

**This is native ERPNext behaviour, traced in DS-0 (2026-08-11) rather than assumed.**
A Subscription carrying ``trial_period_start`` / ``trial_period_end`` reports status
``Trialling``, its ``process()`` generates NO invoice, and its first billing period
starts by itself at ``trial_period_end + 1``. So DS-4 is three small things:

1. resolve how many trial days this member gets (plan default, per-member override, or
   an explicit "no trial" for someone who has already had one);
2. stamp the window on the Subscription when billing is provisioned — and, crucially,
   **do not force the first invoice** at enrolment, because
   ``billing.force_generate_invoice`` posts at ``current_invoice_start``, which during a
   trial is already the post-trial date, and would bill a trial member on day one;
3. show the trial: the membership reads ``Trial`` with the date it ends, and the owner
   gets a "trials ending" list to follow up on — the follow-up itself becomes a proper
   pipeline task in Stage 9's OP-2.

A trial re-anchors the billing cycle to the day it ends, which is what a member would
expect: they pay for their first full period starting the day the free one stops.
"""

import frappe
from frappe.utils import add_days, getdate, today

TRIAL_STATUS = "Trial"


# --------------------------------------------------------------------------- #
# how long is this member's trial?
# --------------------------------------------------------------------------- #
def plan_trial_days(membership_plan) -> int:
	if not membership_plan:
		return 0
	return int(frappe.db.get_value("Membership Plan", membership_plan, "trial_days") or 0)


def resolve_trial_days(membership) -> int:
	"""The trial this membership gets: none if skipped, its own override, else the plan's.

	``skip_trial`` exists because "0 days" cannot mean both "use the plan's setting" and
	"this one gets nothing" — and the second case is real (someone who already had their
	free week, or a member the owner simply does not want to give one to).
	"""
	if membership.get("skip_trial"):
		return 0
	own = int(membership.get("trial_days") or 0)
	if own > 0:
		return own
	return plan_trial_days(membership.get("membership_plan"))


def trial_window(membership, start) -> tuple | None:
	"""(first day, last day) of the trial, or None when there isn't one.

	The window starts no earlier than today: a member enrolling mid-cycle has a billing
	anchor in the past (WP-10.0), and a trial that was already over before it began
	would be a strange thing to hand someone.
	"""
	days = resolve_trial_days(membership)
	if days <= 0:
		return None
	first = max(getdate(start or today()), getdate(today()))
	return first, add_days(first, days - 1)


# --------------------------------------------------------------------------- #
# is this membership on trial right now?
# --------------------------------------------------------------------------- #
def trial_end(membership) -> object | None:
	"""The membership's trial end date, read from the Subscription that owns it."""
	subscription = membership.get("subscription")
	if not subscription:
		return None
	end = frappe.db.get_value("Subscription", subscription, "trial_period_end")
	return getdate(end) if end else None


def is_on_trial(membership, on_date=None) -> bool:
	end = trial_end(membership)
	return bool(end) and getdate(on_date or today()) <= end


def first_billing_date(membership) -> object | None:
	"""When this trial member's first real invoice falls: the day after the trial."""
	end = trial_end(membership)
	return add_days(end, 1) if end else None


def sync_trial_fields(membership) -> None:
	"""Persist the trial's end date and first billing date onto the membership.

	Stored so every list, filter and report can read the trial without joining
	Subscription — and so the owner app can say "on trial until the 18th" plainly.
	"""
	end = trial_end(membership)
	if not end:
		return
	membership.db_set(
		{"trial_ends_on": end, "next_renewal": add_days(end, 1), "status": TRIAL_STATUS},
		update_modified=False,
	)


# --------------------------------------------------------------------------- #
# what the owner needs to see
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def trials_ending(within_days=7) -> dict:
	"""Trials running now, split into "ending soon" and "still running".

	Read-only. A trial ending is the single most useful follow-up a gym has: the member
	is in the building today and paying from tomorrow.
	"""
	within = int(within_days or 7)
	td = getdate(today())
	horizon = add_days(td, within)

	rows = frappe.get_all(
		"Membership",
		filters={"trial_ends_on": [">=", td]},
		fields=[
			"name",
			"member",
			"member_name",
			"membership_plan",
			"tariff",
			"trial_ends_on",
			"status",
		],
		order_by="trial_ends_on asc",
		limit_page_length=0,
	)
	ending_soon = [r for r in rows if getdate(r.trial_ends_on) <= horizon]
	later = [r for r in rows if getdate(r.trial_ends_on) > horizon]
	return {
		"within_days": within,
		"ending_soon": ending_soon,
		"later": later,
		"on_trial": len(rows),
	}


@frappe.whitelist()
def trial_summary(start=None, end=None) -> dict:
	"""Trials given in a window, and how many turned into paying members.

	"Converted" means the trial has finished and the membership has been billed at
	least once — the honest test, since the first invoice only exists once the trial
	ended. Trials still running are counted separately rather than as failures.
	"""
	filters = {"trial_ends_on": ["is", "set"]}
	if start and end:
		filters["creation"] = ["between", [start, end]]

	rows = frappe.get_all(
		"Membership",
		filters=filters,
		fields=["name", "subscription", "trial_ends_on"],
		limit_page_length=0,
	)
	td = getdate(today())
	running = [r for r in rows if getdate(r.trial_ends_on) >= td]
	finished = [r for r in rows if getdate(r.trial_ends_on) < td]
	converted = [
		r
		for r in finished
		if r.subscription
		and frappe.db.exists(
			"Sales Invoice", {"subscription": r.subscription, "docstatus": 1, "is_return": 0}
		)
	]
	return {
		"trials": len(rows),
		"running": len(running),
		"finished": len(finished),
		"converted": len(converted),
		"conversion_rate": round(len(converted) * 100.0 / len(finished), 1) if finished else None,
	}
