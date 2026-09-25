# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 12.1 — set up a brand-new gym from the owner-app, never from Desk.

On a fresh site the only Desk-only step left was ERPNext's setup screen: it makes the
Company, the Fiscal Year and the chart of accounts. ``setup_business`` runs that same
routine (Frappe's setup stages — every installed app's steps, India Compliance's tax
templates included), then the NetGainz pieces that would otherwise wait for first use
(the "Main" branch, payment modes). It runs as a background job because the India
chart + GST fixtures can outlast a Vercel request; the page polls ``get_setup_status``.

Everything after that already has a screen (branches, plans, Profit First, staff,
data load), so the rest of onboarding is a checklist linking to them.
"""

import frappe
from frappe.utils import add_days, add_years, cint, getdate, today
from frappe.utils.background_jobs import is_job_enqueued

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import branch, payment_modes
from netgainz.net_gainz.profit_first import accounts as pf_accounts

CONSTITUTIONS = ("Proprietorship", "Partnership", "LLP", "Private Limited")
JOB_ID = "netgainz-setup-business"


def financial_year(start_month: int, on=None) -> tuple[str, str]:
	"""The financial year that contains ``on`` (default today), starting on the 1st of
	``start_month``. India's is April (4)."""
	on = getdate(on or today())
	start = on.replace(month=start_month, day=1)
	if start > on:
		start = start.replace(year=start.year - 1)
	return str(start), str(add_days(add_years(start, 1), -1))


def company_abbr(name: str) -> str:
	"""ERPNext suffixes every account with this ("Cash - IFF"). Initials, max 5."""
	words = [w for w in name.split() if w[:1].isalnum()]
	abbr = "".join(w[0] for w in words).upper()[:5]
	return abbr if len(abbr) > 1 else name.strip()[:3].upper()


def _setup_failure() -> str | None:
	"""Frappe logs a failed setup as an Error Log titled "Setup failed: ..."."""
	return frappe.db.get_value(
		"Error Log", {"method": ["like", "Setup failed%"]}, "method", order_by="creation desc"
	)


@frappe.whitelist()
def get_setup_status() -> dict:
	"""Owner: how far this gym is through setting up. ``company`` is empty until the
	business step is done; ``steps`` is the checklist the owner-app shows."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	company = pf_accounts.default_company()
	running = not company and is_job_enqueued(JOB_ID)
	owner_logins = frappe.get_all(
		"Has Role",
		filters={"role": permissions.GYM_OWNER, "parenttype": "User", "parent": ["!=", "Administrator"]},
		limit=1,
	)
	steps = [
		("business", "Your business", bool(company), "/setup"),
		("owner_login", "Your own login", bool(owner_logins), "/staff"),
		("branches", "Branches", frappe.db.exists("Business Branch", {}), "/branches"),
		("plans", "Membership plans", frappe.db.exists("Membership Plan", {}), "/plans"),
		(
			"profit_first",
			"Profit First targets",
			cint(frappe.db.get_single_value("Profit First Settings", "pf_enabled")),
			"/profit-first",
		),
		("members", "Your members", frappe.db.exists("Member", {}), "/data-load"),
	]
	return {
		"company": company,
		"running": running,
		"error": None if (company or running) else _setup_failure(),
		"constitution": frappe.db.get_single_value("Business Settings", "constitution"),
		"gst_registered": cint(frappe.db.get_single_value("Business Settings", "gst_registered")),
		"steps": [
			{"key": k, "label": label, "done": bool(done), "href": href} for k, label, done, href in steps
		],
	}


@frappe.whitelist(methods=["POST"])
def setup_business(
	company_name,
	fy_start_month=4,
	constitution="Proprietorship",
	gst_registered=0,
	gstin=None,
	bank_account=None,
) -> dict:
	"""Owner: create the business — Company, Fiscal Year, chart of accounts — the way
	ERPNext's setup screen would, then the NetGainz defaults. Once only."""
	permissions.require_role(permissions.GYM_OWNER)
	if pf_accounts.default_company():
		frappe.throw("This business is already set up.")
	if is_job_enqueued(JOB_ID):
		return {"status": "running"}

	company_name = (company_name or "").strip()
	if not company_name:
		frappe.throw("Give the business a name.")
	if constitution not in CONSTITUTIONS:
		frappe.throw("Pick a business type.")
	month = cint(fy_start_month)
	if not 1 <= month <= 12:
		frappe.throw("Pick the month your financial year starts.")
	gst_registered = cint(gst_registered)
	gstin = (gstin or "").strip().upper() or None
	if gst_registered:
		if not gstin:
			frappe.throw("Enter your GSTIN, or untick GST registered.")
		from india_compliance.gst_india.utils import validate_gstin

		validate_gstin(gstin)

	settings = frappe.get_single("Business Settings")
	settings.constitution = constitution
	settings.gst_registered = gst_registered
	settings.save(ignore_permissions=True)

	fy_start, fy_end = financial_year(month)
	args = {
		# ponytail: India-only product today; country/currency/timezone become inputs
		# when the first non-Indian gym signs up.
		"country": "India",
		"currency": "INR",
		"timezone": "Asia/Kolkata",
		"language": "English",
		"company_name": company_name,
		"company_abbr": company_abbr(company_name),
		"chart_of_accounts": "Standard",
		"fy_start_date": fy_start,
		"fy_end_date": fy_end,
		"bank_account": (bank_account or "").strip() or "Bank Account",
		"company_gstin": gstin if gst_registered else None,
		# Never an "email": ERPNext would log the session in as that user, swapping
		# the owner-app's own session mid-request. The owner's login is its own step.
	}
	frappe.enqueue(_run_setup, queue="long", timeout=1500, job_id=JOB_ID, deduplicate=True, args=args)
	return {"status": "running"}


def _run_setup(args: dict) -> None:
	from frappe.desk.page.setup_wizard.setup_wizard import get_setup_stages, process_setup_stages

	args = frappe._dict(args)
	# Raises (and rolls back) on failure; Frappe logs it as "Setup failed: ...".
	process_setup_stages(get_setup_stages(args), args)
	company = pf_accounts.default_company()
	branch.ensure_default_branch(company)
	payment_modes.setup_payment_modes(company)
	if not frappe.db.get_single_value("Profit First Settings", "company"):
		frappe.db.set_single_value("Profit First Settings", "company", company)
