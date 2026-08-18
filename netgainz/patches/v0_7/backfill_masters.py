# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-2: backfill ERPNext masters for existing Members / Membership Plans.

Runs in [post_model_sync] (the new link columns -- Member.customer, Membership
Plan.item / .subscription_plan / .gst_hsn_code -- must be synced onto the tables
before we can write them). Mirrors the canonical backfill (v0_2/backfill_paid_date):
table-exists guards, WHERE-clause idempotency, no manual commit.

Step 1 seeds a default HSN/SAC on existing plans that lack one -- ``999723``
(physical well-being incl. health club & fitness centre services) -- so their
sellable Item can be created under india_compliance. This is a ONE-TIME seed for
the pilot's existing plans only; new plans set their own SAC via the per-plan
HSN/SAC field. Step 2/3 then provision the Customers / Items / Subscription Plans
through the shared (idempotent) provisioning routines.
"""

import frappe

# Fitness / health-club SAC; seeds pre-existing pilot plans only (see module docstring).
DEFAULT_PILOT_SAC = "999723"


def execute():
	# table_exists() prepends "tab" itself, so pass the bare doctype name.
	if not frappe.db.table_exists("Membership Plan"):
		return

	from netgainz.net_gainz.accounting import provisioning

	company = provisioning._company()
	if not company:
		return  # no Company configured yet; nothing to scope masters to

	# 1. Seed a SAC on existing plans missing one, so their Item can be created.
	if frappe.db.exists("GST HSN Code", DEFAULT_PILOT_SAC):
		for name in frappe.get_all(
			"Membership Plan", filters={"gst_hsn_code": ["in", [None, ""]]}, pluck="name"
		):
			frappe.db.set_value(
				"Membership Plan", name, "gst_hsn_code", DEFAULT_PILOT_SAC, update_modified=False
			)

	# 2. Provision a Customer for every Member that has none yet.
	for name in frappe.get_all("Member", filters={"customer": ["in", [None, ""]]}, pluck="name"):
		provisioning.provision_customer(name, company)

	# 3. Provision Item + Subscription Plan for every plan (idempotent per plan).
	for name in frappe.get_all("Membership Plan", pluck="name"):
		provisioning.provision_plan(name, company)
