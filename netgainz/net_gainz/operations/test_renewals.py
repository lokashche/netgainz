# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from netgainz.net_gainz.operations import renewals


def _member(name):
	return frappe.get_doc({"doctype": "Member", "full_name": name}).insert(ignore_permissions=True)


def _sub(member, next_renewal):
	return frappe.get_doc({"doctype": "Membership", "member": member, "next_renewal": next_renewal}).insert(
		ignore_permissions=True
	)


class TestRenewals(FrappeTestCase):
	def setUp(self):
		self.docs = []
		self.m_due = _member("Renewal Due Member")
		self.m_overdue = _member("Renewal Overdue Member")
		self.m_renewed = _member("Renewal Renewed Member")
		self.docs += [self.m_due, self.m_overdue, self.m_renewed]

		self.s_due = _sub(self.m_due.name, add_days(today(), 3))
		self.s_overdue = _sub(self.m_overdue.name, add_days(today(), -10))
		# A member who lapsed once but has since renewed: the OLD sub is overdue,
		# the NEW one is due soon — only the latest should count.
		self.s_old = _sub(self.m_renewed.name, add_days(today(), -5))
		self.s_new = _sub(self.m_renewed.name, add_days(today(), 4))
		self.docs += [self.s_due, self.s_overdue, self.s_old, self.s_new]

	def tearDown(self):
		for doc in reversed(self.docs):
			frappe.delete_doc(doc.doctype, doc.name, ignore_permissions=True, force=True)

	def test_due_soon_within_window(self):
		data = renewals.get_renewals(within_days=7)
		due_names = {r["subscription"] for r in data["due_soon"]}
		self.assertIn(self.s_due.name, due_names)

	def test_overdue_listed(self):
		data = renewals.get_renewals(within_days=7)
		overdue_names = {r["subscription"] for r in data["overdue"]}
		self.assertIn(self.s_overdue.name, overdue_names)

	def test_only_latest_membership_counts(self):
		data = renewals.get_renewals(within_days=7)
		due_names = {r["subscription"] for r in data["due_soon"]}
		overdue_names = {r["subscription"] for r in data["overdue"]}
		# The renewed member appears via the NEW sub (due soon), never the old one.
		self.assertIn(self.s_new.name, due_names)
		self.assertNotIn(self.s_old.name, overdue_names)
		self.assertNotIn(self.s_old.name, due_names)

	def test_reminder_disabled_returns_none(self):
		frappe.db.set_single_value("Business Settings", "renewal_reminders_enabled", 0)
		self.assertIsNone(renewals.notify_due_renewals())
