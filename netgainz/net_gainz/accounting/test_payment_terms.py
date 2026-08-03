# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Tests for WP-10's payment-policy -> ERPNext Payment Terms Template generator.

The owner-facing contract is two dropdowns (due rule + installment count); these
tests pin the machinery that turns that into a native template the owner never
sees, and the D6 rounding that keeps installments clean AND exactly totalling.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.accounting import payment_terms as pt


class TestSplitAmounts(FrappeTestCase):
	"""D6: clean numbers, last row absorbs the remainder, total always exact."""

	def test_single_part_is_the_whole_amount(self):
		self.assertEqual(pt.split_amounts(9000, 1), [9000.0])

	def test_clean_split_stays_clean(self):
		self.assertEqual(pt.split_amounts(9000, 3), [3000.0, 3000.0, 3000.0])

	def test_uneven_split_rounds_to_clean_numbers(self):
		# The owner's chosen behaviour: 10,000 in 3 -> 3,400 / 3,300 / 3,300.
		self.assertEqual(pt.split_amounts(10000, 3), [3400.0, 3300.0, 3300.0])

	def test_half_yearly_in_two(self):
		self.assertEqual(pt.split_amounts(9000, 2), [4500.0, 4500.0])

	def test_totals_are_exact_for_many_shapes(self):
		"""ERPNext rejects a payment schedule that does not tie to the invoice
		total, so this invariant is load-bearing, not cosmetic."""
		for total in (500, 999, 1000, 1333.33, 9000, 10000, 12000, 25000):
			for parts in range(1, 7):
				rows = pt.split_amounts(total, parts)
				self.assertEqual(len(rows), parts)
				self.assertAlmostEqual(sum(rows), float(total), places=2, msg=f"{total}/{parts}")
				self.assertTrue(all(r > 0 for r in rows), f"{total}/{parts} -> {rows}")

	def test_small_total_many_parts_never_goes_negative(self):
		rows = pt.split_amounts(500, 4)
		self.assertTrue(all(r > 0 for r in rows), rows)
		self.assertAlmostEqual(sum(rows), 500.0, places=2)

	def test_zero_parts_rejected(self):
		with self.assertRaises(ValueError):
			pt.split_amounts(1000, 0)


class TestSplitPortions(FrappeTestCase):
	def test_portions_total_exactly_100(self):
		for parts in range(1, 13):
			self.assertAlmostEqual(sum(pt.split_portions(parts)), 100.00, places=2, msg=str(parts))

	def test_remainder_rides_on_the_first_row(self):
		self.assertEqual(pt.split_portions(3), [33.34, 33.33, 33.33])


class TestEnsureTemplate(FrappeTestCase):
	def test_each_due_rule_builds_a_single_100_percent_row(self):
		for rule in (pt.DUE_ON_JOINING, pt.DUE_IN_7_DAYS, pt.DUE_5TH_NEXT_MONTH):
			name = pt.ensure_template(rule)
			doc = frappe.get_doc("Payment Terms Template", name)
			self.assertEqual(len(doc.terms), 1, rule)
			self.assertEqual(doc.terms[0].invoice_portion, 100.0)

	def test_due_rules_map_to_the_right_erpnext_semantics(self):
		on_joining = frappe.get_doc("Payment Terms Template", pt.ensure_template(pt.DUE_ON_JOINING))
		self.assertEqual(on_joining.terms[0].due_date_based_on, "Day(s) after invoice date")
		self.assertEqual(on_joining.terms[0].credit_days, 0)

		grace = frappe.get_doc("Payment Terms Template", pt.ensure_template(pt.DUE_IN_7_DAYS))
		self.assertEqual(grace.terms[0].credit_days, 7)

		month_end = frappe.get_doc(
			"Payment Terms Template", pt.ensure_template(pt.DUE_5TH_NEXT_MONTH)
		)
		self.assertEqual(
			month_end.terms[0].due_date_based_on, "Day(s) after the end of the invoice month"
		)
		self.assertEqual(month_end.terms[0].credit_days, 5)

	def test_installments_build_one_row_each_with_increasing_due_dates(self):
		name = pt.ensure_template(pt.DUE_ON_JOINING, parts=3, gap_days=30)
		doc = frappe.get_doc("Payment Terms Template", name)
		self.assertEqual(len(doc.terms), 3)
		self.assertEqual([r.credit_days for r in doc.terms], [0, 30, 60])
		self.assertAlmostEqual(sum(r.invoice_portion for r in doc.terms), 100.0, places=2)

	def test_allocate_by_payment_terms_is_on(self):
		"""Required for per-installment paid/outstanding tracking (WP-10.5)."""
		doc = frappe.get_doc(
			"Payment Terms Template", pt.ensure_template(pt.DUE_ON_JOINING, parts=2, gap_days=30)
		)
		self.assertTrue(doc.allocate_payment_based_on_payment_terms)
		self.assertTrue(all(r.payment_term for r in doc.terms))

	def test_is_idempotent(self):
		first = pt.ensure_template(pt.DUE_IN_7_DAYS, parts=4, gap_days=15)
		before = frappe.db.count("Payment Terms Template")
		second = pt.ensure_template(pt.DUE_IN_7_DAYS, parts=4, gap_days=15)
		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Payment Terms Template"), before)

	def test_unknown_due_rule_returns_none_not_an_error(self):
		self.assertIsNone(pt.ensure_template("Whenever they feel like it"))

	def test_zero_gap_rejected_for_installments(self):
		with self.assertRaises(frappe.ValidationError):
			pt.ensure_template(pt.DUE_ON_JOINING, parts=3, gap_days=0)

	def test_too_many_installments_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			pt.ensure_template(pt.DUE_ON_JOINING, parts=pt.MAX_INSTALLMENTS + 1, gap_days=30)
