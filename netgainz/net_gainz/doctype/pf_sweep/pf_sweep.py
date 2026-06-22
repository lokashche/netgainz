# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""PF Sweep — the bi-monthly Profit First allocation (Stage 5b).

A PF Sweep is BOTH the proposal and the audit record. On creation it snapshots
the period's Real Revenue and the tier's target split into a frozen, read-only
proposal (no money moves). On submit — the owner's explicit Approve & Post — it
posts ONE balanced Journal Entry that recognises Real Revenue into the Income
account and debits the four asset reserve accounts by their share. Cancelling the
sweep cancels that Journal Entry. Every rupee is gated behind manual approval.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

from netgainz.net_gainz.profit_first import accounts, calc
from netgainz.net_gainz.profit_first import instant_assessment as ia


class PFSweep(Document):
	def before_insert(self):
		self.populate_proposal()

	def populate_proposal(self):
		"""Snapshot Real Revenue, the target split, and the mapped ledger accounts.
		Taken once at creation so the proposal is a stable audit record."""
		settings = frappe.get_single("Profit First Settings")
		self.company = self.company or settings.company or accounts.default_company()
		# Read the window via a direct DB read: a Single's scalar fields can be
		# served stale from the singles cache within the request they were last
		# changed in (e.g. settings updated then a sweep created in one flow).
		self.assessment_window = (
			self.assessment_window
			or frappe.db.get_single_value("Profit First Settings", "assessment_window")
			or "Trailing 12 Months"
		)
		if not self.sweep_date:
			self.sweep_date = today()

		res = ia.get_target_allocation(self.assessment_window)
		self.real_revenue = calc.to_rupees(res["real_revenue_paise"])
		self.tier_code = res["tier_code"]
		self.period_label = res["period_label"]
		taps = res.get("taps", {})

		acc_map = {r.account_role: r for r in settings.accounts}
		cc_default = frappe.get_cached_value("Company", self.company, "cost_center") if self.company else None

		self.set("allocations", [])
		for role in calc.ALLOCATION_BUCKETS:
			row = acc_map.get(role)
			self.append(
				"allocations",
				{
					"account_role": role,
					"pf_account": row.account_link if row else None,
					"cost_center": (row.cost_center if row and row.cost_center else cc_default),
					"target_pct": taps.get(role),
					"amount": calc.to_rupees(res["allocations_paise"].get(role, 0)),
				},
			)

		inc = acc_map.get("Income")
		self.income_account = inc.account_link if inc else None
		self.income_cost_center = inc.cost_center if inc and inc.cost_center else cc_default

	def before_submit(self):
		if not self.allocations:
			frappe.throw("This sweep has no allocations to post.")
		if flt(self.real_revenue) <= 0:
			frappe.throw("Real Revenue is zero or negative for this period — there is nothing to sweep.")

		missing = [a.account_role for a in self.allocations if not a.pf_account]
		if not self.income_account:
			missing.append("Income")
		if missing:
			frappe.throw(
				"These Profit First accounts are not mapped to a ledger account: "
				+ ", ".join(missing)
				+ ". Run Profit First account setup first."
			)

		# Idempotency: at most one posted sweep per sweep_date.
		dup = frappe.db.exists(
			"PF Sweep",
			{"sweep_date": self.sweep_date, "docstatus": 1, "name": ["!=", self.name]},
		)
		if dup:
			frappe.throw(f"A sweep for {self.sweep_date} has already been posted ({dup}).")

	def on_submit(self):
		self.db_set("journal_entry", self._post_journal_entry())

	def on_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
		self.db_set("journal_entry", None)

	def _post_journal_entry(self) -> str:
		"""Post the balanced recognise-and-allocate Journal Entry.

		Debit each asset reserve account by its allocation; credit the Income
		account by the total Real Revenue. Debits sum to Real Revenue (the split is
		cent-exact), so the entry balances to the paisa.
		"""
		total = flt(self.real_revenue, 2)
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = self.company
		je.posting_date = self.sweep_date
		je.user_remark = f"Profit First sweep {self.name} — {self.period_label or ''}".strip()

		for a in self.allocations:
			je.append(
				"accounts",
				{
					"account": a.pf_account,
					"debit_in_account_currency": flt(a.amount, 2),
					"cost_center": a.cost_center,
				},
			)
		je.append(
			"accounts",
			{
				"account": self.income_account,
				"credit_in_account_currency": total,
				"cost_center": self.income_cost_center,
			},
		)

		je.insert(ignore_permissions=True)
		je.submit()
		return je.name


@frappe.whitelist()
def create_sweep(window: str | None = None, sweep_date: str | None = None) -> str:
	"""Create a draft sweep proposal (no money moves) and return its name."""
	doc = frappe.new_doc("PF Sweep")
	if window:
		doc.assessment_window = window
	if sweep_date:
		doc.sweep_date = sweep_date
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def approve_sweep(name: str) -> str:
	"""Approve a draft sweep — posts the balanced Journal Entry. Money moves here."""
	doc = frappe.get_doc("PF Sweep", name)
	doc.submit()
	return doc.journal_entry


@frappe.whitelist()
def cancel_sweep(name: str) -> str:
	"""Cancel a posted sweep — reverses its Journal Entry."""
	doc = frappe.get_doc("PF Sweep", name)
	doc.cancel()
	return doc.name
