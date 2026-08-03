# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Tests for the billing core: Membership -> native Subscription -> Sales Invoice
-> Payment Entry, and the cash-basis Payment-Entry read.

WP-11: there is ONE billing path — every membership bills through ERPNext from day
one — so the date-gated cut-over tests, the legacy-path test and the
legacy-vs-Payment-Entry continuity test are gone with the code they covered. What
replaces them is a test proving the deprecated `fee_collected` field feeds NOTHING.

Runs on the India company with india_compliance, so generated invoices carry GST;
the cash read counts only the ex-GST (net) revenue.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.profit_first import accounts as pf_accounts


class TestBilling(FrappeTestCase):
	def setUp(self):
		self.company = pf_accounts.default_company()
		fx.ensure_cash_account(self.company)

	# ---- fixtures -------------------------------------------------------- #
	def _enrol(self, tag, amount=1000.0):
		"""A membership with its subscription + first invoice provisioned."""
		ms = fx.enrol(tag, amount=amount)
		return ms, ms.member

	def _outstanding(self, si):
		return flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount"))

	# ---- provisioning ---------------------------------------------------- #
	def test_membership_provisions_subscription_and_invoice(self):
		ms, _ = self._enrol("WP4 Prov")
		self.assertTrue(ms.subscription, "native Subscription should be provisioned")
		self.assertTrue(ms.current_sales_invoice, "first invoice should be generated")
		si = frappe.db.get_value(
			"Sales Invoice", ms.current_sales_invoice, ["subscription", "outstanding_amount"], as_dict=True
		)
		self.assertEqual(si.subscription, ms.subscription)
		self.assertGreater(si.outstanding_amount, 0)

	def test_ensure_subscription_is_idempotent(self):
		ms, _ = self._enrol("WP4 Idem")
		sub = ms.subscription
		before = frappe.db.count("Subscription")
		again = billing.ensure_subscription(ms.name)
		self.assertEqual(again, sub)
		self.assertEqual(frappe.db.count("Subscription"), before, "no duplicate Subscription")

	def test_derived_fields_persisted_on_enrolment(self):
		"""Regression (WP-11): the Subscription + first invoice are provisioned in
		after_insert, i.e. AFTER before_save ran sync_from_invoice. Without an
		explicit re-sync the new membership kept empty status/balance/due_date."""
		ms, _ = self._enrol("WP4 Derived")
		self.assertEqual(ms.status, "Pending")
		self.assertEqual(flt(ms.balance_due), self._outstanding(ms.current_sales_invoice))
		self.assertTrue(ms.due_date, "due_date is derived from the invoice on enrolment")
		self.assertTrue(ms.next_renewal, "next_renewal is derived from the subscription period")

	def test_subscription_anchors_on_member_joining_date(self):
		"""WP-10.0: the cycle keys off date_of_joining, not the enrolment day — so a
		member who joined on the 15th is billed on the 15th. The start is the CURRENT
		period, never the joining date itself, so past periods are not back-billed."""
		joined = add_days(today(), -70)  # ~2 months + 10 days ago
		plan = fx.make_plan("WP10 Anchor Plan", amount=1000.0, duration=30)
		member = frappe.get_doc(
			{
				"doctype": "Member",
				"full_name": "WP10 Anchor Member",
				"membership_plan": plan.name,
				"date_of_joining": joined,
			}
		).insert(ignore_permissions=True)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()

		start = getdate(frappe.db.get_value("Subscription", ms.subscription, "start_date"))
		# Same day-of-month as joining -> the cycle is anchored, not drifted.
		self.assertEqual(start.day, getdate(joined).day)
		# Current period, not the joining date: no retroactive billing.
		self.assertGreater(start, getdate(joined))
		self.assertLessEqual(start, getdate(today()))
		# Exactly ONE invoice was raised, not one per elapsed period.
		self.assertEqual(
			frappe.db.count("Sales Invoice", {"subscription": ms.subscription, "docstatus": 1}), 1
		)

	# ---- payments (R3 / R4) --------------------------------------------- #
	def test_record_payment_reduces_outstanding_and_sets_paid_to(self):
		ms, _ = self._enrol("WP4 Pay")
		outstanding = self._outstanding(ms.current_sales_invoice)
		pe_name = billing.record_payment(ms.name, outstanding, "Cash", today())
		self.assertEqual(self._outstanding(ms.current_sales_invoice), 0.0)
		pe = frappe.db.get_value(
			"Payment Entry", pe_name, ["docstatus", "payment_type", "paid_to"], as_dict=True
		)
		self.assertEqual(pe.docstatus, 1)
		self.assertEqual(pe.payment_type, "Receive")
		self.assertEqual(pe.paid_to, frappe.db.get_value("Company", self.company, "default_cash_account"))

	def test_record_payment_requires_posting_date(self):
		ms, _ = self._enrol("WP4 NoDate")
		with self.assertRaises(frappe.ValidationError):
			billing.record_payment(ms.name, 100, "Cash", None)

	def test_record_payment_honors_explicit_posting_date(self):
		# R3 regression: get_payment_entry defaults posting_date to today; we must override.
		ms, _ = self._enrol("WP4 Date")
		pay_date = add_days(today(), -1)
		pe_name = billing.record_payment(ms.name, 100, "Cash", pay_date)
		self.assertEqual(
			getdate(frappe.db.get_value("Payment Entry", pe_name, "posting_date")), getdate(pay_date)
		)

	def test_overpayment_is_rejected(self):
		ms, _ = self._enrol("WP4 Over")
		outstanding = self._outstanding(ms.current_sales_invoice)
		with self.assertRaises(frappe.ValidationError):
			billing.record_payment(ms.name, outstanding + 1, "Cash", today())

	def test_status_derived_from_invoice(self):
		ms, _ = self._enrol("WP4 Status")
		billing.record_payment(ms.name, self._outstanding(ms.current_sales_invoice), "Cash", today())
		ms.reload()
		ms.save(ignore_permissions=True)  # before_save -> sync_from_invoice
		ms.reload()
		self.assertEqual(ms.status, "Paid")
		self.assertEqual(flt(ms.balance_due), 0.0)

	# ---- the cash read (R1 / R2) ---------------------------------------- #
	def test_collected_paise_is_net_ex_gst(self):
		ms, member = self._enrol("WP4 Net")
		billing.record_payment(ms.name, self._outstanding(ms.current_sales_invoice), "Cash", today())
		# Full payment of a 1000-fee plan -> net revenue 1000 (GST excluded), regardless
		# of the GST-inclusive grand total. Scoped to this member's Customer so
		# pre-existing site data can't perturb it.
		customer = frappe.db.get_value("Member", member, "customer")
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 100000)

	def test_collected_paise_scoped_by_customer(self):
		ms, member = self._enrol("WP4 Scope")
		billing.record_payment(ms.name, self._outstanding(ms.current_sales_invoice), "Cash", today())
		customer = frappe.db.get_value("Member", member, "customer")
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 100000)
		self.assertEqual(billing.collected_paise(today(), today(), ["Some Other Customer"]), 0)

	def test_legacy_fee_collected_is_ignored_by_cash_read(self):
		"""WP-11: `fee_collected` is a deprecated display field. Writing it must NOT
		create revenue — cash comes only from Payment Entries. This is the guard that
		the deleted legacy read cannot creep back in."""
		ms, member = self._enrol("WP4 Ignored")
		frappe.db.set_value(
			"Membership", ms.name, {"fee_collected": 5000.0, "paid_date": today()}, update_modified=False
		)
		self.assertEqual(
			billing.membership_collected_paise(today(), today(), [member]),
			0,
			"fee_collected must contribute nothing to collected cash",
		)
		# ...and a real Payment Entry still counts, on the same membership.
		billing.record_payment(ms.name, self._outstanding(ms.current_sales_invoice), "Cash", today())
		self.assertEqual(billing.membership_collected_paise(today(), today(), [member]), 100000)

	# ---- renewal (period 2+) -------------------------------------------- #
	def test_renewal_payment_targets_open_period_invoice(self):
		"""Once period 1 is paid and the scheduler bills period 2, a renewal payment
		(no explicit SI) must hit the OPEN period-2 invoice, not throw against the
		paid period-1 SI. Regression for the stale-current_sales_invoice bug."""
		ms, _ = self._enrol("WP4 Renew")
		si1 = ms.current_sales_invoice
		billing.record_payment(ms.name, self._outstanding(si1), "Cash", today())
		self.assertEqual(self._outstanding(si1), 0.0)
		# Scheduler bills the next period -> a new submitted SI (submit_invoice=1).
		sub = frappe.get_doc("Subscription", ms.subscription)
		inv2 = sub.create_invoice()
		self.assertNotEqual(inv2.name, si1)
		ms.reload()
		# on_sales_invoice_submit re-points current_sales_invoice at the new period.
		self.assertEqual(ms.current_sales_invoice, inv2.name)
		# status now reflects the open period-2 invoice, not "Paid".
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertNotEqual(ms.status, "Paid")
		# renewal payment with NO explicit SI targets the open SI-2.
		billing.record_payment(ms.name, self._outstanding(inv2.name), "Cash", today())
		self.assertEqual(self._outstanding(inv2.name), 0.0)
