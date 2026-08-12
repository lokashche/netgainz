# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Enquiry → trial → member pipeline (Stage 9 OP-2).

Gyms live on walk-in follow-up, and until now the app had nothing before
"Member". An Enquiry is a person who asked — walk-in, Instagram, referral —
tracked through New → Contacted → Trial Scheduled → Joined / Lost with a
next-follow-up date. Three shapes:

* **Convert to Member is the only door to "Joined".** It creates the Member
  (prefilled from the enquiry, at the enquiry's branch), links it back, and
  stamps ``joined_on`` — so conversion counts can never disagree with the
  members that actually exist. A duplicate name is refused with a pointer to
  the existing member: at a gym desk that is almost always a returning member,
  and silently creating a second record (plus a colliding ERPNext Customer,
  which provisioning would try and fail on) helps nobody.
* **Follow-ups due** is the renewals read-model shape: computed on the fly,
  plus ONE idempotent in-app digest per user per day, opt-out via
  ``followup_reminders_enabled``. No email or SMS.
* **Lost requires a reason** (enforced on the doctype) and
  ``conversion_by_source`` turns the closed pipeline into "which channel
  actually sells" — the read Stage 10's reporting will consume.
"""

import frappe
from frappe.utils import getdate, today

from netgainz.net_gainz import permissions

OPEN_STATUSES = ("New", "Contacted", "Trial Scheduled")
CLOSED_STATUSES = ("Joined", "Lost")

# Member.source_of_reference is an older Select with its own vocabulary
# ("Walk-in", "Social Media", "Referral", "Google", "Other") — map the enquiry's
# channels onto it rather than widening a field the import already uses.
_MEMBER_SOURCE = {
	"Walk-in": "Walk-in",
	"Instagram": "Social Media",
	"Referral": "Referral",
	"Other": "Other",
}


# --------------------------------------------------------------------------- #
# conversion
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def convert_to_member(enquiry: str) -> dict:
	"""One tap at the desk: create the Member from the enquiry and link the two.

	Idempotent — converting an already-converted enquiry returns the existing
	member untouched. The new member inherits name, phone, email, source,
	referrer, program and branch; enrolment (plan, price, trial — DS-4) happens
	on the membership screen the desk lands on next.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	doc = frappe.get_doc("Enquiry", enquiry)
	if doc.member and frappe.db.exists("Member", doc.member):
		return {"enquiry": doc.name, "member": doc.member, "already_converted": True}

	existing = frappe.db.get_value("Member", {"full_name": doc.full_name}, "name")
	if existing:
		frappe.throw(
			f"A member named {doc.full_name} already exists ({existing}). "
			"If this is the same person re-joining, open that member instead of "
			"converting; otherwise adjust the enquiry's name to tell them apart."
		)

	member = frappe.get_doc(
		{
			"doctype": "Member",
			"full_name": doc.full_name,
			"phone": doc.phone,
			"email": doc.email,
			"status": "Active",
			"date_of_joining": today(),
			"source_of_reference": _MEMBER_SOURCE.get(doc.source, "Other"),
			"referred_by": doc.referred_by,
			"gym_program": doc.interested_program,
			"branch": doc.branch,
		}
	)
	member.insert()

	doc.member = member.name
	doc.status = "Joined"
	doc.joined_on = today()
	doc.save()

	return {
		"enquiry": doc.name,
		"member": member.name,
		"member_name": member.full_name,
		"already_converted": False,
	}


# --------------------------------------------------------------------------- #
# follow-ups (renewals pattern)
# --------------------------------------------------------------------------- #
def get_followups() -> dict:
	"""Open enquiries whose follow-up date has arrived: due today vs overdue."""
	td = getdate(today())
	due_today, overdue = [], []
	for e in frappe.get_all(
		"Enquiry",
		filters=[
			["status", "in", list(OPEN_STATUSES)],
			["next_follow_up", "is", "set"],
			["next_follow_up", "<=", str(td)],
		],
		fields=[
			"name",
			"full_name",
			"phone",
			"source",
			"interested_program",
			"status",
			"next_follow_up",
			"branch",
		],
		order_by="next_follow_up asc",
		limit_page_length=0,
	):
		row = {
			"enquiry": e.name,
			"full_name": e.full_name,
			"phone": e.phone,
			"source": e.source,
			"interested_program": e.interested_program,
			"status": e.status,
			"next_follow_up": str(e.next_follow_up),
			"days_overdue": (td - getdate(e.next_follow_up)).days,
			"branch": e.branch,
		}
		(due_today if row["days_overdue"] == 0 else overdue).append(row)

	return {
		"due_today": due_today,
		"overdue": overdue,
		"due_today_count": len(due_today),
		"overdue_count": len(overdue),
	}


@frappe.whitelist()
def get_followups_due() -> dict:
	"""Whitelisted read-model for the Enquiries page + dashboard card."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	return get_followups()


def notify_followups():
	"""Daily scheduler hook: ONE in-app notification per owner/staff user listing
	enquiry follow-ups that are due or overdue. Idempotent (one digest per user
	per day), opt-out via followup_reminders_enabled. No email/SMS is sent."""
	from netgainz.net_gainz.operations import renewals

	if not frappe.db.get_single_value("Business Settings", "followup_reminders_enabled"):
		return None

	data = get_followups()
	due = data["overdue"] + data["due_today"]
	if not due:
		return None

	td = getdate(today())
	subject = f"{len(due)} enquiry follow-up(s) due"
	body = "<br>".join(f"{r['full_name']} ({r['source']}) — {r['next_follow_up']}" for r in due[:20])

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
				"document_type": "Enquiry",
			}
		).insert(ignore_permissions=True)
		created += 1

	frappe.logger("netgainz").info(f"Follow-up reminder: {len(due)} due, notified {created} user(s)")
	return {"due": len(due), "notified": created}


# --------------------------------------------------------------------------- #
# conversion by source (feeds Stage 10)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def conversion_by_source() -> dict:
	"""Per source: how many asked, how many joined, how many were lost (and why
	it matters: this is the gym's marketing report, from data the desk already
	keys in). Conversion % is joined / closed — open enquiries are still in play
	and should not drag the rate down."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	rows = frappe.get_all("Enquiry", fields=["source", "status", "count(*) as n"], group_by="source, status")
	by_source = {}
	for r in rows:
		s = by_source.setdefault(
			r.source or "Other",
			{"source": r.source or "Other", "total": 0, "joined": 0, "lost": 0, "open": 0},
		)
		s["total"] += r.n
		if r.status == "Joined":
			s["joined"] += r.n
		elif r.status == "Lost":
			s["lost"] += r.n
		else:
			s["open"] += r.n

	for s in by_source.values():
		closed = s["joined"] + s["lost"]
		s["conversion_pct"] = round(100 * s["joined"] / closed, 1) if closed else None

	sources = sorted(by_source.values(), key=lambda s: -s["total"])
	return {"sources": sources, "total": sum(s["total"] for s in sources)}
