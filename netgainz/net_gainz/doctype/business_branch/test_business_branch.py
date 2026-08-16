# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.profit_first import accounts as pf_accounts


class TestBusinessBranch(FrappeTestCase):
	def test_defaults_company_when_blank(self):
		b = frappe.get_doc({"doctype": "Business Branch", "branch_name": "WP3 Default Co"})
		b.insert(ignore_permissions=True)
		self.assertEqual(b.company, pf_accounts.default_company())

	def test_rejects_cost_center_from_another_company(self):
		company = pf_accounts.default_company()
		other = frappe.db.get_value("Company", {"name": ["!=", company]}, "name")
		other_cc = (
			frappe.db.get_value("Cost Center", {"company": other, "is_group": 0}, "name") if other else None
		)
		if not other_cc:
			self.skipTest("no second company with a cost center on this site")
		b = frappe.get_doc(
			{
				"doctype": "Business Branch",
				"branch_name": "WP3 Mismatch",
				"company": company,
				"cost_center": other_cc,
			}
		)
		with self.assertRaises(frappe.ValidationError):
			b.insert(ignore_permissions=True)
