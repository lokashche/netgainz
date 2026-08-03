# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-6: drop the dead `accounting_basis` field value from Profit First
Settings.

WP-6 removed the stale read-only `accounting_basis` field (superseded by the real
`Business Settings.accounting_method` Cash/Accrual toggle). Removing it from the
doctype JSON leaves an orphan row in `tabSingles`; delete it so the Single is
clean. Idempotent.
"""

import frappe


def execute():
	frappe.db.delete("Singles", {"doctype": "Profit First Settings", "field": "accounting_basis"})
