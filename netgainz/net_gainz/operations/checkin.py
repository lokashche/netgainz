# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Gym-wide check-in & attendance (Stage 9 OP-1).

The front desk taps a member in as they walk through the door; the app watches
"last visit" per active member and raises a churn-risk list before an absence
becomes a cancellation. Three deliberate shapes (traced in STAGE-9-START-HERE.md):

* A **visit** is a floor check-in *or* an attended class — the absence read-model
  takes the latest of the two, so a member who only does classes never reads as
  absent. The two records themselves stay separate and honest.
* The membership guard is a **soft prompt only** (D3: never freeze at the door).
  It reads the stored ``Membership.status`` plus a read-time overlay — no
  scheduler re-derives status daily, so a due date that passed since the last
  billing event still prompts.
* Absence is only measured from the day the gym started recording visits (the
  earliest visit on record). Before that there is nothing to measure — switching
  the feature on does not flag 40 long-imported members on day one. A member
  with no visit of their own (``never_visited``) is measured from that start,
  or their creation date if they joined later.

Like renewals, this module is read-only and notify-only apart from writing the
check-in row itself: it never charges, blocks, or messages a member.
"""

import frappe
from frappe.utils import add_days, get_datetime, getdate, today

from netgainz.net_gainz import permissions

DEFAULT_ABSENCE_DAYS = 14

# Membership statuses that still owe money and can therefore be past due. Trial
# is deliberately absent (nothing has been sold yet); Paid / Written Off owe
# nothing.
_OWING_STATUSES = ("Overdue", "Pending", "Partial")


def _absence_days() -> int:
	raw = frappe.db.get_single_value("Business Settings", "absence_alert_days")
	try:
		days = int(raw)
	except (TypeError, ValueError):
		days = DEFAULT_ABSENCE_DAYS
	return days if days > 0 else DEFAULT_ABSENCE_DAYS


# --------------------------------------------------------------------------- #
# the desk
# --------------------------------------------------------------------------- #
def membership_alert(member: str) -> dict | None:
	"""The soft-prompt payload for the desk, or ``None`` when all is well.

	Reads the stored membership status **plus a read-time due-date overlay**:
	nothing recomputes ``Membership.status`` at midnight, so a membership still
	marked Pending/Partial whose due date has passed must prompt too. Pure read —
	the stored status is never touched here.
	"""
	frozen = frappe.db.get_value("Member", member, "status") == "Frozen"

	td = getdate(today())
	overdue_rows = []
	for row in frappe.get_all(
		"Membership",
		filters={"member": member, "status": ["in", list(_OWING_STATUSES)]},
		fields=["name", "status", "balance_due", "due_date"],
	):
		if row.status == "Overdue" or (row.due_date and getdate(row.due_date) < td):
			overdue_rows.append(row)

	if not overdue_rows and not frozen:
		return None

	due_dates = [getdate(r.due_date) for r in overdue_rows if r.due_date]
	return {
		"overdue": bool(overdue_rows),
		"frozen": frozen,
		"balance_due": sum(r.balance_due or 0 for r in overdue_rows),
		"due_date": str(min(due_dates)) if due_dates else None,
		"memberships": [r.name for r in overdue_rows],
	}


@frappe.whitelist()
def record_check_in(member: str, source: str = "Front Desk", notes: str | None = None) -> dict:
	"""One desk tap: record the visit, return the row + the soft-prompt payload.

	A repeat check-in the same day is allowed (a member can leave and return) —
	``previous_today`` carries the earlier stamp so the desk can say
	"already checked in at HH:MM" instead of blocking.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	previous_today = frappe.db.get_value(
		"Member Check-in",
		{"member": member, "timestamp": [">=", today()]},
		"timestamp",
		order_by="timestamp desc",
	)

	doc = frappe.get_doc({"doctype": "Member Check-in", "member": member, "source": source, "notes": notes})
	doc.insert()

	return {
		"check_in": doc.name,
		"member": doc.member,
		"member_name": doc.member_name,
		"timestamp": str(doc.timestamp),
		"branch": doc.branch,
		"previous_today": str(previous_today) if previous_today else None,
		"alert": membership_alert(member),
	}


@frappe.whitelist()
def find_members(q: str) -> list[dict]:
	"""Desk search: one query over member code / name / phone (the owner-app's
	generic member search is name-only), annotated with today's check-in so the
	desk sees at a glance who is already in."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	q = (q or "").strip()
	if not q:
		return []
	like = f"%{q}%"
	rows = frappe.get_all(
		"Member",
		or_filters=[
			["name", "like", like],
			["member_code", "like", like],
			["full_name", "like", like],
			["phone", "like", like],
		],
		fields=["name", "member_code", "full_name", "phone", "status", "branch"],
		order_by="full_name asc",
		limit_page_length=8,
	)

	checked_in = {}
	if rows:
		for c in frappe.get_all(
			"Member Check-in",
			filters={
				"member": ["in", [r.name for r in rows]],
				"timestamp": [">=", today()],
			},
			fields=["member", "timestamp"],
			order_by="timestamp asc",
		):
			checked_in[c.member] = str(c.timestamp)

	for r in rows:
		r["checked_in_today"] = checked_in.get(r.name)
	return rows


@frappe.whitelist()
def todays_visits() -> dict:
	"""The desk's own list: floor check-ins recorded today, newest first.

	Class attendance is deliberately not mixed in — class rosters have their own
	screen; this list is what the desk itself has done."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	rows = frappe.get_all(
		"Member Check-in",
		filters={"timestamp": [">=", today()]},
		fields=["name", "member", "member_name", "timestamp", "source", "branch"],
		order_by="timestamp desc",
		limit_page_length=0,
	)
	for r in rows:
		r["timestamp"] = str(r.timestamp)
	return {"visits": rows, "count": len(rows)}


# --------------------------------------------------------------------------- #
# the absence / churn-risk read-model (renewals pattern)
# --------------------------------------------------------------------------- #
def _last_visits() -> dict:
	"""member -> latest visit datetime, unioned across floor check-ins and
	attended classes."""
	last = {}
	for row in frappe.get_all(
		"Member Check-in",
		fields=["member", "max(timestamp) as last_visit"],
		group_by="member",
	):
		if row.last_visit:
			last[row.member] = get_datetime(row.last_visit)
	for row in frappe.get_all(
		"Session Booking",
		filters={"status": "Attended", "check_in_time": ["is", "set"]},
		fields=["member", "max(check_in_time) as last_visit"],
		group_by="member",
	):
		if row.last_visit:
			seen = get_datetime(row.last_visit)
			if row.member not in last or seen > last[row.member]:
				last[row.member] = seen
	return last


def _tracking_started():
	"""The day attendance recording began: the earliest visit on record, of
	either kind. ``None`` until the first visit is ever recorded."""
	firsts = []
	rows = frappe.get_all("Member Check-in", fields=["min(timestamp) as first"])
	if rows and rows[0].first:
		firsts.append(get_datetime(rows[0].first))
	rows = frappe.get_all(
		"Session Booking",
		filters={"status": "Attended", "check_in_time": ["is", "set"]},
		fields=["min(check_in_time) as first"],
	)
	if rows and rows[0].first:
		firsts.append(get_datetime(rows[0].first))
	return min(firsts) if firsts else None


def get_absences(threshold_days=None) -> dict:
	"""Active members not seen at the gym within the absence window.

	Absence only exists once the gym is recording visits, so everyone is measured
	from the earliest visit on record at the earliest — a pilot whose members were
	imported weeks ago is NOT flagged wholesale the day the feature ships, and
	before the first ever visit the list is simply empty. A member with no visit
	of their own is flagged ``never_visited`` and measured from that start (or
	their creation date, if they joined later).
	"""
	threshold = int(threshold_days) if threshold_days else _absence_days()
	td = getdate(today())
	cutoff = add_days(td, -threshold)

	last_visits = _last_visits()
	tracking_start = _tracking_started()
	if tracking_start is None:
		return {
			"threshold_days": threshold,
			"absent": [],
			"absent_count": 0,
			"tracking_started": None,
		}

	absent = []
	for m in frappe.get_all(
		"Member",
		filters={"status": "Active"},
		fields=["name", "full_name", "phone", "branch", "creation"],
		limit_page_length=0,
	):
		seen = last_visits.get(m.name)
		never_visited = seen is None
		since = getdate(seen) if seen else max(getdate(m.creation), getdate(tracking_start))
		if since >= getdate(cutoff):
			continue
		absent.append(
			{
				"member": m.name,
				"member_name": m.full_name,
				"phone": m.phone,
				"branch": m.branch,
				"last_visit": str(getdate(seen)) if seen else None,
				"never_visited": never_visited,
				"days_absent": (td - since).days,
			}
		)

	absent.sort(key=lambda r: r["days_absent"], reverse=True)
	return {
		"threshold_days": threshold,
		"absent": absent,
		"absent_count": len(absent),
		"tracking_started": str(getdate(tracking_start)),
	}


@frappe.whitelist()
def get_churn_risk(threshold_days=None) -> dict:
	"""Whitelisted read-model for the churn-risk list + dashboard card."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	return get_absences(threshold_days)


def notify_absences():
	"""Daily scheduler hook: raise ONE in-app notification per owner/staff user
	listing active members past the absence window. Idempotent (one digest per
	user per day), opt-out via absence_alerts_enabled. No email/SMS is sent."""
	from netgainz.net_gainz.operations import renewals

	if not frappe.db.get_single_value("Business Settings", "absence_alerts_enabled"):
		return None

	data = get_absences()
	absent = data["absent"]
	if not absent:
		return None

	td = getdate(today())
	subject = f"{len(absent)} member(s) not seen in {data['threshold_days']}+ days"
	body = "<br>".join(
		f"{r['member_name'] or r['member']} — "
		+ (f"last visit {r['last_visit']}" if r["last_visit"] else "no visit recorded")
		for r in absent[:20]
	)

	created = 0
	for user in renewals._owner_users():
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
				"document_type": "Member",
			}
		).insert(ignore_permissions=True)
		created += 1

	frappe.logger("netgainz").info(f"Absence alert: {len(absent)} absent, notified {created} user(s)")
	return {"absent": len(absent), "notified": created}
