# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Expenses that repeat — actually raising them.

``Expense`` has carried ``is_recurring`` and ``frequency`` since WP-5, and nothing
read them. An owner could tick "this repeats monthly" on the rent, and the app would
remember the tick and do nothing with it — so every month the rent had to be typed in
again, and the month it was forgotten simply vanished from the books.

**Raised as a DRAFT, never submitted.** This is the PF Sweep precedent, and it is the
right one: an expense that posts to the ledger without a human having looked is a
liability. Rent is the same every month, but electricity is not, and a repeating
expense that quietly posts last month's electricity bill is worse than one that does
nothing. The owner opens the draft, corrects the amount, submits.

**How a repeat is not raised twice.** The expense the owner ticked is the *root*; every
copy points back to it through ``recurred_from`` and is itself not marked repeating. So
the chain is ``root + its children``, the last date in that chain is where the series
has got to, and the next one is due a frequency after it. Re-running the job finds
nothing new, which is what makes it safe to run daily and safe to run twice.

**Catch-up is capped.** A gym that has not opened the app for eight months should not
be handed eight drafts at once — it should be handed the ones that matter and told the
rest were skipped. :data:`MAX_CATCH_UP` is that cap.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_months, getdate, today

#: How many missed periods a single run will raise before giving up on the backlog.
MAX_CATCH_UP = 3

#: frequency label -> months to step forward
STEP_MONTHS = {"Monthly": 1, "Quarterly": 3, "Annually": 12}


def _next_date(last, frequency: str):
	months = STEP_MONTHS.get(frequency)
	if not months:
		return None
	return getdate(add_months(getdate(last), months))


def _chain_latest(root: str):
	"""The most recent date in this repeating series, root included."""
	dates = [frappe.db.get_value("Expense", root, "date")]
	dates += frappe.get_all("Expense", filters={"recurred_from": root}, pluck="date")
	return max(getdate(d) for d in dates if d)


def due_repeats(as_of=None) -> list[dict]:
	"""Every repeating expense that is behind, and the dates it is missing.

	Read-only. One entry per root, carrying the dates that would be raised.
	"""
	ref = getdate(as_of or today())
	out: list[dict] = []

	roots = frappe.get_all(
		"Expense",
		filters={"is_recurring": 1, "docstatus": ["!=", 2], "frequency": ["!=", ""]},
		fields=["name", "category", "amount", "frequency", "vendor", "date"],
	)
	for root in roots:
		latest = _chain_latest(root.name)
		wanted, cursor, skipped = [], latest, 0
		while True:
			cursor = _next_date(cursor, root.frequency)
			if not cursor or cursor > ref:
				break
			if len(wanted) >= MAX_CATCH_UP:
				skipped += 1
				continue
			wanted.append(str(cursor))
		if wanted or skipped:
			out.append(
				{
					"root": root.name,
					"category": root.category,
					"amount": root.amount,
					"vendor": root.vendor,
					"frequency": root.frequency,
					"last_raised": str(latest),
					"due": wanted,
					"skipped": skipped,
				}
			)
	return out


def _copy(root_name: str, when: str) -> str:
	root = frappe.get_doc("Expense", root_name)
	doc = frappe.new_doc("Expense")
	for field in ("category", "amount", "payment_mode", "vendor", "branch", "company", "notes"):
		doc.set(field, root.get(field))
	doc.date = when
	# The copy is NOT itself marked repeating: the root owns the series, so a copy
	# can never start a second one and the chain stays a single line.
	doc.is_recurring = 0
	doc.frequency = ""
	doc.recurred_from = root_name
	note = _("Raised automatically because {0} repeats {1}.").format(
		root_name, (root.frequency or "").lower()
	)
	doc.notes = f"{doc.notes}\n{note}" if doc.notes else note
	doc.insert(ignore_permissions=True)  # left as a draft on purpose
	return doc.name


def generate_recurring_expenses(as_of=None) -> dict:
	"""Daily scheduler hook: raise the drafts a repeating expense is behind on.

	Idempotent — the chain records what has already been raised, so a second run the
	same day creates nothing. Opt-out via ``recurring_expenses_enabled``.
	"""
	if not frappe.db.get_single_value("Business Settings", "recurring_expenses_enabled"):
		return {"created": 0, "skipped": 0}

	created, skipped, names = 0, 0, []
	for row in due_repeats(as_of):
		skipped += row["skipped"]
		for when in row["due"]:
			try:
				names.append(_copy(row["root"], when))
				created += 1
			except Exception:
				# One bad expense must not stop the rest of the gym's costs appearing.
				frappe.log_error(
					title="Repeating expense could not be raised",
					message=f"root={row['root']} date={when}\n{frappe.get_traceback()}",
				)
	if created:
		frappe.db.commit()
	return {"created": created, "skipped": skipped, "expenses": names}


@frappe.whitelist()
def get_repeating(as_of=None) -> dict:
	"""Owner/BFF: what repeats, and what is waiting to be raised."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	rows = due_repeats(as_of)
	return {
		"rows": rows,
		"due_now": sum(len(r["due"]) for r in rows),
		"max_catch_up": MAX_CATCH_UP,
	}


@frappe.whitelist()
def run_now(as_of=None) -> dict:
	"""Owner/BFF: raise the waiting drafts now rather than waiting for tonight."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return generate_recurring_expenses(as_of)
