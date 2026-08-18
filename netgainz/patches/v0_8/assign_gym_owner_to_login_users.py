# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""WP-8 follow-through: the walls went up with the humans still outside.

``apply_permission_matrix`` created Gym Owner / Gym Staff and pointed every
NetGainz doctype at them — but nothing ever granted those roles to the logins
that already ran the gym. A login that is not a System Manager now signs in
successfully and then gets 403 on every read, which the owner app can only
answer by bouncing straight back to the sign-in screen. Found live on
production, 2026-08-18.

Every enabled human login that holds none of the qualifying roles becomes a
Gym Owner. Skipped: Administrator and Guest; test-convention addresses
(@example.com / @test.com), because a leftover test login must not be handed
the owner's keys; and any address that belongs to a gym Member, because a
member must never hold them either. Future tenants get roles explicitly from
provisioning, which makes this a no-op there. Idempotent.
"""

import frappe

TEST_DOMAINS = ("@example.com", "@test.com")


def execute():
	from netgainz.net_gainz import permissions

	permissions.ensure_roles()

	qualifying = {"System Manager", permissions.GYM_OWNER, permissions.GYM_STAFF}
	member_emails = {e.lower() for e in frappe.get_all("Member", pluck="email") if e}

	for name in frappe.get_all("User", filters={"enabled": 1}, pluck="name"):
		lowered = name.lower()
		if name in ("Administrator", "Guest"):
			continue
		if lowered.endswith(TEST_DOMAINS):
			continue
		if lowered in member_emails:
			continue
		if qualifying & set(frappe.get_roles(name)):
			continue
		user = frappe.get_doc("User", name)
		user.append("roles", {"role": permissions.GYM_OWNER})
		# A login stripped of desk roles gets auto-demoted to Website User;
		# promote it back so the API treats it as gym staff, not a visitor.
		if user.user_type != "System User":
			user.user_type = "System User"
		user.save(ignore_permissions=True)
