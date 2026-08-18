# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-10: turn a gym's plain-language payment policy into an ERPNext
Payment Terms Template — silently.

**D7 / "ERPNext is an engine, not a UI".** A gym owner configures two things on a
plan, in gym language::

    Payment due:        On joining | Within 7 days | By the 5th of next month
    Allow installments: No | 2 | 3 | 4 ... parts
    Collect a part:     every N days | weeks | months

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
from frappe.utils import add_days, add_months, flt, getdate

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

# --------------------------------------------------------------------------- #
# how far apart the parts fall (the gym picks the unit, not just the number)
# --------------------------------------------------------------------------- #
# A gym does not think in days. "Half now, half next month" is the deal struck at
# the desk; expressing it as 30 days is a different promise, because 30 days from
# the 31st of January is the 2nd of March and every renewal drifts further. So the
# gap carries a UNIT, and MONTHS means the calendar month — same day, next month,
# clamped to the month's last day when that day does not exist.
GAP_DAYS = "Days"
GAP_WEEKS = "Weeks"
GAP_MONTHS = "Months"
GAP_UNITS = (GAP_DAYS, GAP_WEEKS, GAP_MONTHS)

# Nominal day-length of one unit. Used ONLY to space the generated Payment Terms
# Template rows far enough apart that ERPNext accepts them as distinct; the real
# due dates are computed by :func:`part_due_dates` and written onto the invoice.
_NOMINAL_DAYS = {GAP_DAYS: 1, GAP_WEEKS: 7, GAP_MONTHS: 30}

# D6: installment amounts round to clean numbers. ₹10,000 in 3 -> 3,400/3,300/3,300.
ROUNDING_UNIT = 100.0
MAX_INSTALLMENTS = 12


def normalise_unit(unit: str | None) -> str:
	"""Any unknown / empty unit means Days — the behaviour before units existed."""
	return unit if unit in GAP_UNITS else GAP_DAYS


def gap_nominal_days(gap: int, unit: str | None) -> int:
	"""Approximate day-length of one gap. Spacing only — never a real due date."""
	return int(gap or 0) * _NOMINAL_DAYS[normalise_unit(unit)]


def part_due_dates(first_due, parts: int, gap: int, unit: str | None = GAP_DAYS) -> list:
	"""**When each part actually falls**, given when the FIRST part is due.

	The single source of truth for installment timing. Every later part is measured
	from the first part's real due date, not from the invoice date — so a policy
	like "by the 5th of next month, then monthly" lands on the 5th every time
	instead of drifting by whatever the first row's offset happened to be.

	``Months`` uses :func:`frappe.utils.add_months`, which walks the calendar and
	clamps: a member who joins on the 31st of January owes part two on the 28th of
	February, not the 2nd of March.
	"""
	first = getdate(first_due)
	parts = max(1, int(parts or 1))
	gap = int(gap or 0)
	unit = normalise_unit(unit)
	dates = [first]
	for index in range(1, parts):
		if unit == GAP_MONTHS:
			dates.append(getdate(add_months(first, gap * index)))
		elif unit == GAP_WEEKS:
			dates.append(getdate(add_days(first, gap * 7 * index)))
		else:
			dates.append(getdate(add_days(first, gap * index)))
	return dates


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
def template_name(due_rule: str, parts: int, gap: int, unit: str | None = GAP_DAYS) -> str:
	"""Deterministic, human-readable name. Same policy -> same template, always.

	Prefixed so it is obvious in Desk (support/superadmin only) that these are
	generated, not hand-authored.

	A Days gap keeps its original ``...every 30d`` spelling on purpose: every plan
	written before units existed is a Days plan, and changing the name would strand
	them on an orphaned template and generate a duplicate for the same policy.
	"""
	if parts <= 1:
		return f"NetGainz: {due_rule}"
	unit = normalise_unit(unit)
	if unit == GAP_DAYS:
		return f"NetGainz: {due_rule}, {parts} parts every {gap}d"
	return f"NetGainz: {due_rule}, {parts} parts {describe_gap(gap, unit)}"


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


def _row_specs(due_rule: str, parts: int, gap: int, unit: str | None) -> list[tuple]:
	"""(portion, due_date_based_on, credit_days, credit_months) per installment.

	The FIRST installment carries the gym's chosen due rule verbatim; each later one
	is spaced by the gap's NOMINAL day-length. A month-end-based rule only makes
	sense for the first row, so later rows always count plain days after the invoice
	date.

	These template dates are a fallback, not the promise. ERPNext builds the
	schedule from them and ``billing.on_sales_invoice_validate`` then restates each
	row's due date from :func:`part_due_dates`, which walks the real calendar. The
	template only has to place the rows in the right order and keep them distinct —
	ERPNext rejects two rows sharing (term, credit_days, credit_months, based_on).
	"""
	based_on, credit_days, credit_months = DUE_RULES[due_rule]
	step = gap_nominal_days(gap, unit)
	specs = []
	for index, portion in enumerate(split_portions(parts)):
		if index == 0:
			specs.append((portion, based_on, credit_days, credit_months))
		else:
			offset = _first_row_offset_days(based_on, credit_days) + step * index
			specs.append((portion, "Day(s) after invoice date", offset, 0))
	return specs


def ensure_template(due_rule: str, parts: int = 1, gap: int = 30, unit: str | None = GAP_DAYS) -> str | None:
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
	gap = int(gap or 0)
	unit = normalise_unit(unit)
	if parts > 1 and gap < 1:
		frappe.throw(f"Installments must be at least 1 {unit.lower().rstrip('s')} apart.")

	name = template_name(due_rule, parts, gap, unit)
	if frappe.db.exists("Payment Terms Template", name):
		return name

	template = frappe.new_doc("Payment Terms Template")
	template.template_name = name
	# Lets ERPNext track paid/outstanding PER installment on the invoice's
	# payment_schedule, and lets a Payment Entry name the installment it settles.
	template.allocate_payment_based_on_payment_terms = 1
	for index, (portion, based_on, days, months) in enumerate(_row_specs(due_rule, parts, gap, unit)):
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


def resolve_policy(membership) -> "frappe._dict":
	"""**Whose payment policy is in force for this membership** — and what it says.

	A member's own setting wins field by field; anything they leave blank falls back
	to the plan; anything the plan leaves blank falls back to the built-in default.
	One function, so the membership controller, the invoice hook and the owner's
	screen can never disagree about which policy applies.
	"""
	plan_name = membership.get("membership_plan")
	plan = (
		frappe.db.get_value(
			"Membership Plan",
			plan_name,
			[
				"payment_due_rule",
				"installment_count",
				"installment_gap_days",
				"installment_gap_unit",
			],
			as_dict=True,
		)
		if plan_name
		else None
	) or frappe._dict()

	return frappe._dict(
		plan=plan_name,
		uses_own_terms=bool(
			membership.get("payment_due_rule") or int(membership.get("installment_count") or 0) > 1
		),
		due_rule=membership.get("payment_due_rule") or plan.get("payment_due_rule") or DUE_ON_JOINING,
		parts=int(membership.get("installment_count") or 0) or int(plan.get("installment_count") or 1),
		gap=int(membership.get("installment_gap_days") or 0) or int(plan.get("installment_gap_days") or 30),
		unit=normalise_unit(membership.get("installment_gap_unit") or plan.get("installment_gap_unit")),
		plan_due_rule=plan.get("payment_due_rule"),
		plan_parts=plan.get("installment_count"),
		plan_gap=plan.get("installment_gap_days"),
		plan_unit=plan.get("installment_gap_unit"),
	)


def sync_plan_template(plan) -> str | None:
	"""Regenerate a Membership Plan's system-managed ``payment_terms_template``
	from its owner-facing policy fields. Called from the plan controller."""
	due_rule = plan.get("payment_due_rule") or DUE_ON_JOINING
	parts = int(plan.get("installment_count") or 1)
	gap = int(plan.get("installment_gap_days") or 30)
	unit = normalise_unit(plan.get("installment_gap_unit"))
	template = ensure_template(due_rule, parts, gap, unit)
	if template and plan.get("payment_terms_template") != template:
		plan.payment_terms_template = template
	return template


# --------------------------------------------------------------------------- #
# owner-facing: describing and changing a member's terms
# --------------------------------------------------------------------------- #
def describe_gap(gap: int | None, unit: str | None) -> str:
	"""\"every month\" / \"every 4 weeks\" / \"every 45 days\" — never \"gap_days=45\"."""
	gap = int(gap or 0)
	if gap < 1:
		return ""
	unit = normalise_unit(unit)
	singular = {GAP_DAYS: "day", GAP_WEEKS: "week", GAP_MONTHS: "month"}[unit]
	if gap == 1:
		return f"every {singular}"
	return f"every {gap} {singular}s"


def describe(
	due_rule: str | None,
	parts: int | None,
	gap_days: int | None,
	gap_unit: str | None = GAP_DAYS,
) -> str:
	"""The policy in the words a gym owner would use.

	The owner never sees a Payment Terms Template, so this is the only place the
	policy is ever spelled out to them.
	"""
	parts = max(1, int(parts or 1))
	rule = due_rule or DUE_ON_JOINING
	if parts == 1:
		return {
			DUE_ON_JOINING: "Pays in full when they join",
			DUE_IN_7_DAYS: "Pays in full within 7 days",
			DUE_5TH_NEXT_MONTH: "Pays in full by the 5th of next month",
		}.get(rule, "Pays in full")
	when = {
		DUE_ON_JOINING: "starting when they join",
		DUE_IN_7_DAYS: "starting within 7 days",
		DUE_5TH_NEXT_MONTH: "starting by the 5th of next month",
	}.get(rule, "")
	every = describe_gap(gap_days, gap_unit)
	return " ".join(x for x in (f"Pays in {parts} parts", every, when) if x)


@frappe.whitelist()
def get_membership_terms(membership) -> dict:
	"""Owner/BFF: this member's payment terms, and the plan default behind them."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	ms = frappe.get_doc("Membership", membership)
	policy = resolve_policy(ms)

	return {
		"membership": ms.name,
		"uses_own_terms": policy.uses_own_terms,
		"payment_due_rule": policy.due_rule,
		"installment_count": policy.parts,
		"installment_gap_days": policy.gap,
		"installment_gap_unit": policy.unit,
		"summary": describe(policy.due_rule, policy.parts, policy.gap, policy.unit),
		"plan": ms.membership_plan,
		"plan_summary": describe(policy.plan_due_rule, policy.plan_parts, policy.plan_gap, policy.plan_unit),
		"due_rules": list(DUE_RULES),
		"gap_units": list(GAP_UNITS),
		"max_installments": MAX_INSTALLMENTS,
	}


@frappe.whitelist()
def set_membership_terms(
	membership,
	payment_due_rule=None,
	installment_count=None,
	installment_gap_days=None,
	installment_gap_unit=None,
) -> dict:
	"""Owner/BFF: give ONE member their own payment terms, or send them back to
	the plan's.

	**Applies to the next invoice, not one already raised.** ERPNext marks a Sales
	Invoice's ``payment_schedule`` and ``payment_terms_template``
	``allow_on_submit = 0``, so a submitted invoice's instalments cannot be
	restated -- and rightly so, because money may already be allocated against
	those rows. Pass no values to clear the override and follow the plan again.
	"""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	ms = frappe.get_doc("Membership", membership)

	parts = int(installment_count or 0)
	if parts and parts > MAX_INSTALLMENTS:
		frappe.throw(f"At most {MAX_INSTALLMENTS} parts are supported (got {parts}).")
	if payment_due_rule and payment_due_rule not in DUE_RULES:
		frappe.throw(f"Unknown payment due rule {payment_due_rule!r}.")
	if installment_gap_unit and installment_gap_unit not in GAP_UNITS:
		frappe.throw(f"Unknown gap unit {installment_gap_unit!r}.")

	ms.payment_due_rule = payment_due_rule or None
	ms.installment_count = parts or 0
	ms.installment_gap_days = int(installment_gap_days or 0) or 0
	# Blank means "follow the plan", exactly as the count and the due rule do.
	ms.installment_gap_unit = installment_gap_unit or None
	ms.save(ignore_permissions=True)
	frappe.db.commit()
	return get_membership_terms(ms.name)
