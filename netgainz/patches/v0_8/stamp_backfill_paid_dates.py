# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Backfilled memberships carried no paid_date, so cash-basis income read Rs.0.

The dashboard's income tile counts a membership in the month its money was
RECEIVED (``paid_date``) when the gym keeps cash-basis books. The July history
rows loaded through the owner app carried fees but no received-date, so July's
income showed as nothing at all. The owner-confirmed backfill rule has always
been **payment date = due date** (monthly P&L right, daily cash reconciliation
knowingly not). Stamp exactly that, exactly once: history rows only, rows that
actually collected money, rows not already stamped. Idempotent.
"""

import frappe


def execute():
	for row in frappe.get_all(
		"Membership",
		filters={"is_backfill": 1, "paid_date": ("is", "not set"), "fee_collected": (">", 0)},
		fields=["name", "due_date"],
	):
		frappe.db.set_value("Membership", row.name, "paid_date", row.due_date, update_modified=False)
