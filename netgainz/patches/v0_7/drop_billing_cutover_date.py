# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-11: drop the dead `billing_cutover_date` value from Business Settings.

WP-11 removed the billing cut-over entirely (ERPNext billing is on for every
membership from day one — no tenant ever had production data to migrate). Removing
the field from the doctype JSON leaves an orphan row in `tabSingles`; delete it so
the Single is clean. Mirrors `v0_7/drop_accounting_basis`. Idempotent.

Note this patch is a no-op on a freshly installed site: `frappe.installer.install_app`
defaults to `set_as_patched=True`, so every patch is marked complete and never runs.
It exists for the dev/staging sites that already carry the field.
"""

import frappe


def execute():
	frappe.db.delete("Singles", {"doctype": "Business Settings", "field": "billing_cutover_date"})
