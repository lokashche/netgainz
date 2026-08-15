# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 9 OP-5: install the starter assessment-metric library on existing sites.

`after_install` seeds a brand-new gym; a site that already exists gets the same
starter library from here, so the Height / Weight / BMI built-ins the assessment
form mirrors into exist before the first assessment is filed.

Idempotent: `seed_default_metrics` skips any metric already present, so a
tenant's own edits — and any starter metric they deliberately deleted — survive.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Assessment Metric"):
		return
	from netgainz.net_gainz.operations import assessments

	assessments.seed_default_metrics()
