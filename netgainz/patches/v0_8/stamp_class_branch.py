# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 10.2: give existing timetables, classes and bookings a branch.

They had no branch field before 10.2. Every one of them ran at the gym's only
location, so they all belong to the default branch. Rule R19: every operational
record carries a branch, so later reports never meet a blank one.
"""

import frappe

from netgainz.net_gainz.accounting import branch


def execute():
	default = branch.ensure_default_branch()
	if not default:
		return
	for doctype in ("Session Schedule", "Session", "Session Booking"):
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET branch = %s WHERE IFNULL(branch, '') = ''",
			default,
		)
