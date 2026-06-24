# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Tests for the Stage 7 WP-4 billing core: Membership -> native Subscription ->
Sales Invoice -> Payment Entry, the cash-basis Payment-Entry read, and the
date-based cut-over (legacy fee_collected before, Payment Entries after).

Runs on the India company with india_compliance, so generated invoices carry GST;
the cash read counts only the ex-GST (net) revenue.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.profit_first import accounts as pf_accounts

SAC = "999723"


class TestBilling(FrappeTestCase):
	def setUp(self):
		self.company = pf_accounts.default_company()
		# record_payment needs a deposit account for the Cash mode.
		cash = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Cash", "is_group": 0}, "name"
		)
		if cash and not frappe.db.get_value("Company", self.company, "default_cash_account"):
			frappe.db.set_value("Company", self.company, "default_cash_account", cash)
		# Start every test cut-over-OFF: the Single's value (and its cache) can survive
		# the per-test rollback, so reset it explicitly.
		frappe.db.set_single_value("Business Settings", "billing_cutover_date", None)

	# ---- fixtures -------------------------------------------------------- #
	def _plan(self, name, amount=1000.0, duration=30):
		return frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": name,
				"duration_in_days": duration,
				"amount": amount,
				"gst_hsn_code": SAC,
			}
		).insert(ignore_permissions=True)

	def _member(self, name, plan):
		return frappe.get_doc(
			{"doctype": "Member", "full_name": name, "membership_plan": plan}
		).insert(ignore_permissions=True)

	def _set_cutover(self, date):
		frappe.db.set_single_value("Business Settings", "billing_cutover_date", date)

	def _enrol(self, tag):
		"""A cut-over membership (subscription + first invoice provisioned)."""
		plan = self._plan(f"{tag} Plan")
		member = self._member(f"{tag} Member", plan.name)
		ms = frappe.get_doc({"doctype": "Membership", "member": member.name}).insert(
			ignore_permissions=True
		)
		ms.reload()
		return ms, member

	# ---- provisioning ---------------------------------------------------- #
	def test_cutover_membership_provisions_subscription_and_invoice(self):
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 Prov")
		self.assertTrue(ms.subscription, "native Subscription should be provisioned")
		self.assertTrue(ms.current_sales_invoice, "first invoice should be generated")
		si = frappe.db.get_value(
			"Sales Invoice", ms.current_sales_invoice, ["subscription", "outstanding_amount"], as_dict=True
		)
		self.assertEqual(si.subscription, ms.subscription)
		self.assertGreater(si.outstanding_amount, 0)

	def test_ensure_subscription_is_idempotent(self):
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 Idem")
		sub = ms.subscription
		before = frappe.db.count("Subscription")
		again = billing.ensure_subscription(ms.name)
		self.assertEqual(again, sub)
		self.assertEqual(frappe.db.count("Subscription"), before, "no duplicate Subscription")

	def test_no_cutover_uses_legacy_path(self):
		# cut-over unset -> membership keeps the legacy fee_collected model, no Subscription.
		plan = self._plan("WP4 Legacy Plan")
		member = self._member("WP4 Legacy Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "fee_collected": 1000.0}
		).insert(ignore_permissions=True)
		ms.reload()
		self.assertFalse(ms.subscription)
		self.assertEqual(ms.status, "Paid")  # legacy: fee_collected >= tariff

	# ---- payments (R3 / R4) --------------------------------------------- #
	def test_record_payment_reduces_outstanding_and_sets_paid_to(self):
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 Pay")
		outstanding = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount"))
		pe_name = billing.record_payment(ms.name, outstanding, "Cash", today())
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount")), 0.0
		)
		pe = frappe.db.get_value("Payment Entry", pe_name, ["docstatus", "payment_type", "paid_to"], as_dict=True)
		self.assertEqual(pe.docstatus, 1)
		self.assertEqual(pe.payment_type, "Receive")
		self.assertEqual(pe.paid_to, frappe.db.get_value("Company", self.company, "default_cash_account"))

	def test_record_payment_requires_posting_date(self):
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 NoDate")
		with self.assertRaises(frappe.ValidationError):
			billing.record_payment(ms.name, 100, "Cash", None)

	def test_record_payment_honors_explicit_posting_date(self):
		# R3 regression: get_payment_entry defaults posting_date to today; we must override.
		self._set_cutover(add_days(today(), -3))
		ms, _ = self._enrol("WP4 Date")
		pay_date = add_days(today(), -1)
		pe_name = billing.record_payment(ms.name, 100, "Cash", pay_date)
		self.assertEqual(
			getdate(frappe.db.get_value("Payment Entry", pe_name, "posting_date")), getdate(pay_date)
		)

	def test_overpayment_is_rejected(self):
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 Over")
		outstanding = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount"))
		with self.assertRaises(frappe.ValidationError):
			billing.record_payment(ms.name, outstanding + 1, "Cash", today())

	def test_status_derived_from_invoice(self):
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 Status")
		outstanding = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount"))
		billing.record_payment(ms.name, outstanding, "Cash", today())
		ms.reload()
		ms.save(ignore_permissions=True)  # before_save -> sync_from_invoice
		ms.reload()
		self.assertEqual(ms.status, "Paid")
		self.assertEqual(flt(ms.balance_due), 0.0)

	# ---- the cash read (R1 / R2) ---------------------------------------- #
	def test_collected_paise_is_net_ex_gst(self):
		self._set_cutover(today())
		ms, member = self._enrol("WP4 Net")
		outstanding = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount"))
		billing.record_payment(ms.name, outstanding, "Cash", today())
		# Full payment of a 1000-fee plan -> net revenue 1000 (GST excluded), regardless
		# of the GST-inclusive grand total. Scoped to this member's Customer so
		# pre-existing site data can't perturb it.
		customer = frappe.db.get_value("Member", member.name, "customer")
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 100000)

	def test_collected_paise_scoped_by_customer(self):
		self._set_cutover(today())
		ms, member = self._enrol("WP4 Scope")
		outstanding = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount"))
		billing.record_payment(ms.name, outstanding, "Cash", today())
		customer = frappe.db.get_value("Member", member.name, "customer")
		self.assertEqual(billing.collected_paise(today(), today(), [customer]), 100000)
		self.assertEqual(billing.collected_paise(today(), today(), ["Some Other Customer"]), 0)

	# ---- renewal (period 2+) -------------------------------------------- #
	def test_renewal_payment_targets_open_period_invoice(self):
		"""Once period 1 is paid and the scheduler bills period 2, a renewal payment
		(no explicit SI) must hit the OPEN period-2 invoice, not throw against the
		paid period-1 SI. Regression for the stale-current_sales_invoice bug."""
		self._set_cutover(today())
		ms, _ = self._enrol("WP4 Renew")
		si1 = ms.current_sales_invoice
		out1 = flt(frappe.db.get_value("Sales Invoice", si1, "outstanding_amount"))
		billing.record_payment(ms.name, out1, "Cash", today())
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", si1, "outstanding_amount")), 0.0)
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
		out2 = flt(frappe.db.get_value("Sales Invoice", inv2.name, "outstanding_amount"))
		billing.record_payment(ms.name, out2, "Cash", today())
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", inv2.name, "outstanding_amount")), 0.0)

	def test_cutover_date_immutable_once_billed(self):
		self._set_cutover(today())
		self._enrol("WP4 Lock")  # creates a subscription-generated Sales Invoice
		bs = frappe.get_single("Business Settings")
		bs.billing_cutover_date = add_days(today(), 5)
		with self.assertRaises(frappe.ValidationError):
			bs.save(ignore_permissions=True)

	def test_golden_continuity_across_cutover(self):
		"""The shared read sums legacy fee_collected (before the cut-over) AND
		Payment-Entry net cash (on/after) over one window — continuous, no collapse,
		no double-count. The R1+R2 safety net."""
		now = getdate(today())
		# 1. A legacy collection BEFORE the cut-over (cut-over still unset).
		lplan = self._plan("WP4 Cont Legacy Plan")
		lmember = self._member("WP4 Cont Legacy Member", lplan.name)
		frappe.get_doc(
			{
				"doctype": "Membership",
				"member": lmember.name,
				"fee_collected": 500.0,
				"paid_date": add_days(now, -10),
			}
		).insert(ignore_permissions=True)
		# 2. Cut over, then a Payment-Entry collection ON/AFTER it.
		self._set_cutover(add_days(now, -5))
		ms, pe_member = self._enrol("WP4 Cont PE")
		outstanding = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "outstanding_amount"))
		billing.record_payment(ms.name, outstanding, "Cash", now)
		# Window spans both: legacy 500 (ex-GST already) + PE net 1000 = 1500. Scoped to
		# the two test members so pre-existing site data can't perturb it.
		total = billing.membership_collected_paise(
			add_days(now, -15), now, [lmember.name, pe_member.name]
		)
		self.assertEqual(total, 150000)
