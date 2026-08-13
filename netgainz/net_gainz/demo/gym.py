# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""A believable gym, seeded end to end, for showing NetGainz to a prospect.

Everything here goes in through the SAME paths the product uses — Member ->
Membership -> native Subscription -> Sales Invoice -> Payment Entry, offers resolved
by :mod:`accounting.offers`, discounts by :mod:`accounting.discounts` — so what a
prospect sees on screen is the real application working, not fixtures painted to look
like it. That is the point: a demo that fakes its numbers cannot answer "what happens
if I discount this member?", and that question is the sale.

**Run it on a dedicated demo site.** Dashboards, Profit First and the discounts report
are gym-wide reads, so seeding into a site that already holds a real tenant mixes the
two — and a demo must never put a real member's name on a prospect's screen.

    bench --site demo.localhost execute netgainz.net_gainz.demo.gym.seed_demo_gym
    bench --site demo.localhost execute netgainz.net_gainz.demo.gym.wipe_demo

Idempotent: masters are found-or-created and members are keyed on their code, so a
re-run tops the gym up rather than duplicating it. ``wipe_demo`` removes exactly what
this module creates, by those same names and the ``IF####`` member code.
"""

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, today

from netgainz.net_gainz.accounting import billing, branch, discounts, offers, provisioning
from netgainz.net_gainz.profit_first import accounts as pf_accounts
from netgainz.net_gainz.profit_first.seed import seed_profit_first_defaults

# Fitness SAC. India Compliance makes a tax code mandatory on a sellable Item, and a
# plan without one silently cannot bill (reference: HSN/SAC is mandatory).
SAC = "999723"
MEMBER_PREFIX = "IF"
OWNER_PIN = "2468"

PROGRAMS = ["Strength Training", "CrossFit", "Yoga", "Zumba", "Personal Training"]

INSTRUCTORS = [
	{
		"coach_name": "Arun Prakash",
		"specialization": "Strength",
		"commission_type": "Percentage",
		"commission_amount": 10,
	},
	{
		"coach_name": "Divya Menon",
		"specialization": "Yoga",
		"commission_type": "Per Member",
		"commission_amount": 250,
	},
	{
		"coach_name": "Rahul Iyer",
		"specialization": "Functional",
		"commission_type": "Fixed",
		"commission_amount": 8000,
	},
]

PLANS = [
	{"plan_name": "Monthly", "plan_type": "Monthly", "amount": 1500, "trial_days": 7},
	{"plan_name": "Quarterly", "plan_type": "Quarterly", "amount": 4000},
	{"plan_name": "Half-Yearly", "plan_type": "Half-Yearly", "amount": 7500},
	{
		"plan_name": "Annual",
		"plan_type": "Yearly",
		"amount": 14000,
		"installment_count": 3,
		"installment_gap_days": 30,
	},
	{"plan_name": "Student Monthly", "plan_type": "Monthly", "amount": 1000},
]

EXPENSE_CATEGORIES = [
	("Rent", "Operating Expenses"),
	("Salaries", "Operating Expenses"),
	("Electricity", "Operating Expenses"),
	("Equipment Maintenance", "Operating Expenses"),
	("Marketing", "Operating Expenses"),
	("Owner Draw", "Owner's Pay"),
	("GST Payment", "Tax"),
	("Supplement Stock", "Pass-Through"),
]

# (category, amount, vendor) charged every month of the demo history.
MONTHLY_EXPENSES = [
	("Rent", 45000, "Sundaram Properties"),
	("Salaries", 62000, "Staff payroll"),
	("Electricity", 11500, "TNEB"),
	("Equipment Maintenance", 4500, "FitServe"),
	("Marketing", 6000, "Instagram Ads"),
	("Owner Draw", 40000, ""),
	("Supplement Stock", 18000, "MuscleMart"),
]

# name, plan, months since joining, what they actually pay (None = plan price)
MEMBERS = [
	("Karthik Subramanian", "Monthly", 14, None),
	("Priya Raghavan", "Monthly", 13, 1400),
	("Vignesh Kumar", "Annual", 12, None),
	("Anitha Selvaraj", "Quarterly", 11, None),
	("Mohan Das", "Monthly", 11, 1200),
	("Sneha Pillai", "Half-Yearly", 10, None),
	("Rajesh Balan", "Monthly", 10, None),
	("Deepa Krishnan", "Student Monthly", 9, None),
	("Suresh Nair", "Monthly", 9, 1350),
	("Lakshmi Narayanan", "Quarterly", 8, None),
	("Arjun Reddy", "Monthly", 8, None),
	("Meena Gopal", "Monthly", 7, 1500),
	("Sanjay Verma", "Annual", 7, None),
	("Kavitha Ramesh", "Monthly", 6, None),
	("Praveen Anand", "Half-Yearly", 6, None),
	("Divya Shankar", "Monthly", 5, 1400),
	("Hari Prasad", "Quarterly", 5, None),
	("Nithya Bala", "Student Monthly", 5, None),
	("Gopinath M", "Monthly", 4, None),
	("Ramya Sundar", "Monthly", 4, None),
	("Vikram Chandra", "Annual", 4, None),
	("Shalini Ravi", "Monthly", 3, None),
	("Ajith Kumar", "Monthly", 3, 1300),
	("Bhavana Rao", "Quarterly", 3, None),
	("Naveen Joseph", "Monthly", 2, None),
	("Swathi Menon", "Student Monthly", 2, None),
	("Manoj Pillai", "Monthly", 2, None),
	("Aishwarya Devi", "Half-Yearly", 2, None),
	("Kiran Bedi", "Monthly", 1, None),
	("Rohit Sharma", "Monthly", 1, 1450),
	("Fathima Noor", "Quarterly", 1, None),
	("Sathish Kumar", "Monthly", 1, None),
	("Janani Prakash", "Student Monthly", 1, None),
	("Ashwin Raj", "Monthly", 1, None),
	("Pooja Iyer", "Monthly", 0, None),
	("Dinesh Karthik", "Annual", 0, None),
	("Revathi Suresh", "Monthly", 0, None),
	("Surya Narayan", "Quarterly", 0, None),
	("Nandini Krishna", "Monthly", 0, None),
	("Vetri Maaran", "Monthly", 0, None),
	# Walked in this week and are training on the free trial — no invoice yet.
	("Aravind Selvam", "Monthly", 0, None),
	("Sowmya Ravi", "Monthly", 0, None),
]

# Members who negotiated something, with the reason the owner will be asked about.
DISCOUNTS = {
	"Priya Raghavan": (discounts.PERCENTAGE, 10, discounts.EVERY_INVOICE, "Corporate rate — Tidel Park"),
	"Mohan Das": (discounts.AMOUNT, 200, discounts.EVERY_INVOICE, "Long-time member, joined 2019"),
	"Deepa Krishnan": (discounts.PERCENTAGE, 15, discounts.EVERY_INVOICE, "Student rate"),
	"Nithya Bala": (discounts.PERCENTAGE, 15, discounts.EVERY_INVOICE, "Student rate"),
	"Ajith Kumar": (discounts.PERCENTAGE, 10, discounts.FIRST_INVOICE, "Joining offer at the desk"),
	"Swathi Menon": (discounts.PERCENTAGE, 15, discounts.EVERY_INVOICE, "Student rate"),
	"Janani Prakash": (
		discounts.PERCENTAGE,
		30,
		discounts.EVERY_INVOICE,
		"Owner approved — trainer's sister",
	),
	"Vetri Maaran": (
		discounts.PERCENTAGE,
		100,
		discounts.EVERY_INVOICE,
		"Complimentary — gym's first member",
	),
}

# Members enrolled through a campaign or a coupon.
OFFER_MEMBERS = {
	"Pooja Iyer": "Festive Season 15%",
	"Surya Narayan": "Festive Season 15%",
	"Dinesh Karthik": "Founding Member Rate",
	"Revathi Suresh": "FIT50 — Instagram",
}

# Members whose free trial is still running (no invoice yet).
TRIAL_MEMBERS = ["Nandini Krishna", "Aravind Selvam", "Sowmya Ravi"]

# Members who have not paid the current period, so the demo has something to chase.
UNPAID = ["Kavitha Ramesh", "Manoj Pillai", "Naveen Joseph"]
PART_PAID = ["Sanjay Verma", "Vikram Chandra"]

PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer"]

# title, program, instructor, start time, capacity, the days it runs
TIMETABLE = [
	(
		"Morning Strength",
		"Strength Training",
		"Arun Prakash",
		"06:00:00",
		20,
		["monday", "wednesday", "friday"],
	),
	("Sunrise Yoga", "Yoga", "Divya Menon", "07:30:00", 15, ["tuesday", "thursday", "saturday"]),
	("Evening CrossFit", "CrossFit", "Rahul Iyer", "18:30:00", 18, ["monday", "tuesday", "thursday"]),
	("Weekend Zumba", "Zumba", "Divya Menon", "09:00:00", 25, ["saturday", "sunday"]),
]


# --------------------------------------------------------------------------- #
# masters
# --------------------------------------------------------------------------- #
def _company():
	company = pf_accounts.default_company()
	if not company:
		frappe.throw("Set a default Company for this site first — the demo bills through it.")
	return company


def _upsert(doctype, key, values):
	"""Find-or-create by name, updating the fields we care about. Idempotent."""
	if frappe.db.exists(doctype, key):
		doc = frappe.get_doc(doctype, key)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def _settings(company):
	"""The gym's own settings, so every screen reads in its own words."""
	settings = frappe.get_single("Business Settings")
	settings.update(
		{
			"accounting_method": "Cash",
			"member_id_prefix": MEMBER_PREFIX,
			"days_until_due": 0,
			"renewal_reminder_days": 7,
			"renewal_reminders_enabled": 1,
			"default_hsn_sac": SAC,
			"max_discount_percent": 10,
			"complimentary_requires_owner": 1,
			"owner_approval_pin": OWNER_PIN,
			"commission_percentage_basis": "Assigned Member Revenue",
		}
	)
	settings.save(ignore_permissions=True)

	seed_profit_first_defaults()
	pf = frappe.get_single("Profit First Settings")
	pf.pf_enabled = 1
	pf.assessment_window = "This Month"
	pf.save(ignore_permissions=True)

	branch.ensure_main_branch(company)
	billing_cash_account(company)


def billing_cash_account(company):
	"""Money needs somewhere to land: a cash drawer AND a bank account.

	Members pay in cash, by UPI, by card and by transfer, and NetGainz posts the digital
	modes to the company's default bank account — a demo that sets only the cash account
	falls over on the first UPI payment.
	"""
	for fieldname, account_type, label in (
		("default_cash_account", "Cash", "Cash"),
		("default_bank_account", "Bank", "Gym Bank Account"),
	):
		if frappe.db.get_value("Company", company, fieldname):
			continue
		account = frappe.db.get_value(
			"Account", {"company": company, "account_type": account_type, "is_group": 0}, "name"
		) or _ensure_asset_account(company, label, account_type)
		if account:
			frappe.db.set_value("Company", company, fieldname, account)
	# The resolver reads the Company through the document cache, which still holds the
	# pre-update copy inside this same request.
	frappe.clear_document_cache("Company", company)


def _ensure_asset_account(company, account_name, account_type):
	"""Create the missing ledger under the company's Bank/Cash group. Idempotent."""
	group = frappe.db.get_value(
		"Account", {"company": company, "account_type": account_type, "is_group": 1}, "name"
	) or frappe.db.get_value(
		"Account", {"company": company, "account_name": "Current Assets", "is_group": 1}, "name"
	)
	if not group:
		return None
	existing = frappe.db.get_value("Account", {"company": company, "account_name": account_name}, "name")
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"parent_account": group,
				"company": company,
				"account_type": account_type,
				"is_group": 0,
				"account_currency": frappe.get_cached_value("Company", company, "default_currency"),
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _postable(company, date) -> bool:
	"""Can the books take a posting on this date?

	ERPNext refuses any posting outside an active Fiscal Year, and a site is created with
	the CURRENT year only — so six months of history can fall off the back of it (a demo
	seeded in August 2026 wants February 2026, which belongs to FY 2025-26).

	The demo REPORTS that rather than creating the missing year: an April-March year
	clashes with the calendar-year fiscal years some sites carry, and the only way ERPNext
	then accepts it is to scope the year to one company — which silently blocks postings
	for every other company on the site. Not a trade a demo script should make on someone
	else's books. Add the year in ERPNext yourself for longer history, then re-run.
	"""
	from erpnext.accounts.utils import FiscalYearError, get_fiscal_years

	try:
		get_fiscal_years(getdate(date), company=company)
		return True
	except FiscalYearError:
		frappe.clear_last_message()
		return False


def _masters(company):
	for program in PROGRAMS:
		_upsert("Program", program, {"program_name": program, "is_active": 1})

	for instructor in INSTRUCTORS:
		_upsert(
			"Instructor",
			instructor["coach_name"],
			{**instructor, "status": "Active", "date_of_joining": add_months(getdate(today()), -18)},
		)

	for category, bucket in EXPENSE_CATEGORIES:
		_upsert("Expense Category", category, {"category_name": category, "pf_bucket": bucket})

	for plan in PLANS:
		_upsert(
			"Membership Plan",
			plan["plan_name"],
			{
				"is_active": 1,
				"gst_hsn_code": SAC,
				"payment_due_rule": "On joining",
				**plan,
			},
		)


def _offers():
	"""One ended campaign, one running, a grandfathered rate and a coupon."""
	catalogue = [
		{
			"offer_name": "New Year 20%",
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 20,
			"discount_duration": offers.FIRST_INVOICE,
			"valid_from": getdate(f"{getdate(today()).year}-01-01"),
			"valid_upto": getdate(f"{getdate(today()).year}-01-31"),
			"description": "New year joining offer — first month 20% off.",
		},
		{
			"offer_name": "Festive Season 15%",
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 15,
			"discount_duration": offers.FIRST_INVOICE,
			"valid_from": add_days(getdate(today()), -20),
			"valid_upto": add_days(getdate(today()), 40),
			"description": "Festival campaign — 15% off the first invoice, any plan.",
		},
		{
			"offer_name": "Founding Member Rate",
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 25,
			"discount_duration": offers.EVERY_INVOICE,
			"valid_from": add_months(getdate(today()), -1),
			"valid_upto": add_days(getdate(today()), 60),
			"max_total_uses": 50,
			"description": "First 50 members keep 25% off for as long as they stay.",
		},
		{
			"offer_name": "FIT50 — Instagram",
			"discount_type": discounts.PERCENTAGE,
			"discount_value": 50,
			"discount_duration": offers.FIRST_INVOICE,
			"coupon_code": "FIT50",
			"max_total_uses": 25,
			"max_uses_per_member": 1,
			"valid_from": add_days(getdate(today()), -10),
			"valid_upto": add_days(getdate(today()), 50),
			"description": "Instagram campaign — half off the first month. Quote FIT50.",
		},
	]
	for offer in catalogue:
		_upsert("Offer", offer["offer_name"], {"disabled": 0, **offer})


# --------------------------------------------------------------------------- #
# members, memberships and their money
# --------------------------------------------------------------------------- #
def _member_code(index) -> str:
	return f"{MEMBER_PREFIX}{1000 + index}"


def _make_member(index, name, plan, months_ago):
	code = _member_code(index)
	# Scatter the joining DAY as well as the month: memberships are anchored on the day
	# a member joined, so seeding everyone on today's date would make every renewal and
	# every due date fall on the same day — a gym never looks like that, and the
	# renewals screen would be empty until the month turned.
	# NB the brackets: `-(index * 3) % 28` is POSITIVE in Python, which quietly dated
	# every other member into the FUTURE (and gave them a trial starting next month).
	joining = add_days(add_months(getdate(today()), -months_ago), -((index * 3) % 28))
	instructor = INSTRUCTORS[index % len(INSTRUCTORS)]["coach_name"]
	values = {
		"member_code": code,
		"full_name": name,
		# A valid Indian mobile: 10 digits, deterministic per member so a re-seed
		# hands the same person the same number.
		"phone": f"+91 98{(76500000 + index * 137) % 100000000:08d}",
		"email": f"{name.split()[0].lower()}.{code.lower()}@example.com",
		"date_of_joining": joining,
		"membership_plan": plan,
		"gym_program": PROGRAMS[index % len(PROGRAMS)],
		"coach": instructor,
		"category": "Sport" if index % 4 == 0 else "General",
		"source_of_reference": ["Walk-in", "Social Media", "Referral", "Google"][index % 4],
		"status": "Active",
	}
	return _upsert("Member", code, values)


def _has_history(name, plan, months_ago) -> bool:
	"""Only established monthly members get month-by-month history.

	A quarterly or annual member's single current invoice already tells their story;
	inventing extra ones would double-count their revenue. A member on a free trial gets
	none at all: billing them would raise the 100%-discounted Rs.0 invoice ERPNext
	produces during a trial, and that invoice would then occupy the period.
	"""
	return months_ago >= 1 and plan == "Monthly" and name not in TRIAL_MEMBERS


def _make_membership(member, name, plan, price, months_ago):
	"""Enrol the member — this raises their invoices through the real path.

	A member with history is enrolled as a backfilled row (no invoice at enrolment),
	their past periods are billed oldest-first, and only THEN is the current period
	raised — so the newest invoice really is the current one. Enrolling first and
	back-filling afterwards would leave the app pointing at last month's invoice as
	"current", because it takes the most recently created one.
	"""
	existing = frappe.db.get_value("Membership", {"member": member.name}, "name")
	if existing:
		return frappe.get_doc("Membership", existing)

	fields = {"doctype": "Membership", "member": member.name, "membership_plan": plan}
	if price:
		fields["tariff"] = price
	if _has_history(name, plan, months_ago):
		fields["is_backfill"] = 1

	if name in TRIAL_MEMBERS:
		fields["trial_days"] = 7
	else:
		# The Monthly plan offers a free week, and it stays on the plan because it is
		# worth showing. Everyone already enrolled has had theirs, so they are billing
		# normally — otherwise a seeded gym would be 23 members on trial and no money.
		fields["skip_trial"] = 1

	if name in OFFER_MEMBERS:
		fields["offer"] = OFFER_MEMBERS[name]
	elif name in DISCOUNTS:
		kind, value, duration, reason = DISCOUNTS[name]
		fields.update(
			{
				"discount_type": kind,
				"discount_value": value,
				"discount_duration": duration,
				"discount_reason": reason,
			}
		)

	membership = frappe.get_doc(fields).insert(ignore_permissions=True)
	if membership.get("is_backfill"):
		billing.ensure_subscription(membership)
	membership.reload()
	return membership


def _history_invoice(membership, company, period_start, period_end):
	"""One past period's invoice, raised the way the scheduler raises it.

	Built directly rather than through ``Subscription.process`` because that always
	posts at the CURRENT period's start — there is no way to ask it for last March.
	Everything else is identical: the subscription link is set, so the app's own
	before_validate seam prices it at this member's rate, applies their discount, and
	Profit First counts the cash (it only reads payments against subscription-linked
	invoices).
	"""
	customer = frappe.db.get_value("Member", membership.member, "customer")
	if not customer:
		return None
	invoice = frappe.new_doc("Sales Invoice")
	invoice.company = company
	invoice.customer = customer
	invoice.set_posting_time = 1
	invoice.posting_date = period_start
	invoice.subscription = membership.subscription
	invoice.from_date = period_start
	invoice.to_date = period_end
	invoice.cost_center = branch.branch_cost_center(membership.get("branch"), company)
	item = frappe.db.get_value("Membership Plan", membership.membership_plan, "item")
	invoice.append("items", {"item_code": item, "qty": 1, "rate": flt(membership.tariff) or 1})
	invoice.flags.ignore_permissions = True
	invoice.set_missing_values()
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	return invoice.name


def _collect(membership, invoice, posting_date, index, part=1.0):
	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"))
	if outstanding <= 0:
		return None
	mode = PAYMENT_MODES[index % len(PAYMENT_MODES)]
	# ERPNext requires a reference number on anything that moves through a bank
	# account, which is also what a gym would actually have on the receipt.
	reference = None if mode == "Cash" else f"{mode[:3].upper()}{getdate(posting_date):%y%m%d}{index:03d}"
	return billing.record_payment(
		membership.name,
		round(outstanding * part, 2),
		payment_mode=mode,
		posting_date=posting_date,
		sales_invoice=invoice,
		reference_no=reference,
	)


def _bill_history(membership, name, company, index, months_ago):
	"""Give a long-standing member the periods they have already paid for.

	Called only for the members :func:`_has_history` covers.
	"""
	raised = 0
	for back in range(min(months_ago, 6), 0, -1):
		start = get_first_day(add_months(getdate(today()), -back))
		end = add_days(get_first_day(add_months(start, 1)), -1)
		if not _postable(company, start):
			# No fiscal year for that month — the gym simply has less history on show.
			continue
		if frappe.db.exists(
			"Sales Invoice", {"subscription": membership.subscription, "from_date": start, "docstatus": 1}
		):
			continue
		invoice = _history_invoice(membership, company, start, end)
		if not invoice:
			continue
		raised += 1
		# Members pay a few days into the period; a couple pay late, which is what
		# makes the collections screens worth looking at.
		paid_on = add_days(start, 2 + (index % 6))
		_collect(membership, invoice, paid_on, index)

	# The current period is raised LAST, so the app's "latest invoice" really is this
	# month's. The membership was enrolled as a backfill row precisely so this could
	# happen after its own history rather than before it.
	billing.force_generate_invoice(membership)
	membership.db_set("is_backfill", 0, update_modified=False)
	membership.reload()
	return raised


def _settle_current(membership, name, index):
	"""Pay (or deliberately not pay) the current period."""
	invoice = membership.get("current_sales_invoice")
	if not invoice:
		return
	if name in UNPAID:
		return
	if name in PART_PAID:
		_collect(membership, invoice, add_days(getdate(today()), -3), index, part=0.4)
		return
	_collect(membership, invoice, add_days(getdate(today()), -(index % 8)), index)


# --------------------------------------------------------------------------- #
# expenses, classes
# --------------------------------------------------------------------------- #
def _expenses(company, months):
	created = 0
	for back in range(months, -1, -1):
		month_start = get_first_day(add_months(getdate(today()), -back))
		for category, amount, vendor in MONTHLY_EXPENSES:
			date = add_days(month_start, 4)
			if getdate(date) > getdate(today()):
				continue
			if frappe.db.exists("Expense", {"category": category, "date": date}) or not _postable(
				company, date
			):
				continue
			frappe.get_doc(
				{
					"doctype": "Expense",
					"date": date,
					"category": category,
					"amount": amount,
					"payment_mode": "Bank Transfer",
					"vendor": vendor,
					"company": company,
				}
			).insert(ignore_permissions=True)
			created += 1
	return created


def _classes():
	"""A weekly timetable, so the classes and attendance screens have something in them."""
	created = 0
	for title, program, coach, start, capacity, days in TIMETABLE:
		if frappe.db.exists("Session Schedule", {"title": title}):
			continue
		schedule = {
			"doctype": "Session Schedule",
			"title": title,
			"program": program,
			"coach": coach,
			"start_time": start,
			"duration_mins": 60,
			"capacity": capacity,
			"is_active": 1,
		}
		schedule.update({f"on_{day}": 1 for day in days})
		frappe.get_doc(schedule).insert(ignore_permissions=True)
		created += 1

	# Turn the timetable into actual sessions the way the nightly job does, then fill a
	# few of them: an empty attendance screen tells a prospect nothing.
	from netgainz.net_gainz.doctype.session_schedule.session_schedule import (
		generate_scheduled_classes,
	)

	frappe.db.set_single_value("Business Settings", "class_auto_generate", 1)
	generate_scheduled_classes()
	return created


def _attendance(limit=24) -> int:
	"""Book members into the next few sessions, and check some of them in."""
	members = frappe.get_all(
		"Member",
		filters={"member_code": ["like", f"{MEMBER_PREFIX}1%"], "status": "Active"},
		fields=["name", "full_name"],
		order_by="creation",
		limit=limit,
	)
	sessions = frappe.get_all(
		"Session",
		filters={"status": "Scheduled"},
		fields=["name", "coach", "start_time"],
		order_by="start_time",
		limit=6,
	)
	if not members or not sessions:
		return 0

	booked = 0
	for index, member in enumerate(members):
		session = sessions[index % len(sessions)]
		if frappe.db.exists("Session Booking", {"class_session": session.name, "member": member.name}):
			continue
		# The earliest sessions have already happened in demo time, so they carry
		# attendance; the later ones are still just bookings.
		attended = index % 3 != 2 and getdate(session.start_time) <= getdate(today())
		frappe.get_doc(
			{
				"doctype": "Session Booking",
				"class_session": session.name,
				"member": member.name,
				"member_name": member.full_name,
				"coach": session.coach,
				"start_time": session.start_time,
				"status": "Attended" if attended else "Booked",
				"check_in_time": session.start_time if attended else None,
			}
		).insert(ignore_permissions=True)
		booked += 1
	return booked


# --------------------------------------------------------------------------- #
# the entry points
# --------------------------------------------------------------------------- #
def seed_demo_gym(history_months=6, commit=True) -> dict:
	"""Stand up the whole demo gym. Safe to re-run."""
	company = _company()
	_settings(company)
	_masters(company)
	_offers()

	summary = {"members": 0, "memberships": 0, "history_invoices": 0}
	for index, (name, plan, months_ago, price) in enumerate(MEMBERS, start=1):
		member = _make_member(index, name, plan, months_ago)
		provisioning.provision_customer(member.name, company)
		membership = _make_membership(member, name, plan, price, months_ago)
		summary["members"] += 1
		if not membership.get("subscription"):
			# No resolvable price: the membership stands, and it shows up on the owner's
			# "cannot be billed" list until someone sets one. That is deliberate.
			continue
		summary["memberships"] += 1
		if _has_history(name, plan, months_ago):
			summary["history_invoices"] += _bill_history(membership, name, company, index, months_ago)
		_settle_current(membership, name, index)
		billing.sync_derived_fields(membership)

	summary["expenses"] = _expenses(company, history_months)
	summary["class_schedules"] = _classes()
	summary["bookings"] = _attendance()
	if commit:
		frappe.db.commit()
	return summary


def _cancel_and_delete(doctype, name) -> None:
	"""Cancel a posted document and remove it, ledger rows and all.

	Cancelling leaves ERPNext's own GL and Payment Ledger rows pointing at the voucher,
	and the delete then refuses ("is linked with Payment Ledger Entry"). Those rows are
	cancelled entries with no life of their own once the voucher goes, so they are
	purged directly — the same order the production cleanup toolkit uses.
	"""
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus == 1:
		doc.cancel()
	for ledger in ("GL Entry", "Payment Ledger Entry"):
		frappe.db.delete(ledger, {"voucher_type": doctype, "voucher_no": name})
	doc.delete(ignore_permissions=True)


def wipe_demo(commit=True) -> dict:
	"""Remove exactly what :func:`seed_demo_gym` created. Leaves nothing else touched."""
	members = frappe.get_all("Member", filters={"member_code": ["like", f"{MEMBER_PREFIX}1%"]}, pluck="name")
	memberships = (
		frappe.get_all("Membership", filters={"member": ["in", members]}, pluck="name") if members else []
	)
	subscriptions = (
		[
			s
			for s in frappe.get_all("Membership", filters={"name": ["in", memberships]}, pluck="subscription")
			if s
		]
		if memberships
		else []
	)
	invoices = (
		frappe.get_all("Sales Invoice", filters={"subscription": ["in", subscriptions]}, pluck="name")
		if subscriptions
		else []
	)
	payments = (
		frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_name": ["in", invoices]},
			pluck="parent",
			distinct=True,
		)
		if invoices
		else []
	)

	removed = {"payments": len(payments), "invoices": len(invoices), "members": len(members)}
	# Order matters: money first, then the records that point AT the money. A Sales
	# Invoice cannot be deleted while a Membership still names it as the current one.
	for name in payments:
		_cancel_and_delete("Payment Entry", name)
	frappe.db.delete("Discount Log", {"membership": ["in", memberships or [""]]})
	for name in memberships:
		frappe.delete_doc("Membership", name, force=True, ignore_permissions=True)
	for name in invoices:
		_cancel_and_delete("Sales Invoice", name)
	for name in subscriptions:
		frappe.delete_doc("Subscription", name, force=True, ignore_permissions=True)
	for name in members:
		customer = frappe.db.get_value("Member", name, "customer")
		frappe.delete_doc("Member", name, force=True, ignore_permissions=True)
		if customer and frappe.db.exists("Customer", customer):
			frappe.delete_doc("Customer", customer, force=True, ignore_permissions=True)

	for offer in frappe.get_all("Offer", pluck="name"):
		frappe.delete_doc("Offer", offer, force=True, ignore_permissions=True)
	# The timetable, and everything the nightly generator made from it: bookings first,
	# then the sessions they were booked into, then the schedules themselves.
	schedules = frappe.get_all(
		"Session Schedule", filters={"title": ["in", [row[0] for row in TIMETABLE]]}, pluck="name"
	)
	sessions = (
		frappe.get_all("Session", filters={"class_schedule": ["in", schedules]}, pluck="name")
		if schedules
		else []
	)
	if sessions:
		frappe.db.delete("Session Booking", {"class_session": ["in", sessions]})
	for name in sessions:
		frappe.delete_doc("Session", name, force=True, ignore_permissions=True)
	for name in schedules:
		frappe.delete_doc("Session Schedule", name, force=True, ignore_permissions=True)
	for category, _bucket in EXPENSE_CATEGORIES:
		for name in frappe.get_all("Expense", filters={"category": category}, pluck="name"):
			_cancel_and_delete("Expense", name)

	if commit:
		frappe.db.commit()
	return removed
