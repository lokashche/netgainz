# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

# Custom imports
from datetime import date

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class Membership(Document):
	"""A member's enrolment on a plan, billed through ERPNext.

	WP-11 (fresh-start): there is exactly ONE billing path. Every membership drives
	a native ERPNext Subscription, so ``status`` / ``balance_due`` / ``due_date`` /
	``next_renewal`` all derive from that period's Sales Invoice (R4 — the invoice's
	``outstanding_amount`` is the single source of truth). The legacy
	``fee_collected``-vs-``tariff`` controller math is gone; those two fields remain
	only as deprecated display values and feed no calculation. Money is recorded
	exclusively as Payment Entries via ``accounting.billing.record_payment`` — never
	by editing ``fee_collected``.
	"""

	def validate(self):
		from netgainz.net_gainz.accounting import discounts, offers

		# DS-2: a chosen offer writes its terms in as an ordinary discount grant, so
		# everything below (and the invoice) sees ONE discount however it was given.
		offers.apply_offer_to_membership(self)
		# R17: the discount guardrails run server-side, so they hold however the
		# membership was saved — owner app, Desk, import or script.
		discounts.validate_membership_discount(self)

	def before_save(self):
		from netgainz.net_gainz.accounting import billing

		self.resolve_payment_terms()
		# Derives status / balance_due / due_date / next_renewal from the current
		# Sales Invoice. A no-op while billing has not been provisioned yet
		# (provisioning is best-effort and must never block enrolment).
		billing.sync_from_billing(self)
		self.calculate_overdue_days()

	def resolve_payment_terms(self):
		"""WP-10.1 (D2/D7): resolve this membership's payment terms.

		A per-member override (its own due rule / installment settings) wins;
		otherwise the plan's policy applies. The resolved template is stored
		read-only — the owner configures gym-language dropdowns, never a template.
		"""
		from netgainz.net_gainz.accounting import payment_terms

		if self.payment_due_rule or int(self.installment_count or 0) > 1:
			plan = (
				frappe.db.get_value(
					"Membership Plan",
					self.membership_plan,
					["payment_due_rule", "installment_count", "installment_gap_days"],
					as_dict=True,
				)
				if self.membership_plan
				else None
			)
			due_rule = self.payment_due_rule or (plan and plan.payment_due_rule)
			parts = int(self.installment_count or 0) or int((plan and plan.installment_count) or 1)
			gap = int(self.installment_gap_days or 0) or int(
				(plan and plan.installment_gap_days) or 30
			)
			self.payment_terms_template = payment_terms.ensure_template(due_rule, parts, gap)
		elif self.membership_plan:
			self.payment_terms_template = frappe.db.get_value(
				"Membership Plan", self.membership_plan, "payment_terms_template"
			)

	def on_update(self):
		from netgainz.net_gainz.accounting import discounts

		# DS-5: record what happened to this membership's discount, if anything did.
		# After the save, so a refused grant leaves no trace claiming it was given.
		discounts.log_discount_change(self)
		# NB: `on_update` is Frappe's post-save hook. This used to be spelled
		# `after_save`, which Frappe never calls — so member freezing silently did
		# nothing from the day it was written until WP-10.6's tests caught it.
		self.sync_member_status()

	def calculate_overdue_days(self):
		"""Days past the current invoice's due date, once it is genuinely overdue.

		``due_date`` is invoice-derived (set by ``sync_from_invoice``), never typed.
		"""
		if self.due_date and self.status != "Paid":
			due_date = getdate(self.due_date)
			diff = (date.today() - due_date).days
			self.overdue_days = max(0, diff)
		else:
			self.overdue_days = 0

	def has_collected_this_period(self) -> bool:
		"""True when ANY money has been collected against the current period."""
		from netgainz.net_gainz.accounting import billing

		obligations = billing.open_obligations(self)
		if not obligations:
			return False
		total = sum(flt(o["amount"]) for o in obligations)
		outstanding = sum(flt(o["outstanding"]) for o in obligations)
		return total - outstanding > 0

	def sync_member_status(self):
		"""If all memberships are overdue, freeze the member.

		WP-10.6 (D3): a member who has PAID something this period is never frozen
		for missing a later installment. They are marked Overdue and surface in the
		owner's collections list, but keep access — freezing someone who has already
		handed the gym money (and may just be a few days late on installment 2) is
		the wrong default. A member who has paid nothing at all still freezes.
		"""
		if not self.member or self.status != "Overdue":
			return
		if self.has_collected_this_period():
			return
		active_subs = frappe.get_all(
			"Membership",
			filters={
				"member": self.member,
				# DS-4: a trial membership is a live one — a member training on a free
				# trial must not be frozen because an older membership lapsed.
				"status": ["in", ["Trial", "Paid", "Pending", "Partial"]],
				"name": ["!=", self.name],
			},
		)
		if not active_subs:
			member = frappe.get_doc("Member", self.member)
			if member.status == "Active":
				member.status = "Frozen"
				member.save(ignore_permissions=True)
