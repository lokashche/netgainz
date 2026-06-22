# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Profit First — dashboard data (Stage 5c).

Read-only summary for the owner: how much cash is set aside in each allocation
reserve, when the next sweep is due, and any sweep awaiting approval.
"""

import frappe

from netgainz.net_gainz.profit_first import calc
from netgainz.net_gainz.profit_first.schedule import next_sweep_date, parse_allocation_days


def _balance(account: str) -> float:
	"""Current ledger balance of a reserve account (0 if unmapped/unposted)."""
	if not account:
		return 0.0
	try:
		from erpnext.accounts.utils import get_balance_on

		return get_balance_on(account=account) or 0.0
	except Exception:
		return 0.0


@frappe.whitelist()
def get_pf_dashboard() -> dict:
	settings = frappe.get_single("Profit First Settings")
	if not settings.pf_enabled:
		return {"enabled": False}

	acc_map = {r.account_role: r for r in settings.accounts}
	reserves = []
	for role in calc.ALLOCATION_BUCKETS:
		row = acc_map.get(role)
		account = row.account_link if row else None
		reserves.append({"role": role, "account": account, "balance": _balance(account)})

	days = parse_allocation_days(settings.allocation_days)
	nxt = next_sweep_date(days=days)

	pending = frappe.get_all(
		"PF Sweep",
		filters={"docstatus": 0},
		fields=["name", "sweep_date", "real_revenue", "tier_code"],
		order_by="sweep_date desc",
		limit_page_length=0,
	)
	last = frappe.get_all(
		"PF Sweep",
		filters={"docstatus": 1},
		fields=["name", "sweep_date", "real_revenue", "journal_entry"],
		order_by="sweep_date desc",
		limit_page_length=1,
	)

	return {
		"enabled": True,
		"accounts_ready": all(r["account"] for r in reserves),
		"reserves": reserves,
		# effective days (so display is correct even if the stored value is blank
		# on a Single that predates the field)
		"allocation_days": ", ".join(str(d) for d in days),
		"auto_create": bool(settings.sweep_auto_create),
		"next_sweep_date": str(nxt) if nxt else None,
		"pending_sweeps": pending,
		"last_sweep": last[0] if last else None,
	}
