# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Branch dimension helpers (Stage 7 WP-3).

A tenant runs on one ERPNext Company; physical locations are Business Branches
mapped to Cost Centers. This module is the single seam every NetGainz financial
path uses to (a) resolve the cost center to post against and (b) stamp a default
branch so no financial doc is ever created without one (load-bearing rule: stamp
branch/cost-center from day one, never retrofit).

- ``branch_cost_center`` is what the JE builders / invoice creators call.
- ``ensure_main_branch`` idempotently seeds the default "Main" branch.
- ``stamp_default_branch`` is the doc_events ``before_insert`` handler for the
  financial doctypes; it self-heals (creates Main on first use).
"""

import frappe

from netgainz.net_gainz.profit_first import accounts as pf_accounts

# The default branch every tenant starts with (its HQ / only location). Company-
# wide postings (PF sweep, commission run) sit here until a tenant adds branches.
MAIN_BRANCH = "Main"


def _company(company=None):
	return company or pf_accounts.default_company()


def ensure_main_branch(company=None) -> str | None:
	"""Idempotently create the default "Main" Business Branch; return its name.

	Returns ``None`` when no Company is configured yet (nothing to scope to) — the
	caller then leaves ``branch`` empty and ``branch_cost_center`` falls back to
	the company default. Safe to call repeatedly.
	"""
	company = _company(company)
	if not company:
		return None
	if not frappe.db.exists("Business Branch", MAIN_BRANCH):
		doc = frappe.new_doc("Business Branch")
		doc.branch_name = MAIN_BRANCH
		doc.company = company
		doc.cost_center = frappe.get_cached_value("Company", company, "cost_center")
		doc.insert(ignore_permissions=True)
	return MAIN_BRANCH


def branch_cost_center(branch=None, company=None) -> str | None:
	"""Resolve the cost center a financial doc posts against.

	Prefers the branch's own ``cost_center`` *iff it belongs to the posting
	company*; otherwise falls back to the Company default cost center. The
	company check keeps a JE valid even if the branch is scoped to another
	company (a multi-company test fixture, or a misconfigured branch), and means
	an empty/absent branch posts exactly as before WP-3.
	"""
	company = _company(company)
	if branch and frappe.db.exists("Business Branch", branch):
		cc = frappe.db.get_value("Business Branch", branch, "cost_center")
		if cc and (not company or frappe.db.get_value("Cost Center", cc, "company") == company):
			return cc
	return frappe.get_cached_value("Company", company, "cost_center") if company else None


def resolve_default_branch(doc) -> str | None:
	"""The branch to stamp on ``doc`` when it has none: a Membership inherits its
	member's home branch when set; everything else uses (and seeds) Main."""
	if doc.doctype == "Membership" and doc.get("member"):
		member_branch = frappe.db.get_value("Member", doc.member, "branch")
		if member_branch:
			return member_branch
	return ensure_main_branch(doc.get("company"))


def stamp_default_branch(doc, method=None):
	"""``before_insert`` doc_event: ensure every financial doc carries a branch."""
	if frappe.flags.in_install:
		return
	if not doc.get("branch"):
		branch = resolve_default_branch(doc)
		if branch:
			doc.branch = branch


@frappe.whitelist()
def setup_branches(company=None) -> dict:
	"""Owner-triggered: ensure the default Main branch exists. Mirrors the other
	setup_* entry points (payment modes, PF accounts)."""
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	main = ensure_main_branch(company)
	return {"company": company, "main_branch": main}
