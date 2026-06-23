# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""DB-backed tests for the Profit First sweep (Stage 5b) — the money-moving slice.

Covers account setup (idempotent), proposal snapshotting, balanced Journal Entry
posting on approval, cancellation reversal, and the double-post guard.

Run: bench --site <site> run-tests --module netgainz.net_gainz.profit_first.test_sweep
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from netgainz.net_gainz.profit_first import accounts, calc
from netgainz.net_gainz.profit_first.seed import seed_profit_first_defaults


class TestPFSweep(FrappeTestCase):
	def setUp(self):
		# FrappeTestCase shares one transaction across the class; clear prior
		# sweeps so a posted sweep from an earlier test can't trip another test's
		# one-sweep-per-date idempotency guard.
		frappe.db.delete("PF Sweep")
		frappe.db.delete("Membership")
		frappe.db.delete("Expense")

		seed_profit_first_defaults()
		company = accounts.default_company()
		settings = frappe.get_single("Profit First Settings")
		settings.pf_enabled = 1
		settings.assessment_window = "This Month"
		# Pin ONE company and clear any stale account links/cost-centers so the
		# sweep's company, accounts and cost centers stay consistent even when the
		# test runner left a different company as the ambient default (e.g. the
		# ERPNext / india_compliance fixture companies). setup_pf_accounts re-maps.
		settings.company = company
		for row in settings.accounts:
			row.account_link = None
			row.cost_center = None
		settings.save(ignore_permissions=True)

		accounts.setup_pf_accounts(company)  # idempotent; creates + maps the 5 accounts

	# ---- helpers --------------------------------------------------------- #
	def _sub(self, fee):
		frappe.get_doc({"doctype": "Membership", "tariff": fee, "fee_collected": fee}).insert(
			ignore_permissions=True
		)

	def _new_sweep(self):
		return frappe.get_doc({"doctype": "PF Sweep", "sweep_date": today()}).insert(ignore_permissions=True)

	# ---- account setup --------------------------------------------------- #
	def test_account_setup_creates_and_maps_five(self):
		settings = frappe.get_single("Profit First Settings")
		links = {r.account_role: r.account_link for r in settings.accounts}
		self.assertEqual(len(settings.accounts), 5)
		for role in ("Income", "Profit", "Owner's Pay", "Tax", "Operating Expenses"):
			self.assertTrue(links.get(role), f"{role} not mapped")
		# Income is an Income account; allocations are Asset accounts.
		self.assertEqual(frappe.db.get_value("Account", links["Income"], "root_type"), "Income")
		self.assertEqual(frappe.db.get_value("Account", links["Profit"], "root_type"), "Asset")

	def test_account_setup_idempotent(self):
		before = frappe.db.count("Account")
		accounts.setup_pf_accounts()
		accounts.setup_pf_accounts()
		self.assertEqual(frappe.db.count("Account"), before)

	# ---- proposal -------------------------------------------------------- #
	def test_proposal_snapshot_matches_real_revenue(self):
		self._sub(200000)
		self._sub(100000)  # topline 300000, no pass-through -> RR 300000
		sweep = self._new_sweep()
		self.assertEqual(sweep.real_revenue, 300000.00)
		# This Month annualised x12 = 3.6M -> Tier D (10/10/15/65)
		self.assertEqual(sweep.tier_code, "D")
		by_role = {a.account_role: a for a in sweep.allocations}
		self.assertEqual(by_role["Profit"].amount, 30000.00)
		self.assertEqual(by_role["Owner's Pay"].amount, 30000.00)
		self.assertEqual(by_role["Tax"].amount, 45000.00)
		self.assertEqual(by_role["Operating Expenses"].amount, 195000.00)
		# allocations sum exactly to Real Revenue
		self.assertEqual(sum(flt(a.amount) for a in sweep.allocations), 300000.00)

	# ---- posting --------------------------------------------------------- #
	def test_submit_posts_balanced_journal_entry(self):
		self._sub(200000)
		self._sub(100000)
		sweep = self._new_sweep()
		sweep.submit()

		self.assertTrue(sweep.journal_entry)
		je = frappe.get_doc("Journal Entry", sweep.journal_entry)
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(flt(je.total_debit), 300000.00)
		self.assertEqual(flt(je.total_credit), 300000.00)
		self.assertEqual(flt(je.difference), 0.0)

		settings = frappe.get_single("Profit First Settings")
		links = {r.account_role: r.account_link for r in settings.accounts}
		lines = {l.account: l for l in je.accounts}
		# Income credited the full Real Revenue
		self.assertEqual(flt(lines[links["Income"]].credit_in_account_currency), 300000.00)
		# Each reserve debited its share
		self.assertEqual(flt(lines[links["Tax"]].debit_in_account_currency), 45000.00)
		self.assertEqual(flt(lines[links["Operating Expenses"]].debit_in_account_currency), 195000.00)

	def test_cancel_reverses_journal_entry(self):
		self._sub(120000)
		sweep = self._new_sweep()
		sweep.submit()
		je_name = sweep.journal_entry
		sweep.reload()
		sweep.cancel()
		self.assertEqual(frappe.db.get_value("Journal Entry", je_name, "docstatus"), 2)

	def test_double_post_blocked(self):
		self._sub(100000)
		s1 = self._new_sweep()
		s1.submit()
		s2 = self._new_sweep()  # same sweep_date
		with self.assertRaises(frappe.ValidationError):
			s2.submit()

	def test_cannot_submit_without_revenue(self):
		# No subscriptions -> Real Revenue 0 -> cannot post
		sweep = self._new_sweep()
		self.assertEqual(sweep.real_revenue, 0.0)
		with self.assertRaises(frappe.ValidationError):
			sweep.submit()

	def test_cannot_submit_with_unmapped_accounts(self):
		self._sub(100000)
		# Unmap the Tax account to simulate incomplete setup
		settings = frappe.get_single("Profit First Settings")
		for r in settings.accounts:
			if r.account_role == "Tax":
				r.account_link = None
		settings.save(ignore_permissions=True)
		sweep = self._new_sweep()
		with self.assertRaises(frappe.ValidationError):
			sweep.submit()
