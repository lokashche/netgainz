# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

# Custom imports
from datetime import date

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


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

	def before_save(self):
		from netgainz.net_gainz.accounting import billing

		# Derives status / balance_due / due_date / next_renewal from the current
		# Sales Invoice. A no-op while billing has not been provisioned yet
		# (provisioning is best-effort and must never block enrolment).
		billing.sync_from_invoice(self)
		self.calculate_overdue_days()

	def after_save(self):
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

	def sync_member_status(self):
		"""If all memberships are overdue, freeze the member"""
		if self.member and self.status == "Overdue":
			active_subs = frappe.get_all(
				"Membership",
				filters={
					"member": self.member,
					"status": ["in", ["Paid", "Pending", "Partial"]],
					"name": ["!=", self.name],
				},
			)
			if not active_subs:
				member = frappe.get_doc("Member", self.member)
				if member.status == "Active":
					member.status = "Frozen"
					member.save(ignore_permissions=True)
