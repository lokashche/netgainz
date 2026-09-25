# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Branch dimension helpers (Stage 7 WP-3).

A tenant runs on one ERPNext Company; physical locations are Business Branches
mapped to Cost Centers. This module is the single seam every NetGainz financial
path uses to (a) resolve the cost center to post against and (b) stamp a default
branch so no financial doc is ever created without one (load-bearing rule: stamp
branch/cost-center from day one, never retrofit).

- ``branch_cost_center`` is what the JE builders / invoice creators call.
- ``ensure_default_branch`` finds the default branch by its ``is_default`` flag
  (never by name — the owner renames "Main" to the real location), seeding "Main"
  on first use.
- ``stamp_default_branch`` is the doc_events ``before_insert`` handler for the
  financial doctypes; it self-heals (creates the default branch on first use).
- ``get_branches`` / ``create_branch`` / ``update_branch`` back the owner-app
  Branches screen (Stage 10.1).
"""

import frappe

from netgainz.net_gainz.profit_first import accounts as pf_accounts

# The name the first branch is created with. Only a starting name: the default is
# found by the ``is_default`` flag, so renaming it to the real location is safe.
MAIN_BRANCH = "Main"


def _company(company=None):
	return company or pf_accounts.default_company()


def ensure_default_branch(company=None) -> str | None:
	"""The tenant's default branch; seeds "Main" on first use. Idempotent.

	Returns ``None`` when no Company is configured yet (nothing to scope to) — the
	caller then leaves ``branch`` empty and ``branch_cost_center`` falls back to
	the company default. Safe to call repeatedly.
	"""
	company = _company(company)
	if not company:
		return None
	default = frappe.db.get_value("Business Branch", {"is_default": 1}, "name")
	if default:
		return default
	# A site from before the flag existed: its "Main" is the default.
	if frappe.db.exists("Business Branch", MAIN_BRANCH):
		frappe.db.set_value("Business Branch", MAIN_BRANCH, "is_default", 1, update_modified=False)
		return MAIN_BRANCH
	doc = frappe.new_doc("Business Branch")
	doc.branch_name = MAIN_BRANCH
	doc.company = company
	doc.is_default = 1
	# The first branch IS the company: it keeps the company's own cost center, so
	# everything posted before branches existed stays in its figures.
	doc.cost_center = frappe.get_cached_value("Company", company, "cost_center")
	doc.insert(ignore_permissions=True)
	return doc.name


# Older call sites and patches use the pre-10.1 name.
ensure_main_branch = ensure_default_branch


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
	"""The branch to stamp on ``doc`` when it has none: any member-bearing doc
	(Membership, Member Check-in, later OP doctypes) inherits its member's home
	branch when set; everything else uses (and seeds) the default branch."""
	if doc.get("member"):
		member_branch = frappe.db.get_value("Member", doc.member, "branch")
		if member_branch:
			return member_branch
	return ensure_default_branch(doc.get("company"))


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
	"""Owner-triggered: ensure the default branch exists. Mirrors the other
	setup_* entry points (payment modes, PF accounts)."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	main = ensure_default_branch(company)
	return {"company": company, "main_branch": main}


# --------------------------------------------------------------------------- #
# Stage 10.1: the owner-app Branches screen
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_branches(include_disabled=1) -> list[dict]:
	"""Every branch with its member count, default first. Read through
	``frappe.get_list`` so a user limited to one branch sees only that one."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	ensure_default_branch()
	filters = {} if int(include_disabled or 0) else {"disabled": 0}
	rows = frappe.get_list(
		"Business Branch",
		filters=filters,
		fields=["name", "branch_name", "is_default", "disabled", "description"],
		order_by="is_default desc, branch_name asc",
	)
	counts = dict(
		frappe.db.sql(
			"SELECT branch, COUNT(*) FROM `tabMember` WHERE IFNULL(branch, '') != '' GROUP BY branch"
		)
	)
	for r in rows:
		r["members"] = counts.get(r.name, 0)
	return rows


@frappe.whitelist()
def create_branch(branch_name, description=None) -> dict:
	"""Owner: open a new branch. Its cost center is created silently."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	branch_name = (branch_name or "").strip()
	if not branch_name:
		frappe.throw("Give the branch a name.")
	if frappe.db.exists("Business Branch", branch_name):
		frappe.throw(f"There is already a branch called {branch_name}.")
	ensure_default_branch()
	doc = frappe.get_doc(
		{"doctype": "Business Branch", "branch_name": branch_name, "description": description}
	).insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def update_branch(name, new_name=None, description=None, disabled=None, make_default=None) -> dict:
	"""Owner: rename, describe, switch off/on, or make the default branch.

	A rename carries every record that points at the branch (members, memberships,
	expenses, check-ins …) with it — Frappe's own rename, not a copy."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	if not frappe.db.exists("Business Branch", name):
		frappe.throw(f"Branch {name} not found.")

	new_name = (new_name or "").strip()
	if new_name and new_name != name:
		if frappe.db.exists("Business Branch", new_name):
			frappe.throw(f"There is already a branch called {new_name}.")
		name = frappe.rename_doc("Business Branch", name, new_name, force=True, rebuild_search=False)

	doc = frappe.get_doc("Business Branch", name)
	if description is not None:
		doc.description = description
	if disabled is not None:
		doc.disabled = int(disabled)
	if make_default is not None and int(make_default):
		doc.is_default = 1
		doc.disabled = 0
	doc.save(ignore_permissions=True)
	return {"name": doc.name}
