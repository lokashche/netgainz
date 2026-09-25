# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Stage 12.7: the uptime check's health answer fails on a fresh background error
and on a stopped scheduler, and says only how many — never what."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz import health


class TestHealth(FrappeTestCase):
	def _check(self, inactive=False):
		with patch("frappe.utils.scheduler.is_scheduler_inactive", return_value=inactive):
			return health.check(30)

	def setUp(self):
		frappe.db.delete("Error Log")
		frappe.get_doc(
			{
				"doctype": "Scheduled Job Log",
				"scheduled_job_type": frappe.get_all("Scheduled Job Type", pluck="name", limit=1)[0],
				"status": "Complete",
			}
		).insert(ignore_permissions=True)

	def test_healthy(self):
		self.assertEqual(self._check(), {"ok": True, "problems": []})

	def test_background_error_fails_without_saying_what(self):
		frappe.log_error(title="HB secret member detail")
		result = self._check()
		self.assertFalse(result["ok"])
		self.assertIn("1 background error", result["problems"][0])
		self.assertNotIn("secret", str(result))

	def test_scheduler_off_fails(self):
		self.assertIn("switched off", self._check(inactive=True)["problems"][0])
