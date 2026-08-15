# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 9 demo data — the operations features the original seeder predates.

``demo/gym.py`` seeds the money: members, memberships, invoices, payments, expenses,
Profit First. It was written before Stage 9, so a demo of it shows empty screens for
check-in, enquiries, packs, day passes and assessments — which are exactly the screens
a gym owner recognises as their day.

This tops those up, on the members the seeder already made, through the same whitelisted
paths the product uses. Nothing here paints a fixture: a check-in is a real check-in, a
pack sale raises a real invoice and payment.

    bench --site <site> console
    >>> from netgainz.net_gainz.demo import stage9; stage9.seed()

Idempotent: everything is keyed, so a re-run tops up rather than duplicating.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, today

from netgainz.net_gainz.operations import assessments, checkin, enquiries, packs

MEMBER_PREFIX = "IF"


def _members(limit=None):
	rows = frappe.get_all(
		"Member",
		filters={"name": ["like", f"{MEMBER_PREFIX}%"], "status": "Active"},
		fields=["name", "full_name"],
		order_by="name",
	)
	return rows[:limit] if limit else rows


# --------------------------------------------------------------------------- #
# OP-1 — a gym floor with a fortnight of traffic behind it
# --------------------------------------------------------------------------- #
def _check_ins(days_back=21):
	"""Visits spread over three weeks, so the churn-risk list has something to say.

	Deliberately uneven: regulars most days, a middle group tailing off, and a few who
	stopped coming a fortnight ago -- that last group is what makes the Churn Risk
	screen worth looking at.
	"""
	members = _members()
	if not members:
		return 0

	made = 0
	regulars = members[: max(1, len(members) // 2)]
	fading = members[len(members) // 2 : max(len(members) // 2 + 1, int(len(members) * 0.8))]
	lapsed = members[int(len(members) * 0.8) :]

	def visit(member, days_ago, hour):
		stamp = add_to_date(now_datetime(), days=-days_ago).replace(hour=hour, minute=15, second=0)
		if frappe.db.exists(
			"Member Check-in", {"member": member, "timestamp": ["between", [
				stamp.replace(hour=0, minute=0), stamp.replace(hour=23, minute=59)]]}
		):
			return 0
		doc = frappe.new_doc("Member Check-in")
		doc.member = member
		doc.source = "Manual"  # Manual is the only source allowed to backdate
		doc.insert(ignore_permissions=True)
		# Timestamp is stamped server-side on insert, so backdate it afterwards.
		doc.db_set("timestamp", stamp, update_modified=False)
		return 1

	for i, m in enumerate(regulars):
		for d in range(0, days_back, 2):
			made += visit(m.name, d, 7 + (i % 3))
	for i, m in enumerate(fading):
		for d in range(7, days_back, 3):
			made += visit(m.name, d, 18 + (i % 2))
	for i, m in enumerate(lapsed):
		for d in range(16, days_back, 2):
			made += visit(m.name, d, 8)
	return made


# --------------------------------------------------------------------------- #
# OP-2 — a sales pipeline mid-flow
# --------------------------------------------------------------------------- #
ENQUIRIES = [
	("Sneha Kulkarni", "+919845010101", "Instagram", "Yoga", "New", 0),
	("Rahul Bhatt", "+919845010102", "Walk-in", "Strength Training", "Contacted", -2),
	("Fatima Sheikh", "+919845010103", "Referral", "Personal Training", "Trial Scheduled", 1),
	("Joseph Mathew", "+919845010104", "Walk-in", "CrossFit", "Contacted", -5),
	("Ananya Rao", "+919845010105", "Instagram", "Zumba", "New", 2),
	("Kiran Desai", "+919845010106", "Other", "Strength Training", "Lost", -9),
]


def _enquiries():
	made = 0
	for name, phone, source, program, status, follow_in in ENQUIRIES:
		if frappe.db.exists("Enquiry", {"full_name": name}):
			continue
		doc = frappe.new_doc("Enquiry")
		doc.full_name = name
		doc.phone = phone
		doc.source = source
		if frappe.db.exists("Program", program):
			doc.interested_program = program
		doc.status = status
		doc.next_follow_up = add_days(today(), follow_in)
		if status == "Lost":
			doc.lost_reason = "Chose a gym closer to home"
		doc.insert(ignore_permissions=True)
		made += 1
	return made


# --------------------------------------------------------------------------- #
# OP-4 — packs sold and partly burnt down, plus a couple of walk-ins
# --------------------------------------------------------------------------- #
PACKS = [
	{"pack_name": "PT 10-Pack", "sessions": 10, "validity_days": 90, "price": 8000},
	{"pack_name": "PT 5-Pack", "sessions": 5, "validity_days": 60, "price": 4500},
]


def _packs():
	from netgainz.net_gainz.accounting import provisioning

	made = {"products": 0, "sold": 0, "used": 0, "day_passes": 0}
	for spec in PACKS:
		if frappe.db.exists("Session Pack", spec["pack_name"]):
			continue
		doc = frappe.new_doc("Session Pack")
		doc.pack_name = spec["pack_name"]
		doc.sessions = spec["sessions"]
		doc.validity_days = spec["validity_days"]
		doc.price = spec["price"]
		doc.is_active = 1
		doc.insert(ignore_permissions=True)
		made["products"] += 1

	buyers = _members(4)
	for i, m in enumerate(buyers):
		if frappe.db.exists("Pack Purchase", {"member": m.name}):
			continue
		spec = PACKS[i % len(PACKS)]
		try:
			res = packs.sell_pack(member=m.name, session_pack=spec["pack_name"], payment_mode="Cash")
			made["sold"] += 1
			purchase = res.get("pack_purchase") if isinstance(res, dict) else res
			# Burn a few sessions so the balances screen shows movement, not just sales.
			for _ in range(i + 1):
				try:
					packs.use_session(pack_purchase=purchase)
					made["used"] += 1
				except Exception:
					break
		except Exception as exc:
			print(f"    pack sale skipped for {m.name}: {str(exc)[:80]}")

	for who, phone in (("Ramesh Gupta", "+919845020201"), ("Leela Krishnan", "+919845020202")):
		if frappe.db.exists("Day Pass", {"guest_name": who}):
			continue
		try:
			packs.sell_day_pass(guest_name=who, phone=phone, amount=400, payment_mode="Cash")
			made["day_passes"] += 1
		except Exception as exc:
			print(f"    day pass skipped for {who}: {str(exc)[:80]}")
	return made


# --------------------------------------------------------------------------- #
# OP-5 — measured members, with progress to show
# --------------------------------------------------------------------------- #
def _assessments():
	"""Two visits each, three months apart, so the progress view has a direction.

	Weight comes down and the lifts go up, because a demo of a progress screen with a
	single reading on it shows nothing at all.
	"""
	assessments.seed_default_metrics()
	members = _members(6)
	made = {"assessments": 0, "targets": 0}

	# Pick whatever the gym's library actually holds rather than guessing names --
	# the library is the tenant's to edit, so hardcoding "Back Squat 1RM" would give a
	# blank progress screen on any gym that renamed it.
	library = frappe.get_all(
		"Assessment Metric",
		filters={"is_active": 1},
		fields=["name", "direction"],
		order_by="metric_group asc, name asc",
		limit=3,
	)
	if not library:
		return made

	for i, m in enumerate(members):
		if frappe.db.exists("Fitness Assessment", {"member": m.name}):
			continue
		start_w = 82 + i * 2
		for visit, days_ago in ((0, 90), (1, 5)):
			rows = []
			for k, metric in enumerate(library):
				base = 25 + i * 3 + k * 8
				# Move each reading the RIGHT way for its metric, so the progress view
				# shows improvement rather than a random walk.
				step = visit * 3
				value = base - step if metric.direction == "Lower is better" else base + step
				rows.append({"metric": metric.name, "value": value})
			try:
				assessments.record_assessment(
					member=m.name,
					assessment_date=add_days(today(), -days_ago),
					height_cm=170 + i,
					weight_kg=start_w - (visit * 3.5),
					measurements=rows,
					notes="First assessment" if visit == 0 else "Three-month review",
				)
				made["assessments"] += 1
			except Exception as exc:
				print(f"    assessment skipped for {m.name}: {str(exc)[:100]}")
		if i < 3:
			target_metric = library[0]
			try:
				current = 25 + i * 3
				goal = current - 5 if target_metric.direction == "Lower is better" else current + 5
				assessments.set_target(member=m.name, metric=target_metric.name, target_value=goal)
				made["targets"] += 1
			except Exception as exc:
				print(f"    target skipped for {m.name}: {str(exc)[:100]}")
	return made


def seed(commit=True) -> dict:
	"""Top up a seeded demo gym with the Stage 9 operations data."""
	result = {}
	print("  check-ins…")
	result["check_ins"] = _check_ins()
	print("  enquiries…")
	result["enquiries"] = _enquiries()
	print("  packs and day passes…")
	result["packs"] = _packs()
	print("  assessments…")
	result["assessments"] = _assessments()
	if commit:
		frappe.db.commit()
	return result
