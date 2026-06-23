# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-1: rename the gym-specific DocTypes to vertical-neutral names.

Runs in [pre_model_sync] so the DB doctypes/tables are renamed BEFORE Frappe
syncs the (already-renamed on disk) JSON definitions. If it ran after sync,
Frappe would create fresh empty doctypes under the new names and the rename would
then collide with them.

Idempotent and safe on fresh sites: rename_doctype() no-ops when <old> is absent
(fresh install) or <new> already present (re-run).
"""

from netgainz.patches.rename_helpers import rename_doctype

# (old, new). rename_doc rewrites cross-references (Link options, link values,
# child parenttype, Singles) on each call, so order is largely independent; the
# child table is listed next to its parent for readability.
RENAMES = [
	("Coach", "Instructor"),
	("Coach Commission Line", "Instructor Commission Line"),
	("Coach Commission Run", "Instructor Commission Run"),
	("Subscription", "Membership"),
	("Gym Expense", "Expense"),
	("Gym Settings", "Business Settings"),
	("Class Session", "Session"),
	("Class Schedule", "Session Schedule"),
	("Class Booking", "Session Booking"),
]


def execute():
	for old, new in RENAMES:
		rename_doctype(old, new)
