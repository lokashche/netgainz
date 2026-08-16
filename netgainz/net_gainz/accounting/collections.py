# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Who owes money, and when — the collections read and its daily reminder.

**Why this exists.** A gym that lets a member pay a quarterly fee in three parts has
made three promises to chase, not one. Everything needed to chase them was already
here — :func:`billing.open_obligations` turns any membership, in either billing mode,
into a plain list of ``(due_date, amount, outstanding)`` rows — but nothing read it
across the whole gym, and nothing told the owner when a part fell due.

Five daily reminders already existed on the day this was written: renewals, absences,
enquiry follow-ups, pack expiry, assessments. **None of them was about money.** The gym
was reminded to chase a member who had stopped coming, but not one who had missed an
instalment.

Deliberately built on ``open_obligations`` rather than on invoices, so a gym billing
in Commitment mode (one invoice, several scheduled parts) and one billing
Pay-as-you-go (one invoice per part) produce the same list without either being a
special case.

Notify-only, like every other digest here: an in-app Notification Log entry, one per
user per day, opt-out in Business Settings. No email, no SMS.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.operations.renewals import _owner_users

#: A part is "due soon" this many days ahead unless the tenant says otherwise.
DEFAULT_DUE_SOON_DAYS = 3

#: Statuses whose obligations are worth chasing. A cancelled membership is not.
CHASEABLE = ("Pending", "Partial", "Overdue", "Paid")


def _due_soon_days() -> int:
	raw = frappe.db.get_single_value("Business Settings", "dues_reminder_days")
	# An unset Int Single reads 0, not None, so `or` is the correct guard here --
	# the same trap that made two other settings display "0 days" on screen.
	return int(raw or 0) or DEFAULT_DUE_SOON_DAYS


def get_dues(within_days: int | None = None) -> dict:
	"""Every unpaid part across the gym, split into late / due now / due soon.

	Read-only. One row per *part*, not per member, because that is the thing that
	gets chased and the thing a payment settles.
	"""
	horizon = int(within_days) if within_days is not None else _due_soon_days()
	td = getdate(today())

	late: list[dict] = []
	due_today: list[dict] = []
	due_soon: list[dict] = []

	memberships = frappe.get_all(
		"Membership",
		filters={"status": ["in", CHASEABLE]},
		fields=["name", "member", "member_name", "membership_plan", "branch"],
	)
	for ms in memberships:
		try:
			rows = billing.open_obligations(ms.name)
		except Exception:
			# One broken membership must not blind the owner to every other debt.
			continue
		for row in rows:
			outstanding = flt(row.get("outstanding"))
			if outstanding <= 0:
				continue
			due = getdate(row.get("due_date")) if row.get("due_date") else None
			if not due:
				continue
			entry = {
				"membership": ms.name,
				"member": ms.member,
				"member_name": ms.member_name,
				"membership_plan": ms.membership_plan,
				"branch": ms.branch,
				"due_date": str(due),
				"amount": flt(row.get("amount")),
				"outstanding": outstanding,
				"sales_invoice": row.get("sales_invoice"),
				"part": row.get("idx"),
				"days_late": (td - due).days,
			}
			if due < td:
				late.append(entry)
			elif due == td:
				due_today.append(entry)
			elif (due - td).days <= horizon:
				due_soon.append(entry)

	late.sort(key=lambda r: (-r["days_late"], -r["outstanding"]))
	due_today.sort(key=lambda r: -r["outstanding"])
	due_soon.sort(key=lambda r: (r["due_date"], -r["outstanding"]))

	return {
		"within_days": horizon,
		"late": late,
		"due_today": due_today,
		"due_soon": due_soon,
		"total_late": round(sum(r["outstanding"] for r in late), 2),
		"total_due_today": round(sum(r["outstanding"] for r in due_today), 2),
		"total_due_soon": round(sum(r["outstanding"] for r in due_soon), 2),
	}


@frappe.whitelist()
def get_collections(within_days=None) -> dict:
	"""Owner/BFF: the collections list — who owes what, and how late."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	return get_dues(within_days)


def notify_dues():
	"""Daily scheduler hook: one in-app digest per owner/staff user, listing the
	money that is late or falls due today.

	Idempotent (one digest per user per day), opt-out via ``dues_reminders_enabled``,
	notify-only. Silent when there is nothing owed, so switching it on does not
	produce a daily message saying nothing is wrong.
	"""
	if not frappe.db.get_single_value("Business Settings", "dues_reminders_enabled"):
		return None

	data = get_dues()
	chase = data["late"] + data["due_today"]
	if not chase:
		return None

	owed = data["total_late"] + data["total_due_today"]
	subject = _("{0} payment(s) to collect — {1} outstanding").format(
		len(chase), frappe.utils.fmt_money(owed)
	)
	lines = []
	for r in chase[:20]:
		who = r["member_name"] or r["member"]
		when = _("{0} days late").format(r["days_late"]) if r["days_late"] > 0 else _("due today")
		lines.append(f"{who} — {frappe.utils.fmt_money(r['outstanding'])} ({when})")
	body = "<br>".join(lines)

	td = getdate(today())
	created = 0
	for user in _owner_users():
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
			}
		).insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()
	return created
