# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from netgainz.net_gainz.accounting import billing_intervals, payment_terms

# WP-10.1: the gym picks a cadence; the day count follows. "Custom" leaves
# duration_in_days alone for the rare plan that is not one of the four.
PLAN_TYPE_DURATIONS = {
	"Monthly": 30,
	"Quarterly": 90,
	"Half-Yearly": 180,
	"Yearly": 365,
}
DURATION_PLAN_TYPES = {days: name for name, days in PLAN_TYPE_DURATIONS.items()}

COMMITMENT = "Commitment"
PAY_AS_YOU_GO = "Pay-as-you-go"


class MembershipPlan(Document):
	def validate(self):
		self._apply_plan_type()
		self._validate_installments()
		payment_terms.sync_plan_template(self)

	def _apply_plan_type(self):
		"""Derive duration_in_days from the chosen cadence.

		Keeps the day count on a value `duration_to_billing_interval` maps to a
		clean CALENDAR interval (30/90/180/365 -> Month x1/x3/x6, Year x1). A free
		-text duration like 45 would silently degrade to "Day x 45" and drift off
		the calendar forever, which is why Custom is the only way to set one.

		A NEW plan that arrives with an explicit duration (an API caller, a data
		import, or a plan created before this field existed) keeps it: the cadence
		is inferred from the duration instead. Without that, `plan_type`'s default
		of Monthly would silently rewrite a 90-day plan to 30 days.
		"""
		supplied = int(self.duration_in_days or 0)
		if self.is_new() and supplied and PLAN_TYPE_DURATIONS.get(self.plan_type) != supplied:
			self.plan_type = DURATION_PLAN_TYPES.get(supplied) or "Custom"

		duration = PLAN_TYPE_DURATIONS.get(self.plan_type)
		if duration:
			self.duration_in_days = duration

	def _validate_installments(self):
		"""Guard the installment settings, including Mode B's divisibility rule (R12)."""
		parts = int(self.installment_count or 1)
		if parts < 1:
			self.installment_count = parts = 1
		if parts > payment_terms.MAX_INSTALLMENTS:
			frappe.throw(
				f"At most {payment_terms.MAX_INSTALLMENTS} installments are supported."
			)
		if parts > 1 and int(self.installment_gap_days or 0) < 1:
			frappe.throw("Installments must be at least 1 day apart.")

		if parts > 1 and self.billing_mode == PAY_AS_YOU_GO:
			self._validate_pay_as_you_go_split(parts)

	def _validate_pay_as_you_go_split(self, parts: int):
		"""R12: a Pay-as-you-go split must land on a clean calendar interval.

		Pay-as-you-go bills each installment as its own invoice, so the SUBSCRIPTION
		cadence becomes duration / parts. Quarterly-in-3 = 30 days (Month x1). But
		quarterly-in-**2** = 45 days, which ERPNext can only express as "Day x 45" —
		drifting off the calendar month permanently. Reject it at save with the
		splits that do work, rather than shipping a plan that misbehaves months later.
		"""
		duration = int(self.duration_in_days or 0)
		if duration < 1:
			return
		legal = [
			n
			for n in range(2, payment_terms.MAX_INSTALLMENTS + 1)
			if duration % n == 0 and _is_calendar_interval(duration // n)
		]
		if duration % parts == 0 and _is_calendar_interval(duration // parts):
			return
		options = ", ".join(str(n) for n in legal) if legal else "none"
		frappe.throw(
			f"A {duration}-day Pay-as-you-go plan cannot be split into {parts} parts — "
			f"each part would be {duration / parts:g} days, which is not a whole "
			f"month, week or year. Workable splits for this plan: {options}. "
			f"(Commitment mode has no such limit — any split works there.)"
		)


def _is_calendar_interval(days: int) -> bool:
	"""True when ``days`` maps to a whole Week / Month / Year period.

	Day x N is what ERPNext falls back to for anything else, and a Day-based
	period does not track the calendar (a 45-day cycle never lands on the same
	date twice).
	"""
	try:
		interval, _count = billing_intervals.duration_to_billing_interval(days)
	except ValueError:
		return False
	return interval != "Day"
