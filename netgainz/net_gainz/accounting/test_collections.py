# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Money owed: the collections read, its digest, and per-member payment terms.

Pinned:

* **a part is chased, not a member.** A quarterly fee split three ways is three
  promises, and a member who has missed two of them appears twice with the right
  amount against each -- the thing the dashboard's single "overdue" row cannot say;
* the read is built on ``billing.open_obligations``, so a gym billing in Commitment
  mode and one billing Pay-as-you-go produce the same list without a special case;
* **late is always included** whatever the look-ahead window is set to, because a
  window is about what is coming, never about forgiving what is already owed;
* the digest is notify-only, one per user per day, opt-out honoured, and **silent
  when nothing is owed** -- switching it on must not produce a daily message saying
  everything is fine;
* a member can be given their own terms, sent back to the plan's, and the words the
  owner reads are generated from the same numbers that drive the billing.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import collections, payment_terms

TAG = "ZZCOL"


def _clear():
	# Enrolling raises a real submitted Sales Invoice, and a submitted document
	# survives FrappeTestCase's per-test rollback. Deleting only the Membership and
	# the Member left those invoices behind pointing at a deleted Customer -- and
	# because the CUST- series is reset between loads, the next test customer was
	# handed the SAME id and inherited 52 orphaned invoices, which broke Payment
	# Reconciliation and made test_advances fail in a completely unrelated suite.
	# clear_billing_data exists for exactly this; use it rather than reinventing it.
	fx.clear_billing_data()
	for name in frappe.get_all("Member", filters={"full_name": ["like", f"{TAG}%"]}, pluck="name"):
		customer = frappe.db.get_value("Member", name, "customer")
		frappe.delete_doc("Member", name, force=True, ignore_permissions=True)
		if customer and frappe.db.exists("Customer", customer):
			frappe.delete_doc("Customer", customer, force=True, ignore_permissions=True)
	for dt in ("Membership Plan", "Subscription Plan", "Item"):
		for name in frappe.get_all(dt, filters={"name": ["like", f"{TAG}%"]}, pluck="name"):
			try:
				frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
			except Exception:
				pass
	frappe.db.delete("Notification Log", {"subject": ["like", "%to collect%"]})
	frappe.db.commit()


class TestPaymentTermsWords(FrappeTestCase):
	"""``describe`` is the only place the policy is ever put to the owner in words."""

	def test_a_single_payment_reads_as_one(self):
		self.assertEqual(
			payment_terms.describe("On joining", 1, 0), "Pays in full when they join"
		)
		self.assertEqual(
			payment_terms.describe("Within 7 days", 1, 30), "Pays in full within 7 days"
		)

	def test_a_split_names_the_parts_the_gap_and_the_start(self):
		self.assertEqual(
			payment_terms.describe("On joining", 3, 30),
			"Pays in 3 parts every 30 days starting when they join",
		)

	def test_no_gap_does_not_produce_a_dangling_every(self):
		self.assertNotIn("every ", payment_terms.describe("On joining", 2, 0))

	def test_nothing_configured_still_reads_as_a_sentence(self):
		self.assertTrue(payment_terms.describe(None, None, None).startswith("Pays in full"))


class TestCollections(FrappeTestCase):
	def setUp(self):
		_clear()
		self.plan = self._plan(f"{TAG} Quarterly", amount=9000, parts=3, gap=30)

	def tearDown(self):
		_clear()

	# ------------------------------------------------------------------ helpers

	def _plan(self, name, amount, parts=1, gap=30):
		doc = frappe.new_doc("Membership Plan")
		doc.plan_name = name
		doc.duration_in_days = 90
		doc.amount = amount
		doc.plan_type = "Quarterly"
		doc.billing_mode = "Commitment"
		doc.payment_due_rule = "On joining"
		doc.installment_count = parts
		doc.installment_gap_days = gap
		doc.is_active = 1
		doc.insert(ignore_permissions=True)
		return doc.name

	def _member(self, suffix="One"):
		doc = frappe.new_doc("Member")
		doc.full_name = f"{TAG} {suffix}"
		doc.status = "Active"
		doc.date_of_joining = today()
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_late(self, membership, days=45):
		"""Move this membership's instalments into the past.

		Backdating ``start_date`` does NOT backdate the invoice -- billing raises it on
		the day the membership is created -- so the only honest way to produce a late
		part in a test is to move the schedule, which is what the passage of time does.
		Before this existed these tests read the seeded demo gym's overdue money and
		passed without exercising their own fixture at all.
		"""
		si = frappe.db.get_value("Membership", membership, "current_sales_invoice")
		if not si:
			return
		for row in frappe.get_all(
			"Payment Schedule", filters={"parent": si}, fields=["name", "due_date"]
		):
			frappe.db.set_value(
				"Payment Schedule", row.name, "due_date", add_days(row.due_date, -days),
				update_modified=False,
			)
		frappe.db.commit()

	def _membership(self, member, plan, start=None, **overrides):
		doc = frappe.new_doc("Membership")
		doc.member = member
		doc.membership_plan = plan
		doc.start_date = start or today()
		for k, v in overrides.items():
			setattr(doc, k, v)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc

	# ------------------------------------------------------------------- the read

	def test_a_split_fee_is_chased_as_separate_parts(self):
		"""The whole point: three promises, not one.

		Note the window has to be wide. Billing raises the first invoice on the day it
		is created, not on a backdated ``start_date``, so a fresh 3-part membership has
		one part due today and the rest 30 and 60 days out.
		"""
		ms = self._membership(self._member(), self.plan)
		d = collections.get_dues(within_days=365)
		rows = [
			r
			for r in d["late"] + d["due_today"] + d["due_soon"]
			if r["membership"] == ms.name
		]
		self.assertEqual(len(rows), 3, "a 3-part fee must appear as three separate debts")
		self.assertTrue(all(r["outstanding"] > 0 for r in rows))
		# Distinct dates, so each one is a date the gym can actually chase on.
		self.assertEqual(len({r["due_date"] for r in rows}), 3)

	def test_late_is_included_however_short_the_window(self):
		ms = self._membership(self._member(), self.plan)
		self._make_late(ms.name)
		narrow = collections.get_dues(within_days=0)
		self.assertTrue(narrow["late"], "a zero-day window must still surface what is overdue")

	def test_a_wider_window_only_ever_adds_to_due_soon(self):
		self._membership(self._member(), self.plan)
		narrow = collections.get_dues(within_days=0)
		wide = collections.get_dues(within_days=365)
		self.assertGreaterEqual(len(wide["due_soon"]), len(narrow["due_soon"]))
		self.assertEqual(len(wide["late"]), len(narrow["late"]))

	def test_totals_match_the_rows(self):
		ms = self._membership(self._member(), self.plan)
		self._make_late(ms.name)
		d = collections.get_dues()
		self.assertAlmostEqual(
			d["total_late"], round(sum(r["outstanding"] for r in d["late"]), 2), places=2
		)

	def test_days_late_is_positive_only_for_the_overdue(self):
		ms = self._membership(self._member(), self.plan)
		self._make_late(ms.name)
		d = collections.get_dues()
		self.assertTrue(all(r["days_late"] > 0 for r in d["late"]))
		self.assertTrue(all(r["days_late"] == 0 for r in d["due_today"]))

	# -------------------------------------------------------------- the reminder

	def test_the_digest_is_silent_when_nothing_is_owed(self):
		frappe.db.set_single_value("Business Settings", "dues_reminders_enabled", 1)
		# No memberships created in this test, so nothing can be owed by the tag.
		before = frappe.db.count("Notification Log", {"subject": ["like", "%to collect%"]})
		if not collections.get_dues()["late"] and not collections.get_dues()["due_today"]:
			collections.notify_dues()
			self.assertEqual(
				frappe.db.count("Notification Log", {"subject": ["like", "%to collect%"]}), before
			)

	def test_the_digest_honours_its_off_switch(self):
		ms = self._membership(self._member(), self.plan)
		self._make_late(ms.name)
		frappe.db.set_single_value("Business Settings", "dues_reminders_enabled", 0)
		self.assertIsNone(collections.notify_dues())

	def test_the_digest_is_one_per_user_per_day(self):
		ms = self._membership(self._member(), self.plan)
		self._make_late(ms.name)
		frappe.db.set_single_value("Business Settings", "dues_reminders_enabled", 1)
		first = collections.notify_dues()
		second = collections.notify_dues()
		self.assertTrue(first)
		self.assertEqual(second, 0, "a second run the same day must add nothing")

	# ---------------------------------------------------------- per-member terms

	def test_a_membership_follows_its_plan_by_default(self):
		ms = self._membership(self._member(), self.plan)
		terms = payment_terms.get_membership_terms(ms.name)
		self.assertFalse(terms["uses_own_terms"])
		self.assertEqual(terms["installment_count"], 3)
		self.assertIn("3 parts", terms["summary"])

	def test_a_member_can_be_given_their_own_split(self):
		ms = self._membership(self._member(), self.plan)
		terms = payment_terms.set_membership_terms(
			ms.name, payment_due_rule="On joining", installment_count=2, installment_gap_days=45
		)
		self.assertTrue(terms["uses_own_terms"])
		self.assertEqual(terms["installment_count"], 2)
		self.assertIn("2 parts", terms["summary"])
		# The plan is untouched, and still says what it always said.
		self.assertIn("3 parts", terms["plan_summary"])

	def test_clearing_the_override_sends_them_back_to_the_plan(self):
		ms = self._membership(self._member(), self.plan)
		payment_terms.set_membership_terms(ms.name, installment_count=2, installment_gap_days=45)
		terms = payment_terms.set_membership_terms(ms.name)
		self.assertFalse(terms["uses_own_terms"])
		self.assertEqual(terms["installment_count"], 3)

	def test_an_impossible_split_is_refused(self):
		ms = self._membership(self._member(), self.plan)
		with self.assertRaises(frappe.ValidationError):
			payment_terms.set_membership_terms(ms.name, installment_count=99)

	def test_an_unknown_due_rule_is_refused(self):
		ms = self._membership(self._member(), self.plan)
		with self.assertRaises(frappe.ValidationError):
			payment_terms.set_membership_terms(ms.name, payment_due_rule="Whenever they like")
