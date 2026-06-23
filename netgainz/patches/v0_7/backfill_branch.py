# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-3: seed the default "Main" branch and stamp it on existing financial
docs so none predates the branch dimension (load-bearing rule: every financial doc
carries a branch from day one).

post_model_sync (the new ``branch`` columns must be synced first). Idempotent:
only rows whose branch is empty are touched. Posted (docstatus=1) PF Sweeps /
Commission Runs are stamped via ``db_set`` — this only labels the dimension; their
already-posted Journal Entries (whose cost center was the Company default, i.e.
Main's cost center) are untouched.
"""

import frappe

# Financial doctypes that gained a `branch` link in WP-3 (Member is the home-branch
# source that flows to memberships).
BRANCHED_DOCTYPES = (
	"Member",
	"Membership",
	"Expense",
	"PF Sweep",
	"Instructor Commission Run",
)


def execute():
	from netgainz.net_gainz.accounting import branch

	company = branch._company()
	if not company:
		return  # no Company configured yet; the branch self-seeds on first use

	main = branch.ensure_main_branch(company)
	if not main:
		return

	for doctype in BRANCHED_DOCTYPES:
		if not frappe.db.table_exists(doctype):
			continue
		if "branch" not in frappe.db.get_table_columns(doctype):
			continue  # column not synced yet (defensive)
		for name in frappe.get_all(doctype, filters={"branch": ["in", [None, ""]]}, pluck="name"):
			frappe.db.set_value(doctype, name, "branch", main, update_modified=False)
