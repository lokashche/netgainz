# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-8: create the Gym Owner / Gym Staff roles and apply the matrix.

post_model_sync — the NetGainz doctypes carry their own role rows in JSON and are
synced by migrate; this patch creates the two Role records those rows point at
(a DocPerm on a missing Role is inert) and writes the Custom DocPerm rows that
give the owner read access to the ERPNext documents the engine creates on their
behalf.

Idempotent: `apply_permission_matrix` only rewrites rows whose flags differ, so
re-running is a no-op and a tenant's own role tweaks elsewhere are untouched.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Custom DocPerm"):
		return
	from netgainz.net_gainz import permissions

	permissions.apply_permission_matrix()
