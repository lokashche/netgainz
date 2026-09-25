# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 12.2: loaded billing history into the official books.

Pinned: a history row becomes one submitted invoice for what was charged and one
payment for what was paid, marked with its row; that money counts as membership
income (Profit First / dashboard); a second run posts nothing; the month check
reads "matches" once posted; a row in a month Profit First or a commission run has
closed is refused, and so is one paid more than it was charged.

``_post_all`` commits per row (a failing row must not undo the good ones), so the
billing slate is cleared before and after each test.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_first_day, get_last_day, getdate, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.loader import history_books


def _history_row(tag, tariff=1000, paid=600):
	plan = fx.make_plan(f"HB {tag} Plan", amount=0)
	member = fx.make_member(f"HB {tag} Member", plan.name)
	return frappe.get_doc(
		{
			"doctype": "Membership",
			"member": member.name,
			"membership_plan": plan.name,
			"is_backfill": 1,
			"tariff": tariff,
			"fee_collected": paid,
			"due_date": get_first_day(today()),
			"status": "Overdue" if paid < tariff else "Paid",
		}
	).insert(ignore_permissions=True)


class TestHistoryBooks(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		frappe.cache().delete_value(history_books._LAST_RUN)

	def tearDown(self):
		fx.clear_billing_data()
		# Posting commits per row, so the test's members and plans outlive the rollback.
		for name in frappe.get_all("Member", filters={"full_name": ["like", "HB %"]}, pluck="name"):
			customer = frappe.db.get_value("Member", name, "customer")
			frappe.delete_doc("Member", name, force=True, ignore_permissions=True)
			if customer and frappe.db.exists("Customer", customer):
				frappe.delete_doc("Customer", customer, force=True, ignore_permissions=True)
		for name in frappe.get_all("Membership Plan", filters={"name": ["like", "HB %"]}, pluck="name"):
			frappe.delete_doc("Membership Plan", name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def _month(self, preview):
		key = f"{getdate(today()):%Y-%m}"
		return next(m for m in preview["months"] if m["month"] == key)

	def test_posts_invoice_and_payment_once(self):
		row = _history_row("once")
		before = history_books.preview()
		self.assertEqual(before["pending"], 1)
		self.assertFalse(self._month(before)["matches"])

		result = history_books._post_all()
		self.assertEqual(result["posted"], 1, result["failed"])
		si = frappe.get_all(
			"Sales Invoice",
			filters={"membership": row.name, "docstatus": 1},
			fields=["name", "grand_total", "outstanding_amount", "posting_date"],
		)
		self.assertEqual(len(si), 1)
		self.assertEqual(si[0].grand_total, 1000)
		self.assertEqual(si[0].outstanding_amount, 400)  # still owed, as in the sheet
		self.assertEqual(getdate(si[0].posting_date), get_first_day(today()))

		after = history_books.preview()
		self.assertEqual(after["pending"], 0)
		self.assertTrue(self._month(after)["matches"])

		# Again: nothing new.
		self.assertEqual(history_books._post_all()["posted"], 0)
		self.assertEqual(frappe.db.count("Sales Invoice", {"membership": row.name}), 1)

	def test_history_cash_counts_as_membership_income(self):
		row = _history_row("cash", tariff=1000, paid=1000)
		result = history_books._post_all()
		self.assertEqual(result["posted"], 1, result["failed"])
		collected = billing.membership_collected_paise(get_first_day(today()), get_last_day(today()))
		# Ex-GST, like all membership income (GST collected is not revenue).
		net = frappe.db.get_value("Sales Invoice", {"membership": row.name}, "net_total")
		self.assertGreater(collected, 0)
		self.assertEqual(collected, round(net * 100))

	def test_closed_month_is_refused(self):
		_history_row("locked")
		with patch.object(history_books, "locked_until", return_value=getdate(today())):
			preview = history_books.preview()
			self.assertEqual(preview["pending"], 0)
			self.assertIn("already closed", preview["blocked"][0]["reason"])
			self.assertEqual(history_books._post_all()["posted"], 0)

	def test_overpaid_row_is_refused(self):
		_history_row("over", tariff=500, paid=800)
		self.assertIn("more than", history_books.preview()["blocked"][0]["reason"])
