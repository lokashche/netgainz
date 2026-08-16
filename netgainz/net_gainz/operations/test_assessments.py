# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 9 OP-5: fitness assessments & progress.

Pinned:

* the metric library is the gym's own — seeding is idempotent, and a metric with
  readings behind it can be retired but never deleted or re-united, because both
  would silently rewrite a member's history;
* Height / Weight / BMI are typed into their own fields and mirrored into the
  same measurement rows as everything else, so progress walks ONE path; saving
  the same assessment twice must not double those rows;
* BMI is computed, never typed; age comes from the member's date of birth; a
  blank height carries forward from the member's last reading;
* one reading per metric per visit — a second would make "the value on this
  date" ambiguous for the whole progress view;
* improvement respects the metric's direction: a sprint time falling and a jump
  height rising are both progress;
* percent-to-target is measured from the baseline frozen when the target was
  agreed, so adjusting a target never resets the bar, and overshooting clamps
  at 100;
* only a member's LATEST assessment decides whether they are due, and a member
  never assessed is offered, not chased;
* the daily digest is one per user per day and opt-out honoured — notify-only,
  no email or SMS;
* the desk may measure members and agree targets, the metric library is the
  owner's, and a role-less session is refused (exercised as real sessions — as
  Administrator they would pass vacuously).
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.operations import assessments

STAFF_USER = "op5-frontdesk@example.com"
NOROLE_USER = "op5-visitor@example.com"
OWNER_USER = "op5-owner@example.com"


def _member(name, **fields):
	return frappe.get_doc({"doctype": "Member", "full_name": name, "status": "Active", **fields}).insert(
		ignore_permissions=True
	)


def _metric(name, unit="cm", direction="Higher is better", **fields):
	if frappe.db.exists("Assessment Metric", name):
		return frappe.get_doc("Assessment Metric", name)
	return frappe.get_doc(
		{
			"doctype": "Assessment Metric",
			"metric_name": name,
			"unit": unit,
			"direction": direction,
			**fields,
		}
	).insert(ignore_permissions=True)


def _assess(member, date=None, height=None, weight=None, rows=None, **fields):
	return frappe.get_doc(
		{
			"doctype": "Fitness Assessment",
			"member": member,
			"assessment_date": date or today(),
			"height_cm": height,
			"weight_kg": weight,
			"measurements": rows or [],
			**fields,
		}
	).insert(ignore_permissions=True)


def _reading(doc, metric):
	for row in doc.measurements:
		if row.metric == metric:
			return row
	return None


class TestAssessments(FrappeTestCase):
	def setUp(self):
		assessments.seed_default_metrics()
		permissions.ensure_roles()
		self._user(STAFF_USER, permissions.GYM_STAFF)
		self._user(NOROLE_USER, None)
		self.addCleanup(frappe.set_user, "Administrator")
		self.tag = frappe.generate_hash(length=5)
		self.member = _member(f"OP5 Member {self.tag}", category="Sport", date_of_birth="2008-05-01")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _user(self, email, role):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@")[0],
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		if role:
			user = frappe.get_doc("User", email)
			if role not in [r.role for r in user.roles]:
				user.append("roles", {"role": role})
				user.save(ignore_permissions=True)

	# ---- the metric library ----------------------------------------------------------- #
	def test_seeding_twice_adds_nothing(self):
		first = assessments.seed_default_metrics()
		second = assessments.seed_default_metrics()
		self.assertEqual(first["created"], 0, "already seeded in setUp")
		self.assertEqual(second["created"], 0)
		self.assertEqual(frappe.db.count("Assessment Metric", {"metric_name": "Weight"}), 1)

	def test_the_three_builtins_are_flagged_and_carry_their_own_units(self):
		for name, unit in (("Height", "cm"), ("Weight", "kg"), ("BMI", "kg/m2")):
			doc = frappe.get_doc("Assessment Metric", name)
			self.assertEqual(doc.is_builtin, 1, f"{name} must be a built-in")
			self.assertEqual(doc.unit, unit)

	def test_a_builtin_cannot_be_deleted(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Assessment Metric", "Weight")

	def test_a_builtin_keeps_its_meaning_even_if_edited(self):
		doc = frappe.get_doc("Assessment Metric", "Weight")
		doc.unit = "lb"
		doc.direction = "Higher is better"
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.unit, "kg", "BMI arithmetic depends on this")
		self.assertEqual(doc.direction, "Lower is better")

	def test_the_unit_is_locked_once_a_reading_exists(self):
		metric = _metric(f"OP5 Girth {self.tag}", unit="cm")
		_assess(self.member.name, rows=[{"metric": metric.name, "value": 40.0}])

		metric.reload()
		metric.unit = "in"
		with self.assertRaises(frappe.ValidationError):
			metric.save(ignore_permissions=True)

	def test_a_metric_with_readings_is_retired_not_deleted(self):
		metric = _metric(f"OP5 Doomed {self.tag}", unit="cm")
		_assess(self.member.name, rows=[{"metric": metric.name, "value": 12.0}])

		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Assessment Metric", metric.name)

		metric.reload()
		metric.is_active = 0
		metric.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Assessment Metric", metric.name, "is_active"), 0)

	def test_an_unused_metric_can_be_deleted(self):
		metric = _metric(f"OP5 Unused {self.tag}", unit="cm")
		frappe.delete_doc("Assessment Metric", metric.name)
		self.assertFalse(frappe.db.exists("Assessment Metric", metric.name))

	def test_a_metric_needs_a_unit(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Assessment Metric",
					"metric_name": f"OP5 Unitless {self.tag}",
					"unit": "   ",
					"direction": "Higher is better",
				}
			).insert(ignore_permissions=True)

	def test_the_form_offers_the_battery_that_fits_the_member(self):
		general = _member(f"OP5 General {self.tag}", category="General")

		sport_metrics = {m.name for m in assessments.get_metrics(self.member.name)}
		general_metrics = {m.name for m in assessments.get_metrics(general.name)}

		self.assertIn("20m Sprint", sport_metrics, "a Sport member gets the performance battery")
		self.assertNotIn("20m Sprint", general_metrics)
		self.assertIn("Waist", general_metrics, "a General member gets the body-composition check")
		self.assertNotIn("Waist", sport_metrics)
		for both in (sport_metrics, general_metrics):
			self.assertIn("Body Fat %", both, "Everyone metrics are offered to all")
			self.assertNotIn("Weight", both, "built-ins have their own fields on the form")

	def test_retired_metrics_are_not_offered(self):
		metric = _metric(f"OP5 Retired {self.tag}", unit="cm", applies_to="Everyone")
		metric.is_active = 0
		metric.save(ignore_permissions=True)
		self.assertNotIn(metric.name, {m.name for m in assessments.get_metrics(self.member.name)})
		self.assertIn(
			metric.name,
			{m.name for m in assessments.get_metrics(self.member.name, include_inactive=1)},
		)

	# ---- the assessment --------------------------------------------------------------- #
	def test_bmi_is_computed_not_typed(self):
		doc = _assess(self.member.name, height=172.0, weight=78.4)
		self.assertEqual(doc.bmi, 26.5)

	def test_age_comes_from_the_members_date_of_birth(self):
		doc = _assess(self.member.name, date="2026-08-14", height=170.0, weight=60.0)
		self.assertEqual(doc.age_years, 18, "born 2008-05-01, measured 2026-08-14")

	def test_a_blank_height_carries_forward(self):
		_assess(self.member.name, date=add_days(today(), -60), height=172.0, weight=80.0)
		later = _assess(self.member.name, weight=78.0)
		self.assertEqual(later.height_cm, 172.0)
		self.assertEqual(later.bmi, 26.4, "BMI still computes without re-measuring height")

	def test_builtins_are_mirrored_into_the_readings(self):
		doc = _assess(self.member.name, height=172.0, weight=78.4)
		self.assertEqual(_reading(doc, "Weight").value, 78.4)
		self.assertEqual(_reading(doc, "Height").value, 172.0)
		self.assertEqual(_reading(doc, "BMI").value, 26.5)
		self.assertEqual(_reading(doc, "Weight").unit, "kg")

	def test_resaving_does_not_double_the_mirrored_rows(self):
		doc = _assess(self.member.name, height=172.0, weight=78.4)
		self.assertEqual(len(doc.measurements), 3)

		doc.notes = "second thoughts"
		doc.save(ignore_permissions=True)
		doc.reload()

		self.assertEqual(len(doc.measurements), 3, "mirroring is idempotent")
		self.assertEqual(len([r for r in doc.measurements if r.metric == "Weight"]), 1)

	def test_a_changed_weight_restates_the_mirrored_rows(self):
		doc = _assess(self.member.name, height=172.0, weight=78.4)
		doc.weight_kg = 76.0
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(_reading(doc, "Weight").value, 76.0)
		self.assertEqual(_reading(doc, "BMI").value, 25.7, "BMI follows the weight")

	def test_a_weight_typed_as_a_row_is_absorbed_not_lost(self):
		doc = _assess(self.member.name, height=172.0, rows=[{"metric": "Weight", "value": 78.4}])
		self.assertEqual(doc.weight_kg, 78.4, "the number survives")
		self.assertEqual(doc.bmi, 26.5, "and still drives BMI")
		self.assertEqual(len([r for r in doc.measurements if r.metric == "Weight"]), 1)

	def test_the_field_wins_over_a_conflicting_row(self):
		doc = _assess(self.member.name, height=172.0, weight=78.4, rows=[{"metric": "Weight", "value": 99.0}])
		self.assertEqual(doc.weight_kg, 78.4)
		self.assertEqual(_reading(doc, "Weight").value, 78.4)

	def test_one_reading_per_metric_per_visit(self):
		metric = _metric(f"OP5 Twice {self.tag}", unit="cm")
		with self.assertRaises(frappe.ValidationError):
			_assess(
				self.member.name,
				rows=[{"metric": metric.name, "value": 10.0}, {"metric": metric.name, "value": 11.0}],
			)

	def test_a_reading_without_a_number_is_refused(self):
		metric = _metric(f"OP5 Empty {self.tag}", unit="cm")
		with self.assertRaises(frappe.ValidationError):
			_assess(self.member.name, rows=[{"metric": metric.name, "value": None}])

	def test_an_assessment_cannot_be_dated_in_the_future(self):
		with self.assertRaises(frappe.ValidationError):
			_assess(self.member.name, date=add_days(today(), 1), weight=70.0)

	def test_a_height_in_metres_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			_assess(self.member.name, height=1.72, weight=70.0)

	def test_next_due_follows_the_configured_interval(self):
		frappe.db.set_single_value("Business Settings", "assessment_interval_days", 45)
		self.addCleanup(frappe.db.set_single_value, "Business Settings", "assessment_interval_days", 90)
		doc = _assess(self.member.name, weight=70.0)
		self.assertEqual(str(doc.next_due_date), add_days(doc.assessment_date, 45))

	def test_a_coach_set_due_date_is_kept(self):
		chosen = add_days(today(), 14)
		doc = _assess(self.member.name, weight=70.0, next_due_date=chosen)
		self.assertEqual(str(doc.next_due_date), chosen)

	def test_the_assessment_inherits_the_members_branch(self):
		doc = _assess(self.member.name, weight=70.0)
		self.assertEqual(doc.branch, self.member.branch, "R19: branch from birth")

	def test_the_coach_defaults_to_the_members_own(self):
		instructor = frappe.get_doc({"doctype": "Instructor", "coach_name": f"OP5 Coach {self.tag}"}).insert(
			ignore_permissions=True
		)
		member = _member(f"OP5 Coached {self.tag}", coach=instructor.name)
		doc = _assess(member.name, weight=70.0)
		self.assertEqual(doc.coach, instructor.name)

	# ---- progress --------------------------------------------------------------------- #
	def test_progress_reports_change_since_last_and_since_first(self):
		_assess(self.member.name, date=add_days(today(), -120), height=172.0, weight=82.1)
		_assess(self.member.name, date=add_days(today(), -60), weight=80.0)
		_assess(self.member.name, date=today(), weight=78.4)

		progress = assessments.get_progress(self.member.name)
		weight = next(s for s in progress["series"] if s["metric"] == "Weight")

		self.assertEqual(weight["count"], 3)
		self.assertEqual(weight["current"], 78.4)
		self.assertAlmostEqual(weight["change_since_last"], 1.6, places=2, msg="lost 1.6kg since last")
		self.assertAlmostEqual(weight["change_since_first"], 3.7, places=2)
		self.assertEqual(progress["assessment_count"], 3)
		self.assertEqual(progress["sport_goal"], self.member.sport_goal)

	def test_improvement_follows_the_metrics_direction(self):
		_assess(self.member.name, date=add_days(today(), -30), rows=[{"metric": "20m Sprint", "value": 3.70}])
		_assess(self.member.name, date=today(), rows=[{"metric": "20m Sprint", "value": 3.55}])

		sprint = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "20m Sprint"
		)
		self.assertAlmostEqual(
			sprint["change_since_last"], 0.15, places=2, msg="a faster time is a positive change"
		)

		_assess(
			self.member.name, date=add_days(today(), -30), rows=[{"metric": "Vertical Jump", "value": 45.0}]
		)
		_assess(self.member.name, date=today(), rows=[{"metric": "Vertical Jump", "value": 48.0}])
		jump = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Vertical Jump"
		)
		self.assertAlmostEqual(jump["change_since_last"], 3.0, places=2, msg="a higher jump too")

	def test_a_single_reading_has_no_change_yet(self):
		_assess(self.member.name, height=172.0, weight=78.4)
		weight = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Weight"
		)
		self.assertIsNone(weight["change_since_last"])
		self.assertIsNone(weight["change_since_first"])

	def test_a_member_never_assessed_has_an_empty_progress(self):
		fresh = _member(f"OP5 Untouched {self.tag}")
		progress = assessments.get_progress(fresh.name)
		self.assertEqual(progress["series"], [])
		self.assertEqual(progress["assessment_count"], 0)
		self.assertIsNone(progress["last_assessment"])

	def test_body_composition_is_listed_before_performance(self):
		_assess(self.member.name, height=172.0, weight=78.4, rows=[{"metric": "20m Sprint", "value": 3.6}])
		groups = [s["group"] for s in assessments.get_progress(self.member.name)["series"]]
		self.assertEqual(groups, sorted(groups, key=lambda g: {"Body Composition": 0, "Performance": 1}[g]))

	# ---- targets ---------------------------------------------------------------------- #
	def test_setting_a_target_freezes_the_starting_point(self):
		_assess(self.member.name, height=172.0, weight=82.0)
		result = assessments.set_target(self.member.name, "Weight", 72.0)
		self.assertEqual(result["baseline_value"], 82.0)

	def test_percent_to_target_is_measured_from_the_starting_point(self):
		_assess(self.member.name, date=add_days(today(), -60), height=172.0, weight=82.0)
		assessments.set_target(self.member.name, "Weight", 72.0)
		_assess(self.member.name, date=today(), weight=78.4)

		weight = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Weight"
		)
		self.assertEqual(weight["target"], 72.0)
		self.assertEqual(weight["baseline"], 82.0)
		self.assertAlmostEqual(weight["percent_to_target"], 36.0, places=1, msg="3.6 of the 10 kg")

	def test_overshooting_a_target_reads_as_reached_not_more(self):
		_assess(self.member.name, date=add_days(today(), -60), height=172.0, weight=82.0)
		assessments.set_target(self.member.name, "Weight", 72.0)
		_assess(self.member.name, date=today(), weight=70.0)

		weight = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Weight"
		)
		self.assertEqual(weight["percent_to_target"], 100.0)

	def test_moving_the_wrong_way_never_reads_below_zero(self):
		_assess(self.member.name, date=add_days(today(), -60), height=172.0, weight=82.0)
		assessments.set_target(self.member.name, "Weight", 72.0)
		_assess(self.member.name, date=today(), weight=85.0)

		weight = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Weight"
		)
		self.assertEqual(weight["percent_to_target"], 0.0)

	def test_adjusting_a_target_keeps_the_original_starting_point(self):
		_assess(self.member.name, date=add_days(today(), -60), height=172.0, weight=82.0)
		first = assessments.set_target(self.member.name, "Weight", 72.0)
		_assess(self.member.name, date=today(), weight=78.4)

		second = assessments.set_target(self.member.name, "Weight", 74.0)
		self.assertEqual(second["target"], first["target"], "the same target, edited")
		self.assertEqual(second["baseline_value"], 82.0, "the bar does not reset")

	def test_two_active_targets_for_one_metric_are_refused(self):
		_assess(self.member.name, height=172.0, weight=82.0)
		assessments.set_target(self.member.name, "Weight", 72.0)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Member Metric Target",
					"member": self.member.name,
					"metric": "Weight",
					"target_value": 70.0,
				}
			).insert(ignore_permissions=True)

	def test_a_weight_gain_goal_is_allowed_and_reads_as_progress(self):
		"""Two of the pilot's own members have "Weight Gain" as their goal. Weight
		is a built-in that runs "Lower is better" for the gym at large, so a
		metric-level direction check would refuse exactly the people the feature
		is meant to motivate. Which way THIS member travels comes from their own
		starting point."""
		_assess(self.member.name, date=add_days(today(), -60), height=172.0, weight=55.0)
		assessments.set_target(self.member.name, "Weight", 62.0)
		_assess(self.member.name, date=today(), weight=58.0)

		weight = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Weight"
		)
		self.assertEqual(weight["direction"], "Higher is better", "this member is gaining on purpose")
		self.assertAlmostEqual(weight["change_since_last"], 3.0, places=2, msg="+3kg is progress for them")
		self.assertAlmostEqual(weight["percent_to_target"], 42.9, places=1, msg="3 of the 7 kg")

	def test_the_same_metric_still_reads_the_gyms_way_without_a_target(self):
		other = _member(f"OP5 Slimming {self.tag}")
		_assess(other.name, date=add_days(today(), -60), height=172.0, weight=90.0)
		_assess(other.name, date=today(), weight=87.0)

		weight = next(s for s in assessments.get_progress(other.name)["series"] if s["metric"] == "Weight")
		self.assertEqual(weight["direction"], "Lower is better", "the metric's own default")
		self.assertAlmostEqual(weight["change_since_last"], 3.0, places=2, msg="-3kg is progress")

	def test_an_assessment_with_nothing_in_it_is_refused(self):
		"""A mis-click would otherwise push next-due a whole interval out and move
		the member off the never-measured list, so the gym would believe someone
		had been assessed who never was."""
		fresh = _member(f"OP5 Misclick {self.tag}")
		with self.assertRaises(frappe.ValidationError):
			assessments.record_assessment(fresh.name)

		# A height carried forward from an earlier visit is not a measurement today.
		_assess(fresh.name, date=add_days(today(), -60), height=170.0, weight=60.0)
		with self.assertRaises(frappe.ValidationError):
			assessments.record_assessment(fresh.name)

	def test_age_is_right_on_the_birthday_itself(self):
		born = _member(f"OP5 Birthday {self.tag}", date_of_birth="2008-05-01")
		doc = _assess(born.name, date="2026-05-01", weight=60.0)
		self.assertEqual(doc.age_years, 18, "eighteen on the day, not seventeen")
		day_before = _assess(born.name, date="2026-04-30", weight=60.0)
		self.assertEqual(day_before.age_years, 17)

	def test_a_target_can_be_set_before_the_first_measurement(self):
		fresh = _member(f"OP5 Ambitious {self.tag}")
		result = assessments.set_target(fresh.name, "Weight", 70.0)
		self.assertTrue(result["target"])
		self.assertIsNone(result["baseline_value"], "nothing to measure from yet")

		weight = next(s for s in assessments.get_progress(fresh.name)["series"] if s["metric"] == "Weight")
		self.assertIsNone(weight["percent_to_target"])
		self.assertEqual(weight["target"], 70.0)

	def test_a_goal_agreed_before_the_scales_is_not_instantly_100_percent(self):
		"""The Float column reads back 0.0, never NULL, so an unstamped baseline
		used to make every falling metric report "100% there" at any weight."""
		fresh = _member(f"OP5 Phantom {self.tag}")
		assessments.set_target(fresh.name, "Weight", 70.0)
		_assess(fresh.name, height=172.0, weight=85.0)

		weight = next(s for s in assessments.get_progress(fresh.name)["series"] if s["metric"] == "Weight")
		self.assertEqual(weight["baseline"], 85.0, "the first reading becomes the starting point")
		self.assertEqual(
			weight["percent_to_target"], 0.0, "85kg against a 70kg goal is the start, not the end"
		)

	def test_a_goal_agreed_before_the_scales_can_still_be_changed_and_cleared(self):
		"""A phantom 0.0 baseline used to fail the direction check on every later
		save, so the coach could neither adjust nor switch the target off."""
		fresh = _member(f"OP5 Stuck {self.tag}")
		created = assessments.set_target(fresh.name, "Weight", 70.0)

		adjusted = assessments.set_target(fresh.name, "Weight", 72.0)
		self.assertEqual(adjusted["target"], created["target"])
		self.assertEqual(adjusted["target_value"], 72.0)

		cleared = assessments.clear_target(created["target"])
		self.assertEqual(cleared["is_active"], 0)

	def test_the_backfilled_starting_point_is_the_earliest_reading(self):
		fresh = _member(f"OP5 Backfill {self.tag}")
		assessments.set_target(fresh.name, "Weight", 70.0)
		# Filed newest-first, as a desk would when catching up on paper records.
		_assess(fresh.name, date=today(), height=172.0, weight=80.0)
		_assess(fresh.name, date=add_days(today(), -60), height=172.0, weight=88.0)

		weight = next(s for s in assessments.get_progress(fresh.name)["series"] if s["metric"] == "Weight")
		self.assertEqual(weight["baseline"], 88.0, "where they actually started")
		self.assertAlmostEqual(weight["percent_to_target"], 44.4, places=1, msg="8 of the 18 kg")

	def test_a_stamped_starting_point_is_never_moved_by_a_later_visit(self):
		fresh = _member(f"OP5 Frozen {self.tag}")
		_assess(fresh.name, date=add_days(today(), -90), height=172.0, weight=90.0)
		assessments.set_target(fresh.name, "Weight", 70.0)
		_assess(fresh.name, date=today(), weight=80.0)

		weight = next(s for s in assessments.get_progress(fresh.name)["series"] if s["metric"] == "Weight")
		self.assertEqual(weight["baseline"], 90.0, "the goalposts do not move")

	def test_a_hold_this_number_target_shows_the_member_drifting_off_it(self):
		"""baseline == target is a legitimate "stay here" goal. It reads as reached
		only while the member is still there — drifting off must show."""
		fresh = _member(f"OP5 Holding {self.tag}")
		_assess(fresh.name, date=add_days(today(), -60), height=172.0, weight=70.0)
		assessments.set_target(fresh.name, "Weight", 70.0)

		held = next(s for s in assessments.get_progress(fresh.name)["series"] if s["metric"] == "Weight")
		self.assertEqual(held["percent_to_target"], 100.0, "still on the number")

		_assess(fresh.name, date=today(), weight=78.0)
		drifted = next(s for s in assessments.get_progress(fresh.name)["series"] if s["metric"] == "Weight")
		self.assertEqual(drifted["percent_to_target"], 0.0, "8kg above the number they agreed to hold")

	def test_clearing_a_target_keeps_the_readings(self):
		_assess(self.member.name, height=172.0, weight=82.0)
		target = assessments.set_target(self.member.name, "Weight", 72.0)
		assessments.clear_target(target["target"])

		weight = next(
			s for s in assessments.get_progress(self.member.name)["series"] if s["metric"] == "Weight"
		)
		self.assertIsNone(weight["target"])
		self.assertEqual(weight["current"], 82.0, "the history is untouched")

	def test_the_target_inherits_the_members_branch(self):
		result = assessments.set_target(self.member.name, "Weight", 70.0)
		self.assertEqual(result["branch"], self.member.branch, "R19: branch from birth")

	# ---- who is due ------------------------------------------------------------------- #
	def test_the_due_list_splits_overdue_due_soon_and_never_measured(self):
		overdue_member = _member(f"OP5 Overdue {self.tag}")
		soon_member = _member(f"OP5 Soon {self.tag}")
		later_member = _member(f"OP5 Later {self.tag}")
		never_member = _member(f"OP5 Never {self.tag}")

		_assess(
			overdue_member.name,
			date=add_days(today(), -120),
			weight=70.0,
			next_due_date=add_days(today(), -5),
		)
		_assess(
			soon_member.name, date=add_days(today(), -80), weight=70.0, next_due_date=add_days(today(), 3)
		)
		_assess(
			later_member.name, date=add_days(today(), -10), weight=70.0, next_due_date=add_days(today(), 60)
		)

		due = assessments.get_due()
		self.assertIn(overdue_member.name, {r["member"] for r in due["overdue"]})
		self.assertIn(soon_member.name, {r["member"] for r in due["due_soon"]})
		self.assertNotIn(later_member.name, {r["member"] for r in due["due_soon"]})
		self.assertNotIn(later_member.name, {r["member"] for r in due["overdue"]})
		self.assertIn(never_member.name, {r["member"] for r in due["never_assessed"]})

	def test_only_the_latest_assessment_decides_who_is_due(self):
		member = _member(f"OP5 Remeasured {self.tag}")
		_assess(member.name, date=add_days(today(), -120), weight=70.0, next_due_date=add_days(today(), -30))
		_assess(member.name, date=today(), weight=69.0, next_due_date=add_days(today(), 90))

		due = assessments.get_due()
		self.assertNotIn(member.name, {r["member"] for r in due["overdue"]}, "re-measured yesterday")
		self.assertNotIn(member.name, {r["member"] for r in due["never_assessed"]})

	def test_an_inactive_member_is_not_chased(self):
		member = _member(f"OP5 Lapsed {self.tag}", status="Inactive")
		_assess(member.name, date=add_days(today(), -120), weight=70.0, next_due_date=add_days(today(), -5))
		due = assessments.get_due()
		self.assertNotIn(member.name, {r["member"] for r in due["overdue"]})

	def test_the_due_window_is_configurable(self):
		member = _member(f"OP5 Window {self.tag}")
		_assess(member.name, date=add_days(today(), -80), weight=70.0, next_due_date=add_days(today(), 20))

		self.assertNotIn(member.name, {r["member"] for r in assessments.get_due()["due_soon"]})
		self.assertIn(member.name, {r["member"] for r in assessments.get_due(within_days=30)["due_soon"]})

	# ---- the daily digest ------------------------------------------------------------- #
	def test_the_digest_is_one_per_user_per_day(self):
		self._user(OWNER_USER, None)
		owner = frappe.get_doc("User", OWNER_USER)
		if "System Manager" not in [r.role for r in owner.roles]:
			owner.append("roles", {"role": "System Manager"})
			owner.save(ignore_permissions=True)

		member = _member(f"OP5 Chased {self.tag}")
		_assess(member.name, date=add_days(today(), -120), weight=70.0, next_due_date=add_days(today(), -5))

		frappe.db.set_single_value("Business Settings", "assessment_reminders_enabled", 1)
		first = assessments.notify_assessments_due()
		self.assertGreaterEqual(first["notified"], 1)

		second = assessments.notify_assessments_due()
		self.assertEqual(second["notified"], 0, "the same digest does not go twice in a day")

	def test_the_digest_can_be_switched_off(self):
		member = _member(f"OP5 Quiet {self.tag}")
		_assess(member.name, date=add_days(today(), -120), weight=70.0, next_due_date=add_days(today(), -5))

		frappe.db.set_single_value("Business Settings", "assessment_reminders_enabled", 0)
		self.addCleanup(frappe.db.set_single_value, "Business Settings", "assessment_reminders_enabled", 1)
		self.assertIsNone(assessments.notify_assessments_due())

	# ---- who may do what -------------------------------------------------------------- #
	def test_the_desk_may_measure_and_agree_targets(self):
		frappe.set_user(STAFF_USER)
		result = assessments.record_assessment(
			self.member.name,
			height_cm=172.0,
			weight_kg=78.4,
			measurements=[{"metric": "20m Sprint", "value": 3.6}],
			notes="baseline",
		)
		self.assertTrue(result["assessment"])
		self.assertEqual(result["bmi"], 26.5)
		self.assertTrue(result["progress"]["series"])

		target = assessments.set_target(self.member.name, "Weight", 72.0)
		self.assertTrue(target["target"])

	def test_the_metric_library_is_the_owners(self):
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Assessment Metric",
					"metric_name": f"OP5 Staff Metric {self.tag}",
					"unit": "cm",
					"direction": "Higher is better",
				}
			).insert()

	def test_role_less_session_is_refused(self):
		frappe.set_user(NOROLE_USER)
		with self.assertRaises(frappe.PermissionError):
			assessments.record_assessment(self.member.name, weight_kg=70.0)
		with self.assertRaises(frappe.PermissionError):
			assessments.get_progress(self.member.name)
		with self.assertRaises(frappe.PermissionError):
			assessments.get_assessments_due()
		with self.assertRaises(frappe.PermissionError):
			assessments.set_target(self.member.name, "Weight", 70.0)
