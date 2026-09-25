# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 12.2 — a gym's past money into the official books.

The Subscriptions load step brings in billing history strictly as records: each row
says what a member was charged (``tariff``), what they paid (``fee_collected``) and
when (``due_date`` / ``paid_date``), but nothing reaches the ledger — so the P&L,
the dashboard and Profit First all read those months as zero. This turns each such
row into what ERPNext would have held had the gym been on NetGainz then: one
submitted Sales Invoice dated the due date and, if money came in, one Payment Entry
dated the day it was paid (the due date when the sheet has no paid date — owner
rule, 2026-08-07). What is left unpaid stays owed, exactly as in the gym's sheet.

**Why not a CSV of invoices.** The July backfill tried that; the file named
customers by generated ID and a reload repointed every invoice at the wrong person.
Here the rows are already in the register, so nothing in a file names anything.

**Once only, by construction.** Each invoice carries the Membership row it came from
(``Sales Invoice.membership``, a field this app adds). A row with a submitted invoice
is done; running again posts only what is left.

**Counted like any membership income.** Profit First, commissions and the dashboard
read cash only from membership invoices — until now "has a subscription". History
has none, so ``billing.MEMBERSHIP_INVOICE`` also accepts the mark above.

**Never into a closed month.** A posted Profit First sweep has already allocated a
month's cash, and a posted commission run has already paid coaches on it. Money
landing in or before those dates would silently change figures the owner acted on,
so such rows are refused and named. ERPNext's own freeze / closing-voucher lock
applies too.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, add_years, flt, getdate, today
from frappe.utils.background_jobs import is_job_enqueued

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import billing, branch, period_lock, provisioning
from netgainz.net_gainz.accounting.billing import _as_engine
from netgainz.net_gainz.profit_first import accounts as pf_accounts

JOB_ID = "netgainz-history-into-books"
_LAST_RUN = "netgainz:history-books:last-run"


def ensure_invoice_mark() -> None:
	"""Add ``Sales Invoice.membership``. Idempotent; run on install and by patch."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "membership",
					"label": "Membership (loaded history)",
					"fieldtype": "Link",
					"options": "Membership",
					"insert_after": "subscription",
					"read_only": 1,
					"no_copy": 1,
				}
			]
		},
		update=True,
	)


def _require_owner():
	if not permissions.has_role(permissions.GYM_OWNER):
		frappe.throw("Only the gym owner can put past money into the books.", frappe.PermissionError)


# ------------------------------------------------------------------ what is there


def _history_rows() -> list:
	"""Membership rows that are history: loaded as such (``is_backfill``), or the
	loaded row Start Billing later switched on, for the period before its billing
	began. Rows with nothing charged have nothing to post."""
	rows = frappe.get_all(
		"Membership",
		filters={"tariff": [">", 0], "due_date": ["is", "set"]},
		or_filters={"is_backfill": 1, "subscription": ["is", "set"]},
		fields=[
			"name",
			"member",
			"member_name",
			"membership_plan",
			"branch",
			"tariff",
			"fee_collected",
			"payment_mode",
			"due_date",
			"paid_date",
			"is_backfill",
			"subscription",
		],
		order_by="due_date asc",
		limit_page_length=0,
	)
	subs = {r.subscription for r in rows if r.subscription}
	starts = (
		dict(
			frappe.get_all(
				"Subscription",
				filters={"name": ["in", list(subs)]},
				fields=["name", "start_date"],
				as_list=True,
			)
		)
		if subs
		else {}
	)
	return [
		r
		for r in rows
		if r.is_backfill
		or (starts.get(r.subscription) and getdate(r.due_date) < getdate(starts[r.subscription]))
	]


def _posted() -> dict:
	"""Membership row -> its submitted history invoice (grand total, still owed)."""
	return {
		r.membership: r
		for r in frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "membership": ["is", "set"], "is_return": 0},
			fields=["membership", "name", "grand_total", "outstanding_amount"],
			limit_page_length=0,
		)
	}


def locked_until():
	"""The last date money may no longer land on: the latest posted Profit First sweep
	or coach commission run. ``None`` when neither has been posted."""
	dates = [
		frappe.db.get_value("PF Sweep", {"docstatus": 1}, "max(sweep_date)"),
		frappe.db.get_value("Instructor Commission Run", {"docstatus": 1}, "max(period_end)"),
	]
	dates = [getdate(d) for d in dates if d]
	return max(dates) if dates else None


def _fiscal_year_for(date, company):
	"""(exists?, name-to-create) for the financial year holding ``date``."""
	from erpnext.accounts.utils import get_fiscal_year

	if get_fiscal_year(date, company=company, boolean=True):
		return True, None
	return False, _aligned_year_start(date)


def _aligned_year_start(date):
	"""Start of the year holding ``date``, on the same day-of-year every existing
	financial year starts on. ``None`` if the site has no year to align to."""
	first = frappe.db.get_value("Fiscal Year", {}, "year_start_date", order_by="year_start_date asc")
	if not first:
		return None
	first, date = getdate(first), getdate(date)
	start = first.replace(year=date.year)
	if start > date:
		start = start.replace(year=date.year - 1)
	return start


def _ensure_fiscal_year(start) -> None:
	"""Add the missing financial year, company-agnostic like the one setup made.
	Never scoped to a company: a non-empty ``companies`` table would hide the year
	from every other company (see reference_frappe_fiscal_year_company_scoping)."""
	from erpnext.setup.setup_wizard.operations.install_fixtures import get_fy_details

	end = add_days(add_years(start, 1), -1)
	name = get_fy_details(start, end)
	if not frappe.db.exists("Fiscal Year", name):
		frappe.get_doc(
			{"doctype": "Fiscal Year", "year": name, "year_start_date": start, "year_end_date": end}
		).insert(ignore_permissions=True)


def _blocker(row, company, lock) -> str | None:
	"""Why this row cannot be posted, in the owner's words — or ``None``."""
	due = getdate(row.due_date)
	paid_on = getdate(row.paid_date or row.due_date)
	if due > getdate(today()):
		return "not due yet — it will bill the normal way"
	if flt(row.fee_collected) > flt(row.tariff):
		return f"paid {flt(row.fee_collected):,.0f}, more than the {flt(row.tariff):,.0f} charged"
	if lock and min(due, paid_on) <= lock:
		return f"on or before {lock:%d %b %Y}, which Profit First or a commission run has already closed"
	for d in {due, paid_on}:
		if period_lock.is_period_locked(d, company):
			return f"{d:%d %b %Y} is in a period your books have closed"
	if not row.membership_plan:
		return "no plan on this row, so there is nothing to bill it as"
	return None


# ------------------------------------------------------------------ the owner's view


@frappe.whitelist()
def preview() -> dict:
	"""Owner/BFF: month by month, what the gym's records say against what the books
	hold, plus every row that cannot be posted and why. Writes nothing."""
	_require_owner()
	company = pf_accounts.default_company()
	lock = locked_until()
	posted = _posted()
	months: dict[str, dict] = {}
	blocked, pending, years_to_add = [], 0, set()

	for r in _history_rows():
		m = months.setdefault(
			f"{getdate(r.due_date):%Y-%m}",
			{
				"rows": 0,
				"posted": 0,
				"sheet_billed": 0.0,
				"sheet_paid": 0.0,
				"books_billed": 0.0,
				"books_paid": 0.0,
			},
		)
		m["rows"] += 1
		m["sheet_billed"] += flt(r.tariff)
		m["sheet_paid"] += flt(r.fee_collected)
		inv = posted.get(r.name)
		if inv:
			m["posted"] += 1
			m["books_billed"] += flt(inv.grand_total)
			m["books_paid"] += flt(inv.grand_total) - flt(inv.outstanding_amount)
			continue
		reason = _blocker(r, company, lock)
		if reason:
			blocked.append(
				{"membership": r.name, "member": r.member_name, "due_date": r.due_date, "reason": reason}
			)
			continue
		pending += 1
		for d in {getdate(r.due_date), getdate(r.paid_date or r.due_date)}:
			exists, start = _fiscal_year_for(d, company)
			if not exists and start:
				years_to_add.add(str(start))

	for key, m in months.items():
		m["month"] = key
		m["matches"] = (
			m["posted"] == m["rows"]
			and round(m["sheet_billed"], 2) == round(m["books_billed"], 2)
			and round(m["sheet_paid"], 2) == round(m["books_paid"], 2)
		)
	return {
		"months": [months[k] for k in sorted(months)],
		"pending": pending,
		"blocked": blocked,
		"locked_until": lock,
		"years_to_add": sorted(years_to_add),
		"running": is_job_enqueued(JOB_ID),
		"last_run": frappe.cache().get_value(_LAST_RUN),
	}


@frappe.whitelist(methods=["POST"])
def post_history() -> dict:
	"""Owner/BFF: post every postable history row. Background job; poll ``preview``."""
	_require_owner()
	if not pf_accounts.default_company():
		frappe.throw("Set up your business first.")
	if not is_job_enqueued(JOB_ID):
		frappe.enqueue(_post_all, queue="long", timeout=3600, job_id=JOB_ID, deduplicate=True)
	return {"status": "running"}


def _post_all() -> dict:
	company = pf_accounts.default_company()
	lock = locked_until()
	posted = _posted()
	done, failed = 0, []
	with _as_engine():
		for r in _history_rows():
			if r.name in posted or _blocker(r, company, lock):
				continue
			try:
				for d in {getdate(r.due_date), getdate(r.paid_date or r.due_date)}:
					exists, start = _fiscal_year_for(d, company)
					if not exists and start:
						_ensure_fiscal_year(start)
				post_row(r, company)
				frappe.db.commit()
				done += 1
			except Exception as exc:
				frappe.db.rollback()
				failed.append(
					{"member": r.member_name, "due_date": str(r.due_date), "reason": _last_line(exc)}
				)
	result = {"posted": done, "failed": failed, "finished": frappe.utils.now()}
	frappe.cache().set_value(_LAST_RUN, result, expires_in_sec=7 * 24 * 3600)
	return result


def _last_line(exc) -> str:
	text = str(exc).strip() or exc.__class__.__name__
	return frappe.utils.strip_html(text.splitlines()[-1])


def post_row(row, company) -> str:
	"""One history row -> submitted Sales Invoice (+ Payment Entry if paid)."""
	customer = frappe.db.get_value("Member", row.member, "customer") or provisioning.provision_customer(
		row.member, company
	)
	item = frappe.db.get_value("Membership Plan", row.membership_plan, "item") or provisioning.provision_item(
		row.membership_plan, company
	)
	if not (customer and item):
		frappe.throw("The member or the plan could not be set up for billing.")

	si = frappe.new_doc("Sales Invoice")
	si.company = company
	si.customer = customer
	si.set_posting_time = 1
	si.posting_date = row.due_date
	si.due_date = row.due_date
	si.membership = row.name
	si.cost_center = branch.branch_cost_center(row.branch, company)
	si.append("items", {"item_code": item, "qty": 1, "rate": flt(row.tariff)})
	si.set_missing_values()
	# The sheet says what the member was charged, full stop. Where GST applies (the
	# same rules as live billing decide), it is inside that figure, not on top of it.
	for tax in si.get("taxes") or []:
		tax.included_in_print_rate = 1
	si.insert(ignore_permissions=True)
	si.submit()

	if flt(row.fee_collected) > 0:
		# record_payment re-points the membership at the invoice it settles. For the
		# row Start Billing switched on, that pointer belongs to live billing — put it back.
		live = (
			frappe.db.get_value("Membership", row.name, "current_sales_invoice") if row.subscription else None
		)
		billing.record_payment(
			row.name,
			flt(row.fee_collected),
			row.payment_mode or "Cash",
			row.paid_date or row.due_date,
			sales_invoice=si.name,
			company=company,
		)
		if row.subscription:
			frappe.db.set_value("Membership", row.name, "current_sales_invoice", live, update_modified=False)
			billing.sync_derived_fields(row.name)
	return si.name
