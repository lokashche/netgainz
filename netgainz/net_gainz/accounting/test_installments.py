# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""WP-10 end-to-end: plan cadences, due mechanism and installments, both modes.

Commitment  — one invoice for the period carrying a payment_schedule row per part.
Pay-as-you-go — one invoice per part, so the member only ever owes the current one.

Both reduce to the same `open_obligations()` list, which is what everything
downstream (status, balance, next-due, payment allocation) actually reads.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import billing
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestCommitmentInstallments(FrappeTestCase):
	"""Mode A: one invoice, several scheduled installments."""

	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	def _schedule(self, si):
		return frappe.get_all(
			"Payment Schedule",
			filters={"parent": si, "parenttype": "Sales Invoice"},
			fields=["due_date", "payment_amount", "outstanding", "payment_term", "idx"],
			order_by="idx asc",
		)

	def test_quarterly_in_three_builds_three_scheduled_rows(self):
		ms = fx.enrol(
			"Q3", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30
		)
		rows = self._schedule(ms.current_sales_invoice)
		self.assertEqual(len(rows), 3)
		# Due dates step by the configured gap.
		self.assertEqual(
			[getdate(r.due_date) for r in rows],
			[getdate(r0.due_date) for r0 in rows],  # sanity: all set
		)
		self.assertTrue(all(r.due_date for r in rows))
		gaps = [
			(getdate(rows[i + 1].due_date) - getdate(rows[i].due_date)).days
			for i in range(len(rows) - 1)
		]
		self.assertEqual(gaps, [30, 30])

	def test_schedule_always_totals_the_invoice(self):
		"""ERPNext rejects a schedule that does not tie to the grand total, so this
		is the invariant D6 rounding must never break."""
		for parts in (2, 3, 4):
			ms = fx.enrol(f"Tot{parts}", amount=10000.0, plan_type="Yearly", parts=parts, gap_days=30)
			grand = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
			rows = self._schedule(ms.current_sales_invoice)
			self.assertEqual(len(rows), parts)
			self.assertAlmostEqual(sum(flt(r.payment_amount) for r in rows), grand, places=2)

	def test_installment_amounts_are_clean_numbers(self):
		"""D6: the odd money rides on the FIRST installment, not the last."""
		ms = fx.enrol("Clean", amount=10000.0, plan_type="Yearly", parts=3, gap_days=30)
		rows = self._schedule(ms.current_sales_invoice)
		amounts = [flt(r.payment_amount) for r in rows]
		self.assertEqual(amounts[1], amounts[2], "later installments are equal")
		self.assertGreaterEqual(amounts[0], amounts[1], "the first absorbs the remainder")
		self.assertTrue(all(a % 100 == 0 for a in amounts[1:]), amounts)

	def test_obligations_expose_each_installment(self):
		ms = fx.enrol("Obl", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		obligations = billing.open_obligations(ms)
		self.assertEqual(len(obligations), 3)
		self.assertTrue(all(o["outstanding"] > 0 for o in obligations))
		# next_due is the earliest unpaid one.
		self.assertEqual(billing.next_due(obligations)["idx"], obligations[0]["idx"])

	def test_payment_settles_the_oldest_installment_first(self):
		"""A part payment must CLEAR installment 1, not smear across all three —
		otherwise none would ever read as settled and nothing would go overdue."""
		ms = fx.enrol("Alloc", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		first = billing.open_obligations(ms)[0]
		fx.collect(ms, amount=first["amount"])
		ms.reload()

		obligations = billing.open_obligations(ms)
		self.assertEqual(flt(obligations[0]["outstanding"]), 0.0, "installment 1 is settled")
		self.assertGreater(flt(obligations[1]["outstanding"]), 0.0, "installment 2 still open")
		self.assertEqual(billing.next_due(obligations)["idx"], obligations[1]["idx"])

	def test_status_is_partial_after_one_installment(self):
		ms = fx.enrol("Part", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		fx.collect(ms, amount=billing.open_obligations(ms)[0]["amount"])
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(ms.status, "Partial")
		self.assertGreater(flt(ms.balance_due), 0.0)

	def test_due_date_tracks_the_next_unpaid_installment(self):
		"""R8: due_date must be the EARLIEST unpaid obligation, never the invoice's
		own due date (which, with installments, is the LAST one)."""
		ms = fx.enrol("Due", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		obligations = billing.open_obligations(ms)
		ms.save(ignore_permissions=True)
		self.assertEqual(getdate(ms.due_date), obligations[0]["due_date"])

		fx.collect(ms, amount=obligations[0]["amount"])
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(getdate(ms.due_date), obligations[1]["due_date"])

	def test_paying_every_installment_settles_the_membership(self):
		ms = fx.enrol("Full", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		for obligation in billing.open_obligations(ms):
			fx.collect(ms, amount=obligation["amount"])
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(ms.status, "Paid")
		self.assertEqual(flt(ms.balance_due), 0.0)

	def test_missed_installment_reads_overdue(self):
		"""D3: a member who paid part 1 and missed part 2 is Overdue."""
		ms = fx.enrol("Miss", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		obligations = billing.open_obligations(ms)
		fx.collect(ms, amount=obligations[0]["amount"])
		# Drag installment 2's due date into the past.
		frappe.db.set_value(
			"Payment Schedule",
			{"parent": ms.current_sales_invoice, "idx": obligations[1]["idx"]},
			"due_date",
			add_days(today(), -3),
		)
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(ms.status, "Overdue")

	def test_missed_installment_does_not_freeze_the_member(self):
		"""D3: Overdue, yes — frozen, no. They have already given the gym money."""
		ms = fx.enrol("NoFreeze", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		obligations = billing.open_obligations(ms)
		fx.collect(ms, amount=obligations[0]["amount"])
		frappe.db.set_value(
			"Payment Schedule",
			{"parent": ms.current_sales_invoice, "idx": obligations[1]["idx"]},
			"due_date",
			add_days(today(), -3),
		)
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(ms.status, "Overdue")
		self.assertEqual(frappe.db.get_value("Member", ms.member, "status"), "Active")

	def test_member_who_paid_nothing_still_freezes(self):
		"""The contrast to the test above: the no-freeze guard is about members who
		have ALREADY paid something, not a blanket amnesty."""
		ms = fx.enrol("Freeze", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		for obligation in billing.open_obligations(ms):
			frappe.db.set_value(
				"Payment Schedule",
				{"parent": ms.current_sales_invoice, "idx": obligation["idx"]},
				"due_date",
				add_days(today(), -3),
			)
		ms.reload()
		ms.save(ignore_permissions=True)
		self.assertEqual(ms.status, "Overdue")
		self.assertEqual(frappe.db.get_value("Member", ms.member, "status"), "Frozen")

	def test_single_part_plan_has_one_obligation(self):
		ms = fx.enrol("One", amount=1000.0, plan_type="Monthly", parts=1)
		self.assertEqual(len(billing.open_obligations(ms)), 1)


class TestPayAsYouGo(FrappeTestCase):
	"""Mode B: one invoice per installment; cadence = duration / parts."""

	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	def test_cadence_is_duration_divided_by_parts(self):
		# Quarterly (90d) in 3 -> bills monthly.
		ms = fx.enrol(
			"PAYG", amount=9000.0, plan_type="Quarterly",
			billing_mode="Pay-as-you-go", parts=3, gap_days=30,
		)
		plan = frappe.db.get_value("Membership Plan", ms.membership_plan, "subscription_plan")
		interval, count = frappe.db.get_value(
			"Subscription Plan", plan, ["billing_interval", "billing_interval_count"]
		)
		self.assertEqual((interval, count), ("Month", 1))

	def test_member_only_owes_the_current_period(self):
		ms = fx.enrol(
			"PAYGOwe", amount=9000.0, plan_type="Quarterly",
			billing_mode="Pay-as-you-go", parts=3, gap_days=30,
		)
		obligations = billing.open_obligations(ms)
		self.assertEqual(len(obligations), 1, "only the current invoice is owed")
		grand = flt(frappe.db.get_value("Sales Invoice", ms.current_sales_invoice, "grand_total"))
		self.assertAlmostEqual(flt(obligations[0]["amount"]), grand, places=2)

	def test_invoice_is_not_split_into_a_schedule(self):
		"""Each invoice IS one installment, so it carries a single due date."""
		ms = fx.enrol(
			"PAYGSched", amount=9000.0, plan_type="Quarterly",
			billing_mode="Pay-as-you-go", parts=3, gap_days=30,
		)
		rows = frappe.get_all(
			"Payment Schedule", filters={"parent": ms.current_sales_invoice}, fields=["name"]
		)
		self.assertLessEqual(len(rows), 1)

	def test_non_calendar_split_is_rejected_at_plan_save(self):
		"""R12: quarterly-in-2 = 45 days, which ERPNext can only express as Day x 45
		— drifting off the calendar forever. Reject it now, not six months later."""
		with self.assertRaises(frappe.ValidationError) as caught:
			fx.make_plan(
				"PAYG Bad Split Plan", amount=9000.0, plan_type="Quarterly",
				billing_mode="Pay-as-you-go", parts=2, gap_days=45,
			)
		self.assertIn("45", str(caught.exception))

	def test_commitment_mode_allows_any_split(self):
		"""The same 2-way split is fine under Commitment — the due dates are just
		dates on a schedule, with no cadence to divide."""
		plan = fx.make_plan(
			"Commitment Any Split Plan", amount=9000.0, plan_type="Quarterly",
			billing_mode="Commitment", parts=2, gap_days=45,
		)
		self.assertEqual(plan.installment_count, 2)


class TestPlanConfiguration(FrappeTestCase):
	def test_plan_type_sets_the_duration(self):
		for plan_type, days in (
			("Monthly", 30), ("Quarterly", 90), ("Half-Yearly", 180), ("Yearly", 365)
		):
			plan = fx.make_plan(f"Cadence {plan_type} Plan", amount=1000.0, plan_type=plan_type)
			self.assertEqual(plan.duration_in_days, days, plan_type)

	def test_explicit_duration_infers_the_cadence(self):
		"""A plan created with a duration but no plan_type (API caller, import, or a
		pre-WP-10 plan) keeps its duration — the Monthly default must not rewrite it."""
		plan = frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": "Inferred Quarterly Plan",
				"duration_in_days": 90,
				"amount": 9000.0,
				"gst_hsn_code": fx.SAC,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(plan.duration_in_days, 90)
		self.assertEqual(plan.plan_type, "Quarterly")

	def test_explicit_odd_duration_becomes_custom(self):
		plan = frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": "Inferred Odd Plan",
				"duration_in_days": 45,
				"amount": 1000.0,
				"gst_hsn_code": fx.SAC,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(plan.duration_in_days, 45)
		self.assertEqual(plan.plan_type, "Custom")

	def test_custom_plan_type_keeps_its_own_duration(self):
		plan = fx.make_plan(
			"Cadence Custom Plan", amount=1000.0, plan_type="Custom", duration=45
		)
		self.assertEqual(plan.duration_in_days, 45)

	def test_policy_generates_a_template_the_owner_never_names(self):
		"""D7: the owner sets dropdowns; the ERPNext template is created silently."""
		plan = fx.make_plan(
			"Silent Template Plan", amount=9000.0, plan_type="Quarterly",
			due_rule="Within 7 days", parts=3, gap_days=30,
		)
		self.assertTrue(plan.payment_terms_template)
		self.assertTrue(
			frappe.db.exists("Payment Terms Template", plan.payment_terms_template)
		)

	def test_membership_inherits_the_plan_policy(self):
		ms = fx.enrol("Inherit", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		plan_template = frappe.db.get_value(
			"Membership Plan", ms.membership_plan, "payment_terms_template"
		)
		self.assertEqual(ms.payment_terms_template, plan_template)

	def test_membership_override_beats_the_plan(self):
		"""D2: one member can negotiate different terms without cloning the plan."""
		ms = fx.enrol("Override", amount=9000.0, plan_type="Quarterly", parts=3, gap_days=30)
		inherited = ms.payment_terms_template
		ms.installment_count = 2
		ms.installment_gap_days = 45
		ms.save(ignore_permissions=True)
		self.assertNotEqual(ms.payment_terms_template, inherited)
		# ...and the override really is a 2-part policy.
		template = frappe.get_doc("Payment Terms Template", ms.payment_terms_template)
		self.assertEqual(len(template.terms), 2)

	def test_plan_without_a_tax_code_still_bills(self):
		"""Regression: the owner app never sends an HSN/SAC, and provision_item
		SKIPS silently without one — so every plan created through the app was
		unbillable (no Item, no Subscription Plan). The tenant default fills it."""
		plan = frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": "No SAC From Owner App Plan",
				"plan_type": "Monthly",
				"amount": 1500.0,
			}
		).insert(ignore_permissions=True)
		plan.reload()
		self.assertTrue(plan.gst_hsn_code, "the tenant default tax code is applied")
		self.assertTrue(plan.item, "a sellable Item is provisioned")
		self.assertTrue(plan.subscription_plan, "so billing can actually happen")

	def test_split_due_date_field_is_gone(self):
		"""It was declared but never read — an abandoned first attempt at this."""
		self.assertFalse(frappe.get_meta("Membership").has_field("split_due_date"))
