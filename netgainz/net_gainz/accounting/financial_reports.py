# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 11.5 — financial reports for the owner-app, from ERPNext's own reports.

No accounting maths here: each report is ERPNext's (Profit and Loss Statement,
Balance Sheet, Cash Flow, Trial Balance, General Ledger, Accounts Receivable) run
with the gym's company, the period asked for and — when the branch switcher is on
one branch — that branch's cost center. This module only picks the filters and
flattens the result to plain columns + rows the owner-app can draw and download.

Owner only: these are the gym's whole books.
"""

import io

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.desk.query_report import run
from frappe.utils import getdate

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import branch as branch_mod

# key -> (ERPNext report, kind, gym-language title)
REPORTS = {
	"profit_and_loss": ("Profit and Loss Statement", "statement", "Profit & Loss"),
	"balance_sheet": ("Balance Sheet", "statement", "Balance Sheet — what the gym owns and owes"),
	"cash_flow": ("Cash Flow", "statement", "Cash Flow — money in and out"),
	"trial_balance": ("Trial Balance", "trial", "Trial Balance"),
	"general_ledger": ("General Ledger", "ledger", "Day Book — every entry, by date"),
	"cash_book": ("General Ledger", "cash", "Cash Book"),
	"bank_book": ("General Ledger", "bank", "Bank Book (UPI, card, bank transfer)"),
	"receivables": ("Accounts Receivable", "ageing", "Who owes the gym, and for how long"),
}

# The ledger reports carry ~20 columns; these are the ones a person reads.
_KEEP = {
	"ledger": [
		"posting_date",
		"account",
		"party",
		"voucher_type",
		"voucher_no",
		"debit",
		"credit",
		"balance",
		"remarks",
	],
	"ageing": [
		"party",
		"voucher_no",
		"posting_date",
		"due_date",
		"invoiced",
		"paid",
		"outstanding",
		"range1",
		"range2",
		"range3",
		"range4",
		"range5",
	],
}


def _fy(date, company):
	return get_fiscal_year(date, company=company)  # (name, start, end); throws if none


def _filters(kind, start, end, periodicity, company, ccs):
	start, end = getdate(start), getdate(end)
	if kind == "statement":
		f = {
			"company": company,
			"filter_based_on": "Date Range",
			"period_start_date": start,
			"period_end_date": end,
			"from_fiscal_year": _fy(start, company)[0],
			"to_fiscal_year": _fy(end, company)[0],
			"periodicity": periodicity or "Monthly",
			"presentation_currency": frappe.get_cached_value("Company", company, "default_currency"),
		}
		if ccs:
			f["cost_center"] = ccs
		return f
	if kind == "trial":
		fy, _, fy_end = _fy(start, company)
		# ponytail: one financial year per run (ERPNext's rule); a range crossing
		# 31 March is cut at the year end.
		f = {"company": company, "fiscal_year": fy, "from_date": start, "to_date": min(end, getdate(fy_end))}
		if ccs:
			f["cost_center"] = ccs[0]
		return f
	if kind == "ageing":
		f = {
			"company": company,
			"report_date": end,
			"ageing_based_on": "Due Date",
			"range": "30, 60, 90, 120",
			"party_type": "Customer",
		}
		if ccs:
			f["cost_center"] = ccs[0]
		return f
	f = {
		"company": company,
		"from_date": start,
		"to_date": end,
		"group_by": "Group by Voucher (Consolidated)",
	}
	if kind in ("cash", "bank"):
		f["account"] = frappe.get_all(
			"Account",
			filters={"company": company, "account_type": kind.title(), "is_group": 0},
			pluck="name",
		)
	if ccs:
		f["cost_center"] = ccs
	return f


def _columns(raw, kind):
	cols = []
	for c in raw or []:
		if isinstance(c, str):  # "Label:Fieldtype/Options:width"
			label, _, rest = c.partition(":")
			c = {
				"label": label,
				"fieldname": frappe.scrub(label),
				"fieldtype": rest.split(":")[0].split("/")[0],
			}
		if c.get("hidden") or not c.get("fieldname"):
			continue
		cols.append(
			{
				"fieldname": c["fieldname"],
				"label": c.get("label") or c["fieldname"],
				"fieldtype": c.get("fieldtype") or "Data",
			}
		)
	keep = _KEEP.get(kind if kind not in ("cash", "bank") else "ledger")
	if keep:
		by = {c["fieldname"]: c for c in cols}
		cols = [by[f] for f in keep if f in by]
	return [c for c in cols if c["fieldname"] != "currency"]


def _rows(raw, columns):
	names = [c["fieldname"] for c in columns]
	out = []
	for r in raw or []:
		if isinstance(r, list | tuple) or not r:
			continue
		label = r.get("account_name") or r.get("section_name") or r.get("section")
		row = {n: r.get(n) for n in names}
		# Statements put the readable name in account_name / section; ERPNext quotes
		# its computed lines ("'Profit for the year'").
		for key in ("account", "section"):
			if key in row and (label or row[key]):
				row[key] = str(label or row[key]).strip("'")
		row["_indent"] = int(r.get("indent") or 0)
		out.append(row)
	return out


def build(report, start, end, periodicity=None, branch=None) -> dict:
	if report not in REPORTS:
		frappe.throw(f"Unknown report {report}.")
	erp_report, kind, title = REPORTS[report]
	company = branch_mod._company()
	ccs = branch_mod.scope_cost_centers(branch_mod.scope(branch))
	result = run(
		erp_report, filters=_filters(kind, start, end, periodicity, company, ccs), ignore_prepared_report=True
	)
	columns = _columns(result.get("columns"), kind)
	return {
		"report": report,
		"title": title,
		"columns": columns,
		"rows": _rows(result.get("result"), columns),
	}


@frappe.whitelist()
def get_financial_report(report, start, end, periodicity=None, branch=None) -> dict:
	"""Owner: one financial report as plain columns + rows."""
	permissions.require_role(permissions.GYM_OWNER)
	return build(report, start, end, periodicity, branch)


@frappe.whitelist()
def accountant_pack(start, end, branch=None):
	"""Owner: one Excel file for the accountant — P&L, Balance Sheet, Cash Flow,
	Trial Balance and the Day Book for the period, one sheet each."""
	from openpyxl import Workbook

	permissions.require_role(permissions.GYM_OWNER)
	wb = Workbook()
	wb.remove(wb.active)
	for key in ("profit_and_loss", "balance_sheet", "cash_flow", "trial_balance", "general_ledger"):
		data = build(key, start, end, "Monthly", branch)
		ws = wb.create_sheet(REPORTS[key][0][:31])
		ws.append([c["label"] for c in data["columns"]])
		for r in data["rows"]:
			ws.append(
				[
					("  " * r["_indent"] + str(r[c["fieldname"]] or "")) if i == 0 else r[c["fieldname"]]
					for i, c in enumerate(data["columns"])
				]
			)
	buf = io.BytesIO()
	wb.save(buf)
	frappe.response["filename"] = f"accounts-{start}-to-{end}.xlsx"
	frappe.response["filecontent"] = buf.getvalue()
	frappe.response["type"] = "binary"
