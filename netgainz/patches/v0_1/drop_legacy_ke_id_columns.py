import frappe


def execute():
	# Uses IF EXISTS rather than frappe.db.has_column because the latter reads
	# from a Redis-cached column list that can be stale mid-migrate.
	for doctype in ("Member", "Subscription"):
		table = f"tab{doctype}"
		if frappe.db.table_exists(table):
			frappe.db.sql_ddl(f"ALTER TABLE `{table}` DROP COLUMN IF EXISTS `ke_id`")
			frappe.cache.hdel("table_columns", table)
