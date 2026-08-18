# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-8: the NetGainz role & permission matrix.

Until now every NetGainz doctype granted exactly one role — **System Manager** —
so the only way to run a gym was to be a full Frappe administrator, and every
money-moving whitelisted method was callable by *any* logged-in user (``@frappe
.whitelist()`` gates on being logged in, nothing more). Both are closed here.

Two product roles, matching how a gym actually runs:

* **Gym Owner** — the customer. Everything the product exposes: members, plans,
  billing, expenses, Profit First, commissions, branches, settings. Money leaving
  the business (refunds, write-offs) and anything that changes the books' shape
  (account setup, sweeps, commission runs) is owner-only.
* **Gym Staff** — the front desk. Enrol members, take payments, run sessions and
  check-ins. Reads the plans and instructors they need; cannot refund, cannot
  write off, cannot see or touch Profit First, expenses or settings.

Two rules make this coherent with the standing "ERPNext is an engine, not a UI"
decision:

1. **NetGainz doctypes carry the roles; ERPNext doctypes do not.** Every ERPNext
   document (Sales Invoice, Payment Entry, Journal Entry, Subscription, Customer,
   Item) is created by NetGainz code with ``ignore_permissions=True`` and is never
   opened by a gym user, so granting write access to them would widen the blast
   radius for no product benefit. The Gym Owner gets **read + report** on the
   financial ones so future reporting screens (Stage 11) can query them, and
   nothing more.
2. **The whitelisted method is the real permission boundary.** ``require_role`` is
   called at the top of every entry point that moves money or reshapes the ledger.
   That is what stops a Gym Staff session — or any authenticated non-gym user —
   from POSTing a refund.

The matrix is applied idempotently by :func:`apply_permission_matrix` from
``after_install`` and from the ``v0_8`` patch, using **Custom DocPerm** rows for
the ERPNext side so no upstream JSON is edited.
"""

from __future__ import annotations

import frappe

GYM_OWNER = "Gym Owner"
GYM_STAFF = "Gym Staff"
SYSTEM_MANAGER = "System Manager"

NETGAINZ_ROLES = (GYM_OWNER, GYM_STAFF)

# Permission shorthands. `submit` implies the doctype is submittable.
FULL = {
	"read": 1,
	"write": 1,
	"create": 1,
	"delete": 1,
	"report": 1,
	"export": 1,
	"print": 1,
	"email": 1,
	"share": 1,
}
SUBMIT = {**FULL, "submit": 1, "cancel": 1, "amend": 1}
EDIT = {"read": 1, "write": 1, "create": 1, "report": 1, "print": 1}
READ = {"read": 1, "report": 1, "print": 1}
READ_ONLY = {"read": 1}

# ---------------------------------------------------------------------------
# NetGainz doctypes: role -> permissions.
# A doctype absent from a role's map grants that role nothing.
# ---------------------------------------------------------------------------
NETGAINZ_MATRIX: dict[str, dict[str, dict]] = {
	GYM_OWNER: {
		"Member": FULL,
		"Membership": FULL,
		"Membership Plan": FULL,
		"Offer": FULL,
		"Discount Log": READ,
		"Program": FULL,
		"Instructor": FULL,
		"Instructor Commission Run": SUBMIT,
		"Expense": SUBMIT,
		"Expense Category": FULL,
		"Session": FULL,
		"Session Schedule": FULL,
		"Session Booking": FULL,
		"Member Check-in": FULL,
		"Enquiry": FULL,
		"Membership Freeze": FULL,
		"Session Pack": FULL,
		"Pack Purchase": FULL,
		"Pack Session Use": READ,
		"Day Pass": FULL,
		"Assessment Metric": FULL,
		"Fitness Assessment": FULL,
		"Member Metric Target": FULL,
		# Loading the gym's own register is the owner's act, never the front desk's.
		"Data Load Step": FULL,
		"Business Branch": FULL,
		"Business Settings": {"read": 1, "write": 1, "print": 1, "email": 1, "share": 1},
		"Profit First Settings": {"read": 1, "write": 1, "print": 1, "email": 1, "share": 1},
		"PF Sweep": SUBMIT,
	},
	GYM_STAFF: {
		# The front desk enrols members and takes their money.
		"Member": EDIT,
		"Membership": EDIT,
		"Session": FULL,
		"Session Schedule": EDIT,
		"Session Booking": FULL,
		"Member Check-in": FULL,
		"Enquiry": FULL,
		"Membership Freeze": FULL,
		# The desk sells packs and day passes; the products are the owner's.
		"Pack Purchase": EDIT,
		"Pack Session Use": READ,
		"Day Pass": EDIT,
		# OP-5: the coach measures the member and agrees a target with them; the
		# metric library itself is the owner's to define.
		"Fitness Assessment": EDIT,
		"Member Metric Target": EDIT,
		# Reference data they read but never change.
		"Session Pack": READ,
		"Assessment Metric": READ,
		"Membership Plan": READ,
		# Campaigns and coupons are the owner's to define; the desk gives them out.
		"Offer": READ,
		"Program": READ,
		"Instructor": READ,
		"Business Branch": READ_ONLY,
		"Business Settings": READ_ONLY,
		# Deliberately absent: Expense, Expense Category, PF Sweep,
		# Profit First Settings, Instructor Commission Run.
	},
}

# ---------------------------------------------------------------------------
# ERPNext doctypes the engine creates on the tenant's behalf. **Read only** — the
# documents are written by NetGainz code with ``ignore_permissions=True`` and are
# never opened by a gym user, so write access would widen the blast radius for no
# product benefit.
#
# Read is not cosmetic, though: ERPNext's own helpers read as the SESSION user
# even when the document they build is inserted with permissions ignored.
# ``get_payment_entry`` -> ``get_bank_cash_account`` -> ``get_balance_on`` calls
# ``Account.check_permission("read")``, so without Account read a Gym Staff user
# simply cannot take a payment (caught by the WP-8 end-to-end trace, not by the
# unit tests, which run as Administrator).
# ---------------------------------------------------------------------------
ERPNEXT_READ = (
	"Sales Invoice",
	"Payment Entry",
	"Subscription",
	"Subscription Plan",
	"Customer",
	"Item",
	"Item Price",
	"Payment Terms Template",
	"Mode of Payment",
	"Cost Center",
	"Account",
	"Company",
)

# The ledger itself is the owner's business, not the front desk's.
ERPNEXT_READ_FOR_OWNER = ("Journal Entry", "GL Entry")

# Every grantable right on a (Custom) DocPerm in Frappe v15. `if_owner` is a
# scoping flag rather than a right, so it is deliberately not written here.
ALL_PERM_KEYS = (
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"import",
	"print",
	"email",
	"share",
	"select",
)


# --------------------------------------------------------------------------- #
# the runtime guard
# --------------------------------------------------------------------------- #
def require_role(*roles: str) -> None:
	"""Throw ``frappe.PermissionError`` unless the session user holds one of ``roles``.

	System Manager and Administrator always pass — a site admin supporting a tenant
	must not be locked out of the tenant's own actions.

	Deliberately NOT ``frappe.only_for``: that helper short-circuits whenever
	``frappe.flags.in_test`` is set, which would make every permission test in this
	app pass vacuously. Tests run as Administrator, so the existing suite is
	unaffected either way, and the guard can be exercised for real by switching
	user.
	"""
	user = frappe.session.user
	if user == "Administrator":
		return
	permitted = set(roles) | {SYSTEM_MANAGER}
	if permitted.isdisjoint(frappe.get_roles(user)):
		frappe.throw(
			"You do not have permission to do this. It is restricted to: " + ", ".join(sorted(roles)),
			frappe.PermissionError,
			title="Not Permitted",
		)


def has_role(*roles: str) -> bool:
	"""Non-raising probe for the same test — for hiding UI a user cannot use."""
	user = frappe.session.user
	if user == "Administrator":
		return True
	return not (set(roles) | {SYSTEM_MANAGER}).isdisjoint(frappe.get_roles(user))


@frappe.whitelist()
def get_my_capabilities() -> dict:
	"""Owner/BFF: what the signed-in user is allowed to do.

	The owner app uses this to hide actions rather than let a user click something
	that will only fail server-side.
	"""
	from netgainz.net_gainz.accounting import discounts

	policy = discounts.policy()
	is_owner = has_role(GYM_OWNER)
	return {
		"roles": [r for r in NETGAINZ_ROLES if has_role(r)],
		"can_refund": is_owner,
		"can_write_off": is_owner,
		"can_record_payment": has_role(GYM_OWNER, GYM_STAFF),
		"can_manage_finance": is_owner,
		# DS-5: the discount policy this user is working under, so the desk can ask for
		# the owner's PIN at the right moment instead of after a refused save.
		"can_discount_freely": is_owner,
		"max_discount_percent": policy["max_staff_percent"],
		"complimentary_requires_owner": policy["complimentary_requires_owner"],
		"can_see_discount_history": is_owner,
	}


# --------------------------------------------------------------------------- #
# applying the matrix
# --------------------------------------------------------------------------- #
def ensure_roles() -> list[str]:
	"""Create the two product roles if missing. Idempotent."""
	created = []
	for role in NETGAINZ_ROLES:
		if not frappe.db.exists("Role", role):
			doc = frappe.new_doc("Role")
			doc.role_name = role
			doc.desk_access = 1
			doc.insert(ignore_permissions=True)
			created.append(role)
	return created


def _write_docperm(doctype: str, role: str, perms: dict) -> bool:
	"""Grant ``role`` exactly ``perms`` on ``doctype``. Returns True if changed.

	Writes a **Custom DocPerm** — the supported way to permission a doctype you do
	not own — so upstream ERPNext/Frappe JSON is never edited and an app update
	cannot silently revert it.
	"""
	if not frappe.db.exists("DocType", doctype):
		return False
	values = {key: int(bool(perms.get(key))) for key in ALL_PERM_KEYS}
	values["permlevel"] = 0

	name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, "name")
	if name:
		existing = frappe.db.get_value("Custom DocPerm", name, list(values), as_dict=True)
		if all(int(existing.get(key) or 0) == values[key] for key in values):
			return False
		frappe.db.set_value("Custom DocPerm", name, values)
		return True

	doc = frappe.new_doc("Custom DocPerm")
	doc.parent = doctype
	doc.parenttype = "DocType"
	doc.parentfield = "permissions"
	doc.role = role
	doc.update(values)
	doc.insert(ignore_permissions=True)
	return True


def apply_permission_matrix() -> dict:
	"""Create the roles and apply every grant in the matrix. Idempotent.

	Safe to re-run: it rewrites only the rows whose flags actually differ, so a
	tenant that has hand-tuned an unrelated role keeps it.
	"""
	created_roles = ensure_roles()
	changed = 0

	# A Custom DocPerm row replaces the doctype's built-in permission rows
	# WHOLESALE — including the JSON's System Manager grant. So every doctype
	# this matrix touches must carry an explicit System Manager row as well, or
	# the site admin is locked out of the product the moment the custom rows
	# land. Found live on production 2026-08-18: the owner's System Manager
	# login 403'd on every screen, while the tests — which run as
	# Administrator, who bypasses permissions — stayed green.
	sm_grants: dict[str, dict] = {}

	def note_sm(doctype: str, perms: dict) -> None:
		merged = sm_grants.setdefault(doctype, {})
		for key, value in perms.items():
			if value:
				merged[key] = 1

	for role, doctypes in NETGAINZ_MATRIX.items():
		for doctype, perms in doctypes.items():
			changed += _write_docperm(doctype, role, perms)
			note_sm(doctype, perms)

	for doctype in ERPNEXT_READ:
		for role in NETGAINZ_ROLES:
			changed += _write_docperm(doctype, role, READ)
		note_sm(doctype, READ)
	for doctype in ERPNEXT_READ_FOR_OWNER:
		changed += _write_docperm(doctype, GYM_OWNER, READ)
		note_sm(doctype, READ)

	for doctype, merged in sm_grants.items():
		changed += _write_docperm(doctype, SYSTEM_MANAGER, merged)

	frappe.clear_cache()
	return {"roles_created": created_roles, "permissions_written": changed}


@frappe.whitelist()
def setup_roles(company=None) -> dict:
	"""Whitelisted entry point, mirroring the other ``setup_*`` owner actions."""
	require_role(GYM_OWNER)
	return apply_permission_matrix()
