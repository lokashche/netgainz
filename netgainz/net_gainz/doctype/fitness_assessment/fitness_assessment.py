# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today

DEFAULT_INTERVAL_DAYS = 90

# Below these the reading is a typo, not a person. Deliberately wide — this is a
# sanity rail, not a clinical range.
MIN_HEIGHT_CM, MAX_HEIGHT_CM = 50.0, 260.0
MIN_WEIGHT_KG, MAX_WEIGHT_KG = 10.0, 400.0


def _interval_days() -> int:
	raw = frappe.db.get_single_value("Business Settings", "assessment_interval_days")
	try:
		days = int(raw)
	except (TypeError, ValueError):
		days = DEFAULT_INTERVAL_DAYS
	return days if days > 0 else DEFAULT_INTERVAL_DAYS


def _row_values(row) -> dict:
	"""The part of a measurement row that is data, not ORM bookkeeping.

	The grid is rewritten on every save (builtins are stripped and re-mirrored),
	so rows are rebuilt from their values; child-row names are referenced nowhere.
	"""
	return {"metric": row.metric, "value": row.value, "unit": row.unit, "note": row.note}


class FitnessAssessment(Document):
	def validate(self):
		self._height_carried = False
		self._validate_date()
		self._default_coach()
		self._absorb_builtin_rows()
		self._carry_height_forward()
		self._validate_body()
		self._compute_bmi()
		self._compute_age()
		self._validate_measurements()
		self._require_a_reading()
		self._mirror_builtins()
		self._default_next_due()

	# ---- the visit ---------------------------------------------------------- #

	def _validate_date(self):
		if not self.assessment_date:
			self.assessment_date = today()
		if getdate(self.assessment_date) > getdate(today()):
			frappe.throw("An assessment cannot be dated in the future.")

	def _default_coach(self):
		if not self.coach and self.member:
			self.coach = frappe.db.get_value("Member", self.member, "coach")

	# ---- body composition --------------------------------------------------- #

	def _carry_height_forward(self):
		"""An adult is measured once. Blank height takes the member's last known
		reading so BMI still computes, rather than silently coming out empty."""
		if self.height_cm:
			return
		self._height_carried = True
		previous = frappe.db.get_value(
			"Fitness Assessment",
			{
				"member": self.member,
				"height_cm": [">", 0],
				"assessment_date": ["<=", self.assessment_date],
				"name": ["!=", self.name or ""],
			},
			"height_cm",
			order_by="assessment_date desc, creation desc",
		)
		if previous:
			self.height_cm = previous

	def _validate_body(self):
		if self.height_cm and not (MIN_HEIGHT_CM <= self.height_cm <= MAX_HEIGHT_CM):
			frappe.throw(f"Height {self.height_cm} cm does not look right — record it in centimetres.")
		if self.weight_kg and not (MIN_WEIGHT_KG <= self.weight_kg <= MAX_WEIGHT_KG):
			frappe.throw(f"Weight {self.weight_kg} kg does not look right — record it in kilograms.")

	def _compute_bmi(self):
		if self.height_cm and self.weight_kg:
			metres = self.height_cm / 100.0
			self.bmi = round(self.weight_kg / (metres * metres), 1)
		else:
			self.bmi = 0

	def _compute_age(self):
		"""Calendar age on the day, not days/365.25 — that reads 17 on an
		eighteenth birthday, and age matters most for the youngest members."""
		dob = frappe.db.get_value("Member", self.member, "date_of_birth") if self.member else None
		if not dob:
			self.age_years = 0
			return
		dob, on = getdate(dob), getdate(self.assessment_date)
		years = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
		self.age_years = max(0, years)

	# ---- the readings ------------------------------------------------------- #

	def _absorb_builtin_rows(self):
		"""Take height / weight typed into the grid up into their own fields.

		The fields are the canonical entry point, but a coach who types Weight as
		a measurement row should not lose the number. Whatever is in the field
		wins; an empty field adopts the row. Either way the builtin rows are
		cleared here and rebuilt by ``_mirror_builtins`` after BMI is computed —
		which is also what makes re-saving an assessment idempotent.
		"""
		from netgainz.net_gainz.doctype.assessment_metric.assessment_metric import BUILTIN_METRICS

		absorbed = {"Height": "height_cm", "Weight": "weight_kg"}
		kept = []
		for row in self.measurements:
			if row.metric not in BUILTIN_METRICS:
				kept.append(_row_values(row))
				continue
			field = absorbed.get(row.metric)
			if field and row.value and not self.get(field):
				self.set(field, row.value)

		self.set("measurements", [])
		for row in kept:
			self.append("measurements", row)

	def _validate_measurements(self):
		"""Every reading has a number, and one reading per metric per visit.

		Two readings of the same metric on one day would make "the value on this
		date" ambiguous for the whole progress view, so the second is refused at
		the door rather than silently won by sort order.
		"""
		seen = set()
		for row in self.measurements:
			if row.value in (None, ""):
				frappe.throw(f"{row.metric} has no reading. Enter a value or remove the row.")
			if row.metric in seen:
				frappe.throw(f"{row.metric} is measured twice on this assessment. Keep one reading.")
			seen.add(row.metric)

	def _require_a_reading(self):
		"""An assessment with nothing in it is a mis-click, not a measurement.

		Saving one would push the member's next-due date a whole interval out and
		move them off the "never measured" list — the gym would believe someone
		had been assessed who never was. A height carried forward from a previous
		visit does not count: nothing was measured today.
		"""
		measured_today = bool(self.weight_kg) or bool(self.measurements)
		if self.height_cm and not self._height_carried:
			measured_today = True
		if not measured_today:
			frappe.throw(
				"Nothing was recorded. Enter at least one reading — a weight, or any "
				"measurement — before saving the assessment."
			)

	def _mirror_builtins(self):
		"""File height / weight / BMI as ordinary readings too.

		The fields above are for the coach's fingers; these rows are what the
		progress view and the targets read. Keeping ONE path over every metric is
		what stops body composition being a special case in four places.
		"""
		from netgainz.net_gainz.doctype.assessment_metric.assessment_metric import BUILTIN_METRICS

		values = {"Height": self.height_cm, "Weight": self.weight_kg, "BMI": self.bmi}

		kept = [_row_values(row) for row in self.measurements]
		mirrored = []
		for metric, value in values.items():
			if not value:
				continue
			if not frappe.db.exists("Assessment Metric", metric):
				# The seed has not run on this site; the field still holds the
				# number, it simply is not trended until the metric exists.
				continue
			mirrored.append({"metric": metric, "value": value, "unit": BUILTIN_METRICS[metric]["unit"]})

		self.set("measurements", [])
		for row in mirrored:
			self.append("measurements", row)
		for row in kept:
			self.append("measurements", row)

	# ---- the next visit ----------------------------------------------------- #

	def _default_next_due(self):
		if not self.next_due_date:
			self.next_due_date = add_days(self.assessment_date, _interval_days())
