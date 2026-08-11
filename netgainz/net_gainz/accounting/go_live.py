# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Switching automatic billing on for a tenant that already has members.

Every membership created through the app bills from the moment it is saved — WP-11
removed the cut-over flag, and there is nothing to switch. But a tenant does not
arrive that way. Kinetic Edge's 267 members and 75 July memberships were **loaded**
from the gym's own records with ``is_backfill = 1``, which tells
``billing.on_membership_insert`` to skip provisioning (otherwise the load would
raise a second, wrong-priced invoice for a period the gym had already collected).

Nothing ever un-skips them. Those memberships have no Subscription, so they will
never bill. This module is the missing step: an explicit, previewable, idempotent
"start billing" for memberships that already exist.

**The hazard it exists to avoid.** ``billing.cycle_start`` anchors a member's cycle
to their joining day and returns the CURRENT period's start — which is usually in
the past. A member who joined on the 15th, switched on today (the 9th), would have
their subscription start on the 15th of LAST month, and ERPNext would immediately
raise an invoice for a period the gym has already collected in cash. That is a
duplicate charge to a real person.

So the default is :data:`NEXT_PERIOD`: keep the joining-day alignment, but start
from the next boundary. The gym's existing collections stand, and the system takes
over cleanly from the following cycle. :data:`CURRENT_PERIOD` is offered for a
tenant that genuinely has not collected the current period yet.

Everything here is a **dry run by default**. Read the preview, then commit.
"""

from __future__ import annotations

import frappe
from frappe.utils import getdate, today

from netgainz.net_gainz.accounting import billing, billing_intervals, branch, provisioning
from netgainz.net_gainz.profit_first import accounts as pf_accounts

NEXT_PERIOD = "Next period"
CURRENT_PERIOD = "Current period"
START_MODES = (NEXT_PERIOD, CURRENT_PERIOD)


def _company(company=None):
	return company or pf_accounts.default_company()


# --------------------------------------------------------------------------- #
# readiness
# --------------------------------------------------------------------------- #
def _cadence(membership_plan) -> tuple[str, int] | None:
	"""The (interval, count) a plan bills on, or None if it cannot be resolved."""
	sub_plan = frappe.db.get_value("Membership Plan", membership_plan, "subscription_plan")
	if not sub_plan:
		return None
	row = frappe.db.get_value(
		"Subscription Plan", sub_plan, ["billing_interval", "billing_interval_count"], as_dict=True
	)
	if not row or not row.billing_interval:
		return None
	return row.billing_interval, int(row.billing_interval_count or 1)


def assess(membership) -> dict:
	"""Can this membership start billing, and what would happen if it did?

	Never writes. Returns the row the owner reads before committing.
	"""
	ms = frappe.db.get_value(
		"Membership",
		membership,
		["name", "member", "member_name", "membership_plan", "tariff", "subscription", "branch"],
		as_dict=True,
	)
	row = {
		"membership": ms.name,
		"member": ms.member,
		"member_name": ms.member_name or ms.member,
		"membership_plan": ms.membership_plan,
		"price": billing.membership_price(ms.name),
		"already_billing": bool(ms.subscription and frappe.db.exists("Subscription", ms.subscription)),
		"ready": False,
		"blocked_reason": None,
		"joining_date": None,
		"first_invoice_on": None,
		"warnings": [],
	}

	if row["already_billing"]:
		row["blocked_reason"] = "Already billing"
		return row
	if not ms.membership_plan:
		row["blocked_reason"] = "No plan on the membership"
		return row
	if row["price"] <= 0:
		row["blocked_reason"] = "No price on the membership or the plan"
		return row
	if not frappe.db.get_value("Member", ms.member, "customer"):
		row["blocked_reason"] = "Member has no billing account yet"
		return row
	cadence = _cadence(ms.membership_plan)
	if not cadence:
		row["blocked_reason"] = "Plan has no billing cadence — set a HSN/SAC and a duration"
		return row

	joining = frappe.db.get_value("Member", ms.member, "date_of_joining")
	row["joining_date"] = str(getdate(joining)) if joining else None
	if not joining:
		# Not a blocker, but the member loses their real anniversary: their cycle
		# will fall on the day billing was switched on instead.
		row["warnings"].append("No joining date — the billing day will be today, not their anniversary")

	interval, count = cadence
	anchor = getdate(joining) if joining else getdate(today())
	row["current_period_start"] = str(
		billing_intervals.latest_cycle_start(anchor, interval, count, getdate(today()))
	)
	row["next_period_start"] = str(
		billing_intervals.next_cycle_start(anchor, interval, count, getdate(today()))
	)
	row["ready"] = True
	return row


@frappe.whitelist()
def billing_readiness() -> dict:
	"""Owner/BFF: the go-live preview — who will start billing, who cannot, and why.

	Read-only. This is the screen the owner works through before switching on.
	"""
	rows = [assess(name) for name in frappe.get_all("Membership", pluck="name")]
	ready = [r for r in rows if r["ready"]]
	blocked = [r for r in rows if not r["ready"] and not r["already_billing"]]
	return {
		"total": len(rows),
		"ready_count": len(ready),
		"blocked_count": len(blocked),
		"already_billing_count": sum(1 for r in rows if r["already_billing"]),
		"warning_count": sum(1 for r in ready if r["warnings"]),
		"ready": ready,
		"blocked": blocked,
		"start_modes": list(START_MODES),
	}


# --------------------------------------------------------------------------- #
# the switch
# --------------------------------------------------------------------------- #
def _provision(row, start_mode, company) -> str | None:
	"""Create the Subscription for one ready membership, anchored per ``start_mode``."""
	membership = frappe.get_doc("Membership", row["membership"])
	sub_plan = frappe.db.get_value(
		"Membership Plan", membership.membership_plan, "subscription_plan"
	) or provisioning.provision_subscription_plan(membership.membership_plan, company)
	if not sub_plan:
		return None

	start = getdate(
		row["next_period_start"] if start_mode == NEXT_PERIOD else row["current_period_start"]
	)

	sub = frappe.new_doc("Subscription")
	sub.party_type = "Customer"
	sub.party = frappe.db.get_value("Member", membership.member, "customer")
	sub.company = company
	sub.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	sub.start_date = start
	sub.generate_invoice_at = billing.GENERATE_INVOICE_AT
	sub.submit_invoice = 1
	sub.days_until_due = frappe.db.get_single_value("Business Settings", "days_until_due") or 0
	sub.append("plans", {"plan": sub_plan, "qty": 1})
	sub.insert(ignore_permissions=True)

	membership.db_set("subscription", sub.name, update_modified=False)
	# The load flag has done its job — clear it so the membership behaves like any
	# other from here, and a second run cannot mistake it for un-billable history.
	if membership.get("is_backfill"):
		membership.db_set("is_backfill", 0, update_modified=False)
	return sub.name


@frappe.whitelist()
def start_billing(start_mode=NEXT_PERIOD, dry_run=1, memberships=None) -> dict:
	"""Owner/BFF: switch automatic billing on for memberships that already exist.

	``start_mode`` — :data:`NEXT_PERIOD` (default, safe: the gym's existing
	collections stand) or :data:`CURRENT_PERIOD` (bills the period in progress,
	which for most members started before today).

	``dry_run`` — 1 by default. Nothing is created; the result tells the owner
	exactly what would happen. Pass 0 to commit.

	Idempotent: a membership that already has a Subscription is skipped, so a
	re-run after fixing a few prices only picks up the newly-ready ones.
	"""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)

	start_mode = start_mode if start_mode in START_MODES else NEXT_PERIOD
	dry_run = bool(int(dry_run or 0))
	company = _company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")

	if isinstance(memberships, str):
		memberships = frappe.parse_json(memberships)
	names = memberships or frappe.get_all("Membership", pluck="name")

	started, skipped, failed = [], [], []
	for name in names:
		row = assess(name)
		if not row["ready"]:
			skipped.append({"membership": name, "reason": row["blocked_reason"]})
			continue
		first_invoice = row["next_period_start"] if start_mode == NEXT_PERIOD else row["current_period_start"]
		if dry_run:
			started.append(
				{
					"membership": name,
					"member_name": row["member_name"],
					"price": row["price"],
					"first_invoice_on": first_invoice,
					"warnings": row["warnings"],
				}
			)
			continue
		try:
			subscription = _provision(row, start_mode, company)
			if not subscription:
				failed.append({"membership": name, "error": "Could not provision a billing plan"})
				continue
			started.append(
				{
					"membership": name,
					"member_name": row["member_name"],
					"price": row["price"],
					"first_invoice_on": first_invoice,
					"subscription": subscription,
					"warnings": row["warnings"],
				}
			)
		except Exception as exc:
			# One bad row must never stop the switch part-way through the gym.
			frappe.log_error(title=f"Go-live: could not start billing for {name}")
			failed.append({"membership": name, "error": str(exc)[:200]})

	return {
		"dry_run": dry_run,
		"start_mode": start_mode,
		"started_count": len(started),
		"skipped_count": len(skipped),
		"failed_count": len(failed),
		"started": started,
		"skipped": skipped,
		"failed": failed,
	}
