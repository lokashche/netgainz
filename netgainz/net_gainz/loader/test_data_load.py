# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""TL-1 phase 1: loading a gym's masters and register from the owner app.

Pinned:

* the loader **wraps** Frappe's Data Import and never inserts a row itself, so what
  is tested here is the wrapping: validation, ordering, and retry safety;
* **a step owns ONE Data Import record.** This is the whole ballgame. Idempotency
  belongs to a Data Import record, not to a file -- a second record over the same
  file re-attempts every row, which for series-named doctypes mints duplicates. A
  re-upload must reuse the step's existing record;
* **order is enforced, not documented.** A member file naming a plan or programme
  that does not exist yet is refused, and the refusal names the missing ones;
* validation writes nothing -- it is the dry run Data Import does not have;
* rows already loaded are reported as information, not as an error, because
  re-uploading is how a partial load is finished;
* a blank required value, a missing column and a duplicated key are each caught
  before anything is written;
* loading the register is the owner's act: a Gym Staff session is refused
  (exercised as a real session -- as Administrator it would pass vacuously).

``run`` commits by design (Data Import's failure handler rolls back, and would
otherwise discard the loader's own bookkeeping), so committed artefacts outlive
FrappeTestCase's per-test rollback and are cleared explicitly.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.loader import data_load

PROGRAMS_CSV = "program_name,is_active\nTL Strength,1\nTL Mobility,1\n"

PLANS_CSV = (
	"plan_name,duration_in_days,amount,is_active,plan_type,billing_mode,payment_due_rule\n"
	"TL Monthly,30,1000,1,Monthly,Commitment,On joining\n"
)

MEMBERS_CSV = (
	"member_code,full_name,membership_plan,gym_program\n"
	"TL0001,Loader One,TL Monthly,TL Strength\n"
	"TL0002,Loader Two,TL Monthly,TL Mobility\n"
)


def _clear():
	"""Remove everything the loader commits, plus the rows it created."""
	for name in frappe.get_all("Data Load Step", pluck="name"):
		doc = frappe.db.get_value("Data Load Step", name, "data_import")
		if doc:
			frappe.db.delete("Data Import Log", {"data_import": doc})
			frappe.db.delete("Data Import", {"name": doc})
		frappe.db.delete("Data Load Step", {"name": name})
	# Member has no on_trash, so deleting one leaves its auto-provisioned Customer
	# behind. Under "Customer Name" naming -- which the test fixtures use -- that
	# orphan then collides with the next run and fails the whole member row.
	for name in frappe.get_all("Member", filters={"name": ["like", "TL%"]}, pluck="name"):
		customer = frappe.db.get_value("Member", name, "customer")
		frappe.delete_doc("Member", name, force=True, ignore_permissions=True)
		if customer and frappe.db.exists("Customer", customer):
			frappe.delete_doc("Customer", customer, force=True, ignore_permissions=True)
	for name in frappe.get_all("Customer", filters={"name": ["like", "Loader %"]}, pluck="name"):
		frappe.delete_doc("Customer", name, force=True, ignore_permissions=True)
	for dt, like in (("Membership Plan", "TL %"), ("Program", "TL %")):
		for name in frappe.get_all(dt, filters={"name": ["like", like]}, pluck="name"):
			frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
	frappe.db.delete("File", {"file_name": ["like", "tl_%"]})
	frappe.db.commit()


class TestDataLoad(FrappeTestCase):
	def setUp(self):
		_clear()

	def tearDown(self):
		_clear()

	# ------------------------------------------------------------- validation

	def test_missing_required_column_is_refused(self):
		report = data_load.validate("plans", "plan_name,amount\nTL Monthly,1000\n")
		self.assertFalse(report["ok"])
		blocking = " ".join(p["message"] for p in report["problems"] if p["kind"] == "error")
		self.assertIn("duration_in_days", blocking)
		self.assertIn("billing_mode", blocking)

	def test_blank_required_value_is_refused_and_counted(self):
		csv = "program_name,is_active\nTL Strength,1\n,1\n"
		report = data_load.validate("programs", csv)
		self.assertFalse(report["ok"])
		problem = next(p for p in report["problems"] if p["kind"] == "error")
		# Row 3 of the file (header is row 1), named so the owner can go and look.
		self.assertEqual(problem["rows"], [3])

	def test_duplicate_key_inside_the_file_is_refused(self):
		csv = "program_name,is_active\nTL Strength,1\nTL Strength,1\n"
		report = data_load.validate("programs", csv)
		self.assertFalse(report["ok"])
		self.assertTrue(
			any("more than once" in p["message"] for p in report["problems"])
		)

	def test_empty_file_is_refused(self):
		self.assertFalse(data_load.validate("programs", "")["ok"])
		self.assertFalse(data_load.validate("programs", "program_name,is_active\n")["ok"])

	def test_validation_writes_nothing(self):
		before = frappe.db.count("Program")
		data_load.validate("programs", PROGRAMS_CSV)
		self.assertEqual(frappe.db.count("Program"), before)
		self.assertFalse(frappe.db.exists("Data Load Step", "programs"))

	# ------------------------------------------------------------------ order

	def test_members_refused_when_their_programs_do_not_exist(self):
		"""The guard that replaces 'remember to load the masters first'."""
		report = data_load.validate("members", MEMBERS_CSV)
		self.assertFalse(report["ok"])
		messages = " ".join(p["message"] for p in report["problems"] if p["kind"] == "error")
		self.assertIn("TL Monthly", messages)
		self.assertIn("TL Strength", messages)
		self.assertIn("TL Mobility", messages)

	def test_members_accepted_once_the_masters_are_there(self):
		self._load_masters()
		report = data_load.validate("members", MEMBERS_CSV)
		self.assertTrue(report["ok"], report["problems"])
		self.assertEqual(report["total_rows"], 2)

	def test_run_refuses_and_writes_nothing_when_validation_fails(self):
		result = data_load.run("members", MEMBERS_CSV, "tl_members.csv")
		self.assertFalse(result["started"])
		self.assertFalse(frappe.db.exists("Data Load Step", "members"))
		self.assertEqual(frappe.db.count("Member", {"name": ["like", "TL%"]}), 0)

	# ------------------------------------------------------------------- runs

	def test_programs_load(self):
		result = data_load.run("programs", PROGRAMS_CSV, "tl_programs.csv")
		self.assertTrue(result["started"], result)
		self.assertTrue(frappe.db.exists("Program", "TL Strength"))
		self.assertTrue(frappe.db.exists("Program", "TL Mobility"))
		self.assertEqual(data_load.status("programs")["status"], data_load.COMPLETE)

	def test_reupload_reuses_the_same_data_import_and_does_not_duplicate(self):
		"""The money-safety test, in miniature.

		A fresh Data Import over the same file re-attempts every row. Programs are
		saved from duplication only by their own natural key -- a Sales Invoice,
		named from a series, would be minted twice. So what is pinned is that the
		step keeps ONE Data Import record across re-uploads.
		"""
		data_load.run("programs", PROGRAMS_CSV, "tl_programs.csv")
		first = frappe.db.get_value("Data Load Step", "programs", "data_import")
		count_after_first = frappe.db.count("Program", {"name": ["like", "TL %"]})

		data_load.run("programs", PROGRAMS_CSV, "tl_programs.csv")
		second = frappe.db.get_value("Data Load Step", "programs", "data_import")

		self.assertEqual(first, second, "a re-upload must not start a new Data Import")
		self.assertEqual(
			frappe.db.count("Program", {"name": ["like", "TL %"]}), count_after_first
		)
		self.assertEqual(frappe.db.count("Data Import", {"reference_doctype": "Program"}), 1)

	def test_already_loaded_rows_are_information_not_an_error(self):
		data_load.run("programs", PROGRAMS_CSV, "tl_programs.csv")
		report = data_load.validate("programs", PROGRAMS_CSV)
		self.assertTrue(report["ok"], "re-uploading is how a partial load is finished")
		self.assertEqual(report["already_loaded"], 2)
		self.assertTrue(any(p["kind"] == "info" for p in report["problems"]))

	def test_members_load_with_their_links_resolved(self):
		self._load_masters()
		data_load.run("members", MEMBERS_CSV, "tl_members.csv")
		self.assertTrue(frappe.db.exists("Member", "TL0001"))
		self.assertEqual(
			frappe.db.get_value("Member", "TL0001", "membership_plan"), "TL Monthly"
		)
		self.assertEqual(frappe.db.get_value("Member", "TL0002", "gym_program"), "TL Mobility")

	def test_repeated_names_refused_when_customers_are_named_after_people(self):
		"""Runbook step 4.3, enforced instead of remembered.

		A Member auto-provisions a Customer. Under "Customer Name" naming the
		customer's ID IS the person's name, so a repeated name collides -- and the
		collision fails the whole member row, losing the member. The real 267-row
		register carries five repeated names, so this had to become a guard.
		"""
		self._load_masters()
		# The global default is what ERPNext consults, and it is NOT the single.
		before = frappe.defaults.get_global_default("cust_master_name")
		frappe.db.set_default("cust_master_name", "Customer Name")
		try:
			twins = (
				"member_code,full_name,membership_plan,gym_program\n"
				"TL0003,Loader Twin,TL Monthly,TL Strength\n"
				"TL0004,Loader Twin,TL Monthly,TL Strength\n"
			)
			report = data_load.validate("members", twins)
			self.assertFalse(report["ok"])
			messages = " ".join(p["message"] for p in report["problems"] if p["kind"] == "error")
			self.assertIn("Loader Twin", messages)
			self.assertIn("Naming Series", messages)
		finally:
			frappe.db.set_default("cust_master_name", before or "")

	def test_repeated_names_are_fine_under_naming_series(self):
		self._load_masters()
		before = frappe.defaults.get_global_default("cust_master_name")
		frappe.db.set_default("cust_master_name", "Naming Series")
		try:
			twins = (
				"member_code,full_name,membership_plan,gym_program\n"
				"TL0003,Loader Twin,TL Monthly,TL Strength\n"
				"TL0004,Loader Twin,TL Monthly,TL Strength\n"
			)
			self.assertTrue(data_load.validate("members", twins)["ok"])
		finally:
			frappe.db.set_default("cust_master_name", before or "")

	def test_naming_guard_ignores_members_already_loaded(self):
		"""A member already in the register is skipped, so their customer is not a
		clash. Without this the guard flagged 134 rows on a half-loaded site."""
		self._load_masters()
		data_load.run("members", MEMBERS_CSV, "tl_members.csv")
		before = frappe.defaults.get_global_default("cust_master_name")
		frappe.db.set_default("cust_master_name", "Customer Name")
		try:
			report = data_load.validate("members", MEMBERS_CSV)
			blocking = [p for p in report["problems"] if p["kind"] == "error"]
			self.assertEqual(blocking, [], "already-loaded members must not be flagged")
			self.assertTrue(report["ok"])
		finally:
			frappe.db.set_default("cust_master_name", before or "")

	# ------------------------------------------------------------------ shape

	def test_get_steps_is_in_load_order(self):
		self.assertEqual(
			[s["key"] for s in data_load.get_steps()], ["programs", "plans", "members"]
		)

	def test_status_of_an_untouched_step(self):
		state = data_load.status("members")
		self.assertEqual(state["status"], data_load.NOT_STARTED)

	def test_unknown_step_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			data_load.validate("invoices", PROGRAMS_CSV)

	# ------------------------------------------------------------ permissions

	def test_gym_staff_may_not_load_data(self):
		user = _staff_user()
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				data_load.get_steps()
			with self.assertRaises(frappe.PermissionError):
				data_load.run("programs", PROGRAMS_CSV, "tl_programs.csv")
		finally:
			frappe.set_user("Administrator")

	# ----------------------------------------------------------------- helper

	def _load_masters(self):
		data_load.run("programs", PROGRAMS_CSV, "tl_programs.csv")
		data_load.run("plans", PLANS_CSV, "tl_plans.csv")


def _staff_user() -> str:
	email = "tl-staff@example.com"
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = "TL Staff"
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
		user.add_roles("Gym Staff")
	return email
