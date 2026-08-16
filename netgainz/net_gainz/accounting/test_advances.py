# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""WP-8: partial payments, advances and on-account money.

The recognition rule under test: cash becomes Profit First revenue when it is
ALLOCATED to a membership invoice, dated the day the money actually arrived.
Money sitting on account is not revenue — the gym might still have to hand it
back — but the moment it settles an invoice it counts, in its own period.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from netgainz.net_gainz.accounting import advances, billing
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestAdvances(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	def _outstanding(self, si):
		return flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))

	def _customer(self, membership):
		return frappe.db.get_value("Member", membership.member, "customer")

	def _cash(self, membership, start=None, end=None):
		return billing.collected_paise(
			start or add_days(today(), -10), end or today(), [self._customer(membership)]
		)

	# ---- partial payment -------------------------------------------------- #
	def test_partial_payment_leaves_the_rest_outstanding(self):
		ms = fx.enrol("ADV Partial", amount=1000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)
		billing.record_payment(ms.name, owed / 2, "Cash", today())
		self.assertAlmostEqual(self._outstanding(si), owed / 2, places=2)
		ms.reload()
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertIn(ms.status, ("Partial", "Overdue"))

	# ---- overpayment becomes money on account ----------------------------- #
	def test_overpayment_is_rejected_unless_explicitly_allowed(self):
		ms = fx.enrol("ADV Reject", amount=1000.0)
		owed = self._outstanding(ms.current_sales_invoice)
		with self.assertRaises(frappe.ValidationError):
			billing.record_payment(ms.name, owed + 500, "Cash", today())

	def test_overpayment_parks_the_excess_on_account(self):
		ms = fx.enrol("ADV Over", amount=1000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)

		pe = billing.record_payment(ms.name, owed + 500, "Cash", today(), allow_advance=True)

		self.assertEqual(self._outstanding(si), 0.0)
		self.assertAlmostEqual(
			flt(frappe.db.get_value("Payment Entry", pe, "unallocated_amount")), 500.0, places=2
		)
		self.assertAlmostEqual(advances.advance_balance(ms.name), 500.0, places=2)
		# The invoice's share is revenue; the parked 500 is not (yet).
		self.assertEqual(self._cash(ms), 100000)

	# ---- taking money with no invoice ------------------------------------- #
	def test_advance_is_cash_in_hand_but_not_revenue(self):
		ms = fx.enrol("ADV Pure", amount=1000.0)
		advances.record_advance(ms.member, 5000.0, "Cash", today())

		self.assertAlmostEqual(advances.advance_balance(ms.member), 5000.0, places=2)
		self.assertEqual(self._cash(ms), 0, "unapplied money is a liability, not membership revenue")

	def test_advance_requires_a_posting_date_and_a_positive_amount(self):
		ms = fx.enrol("ADV Guard", amount=1000.0)
		with self.assertRaises(frappe.ValidationError):
			advances.record_advance(ms.member, 500.0, "Cash", None)
		with self.assertRaises(frappe.ValidationError):
			advances.record_advance(ms.member, 0, "Cash", today())

	# ---- applying it ------------------------------------------------------- #
	def test_applying_an_advance_settles_the_invoice_and_recognises_revenue(self):
		ms = fx.enrol("ADV Apply", amount=1000.0)
		si = ms.current_sales_invoice
		owed = self._outstanding(si)
		advances.record_advance(ms.member, 5000.0, "Cash", today())

		result = advances.apply_advances(ms.member)

		self.assertAlmostEqual(result["applied"], owed, places=2)
		self.assertEqual(self._outstanding(si), 0.0)
		self.assertAlmostEqual(advances.advance_balance(ms.member), 5000.0 - owed, places=2)
		self.assertEqual(self._cash(ms), 100000)

	def test_revenue_is_recognised_on_the_day_the_money_arrived(self):
		"""Not the day it was applied. The owner banked it when they banked it."""
		received = add_days(today(), -3)
		ms = fx.enrol("ADV Date", amount=1000.0)
		advances.record_advance(ms.member, 5000.0, "Cash", received)
		advances.apply_advances(ms.member)

		self.assertEqual(self._cash(ms, received, received), 100000)
		self.assertEqual(self._cash(ms, today(), today()), 0)

	def test_advance_is_not_spent_on_a_non_membership_invoice(self):
		"""Money a member left for their membership must not silently settle some
		unrelated receivable raised against the same Customer."""
		ms = fx.enrol("ADV Scope", amount=1000.0)
		customer = self._customer(ms)
		other = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"company": frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "company"),
				"posting_date": today(),
				"due_date": today(),
				"items": [
					{
						"item_code": frappe.db.get_value("Membership Plan", ms.membership_plan, "item"),
						"qty": 1,
						"rate": 700,
					}
				],
			}
		).insert(ignore_permissions=True)
		other.submit()
		self.assertFalse(frappe.db.get_value("Sales Invoice", other.name, "subscription"))

		advances.record_advance(ms.member, 700.0, "Cash", today())
		advances.apply_advances(ms.member)

		self.assertGreater(self._outstanding(other.name), 0, "the ad-hoc invoice is untouched")

	def test_advance_auto_applies_when_the_next_period_is_billed(self):
		"""A member who paid several periods up front must not read as Overdue the
		moment the scheduler bills the next one."""
		ms = fx.enrol("ADV Renew", amount=1000.0)
		si1 = ms.current_sales_invoice
		billing.record_payment(ms.name, self._outstanding(si1), "Cash", today())
		advances.record_advance(ms.member, 5000.0, "Cash", today())

		sub = frappe.get_doc("Subscription", ms.subscription)
		si2 = sub.create_invoice()

		self.assertEqual(self._outstanding(si2.name), 0.0, "the advance settled the new period on submit")
		ms.reload()
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertEqual(ms.status, "Paid")

	def test_advance_context_lists_what_is_on_account(self):
		ms = fx.enrol("ADV Ctx", amount=1000.0)
		advances.record_advance(ms.member, 2500.0, "Cash", today())
		context = advances.get_advance_context(ms.member)
		self.assertAlmostEqual(context["balance"], 2500.0, places=2)
		self.assertEqual(len(context["advances"]), 1)
		self.assertAlmostEqual(context["advances"][0]["unapplied"], 2500.0, places=2)

	def test_applying_nothing_is_a_no_op(self):
		ms = fx.enrol("ADV None", amount=1000.0)
		result = advances.apply_advances(ms.member)
		self.assertEqual(result["applied"], 0.0)
		self.assertEqual(result["allocations"], [])
