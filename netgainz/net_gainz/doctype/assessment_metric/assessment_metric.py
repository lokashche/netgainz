# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# The three series the app maintains itself. They are typed into their own fields
# on a Fitness Assessment (height and weight) or computed from them (BMI), then
# mirrored into the readings — so the progress view and targets have ONE uniform
# path over every metric instead of a special case for body composition.
BUILTIN_METRICS = {
	"Height": {"unit": "cm", "direction": "Higher is better", "metric_group": "Body Composition"},
	"Weight": {"unit": "kg", "direction": "Lower is better", "metric_group": "Body Composition"},
	"BMI": {"unit": "kg/m2", "direction": "Lower is better", "metric_group": "Body Composition"},
}


class AssessmentMetric(Document):
	def validate(self):
		self.unit = (self.unit or "").strip()
		if not self.unit:
			frappe.throw("A metric needs a unit — what is the reading in? (kg, cm, %, sec, reps …)")

		if self.metric_name in BUILTIN_METRICS:
			self.is_builtin = 1

		if self.is_builtin:
			self._protect_builtin()

		# A metric's unit is the meaning of every reading already filed under it.
		# Changing kg to lb would silently rewrite the member's whole history, so
		# once there are readings the unit is fixed — retire the metric and make a
		# new one instead.
		if not self.is_new():
			before = self.get_doc_before_save()
			if before and before.unit != self.unit and self._reading_count():
				frappe.throw(
					f"{self.metric_name} already has {self._reading_count()} reading(s) recorded in "
					f"{before.unit}. Changing the unit would rewrite that history. Switch this metric "
					"off and add a new one instead."
				)

	def on_trash(self):
		if self.is_builtin:
			frappe.throw(f"{self.metric_name} is maintained by the app and cannot be deleted.")
		count = self._reading_count()
		if count:
			frappe.throw(
				f"{self.metric_name} has {count} reading(s) recorded against it. Switch it off "
				"instead of deleting it, so the members' history stays intact."
			)

	def _protect_builtin(self):
		"""Built-ins carry the meaning the assessment form and BMI maths rely on."""
		spec = BUILTIN_METRICS.get(self.metric_name)
		if not spec:
			return
		self.unit = spec["unit"]
		self.direction = spec["direction"]
		self.metric_group = spec["metric_group"]
		self.applies_to = "Everyone"
		self.is_active = 1

	def _reading_count(self) -> int:
		return frappe.db.count("Fitness Assessment Measurement", {"metric": self.name})
