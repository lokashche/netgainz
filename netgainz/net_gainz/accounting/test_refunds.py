# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""WP-8: refunds and credit notes, and the Profit First cash-impact rule.

The rule under test, in one line: **a refunded rupee must leave the Profit First
cash read.** Waiving an unpaid charge must NOT, because no cash ever moved.

Runs on the India company with india_compliance, so invoices carry GST and the
cash read counts only the ex-GST slice — the assertions are in plan-amount terms.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz.accounting import billing, refunds
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestRefunds(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	# ---- helpers --------------------------------------------------------- #
	def _outstanding(self, si):
		return flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))

	def _customer(self, membership):
		return frappe.db.get_value("Member", membership.member, "customer")

	def _cash(self, membership):
		return billing.collected_paise(today(), today(), [self._customer(membership)])

	# ---- the cash-impact rule -------------------------------------------- #
	def test_refund_leaves_the_profit_first_cash_read(self):
		"""THE WP-8 rule. Collect 1000 ex-GST, refund the whole invoice, and Profit
		First must fall back to zero — not stay at 1000, which is what the old
		`payment_type = 'Receive'` filter did."""
		ms = fx.enrol_and_collect("R Full", amount=1000.0)
		self.assertEqual(self._cash(ms), 100000)

		gross = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		result = refunds.refund_membership(ms.name, amount=gross, reason="Cancelled Membership")

		self.assertTrue(result["credit_note"])
		self.assertTrue(result["payment_entry"], "a paid invoice refunds cash out")
		self.assertEqual(self._cash(ms), 0, "the refunded rupee must leave the PF cash read")

	def test_partial_refund_reduces_cash_by_exactly_the_refund(self):
		ms = fx.enrol_and_collect("R Part", amount=1000.0)
		gross = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		# Refund half the money; ex-GST, that is half the plan amount.
		refunds.refund_membership(ms.name, amount=gross / 2, reason="Goodwill")
		self.assertEqual(self._cash(ms), 50000)

	def test_refund_payment_entry_is_a_pay_with_negative_allocation(self):
		"""The sign convention the netted cash read depends on."""
		ms = fx.enrol_and_collect("R Sign", amount=1000.0)
		gross = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		result = refunds.refund_membership(ms.name, amount=gross)

		pe = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(pe.payment_type, "Pay")
		self.assertEqual(pe.docstatus, 1)
		self.assertEqual(len(pe.references), 1)
		self.assertLess(flt(pe.references[0].allocated_amount), 0)

	# ---- waiving an unpaid charge ---------------------------------------- #
	def test_waiving_an_unpaid_charge_moves_no_cash(self):
		ms = fx.enrol("R Waive", amount=1000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)
		self.assertGreater(owed, 0)

		result = refunds.refund_membership(ms.name, amount=owed, reason="Billing Error")
		self.assertIsNone(result["payment_entry"], "nothing was collected, so nothing is paid back")
		self.assertEqual(self._cash(ms), 0)
		# The credit netted into the original invoice, so the member owes nothing.
		self.assertEqual(self._outstanding(si), 0.0)

	def test_waived_membership_reads_as_paid_with_zero_balance(self):
		ms = fx.enrol("R Waived Status", amount=1000.0)
		owed = self._outstanding(ms.current_sales_invoice)
		refunds.refund_membership(ms.name, amount=owed, reason="Goodwill")
		ms.reload()
		self.assertEqual(flt(ms.balance_due), 0.0)
		self.assertEqual(ms.status, "Paid")
		self.assertGreater(flt(ms.refunded_amount), 0)

	# ---- the credit note must not masquerade as the period's invoice ----- #
	def test_credit_note_does_not_become_the_current_invoice(self):
		"""Regression: `make_return_doc` copies `subscription` onto the credit note,
		so every subscription-keyed read used to pick it up — `current_sales_invoice`
		re-pointed at the refund and obligations went NEGATIVE."""
		ms = fx.enrol_and_collect("R Latest", amount=1000.0)
		si = ms.current_sales_invoice
		gross = flt(frappe.db.get_value("Sales Invoice", si, "grand_total"))
		credit_note = refunds.refund_membership(ms.name, amount=gross)["credit_note"]

		# The credit note really does carry the subscription link...
		self.assertEqual(frappe.db.get_value("Sales Invoice", credit_note, "subscription"), ms.subscription)
		# ...and is still never treated as the period's invoice.
		self.assertEqual(billing._latest_invoice(ms.subscription), si)
		self.assertEqual(billing.current_invoice(ms.name), si)
		ms.reload()
		self.assertEqual(ms.current_sales_invoice, si)
		for obligation in billing.open_obligations(ms.name):
			self.assertGreaterEqual(flt(obligation["outstanding"]), 0)
			self.assertNotEqual(obligation["sales_invoice"], credit_note)

	def test_pay_as_you_go_obligations_exclude_credit_notes(self):
		ms = fx.enrol_and_collect(
			"R PAYG", amount=9000.0, plan_type="Quarterly", billing_mode="Pay-as-you-go", parts=3
		)
		si = ms.current_sales_invoice
		gross = flt(frappe.db.get_value("Sales Invoice", si, "grand_total"))
		credit_note = refunds.refund_membership(ms.name, amount=gross)["credit_note"]
		invoices = {o["sales_invoice"] for o in billing.open_obligations(ms.name)}
		self.assertNotIn(credit_note, invoices)

	# ---- guards ---------------------------------------------------------- #
	def test_cannot_refund_more_than_was_charged(self):
		ms = fx.enrol_and_collect("R Over", amount=1000.0)
		gross = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		with self.assertRaises(frappe.ValidationError):
			refunds.refund_membership(ms.name, amount=gross + 1)

	def test_two_refunds_cannot_exceed_the_invoice(self):
		ms = fx.enrol_and_collect("R Twice", amount=1000.0)
		si = ms.current_sales_invoice
		gross = flt(frappe.db.get_value("Sales Invoice", si, "grand_total"))
		refunds.refund_membership(ms.name, amount=gross / 2)
		self.assertAlmostEqual(refunds.refundable_amount(si), gross / 2, places=2)
		with self.assertRaises(frappe.ValidationError):
			refunds.refund_membership(ms.name, amount=gross)

	def test_zero_refund_is_rejected(self):
		ms = fx.enrol_and_collect("R Zero", amount=1000.0)
		with self.assertRaises(frappe.ValidationError):
			refunds.refund_membership(ms.name, amount=0)

	def test_refund_context_reports_what_is_left(self):
		ms = fx.enrol_and_collect("R Ctx", amount=1000.0)
		si = ms.current_sales_invoice
		gross = flt(frappe.db.get_value("Sales Invoice", si, "grand_total"))
		context = refunds.get_refund_context(ms.name)
		self.assertEqual(context["sales_invoice"], si)
		self.assertAlmostEqual(context["refundable"], gross, places=2)
		self.assertAlmostEqual(context["collected"], gross, places=2)
		self.assertEqual(context["credited"], 0.0)
		self.assertIn("Goodwill", context["reasons"])

		refunds.refund_membership(ms.name, amount=gross / 2)
		context = refunds.get_refund_context(ms.name)
		self.assertAlmostEqual(context["credited"], gross / 2, places=2)
		self.assertAlmostEqual(context["refundable"], gross / 2, places=2)

	# ---- commissions read the same netted cash --------------------------- #
	def test_commission_revenue_base_is_net_of_refunds(self):
		"""Profit First and instructor commissions share one cash read (R2), so a
		refund must move both or the two disagree."""
		from netgainz.net_gainz.operations import commissions

		ms = fx.enrol_and_collect("R Comm", amount=1000.0)
		member = ms.member
		self.assertEqual(commissions._collected_between(today(), today(), [member]), 1000.0)

		gross = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		refunds.refund_membership(ms.name, amount=gross / 2)
		self.assertEqual(commissions._collected_between(today(), today(), [member]), 500.0)
