# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 11.5: the owner-app's financial reports are ERPNext's own, flattened."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_first_day, get_last_day, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import financial_reports as fr

DESK = "fr-desk@example.com"


class TestFinancialReports(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		permissions.ensure_roles()
		if not frappe.db.exists("User", DESK):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": DESK,
					"first_name": "FR Desk",
					"send_welcome_email": 0,
					"roles": [{"role": permissions.GYM_STAFF}],
				}
			).insert(ignore_permissions=True)
		self.addCleanup(frappe.set_user, "Administrator")
		self.start, self.end = str(get_first_day(today())), str(get_last_day(today()))

	def test_every_report_runs_and_flattens(self):
		fx.enrol_and_collect("FR Income", amount=1500.0)
		for key in fr.REPORTS:
			with self.subTest(report=key):
				data = fr.get_financial_report(key, self.start, self.end, "Monthly")
				self.assertTrue(data["columns"])
				self.assertTrue(all("_indent" in r for r in data["rows"]))

		pnl = fr.get_financial_report("profit_and_loss", self.start, self.end, "Monthly")
		income = next(r for r in pnl["rows"] if r["account"] == "Income")
		self.assertGreaterEqual(income["total"], 1500.0)

	def test_the_accountant_pack_is_an_excel_file(self):
		fr.accountant_pack(self.start, self.end)
		self.assertEqual(frappe.response["type"], "binary")
		self.assertTrue(frappe.response["filecontent"].startswith(b"PK"))  # xlsx is a zip

	def test_the_books_are_the_owners(self):
		frappe.set_user(DESK)
		with self.assertRaises(frappe.PermissionError):
			fr.get_financial_report("profit_and_loss", self.start, self.end)

	def test_a_book_with_no_such_account_is_empty_not_the_whole_ledger(self):
		fx.enrol_and_collect("FR Book", amount=500.0)
		for acc in frappe.get_all("Account", filters={"account_type": "Bank", "is_group": 0}, pluck="name"):
			frappe.db.set_value("Account", acc, "account_type", "")
		data = fr.get_financial_report("bank_book", self.start, self.end)
		self.assertEqual(data["rows"], [], "no bank account -> an empty Bank Book, not the whole ledger")
