# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz.profit_first import accounts as pf_accounts
from netgainz.net_gainz.profit_first import calc
from netgainz.net_gainz.profit_first import instant_assessment as ia


class TestGymExpense(FrappeTestCase):
	def _new_exp(self):
		doc = frappe.new_doc("Expense")
		doc.date = today()
		return doc

	# ---- validate (unchanged behaviour) ---------------------------------- #
	def test_validate_clears_frequency_when_not_recurring(self):
		doc = self._new_exp()
		doc.amount = 500
		doc.is_recurring = 0
		doc.frequency = "Monthly"
		doc.validate()
		self.assertEqual(doc.frequency, "")

	def test_validate_keeps_frequency_when_recurring(self):
		doc = self._new_exp()
		doc.amount = 500
		doc.is_recurring = 1
		doc.frequency = "Monthly"
		doc.validate()
		self.assertEqual(doc.frequency, "Monthly")

	def test_validate_rejects_zero_amount(self):
		doc = self._new_exp()
		doc.amount = 0
		doc.is_recurring = 0
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_validate_rejects_negative_amount(self):
		doc = self._new_exp()
		doc.amount = -100
		doc.is_recurring = 0
		self.assertRaises(frappe.ValidationError, doc.validate)

	# ---- WP-5 ledger posting --------------------------------------------- #
	def _company(self):
		return pf_accounts.default_company()

	def _an_expense_account(self):
		return frappe.db.get_value(
			"Account", {"company": self._company(), "root_type": "Expense", "is_group": 0}, "name"
		)

	def _category(self, name, expense_account=None, bucket="Operating Expenses"):
		if frappe.db.exists("Expense Category", name):
			frappe.db.set_value("Expense Category", name, "expense_account", expense_account)
			return name
		return (
			frappe.get_doc(
				{
					"doctype": "Expense Category",
					"category_name": name,
					"pf_bucket": bucket,
					"expense_account": expense_account,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _make_expense(self, amount, category):
		return frappe.get_doc(
			{
				"doctype": "Expense",
				"date": today(),
				"category": category,
				"amount": amount,
				"payment_mode": "Cash",
			}
		).insert(ignore_permissions=True)

	def test_submit_posts_nothing_when_ledger_posting_off(self):
		frappe.db.set_single_value("Business Settings", "expense_post_to_ledger", 0)
		cat = self._category("WP5 Cat Off", self._an_expense_account())
		exp = self._make_expense(500, cat)
		exp.submit()
		self.assertFalse(exp.journal_entry, "posting off -> reference-only, no JE")

	def test_submit_posts_balanced_je_and_cancel_reverses(self):
		frappe.db.set_single_value("Business Settings", "expense_post_to_ledger", 1)
		acc = self._an_expense_account()
		cat = self._category("WP5 Cat On", acc)
		exp = self._make_expense(1200, cat)
		exp.submit()
		self.assertTrue(exp.journal_entry, "posting on + account -> a JE posts")

		je = frappe.get_doc("Journal Entry", exp.journal_entry)
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(flt(je.total_debit), 1200.0)
		self.assertEqual(flt(je.total_credit), 1200.0)
		self.assertIn(acc, {r.account for r in je.accounts}, "debits the category's expense account")

		exp.reload()
		exp.cancel()
		exp.reload()
		self.assertFalse(exp.journal_entry, "cancel clears the link")
		self.assertEqual(frappe.db.get_value("Journal Entry", je.name, "docstatus"), 2, "JE reversed")

	def test_submit_posts_nothing_without_category_account(self):
		frappe.db.set_single_value("Business Settings", "expense_post_to_ledger", 1)
		cat = self._category("WP5 Cat NoAcct", None)
		exp = self._make_expense(700, cat)
		exp.submit()
		self.assertFalse(exp.journal_entry, "no category account -> skip posting")

	def test_pf_expense_read_excludes_cancelled(self):
		frappe.db.set_single_value("Business Settings", "expense_post_to_ledger", 1)
		frappe.db.delete("Expense")  # isolate the period read (rolled back after)
		acc = self._an_expense_account()
		cat = self._category("WP5 Cat PF", acc)
		self._make_expense(300, cat).submit()  # live -> counts
		gone = self._make_expense(999, cat)
		gone.submit()
		gone.reload()
		gone.cancel()  # docstatus=2 -> excluded

		has_field = frappe.get_meta("Expense Category").has_field("pf_bucket")
		buckets, _ = ia._expense_buckets_paise(today(), today(), has_field)
		self.assertEqual(buckets[calc.OPEX], calc.to_paise(300), "cancelled expense must not count")
