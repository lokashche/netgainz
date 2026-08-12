# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 9 OP-3: freeze, plan change, cancellation, transfer (ADR-0008).

Pinned — the two traps the OP-3.0 trace found come first:

* a freeze shifts BOTH period dates and keeps the window a full cycle long
  (ERPNext left alone anchors the end to start_date and bills a short window at
  the full rate);
* a spent trial no longer steers billing (the subclass override): the period
  advance and a restart both honor the requested date on ex-trial
  subscriptions — without this, every trial member silently stops renewing
  after one paid cycle;
* the freeze survives the daily job and bills exactly at the unfreeze date;
* credits come only from the current PAID period, are capped at the new price,
  and are exempt from the staff discount cap (engine arithmetic, not
  generosity);
* cancellation follows the TENANT's refund policy; cash out is owner-only;
  Cancelled is terminal and never renews or nags;
* a transfer cancels one membership and starts the other with the remaining
  value as a first-invoice credit.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing_fixtures as fx
from netgainz.net_gainz.accounting import refunds
from netgainz.net_gainz.operations import lifecycle, renewals

STAFF_USER = "op3-frontdesk@example.com"
OWNER_USER = "op3-owner@example.com"


class TestLifecycle(FrappeTestCase):
	def setUp(self):
		fx.clear_billing_data()
		fx.ensure_cash_account()
		permissions.ensure_roles()
		self._user(STAFF_USER, permissions.GYM_STAFF)
		self._user(OWNER_USER, permissions.GYM_OWNER)
		frappe.db.set_single_value("Business Settings", "cancellation_refund_policy", "No refund")
		self.addCleanup(frappe.set_user, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _user(self, email, role):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@")[0],
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		if role:
			user = frappe.get_doc("User", email)
			if role not in [r.role for r in user.roles]:
				user.append("roles", {"role": role})
				user.save(ignore_permissions=True)

	def _sub(self, ms):
		return frappe.get_doc("Subscription", ms.subscription)

	def _trial_enrol(self, tag, amount=1000.0, trial_days=7):
		plan = fx.make_plan(f"{tag} Plan", amount=amount)
		plan.trial_days = trial_days
		plan.save(ignore_permissions=True)
		member = fx.make_member(f"{tag} Member", plan.name)
		ms = frappe.get_doc(
			{"doctype": "Membership", "member": member.name, "membership_plan": plan.name}
		).insert(ignore_permissions=True)
		ms.reload()
		return ms

	def _window_days(self, ms):
		return lifecycle._paid_window(ms)["days"]

	# ---- the traps first ---------------------------------------------------- #
	def test_freeze_shifts_both_dates_full_cycle(self):
		ms = fx.enrol_and_collect("OP3 Freeze", amount=1000.0, duration=30)
		sub = self._sub(ms)
		old_start = getdate(sub.current_invoice_start)

		result = lifecycle.freeze_membership(ms.name, today(), add_days(today(), 13), reason="Vacation")
		self.assertEqual(result["days"], 14)

		sub.reload()
		new_start = getdate(sub.current_invoice_start)
		self.assertEqual(new_start, add_days(old_start, 14))
		# R21: the window stays a full cycle — never a short window at full price.
		from frappe.utils import add_to_date

		expected_end = getdate(add_to_date(new_start, **sub.get_billing_cycle_data()))
		self.assertEqual(getdate(sub.current_invoice_end), expected_end)

	def test_spent_trial_no_longer_steers_the_period(self):
		# The override regression: without it, update_subscription_period snaps an
		# ex-trial subscription back to trial_end + 1 and renewals silently stop.
		ms = fx.enrol_and_collect("OP3 ExTrial", amount=1000.0, duration=30)
		sub_name = ms.subscription
		frappe.db.set_value(
			"Subscription",
			sub_name,
			{
				"start_date": add_days(today(), -40),
				"trial_period_start": add_days(today(), -40),
				"trial_period_end": add_days(today(), -33),
			},
		)
		sub = frappe.get_doc("Subscription", sub_name)
		requested = add_days(today(), -2)
		sub.update_subscription_period(requested)
		self.assertEqual(getdate(sub.current_invoice_start), getdate(requested))

		# ...and restart_subscription lands where asked, not at trial_end + 1.
		sub.reload()
		sub.cancel_subscription()
		sub.reload()
		restart_on = add_days(today(), 10)
		sub.restart_subscription(posting_date=restart_on)
		sub.reload()
		self.assertEqual(getdate(sub.current_invoice_start), getdate(restart_on))

	def test_running_trial_still_anchors_the_period(self):
		# The override must not touch a LIVE trial: first paid period stays at
		# trial_end + 1.
		ms = self._trial_enrol("OP3 LiveTrial")
		sub = self._sub(ms)
		self.assertEqual(getdate(sub.current_invoice_start), add_days(getdate(sub.trial_period_end), 1))

	# ---- freeze behaviour ---------------------------------------------------- #
	def test_freeze_survives_daily_job_and_bills_at_unfreeze(self):
		ms = fx.enrol_and_collect("OP3 FreezeBill", amount=1000.0, duration=30)
		sub = self._sub(ms)
		lifecycle.freeze_membership(ms.name, today(), add_days(today(), 13))
		sub.reload()
		new_start = getdate(sub.current_invoice_start)
		invoices_before = len(sub.invoices)

		sub.process(posting_date=add_days(today(), 1))
		sub.reload()
		self.assertEqual(len(sub.invoices), invoices_before, "no invoice during the freeze")
		self.assertEqual(getdate(sub.current_invoice_start), new_start, "dates survive the job")

		sub.process(posting_date=new_start)
		sub.reload()
		self.assertEqual(len(sub.invoices), invoices_before + 1)
		newest = frappe.db.get_value(
			"Sales Invoice", sub.invoices[-1].name, ["from_date", "net_total"], as_dict=True
		)
		self.assertEqual(getdate(newest.from_date), new_start)
		self.assertEqual(flt(newest.net_total), 1000.0)

	def test_freeze_updates_next_renewal(self):
		ms = fx.enrol_and_collect("OP3 FreezeRenewal", amount=1000.0, duration=30)
		before = getdate(frappe.db.get_value("Membership", ms.name, "next_renewal"))
		lifecycle.freeze_membership(ms.name, today(), add_days(today(), 9))
		after = getdate(frappe.db.get_value("Membership", ms.name, "next_renewal"))
		self.assertEqual(after, add_days(before, 10))

	def test_unfreeze_early_gives_unused_days_back(self):
		ms = fx.enrol_and_collect("OP3 Unfreeze", amount=1000.0, duration=30)
		result = lifecycle.freeze_membership(ms.name, today(), add_days(today(), 13))
		sub = self._sub(ms)
		frozen_start = getdate(sub.current_invoice_start)

		# Back after 4 days: 10 of the 14 shifted days come back.
		back = lifecycle.unfreeze_membership(result["freeze"], on_date=add_days(today(), 4))
		self.assertEqual(back["days_returned"], 10)
		sub.reload()
		self.assertEqual(getdate(sub.current_invoice_start), add_days(frozen_start, -10))
		frz = frappe.get_doc("Membership Freeze", result["freeze"])
		self.assertEqual(getdate(frz.to_date), getdate(add_days(today(), 3)))
		self.assertEqual(frz.days_shifted, 4)

	def test_freeze_guards(self):
		trial_ms = self._trial_enrol("OP3 TrialFreeze")
		with self.assertRaises(frappe.ValidationError):
			lifecycle.freeze_membership(trial_ms.name, today(), add_days(today(), 5))

		ms = fx.enrol_and_collect("OP3 Overlap", amount=1000.0, duration=30)
		lifecycle.freeze_membership(ms.name, today(), add_days(today(), 5))
		with self.assertRaises(frappe.ValidationError):
			lifecycle.freeze_membership(ms.name, add_days(today(), 3), add_days(today(), 8))

	def test_freeze_record_inherits_member_branch(self):
		ms = fx.enrol_and_collect("OP3 FrzBranch", amount=1000.0, duration=30)
		result = lifecycle.freeze_membership(ms.name, today(), add_days(today(), 2))
		self.assertEqual(
			frappe.db.get_value("Membership Freeze", result["freeze"], "branch"),
			frappe.db.get_value("Member", ms.member, "branch"),
		)

	# ---- plan change --------------------------------------------------------- #
	def test_change_plan_same_day_full_credit(self):
		ms = fx.enrol_and_collect("OP3 Upgrade", amount=1000.0, duration=30)
		up = fx.make_plan("OP3 Upgrade Target Plan", amount=2000.0)
		days = self._window_days(ms)

		result = lifecycle.change_plan(ms.name, up.name)
		self.assertEqual(result["credit"], 1000.0, "nothing used yet: the whole 1000 comes back")
		self.assertEqual(result["unused_days"], days)

		inv = frappe.db.get_value(
			"Sales Invoice", result["invoice"], ["net_total", "from_date"], as_dict=True
		)
		self.assertEqual(flt(inv.net_total), 1000.0, "2000 for the new cycle minus 1000 credit")
		self.assertEqual(getdate(inv.from_date), getdate(today()))
		item = frappe.db.get_value("Sales Invoice Item", {"parent": result["invoice"]}, "item_code")
		self.assertEqual(item, "OP3 Upgrade Target Plan")
		self.assertEqual(frappe.db.get_value("Membership", ms.name, "membership_plan"), up.name)

	def test_change_plan_mid_cycle_prorates(self):
		ms = fx.enrol_and_collect("OP3 MidCycle", amount=900.0, duration=30)
		up = fx.make_plan("OP3 MidCycle Target Plan", amount=2000.0)
		days = self._window_days(ms)

		# 10 days in: the unused remainder of the 900-rupee period comes back.
		result = lifecycle.change_plan(ms.name, up.name, change_date=add_days(today(), 10))
		expected_unused = days - 10
		expected_credit = flt(900.0 * expected_unused / days, 2)
		self.assertEqual(result["unused_days"], expected_unused)
		self.assertEqual(result["credit"], expected_credit)
		inv_net = frappe.db.get_value("Sales Invoice", result["invoice"], "net_total")
		self.assertEqual(flt(inv_net), flt(2000.0 - expected_credit, 2))

	def test_change_plan_downgrade_credit_capped(self):
		ms = fx.enrol_and_collect("OP3 Downgrade", amount=1000.0, duration=30)
		down = fx.make_plan("OP3 Downgrade Target Plan", amount=300.0)

		result = lifecycle.change_plan(ms.name, down.name)
		self.assertEqual(result["credit"], 300.0, "capped at the new price — no minted money")
		inv_net = frappe.db.get_value("Sales Invoice", result["invoice"], "net_total")
		self.assertEqual(flt(inv_net), 0.0)

	def test_change_plan_unpaid_period_gives_no_credit(self):
		ms = fx.enrol("OP3 UnpaidChange", amount=1000.0, duration=30)
		up = fx.make_plan("OP3 UnpaidChange Target Plan", amount=2000.0)
		result = lifecycle.change_plan(ms.name, up.name)
		self.assertEqual(result["credit"], 0.0)

	def test_staff_change_plan_needs_no_pin(self):
		# The credit is engine arithmetic, not staff generosity — DS-5's cap must
		# not demand the owner's PIN for it.
		frappe.db.set_single_value("Business Settings", "max_discount_percent", 10)
		ms = fx.enrol_and_collect("OP3 StaffChange", amount=1000.0, duration=30)
		up = fx.make_plan("OP3 StaffChange Target Plan", amount=2000.0)
		frappe.set_user(STAFF_USER)
		result = lifecycle.change_plan(ms.name, up.name)
		self.assertEqual(result["credit"], 1000.0)

	# ---- cancellation -------------------------------------------------------- #
	def test_cancel_no_refund_policy(self):
		ms = fx.enrol_and_collect("OP3 Cancel", amount=1000.0, duration=30)
		result = lifecycle.cancel_membership(ms.name, reason="Moving city")
		self.assertEqual(result["refund_amount"], 0.0)

		ms.reload()
		self.assertEqual(ms.status, "Cancelled")
		self.assertFalse(ms.next_renewal)
		self.assertEqual(ms.cancellation_reason, "Moving city")
		self.assertEqual(frappe.db.get_value("Subscription", ms.subscription, "status"), "Cancelled")
		self.assertEqual(refunds.credited_against(ms.current_sales_invoice), 0.0)

		# Terminal: a later save does not resurrect a derived status...
		ms.save(ignore_permissions=True)
		ms.reload()
		self.assertEqual(ms.status, "Cancelled")
		# ...and the renewals list never nags about it.
		names = {
			r["subscription"]
			for r in renewals.get_renewals(within_days=60)["due_soon"]
			+ renewals.get_renewals(within_days=60)["overdue"]
		}
		self.assertNotIn(ms.name, names)

	def test_cancel_prorated_refund_pays_cash_and_is_owner_only(self):
		frappe.db.set_single_value("Business Settings", "cancellation_refund_policy", "Prorated unused days")

		staff_ms = fx.enrol_and_collect("OP3 StaffRefund", amount=1000.0, duration=30)
		frappe.set_user(STAFF_USER)
		with self.assertRaises(frappe.PermissionError):
			lifecycle.cancel_membership(staff_ms.name)

		frappe.set_user(OWNER_USER)
		result = lifecycle.cancel_membership(staff_ms.name, reason="Injury")
		self.assertEqual(result["refund_amount"], 1000.0, "cancelled on day one: every day unused")
		self.assertTrue(result["refund"]["credit_note"])
		self.assertEqual(flt(result["refund"]["cash_refunded"]), 1000.0)

	def test_staff_can_cancel_when_nothing_to_refund(self):
		frappe.db.set_single_value("Business Settings", "cancellation_refund_policy", "Prorated unused days")
		ms = fx.enrol("OP3 StaffCancel", amount=1000.0, duration=30)  # unpaid
		frappe.set_user(STAFF_USER)
		result = lifecycle.cancel_membership(ms.name)
		self.assertEqual(result["refund_amount"], 0.0)
		self.assertEqual(frappe.db.get_value("Membership", ms.name, "status"), "Cancelled")

	def test_cancelled_membership_locks_lifecycle(self):
		ms = fx.enrol_and_collect("OP3 Locked", amount=1000.0, duration=30)
		lifecycle.cancel_membership(ms.name)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.freeze_membership(ms.name, today(), add_days(today(), 5))
		with self.assertRaises(frappe.ValidationError):
			lifecycle.cancel_membership(ms.name)

	# ---- transfer ------------------------------------------------------------ #
	def test_transfer_moves_remaining_value(self):
		ms = fx.enrol_and_collect("OP3 TransferFrom", amount=1000.0, duration=30)
		to_member = fx.make_member("OP3 TransferTo Member")

		result = lifecycle.transfer_membership(ms.name, to_member.name)
		self.assertEqual(result["credit"], 1000.0)

		old = frappe.get_doc("Membership", ms.name)
		self.assertEqual(old.status, "Cancelled")
		self.assertIn(to_member.name, old.cancellation_reason)

		new = frappe.get_doc("Membership", result["new_membership"])
		self.assertEqual(new.member, to_member.name)
		self.assertEqual(new.membership_plan, ms.membership_plan)
		self.assertEqual(flt(new.discount_value), 1000.0)
		# The receiver's first invoice is fully covered by the transferred value.
		inv_net = frappe.db.get_value("Sales Invoice", new.current_sales_invoice, "net_total")
		self.assertEqual(flt(inv_net), 0.0)

	def test_transfer_refused_when_receiver_has_live_membership(self):
		ms = fx.enrol_and_collect("OP3 TransferBlockedFrom", amount=1000.0, duration=30)
		other = fx.enrol_and_collect("OP3 TransferBlockedTo", amount=1000.0, duration=30)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.transfer_membership(ms.name, other.member)

	# ---- who may call it ----------------------------------------------------- #
	def test_role_less_session_is_refused(self):
		ms = fx.enrol_and_collect("OP3 NoRole", amount=1000.0, duration=30)
		self._user("op3-visitor@example.com", None)
		frappe.set_user("op3-visitor@example.com")
		with self.assertRaises(frappe.PermissionError):
			lifecycle.freeze_membership(ms.name, today(), add_days(today(), 5))
		with self.assertRaises(frappe.PermissionError):
			lifecycle.cancel_membership(ms.name)
