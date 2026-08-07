# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt


def before_tests():
	"""Set up a complete INDIA ERPNext company before NetGainz tests run.

	NetGainz' Profit First sweeps and coach-commission runs post to ERPNext
	(Company, Account, Cost Center, Journal Entry), and the Stage 7 re-platform
	bills via India-Compliance-aware Sales Invoices. So the test company must be an
	**India** company (INR + India COA + GST fields from india_compliance), not
	ERPNext's default US "Wind Power LLC". `bench run-tests --app netgainz` only
	runs THIS app's before_tests hook, so we run the setup wizard ourselves with
	India parameters, then defer to ERPNext's standard test bootstrap (roles,
	Item Price cleanup, the "Transit" Warehouse Type, defaults) — which skips its
	own US company creation because our India company already exists.

	The fiscal year is kept on the CALENDAR year (not India's Apr-Mar) so the
	suite's existing posting dates all fall inside one open FY.
	"""
	import frappe
	from frappe.utils import now_datetime

	frappe.clear_cache()
	if not frappe.db.a_row_exists("Company"):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		current_year = now_datetime().year
		setup_complete(
			{
				"currency": "INR",
				"full_name": "Test User",
				"company_name": "Test Gym",
				"timezone": "Asia/Kolkata",
				"company_abbr": "TG",
				"industry": "Services",
				"country": "India",
				"fy_start_date": f"{current_year}-01-01",
				"fy_end_date": f"{current_year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@netgainz.app",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

	from erpnext.setup.utils import before_tests as erpnext_before_tests

	erpnext_before_tests()

	# Stage 7 WP-3: seed the default "Main" Business Branch so financial docs
	# created in tests can stamp a branch (idempotent; no-op without a company).
	from netgainz.net_gainz.accounting.branch import ensure_main_branch

	ensure_main_branch()
