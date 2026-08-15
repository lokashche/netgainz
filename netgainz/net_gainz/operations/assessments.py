# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Fitness assessments & progress (Stage 9 OP-5).

The gym measures a member, and then keeps measuring them. This module records
those visits and turns the readings into the one thing a member actually renews
for: visible proof they are getting better.

Three shapes worth knowing before reading the code:

* **Every reading is a measurement row.** Height, weight and BMI are typed into
  their own fields on the assessment for the coach's convenience and mirrored
  into the same child table as everything else, so progress, targets and the
  reminder all walk ONE path. Body composition is not a special case.
* **Progress is counted, never stored.** "Is this member on track?" is derived
  from their readings each time it is asked — the OP-4 lesson (a balance you
  increment drifts; a balance you count cannot). Only the target's *baseline* is
  frozen, because that is a fact about the day the target was agreed.
* **A metric knows which way is better.** A sprint time falling and a jump height
  rising are both improvement; ``direction`` on Assessment Metric is what lets
  one piece of arithmetic serve both without a table of special cases.

Like every other OP module this one is read-only and notify-only apart from the
records it writes: it never charges, blocks, or messages a member.
"""

import frappe
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.doctype.member_metric_target.member_metric_target import target_direction
from netgainz.net_gainz.operations import renewals

DEFAULT_DUE_SOON_DAYS = 7

# The starter library a gym gets on install. Deliberately small and universal —
# a sports centre adds its own sport tests, a weights gym switches the
# performance rows off. Nothing here is hardcoded anywhere else in the app.
SEED_METRICS = [
	# (name, unit, direction, group, applies_to, how to measure)
	("Height", "cm", "Higher is better", "Body Composition", "Everyone", ""),
	("Weight", "kg", "Lower is better", "Body Composition", "Everyone", ""),
	("BMI", "kg/m2", "Lower is better", "Body Composition", "Everyone", ""),
	(
		"Body Fat %",
		"%",
		"Lower is better",
		"Body Composition",
		"Everyone",
		"From the calliper or BIA reading — enter the figure the device gives.",
	),
	(
		"Waist",
		"cm",
		"Lower is better",
		"Body Composition",
		"General",
		"At the navel, relaxed, after breathing out.",
	),
	("Chest", "cm", "Higher is better", "Body Composition", "General", "At nipple line, arms relaxed."),
	("Arm (relaxed)", "cm", "Higher is better", "Body Composition", "General", "Mid-bicep, arm hanging."),
	(
		"Resting Heart Rate",
		"bpm",
		"Lower is better",
		"Body Composition",
		"Everyone",
		"Seated, after five minutes' rest.",
	),
	(
		"20m Sprint",
		"sec",
		"Lower is better",
		"Performance",
		"Sport",
		"Best of three from a standing start, full recovery between runs.",
	),
	(
		"Vertical Jump",
		"cm",
		"Higher is better",
		"Performance",
		"Sport",
		"Best of three; subtract standing reach.",
	),
	(
		"Agility 5-10-5",
		"sec",
		"Lower is better",
		"Performance",
		"Sport",
		"Pro-agility shuttle, best of two, one each side.",
	),
	(
		"Plank Hold",
		"sec",
		"Higher is better",
		"Performance",
		"Everyone",
		"To form breakdown, not to failure.",
	),
	(
		"Push-ups",
		"reps",
		"Higher is better",
		"Performance",
		"Everyone",
		"Maximum in one set with clean form.",
	),
	(
		"Sit and Reach",
		"cm",
		"Higher is better",
		"Performance",
		"Everyone",
		"Best of three, no bouncing.",
	),
	(
		"Beep Test Level",
		"level",
		"Higher is better",
		"Performance",
		"Sport",
		"20m multistage shuttle; record level.shuttle as a decimal.",
	),
]


def _due_soon_days() -> int:
	raw = frappe.db.get_single_value("Business Settings", "assessment_due_soon_days")
	try:
		days = int(raw)
	except (TypeError, ValueError):
		days = DEFAULT_DUE_SOON_DAYS
	return days if days > 0 else DEFAULT_DUE_SOON_DAYS


# --------------------------------------------------------------------------- #
# the metric library
# --------------------------------------------------------------------------- #
def seed_default_metrics() -> dict:
	"""Install the starter metric library. Idempotent — never touches a metric
	the gym already has, so a tenant's own edits and retirements survive."""
	created = 0
	for name, unit, direction, group, applies_to, how in SEED_METRICS:
		if frappe.db.exists("Assessment Metric", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Assessment Metric",
				"metric_name": name,
				"unit": unit,
				"direction": direction,
				"metric_group": group,
				"applies_to": applies_to,
				"description": how,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
		created += 1
	return {"created": created, "total": len(SEED_METRICS)}


def after_install():
	"""``after_install`` hook — a fresh gym starts with something to measure."""
	seed_default_metrics()


@frappe.whitelist()
def get_metrics(member: str | None = None, include_inactive: int = 0) -> list[dict]:
	"""The metrics offered on an assessment form.

	Passing a member narrows the list to their category — a Sport member sees the
	performance battery, a General member the body-composition check, everyone
	sees the ``Everyone`` metrics. Built-ins are excluded: they have their own
	fields on the form.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	filters = {"is_builtin": 0}
	if not int(include_inactive or 0):
		filters["is_active"] = 1

	rows = frappe.get_all(
		"Assessment Metric",
		filters=filters,
		fields=["name", "unit", "direction", "metric_group", "applies_to", "description", "is_active"],
		order_by="metric_group asc, name asc",
		limit_page_length=0,
	)

	if member:
		category = frappe.db.get_value("Member", member, "category")
		if category:
			rows = [r for r in rows if r.applies_to in ("Everyone", category)]

	return rows


# --------------------------------------------------------------------------- #
# recording a visit
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def record_assessment(
	member: str,
	assessment_date: str | None = None,
	height_cm: float | None = None,
	weight_kg: float | None = None,
	measurements: list | str | None = None,
	notes: str | None = None,
	coach: str | None = None,
	next_due_date: str | None = None,
) -> dict:
	"""File one assessment and hand back the member's fresh progress.

	``measurements`` is a list of ``{"metric": ..., "value": ..., "note": ...}``
	(JSON is accepted, since this is called from the owner app). Height, weight
	and BMI are handled by the doctype — do not pass them as rows.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	rows = frappe.parse_json(measurements) if isinstance(measurements, str) else (measurements or [])

	doc = frappe.get_doc(
		{
			"doctype": "Fitness Assessment",
			"member": member,
			"assessment_date": assessment_date or today(),
			"height_cm": flt(height_cm) or None,
			"weight_kg": flt(weight_kg) or None,
			"notes": notes,
			"coach": coach,
			"next_due_date": next_due_date,
			"measurements": [
				{"metric": r.get("metric"), "value": flt(r.get("value")), "note": r.get("note")}
				for r in rows
				if r.get("metric") and r.get("value") not in (None, "")
			],
		}
	)
	doc.insert()

	return {
		"assessment": doc.name,
		"member": doc.member,
		"member_name": doc.member_name,
		"assessment_date": str(doc.assessment_date),
		"bmi": doc.bmi,
		"age_years": doc.age_years,
		"next_due_date": str(doc.next_due_date) if doc.next_due_date else None,
		"branch": doc.branch,
		"progress": get_progress(member),
	}


# --------------------------------------------------------------------------- #
# progress
# --------------------------------------------------------------------------- #
def _readings(member: str) -> list[frappe._dict]:
	"""Every reading this member has, oldest first, with the date it was taken.

	Two queries rather than a join: the readings live in the assessment's child
	table, so the visits are read first (they carry the date and the order) and
	the rows are hung off them. A member has dozens of readings, not thousands.
	"""
	visits = frappe.get_all(
		"Fitness Assessment",
		filters={"member": member},
		fields=["name", "assessment_date"],
		order_by="assessment_date asc, creation asc",
		limit_page_length=0,
	)
	if not visits:
		return []

	when = {v.name: v.assessment_date for v in visits}
	sequence = {v.name: i for i, v in enumerate(visits)}

	rows = frappe.get_all(
		"Fitness Assessment Measurement",
		filters={"parent": ["in", list(when)], "parenttype": "Fitness Assessment"},
		fields=["metric", "value", "unit", "note", "parent"],
		limit_page_length=0,
	)
	readings = [
		frappe._dict(
			{
				"metric": r.metric,
				"value": r.value,
				"unit": r.unit,
				"note": r.note,
				"assessment": r.parent,
				"date": when[r.parent],
			}
		)
		for r in rows
	]
	readings.sort(key=lambda r: sequence[r.assessment])
	return readings


def _improvement(direction: str, earlier: float, later: float) -> float:
	"""How much better the member got, signed so positive is always better."""
	delta = flt(later) - flt(earlier)
	return -delta if direction == "Lower is better" else delta


def _percent_to_target(direction: str, baseline, current, target) -> float | None:
	"""How far along the road from the starting point to the target, 0-100.

	Measured against the distance actually travelled in the right direction, so
	it reads the same whether the number is climbing or falling. Returns None
	when there is no starting point to measure from, and clamps at 100 once
	reached — a member who overshoots is at their target, not at 140% of it.
	"""
	if baseline is None or target in (None, "") or current in (None, ""):
		return None
	span = _improvement(direction, flt(baseline), flt(target))
	if span <= 0:
		# The target was already met, or held, when it was agreed — there is no
		# road to travel. It reads as reached only while the member is STILL at
		# or better than the number; drifting off it must show, not sit at 100.
		return 100.0 if _improvement(direction, flt(target), flt(current)) >= 0 else 0.0
	travelled = _improvement(direction, flt(baseline), flt(current))
	return max(0.0, min(100.0, round(travelled / span * 100.0, 1)))


@frappe.whitelist()
def get_progress(member: str) -> dict:
	"""One member's whole assessment history, shaped as a series per metric.

	Each series carries the readings in order plus the three numbers a coach
	actually says out loud: where they are now, what changed since last time, and
	what changed since the very first reading. An active target adds where they
	are heading and how far along they are.
	"""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	rows = _readings(member)

	metric_names = sorted({r.metric for r in rows})
	targets = {
		t.metric: t
		for t in frappe.get_all(
			"Member Metric Target",
			filters={"member": member, "is_active": 1},
			fields=["name", "metric", "target_value", "target_date", "baseline_value", "baseline_date"],
			limit_page_length=0,
		)
	}
	metric_names = sorted(set(metric_names) | set(targets))

	meta = {}
	if metric_names:
		for m in frappe.get_all(
			"Assessment Metric",
			filters={"name": ["in", metric_names]},
			fields=["name", "unit", "direction", "metric_group", "is_builtin"],
			limit_page_length=0,
		):
			meta[m.name] = m

	series = []
	for metric in metric_names:
		points = [r for r in rows if r.metric == metric]
		info = meta.get(metric) or frappe._dict(
			{
				"unit": points[0].unit if points else "",
				"direction": "Higher is better",
				"metric_group": "Other",
			}
		)
		direction = info.direction or "Higher is better"
		target = targets.get(metric)

		current = points[-1].value if points else None
		first = points[0].value if points else None
		previous = points[-2].value if len(points) > 1 else None

		baseline = None
		if target:
			baseline = target.baseline_value if target.baseline_date else first
			# Which way THIS member is travelling beats the metric's default: a
			# member whose goal is Weight Gain is improving as the number climbs,
			# even though Weight reads "Lower is better" for the gym at large.
			direction = target_direction(baseline, target.target_value) or direction

		series.append(
			{
				"metric": metric,
				"unit": info.unit,
				"direction": direction,
				"group": info.metric_group,
				"is_builtin": int(info.get("is_builtin") or 0),
				"readings": [
					{
						"date": str(getdate(p.date)),
						"value": p.value,
						"assessment": p.assessment,
						"note": p.note,
					}
					for p in points
				],
				"count": len(points),
				"current": current,
				"current_date": str(getdate(points[-1].date)) if points else None,
				"change_since_last": _improvement(direction, previous, current)
				if previous is not None
				else None,
				"change_since_first": _improvement(direction, first, current) if len(points) > 1 else None,
				"target": target.target_value if target else None,
				"target_date": str(target.target_date) if target and target.target_date else None,
				"target_name": target.name if target else None,
				# Where the member started. A target agreed AFTER a reading froze its
				# baseline that day (a fact about the agreement); one agreed before
				# the member was ever measured has none — those measure from the
				# earliest reading instead, derived here so it stays right however
				# the assessments were filed. `baseline_date` is the honest flag:
				# `baseline_value` is a Float column and reads back as 0.0 when it
				# was never stamped, which would make every falling metric read
				# "100% there" at any weight.
				"baseline": baseline,
				"percent_to_target": _percent_to_target(direction, baseline, current, target.target_value)
				if target
				else None,
			}
		)

	# Body composition first — it is what most members ask about — then
	# performance, then anything the gym invented.
	order = {"Body Composition": 0, "Performance": 1, "Other": 2}
	series.sort(key=lambda s: (order.get(s["group"], 9), s["metric"]))

	visits = frappe.get_all(
		"Fitness Assessment",
		filters={"member": member},
		fields=["name", "assessment_date", "coach", "bmi", "age_years", "notes", "next_due_date"],
		order_by="assessment_date desc, creation desc",
		limit_page_length=0,
	)

	member_row = (
		frappe.db.get_value("Member", member, ["full_name", "sport_goal", "category", "coach"], as_dict=True)
		or {}
	)

	return {
		"member": member,
		"member_name": member_row.get("full_name"),
		"sport_goal": member_row.get("sport_goal"),
		"category": member_row.get("category"),
		"coach": member_row.get("coach"),
		"assessment_count": len(visits),
		"first_assessment": str(visits[-1].assessment_date) if visits else None,
		"last_assessment": str(visits[0].assessment_date) if visits else None,
		"next_due_date": str(visits[0].next_due_date) if visits and visits[0].next_due_date else None,
		"series": series,
		"visits": [
			{
				"assessment": v.name,
				"date": str(getdate(v.assessment_date)),
				"coach": v.coach,
				"bmi": v.bmi,
				"age_years": v.age_years,
				"notes": v.notes,
			}
			for v in visits
		],
	}


# --------------------------------------------------------------------------- #
# targets
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def set_target(
	member: str,
	metric: str,
	target_value: float,
	target_date: str | None = None,
	notes: str | None = None,
) -> dict:
	"""Agree a number with the member. Re-setting an existing target edits it in
	place, keeping the original starting point so the progress bar does not reset
	every time the coach adjusts the goal."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	name = frappe.db.get_value(
		"Member Metric Target", {"member": member, "metric": metric, "is_active": 1}, "name"
	)
	if name:
		doc = frappe.get_doc("Member Metric Target", name)
		doc.target_value = flt(target_value)
		doc.target_date = target_date
		doc.notes = notes
		doc.save()
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Member Metric Target",
				"member": member,
				"metric": metric,
				"target_value": flt(target_value),
				"target_date": target_date,
				"notes": notes,
			}
		)
		doc.insert()

	return {
		"target": doc.name,
		"member": doc.member,
		"metric": doc.metric,
		"target_value": doc.target_value,
		# None, not the Float column's 0.0, when the member has never been
		# measured for this metric yet.
		"baseline_value": doc.baseline_value if doc.baseline_date else None,
		"baseline_date": str(doc.baseline_date) if doc.baseline_date else None,
		"branch": doc.branch,
	}


@frappe.whitelist()
def clear_target(target: str) -> dict:
	"""Retire a target without deleting the history behind it."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	doc = frappe.get_doc("Member Metric Target", target)
	doc.is_active = 0
	doc.save()
	return {"target": doc.name, "is_active": 0}


# --------------------------------------------------------------------------- #
# who is due
# --------------------------------------------------------------------------- #
def get_due(within_days=None) -> dict:
	"""Active members whose re-assessment is due soon or already overdue.

	Only each member's LATEST assessment counts, so a member re-measured
	yesterday never lingers on the overdue list because of an older visit. A
	member who has never been assessed is not chased here — there is no due date
	to miss; they appear in ``never_assessed`` so the gym can start them.
	"""
	within = int(within_days) if within_days else _due_soon_days()
	td = getdate(today())
	horizon = add_days(td, within)

	actives = frappe.get_all(
		"Member",
		filters={"status": "Active"},
		fields=["name", "full_name", "phone", "coach", "category", "sport_goal", "branch"],
		limit_page_length=0,
	)
	if not actives:
		return {
			"within_days": within,
			"due_soon": [],
			"overdue": [],
			"never_assessed": [],
			"due_soon_count": 0,
			"overdue_count": 0,
			"never_assessed_count": 0,
		}

	latest = {}
	for row in frappe.get_all(
		"Fitness Assessment",
		filters={"member": ["in", [m.name for m in actives]]},
		fields=["name", "member", "assessment_date", "next_due_date"],
		order_by="assessment_date asc, creation asc",
		limit_page_length=0,
	):
		# Ordered oldest-first, so the last write per member is their latest.
		latest[row.member] = row

	due_soon, overdue, never = [], [], []
	for m in actives:
		last = latest.get(m.name)
		if not last:
			never.append(
				{
					"member": m.name,
					"member_name": m.full_name,
					"phone": m.phone,
					"coach": m.coach,
					"category": m.category,
					"sport_goal": m.sport_goal,
					"branch": m.branch,
				}
			)
			continue
		if not last.next_due_date:
			continue
		due = getdate(last.next_due_date)
		row = {
			"member": m.name,
			"member_name": m.full_name,
			"phone": m.phone,
			"coach": m.coach,
			"category": m.category,
			"sport_goal": m.sport_goal,
			"branch": m.branch,
			"last_assessment": str(getdate(last.assessment_date)),
			"assessment": last.name,
			"next_due_date": str(due),
			"days_until": (due - td).days,
		}
		if due < td:
			overdue.append(row)
		elif due <= horizon:
			due_soon.append(row)

	due_soon.sort(key=lambda r: r["next_due_date"])
	overdue.sort(key=lambda r: r["next_due_date"])
	never.sort(key=lambda r: (r["member_name"] or ""))

	return {
		"within_days": within,
		"due_soon": due_soon,
		"overdue": overdue,
		"never_assessed": never,
		"due_soon_count": len(due_soon),
		"overdue_count": len(overdue),
		"never_assessed_count": len(never),
	}


@frappe.whitelist()
def get_assessments_due(within_days=None) -> dict:
	"""Whitelisted read-model for the Assessments page + dashboard card."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	return get_due(within_days)


def notify_assessments_due():
	"""Daily scheduler hook: ONE in-app notification per owner/staff user listing
	members due for re-assessment. Idempotent (one digest per user per day),
	opt-out via assessment_reminders_enabled. No email or SMS is sent."""
	if not frappe.db.get_single_value("Business Settings", "assessment_reminders_enabled"):
		return None

	data = get_due()
	chase = data["overdue"] + data["due_soon"]
	if not chase:
		return None

	td = getdate(today())
	subject = f"{len(chase)} member(s) due for re-assessment"
	body = "<br>".join(
		f"{r['member_name'] or r['member']} — due {r['next_due_date']}"
		+ (" (overdue)" if r["days_until"] < 0 else "")
		for r in chase[:20]
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
				"document_type": "Fitness Assessment",
			}
		).insert(ignore_permissions=True)
		created += 1

	frappe.logger("netgainz").info(f"Assessment reminder: {len(chase)} due, notified {created} user(s)")
	return {"due": len(chase), "notified": created}
