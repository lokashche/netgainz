# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""The dashboard's "Income this month" figure.

It used to be summed in the owner-app from ``Membership.fee_collected`` / ``tariff``,
which nothing writes any more, so real payments showed as ₹0. These pin that it now
comes from the books:

* a Payment Entry counts as cash received, with ``fee_collected`` left empty;
* it is the same number Profit First reads, to the paisa;
* an invoice counts as billed before it is paid, and the Cash/Accrual setting picks
  which of the two the dashboard shows;
* money outside the month stays out;
* owner and front desk may read it; anyone else is refused.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, flt, get_first_day, get_last_day, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing, income_report
from netgainz.net_gainz.accounting import billing_fixtures as fx

STAFF_USER = "income-frontdesk@example.com"
OUTSIDER_USER = "income-outsider@example.com"


class TestIncomeReport(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		permissions.ensure_roles()
		for email, roles in ((STAFF_USER, [permissions.GYM_STAFF]), (OUTSIDER_USER, [])):
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": email.split("@")[0],
						"send_welcome_email": 0,
						"roles": [{"role": r} for r in roles],
					}
				).insert(ignore_permissions=True)
		original = frappe.db.get_single_value("Business Settings", "accounting_method") or "Cash"
		frappe.db.set_single_value("Business Settings", "accounting_method", "Cash")
		self.addCleanup(frappe.db.set_single_value, "Business Settings", "accounting_method", original)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_a_payment_is_income_even_though_fee_collected_stays_empty(self):
		ms = fx.enrol_and_collect("INC Paid", amount=1500.0)
		# The premise of the old bug: the field the dashboard summed is never written.
		self.assertEqual(flt(ms.fee_collected), 0.0)
		self.assertFalse(ms.paid_date)

		result = income_report.income_for_period()
		self.assertEqual(result["basis"], "Cash")
		self.assertEqual(flt(result["collected"]), 1500.0)
		self.assertEqual(flt(result["income"]), 1500.0)

	def test_it_matches_profit_first_to_the_paisa(self):
		fx.enrol_and_collect("INC PF A", amount=1000.0)
		fx.enrol_and_collect("INC PF B", amount=2499.5)
		start, end = get_first_day(today()), get_last_day(today())
		self.assertEqual(
			income_report.income_for_period()["collected"],
			billing.membership_collected_paise(start, end) / 100,
		)

	def test_an_unpaid_invoice_is_billed_but_not_received(self):
		fx.enrol("INC Unpaid", amount=1200.0)
		result = income_report.income_for_period()
		self.assertEqual(flt(result["billed"]), 1200.0)
		self.assertEqual(flt(result["collected"]), 0.0)
		self.assertEqual(flt(result["income"]), 0.0, "cash basis counts money received, not billed")

	def test_accrual_basis_shows_what_was_billed(self):
		fx.enrol("INC Accrual", amount=1200.0)
		frappe.db.set_single_value("Business Settings", "accounting_method", "Accrual")
		result = income_report.income_for_period()
		self.assertEqual(result["basis"], "Accrual")
		self.assertEqual(flt(result["income"]), 1200.0)

	def test_money_outside_the_month_stays_out(self):
		fx.enrol_and_collect("INC Window", amount=1000.0)
		next_month = add_months(get_first_day(today()), 1)
		result = income_report.income_for_period(next_month, get_last_day(next_month))
		self.assertEqual(flt(result["collected"]), 0.0)
		self.assertEqual(flt(result["billed"]), 0.0)

	def test_front_desk_may_read_it_and_others_may_not(self):
		fx.enrol_and_collect("INC Perms", amount=1000.0)
		frappe.set_user(STAFF_USER)
		self.assertEqual(flt(income_report.get_income()["income"]), 1000.0)
		frappe.set_user(OUTSIDER_USER)
		with self.assertRaises(frappe.PermissionError):
			income_report.get_income()
