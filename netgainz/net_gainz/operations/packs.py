# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""PT session packs & day passes — the second revenue engine (Stage 9 OP-4).

Pure Stage-7-rails reuse: a sale is a real, submitted Sales Invoice plus a
Payment Entry in one action, so the cash lands in the books — and therefore in
Profit First — exactly like a membership payment (R9: no PF code changes).

* A **Session Pack** is an owner-defined product (N sessions, validity days,
  price). Saving one provisions its sellable ERPNext Item silently, HSN/SAC
  defaulted like plans — no tax code, no billing, so the code is never blank.
* A **Pack Purchase** is the sale + burn-down state. ``sessions_used`` is
  counted from the ``Pack Session Use`` log, never incremented in place, so the
  balance cannot drift (the DS-3 redemption reasoning). Expiry is a read-time
  fact stamped lazily — no scheduler recomputes status at midnight.
* A **Day Pass** is a walk-in quick sale: guest name + phone, cash/UPI, one
  action. Walk-ins are not Members; the invoice posts against one provisioned
  "Walk-in" Customer per tenant, and the pass record keeps who actually came.
* Expiry / low-balance alerts follow the renewals pattern: a read-model plus
  ONE idempotent in-app digest per user per day, opt-out via
  ``pack_alerts_enabled``.
"""

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, today

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import (
	branch,
	currency,
	payment_modes,
	period_lock,
)

# The same module, for functions whose ``branch`` argument shadows the name above.
from netgainz.net_gainz.accounting import branch as branch_mod
from netgainz.net_gainz.accounting.provisioning import (
	_ROOT_ITEM_GROUP,
	DEFAULT_CUSTOMER_TYPE,
	DEFAULT_ITEM_GROUP,
	DEFAULT_UOM,
	_company,
	_resolve,
)
from netgainz.net_gainz.doctype.session_pack.session_pack import DEFAULT_HSN_SAC

WALKIN_CUSTOMER_NAME = "Walk-in Guest"
DAY_PASS_ITEM = "Day Pass"

DEFAULT_EXPIRY_ALERT_DAYS = 7
LOW_BALANCE_AT = 1


def _expiry_alert_days() -> int:
	raw = frappe.db.get_single_value("Business Settings", "pack_expiry_alert_days")
	try:
		days = int(raw)
	except (TypeError, ValueError):
		days = DEFAULT_EXPIRY_ALERT_DAYS
	return days if days > 0 else DEFAULT_EXPIRY_ALERT_DAYS


# --------------------------------------------------------------------------- #
# provisioning (silent — ERPNext is an engine, not a UI)
# --------------------------------------------------------------------------- #
def _ensure_item(item_code, item_name, hsn, description=None) -> str | None:
	"""A sellable service Item, provisioned once. Mirrors provisioning.provision_item
	minus the plan-specific parts (no Item Price — pack invoices carry an explicit
	rate; R14: Item Price rows stay untouched)."""
	if frappe.db.exists("Item", item_code):
		return item_code
	if not hsn or not _company():
		return None
	item = frappe.new_doc("Item")
	item.item_code = item_code
	item.item_name = item_name
	item.item_group = _resolve("Item Group", DEFAULT_ITEM_GROUP, _ROOT_ITEM_GROUP)
	item.stock_uom = (
		DEFAULT_UOM
		if frappe.db.exists("UOM", DEFAULT_UOM)
		else (frappe.db.get_single_value("Stock Settings", "stock_uom") or DEFAULT_UOM)
	)
	item.is_stock_item = 0
	item.is_sales_item = 1
	item.is_purchase_item = 0
	item.include_item_in_manufacturing = 0
	item.gst_hsn_code = hsn
	if description:
		item.description = description
	item.insert(ignore_permissions=True)
	return item.name


def provision_pack(pack) -> str | None:
	"""Ensure the Session Pack has its Item; returns the Item name."""
	if isinstance(pack, str):
		pack = frappe.get_doc("Session Pack", pack)
	if pack.get("item") and frappe.db.exists("Item", pack.item):
		return pack.item
	item = _ensure_item(pack.name, pack.pack_name, pack.gst_hsn_code, pack.get("description"))
	if item:
		pack.db_set("item", item, update_modified=False)
	return item


def on_pack_update(doc, method=None):
	"""``on_update`` doc_event for Session Pack. Idempotent, best-effort."""
	if frappe.flags.in_install:
		return
	try:
		provision_pack(doc)
	except Exception:
		frappe.log_error(title="Session Pack provisioning failed")


def _ensure_walkin_customer(company) -> str | None:
	"""One Customer per tenant for day-pass guests — a walk-in is not a Member,
	and minting a Customer per guest would bury the party ledger in one-visit
	records. WHO came is on the Day Pass itself."""
	existing = frappe.db.get_value("Customer", {"customer_name": WALKIN_CUSTOMER_NAME}, "name")
	if existing:
		return existing
	customer = frappe.new_doc("Customer")
	customer.customer_name = WALKIN_CUSTOMER_NAME
	customer.customer_type = DEFAULT_CUSTOMER_TYPE
	group = _resolve("Customer Group", "Individual", None)
	if group:
		customer.customer_group = group
	territory = _resolve("Territory", "All Territories", None)
	if territory:
		customer.territory = territory
	customer.insert(ignore_permissions=True)
	return customer.name


# --------------------------------------------------------------------------- #
# the one-action sale (Sales Invoice + Payment Entry)
# --------------------------------------------------------------------------- #
def _sell(customer, item, rate, payment_mode, cost_center, remarks, company) -> tuple[str, str]:
	"""A submitted Sales Invoice and its full Payment Entry, in one action.

	The invoice shape is the go-live stub's (traced): resolve the party's tax
	template and EXPAND its rows — without ``set_taxes`` the invoice comes out
	with ``taxes_and_charges`` set but no GST charged.
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	currency.assert_paise_safe(company)
	period_lock.assert_postable(getdate(today()), company)

	si = frappe.new_doc("Sales Invoice")
	si.customer = customer
	si.company = company
	si.set_posting_time = 1
	si.posting_date = getdate(today())
	si.due_date = getdate(today())
	si.cost_center = cost_center
	si.remarks = remarks
	si.append("items", {"item_code": item, "qty": 1, "rate": flt(rate), "cost_center": cost_center})
	si.set_missing_values(for_validate=True)
	currency.pin_to_company_currency(si, company)
	if si.taxes_and_charges and not si.get("taxes"):
		si.set_taxes()
	si.insert(ignore_permissions=True)
	si.submit()

	pe = get_payment_entry("Sales Invoice", si.name)
	pe.payment_type = "Receive"
	pe.posting_date = getdate(today())
	pe.reference_date = getdate(today())
	if payment_mode:
		pe.mode_of_payment = payment_mode
		paid_to = payment_modes.paid_to_account(company, payment_mode)
		if paid_to:
			pe.paid_to = paid_to
	pe.cost_center = cost_center
	pe.insert(ignore_permissions=True)
	pe.submit()

	return si.name, pe.name


# --------------------------------------------------------------------------- #
# session packs
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def sell_pack(member, session_pack, payment_mode="Cash", price=None, notes=None) -> dict:
	"""Sell a pack to a member: invoice + payment + the burn-down record, one tap.

	``price`` overrides the pack's list price for THIS sale (gyms negotiate —
	same philosophy as per-member membership pricing)."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	branch_mod.assert_can_see("Member", member)

	company = _company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	if not frappe.db.exists("Member", member):
		frappe.throw(f"Member {member} does not exist.")
	pack = frappe.get_doc("Session Pack", session_pack)
	if not pack.is_active:
		frappe.throw(f"{pack.pack_name} is not on sale.")
	item = provision_pack(pack)
	if not item:
		frappe.throw(f"{pack.pack_name} cannot bill yet (no tax code) — fix the pack first.")

	rate = flt(price) if price not in (None, "") else flt(pack.price)
	if rate <= 0:
		frappe.throw("The pack price must be greater than zero.")

	member_branch = frappe.db.get_value("Member", member, "branch")
	cost_center = branch.branch_cost_center(member_branch, company)
	member_name = frappe.db.get_value("Member", member, "full_name")

	si, pe = _sell(
		customer=frappe.db.get_value("Member", member, "customer"),
		item=item,
		rate=rate,
		payment_mode=payment_mode,
		cost_center=cost_center,
		remarks=f"NetGainz: {pack.pack_name} for {member_name or member}",
		company=company,
	)

	purchase = frappe.get_doc(
		{
			"doctype": "Pack Purchase",
			"member": member,
			"session_pack": pack.name,
			"purchased_on": today(),
			"expires_on": add_days(today(), (pack.validity_days or 1) - 1),
			"sessions_total": pack.sessions,
			"sessions_used": 0,
			"amount": rate,
			"payment_mode": payment_mode,
			"sales_invoice": si,
			"payment_entry": pe,
			"notes": notes,
		}
	)
	purchase.insert()

	return {
		"pack_purchase": purchase.name,
		"member": member,
		"member_name": member_name,
		"sessions": pack.sessions,
		"expires_on": str(purchase.expires_on),
		"amount": rate,
		"sales_invoice": si,
		"payment_entry": pe,
	}


def _refresh_status(purchase) -> str:
	"""Re-derive the burn-down status from the log + the calendar."""
	used = frappe.db.count("Pack Session Use", {"pack_purchase": purchase.name})
	if used >= (purchase.sessions_total or 0):
		status = "Exhausted"
	elif getdate(today()) > getdate(purchase.expires_on):
		status = "Expired"
	else:
		status = "Active"
	purchase.db_set("sessions_used", used, update_modified=False)
	purchase.db_set("status", status, update_modified=False)
	return status


@frappe.whitelist()
def use_session(pack_purchase, note=None) -> dict:
	"""Burn one session off a pack — a PT booking or a desk tap."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	branch_mod.assert_can_see("Pack Purchase", pack_purchase)

	purchase = frappe.get_doc("Pack Purchase", pack_purchase)
	status = _refresh_status(purchase)
	if status == "Exhausted":
		frappe.throw(f"All {purchase.sessions_total} sessions of this pack have been used — sell a new one.")
	if status == "Expired":
		frappe.throw(
			f"This pack expired on {frappe.format_value(purchase.expires_on, {'fieldtype': 'Date'})}."
		)

	frappe.get_doc(
		{
			"doctype": "Pack Session Use",
			"pack_purchase": purchase.name,
			"member": purchase.member,
			"note": note,
		}
	).insert(ignore_permissions=True)

	status = _refresh_status(purchase)
	remaining = (purchase.sessions_total or 0) - (purchase.sessions_used or 0)
	return {
		"pack_purchase": purchase.name,
		"used": purchase.sessions_used,
		"total": purchase.sessions_total,
		"remaining": remaining,
		"status": status,
	}


@frappe.whitelist()
def pack_balances(member=None, branch=None) -> dict:
	"""Live pack balances — the member card and the packs page read this.

	Status is re-derived per row (expiry is a calendar fact; nothing recomputes
	it at midnight), so a pack that lapsed yesterday reads Expired today.
	``branch`` narrows it to packs sold there (Stage 10.3)."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	filters = {}
	if member:
		filters["member"] = member
	filters = branch_mod.filter_by_branch(filters, branch_mod.scope(branch))
	rows = []
	td = getdate(today())
	for name in frappe.get_all("Pack Purchase", filters=filters, pluck="name", limit_page_length=0):
		purchase = frappe.get_doc("Pack Purchase", name)
		status = _refresh_status(purchase)
		rows.append(
			{
				"pack_purchase": purchase.name,
				"member": purchase.member,
				"member_name": purchase.member_name,
				"session_pack": purchase.session_pack,
				"used": purchase.sessions_used or 0,
				"total": purchase.sessions_total or 0,
				"remaining": (purchase.sessions_total or 0) - (purchase.sessions_used or 0),
				"purchased_on": str(purchase.purchased_on),
				"expires_on": str(purchase.expires_on),
				"days_left": max(0, (getdate(purchase.expires_on) - td).days),
				"status": status,
			}
		)
	active = [r for r in rows if r["status"] == "Active"]
	closed = [r for r in rows if r["status"] != "Active"]
	active.sort(key=lambda r: r["expires_on"])
	closed.sort(key=lambda r: r["expires_on"], reverse=True)
	return {"active": active, "closed": closed[:20], "active_count": len(active)}


def get_pack_alerts(branches=None) -> dict:
	"""Active packs about to expire or nearly used up — worth a word at the desk.
	``branches`` narrows it to packs sold there (Stage 10.3)."""
	within = _expiry_alert_days()
	horizon = add_days(getdate(today()), within)
	alerts = []
	for row in pack_balances_unchecked(branches):
		if row["status"] != "Active":
			continue
		expiring = getdate(row["expires_on"]) <= horizon
		low = row["remaining"] <= LOW_BALANCE_AT
		if expiring or low:
			alerts.append({**row, "expiring": expiring, "low_balance": low})
	alerts.sort(key=lambda r: (r["expires_on"], r["remaining"]))
	return {"within_days": within, "alerts": alerts, "alert_count": len(alerts)}


def pack_balances_unchecked(branches=None) -> list[dict]:
	"""pack_balances' rows without the role gate — for the scheduler."""
	td = getdate(today())
	rows = []
	for name in frappe.get_all(
		"Pack Purchase",
		filters=branch_mod.filter_by_branch({}, branches),
		pluck="name",
		limit_page_length=0,
	):
		purchase = frappe.get_doc("Pack Purchase", name)
		status = _refresh_status(purchase)
		rows.append(
			{
				"pack_purchase": purchase.name,
				"member": purchase.member,
				"member_name": purchase.member_name,
				"session_pack": purchase.session_pack,
				"remaining": (purchase.sessions_total or 0) - (purchase.sessions_used or 0),
				"expires_on": str(purchase.expires_on),
				"days_left": max(0, (getdate(purchase.expires_on) - td).days),
				"status": status,
			}
		)
	return rows


@frappe.whitelist()
def get_pack_alerts_due(branch=None) -> dict:
	"""Whitelisted read-model for the packs page."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	return get_pack_alerts(branches=branch_mod.scope(branch))


def notify_pack_alerts():
	"""Daily scheduler hook: ONE in-app notification per owner/staff user listing
	packs expiring or nearly used up. Idempotent (one digest per user per day),
	opt-out via pack_alerts_enabled. No email/SMS is sent."""
	from netgainz.net_gainz.operations import renewals

	if not frappe.db.get_single_value("Business Settings", "pack_alerts_enabled"):
		return None

	data = get_pack_alerts()
	alerts = data["alerts"]
	if not alerts:
		return None

	td = getdate(today())
	subject = f"{len(alerts)} session pack(s) expiring or nearly used up"
	body = "<br>".join(
		f"{r['member_name'] or r['member']} — {r['session_pack']}: "
		f"{r['remaining']} left, expires {r['expires_on']}"
		for r in alerts[:20]
	)

	created = 0
	for user in renewals._owner_users():
		if frappe.db.exists(
			"Notification Log",
			{"for_user": user, "subject": subject, "creation": [">=", str(td)]},
		):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": body,
				"document_type": "Pack Purchase",
			}
		).insert(ignore_permissions=True)
		created += 1

	frappe.logger("netgainz").info(f"Pack alerts: {len(alerts)} flagged, notified {created} user(s)")
	return {"alerts": len(alerts), "notified": created}


# --------------------------------------------------------------------------- #
# day passes
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def sell_day_pass(guest_name, amount, phone=None, payment_mode="Cash", notes=None, branch_name=None) -> dict:
	"""The walk-in quick sale: name + phone, cash/UPI — invoice + payment + the
	pass record in one action."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	company = _company()
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	guest_name = (guest_name or "").strip()
	if not guest_name:
		frappe.throw("Who is the pass for? A name is required.")
	amount = flt(amount)
	if amount <= 0:
		frappe.throw("The day pass amount must be greater than zero.")

	hsn = frappe.db.get_single_value("Business Settings", "default_hsn_sac") or DEFAULT_HSN_SAC
	item = _ensure_item(DAY_PASS_ITEM, DAY_PASS_ITEM, hsn, "Single-visit day pass")
	if not item:
		frappe.throw("Day passes cannot bill yet — set a default tax code in Settings.")
	customer = _ensure_walkin_customer(company)

	# Stage 10.1: a walk-in pays at a branch; its money belongs to that branch.
	branch_name = branch_name or branch.ensure_default_branch(company)
	cost_center = branch.branch_cost_center(branch_name, company)
	si, pe = _sell(
		customer=customer,
		item=item,
		rate=amount,
		payment_mode=payment_mode,
		cost_center=cost_center,
		remarks=f"NetGainz: day pass — {guest_name}",
		company=company,
	)

	day_pass = frappe.get_doc(
		{
			"doctype": "Day Pass",
			"guest_name": guest_name,
			"phone": phone,
			"amount": amount,
			"payment_mode": payment_mode,
			"sales_invoice": si,
			"payment_entry": pe,
			"notes": notes,
			"branch": branch_name,
		}
	)
	day_pass.insert()

	return {
		"day_pass": day_pass.name,
		"guest_name": guest_name,
		"amount": amount,
		"sales_invoice": si,
		"payment_entry": pe,
	}


@frappe.whitelist()
def todays_day_passes(branch=None) -> dict:
	"""The desk's list: passes sold today, newest first, with the day's total.
	``branch`` narrows it to one location (Stage 10.3)."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)

	rows = frappe.get_all(
		"Day Pass",
		filters=branch_mod.filter_by_branch({"visited_on": today()}, branch_mod.scope(branch)),
		fields=["name", "guest_name", "phone", "amount", "payment_mode", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	for r in rows:
		r["creation"] = str(r.creation)
	return {"passes": rows, "count": len(rows), "total": sum(flt(r.amount) for r in rows)}


@frappe.whitelist()
def get_pack_report(months=12, branch=None) -> dict:
	"""Stage 11.3: per pack sold in the last ``months`` months — how many, for how
	much, sessions used, and packs that EXPIRED with sessions left (money taken for
	sessions never used). Same used / expired rule as ``_refresh_status``, read-only:
	sessions used counted from the use log, expiry from the calendar."""
	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	since = add_months(get_first_day(today()), -(max(1, min(int(months), 36)) - 1))
	purchases = frappe.get_all(
		"Pack Purchase",
		filters=branch_mod.filter_by_branch({"purchased_on": [">=", since]}, branch_mod.scope(branch)),
		fields=["name", "session_pack", "expires_on", "sessions_total", "amount"],
	)
	used = dict(
		frappe.get_all(
			"Pack Session Use",
			filters={"pack_purchase": ["in", [p.name for p in purchases] or [""]]},
			fields=["pack_purchase", "count(*)"],
			group_by="pack_purchase",
			as_list=True,
		)
	)
	td = getdate(today())
	packs: dict[str, dict] = {}
	for p in purchases:
		total, n = p.sessions_total or 0, min(used.get(p.name, 0), p.sessions_total or 0)
		r = packs.setdefault(
			p.session_pack,
			{
				"pack": p.session_pack,
				"sold": 0,
				"amount": 0.0,
				"sessions": 0,
				"used": 0,
				"active": 0,
				"expired_unused": 0,
				"sessions_lost": 0,
				"value_lost": 0.0,
			},
		)
		r["sold"] += 1
		r["amount"] += flt(p.amount)
		r["sessions"] += total
		r["used"] += n
		if n < total and td > getdate(p.expires_on):
			r["expired_unused"] += 1
			r["sessions_lost"] += total - n
			r["value_lost"] += flt(p.amount) * (total - n) / total
		elif n < total:
			r["active"] += 1
	rows = sorted(packs.values(), key=lambda r: -r["amount"])
	for r in rows:
		r["used_pct"] = round(100 * r["used"] / r["sessions"], 1) if r["sessions"] else None
		r["amount"], r["value_lost"] = flt(r["amount"], 2), flt(r["value_lost"], 2)
	return {"since": str(since), "rows": rows}
