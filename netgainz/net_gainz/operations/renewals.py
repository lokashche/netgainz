# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Membership renewals — surfacing memberships due for renewal (Stage 6).

A Subscription's ``next_renewal`` is when the member's current membership lapses.
This module reads those dates into an in-app "Renewals Due" list (due soon vs
already overdue) and, optionally, raises a daily in-app notification for the
gym's owner/staff. It is read-only and notify-only: it never charges a member,
sends an email/SMS, or moves money.

Only each member's LATEST membership (the one with the furthest ``next_renewal``)
is considered current, so a member who has already renewed never lingers on the
overdue list because of an older, superseded subscription.
"""

import frappe
from frappe.utils import add_days, getdate, today

from netgainz.net_gainz.accounting import trials

DEFAULT_REMINDER_DAYS = 7


def _reminder_days() -> int:
	raw = frappe.db.get_single_value("Business Settings", "renewal_reminder_days")
	try:
		days = int(raw)
	except (TypeError, ValueError):
		days = DEFAULT_REMINDER_DAYS
	return days if days > 0 else DEFAULT_REMINDER_DAYS


def get_renewals(within_days=None) -> dict:
	"""Return memberships due soon and already overdue for renewal.

	``within_days`` overrides the configured reminder window for "due soon".
	"""
	within = int(within_days) if within_days else _reminder_days()
	td = getdate(today())
	horizon = add_days(td, within)

	subs = frappe.get_all(
		"Membership",
		# DS-4: a member on a free trial has a next_renewal (the day billing starts) but
		# is not "due for renewal" — nothing has been sold to them yet. They get their own
		# "trials ending" list; showing them here would read as a lapsing membership.
		# OP-3: a cancelled membership never renews and never nags.
		filters=[["next_renewal", "is", "set"], ["status", "not in", [trials.TRIAL_STATUS, "Cancelled"]]],
		fields=["name", "member", "member_name", "membership_plan", "next_renewal", "status"],
		order_by="next_renewal asc",
		limit_page_length=0,
	)

	# Keep each member's latest (current) membership only.
	latest = {}
	for s in subs:
		key = s.member or s.name
		cur = latest.get(key)
		if cur is None or getdate(s.next_renewal) > getdate(cur.next_renewal):
			latest[key] = s
	current = list(latest.values())

	members = {s.member for s in current if s.member}
	phones = {}
	if members:
		for m in frappe.get_all(
			"Member", filters={"name": ["in", list(members)]}, fields=["name", "phone"]
		):
			phones[m.name] = m.phone

	due_soon, overdue = [], []
	for s in current:
		nr = getdate(s.next_renewal)
		row = {
			"subscription": s.name,
			"member": s.member,
			"member_name": s.member_name,
			"phone": phones.get(s.member),
			"membership_plan": s.membership_plan,
			"next_renewal": str(nr),
			"days_until": (nr - td).days,
			"status": s.status,
		}
		if nr < td:
			overdue.append(row)
		elif nr <= horizon:
			due_soon.append(row)

	due_soon.sort(key=lambda r: r["next_renewal"])
	overdue.sort(key=lambda r: r["next_renewal"])

	return {
		"within_days": within,
		"due_soon": due_soon,
		"overdue": overdue,
		"due_soon_count": len(due_soon),
		"overdue_count": len(overdue),
	}


@frappe.whitelist()
def get_renewals_due(within_days=None) -> dict:
	"""Whitelisted read-model for the Renewals page + dashboard widget."""
	return get_renewals(within_days)


def notify_due_renewals():
	"""Daily scheduler hook: raise ONE in-app notification per owner/staff user
	listing memberships due within the reminder window. Idempotent (one digest per
	user per day), opt-out via renewal_reminders_enabled. No email/SMS is sent."""
	if not frappe.db.get_single_value("Business Settings", "renewal_reminders_enabled"):
		return None

	data = get_renewals()
	due = data["due_soon"]
	if not due:
		return None

	td = getdate(today())
	subject = f"{len(due)} membership(s) due for renewal within {data['within_days']} days"
	body = "<br>".join(f"{r['member_name'] or r['member']} — {r['next_renewal']}" for r in due[:20])

	created = 0
	for user in _owner_users():
		# Idempotency: skip if this digest already went to the user today.
		if frappe.db.exists(
			"Notification Log",
			{"for_user": user, "subject": subject, "creation": [">=", str(td)]},
		):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": body,
				"document_type": "Membership",
			}
		).insert(ignore_permissions=True)
		created += 1

	frappe.logger("netgainz").info(f"Renewal reminder: {len(due)} due, notified {created} user(s)")
	return {"due": len(due), "notified": created}


def _owner_users() -> list:
	"""Enabled users holding the System Manager role (the gym's owner/staff)."""
	rows = frappe.get_all(
		"Has Role",
		filters={"role": "System Manager", "parenttype": "User"},
		fields=["parent"],
		limit_page_length=0,
	)
	users = []
	for r in rows:
		if r.parent in ("Administrator", "Guest"):
			continue
		if frappe.db.get_value("User", r.parent, "enabled"):
			users.append(r.parent)
	return users
