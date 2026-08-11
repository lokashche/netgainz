# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 7 WP-4: real billing on ERPNext Sales Invoices + Payment Entries.

Each membership drives ONE native ERPNext Subscription (prepaid: an invoice is
generated at the start of each period); each collection is a Payment Entry against
that period's Sales Invoice. Profit First and commissions then read COLLECTED CASH
from Payment Entries, never from the invoice (cash basis), via the single shared
read :func:`membership_collected_paise`.

**WP-11 (fresh-start): ERPNext billing is ON for every membership, always.** There
was never any production data — no tenant ever set a cut-over date, and no Sales
Invoice, Payment Entry or Subscription was ever created — so the date-gated
cut-over and its dual cash read (legacy ``fee_collected`` + Payment Entries) were
deleted rather than migrated. One path, one source of truth: cash is what a
submitted Payment Entry allocated to a subscription-generated Sales Invoice.
``Membership.fee_collected`` / ``tariff`` survive only as deprecated display
fields and feed NO calculation; payments post exclusively through
:func:`record_payment`.

Design conventions mirror provisioning.py / payment_modes.py: idempotent,
best-effort (skip — never block the save — when a prerequisite is missing),
``ignore_permissions=True``, and reuse of the existing helpers
(``pf_accounts.default_company``, ``branch.branch_cost_center``,
``payment_modes.paid_to_account``, ``period_lock.assert_postable``,
``calc.to_paise``/``to_rupees``).
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, today

from netgainz.net_gainz.accounting import (
	billing_intervals,
	branch,
	currency,
	payment_modes,
	period_lock,
	provisioning,
)
from netgainz.net_gainz.profit_first import accounts as pf_accounts
from netgainz.net_gainz.profit_first import calc

GENERATE_INVOICE_AT = "Beginning of the current subscription period"  # prepaid


# --------------------------------------------------------------------------- #
# config / helpers
# --------------------------------------------------------------------------- #
def _as_doc(doctype, ref) -> Document:
	return ref if isinstance(ref, Document) else frappe.get_doc(doctype, ref)


def _company(company=None):
	return company or pf_accounts.default_company()


# --------------------------------------------------------------------------- #
# Membership -> native Subscription -> Sales Invoice
# --------------------------------------------------------------------------- #
def cycle_start(member, subscription_plan) -> object:
	"""WP-10.0: the billing cycle's anchor date for ``member``.

	Dues fall on the member's JOINING day — a member who joined on the 15th is
	billed on the 15th — instead of drifting to whenever their first payment
	happened to land (the defect this fixes: ``next_renewal`` used to be
	``paid_date + duration``, so paying 10 days late bought 10 free days, every
	cycle, forever).

	Returns the CURRENT period's start rather than the joining date itself, so
	enrolling a member who joined months ago cannot make the native daily
	``Process Subscription`` scheduler back-bill every elapsed period. Falls back
	to today when the member has no joining date or the plan has no interval.
	"""
	today_ = getdate(today())
	joining = frappe.db.get_value("Member", member, "date_of_joining") if member else None
	if not joining:
		return today_
	interval, count = frappe.db.get_value(
		"Subscription Plan", subscription_plan, ["billing_interval", "billing_interval_count"]
	) or (None, None)
	if not interval:
		return today_
	return billing_intervals.latest_cycle_start(
		getdate(joining), interval, int(count or 1), today_
	)


def ensure_subscription(membership, company=None) -> str | None:
	"""Idempotently create the native ERPNext Subscription for a membership and
	link it back. Returns its name, or None if a prerequisite is missing."""
	membership = _as_doc("Membership", membership)
	if membership.get("subscription") and frappe.db.exists("Subscription", membership.subscription):
		return membership.subscription

	company = _company(company)
	if not company or not membership.get("member") or not membership.get("membership_plan"):
		return None

	customer = frappe.db.get_value("Member", membership.member, "customer") or provisioning.provision_customer(
		membership.member, company
	)
	if not customer:
		return None
	# WP-8: one transaction currency per tenant. A Customer with a foreign default
	# currency would make ERPNext raise this membership's invoices in that currency
	# — which the owner app renders unlabelled next to rupee totals, and which the
	# paise quantisation is not defined for.
	currency.assert_paise_safe(company)
	currency.assert_membership_billing_currency(customer, company)
	sub_plan = frappe.db.get_value(
		"Membership Plan", membership.membership_plan, "subscription_plan"
	) or provisioning.provision_subscription_plan(membership.membership_plan, company)
	if not sub_plan:
		return None
	# No resolvable price -> no Subscription, so neither the owner nor the daily
	# Process Subscription scheduler can raise a Rs.0 invoice for this member. The
	# membership still enrols; it surfaces in `unbillable_memberships()` until a
	# price is set, and billing starts on the next generate.
	if not is_billable(membership):
		return None

	start = cycle_start(membership.member, sub_plan)

	sub = frappe.new_doc("Subscription")
	sub.party_type = "Customer"
	sub.party = customer
	sub.company = company
	sub.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	sub.start_date = start
	sub.generate_invoice_at = GENERATE_INVOICE_AT
	sub.submit_invoice = 1
	sub.days_until_due = frappe.db.get_single_value("Business Settings", "days_until_due") or 0
	sub.append("plans", {"plan": sub_plan, "qty": 1})
	sub.insert(ignore_permissions=True)

	membership.db_set("subscription", sub.name, update_modified=False)
	return sub.name


# WP-8: a credit note is a Sales Invoice too, and `make_return_doc` COPIES the
# `subscription` link onto it (the field is not no_copy — traced 2026-08-08). That
# copy is deliberate and load-bearing for the cash read, but it means every
# subscription-keyed lookup of "the membership's invoice" must exclude returns, or
# a refund silently becomes the current period's invoice: `current_sales_invoice`
# re-points at the credit note and `open_obligations` reports a NEGATIVE amount
# owing. Anything reading invoices BY SUBSCRIPTION filters on this.
NOT_A_CREDIT_NOTE = {"is_return": 0}


def _latest_invoice(subscription_name) -> str | None:
	return frappe.db.get_value(
		"Sales Invoice",
		{"subscription": subscription_name, "docstatus": ["!=", 2], **NOT_A_CREDIT_NOTE},
		"name",
		order_by="creation desc",
	)


def current_invoice(membership) -> str | None:
	"""The Sales Invoice a membership's money currently moves against.

	The subscription's latest real invoice, falling back to the stored pointer.
	Shared by the payment, refund and write-off paths so all three always act on
	the same document.
	"""
	membership = _as_doc("Membership", membership)
	si_name = _latest_invoice(membership.subscription) if membership.get("subscription") else None
	return si_name or membership.get("current_sales_invoice")


def force_generate_invoice(membership, posting_date=None) -> str | None:
	"""Generate the current period's Sales Invoice now (the prepaid first invoice,
	or an owner-triggered catch-up). Uses native ``Subscription.process`` so it
	dedupes per period; links the resulting invoice back to the membership."""
	membership = _as_doc("Membership", membership)
	sub_name = membership.get("subscription")
	if not sub_name or not frappe.db.exists("Subscription", sub_name):
		return None
	sub = frappe.get_doc("Subscription", sub_name)
	# ERPNext only generates a "Beginning of the current subscription period"
	# invoice when the posting date IS that period's start
	# (Subscription.can_generate_new_invoice). WP-10.0 anchors the cycle on the
	# member's joining day, so a member enrolling mid-cycle has a period start in
	# the PAST — posting "today" would silently raise nothing. Default to the
	# period start so the current period is always billed.
	when = getdate(posting_date) if posting_date else getdate(sub.current_invoice_start or today())
	sub.process(when)
	invoice = _latest_invoice(sub_name)
	if invoice:
		membership.db_set("current_sales_invoice", invoice, update_modified=False)
	return invoice


def on_membership_insert(doc, method=None):
	"""``after_insert`` doc_event: stand up the Subscription and bill the first
	(prepaid) period. Best-effort — never blocks the membership save (a billing
	hiccup must not fail member enrolment; the owner can retry via
	generate_membership_invoice)."""
	if frappe.flags.in_install:
		return
	# Backfill: a historical row loaded from the gym's own records already has its
	# Sales Invoice and Payment Entry, so provisioning here would raise a SECOND,
	# submitted invoice priced from Membership Plan.amount -- a figure that cannot
	# be right for a tenant who prices per member -- and double-count the period.
	#
	# This is a field on the row, deliberately NOT `frappe.flags.in_import`: that
	# flag is also set while importing DocType JSON (migrate/install) and
	# `modules/import_file.py` sets it with no try/finally, so a raise anywhere in
	# that path leaves it stuck on and silently disables billing for the rest of
	# the process. CI caught exactly that. A field is explicit, survives, and shows
	# on the record why no invoice was raised.
	if doc.get("is_backfill"):
		return
	try:
		if ensure_subscription(doc):
			force_generate_invoice(doc)
			sync_derived_fields(doc)
	except Exception:
		frappe.log_error(title=f"WP-4 billing provisioning failed for membership {doc.name}")


def _membership_for_invoice(doc):
	"""The Membership behind a subscription-generated Sales Invoice, or None."""
	if not doc.get("subscription"):
		return None
	name = frappe.db.get_value("Membership", {"subscription": doc.subscription}, "name")
	return frappe.get_doc("Membership", name) if name else None


def on_sales_invoice_before_validate(doc, method=None):
	"""WP-10.3 (Mode A): put the membership's payment terms on the invoice.

	ERPNext's native Subscription hardcodes a SINGLE 100% ``payment_schedule`` row
	from ``days_until_due`` (subscription.py ``create_invoice``) and has no
	``payment_terms_template`` field of its own — and
	``accounts_controller.set_payment_schedule`` only builds from a template when
	the schedule is EMPTY. So the schedule the Subscription pre-seeded is cleared
	here and the resolved template attached, letting ERPNext build the real
	installment rows during validate.

	Pay-as-you-go is skipped: there, each installment is already its own invoice,
	so a single due date per invoice is correct.
	"""
	if frappe.flags.in_install or not doc.get("subscription") or doc.get("is_return"):
		return
	# A go-live part-month invoice is priced pro-rata by go_live.py and carries a
	# single due date on purpose. This hook exists to price a FULL period and to
	# attach installment terms; both would be wrong here.
	if doc.flags.get("netgainz_part_month"):
		return
	membership = _membership_for_invoice(doc)
	if not membership:
		return

	_apply_membership_price(doc, membership)

	if billing_mode(membership) == PAY_AS_YOU_GO:
		return
	template = membership.get("payment_terms_template")
	if not template or not frappe.db.exists("Payment Terms Template", template):
		return
	doc.payment_terms_template = template
	doc.ignore_default_payment_terms_template = 1
	doc.payment_schedule = []


def _apply_membership_price(doc, membership) -> None:
	"""Price the generated invoice at what THIS member actually pays.

	The native Subscription prices its line from the Subscription Plan — one price
	for every member on the plan — which is wrong for a gym: the pilot's 64 monthly
	members pay 18 different amounts. Overriding the rate here is the smallest
	correct seam, and the only one that works:

	* **A per-customer Item Price does NOT work.** ``get_plan_rate`` -> ``utilities
	  .product.get_price`` filters Item Price on ``item_code`` + ``price_list`` only
	  and returns ``price[0]``. Traced 2026-08-09: with both a generic row (1000)
	  and a row scoped to the customer (4321), the customer still priced at 1000 —
	  and because the pick is positional, a second row makes the generic price
	  arbitrary for *everyone*. Actively unsafe.
	* **A Subscription Plan per price** would work but bypasses Pricing Rules
	  (``Fixed Rate`` returns before them), which Stage 8 discounts need.

	Setting the rate before validate leaves ERPNext to do everything downstream from
	the corrected figure — GST on top, the payment schedule, and any Stage 8 Pricing
	Rule, which still runs during validate. Traced end to end: rate 3333 -> net_total
	3333, grand_total 3932.94, schedule 3933.

	The margin / discount fields are zeroed so ``set_missing_values`` cannot re-derive
	a rate from the price list behind us.
	"""
	price = membership_price(membership)
	# 0 means "no price anywhere", not "free": ensure_subscription refuses to
	# provision those, so reaching here with 0 means an older subscription. Leave
	# the plan price alone rather than silently invoicing nothing.
	if price <= 0:
		return
	items = doc.get("items") or []
	if len(items) != 1:
		# A membership subscription always carries exactly one plan line. Anything
		# else is not ours to price.
		return
	item = items[0]
	item.rate = price
	item.price_list_rate = price
	item.margin_rate_or_amount = 0
	item.margin_type = ""
	item.discount_percentage = 0
	item.discount_amount = 0


def on_sales_invoice_validate(doc, method=None):
	"""WP-10.3 (D6): restate the installment amounts as clean numbers.

	Runs AFTER the controller's own validate (frappe runs doc_event hooks after the
	class method), so ``set_payment_schedule`` has already produced percentage-derived
	amounts — 10,000 in 3 becomes 3,334 / 3,333 / 3,333. The owner asked for clean
	numbers instead: 3,400 / 3,300 / 3,300.

	``invoice_portion`` is zeroed on each row deliberately: on any later save
	``set_payment_schedule`` RE-derives ``payment_amount`` from the portion, which
	would silently undo this. With no portion it preserves the explicit amount.
	The split always totals the grand total, which ERPNext independently enforces.
	"""
	if frappe.flags.in_install or not doc.get("subscription") or doc.get("is_return"):
		return
	rows = doc.get("payment_schedule") or []
	if len(rows) < 2:
		return
	membership = _membership_for_invoice(doc)
	if not membership or billing_mode(membership) == PAY_AS_YOU_GO:
		return

	from netgainz.net_gainz.accounting import payment_terms

	total = flt(doc.get("rounded_total") or doc.grand_total)
	amounts = payment_terms.split_amounts(total, len(rows))
	conversion = flt(doc.get("conversion_rate")) or 1.0
	for row, amount in zip(rows, amounts, strict=True):
		row.invoice_portion = 0
		row.payment_amount = amount
		row.base_payment_amount = flt(amount * conversion)
		row.outstanding = amount
		row.base_outstanding = row.base_payment_amount


def on_sales_invoice_submit(doc, method=None):
	"""``on_submit`` doc_event for Sales Invoice: when the native daily Process
	Subscription scheduler bills a new membership period, re-point the membership's
	``current_sales_invoice`` at the freshly generated invoice, so renewal payments
	collect against the right SI and status reflects the current period.

	Credit notes are skipped (WP-8): a refund carries the same ``subscription`` link
	but is not a period to collect against.
	"""
	if frappe.flags.in_install or not doc.get("subscription") or doc.get("is_return"):
		return
	membership = frappe.db.get_value("Membership", {"subscription": doc.subscription}, "name")
	if not membership:
		return
	frappe.db.set_value("Membership", membership, "current_sales_invoice", doc.name, update_modified=False)
	# WP-8: a member who paid several periods up front should not read as Overdue
	# the moment the next one is billed. Best-effort; never blocks the invoice.
	from netgainz.net_gainz.accounting import advances

	advances.on_membership_invoice_submitted(membership)


# --------------------------------------------------------------------------- #
# payments -> Payment Entry
# --------------------------------------------------------------------------- #
def _allocate_oldest_first(pe, si_name, amount) -> None:
	"""WP-10.5: spend ``amount`` on the OLDEST unpaid installment first.

	When the invoice carries a payment schedule, ``get_payment_entry`` returns one
	reference row per installment (the template sets
	``allocate_payment_based_on_payment_terms``). A member paying part of what they
	owe must clear installment 1 before installment 2 — otherwise a part payment
	would be spread across every installment and none would ever read as settled,
	so nothing would show as overdue.

	Rows for other invoices are zeroed; each row's own outstanding caps what it can
	absorb, so the payment can never over-allocate.
	"""
	remaining = flt(amount)
	rows = [r for r in pe.references if r.reference_name == si_name]
	others = [r for r in pe.references if r.reference_name != si_name]
	for row in others:
		row.allocated_amount = 0

	# Oldest first: by due date, then by the schedule's own order.
	rows.sort(key=lambda r: (getdate(r.due_date) if r.get("due_date") else getdate(today()), r.idx))
	for row in rows:
		capacity = flt(row.get("payment_term_outstanding") or row.get("outstanding_amount") or 0)
		if capacity <= 0 or remaining <= 0:
			row.allocated_amount = 0
			continue
		take = min(capacity, remaining)
		row.allocated_amount = take
		remaining -= take

	# No schedule (a single obligation) -> the one row takes the whole payment.
	if remaining > 0 and len(rows) == 1:
		rows[0].allocated_amount = flt(amount)


def record_payment(
	membership,
	amount,
	payment_mode,
	posting_date,
	sales_invoice=None,
	reference_no=None,
	company=None,
	allow_advance=False,
) -> str:
	"""Record a member payment as a submitted Payment Entry against the membership's
	Sales Invoice. ``posting_date`` is REQUIRED (R3 — cash counts when collected).

	WP-8: a payment for MORE than this period's invoice is no longer rejected when
	``allow_advance`` is set. The invoice takes what it is owed and the excess stays
	on the Payment Entry as ``unallocated_amount`` — money on the member's account,
	not revenue, until a later period's invoice claims it (see accounting.advances
	for the recognition rule). Left off by default so a fat-fingered amount is still
	caught rather than quietly parked.
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	membership = _as_doc("Membership", membership)
	company = _company(company)
	if not company:
		frappe.throw("No default Company is set. Create or set a Company in ERPNext first.")
	currency.assert_paise_safe(company)
	if not posting_date:
		frappe.throw("A posting date is required to record a payment.")
	posting_date = getdate(posting_date)
	period_lock.assert_postable(posting_date, company)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw("Payment amount must be greater than zero.")

	# Prefer the subscription's latest OPEN invoice over a (possibly stale)
	# current_sales_invoice — the scheduler bills later periods without re-pointing
	# it, so a paid period-1 SI must not shadow an open period-2 SI on renewal.
	si_name = sales_invoice
	if not si_name and membership.get("subscription"):
		si_name = frappe.db.get_value(
			"Sales Invoice",
			{
				"subscription": membership.subscription,
				"docstatus": 1,
				"outstanding_amount": [">", 0],
				**NOT_A_CREDIT_NOTE,
			},
			"name",
			order_by="posting_date desc",
		)
	si_name = si_name or membership.get("current_sales_invoice")
	if not si_name or not frappe.db.exists("Sales Invoice", si_name):
		frappe.throw("No open Sales Invoice to record this payment against — generate the invoice first.")

	invoice = frappe.db.get_value(
		"Sales Invoice", si_name, ["outstanding_amount", "currency"], as_dict=True
	)
	currency.assert_company_currency(invoice.currency, company, what="invoice")
	outstanding = flt(invoice.outstanding_amount)
	if amount > outstanding and not allow_advance:
		frappe.throw(
			f"Payment {amount} exceeds the invoice outstanding {outstanding}. "
			"Record the extra as money on account if the member is paying ahead."
		)

	pe = get_payment_entry("Sales Invoice", si_name)
	pe.payment_type = "Receive"
	pe.posting_date = posting_date
	pe.reference_date = posting_date
	if payment_mode:
		pe.mode_of_payment = payment_mode
		pe.paid_to = payment_modes.paid_to_account(company, payment_mode)
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	if reference_no:
		pe.reference_no = reference_no
	# Allocate at most what is owed; ERPNext turns the rest into unallocated_amount.
	_allocate_oldest_first(pe, si_name, min(amount, outstanding))
	pe.insert(ignore_permissions=True)
	pe.submit()

	membership.db_set("current_sales_invoice", si_name, update_modified=False)
	return pe.name


# --------------------------------------------------------------------------- #
# derived membership state (R4: one source of truth = invoice outstanding)
# --------------------------------------------------------------------------- #
PAY_AS_YOU_GO = "Pay-as-you-go"


def installment_parts(membership) -> int:
	"""How many invoices a Pay-as-you-go period is split into (1 for Commitment)."""
	if billing_mode(membership) != PAY_AS_YOU_GO:
		return 1
	plan = membership.get("membership_plan")
	parts = int(membership.get("installment_count") or 0) or int(
		(plan and frappe.db.get_value("Membership Plan", plan, "installment_count")) or 1
	)
	return max(1, parts)


def membership_price(membership) -> float:
	"""**What THIS member pays**, per invoice, for their plan.

	A gym does not charge everyone on "Monthly" the same fee — the pilot has 64
	monthly members paying 18 different prices. A Membership Plan holds exactly one
	price, so the plan's amount is the *default*, not the truth.

	``Membership.tariff`` is that truth. The field already carried the right
	semantics — ``fetch_from: membership_plan.amount`` with ``fetch_if_empty``, so a
	blank price fills itself from the plan and an entered one stands — it simply
	stopped being read when WP-11 removed the legacy ``fee_collected``-vs-``tariff``
	status maths. It is the INPUT price again; nothing derives it, and no status or
	balance is computed from it (those still come from the invoice, R4).

	Pay-as-you-go bills one installment per invoice, so the period price is divided
	by the number of parts — mirroring ``provisioning.installment_rate``.

	Returns 0 when neither the membership nor its plan carries a price; callers must
	treat that as **not billable** rather than free (see :func:`is_billable`).
	"""
	membership = _as_doc("Membership", membership)
	price = flt(membership.get("tariff"))
	if price <= 0 and membership.get("membership_plan"):
		price = flt(frappe.db.get_value("Membership Plan", membership.membership_plan, "amount"))
	if price <= 0:
		return 0.0
	return flt(price) / installment_parts(membership)


def is_billable(membership) -> bool:
	"""False when no price can be resolved — billing would raise a Rs.0 invoice."""
	return membership_price(membership) > 0


def billing_mode(membership) -> str:
	"""The membership's plan's billing mode (defaults to Commitment)."""
	plan = membership.get("membership_plan")
	if not plan:
		return "Commitment"
	return frappe.db.get_value("Membership Plan", plan, "billing_mode") or "Commitment"


def open_obligations(membership) -> list[dict]:
	"""**The seam.** What this member owes and when — oldest first.

	Both billing modes reduce to the same list of ``(due_date, amount, outstanding)``
	rows; they differ only in where those rows physically live:

	* **Commitment** — one invoice for the period carrying a ``payment_schedule``
      row per installment.
	* **Pay-as-you-go** — one invoice per installment, each its own obligation.

	Everything downstream (status, balance, next-due, payment allocation, the
	collections list) reads THIS and never touches an invoice directly, so the
	two modes cost one function instead of branching through the codebase.

	Each row: ``{due_date, amount, outstanding, sales_invoice, payment_term, idx}``.
	"""
	membership = _as_doc("Membership", membership)
	if billing_mode(membership) == PAY_AS_YOU_GO:
		return _obligations_from_invoices(membership)
	return _obligations_from_schedule(membership)


def _settle_against_invoice(rows, si_name) -> list[dict]:
	"""Reconcile schedule rows down to the invoice's own ``outstanding_amount``.

	**WP-8.** ``Payment Schedule.outstanding`` is only ever written by Payment
	Entries (``payment_entry.update_payment_schedule``) — nothing else touches it.
	So a credit note or a write-off, both of which genuinely settle a receivable,
	left the installment rows showing the full amount still owing: a written-off
	member kept reading Overdue with their whole balance (traced 2026-08-08 — the
	invoice went to 0 outstanding while its schedule row still said 2,360).

	The invoice's scalar ``outstanding_amount`` IS authoritative — ERPNext re-derives
	it from the payment ledger, so it already reflects payments, credit notes,
	write-off Journal Entries and anything else that hits the receivable. Absorbing
	the difference oldest-first keeps the two in step without this function having
	to know which mechanism did the settling.
	"""
	invoice_outstanding = flt(frappe.db.get_value("Sales Invoice", si_name, "outstanding_amount"))
	# A negative invoice outstanding means the gym owes the member (over-credited);
	# nothing is owed on any installment.
	target = max(0.0, invoice_outstanding)
	surplus = sum(flt(r["outstanding"]) for r in rows) - target
	if surplus <= 0.005:
		return rows
	for row in rows:
		if surplus <= 0:
			break
		take = min(flt(row["outstanding"]), surplus)
		row["outstanding"] = flt(row["outstanding"]) - take
		surplus -= take
	return rows


def _obligations_from_schedule(membership) -> list[dict]:
	"""Commitment mode: the current invoice's payment_schedule rows."""
	si_name = current_invoice(membership)
	if not si_name or not frappe.db.exists("Sales Invoice", si_name):
		return []

	rows = frappe.get_all(
		"Payment Schedule",
		filters={"parent": si_name, "parenttype": "Sales Invoice"},
		fields=["due_date", "payment_amount", "outstanding", "paid_amount", "payment_term", "idx"],
		order_by="due_date asc, idx asc",
	)
	if rows:
		return _settle_against_invoice(
			[
				{
					"due_date": getdate(r.due_date) if r.due_date else None,
					"amount": flt(r.payment_amount),
					"outstanding": flt(r.outstanding),
					"sales_invoice": si_name,
					"payment_term": r.payment_term,
					"idx": r.idx,
				}
				for r in rows
			],
			si_name,
		)

	# No schedule (a plain single-due-date invoice) -> the invoice IS the obligation,
	# and its outstanding already nets credit notes and write-offs.
	si = frappe.db.get_value(
		"Sales Invoice", si_name, ["due_date", "grand_total", "outstanding_amount"], as_dict=True
	)
	return [
		{
			"due_date": getdate(si.due_date) if si.due_date else None,
			"amount": flt(si.grand_total),
			"outstanding": max(0.0, flt(si.outstanding_amount)),
			"sales_invoice": si_name,
			"payment_term": None,
			"idx": 1,
		}
	]


def _obligations_from_invoices(membership) -> list[dict]:
	"""Pay-as-you-go mode: each submitted invoice of the subscription is one
	obligation. Settled invoices are kept (with zero outstanding) so callers can
	still tell Partial from Pending."""
	if not membership.get("subscription"):
		return []
	rows = frappe.get_all(
		"Sales Invoice",
		# WP-8: exclude credit notes — they carry the same subscription link but are
		# a refund of an obligation, not one of their own.
		filters={"subscription": membership.subscription, "docstatus": 1, **NOT_A_CREDIT_NOTE},
		fields=["name", "due_date", "grand_total", "outstanding_amount"],
		order_by="due_date asc, posting_date asc",
	)
	return [
		{
			"due_date": getdate(r.due_date) if r.due_date else None,
			"amount": flt(r.grand_total),
			# Over-credited invoices go negative; the member owes nothing, not less
			# than nothing.
			"outstanding": max(0.0, flt(r.outstanding_amount)),
			"sales_invoice": r.name,
			"payment_term": None,
			"idx": index + 1,
		}
		for index, r in enumerate(rows)
	]


def next_due(obligations) -> dict | None:
	"""The earliest still-unpaid obligation — what the member owes NEXT."""
	unpaid = [o for o in obligations if flt(o["outstanding"]) > 0]
	if not unpaid:
		return None
	return min(unpaid, key=lambda o: (o["due_date"] or getdate(today()), o["idx"]))


def sync_from_billing(membership) -> None:
	"""Set status / balance_due / due_date / next_renewal from :func:`open_obligations`.

	Operates in-memory (the controller calls it in before_save); never infers CASH
	from outstanding (a write-off zeroes outstanding without collecting anything).

	R8: status and due_date come from the EARLIEST UNPAID obligation, never from
	the invoice's own scalar due_date — with installments that date is the LAST
	one, so a member who missed installment 2 would wrongly read as current.

	A no-op when billing has not been provisioned yet — provisioning is
	best-effort and must never block enrolment.
	"""
	obligations = open_obligations(membership)
	if not obligations:
		return

	membership.current_sales_invoice = obligations[-1]["sales_invoice"]
	total = sum(flt(o["amount"]) for o in obligations)
	outstanding = sum(flt(o["outstanding"]) for o in obligations)
	membership.balance_due = outstanding

	upcoming = next_due(obligations)
	if upcoming and upcoming["due_date"]:
		membership.due_date = upcoming["due_date"]

	# WP-8: how this period's balance got settled, for the owner to see. Both are
	# derived per CURRENT invoice, never accumulated on the membership, so the next
	# period starts clean without any state to reset.
	from netgainz.net_gainz.accounting import refunds, writeoff

	si_name = membership.current_sales_invoice
	written_off = writeoff.written_off_against(si_name)
	membership.written_off_amount = written_off
	membership.refunded_amount = refunds.credited_against(si_name)

	if outstanding <= 0 and written_off > 0:
		# ERPNext marks a written-off invoice "Paid". For the owner that is a lie:
		# nobody paid. Say what actually happened.
		membership.status = "Written Off"
	elif outstanding <= 0:
		membership.status = "Paid"
	elif upcoming and upcoming["due_date"] and getdate(today()) > upcoming["due_date"]:
		membership.status = "Overdue"
	elif outstanding < total:
		membership.status = "Partial"
	else:
		membership.status = "Pending"

	if membership.get("subscription") and frappe.db.exists("Subscription", membership.subscription):
		# Prepaid: the next charge falls on the next period's START, which the
		# Subscription has already advanced current_invoice_start to once the
		# current period's invoice was generated.
		start = frappe.db.get_value("Subscription", membership.subscription, "current_invoice_start")
		if start:
			membership.next_renewal = getdate(start)


# Kept as the historical name used before the obligations seam existed.
sync_from_invoice = sync_from_billing


def sync_derived_fields(membership) -> None:
	"""Re-derive AND persist status / balance_due / due_date / next_renewal.

	``sync_from_invoice`` runs from the controller's ``before_save``, but a
	membership's Subscription and first invoice are provisioned in ``after_insert``
	— i.e. after that hook has already run. Without this a freshly enrolled
	membership would keep empty derived fields until something saved it again.
	Writes with ``db_set`` rather than ``save()`` so the just-inserted document is
	not re-validated (and cannot trip a modified-timestamp conflict)."""
	membership = _as_doc("Membership", membership)
	sync_from_billing(membership)
	membership.calculate_overdue_days()
	for field in (
		"current_sales_invoice",
		"status",
		"balance_due",
		"due_date",
		"next_renewal",
		"overdue_days",
		"written_off_amount",
		"refunded_amount",
	):
		value = membership.get(field)
		if value is not None:
			membership.db_set(field, value, update_modified=False)


# --------------------------------------------------------------------------- #
# the shared cash read (R1/R2): collected cash from Payment Entries
# --------------------------------------------------------------------------- #
def _members_to_customers(members):
	"""Translate Member names -> their ERPNext Customer names (drops members with
	no Customer yet). None in -> None out (no party scoping)."""
	if members is None:
		return None
	return [c for m in members if (c := frappe.db.get_value("Member", m, "customer"))]


def collected_paise(start, end, customers=None) -> int:
	"""Membership revenue **net of refunds** collected in [start, end], in integer
	paise, read from Payment Entries.

	Allocation-anchored: sums each Payment Entry Reference's ``allocated_amount``
	for submitted Payment Entries against a subscription-generated Sales Invoice.
	Unallocated cash (advances / money on account) is excluded by construction —
	so are non-membership income, capital injections and transfers — and an advance
	enters this total on the day it was RECEIVED, once it is applied to a membership
	invoice (see accounting.advances for the recognition rule).

	**WP-8 cash-impact rule: a refunded rupee leaves this total.** A refund is a
	``Pay`` Payment Entry allocated to the credit note (or to the over-credited
	original), and ERPNext writes that allocation NEGATIVE — traced 2026-08-08:
	``payment_type='Pay'``, ``allocated_amount=-590`` against a credit note whose
	``grand_total`` is ``-590``. Summing allocations signed is therefore exactly the
	net cash that moved, with no special-casing: the old ``payment_type='Receive'``
	and ``grand_total > 0`` filters are what used to make refunds invisible, and
	they are gone.

	Each allocation is scaled by ``net_total / grand_total`` so only the **ex-GST**
	portion counts — GST collected is a pass-through liability, not revenue. Both
	totals are negative on a credit note, so the ratio stays positive and the sign
	comes from the allocation alone. For a non-GST tenant the ratio is 1.

	Multi-currency safe (WP-8): allocations are converted to **company currency**
	via the reference row's own ``exchange_rate`` (Payment Entry Reference has no
	stored base amount), so a foreign-currency document can never be summed into
	the base-currency total at face value.
	"""
	if customers is not None and not customers:
		return 0
	params = {"start": getdate(start), "end": getdate(end)}
	party_clause = ""
	if customers is not None:
		party_clause = "AND pe.party IN %(customers)s"
		params["customers"] = tuple(customers)
	rows = frappe.db.sql(
		f"""
		SELECT per.allocated_amount
		       * COALESCE(NULLIF(per.exchange_rate, 0), 1)
		       * si.net_total / si.grand_total AS amt
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name
		WHERE pe.docstatus = 1
		  AND pe.payment_type IN ('Receive', 'Pay')
		  AND pe.posting_date BETWEEN %(start)s AND %(end)s
		  AND per.reference_doctype = 'Sales Invoice'
		  AND si.subscription IS NOT NULL AND si.subscription != ''
		  AND si.grand_total != 0
		  {party_clause}
		""",
		params,
		as_dict=True,
	)
	return sum(calc.to_paise(r.amt) for r in rows)


def membership_collected_paise(start, end, members=None) -> int:
	"""THE shared cash read for Profit First + commissions (integer paise).

	WP-11: a single Payment-Entry read. Every membership bills through ERPNext, so
	collected cash is always the ex-GST allocation of a submitted Receive Payment
	Entry against a subscription-generated Sales Invoice — never
	``Membership.fee_collected``, which is a deprecated display field feeding no
	calculation. ``members`` (Member names) optionally scopes the total, translated
	to the members' Customers."""
	return collected_paise(start, end, _members_to_customers(members))


# --------------------------------------------------------------------------- #
# whitelisted owner / BFF entry points
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def record_membership_payment(
	membership, amount, payment_mode=None, posting_date=None, reference_no=None, allow_advance=0
) -> dict:
	"""Owner/BFF: record a payment; returns the Payment Entry + remaining outstanding.

	``allow_advance`` lets the member pay more than this period's invoice; the
	excess is parked on their account (WP-8) instead of being rejected.
	"""
	from netgainz.net_gainz import permissions
	from netgainz.net_gainz.accounting import advances

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	pe = record_payment(
		membership,
		amount,
		payment_mode,
		posting_date or today(),
		reference_no=reference_no,
		allow_advance=bool(int(allow_advance or 0)),
	)
	si = frappe.db.get_value("Membership", membership, "current_sales_invoice")
	outstanding = flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount")) if si else 0
	return {
		"payment_entry": pe,
		"outstanding": outstanding,
		"advance_balance": advances.advance_balance(membership),
	}


@frappe.whitelist()
def generate_membership_invoice(membership, posting_date=None) -> dict:
	"""Owner/BFF: bill the current period now. Provisions the Subscription first."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER, permissions.GYM_STAFF)
	company = _company()
	ensure_subscription(membership, company)
	invoice = force_generate_invoice(membership, posting_date)
	return {"sales_invoice": invoice}


@frappe.whitelist()
def get_membership_obligations(membership) -> dict:
	"""Owner/BFF: what this member owes and when — the installment schedule.

	Serialised straight from :func:`open_obligations`, so the owner app shows the
	same rows the backend bills and allocates against, in either billing mode."""
	from netgainz.net_gainz.accounting import advances, refunds, writeoff

	rows = open_obligations(membership)
	si_name = rows[-1]["sales_invoice"] if rows else None
	return {
		"obligations": [
			{
				"due_date": str(o["due_date"]) if o["due_date"] else None,
				"amount": flt(o["amount"]),
				"outstanding": flt(o["outstanding"]),
				"sales_invoice": o["sales_invoice"],
				"payment_term": o["payment_term"],
				"idx": o["idx"],
			}
			for o in rows
		],
		"total": flt(sum(flt(o["amount"]) for o in rows)),
		"outstanding": flt(sum(flt(o["outstanding"]) for o in rows)),
		# WP-8: how the rest of the period's balance was settled, if not by cash.
		"refunded": refunds.credited_against(si_name) if si_name else 0.0,
		"written_off": writeoff.written_off_against(si_name) if si_name else 0.0,
		"advance_balance": advances.advance_balance(membership),
	}


@frappe.whitelist()
def unbillable_memberships() -> dict:
	"""Owner/BFF: who cannot be billed yet, and why.

	A membership with no resolvable price is deliberately left without a
	Subscription — better an obvious gap than a submitted Rs.0 invoice, which is
	silent revenue leakage and a mess to unwind. This is the list the owner works
	through before switching billing on: set the member's own price (or the plan's),
	then generate.
	"""
	rows = []
	for ms in frappe.get_all(
		"Membership",
		fields=["name", "member", "member_name", "membership_plan", "tariff", "subscription"],
		limit_page_length=0,
	):
		if is_billable(ms.name):
			continue
		plan_amount = flt(
			frappe.db.get_value("Membership Plan", ms.membership_plan, "amount")
		) if ms.membership_plan else 0
		rows.append(
			{
				"membership": ms.name,
				"member": ms.member,
				"member_name": ms.member_name or ms.member,
				"membership_plan": ms.membership_plan,
				"price": flt(ms.tariff),
				"plan_amount": plan_amount,
				"has_subscription": bool(ms.subscription),
				"reason": (
					"No price on the membership and no amount on the plan"
					if not plan_amount
					else "No price on the membership"
				),
			}
		)
	return {"count": len(rows), "rows": rows}


@frappe.whitelist()
def report_cycle_anchor_drift() -> dict:
	"""DRY RUN: which memberships bill on a day other than their joining day.

	Moot on a fresh tenant (every subscription is anchored at enrolment), but kept
	as the safety rail for re-anchoring a tenant that is already live: run this
	FIRST, review the list, brief the front desk, and only then apply a
	convert-once patch (ADR-0007). Reports only — changes nothing.
	"""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	rows = []
	for ms in frappe.get_all(
		"Membership",
		filters=[["subscription", "is", "set"]],
		fields=["name", "member", "member_name", "subscription", "next_renewal"],
		limit_page_length=0,
	):
		sub = frappe.db.get_value(
			"Subscription", ms.subscription, ["start_date", "plans"], as_dict=True
		)
		if not sub or not sub.start_date:
			continue
		plan = frappe.db.get_value(
			"Subscription Plan Detail", {"parent": ms.subscription}, "plan"
		)
		expected = cycle_start(ms.member, plan)
		actual = getdate(sub.start_date)
		if expected and getdate(expected) != actual:
			rows.append(
				{
					"membership": ms.name,
					"member": ms.member_name or ms.member,
					"current_start": str(actual),
					"anchored_start": str(getdate(expected)),
					"shift_days": (getdate(expected) - actual).days,
					"next_renewal": str(ms.next_renewal) if ms.next_renewal else None,
				}
			)
	# Largest backward shift first — those are the members who would suddenly owe
	# sooner, i.e. the ones the front desk has to be warned about.
	rows.sort(key=lambda r: r["shift_days"])
	return {"count": len(rows), "rows": rows}


@frappe.whitelist()
def provision_membership_subscription(membership) -> dict:
	"""Owner: stand up the Subscription for an existing membership (pilot cut-over)."""
	from netgainz.net_gainz import permissions

	permissions.require_role(permissions.GYM_OWNER)
	return {"subscription": ensure_subscription(membership)}
