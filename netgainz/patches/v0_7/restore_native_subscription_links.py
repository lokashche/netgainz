# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-4 prerequisite: undo the WP-1 rename's collateral damage to ERPNext's
own ``subscription`` Link fields.

The WP-1 patch renamed the custom ``Subscription`` doctype to ``Membership`` with
``frappe.rename_doc(..., force=True)``, which rewrites EVERY Link field whose
options matched the old name — including ERPNext's native ``subscription`` Link on
Sales Invoice, Purchase Invoice and Process Subscription (those point at the
*native* Subscription, restored in WP-2). ``bench migrate`` then never repaired
them: model sync only re-syncs a doctype when its JSON hash changes, and these
ERPNext JSONs didn't change, so the corrupted ``options="Membership"`` persisted in
``tabDocField``.

Symptom: any native-Subscription-generated Sales Invoice fails to save with
``LinkValidationError: Could not find Subscription: ACC-SUB-...`` (the link is
validated against the wrong doctype). That blocks WP-4 billing entirely.

Fix: reset those fields' options back to ``Subscription`` (the on-disk ERPNext JSON
value) and clear the doctype cache. Idempotent — only touches rows still wrong.
"""

import frappe

# ERPNext-native doctypes whose `subscription` Link points at the native Subscription.
AFFECTED_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Process Subscription")


def execute():
	for doctype in AFFECTED_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		wrong = frappe.get_all(
			"DocField",
			filters={"parent": doctype, "fieldname": "subscription", "options": "Membership"},
			pluck="name",
		)
		for name in wrong:
			frappe.db.set_value("DocField", name, "options", "Subscription", update_modified=False)
		if wrong:
			frappe.clear_cache(doctype=doctype)
