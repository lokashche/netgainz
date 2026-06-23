# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.doctype.instructor_commission_run.instructor_commission_run import (
	approve_commission_run,
	create_commission_run,
)

PERIOD = ("2026-05-01", "2026-05-31")


class TestInstructorCommissionRun(FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value("Business Settings", "commission_post_to_ledger", 0)
		self.coach = frappe.get_doc(
			{
				"doctype": "Instructor",
				"coach_name": "Run Test Coach",
				"status": "Active",
				"commission_type": "Fixed",
				"commission_amount": 1000,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		for name in frappe.get_all(
			"Instructor Commission Run", filters={"period_start": PERIOD[0]}, pluck="name"
		):
			doc = frappe.get_doc("Instructor Commission Run", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Instructor Commission Run", name, ignore_permissions=True, force=True)
		frappe.delete_doc("Instructor", self.coach.name, ignore_permissions=True, force=True)

	def test_run_snapshots_lines_and_total(self):
		"""Creating a run computes a frozen line per eligible coach + the total."""
		name = create_commission_run(*PERIOD)
		doc = frappe.get_doc("Instructor Commission Run", name)
		line = next(line for line in doc.lines if line.coach == self.coach.name)
		self.assertEqual(line.commission_amount, 1000.0)
		self.assertGreaterEqual(doc.total_commission, 1000.0)
		self.assertEqual(doc.docstatus, 0)

	def test_record_only_submit_posts_no_journal_entry(self):
		"""With posting disabled, approving records the run but posts nothing."""
		name = create_commission_run(*PERIOD)
		approve_commission_run(name)
		doc = frappe.get_doc("Instructor Commission Run", name)
		self.assertEqual(doc.docstatus, 1)
		self.assertFalse(doc.journal_entry)
