# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 11.0: expenses post to the ledger by default.

The switch was off and had no owner-app screen, so the official books held no
expenses. New expenses post from now on; past ones wait for the owner's
"put them in the books" action on the Expenses page (they may already be in an
accountant's books elsewhere, so they are never posted silently).
"""

import frappe


def execute():
	frappe.db.set_single_value("Business Settings", "expense_post_to_ledger", 1)
