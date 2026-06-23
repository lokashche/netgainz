# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-1 follow-up (post_model_sync):

1. Preserve any custom session terminology: the old `class_term_*` Single values
   move to the renamed `session_term_*` fields. The Single is already renamed to
   Business Settings by the pre_model_sync patch, and the new session_term fields
   are synced by the time this runs.
2. Drop the removed `academy` column from Member.

Idempotent: guarded by table/column existence; the Singles rename clears any
freshly-defaulted target row first so it can't duplicate.
"""

import frappe


def execute():
	if frappe.db.table_exists("tabSingles"):
		for old, new in (
			("class_term_singular", "session_term_singular"),
			("class_term_plural", "session_term_plural"),
		):
			frappe.db.sql(
				"DELETE FROM `tabSingles` WHERE doctype=%s AND field=%s",
				("Business Settings", new),
			)
			frappe.db.sql(
				"UPDATE `tabSingles` SET field=%s WHERE doctype=%s AND field=%s",
				(new, "Business Settings", old),
			)

	if frappe.db.table_exists("tabMember"):
		# DROP ... IF EXISTS is itself idempotent; don't gate on get_table_columns,
		# whose Redis 'table_columns' cache can be stale mid-migrate and wrongly
		# skip the drop.
		frappe.db.sql_ddl("ALTER TABLE `tabMember` DROP COLUMN IF EXISTS `academy`")
		frappe.cache.hdel("table_columns", "tabMember")
