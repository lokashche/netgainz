import frappe
from frappe.utils import getdate


def execute():
	"""Backfill paid_date for historical subscriptions that recorded a payment
	but never received a paid_date.

	The Subscription controller previously never set paid_date. Cash-basis Real
	Revenue scopes income by paid_date and SQL BETWEEN excludes NULLs, so these
	collected payments were silently invisible to the Profit First Instant
	Assessment. Use due_date as the best proxy for when the money was due, then
	fall back to the row's creation date. set_value bypasses the controller so we
	don't recompute status/balances on historical rows.
	"""
	if not frappe.db.table_exists("tabSubscription"):
		return

	rows = frappe.db.sql(
		"""
		SELECT name, due_date, creation
		FROM `tabSubscription`
		WHERE fee_collected IS NOT NULL
		  AND fee_collected > 0
		  AND paid_date IS NULL
		""",
		as_dict=True,
	)

	for row in rows:
		fallback = row.due_date or (getdate(row.creation) if row.creation else None)
		if fallback:
			frappe.db.set_value("Subscription", row.name, "paid_date", fallback, update_modified=False)
