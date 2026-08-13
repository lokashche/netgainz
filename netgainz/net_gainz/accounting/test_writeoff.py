# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""WP-8: writing off uncollectable membership dues.

A write-off moves a receivable to bad-debt expense. It settles what the member
owes WITHOUT any cash changing hands, so Profit First must not move — and the
membership must stop claiming the money is still collectable.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz.accounting import billing, writeoff
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestWriteOff(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	def _outstanding(self, si):
		return flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))

	def _cash(self, membership):
		customer = frappe.db.get_value("Member", membership.member, "customer")
		return billing.collected_paise(add_days(today(), -1), today(), [customer])

	# ---- the posting ----------------------------------------------------- #
	def test_write_off_clears_the_receivable(self):
		ms = fx.enrol("WO Basic", amount=2000.0)
		si = ms.current_sales_invoice
		self.assertGreater(self._outstanding(si), 0)

		result = writeoff.write_off_membership(ms.name, reason="Member Unreachable")

		self.assertEqual(self._outstanding(si), 0.0)
		je = frappe.get_doc("Journal Entry", result["journal_entry"])
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(je.voucher_type, "Write Off Entry")

	def test_write_off_debits_an_expense_and_credits_the_member(self):
		ms = fx.enrol("WO Ledger", amount=2000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)
		customer = frappe.db.get_value("Member", ms.member, "customer")

		je = frappe.get_doc("Journal Entry", writeoff.write_off_membership(ms.name)["journal_entry"])
		debit = next(r for r in je.accounts if flt(r.debit_in_account_currency))
		credit = next(r for r in je.accounts if flt(r.credit_in_account_currency))

		self.assertEqual(frappe.db.get_value("Account", debit.account, "root_type"), "Expense")
		self.assertEqual(credit.party_type, "Customer")
		self.assertEqual(credit.party, customer)
		self.assertEqual(credit.reference_name, si)
		self.assertAlmostEqual(flt(debit.debit_in_account_currency), owed, places=2)
		self.assertAlmostEqual(flt(credit.credit_in_account_currency), owed, places=2)

	def test_write_off_moves_no_profit_first_cash(self):
		ms = fx.enrol("WO NoCash", amount=2000.0)
		self.assertEqual(self._cash(ms), 0)
		writeoff.write_off_membership(ms.name)
		self.assertEqual(self._cash(ms), 0, "a write-off is a loss, not a collection")

	# ---- what the owner sees --------------------------------------------- #
	def test_written_off_membership_says_so_instead_of_paid(self):
		"""ERPNext marks the invoice "Paid" once the receivable is gone. For the
		owner that is a lie — nobody paid."""
		ms = fx.enrol("WO Status", amount=2000.0)
		writeoff.write_off_membership(ms.name, reason="Member Left")
		ms.reload()
		self.assertEqual(ms.status, "Written Off")
		self.assertEqual(flt(ms.balance_due), 0.0)
		self.assertGreater(flt(ms.written_off_amount), 0)

	def test_obligations_stop_showing_the_debt(self):
		"""Regression: Payment Schedule.outstanding is only written by Payment
		Entries, so a written-off installment invoice kept reporting the full amount
		owing and the member stayed Overdue."""
		ms = fx.enrol("WO Sched", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		si = ms.current_sales_invoice
		rows = frappe.get_all("Payment Schedule", filters={"parent": si}, fields=["outstanding"])
		self.assertEqual(len(rows), 3)

		writeoff.write_off_membership(ms.name)

		# The raw schedule still says the money is owed...
		raw = sum(flt(r.outstanding) for r in frappe.get_all(
			"Payment Schedule", filters={"parent": si}, fields=["outstanding"]
		))
		self.assertGreater(raw, 0)
		# ...but the obligations seam reconciles to the invoice and reports zero.
		obligations = billing.open_obligations(ms.name)
		self.assertEqual(sum(flt(o["outstanding"]) for o in obligations), 0.0)

	def test_partial_write_off_leaves_the_rest_collectable(self):
		ms = fx.enrol("WO Partial", amount=2000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)

		writeoff.write_off_membership(ms.name, amount=owed / 2, reason="Small Balance")

		self.assertAlmostEqual(self._outstanding(si), owed / 2, places=2)
		ms.reload()
		self.assertAlmostEqual(flt(ms.balance_due), owed / 2, places=2)
		self.assertNotEqual(ms.status, "Written Off", "half is still collectable")
		# ...and the member can still pay the remainder.
		billing.record_payment(ms.name, owed / 2, "Cash", today())
		self.assertEqual(self._outstanding(si), 0.0)

	# ---- reversal --------------------------------------------------------- #
	def test_reversing_a_write_off_restores_the_debt(self):
		ms = fx.enrol("WO Reverse", amount=2000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)
		je = writeoff.write_off_membership(ms.name)["journal_entry"]
		self.assertEqual(self._outstanding(si), 0.0)

		writeoff.reverse_write_off(je)

		self.assertAlmostEqual(self._outstanding(si), owed, places=2)
		self.assertEqual(writeoff.written_off_against(si), 0.0)

	# ---- guards ----------------------------------------------------------- #
	def test_cannot_write_off_more_than_is_owed(self):
		ms = fx.enrol("WO Over", amount=2000.0)
		owed = self._outstanding(ms.current_sales_invoice)
		with self.assertRaises(frappe.ValidationError):
			writeoff.write_off_membership(ms.name, amount=owed + 1)

	def test_cannot_write_off_a_settled_invoice(self):
		ms = fx.enrol_and_collect("WO Paid", amount=2000.0)
		with self.assertRaises(frappe.ValidationError):
			writeoff.write_off_membership(ms.name)

	def test_write_off_context_reports_the_exposure(self):
		ms = fx.enrol("WO Ctx", amount=2000.0)
		owed = self._outstanding(ms.current_sales_invoice)
		context = writeoff.get_write_off_context(ms.name)
		self.assertAlmostEqual(context["outstanding"], owed, places=2)
		self.assertEqual(context["written_off"], 0.0)
		self.assertIn("Member Left", context["reasons"])

		writeoff.write_off_membership(ms.name)
		context = writeoff.get_write_off_context(ms.name)
		self.assertEqual(context["outstanding"], 0.0)
		self.assertAlmostEqual(context["written_off"], owed, places=2)
