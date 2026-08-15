# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 9 OP-1: gym-wide check-in & the absence/churn-risk read-model.

Pinned:

* a desk tap stamps the visit server-side; repeats are allowed and surfaced,
  never blocked;
* a check-in inherits the member's branch (R19) without the desk sending one;
* the overdue prompt reads the stored membership status PLUS the read-time
  due-date overlay (nothing recomputes status at midnight — the stale
  Pending-past-due case must still prompt), and it is a prompt only;
* a "visit" is a floor check-in OR an attended class — a class-only member is
  never absent;
* absence is only measured from the day visit-recording began (earliest visit on
  record) — before that the list is empty, so shipping the feature never flags a
  gym full of long-imported members;
* the desk endpoints are staff-callable but closed to role-less users
  (exercised as real sessions — as Administrator they would pass vacuously).
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_to_date, now_datetime, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.operations import checkin

STAFF_USER = "op1-frontdesk@example.com"
NOROLE_USER = "op1-visitor@example.com"


def _member(name, **fields):
	return frappe.get_doc({"doctype": "Member", "full_name": name, "status": "Active", **fields}).insert(
		ignore_permissions=True
	)


def _backdate_creation(doctype, name, days):
	frappe.db.set_value(
		doctype, name, "creation", add_to_date(now_datetime(), days=-days), update_modified=False
	)


def _check_in(member, days_ago=0):
	doc = frappe.get_doc({"doctype": "Member Check-in", "member": member})
	if days_ago:
		doc.timestamp = add_to_date(now_datetime(), days=-days_ago)
	return doc.insert(ignore_permissions=True)


class TestCheckin(FrappeTestCase):
	def setUp(self):
		permissions.ensure_roles()
		self._user(STAFF_USER, permissions.GYM_STAFF)
		self._user(NOROLE_USER, None)
		self.addCleanup(frappe.set_user, "Administrator")

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

	# ---- the check-in row ------------------------------------------------- #
	def test_timestamp_stamped_when_blank(self):
		m = _member("OP1 Stamp Member")
		chk = frappe.get_doc({"doctype": "Member Check-in", "member": m.name}).insert(ignore_permissions=True)
		self.assertIsNotNone(chk.timestamp)
		self.assertEqual(chk.member_name, "OP1 Stamp Member")

	def test_manual_backdate_kept(self):
		m = _member("OP1 Backdate Member")
		stamp = add_to_date(now_datetime(), days=-3)
		chk = frappe.get_doc(
			{"doctype": "Member Check-in", "member": m.name, "source": "Manual", "timestamp": stamp}
		).insert(ignore_permissions=True)
		self.assertEqual(str(chk.timestamp), str(stamp))

	def test_check_in_defaults_to_main_branch(self):
		m = _member("OP1 Branch Member")
		chk = _check_in(m.name)
		self.assertEqual(chk.branch, "Main")

	def test_repeat_check_in_allowed_and_surfaced(self):
		m = _member("OP1 Repeat Member")
		first = checkin.record_check_in(m.name)
		self.assertIsNone(first["previous_today"])
		second = checkin.record_check_in(m.name)
		self.assertIsNotNone(second["previous_today"])
		self.assertEqual(frappe.db.count("Member Check-in", {"member": m.name}), 2)

	# ---- the soft prompt --------------------------------------------------- #
	def test_no_alert_without_memberships(self):
		m = _member("OP1 Clean Member")
		self.assertIsNone(checkin.membership_alert(m.name))

	def test_alert_for_stored_overdue(self):
		m = _member("OP1 Overdue Member")
		ms = frappe.get_doc({"doctype": "Membership", "member": m.name}).insert(ignore_permissions=True)
		frappe.db.set_value("Membership", ms.name, {"status": "Overdue", "balance_due": 900})
		alert = checkin.membership_alert(m.name)
		self.assertTrue(alert["overdue"])
		self.assertEqual(alert["balance_due"], 900)
		self.assertIn(ms.name, alert["memberships"])

	def test_overlay_catches_stale_pending_past_due(self):
		# The stale-status case: due date passed since the last billing event, so
		# the stored status still says Pending — the desk must prompt anyway.
		m = _member("OP1 Stale Member")
		ms = frappe.get_doc({"doctype": "Membership", "member": m.name}).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Membership",
			ms.name,
			{"status": "Pending", "balance_due": 500, "due_date": add_days(today(), -2)},
		)
		alert = checkin.membership_alert(m.name)
		self.assertTrue(alert["overdue"])
		self.assertEqual(alert["balance_due"], 500)

	def test_pending_not_yet_due_does_not_prompt(self):
		m = _member("OP1 NotDue Member")
		ms = frappe.get_doc({"doctype": "Membership", "member": m.name}).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Membership",
			ms.name,
			{"status": "Pending", "balance_due": 500, "due_date": add_days(today(), 5)},
		)
		self.assertIsNone(checkin.membership_alert(m.name))

	def test_frozen_member_prompts_but_records(self):
		m = _member("OP1 Frozen Member")
		frappe.db.set_value("Member", m.name, "status", "Frozen")
		result = checkin.record_check_in(m.name)
		self.assertTrue(result["alert"]["frozen"])
		# D3: prompted, never blocked — the visit is still on record.
		self.assertTrue(frappe.db.exists("Member Check-in", result["check_in"]))

	# ---- desk search -------------------------------------------------------- #
	def test_find_members_by_code_name_and_phone(self):
		m = _member("OP1 Searchable Zed", phone="+91 90000 12345")
		by_name = {r["name"] for r in checkin.find_members("Searchable Ze")}
		by_code = {r["name"] for r in checkin.find_members(m.name)}
		by_phone = {r["name"] for r in checkin.find_members("90000 123")}
		self.assertIn(m.name, by_name)
		self.assertIn(m.name, by_code)
		self.assertIn(m.name, by_phone)

	def test_find_members_flags_already_in(self):
		m = _member("OP1 AlreadyIn Member")
		self.assertIsNone(
			next(r for r in checkin.find_members("AlreadyIn") if r["name"] == m.name)["checked_in_today"]
		)
		checkin.record_check_in(m.name)
		row = next(r for r in checkin.find_members("AlreadyIn") if r["name"] == m.name)
		self.assertIsNotNone(row["checked_in_today"])

	# ---- absence / churn risk ---------------------------------------------- #
	def test_absent_member_flagged(self):
		m = _member("OP1 Absent Member")
		_backdate_creation("Member", m.name, 40)
		_check_in(m.name, days_ago=20)
		data = checkin.get_absences(threshold_days=14)
		row = next(r for r in data["absent"] if r["member"] == m.name)
		self.assertEqual(row["days_absent"], 20)
		self.assertFalse(row["never_visited"])

	def test_recent_visitor_not_flagged(self):
		m = _member("OP1 Regular Member")
		_backdate_creation("Member", m.name, 40)
		_check_in(m.name, days_ago=3)
		data = checkin.get_absences(threshold_days=14)
		self.assertNotIn(m.name, {r["member"] for r in data["absent"]})

	def test_class_attendance_counts_as_visit(self):
		# A class-only member must never read as absent: the read-model unions
		# floor check-ins with attended class bookings.
		m = _member("OP1 ClassOnly Member")
		_backdate_creation("Member", m.name, 40)
		_check_in(m.name, days_ago=20)
		session = frappe.get_doc(
			{"doctype": "Session", "title": "OP1 Yoga", "start_time": now_datetime()}
		).insert(ignore_permissions=True)
		booking = frappe.get_doc(
			{
				"doctype": "Session Booking",
				"class_session": session.name,
				"member": m.name,
				"status": "Attended",
			}
		).insert(ignore_permissions=True)
		self.assertIsNotNone(booking.check_in_time)
		data = checkin.get_absences(threshold_days=14)
		self.assertNotIn(m.name, {r["member"] for r in data["absent"]})

	def test_no_visits_recorded_means_no_absences(self):
		# Before the first ever visit there is nothing to measure — shipping the
		# feature must not flag a gym full of members imported weeks ago.
		frappe.db.delete("Member Check-in")
		frappe.db.delete("Session Booking")
		old = _member("OP1 Preload Member")
		_backdate_creation("Member", old.name, 60)
		data = checkin.get_absences(threshold_days=14)
		self.assertEqual(data["absent"], [])
		self.assertIsNone(data["tracking_started"])

	def test_never_visited_measured_from_tracking_start(self):
		# Tracking began 30 days ago (another member's visit). A member imported
		# 60 days ago who has never come in is 30 days absent — not 60.
		frappe.db.delete("Member Check-in")
		frappe.db.delete("Session Booking")
		visitor = _member("OP1 FirstVisitor Member")
		_check_in(visitor.name, days_ago=30)
		ghost = _member("OP1 Ghost Member")
		_backdate_creation("Member", ghost.name, 60)
		fresh = _member("OP1 New Member")
		data = checkin.get_absences(threshold_days=14)
		rows = {r["member"]: r for r in data["absent"]}
		self.assertIn(ghost.name, rows)
		self.assertTrue(rows[ghost.name]["never_visited"])
		self.assertEqual(rows[ghost.name]["days_absent"], 30)
		# A member created today is measured from today — not flagged.
		self.assertNotIn(fresh.name, rows)

	def test_inactive_member_not_flagged(self):
		m = _member("OP1 Left Member")
		_backdate_creation("Member", m.name, 60)
		frappe.db.set_value("Member", m.name, "status", "Inactive")
		data = checkin.get_absences(threshold_days=14)
		self.assertNotIn(m.name, {r["member"] for r in data["absent"]})

	# ---- the daily digest --------------------------------------------------- #
	def test_absence_alert_disabled_returns_none(self):
		frappe.db.set_single_value("Business Settings", "absence_alerts_enabled", 0)
		self.assertIsNone(checkin.notify_absences())

	def test_absence_digest_idempotent_per_day(self):
		frappe.db.set_single_value("Business Settings", "absence_alerts_enabled", 1)
		visitor = _member("OP1 DigestVisitor Member")
		_check_in(visitor.name, days_ago=30)
		m = _member("OP1 Digest Member")
		_backdate_creation("Member", m.name, 30)
		first = checkin.notify_absences()
		self.assertIsNotNone(first)
		second = checkin.notify_absences()
		self.assertEqual(second["notified"], 0)

	# ---- who may call the desk --------------------------------------------- #
	def test_staff_session_can_record(self):
		m = _member("OP1 StaffDesk Member")
		frappe.set_user(STAFF_USER)
		result = checkin.record_check_in(m.name)
		self.assertTrue(result["check_in"])

	def test_role_less_session_is_refused(self):
		m = _member("OP1 Locked Member")
		frappe.set_user(NOROLE_USER)
		with self.assertRaises(frappe.PermissionError):
			checkin.record_check_in(m.name)
		with self.assertRaises(frappe.PermissionError):
			checkin.find_members("Locked")
		with self.assertRaises(frappe.PermissionError):
			checkin.get_churn_risk()
