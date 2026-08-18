# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Expenses that repeat: raising them, and never raising them twice.

Pinned:

* **a repeat is raised as a DRAFT.** Rent is the same every month; electricity is not.
  An expense that posted itself would put last month's guess into the accounts, so the
  owner checks the amount and submits;
* **the same period is never raised twice.** The expense the owner ticked is the root,
  every copy points back to it, and the last date in that chain is where the series has
  got to -- so a second run the same day creates nothing, which is what makes a daily
  job safe;
* **a copy does not itself repeat**, or the chain would branch and each month would
  start a new series of its own;
* catch-up is capped, so a gym that has been away for a year gets the recent months and
  is told the rest were skipped rather than handed a year of drafts;
* the off switch is honoured, and the amount, category, vendor, branch and payment mode
  carry across.

Every test passes an explicit ``as_of`` and derives its dates from the root rather than
from today. ``add_months`` is not reversible at a month end -- 31 Mar back one month is
28 Feb, and forward again is 28 Mar, not 31 -- so a suite written against "today" passes
for 28 days a month and fails on the rest. This repository already carries two
date-dependent flakes; this is not going to be the third.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, getdate, today

from netgainz.net_gainz.accounting import recurring

TAG = "ZZREC"


def _clear():
	for name in frappe.get_all("Expense", filters={"notes": ["like", f"%{TAG}%"]}, pluck="name"):
		doc = frappe.get_doc("Expense", name)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc("Expense", name, force=True, ignore_permissions=True)
	for name in frappe.get_all("Expense Category", filters={"name": ["like", f"{TAG}%"]}, pluck="name"):
		frappe.delete_doc("Expense Category", name, force=True, ignore_permissions=True)
	frappe.db.commit()


class TestRecurringExpenses(FrappeTestCase):
	def setUp(self):
		_clear()
		self.category = self._category()

	def tearDown(self):
		_clear()

	# ------------------------------------------------------------------ helpers

	def _category(self):
		name = f"{TAG} Rent"
		if not frappe.db.exists("Expense Category", name):
			doc = frappe.new_doc("Expense Category")
			doc.category_name = name
			doc.insert(ignore_permissions=True)
		return name

	def _dates(self, periods_back, frequency="Monthly"):
		"""A root date and the ``as_of`` that is exactly N periods after it.

		Derived forwards from the root, so the arithmetic is self-consistent whatever
		day the suite runs on.
		"""
		months = recurring.STEP_MONTHS[frequency]
		root = getdate(add_months(today(), -periods_back * months))
		as_of = getdate(add_months(root, periods_back * months))
		return root, as_of

	def _expense(self, date, amount=25000, recurring_=True, frequency="Monthly", submit=True):
		doc = frappe.new_doc("Expense")
		doc.date = date
		doc.category = self.category
		doc.amount = amount
		doc.payment_mode = "Cash"
		doc.vendor = f"{TAG} Landlord"
		doc.notes = f"{TAG} seed"
		doc.is_recurring = 1 if recurring_ else 0
		doc.frequency = frequency if recurring_ else ""
		doc.insert(ignore_permissions=True)
		if submit:
			doc.submit()
		frappe.db.commit()
		return doc

	def _children(self, root):
		return frappe.get_all(
			"Expense", filters={"recurred_from": root}, fields=["name", "date", "docstatus"]
		)

	# -------------------------------------------------------------------- raising

	def test_a_month_behind_raises_one_draft(self):
		when, as_of = self._dates(1)
		root = self._expense(when)
		result = recurring.generate_recurring_expenses(as_of)
		self.assertEqual(result["created"], 1)
		kids = self._children(root.name)
		self.assertEqual(len(kids), 1)
		self.assertEqual(getdate(kids[0].date), as_of)

	def test_it_is_raised_as_a_draft_never_submitted(self):
		when, as_of = self._dates(1)
		root = self._expense(when)
		recurring.generate_recurring_expenses(as_of)
		kid = self._children(root.name)[0]
		self.assertEqual(kid.docstatus, 0, "a repeat must wait for the owner to submit it")

	def test_the_details_carry_across(self):
		when, as_of = self._dates(1)
		root = self._expense(when, amount=31500)
		recurring.generate_recurring_expenses(as_of)
		kid = frappe.get_doc("Expense", self._children(root.name)[0].name)
		self.assertEqual(kid.amount, 31500)
		self.assertEqual(kid.category, self.category)
		self.assertEqual(kid.vendor, f"{TAG} Landlord")
		self.assertEqual(kid.payment_mode, "Cash")

	def test_nothing_is_raised_before_it_is_due(self):
		self._expense(today())
		self.assertEqual(recurring.generate_recurring_expenses(today())["created"], 0)

	# ---------------------------------------------------------------- not twice

	def test_running_twice_raises_nothing_the_second_time(self):
		when, as_of = self._dates(1)
		root = self._expense(when)
		first = recurring.generate_recurring_expenses(as_of)["created"]
		second = recurring.generate_recurring_expenses(as_of)["created"]
		self.assertEqual(first, 1)
		self.assertEqual(second, 0, "a daily job must be safe to run twice")
		self.assertEqual(len(self._children(root.name)), 1)

	def test_a_copy_does_not_start_a_series_of_its_own(self):
		when, as_of = self._dates(1)
		root = self._expense(when)
		recurring.generate_recurring_expenses(as_of)
		kid = frappe.get_doc("Expense", self._children(root.name)[0].name)
		self.assertFalse(kid.is_recurring, "a copy must not branch the chain")
		self.assertEqual(kid.recurred_from, root.name)

	# ------------------------------------------------------------------ catch-up

	def test_a_long_gap_is_capped_and_the_rest_reported_as_skipped(self):
		when, as_of = self._dates(8)
		root = self._expense(when)
		result = recurring.generate_recurring_expenses(as_of)
		self.assertEqual(result["created"], recurring.MAX_CATCH_UP)
		self.assertGreater(result["skipped"], 0, "the backlog must be reported, not hidden")
		self.assertEqual(len(self._children(root.name)), recurring.MAX_CATCH_UP)

	def test_quarterly_steps_three_months(self):
		when, as_of = self._dates(1, "Quarterly")
		root = self._expense(when, frequency="Quarterly")
		recurring.generate_recurring_expenses(as_of)
		kid = self._children(root.name)[0]
		self.assertEqual(getdate(kid.date), as_of)

	def test_annually_does_not_fire_after_a_month(self):
		when, as_of = self._dates(1)
		self._expense(when, frequency="Annually")
		self.assertEqual(recurring.generate_recurring_expenses(as_of)["created"], 0)

	# --------------------------------------------------------------- the switch

	def test_the_off_switch_is_honoured(self):
		when, as_of = self._dates(1)
		self._expense(when)
		frappe.db.set_single_value("Business Settings", "recurring_expenses_enabled", 0)
		try:
			self.assertEqual(recurring.generate_recurring_expenses(as_of)["created"], 0)
		finally:
			frappe.db.set_single_value("Business Settings", "recurring_expenses_enabled", 1)

	def test_an_expense_not_marked_repeating_is_left_alone(self):
		when, as_of = self._dates(1)
		self._expense(when, recurring_=False)
		self.assertEqual(recurring.generate_recurring_expenses(as_of)["created"], 0)

	# ----------------------------------------------------------------- the read

	def test_the_preview_names_what_is_waiting(self):
		when, as_of = self._dates(2)
		root = self._expense(when)
		data = recurring.get_repeating(as_of)
		mine = [r for r in data["rows"] if r["root"] == root.name]
		self.assertEqual(len(mine), 1)
		self.assertEqual(len(mine[0]["due"]), 2)
		self.assertEqual(data["due_now"], sum(len(r["due"]) for r in data["rows"]))
