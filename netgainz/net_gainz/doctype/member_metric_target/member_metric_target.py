# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class MemberMetricTarget(Document):
	def validate(self):
		self._one_active_target_per_metric()
		self._stamp_baseline()
		self._validate_target()

	@property
	def has_baseline(self) -> bool:
		"""Whether a starting point was ever actually recorded.

		``baseline_value`` cannot answer this: it is a Float, and Frappe creates
		Float columns ``not null default 0``, so an unstamped baseline reads back
		as 0.0 — indistinguishable from a real reading of zero. ``baseline_date``
		is a Date and stays NULL, so it is the honest flag. The two are always
		written together in ``_stamp_baseline``.
		"""
		return bool(self.baseline_date)

	def _one_active_target_per_metric(self):
		"""A member aims at one number per metric at a time.

		Two active targets for Weight would make "% to target" meaningless, so the
		second is refused with a pointer to the first — the coach edits it or
		switches it off.
		"""
		if not self.is_active:
			return
		existing = frappe.db.get_value(
			"Member Metric Target",
			{
				"member": self.member,
				"metric": self.metric,
				"is_active": 1,
				"name": ["!=", self.name or ""],
			},
			["name", "target_value"],
			as_dict=True,
		)
		if existing:
			frappe.throw(
				f"This member already has an active {self.metric} target of "
				f"{existing.target_value} ({existing.name}). Change that one, or switch it off first."
			)

	def _stamp_baseline(self):
		"""Freeze where the member started, once.

		Progress reads (current - baseline) / (target - baseline), so the baseline
		has to be the reading at the moment the target was agreed. Re-deriving it
		later would quietly move the goalposts every time a new assessment landed.

		A goal agreed before the member was ever measured has no starting point to
		freeze: both fields stay empty, and ``get_progress`` measures that target
		from the member's earliest reading instead — derived, so it stays right
		however the assessments are filed.
		"""
		if self.has_baseline or not self.is_new():
			return
		latest = _reading(self.member, self.metric)
		if latest:
			self.baseline_value = latest["value"]
			self.baseline_date = latest["date"]

	def _validate_target(self):
		"""A target has to be a number the member can actually aim at.

		Deliberately NOT "the target must sit on the metric's better side of the
		baseline". A metric's ``direction`` is the gym's default reading of it, but
		which way a MEMBER should travel is the member's goal: on the pilot's own
		books two members' stated goal is Weight Gain, and Weight is a built-in
		that runs "Lower is better". Refusing their target would make the feature
		useless to exactly the people it is meant to motivate. Which way this
		member is going is read from baseline -> target instead
		(``target_direction``), and that is what the progress view measures and
		colours by.
		"""
		if self.target_value in (None, ""):
			frappe.throw("A target needs a number to aim at.")

	@property
	def target_direction(self) -> str | None:
		"""Which way THIS member is travelling, from their own starting point.

		``None`` when there is no starting point yet, or when the target is the
		number they are already on (a "hold this" goal) — the caller falls back to
		the metric's own default in both cases.
		"""
		if not self.has_baseline or self.target_value in (None, ""):
			return None
		return target_direction(self.baseline_value, self.target_value)


def target_direction(baseline, target) -> str | None:
	"""Which way a member travels from ``baseline`` to ``target``, or None if
	they are the same number."""
	if baseline is None or target is None or float(target) == float(baseline):
		return None
	return "Higher is better" if float(target) > float(baseline) else "Lower is better"


def _reading(member: str, metric: str) -> dict | None:
	"""The member's most recent reading of one metric, or None.

	Readings live in the assessment's child table, so the visits are walked
	newest-first and the first one carrying this metric wins — a member has a
	handful of assessments, so this is cheaper than it looks and keeps the module
	free of hand-written SQL.
	"""
	visits = frappe.get_all(
		"Fitness Assessment",
		filters={"member": member, "assessment_date": ["<=", today()]},
		fields=["name", "assessment_date"],
		order_by="assessment_date desc, creation desc",
		limit_page_length=0,
	)
	for visit in visits:
		value = frappe.db.get_value(
			"Fitness Assessment Measurement",
			{"parent": visit.name, "parenttype": "Fitness Assessment", "metric": metric},
			"value",
		)
		if value is not None:
			return {"value": value, "date": str(getdate(visit.assessment_date))}
	return None
