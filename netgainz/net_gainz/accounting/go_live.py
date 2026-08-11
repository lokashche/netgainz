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

:data:`CALENDAR_MONTH` is the third shape, and a common one: some gyms want every
member billed **1st to month end**, not on their own joining day, so the month's
takings close cleanly. Billing then starts on the 1st of next month, and the days
left in this month are charged once, pro-rata, as a part-month invoice. ERPNext
cannot do that proration for us — ``get_prorata_factor`` returns 1 outright for
prepaid subscriptions, which ours are (traced 2026-08-11) — so
:func:`raise_part_month_invoice` builds it.

That part-month invoice is deliberately stamped with the membership's
``subscription``. Profit First counts cash by allocations against
subscription-linked invoices, so an unstamped stub would take a member's money
straight out of the owner's revenue figures.

Everything here is a **dry run by default**. Read the preview, then commit.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from netgainz.net_gainz.accounting import billing, billing_intervals, branch, provisioning
from netgainz.net_gainz.profit_first import accounts as pf_accounts

NEXT_PERIOD = "Next period"
CURRENT_PERIOD = "Current period"
CALENDAR_MONTH = "Calendar month"
START_MODES = (NEXT_PERIOD, CURRENT_PERIOD, CALENDAR_MONTH)


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
	# Calendar-month alignment: bill 1st-to-month-end for everyone, and charge the
	# days left in this month once, pro-rata.
	calendar_start, part_days, part_amount = part_month(row["price"])
	row["calendar_month_start"] = str(calendar_start)
	row["part_month_days"] = part_days
	row["part_month_amount"] = part_amount
	row["ready"] = True
	return row


def part_month(price) -> tuple[object, int, float]:
	"""``(first of next month, days left in this one, what those days cost)``.

	Charged on a plain day count: a member joining the switch on the 20th of a
	31-day month pays 12/31 of the fee for the remainder, then a full month from
	the 1st. Rounding is the app's one rule (half away from zero, via paise) so the
	stub can never disagree with the rest of the money maths by a paisa.
	"""
	from netgainz.net_gainz.profit_first import calc

	now = getdate(today())
	month_end = get_last_day(now)
	days_left = (month_end - now).days + 1  # inclusive of today
	days_in_month = month_end.day
	amount = calc.to_rupees(calc.round_half_away(calc.to_paise(price) * days_left / days_in_month))
	return get_first_day(billing_intervals.add_months(now, 1)), days_left, amount


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
def _provision(row, start_mode, company, bill_part_month=True) -> str | None:
	"""Create the Subscription for one ready membership, anchored per ``start_mode``."""
	membership = frappe.get_doc("Membership", row["membership"])
	sub_plan = frappe.db.get_value(
		"Membership Plan", membership.membership_plan, "subscription_plan"
	) or provisioning.provision_subscription_plan(membership.membership_plan, company)
	if not sub_plan:
		return None

	if start_mode == CALENDAR_MONTH:
		start = getdate(row["calendar_month_start"])
	elif start_mode == CURRENT_PERIOD:
		start = getdate(row["current_period_start"])
	else:
		start = getdate(row["next_period_start"])

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
	if start_mode == CALENDAR_MONTH and bill_part_month:
		invoice = raise_part_month_invoice(
			membership.name, sub.name, row["part_month_amount"], company
		)
		if invoice:
			billing.sync_derived_fields(membership.name)
	# The load flag has done its job — clear it so the membership behaves like any
	# other from here, and a second run cannot mistake it for un-billable history.
	if membership.get("is_backfill"):
		membership.db_set("is_backfill", 0, update_modified=False)
	return sub.name


def raise_part_month_invoice(membership, subscription, amount, company) -> str | None:
	"""Charge the days left in the current month, once, before calendar billing starts.

	Stamped with ``subscription`` on purpose: Profit First counts cash from
	allocations against subscription-linked invoices, so an unstamped stub would
	take this money out of the owner's revenue figures entirely. The flag tells
	``billing.on_sales_invoice_before_validate`` to leave it alone — that hook
	exists to price a FULL period and to attach installment terms, and would
	otherwise overwrite the pro-rata rate with the full monthly fee.
	"""
	amount = flt(amount)
	if amount <= 0:
		return None
	membership = frappe.get_doc("Membership", membership)
	item = frappe.db.get_value("Membership Plan", membership.membership_plan, "item")
	if not item:
		return None

	si = frappe.new_doc("Sales Invoice")
	si.flags.netgainz_part_month = True
	si.customer = frappe.db.get_value("Member", membership.member, "customer")
	si.company = company
	si.set_posting_time = 1
	si.posting_date = getdate(today())
	si.due_date = getdate(today())
	si.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	si.subscription = subscription
	si.remarks = "NetGainz: part month before calendar billing starts"
	si.append("items", {"item_code": item, "qty": 1, "rate": amount, "cost_center": si.cost_center})
	# Resolve the party's tax template and EXPAND its rows. Without this the stub
	# came out with `taxes_and_charges` set but `taxes` empty — no GST at all, while
	# every other membership invoice carried it (traced 2026-08-11: generated
	# invoice 1000 -> 1180, stub 500 -> 500). Invisible for a non-GST tenant, an
	# under-charge for a registered one.
	si.set_missing_values(for_validate=True)
	if si.taxes_and_charges and not si.get("taxes"):
		si.set_taxes()
	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


@frappe.whitelist()
def start_billing(start_mode=NEXT_PERIOD, dry_run=1, memberships=None, bill_part_month=1) -> dict:
	"""Owner/BFF: switch automatic billing on for memberships that already exist.

	``start_mode`` — :data:`NEXT_PERIOD` (default, safe: the gym's existing
	collections stand), :data:`CALENDAR_MONTH` (everyone billed 1st-to-month-end,
	with the rest of this month charged once pro-rata unless ``bill_part_month``
	is off), or :data:`CURRENT_PERIOD` (bills the period in progress,
	which for most members started before today).

	``dry_run`` — 1 by default. Nothing is created; the result tells the owner
	exactly what would happen. Pass 0 to commit.

	``memberships`` — an optional list of names. Switching the whole gym on at once
	is the go-live case, but a gym that wants to move members over a few at a time
	(or test with one) passes just those.

	Idempotent: a membership that already has a Subscription is skipped, so a
	re-run after fixing a few prices only picks up the newly-ready ones. New
	memberships created IN the app never need this — they bill from the moment
	they are saved.
	"""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)

	start_mode = start_mode if start_mode in START_MODES else NEXT_PERIOD
	dry_run = bool(int(dry_run or 0))
	bill_part_month = bool(int(bill_part_month or 0))
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
		if start_mode == CALENDAR_MONTH:
			first_invoice = row["calendar_month_start"]
		elif start_mode == CURRENT_PERIOD:
			first_invoice = row["current_period_start"]
		else:
			first_invoice = row["next_period_start"]
		part_month_now = (
			row["part_month_amount"] if start_mode == CALENDAR_MONTH and bill_part_month else 0.0
		)
		if dry_run:
			started.append(
				{
					"membership": name,
					"member_name": row["member_name"],
					"price": row["price"],
					"first_invoice_on": first_invoice,
					"part_month_amount": part_month_now,
					"part_month_days": row["part_month_days"] if part_month_now else 0,
					"warnings": row["warnings"],
				}
			)
			continue
		try:
			subscription = _provision(row, start_mode, company, bill_part_month)
			if not subscription:
				failed.append({"membership": name, "error": "Could not provision a billing plan"})
				continue
			started.append(
				{
					"membership": name,
					"member_name": row["member_name"],
					"price": row["price"],
					"first_invoice_on": first_invoice,
					"part_month_amount": part_month_now,
					"part_month_days": row["part_month_days"] if part_month_now else 0,
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
		"bill_part_month": bill_part_month,
		"part_month_total": flt(sum(r.get("part_month_amount") or 0 for r in started)),
		"started_count": len(started),
		"skipped_count": len(skipped),
		"failed_count": len(failed),
		"started": started,
		"skipped": skipped,
		"failed": failed,
	}
