# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.operations import commissions


class TestCommissionMath(FrappeTestCase):
	"""Pure commission arithmetic — no database."""

	def test_fixed(self):
		self.assertEqual(commissions.commission_for("Fixed", 1500, 0, 0), 1500.0)

	def test_per_member(self):
		self.assertEqual(commissions.commission_for("Per Member", 200, 14, 0), 2800.0)

	def test_per_member_zero_members(self):
		self.assertEqual(commissions.commission_for("Per Member", 200, 0, 0), 0.0)

	def test_percentage(self):
		self.assertEqual(commissions.commission_for("Percentage", 10, 0, 40000), 4000.0)

	def test_percentage_rounds_to_paisa(self):
		# 7.5% of 1333.33 = 99.99975 -> 100.00
		self.assertEqual(commissions.commission_for("Percentage", 7.5, 0, 1333.33), 100.0)

	def test_unknown_type_is_zero(self):
		self.assertEqual(commissions.commission_for("Nope", 100, 5, 5), 0.0)


class TestComputeCommissions(FrappeTestCase):
	def setUp(self):
		self.coach = frappe.get_doc(
			{
				"doctype": "Coach",
				"coach_name": "Compute Test Coach",
				"status": "Active",
				"commission_type": "Per Member",
				"commission_amount": 200,
			}
		).insert(ignore_permissions=True)
		self.members = [
			frappe.get_doc(
				{"doctype": "Member", "full_name": n, "status": s, "coach": self.coach.name}
			).insert(ignore_permissions=True)
			for n, s in [
				("Compute Member A", "Active"),
				("Compute Member B", "Active"),
				("Compute Member C", "Inactive"),
			]
		]

	def tearDown(self):
		for m in self.members:
			frappe.delete_doc("Member", m.name, ignore_permissions=True, force=True)
		frappe.delete_doc("Coach", self.coach.name, ignore_permissions=True, force=True)

	def test_per_member_counts_only_active_members(self):
		result = commissions.compute_commissions("2026-06-01", "2026-06-30")
		line = next(line for line in result["lines"] if line["coach"] == self.coach.name)
		self.assertEqual(line["member_count"], 2)
		self.assertEqual(line["commission_amount"], 400.0)

	def test_total_includes_this_coach(self):
		result = commissions.compute_commissions("2026-06-01", "2026-06-30")
		self.assertGreaterEqual(result["total"], 400.0)
