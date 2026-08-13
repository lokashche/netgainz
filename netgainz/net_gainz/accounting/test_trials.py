# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 8 DS-4: a free trial invoices nothing, then bills by itself.

The whole risk in a trial is billing the member anyway — on day one, at Rs.0, or twice
when it ends. These pin the opposite:

* enrolling on a trial raises **no invoice at all**, and the membership reads ``Trial``
  with the date it ends;
* the first real invoice falls the day AFTER the trial, at the full rate;
* a per-member override and an explicit "no trial" both beat the plan's default;
* a discount granted at joining still applies to that first invoice — a trial delays
  billing, it does not consume the discount.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import billing, discounts, trials
from netgainz.net_gainz.accounting import billing_fixtures as fx


class TestTrials(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()

	# ---- helpers --------------------------------------------------------- #
	def _enrol(self, tag, amount=1000.0, plan_trial_days=0, **membership_fields):
		plan = fx.make_plan(f"{tag} Plan", amount=amount)
		if plan_trial_days:
			plan.trial_days = plan_trial_days
			plan.save(ignore_permissions=True)
		member = fx.make_member(f"{tag} Member", plan.name)
		ms = frappe.get_doc(
			{
				"doctype": "Membership",
				"member": member.name,
				"membership_plan": plan.name,
				**membership_fields,
			}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _invoices(self, membership):
		return frappe.get_all("Sales Invoice", filters={"subscription": membership.subscription})

	def _finish_trial(self, membership):
		"""Wind the trial into the past and bill the first period, as the daily job would.

		ERPNext asks "am I trialling?" of TODAY (``period_has_passed`` uses ``nowdate``),
		never of the posting date — so simply posting a future date would still produce
		the 100%-discounted trial invoice. The dates have to genuinely have passed.
		"""
		today_ = getdate(today())
		frappe.db.set_value(
			"Subscription",
			membership.subscription,
			{
				"trial_period_start": add_days(today_, -8),
				"trial_period_end": add_days(today_, -1),
				"current_invoice_start": today_,
				"current_invoice_end": add_days(today_, 29),
			},
		)
		membership.db_set("trial_ends_on", add_days(today_, -1))
		membership.reload()
		frappe.get_doc("Subscription", membership.subscription).process(posting_date=today_)

	# ---- nothing is billed while the trial runs ---------------------------- #
	def test_a_trial_member_is_not_invoiced_at_enrolment(self):
		ms = self._enrol("DS4 Free", plan_trial_days=7)
		self.assertEqual(self._invoices(ms), [], "a trial raises no invoice, not even Rs.0")
		self.assertFalse(ms.current_sales_invoice)

	def test_the_membership_says_it_is_on_trial_and_when_it_ends(self):
		ms = self._enrol("DS4 Says", plan_trial_days=7)
		self.assertEqual(ms.status, trials.TRIAL_STATUS)
		self.assertEqual(getdate(ms.trial_ends_on), add_days(getdate(today()), 6))
		self.assertEqual(flt(ms.balance_due), 0.0)

	def test_billing_starts_the_day_after_the_trial(self):
		ms = self._enrol("DS4 After", plan_trial_days=7)
		first_billing = add_days(getdate(today()), 7)
		self.assertEqual(getdate(ms.next_renewal), first_billing)
		self.assertEqual(trials.first_billing_date(ms), first_billing)
		start = frappe.db.get_value("Subscription", ms.subscription, "current_invoice_start")
		self.assertEqual(getdate(start), first_billing)

	def test_the_first_invoice_after_the_trial_is_the_full_rate(self):
		ms = self._enrol("DS4 Full", amount=1500.0, plan_trial_days=7)
		self._finish_trial(ms)
		invoices = self._invoices(ms)
		self.assertEqual(len(invoices), 1)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoices[0].name, "net_total")), 1500.0)

	def test_the_subscription_reports_itself_as_trialling(self):
		ms = self._enrol("DS4 Status", plan_trial_days=7)
		self.assertEqual(frappe.db.get_value("Subscription", ms.subscription, "status"), "Trialling")

	# ---- who gets a trial, and who does not -------------------------------- #
	def test_no_trial_on_the_plan_means_billing_as_usual(self):
		ms = self._enrol("DS4 None", amount=1000.0)
		self.assertTrue(ms.current_sales_invoice, "an ordinary member is billed on enrolment")
		self.assertEqual(ms.status, "Pending")

	def test_a_membership_override_beats_the_plan(self):
		ms = self._enrol("DS4 Override", plan_trial_days=7, trial_days=30)
		self.assertEqual(getdate(ms.trial_ends_on), add_days(getdate(today()), 29))

	def test_skip_trial_denies_the_plans_trial(self):
		ms = self._enrol("DS4 Skip", plan_trial_days=7, skip_trial=1)
		self.assertFalse(ms.trial_ends_on)
		self.assertTrue(ms.current_sales_invoice, "billed straight away")

	def test_resolve_trial_days_prefers_the_override_then_the_plan(self):
		plan = fx.make_plan("DS4 Resolve Plan", amount=1000.0)
		plan.trial_days = 14
		plan.save(ignore_permissions=True)
		base = {"membership_plan": plan.name}
		self.assertEqual(trials.resolve_trial_days(frappe._dict(base)), 14)
		self.assertEqual(trials.resolve_trial_days(frappe._dict({**base, "trial_days": 3})), 3)
		self.assertEqual(trials.resolve_trial_days(frappe._dict({**base, "skip_trial": 1})), 0)

	# ---- trials and discounts compose -------------------------------------- #
	def test_a_joining_discount_survives_the_trial(self):
		"""A trial delays the first invoice; it does not use up the discount."""
		ms = self._enrol(
			"DS4 Disc",
			amount=2000.0,
			plan_trial_days=7,
			discount_type=discounts.PERCENTAGE,
			discount_value=25,
			discount_reason="Joining offer",
		)
		self._finish_trial(ms)
		invoice = self._invoices(ms)[0].name
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice, "net_total")), 1500.0)

	# ---- what the owner sees ------------------------------------------------ #
	def test_trials_ending_splits_soon_from_later(self):
		soon = self._enrol("DS4 Soon", plan_trial_days=3)
		later = self._enrol("DS4 Later", plan_trial_days=30)
		report = trials.trials_ending(within_days=7)
		self.assertEqual(report["on_trial"], 2)
		self.assertIn(soon.name, [r["name"] for r in report["ending_soon"]])
		self.assertIn(later.name, [r["name"] for r in report["later"]])

	def test_trial_summary_counts_running_trials_separately(self):
		self._enrol("DS4 Sum", plan_trial_days=7)
		summary = trials.trial_summary()
		self.assertEqual(summary["trials"], 1)
		self.assertEqual(summary["running"], 1)
		self.assertEqual(summary["finished"], 0)
		self.assertIsNone(summary["conversion_rate"], "nothing has finished yet")

	def test_billing_a_trial_member_by_hand_is_refused(self):
		"""The owner's "generate invoice now" would otherwise raise a submitted Rs.0
		invoice — ERPNext discounts a trialling subscription 100% — and that invoice
		would then stand in for the real one."""
		ms = self._enrol("DS4 Manual", plan_trial_days=7)
		with self.assertRaises(frappe.ValidationError):
			billing.generate_membership_invoice(ms.name)
		self.assertEqual(self._invoices(ms), [])

	def test_a_finished_trial_that_was_billed_counts_as_converted(self):
		ms = self._enrol("DS4 Conv", plan_trial_days=7)
		self._finish_trial(ms)
		summary = trials.trial_summary()
		self.assertEqual(summary["finished"], 1)
		self.assertEqual(summary["converted"], 1)
		self.assertEqual(summary["conversion_rate"], 100.0)

	def test_a_trial_member_is_not_listed_as_due_for_renewal(self):
		"""They have a first-billing date, but nothing has been sold to them yet."""
		from netgainz.net_gainz.operations import renewals

		ms = self._enrol("DS4 NotRenewal", plan_trial_days=3)
		listed = [
			r["subscription"]
			for r in renewals.get_renewals(within_days=30)["due_soon"]
			+ renewals.get_renewals(within_days=30)["overdue"]
		]
		self.assertNotIn(ms.name, listed)
