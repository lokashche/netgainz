# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Class Schedule — a recurring class definition (Stage 6).

The owner defines a batch once (program, coach, time of day, which weekdays, and
capacity); a daily job then auto-creates the individual Class Sessions for the
coming days, so fixed daily/weekly batches never have to be re-created by hand.
Generation is idempotent: a session is only created if one for this schedule at
that exact start time doesn't already exist.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, get_datetime, getdate, today

DEFAULT_HORIZON_DAYS = 14

# (python weekday index, check fieldname) — Monday is 0 in date.weekday()
WEEKDAY_FIELDS = [
	(0, "on_monday"),
	(1, "on_tuesday"),
	(2, "on_wednesday"),
	(3, "on_thursday"),
	(4, "on_friday"),
	(5, "on_saturday"),
	(6, "on_sunday"),
]


def _horizon_days() -> int:
	raw = frappe.db.get_single_value("Gym Settings", "class_schedule_horizon_days")
	try:
		horizon = int(raw)
	except (TypeError, ValueError):
		horizon = DEFAULT_HORIZON_DAYS
	return horizon if horizon > 0 else DEFAULT_HORIZON_DAYS


class ClassSchedule(Document):
	def validate(self):
		if self.duration_mins is not None and self.duration_mins <= 0:
			frappe.throw("Duration must be greater than zero.")
		if self.capacity is not None and self.capacity < 0:
			frappe.throw("Capacity cannot be negative.")
		if not self.weekday_set():
			frappe.throw("Select at least one day for the class to repeat on.")

	def after_insert(self):
		# Surface the upcoming sessions immediately rather than waiting for the job.
		if self.is_active:
			self.generate()

	def weekday_set(self) -> set:
		return {wd for wd, field in WEEKDAY_FIELDS if self.get(field)}

	def generate(self, horizon_days=None) -> int:
		"""Create the missing Class Sessions for this schedule over the rolling
		window [today, today + horizon). Idempotent. Returns the number created."""
		if not self.is_active:
			return 0
		days = self.weekday_set()
		if not days:
			return 0

		horizon = int(horizon_days or _horizon_days())
		start = getdate(today())
		created = 0
		for offset in range(horizon):
			d = add_days(start, offset)
			if getdate(d).weekday() not in days:
				continue
			start_dt = get_datetime(f"{getdate(d)} {self.start_time}")
			if frappe.db.exists(
				"Class Session", {"class_schedule": self.name, "start_time": start_dt}
			):
				continue
			frappe.get_doc(
				{
					"doctype": "Class Session",
					"title": self.title,
					"program": self.program,
					"coach": self.coach,
					"start_time": start_dt,
					"duration_mins": self.duration_mins,
					"capacity": self.capacity,
					"status": "Scheduled",
					"class_schedule": self.name,
					"notes": self.notes,
				}
			).insert(ignore_permissions=True)
			created += 1
		return created


def generate_scheduled_classes():
	"""Daily scheduler hook: top up each active schedule's sessions for the
	coming days. Idempotent; opt-out via the class_auto_generate setting."""
	if not frappe.db.get_single_value("Gym Settings", "class_auto_generate"):
		return None

	horizon = _horizon_days()
	total = 0
	for name in frappe.get_all("Class Schedule", filters={"is_active": 1}, pluck="name"):
		total += frappe.get_doc("Class Schedule", name).generate(horizon)

	frappe.logger("netgainz").info(f"Recurring classes: generated {total} session(s)")
	return {"created": total}


@frappe.whitelist()
def generate_classes_now(name=None) -> dict:
	"""Owner-triggered generation — for one schedule (name) or all active ones."""
	if name:
		return {"created": frappe.get_doc("Class Schedule", name).generate()}

	total = 0
	for sched_name in frappe.get_all("Class Schedule", filters={"is_active": 1}, pluck="name"):
		total += frappe.get_doc("Class Schedule", sched_name).generate()
	return {"created": total}
