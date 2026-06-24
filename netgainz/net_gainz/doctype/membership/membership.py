# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

# Custom imports
from datetime import date, timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class Membership(Document):
	def before_save(self):
		if self.subscription:
			# Cut-over membership: status / balance_due / next_renewal derive from
			# the Sales Invoice outstanding_amount (R4 single source of truth), not
			# the legacy fee_collected math. Payments post as Payment Entries
			# (accounting.billing.record_payment), never by editing fee_collected.
			from netgainz.net_gainz.accounting import billing

			billing.sync_from_invoice(self)
			return
		self.calculate_balance_due()
		self.calculate_overdue_days()
		self.auto_update_status()
		self.set_paid_date_on_payment()
		self.calculate_next_renewal()

	def set_paid_date_on_payment(self):
		"""Stamp paid_date the first time money is recorded.

		Cash-basis reporting (and the Profit First Instant Assessment) scopes
		income by paid_date. SQL BETWEEN excludes NULLs, so a collected payment
		with no paid_date is silently dropped from cash totals. Default it to
		today when fees are first collected, without overwriting a date the
		owner set explicitly.
		"""
		if (self.fee_collected or 0) > 0 and not self.paid_date:
			self.paid_date = date.today()

	def after_save(self):
		self.sync_member_status()

	def calculate_balance_due(self):
		# Ensure we treat None as 0 so the math doesn't break
		tariff = self.tariff or 0
		collected = self.fee_collected or 0
		if tariff and collected:
			self.balance_due = tariff - collected
		elif tariff:
			self.balance_due = tariff
		else:
			self.balance_due = 0

	def calculate_overdue_days(self):
		if self.due_date and self.status != "Paid":
			due_date = getdate(self.due_date)
			diff = (date.today() - due_date).days
			self.overdue_days = max(0, diff)
		else:
			self.overdue_days = 0

	def auto_update_status(self):
		# 1. PREPARATION: Make sure we have numbers to work with
		tariff = self.tariff or 0
		collected = self.fee_collected or 0

		# 2. THE MONEY CHECK: Decide status based only on payment
		if tariff > 0:
			if collected >= tariff:
				self.status = "Paid"
			elif collected > 0:
				self.status = "Partial"
			else:
				self.status = "Pending"

		# 3. THE DEADLINE CHECK: If it's late, "Overdue" wins
		if self.due_date and date.today() > getdate(self.due_date):
			# If the date has passed and the status is NOT "Paid"...
			if self.status != "Paid":
				# This marks it "Overdue" even if they paid a little bit (Partial)
				self.status = "Overdue"

	def calculate_next_renewal(self):
		if self.membership_plan and self.paid_date:
			plan = frappe.get_doc("Membership Plan", self.membership_plan)
			if plan.duration_in_days:
				paid_date = getdate(self.paid_date)
				self.next_renewal = paid_date + timedelta(days=plan.duration_in_days)

	def sync_member_status(self):
		"""If all subscriptions are overdue, freeze the member"""
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
