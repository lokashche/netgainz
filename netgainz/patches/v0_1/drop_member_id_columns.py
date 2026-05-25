import frappe


def execute():
	"""Drop now-orphaned member_id columns.

	Member uses controller-generated autoname (name IS the member ID).
	Subscription references Member via the `member` Link, whose value
	is the same identifier — no separate fetched copy needed.
	"""
	# Uses IF EXISTS rather than frappe.db.has_column because the latter reads
	# from a Redis-cached column list that can be stale mid-migrate.
	for doctype in ("Member", "Subscription"):
		table = f"tab{doctype}"
		if frappe.db.table_exists(table):
			frappe.db.sql_ddl(f"ALTER TABLE `{table}` DROP COLUMN IF EXISTS `member_id`")
			frappe.cache.hdel("table_columns", table)
