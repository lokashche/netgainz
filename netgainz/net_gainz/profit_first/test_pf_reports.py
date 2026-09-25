# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 11.6: Profit First over time agrees with the Profit First page."""

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import branch
from netgainz.net_gainz.profit_first import instant_assessment, reports

MANAGER = "pfr-manager@example.com"


class TestPFReports(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		permissions.ensure_roles()
		frappe.db.set_single_value("Profit First Settings", "pf_enabled", 1)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_this_month_matches_the_profit_first_page(self):
		fx.enrol_and_collect("PFR Paid", amount=2000.0)
		trend = reports.get_pf_reports(3)["trend"]
		self.assertEqual(len(trend), 3)
		page = instant_assessment.get_instant_assessment("This Month")
		self.assertEqual(trend[-1]["real_revenue"], page["real_revenue"])

	def test_the_owner_sees_sweeps_reserves_and_tax(self):
		r = reports.get_pf_reports(2)
		self.assertIn("sweeps", r)
		self.assertIn("reserves", r)
		self.assertEqual(len(r["tax"]), 2)

	def test_a_branch_manager_gets_their_trend_only(self):
		other = branch.create_branch(f"PFR Branch {frappe.generate_hash(length=5)}")["name"]
		if not frappe.db.exists("User", MANAGER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": MANAGER,
					"first_name": "PFR Manager",
					"send_welcome_email": 0,
					"roles": [{"role": permissions.GYM_STAFF}],
				}
			).insert(ignore_permissions=True)
		frappe.db.delete("User Permission", {"user": MANAGER})
		frappe.get_doc(
			{"doctype": "User Permission", "user": MANAGER, "allow": "Business Branch", "for_value": other}
		).insert(ignore_permissions=True)
		frappe.db.set_single_value("Business Settings", "pf_per_branch", 1)
		self.addCleanup(frappe.db.set_single_value, "Business Settings", "pf_per_branch", 0)

		frappe.set_user(MANAGER)
		r = reports.get_pf_reports(2)
		self.assertEqual(r["branches"], [other])
		self.assertNotIn("sweeps", r)
