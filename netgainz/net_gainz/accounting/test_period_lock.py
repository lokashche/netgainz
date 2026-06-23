# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Tests for the period-lock guard (wraps ERPNext's native freeze/close guards)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from netgainz.net_gainz.accounting import period_lock


class TestPeriodLock(FrappeTestCase):
	def setUp(self):
		self._orig_frozen = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")

	def tearDown(self):
		frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", self._orig_frozen)

	def test_open_period_is_postable(self):
		frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", None)
		period_lock.assert_postable(nowdate())  # must not raise
		self.assertFalse(period_lock.is_period_locked(nowdate()))

	def test_frozen_period_blocks_posting(self):
		# Freeze through 5 days out, so a posting dated today is on/before the freeze.
		frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", add_days(nowdate(), 5))
		with self.assertRaises(frappe.ValidationError):
			period_lock.assert_postable(nowdate())
		self.assertTrue(period_lock.is_period_locked(nowdate()))

	def test_date_after_freeze_is_postable(self):
		# Freeze through 5 days ago, so a posting dated today is after the freeze.
		frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", add_days(nowdate(), -5))
		period_lock.assert_postable(nowdate())  # must not raise
