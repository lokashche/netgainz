# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 12.1: a new gym sets itself up from the owner-app.

The ERPNext setup routine itself only runs on a site with no Company, which the test
site is not — so these pin what is ours: the financial year and abbreviation we hand
it, the arguments (never an ``email``: that would swap the owner's session), the
once-only guard, and the checklist.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz import onboarding


class TestOnboarding(FrappeTestCase):
	def test_financial_year_contains_today(self):
		self.assertEqual(onboarding.financial_year(4, "2026-09-25"), ("2026-04-01", "2027-03-31"))
		self.assertEqual(onboarding.financial_year(4, "2026-02-10"), ("2025-04-01", "2026-03-31"))
		self.assertEqual(onboarding.financial_year(1, "2026-02-10"), ("2026-01-01", "2026-12-31"))

	def test_company_abbr(self):
		self.assertEqual(onboarding.company_abbr("Iron Forge Fitness"), "IFF")
		self.assertEqual(onboarding.company_abbr("Kinetic Edge"), "KE")
		self.assertEqual(onboarding.company_abbr("Pulse"), "PUL")

	def test_refuses_a_second_setup(self):
		with self.assertRaisesRegex(frappe.ValidationError, "already set up"):
			onboarding.setup_business("Another Gym")

	def test_hands_erpnext_the_business_and_no_email(self):
		with (
			patch.object(onboarding.pf_accounts, "default_company", return_value=None),
			patch.object(onboarding, "is_job_enqueued", return_value=False),
			patch.object(onboarding.frappe, "enqueue") as enqueue,
		):
			result = onboarding.setup_business("Pulse Studio", 4, "LLP", 0, None, "HDFC Current")
		self.assertEqual(result, {"status": "running"})
		args = enqueue.call_args.kwargs["args"]
		self.assertNotIn("email", args)
		self.assertEqual(args["company_abbr"], "PS")
		self.assertEqual(args["bank_account"], "HDFC Current")
		self.assertIsNone(args["company_gstin"])
		self.assertTrue(args["fy_start_date"].endswith("-04-01"))
		self.assertEqual(frappe.db.get_single_value("Business Settings", "constitution"), "LLP")

	def test_gst_registered_needs_a_gstin(self):
		with (
			patch.object(onboarding.pf_accounts, "default_company", return_value=None),
			patch.object(onboarding, "is_job_enqueued", return_value=False),
			patch.object(onboarding.frappe, "enqueue"),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "GSTIN"):
				onboarding.setup_business("Pulse Studio", 4, "Proprietorship", 1, "")

	def test_checklist(self):
		status = onboarding.get_setup_status()
		self.assertTrue(status["company"])
		steps = {s["key"]: s for s in status["steps"]}
		self.assertTrue(steps["business"]["done"])
		self.assertEqual(
			list(steps), ["business", "owner_login", "branches", "plans", "profit_first", "members"]
		)
