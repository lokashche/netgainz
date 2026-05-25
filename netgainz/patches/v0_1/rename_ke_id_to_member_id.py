import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	for doctype in ("Member", "Subscription"):
		table = f"tab{doctype}"
		if not frappe.db.table_exists(table):
			continue
		if frappe.db.has_column(doctype, "ke_id") and not frappe.db.has_column(doctype, "member_id"):
			rename_field(doctype, "ke_id", "member_id")
