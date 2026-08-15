# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 9 OP-2: the enquiry → trial → member pipeline.

Pinned:

* an enquiry is branch-stamped from birth (R19);
* Lost demands a reason, and Joined cannot be set by hand — only the
  conversion sets it, so pipeline counts match the members that exist;
* Convert to Member prefills the member (name, phone, email, source, referrer,
  program, branch, joining date), links the enquiry, and is idempotent;
* a duplicate name is refused with a pointer to the existing member instead of
  minting a second member + a colliding ERPNext Customer;
* follow-ups due = open enquiries whose date has arrived, bucketed
  today/overdue; Joined and Lost never nag;
* the daily digest is opt-out and idempotent per user per day;
* conversion-by-source counts joined/lost/open and rates only the closed;
* the endpoints are staff-callable and closed to role-less users.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.operations import enquiries

STAFF_USER = "op2-frontdesk@example.com"
NOROLE_USER = "op2-visitor@example.com"


def _enquiry(name, **fields):
	return frappe.get_doc({"doctype": "Enquiry", "full_name": name, **fields}).insert(ignore_permissions=True)


class TestEnquiries(FrappeTestCase):
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

	# ---- the doctype ------------------------------------------------------- #
	def test_enquiry_branch_stamped_and_defaults(self):
		e = _enquiry("OP2 Walkin Person")
		self.assertEqual(e.status, "New")
		self.assertEqual(e.source, "Walk-in")
		self.assertEqual(e.branch, "Main")

	def test_lost_requires_a_reason(self):
		e = _enquiry("OP2 Lost Person")
		e.status = "Lost"
		with self.assertRaises(frappe.ValidationError):
			e.save(ignore_permissions=True)
		e.reload()
		e.status = "Lost"
		e.lost_reason = "Too expensive"
		e.save(ignore_permissions=True)
		self.assertEqual(e.status, "Lost")

	def test_joined_cannot_be_set_by_hand(self):
		e = _enquiry("OP2 Handjoin Person")
		e.status = "Joined"
		with self.assertRaises(frappe.ValidationError):
			e.save(ignore_permissions=True)

	# ---- conversion --------------------------------------------------------- #
	def test_convert_prefills_links_and_stamps(self):
		e = _enquiry(
			"OP2 Convert Person",
			phone="+91 88888 77777",
			email="op2convert@example.com",
			source="Instagram",
		)
		result = enquiries.convert_to_member(e.name)
		self.assertFalse(result["already_converted"])

		member = frappe.get_doc("Member", result["member"])
		self.assertEqual(member.full_name, "OP2 Convert Person")
		self.assertEqual(member.phone, "+91 88888 77777")
		self.assertEqual(member.email, "op2convert@example.com")
		self.assertEqual(member.source_of_reference, "Social Media")
		self.assertEqual(member.status, "Active")
		self.assertEqual(str(member.date_of_joining), today())

		e.reload()
		self.assertEqual(e.status, "Joined")
		self.assertEqual(e.member, member.name)
		self.assertEqual(str(e.joined_on), today())

	def test_convert_carries_the_enquiry_branch(self):
		# R19: the member is created at the enquiry's branch, and (via the OP-1
		# resolver) everything member-bearing follows from there.
		b = frappe.get_doc({"doctype": "Business Branch", "branch_name": "OP2 Annex"}).insert(
			ignore_permissions=True
		)
		e = _enquiry("OP2 Annex Person", branch=b.name)
		result = enquiries.convert_to_member(e.name)
		self.assertEqual(frappe.db.get_value("Member", result["member"], "branch"), b.name)

	def test_convert_is_idempotent(self):
		e = _enquiry("OP2 Twice Person")
		first = enquiries.convert_to_member(e.name)
		second = enquiries.convert_to_member(e.name)
		self.assertTrue(second["already_converted"])
		self.assertEqual(first["member"], second["member"])
		self.assertEqual(frappe.db.count("Member", {"full_name": "OP2 Twice Person"}), 1)

	def test_convert_refuses_a_duplicate_name(self):
		frappe.get_doc({"doctype": "Member", "full_name": "OP2 Duplicate Person", "status": "Active"}).insert(
			ignore_permissions=True
		)
		e = _enquiry("OP2 Duplicate Person")
		with self.assertRaises(frappe.ValidationError):
			enquiries.convert_to_member(e.name)
		e.reload()
		self.assertEqual(e.status, "New", "a refused conversion leaves the enquiry open")

	# ---- follow-ups ---------------------------------------------------------- #
	def test_followups_bucketed_today_vs_overdue(self):
		e_today = _enquiry("OP2 Today Person", next_follow_up=today())
		e_over = _enquiry("OP2 Overdue Person", status="Contacted", next_follow_up=add_days(today(), -3))
		e_future = _enquiry("OP2 Future Person", next_follow_up=add_days(today(), 2))
		data = enquiries.get_followups()
		today_names = {r["enquiry"] for r in data["due_today"]}
		overdue_names = {r["enquiry"] for r in data["overdue"]}
		self.assertIn(e_today.name, today_names)
		self.assertIn(e_over.name, overdue_names)
		row = next(r for r in data["overdue"] if r["enquiry"] == e_over.name)
		self.assertEqual(row["days_overdue"], 3)
		self.assertNotIn(e_future.name, today_names | overdue_names)

	def test_closed_enquiries_never_nag(self):
		e = _enquiry(
			"OP2 Closed Person",
			next_follow_up=add_days(today(), -1),
			status="Lost",
			lost_reason="Moved away",
		)
		data = enquiries.get_followups()
		names = {r["enquiry"] for r in data["due_today"] + data["overdue"]}
		self.assertNotIn(e.name, names)

	def test_followup_digest_disabled_returns_none(self):
		frappe.db.set_single_value("Business Settings", "followup_reminders_enabled", 0)
		self.assertIsNone(enquiries.notify_followups())

	def test_followup_digest_idempotent_per_day(self):
		frappe.db.set_single_value("Business Settings", "followup_reminders_enabled", 1)
		_enquiry("OP2 Digest Person", next_follow_up=today())
		first = enquiries.notify_followups()
		self.assertIsNotNone(first)
		second = enquiries.notify_followups()
		self.assertEqual(second["notified"], 0)

	# ---- conversion by source ------------------------------------------------ #
	def test_conversion_by_source_rates_only_the_closed(self):
		frappe.db.delete("Enquiry")
		joined = _enquiry("OP2 Src Joined", source="Instagram")
		enquiries.convert_to_member(joined.name)
		_enquiry("OP2 Src Lost", source="Instagram", status="Lost", lost_reason="Price")
		_enquiry("OP2 Src Open", source="Instagram")
		_enquiry("OP2 Src Walk", source="Walk-in")

		data = enquiries.conversion_by_source()
		insta = next(s for s in data["sources"] if s["source"] == "Instagram")
		self.assertEqual(insta["total"], 3)
		self.assertEqual(insta["joined"], 1)
		self.assertEqual(insta["lost"], 1)
		self.assertEqual(insta["open"], 1)
		self.assertEqual(insta["conversion_pct"], 50.0)
		walk = next(s for s in data["sources"] if s["source"] == "Walk-in")
		self.assertIsNone(walk["conversion_pct"], "an all-open source has no rate yet")

	# ---- who may call it ----------------------------------------------------- #
	def test_staff_session_can_convert(self):
		e = _enquiry("OP2 StaffConvert Person")
		frappe.set_user(STAFF_USER)
		result = enquiries.convert_to_member(e.name)
		self.assertTrue(result["member"])

	def test_role_less_session_is_refused(self):
		e = _enquiry("OP2 Locked Person")
		frappe.set_user(NOROLE_USER)
		with self.assertRaises(frappe.PermissionError):
			enquiries.convert_to_member(e.name)
		with self.assertRaises(frappe.PermissionError):
			enquiries.get_followups_due()
		with self.assertRaises(frappe.PermissionError):
			enquiries.conversion_by_source()
