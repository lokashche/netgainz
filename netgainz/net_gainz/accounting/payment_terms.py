# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-10: turn a gym's plain-language payment policy into an ERPNext
Payment Terms Template — silently.

**D7 / "ERPNext is an engine, not a UI".** A gym owner configures two things on a
plan, in gym language::

    Payment due:        On joining | Within 7 days | By the 5th of next month
    Allow installments: No | 2 | 3 | 4 ... parts, every N days

Everything below is the machinery that turns that pair into a native
``Payment Terms Template`` (+ its ``Payment Terms Template Detail`` rows). The
owner never sees the template, never names it, and never opens Frappe Desk —
exactly as ``provisioning.py`` hides Customer / Item / Subscription Plan.

Design rules mirror provisioning.py: **idempotent** (a deterministic name means
the same policy always resolves to the same template), **best-effort** (a policy
that cannot be expressed returns ``None`` rather than blocking a plan save), and
``ignore_permissions=True``.

Two things ERPNext enforces that shape the code:
  * ``invoice_portion`` across the rows must total **exactly 100** — so portions
    are computed, never hand-entered;
  * the resulting ``payment_schedule`` on an invoice must total the grand total —
    so **D6 rounding** puts clean numbers on the early rows and lets the LAST row
    absorb the remainder (see :func:`split_amounts`).
"""

import frappe
from frappe.utils import flt

from netgainz.net_gainz.profit_first import calc

# --------------------------------------------------------------------------- #
# the gym-language due rules (D4/D7: these three are what the owner picks from)
# --------------------------------------------------------------------------- #
DUE_ON_JOINING = "On joining"
DUE_IN_7_DAYS = "Within 7 days"
DUE_5TH_NEXT_MONTH = "By the 5th of next month"

DUE_RULES = {
	# label -> (due_date_based_on, credit_days, credit_months)
	DUE_ON_JOINING: ("Day(s) after invoice date", 0, 0),
	DUE_IN_7_DAYS: ("Day(s) after invoice date", 7, 0),
	DUE_5TH_NEXT_MONTH: ("Day(s) after the end of the invoice month", 5, 0),
}

# D6: installment amounts round to clean numbers. ₹10,000 in 3 -> 3,400/3,300/3,300.
ROUNDING_UNIT = 100.0
MAX_INSTALLMENTS = 12


# --------------------------------------------------------------------------- #
# D6 rounding
# --------------------------------------------------------------------------- #
def split_amounts(total, parts: int) -> list[float]:
	"""Split ``total`` into ``parts`` clean-number installments that sum EXACTLY.

	Every row is the per-part amount rounded to the nearest :data:`ROUNDING_UNIT`,
	and the **first** row absorbs the remainder — so the gym collects the odd money
	earliest and the member's final installment is never a surprise.
	₹10,000 in 3 -> ``[3400.0, 3300.0, 3300.0]``.

	The exact total is load-bearing: ERPNext rejects a payment schedule that does
	not tie back to the invoice's grand total. When rounding cannot work (a fee
	smaller than the rounding unit, or many parts), this falls back to a plain even
	split so no row is ever zero or negative.
	"""
	total = flt(total)
	if parts < 1:
		raise ValueError(f"parts must be >= 1; got {parts!r}")
	if parts == 1:
		return [total]

	even = total / parts
	# round_half_away keeps this deterministic across sites (calc is the single
	# rounding primitive — never Python's banker's round()).
	base = flt(ROUNDING_UNIT * calc.round_half_away(even / ROUNDING_UNIT))
	first = flt(total - base * (parts - 1))
	if base <= 0 or first <= 0:
		base = flt(even, 2)
		first = flt(total - base * (parts - 1))
	return [first, *([base] * (parts - 1))]


def split_portions(parts: int) -> list[float]:
	"""Percentage portions for ``parts`` installments, totalling exactly 100.

	ERPNext validates the sum, and 100/3 is not representable — so the remainder
	rides on the FIRST row (collect marginally more, earlier) and the rest are
	equal. 3 -> ``[33.34, 33.33, 33.33]``.
	"""
	if parts < 1:
		raise ValueError(f"parts must be >= 1; got {parts!r}")
	if parts == 1:
		return [100.0]
	each = flt(100.0 / parts, 2)
	first = flt(100.0 - each * (parts - 1), 2)
	return [first, *([each] * (parts - 1))]


# --------------------------------------------------------------------------- #
# policy -> Payment Terms Template
# --------------------------------------------------------------------------- #
def template_name(due_rule: str, parts: int, gap_days: int) -> str:
	"""Deterministic, human-readable name. Same policy -> same template, always.

	Prefixed so it is obvious in Desk (support/superadmin only) that these are
	generated, not hand-authored.
	"""
	if parts <= 1:
		return f"NetGainz: {due_rule}"
	return f"NetGainz: {due_rule}, {parts} parts every {gap_days}d"


def ensure_payment_term(name, portion, based_on, credit_days, credit_months) -> str:
	"""Find-or-create one named Payment Term. Idempotent by name.

	Real Payment Term records (rather than bare template rows) are required for
	two reasons: ``allocate_payment_based_on_payment_terms`` makes ``payment_term``
	mandatory on every template row, and a Payment Entry Reference can only be
	attributed to a specific installment via its ``payment_term`` link — which is
	what lets WP-10.5 settle the OLDEST obligation first.
	"""
	if frappe.db.exists("Payment Term", name):
		return name
	term = frappe.new_doc("Payment Term")
	term.payment_term_name = name
	term.invoice_portion = portion
	term.due_date_based_on = based_on
	term.credit_days = credit_days
	term.credit_months = credit_months
	term.insert(ignore_permissions=True)
	return term.name


def _row_specs(due_rule: str, parts: int, gap_days: int) -> list[tuple]:
	"""(portion, due_date_based_on, credit_days, credit_months) per installment.

	The FIRST installment carries the gym's chosen due rule verbatim; each later
	one falls ``gap_days`` after the previous. A month-end-based rule only makes
	sense for the first row, so later rows always count plain days after the
	invoice date.
	"""
	based_on, credit_days, credit_months = DUE_RULES[due_rule]
	specs = []
	for index, portion in enumerate(split_portions(parts)):
		if index == 0:
			specs.append((portion, based_on, credit_days, credit_months))
		else:
			offset = _first_row_offset_days(based_on, credit_days) + gap_days * index
			specs.append((portion, "Day(s) after invoice date", offset, 0))
	return specs


def ensure_template(due_rule: str, parts: int = 1, gap_days: int = 30) -> str | None:
	"""Find-or-create the Payment Terms Template for a policy; return its name.

	Returns ``None`` for an unknown due rule (best-effort — never block a save).
	Idempotent: the deterministic name means repeated calls reuse one template.
	"""
	if due_rule not in DUE_RULES:
		return None
	parts = max(1, int(parts or 1))
	if parts > MAX_INSTALLMENTS:
		frappe.throw(f"At most {MAX_INSTALLMENTS} installments are supported (got {parts}).")
	# ERPNext rejects a template whose rows share
	# (payment_term, credit_days, credit_months, due_date_based_on) — with no gap
	# every installment would collapse onto the same due date anyway.
	gap_days = int(gap_days or 0)
	if parts > 1 and gap_days < 1:
		frappe.throw("Installments must be at least 1 day apart.")

	name = template_name(due_rule, parts, gap_days)
	if frappe.db.exists("Payment Terms Template", name):
		return name

	template = frappe.new_doc("Payment Terms Template")
	template.template_name = name
	# Lets ERPNext track paid/outstanding PER installment on the invoice's
	# payment_schedule, and lets a Payment Entry name the installment it settles.
	template.allocate_payment_based_on_payment_terms = 1
	for index, (portion, based_on, days, months) in enumerate(
		_row_specs(due_rule, parts, gap_days)
	):
		term_name = f"{name} — part {index + 1}" if parts > 1 else name
		template.append(
			"terms",
			{
				"payment_term": ensure_payment_term(term_name, portion, based_on, days, months),
				"invoice_portion": portion,
				"due_date_based_on": based_on,
				"credit_days": days,
				"credit_months": months,
			},
		)
	template.insert(ignore_permissions=True)
	return template.name


def _first_row_offset_days(based_on: str, credit_days: int) -> int:
	"""Approximate day-offset of the FIRST installment, used to space later ones.

	A month-end-based first row has no exact day offset until the invoice date is
	known, so later installments are spaced from a nominal month (30d) plus its
	credit days. Only affects the gap between installments, never the first row's
	own (exact) due date.
	"""
	if based_on == "Day(s) after invoice date":
		return int(credit_days or 0)
	return 30 + int(credit_days or 0)


# --------------------------------------------------------------------------- #
# resolution: membership override -> plan default -> tenant fallback
# --------------------------------------------------------------------------- #
def resolve_for_membership(membership) -> str | None:
	"""The Payment Terms Template that governs ``membership`` (D2).

	Order: the membership's own override, then its plan's default, then None —
	in which case billing falls back to the tenant-wide
	``Business Settings.days_until_due`` single-row behaviour.
	"""
	own = membership.get("payment_terms_template")
	if own and frappe.db.exists("Payment Terms Template", own):
		return own
	plan = membership.get("membership_plan")
	if not plan:
		return None
	plan_template = frappe.db.get_value("Membership Plan", plan, "payment_terms_template")
	if plan_template and frappe.db.exists("Payment Terms Template", plan_template):
		return plan_template
	return None


def sync_plan_template(plan) -> str | None:
	"""Regenerate a Membership Plan's system-managed ``payment_terms_template``
	from its owner-facing policy fields. Called from the plan controller."""
	due_rule = plan.get("payment_due_rule") or DUE_ON_JOINING
	parts = int(plan.get("installment_count") or 1)
	gap_days = int(plan.get("installment_gap_days") or 30)
	template = ensure_template(due_rule, parts, gap_days)
	if template and plan.get("payment_terms_template") != template:
		plan.payment_terms_template = template
	return template
