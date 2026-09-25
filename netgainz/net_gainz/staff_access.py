# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 10.4 — staff logins and which branches they may see, from the owner-app.

Before this, a staff login could only be created in Frappe Desk — a screen no gym
owner opens. The owner now adds a login, names its role (Gym Owner or Gym Staff),
and for front-desk staff picks the branch(es) it may see. That choice is stored as
Frappe's own User Permissions:

* **Business Branch** — limits every record that carries a branch (members,
  memberships, check-ins, enquiries …) and feeds ``branch.scope`` for the custom
  reads;
* **Cost Center** of each chosen branch — limits Sales Invoices and Payment
  Entries, which carry a cost center rather than a branch (trace finding F6).

No branch chosen means the login sees every branch. Owners are never limited —
a gym owner who could lock themselves out of a branch would need Desk to get
back in.
"""

import frappe
from frappe.utils import validate_email_address

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import branch as branch_mod

STAFF_ROLES = (permissions.GYM_OWNER, permissions.GYM_STAFF)
# The two kinds of restriction a branch choice writes; nothing else is touched.
_RESTRICTS = ("Business Branch", "Cost Center")


def _gym_logins() -> dict[str, set[str]]:
	"""user -> the NetGainz roles it holds, for every login holding one."""
	logins: dict[str, set[str]] = {}
	for row in frappe.get_all(
		"Has Role",
		filters={"role": ["in", list(STAFF_ROLES)], "parenttype": "User"},
		fields=["parent", "role"],
	):
		if row.parent in ("Administrator", "Guest"):
			continue
		logins.setdefault(row.parent, set()).add(row.role)
	return logins


def _branches_of(user) -> list[str]:
	return frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Business Branch"},
		pluck="for_value",
		order_by="is_default desc, for_value asc",
	)


def _manageable(user) -> set[str]:
	"""The login's NetGainz roles; refuses logins the owner may not manage."""
	if user == frappe.session.user:
		frappe.throw("You cannot change your own login here.", frappe.PermissionError)
	roles = _gym_logins().get(user)
	if not roles:
		frappe.throw("That is not a gym staff login.", frappe.PermissionError)
	if "System Manager" in frappe.get_roles(user):
		frappe.throw("That login belongs to the system administrator.", frappe.PermissionError)
	return roles


def _set_branches(user, branches) -> list[str]:
	"""Replace the login's branch limits. Empty = every branch."""
	branches = [b for b in dict.fromkeys(branches or []) if b]
	for b in branches:
		if not frappe.db.exists("Business Branch", {"name": b, "disabled": 0}):
			frappe.throw(f"There is no open branch called {b}.")
	frappe.db.delete("User Permission", {"user": user, "allow": ["in", list(_RESTRICTS)]})
	cost_centers = []
	for i, b in enumerate(branches):
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": "Business Branch",
				"for_value": b,
				"is_default": 1 if i == 0 else 0,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)
		cc = branch_mod.branch_cost_center(b)
		if cc and cc not in cost_centers:
			cost_centers.append(cc)
	for cc in cost_centers:
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": "Cost Center",
				"for_value": cc,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)
	frappe.clear_cache(user=user)
	return branches


def _parse_list(value) -> list[str]:
	if not value:
		return []
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return [str(v) for v in value]


@frappe.whitelist()
def get_staff() -> list[dict]:
	"""Owner: every gym login, its role, and the branches it is limited to."""
	permissions.require_role(permissions.GYM_OWNER)
	logins = _gym_logins()
	if not logins:
		return []
	users = frappe.get_all(
		"User",
		filters={"name": ["in", list(logins)]},
		fields=["name", "full_name", "enabled", "last_login"],
		order_by="full_name asc",
	)
	out = []
	for u in users:
		roles = logins[u.name]
		out.append(
			{
				"user": u.name,
				"full_name": u.full_name or u.name,
				"enabled": u.enabled,
				"role": permissions.GYM_OWNER if permissions.GYM_OWNER in roles else permissions.GYM_STAFF,
				"branches": _branches_of(u.name),
				"last_login": str(u.last_login) if u.last_login else None,
				"is_me": u.name == frappe.session.user,
			}
		)
	return out


@frappe.whitelist()
def create_staff(email, full_name, password, role=permissions.GYM_STAFF, branches=None) -> dict:
	"""Owner: add a login. Front-desk staff can be limited to branches at once."""
	permissions.require_role(permissions.GYM_OWNER)
	email = (email or "").strip().lower()
	full_name = (full_name or "").strip()
	if not full_name:
		frappe.throw("Give the login a name.")
	if not validate_email_address(email):
		frappe.throw("Give a valid email address — it is what they sign in with.")
	if frappe.db.exists("User", email):
		frappe.throw(f"There is already a login for {email}.")
	if role not in STAFF_ROLES:
		frappe.throw("A login is either Gym Owner or Gym Staff.")
	if not password:
		frappe.throw("Set a first password for them to sign in with.")

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": full_name,
			"send_welcome_email": 0,
			"user_type": "System User",
			"new_password": password,
			"roles": [{"role": role}],
		}
	).insert(ignore_permissions=True)

	limited = []
	if role == permissions.GYM_STAFF:
		limited = _set_branches(user.name, _parse_list(branches))
	return {"user": user.name, "branches": limited}


@frappe.whitelist()
def set_staff_branches(user, branches=None) -> dict:
	"""Owner: limit a front-desk login to some branches (none = every branch)."""
	permissions.require_role(permissions.GYM_OWNER)
	roles = _manageable(user)
	if permissions.GYM_OWNER in roles:
		frappe.throw("An owner login always sees every branch.")
	return {"user": user, "branches": _set_branches(user, _parse_list(branches))}


@frappe.whitelist()
def set_staff_enabled(user, enabled) -> dict:
	"""Owner: switch a login off (it can no longer sign in) or back on."""
	permissions.require_role(permissions.GYM_OWNER)
	_manageable(user)
	enabled = int(enabled)
	frappe.db.set_value("User", user, "enabled", enabled)
	if not enabled:
		# Sign them out everywhere now, not at their session's natural expiry.
		from frappe.sessions import clear_sessions

		clear_sessions(user=user, keep_current=False, force=True)
	return {"user": user, "enabled": enabled}
