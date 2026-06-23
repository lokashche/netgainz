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


class TestCommissionRounding(FrappeTestCase):
	"""Commission money rounds half-AWAY-from-zero in integer paise, and is
	independent of System Settings.rounding_method (the old flt() path honoured
	it, so the same fee could yield a different paisa across sites)."""

	def setUp(self):
		self._orig_method = frappe.db.get_single_value("System Settings", "rounding_method")

	def tearDown(self):
		frappe.db.set_single_value("System Settings", "rounding_method", self._orig_method)

	def test_half_paise_rounds_away_from_zero(self):
		# 50% of ₹0.01 = 0.5 paise -> 1 paise (away from zero), NOT 0 (bankers).
		self.assertEqual(commissions.commission_for("Percentage", 50, 0, 0.01), 0.01)
		# 10% of ₹0.05 = 0.5 paise -> 1 paise.
		self.assertEqual(commissions.commission_for("Percentage", 10, 0, 0.05), 0.01)

	def test_independent_of_system_rounding_method(self):
		results = {}
		for method in ("Banker's Rounding", "Commercial Rounding"):
			frappe.db.set_single_value("System Settings", "rounding_method", method)
			results[method] = commissions.commission_for("Percentage", 50, 0, 0.01)
		self.assertEqual(results["Banker's Rounding"], results["Commercial Rounding"])
		self.assertEqual(results["Banker's Rounding"], 0.01)


class TestComputeCommissions(FrappeTestCase):
	def setUp(self):
		self.coach = frappe.get_doc(
			{
				"doctype": "Instructor",
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
		frappe.delete_doc("Instructor", self.coach.name, ignore_permissions=True, force=True)

	def test_per_member_counts_only_active_members(self):
		result = commissions.compute_commissions("2026-06-01", "2026-06-30")
		line = next(line for line in result["lines"] if line["coach"] == self.coach.name)
		self.assertEqual(line["member_count"], 2)
		self.assertEqual(line["commission_amount"], 400.0)

	def test_total_includes_this_coach(self):
		result = commissions.compute_commissions("2026-06-01", "2026-06-30")
		self.assertGreaterEqual(result["total"], 400.0)
