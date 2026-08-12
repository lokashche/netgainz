# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""A spent free trial must not steer billing (Stage 9 OP-3; ADR-0008 §4).

Upstream ``Subscription.get_current_invoice_start`` gives ``trial_period_end + 1``
priority over an explicitly requested date — *forever*. Traced live 2026-08-12:
after an ex-trial subscription bills its first paid period, the scheduler's
period advance snaps straight back to that same first period
(``update_subscription_period(end + 1)`` requested Aug 10, got Jul 11), the
freshly billed invoice then sits inside the "current" window, and
``is_current_invoice_generated`` reports the period as already billed — so the
member is **never invoiced again**. Every DS-4 trial membership would silently
stop renewing after one paid cycle. The same priority is why
``restart_subscription`` lands ex-trial subscriptions in the past.

The trial dates have exactly two billing jobs: suppress invoices *during* the
trial, and anchor the first paid period at ``trial_end + 1``. Both need the
trial to still be running (or the requested date to fall inside it). Once the
trial has passed, a requested date must win — which is all this override does.
Registered via ``override_doctype_class`` in hooks.py, the supported seam for
exactly this kind of upstream correction.
"""

from erpnext.accounts.doctype.subscription.subscription import Subscription
from frappe.utils import getdate, nowdate


class NetGainzSubscription(Subscription):
	def get_current_invoice_start(self, date=None):
		if self.trial_period_end and self.period_has_passed(self.trial_period_end, date or nowdate()):
			# Spent trial: mirror upstream's non-trial arms (explicit date, else
			# today) instead of letting the dead trial re-anchor the period.
			return getdate(date) if date else getdate(nowdate())
		return super().get_current_invoice_start(date)
