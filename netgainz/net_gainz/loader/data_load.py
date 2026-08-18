# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Loading a gym's own records into NetGainz, from the owner app.

**Why this exists.** Until now, putting a gym's register into production meant a
developer driving Frappe Desk's Data Import by hand. That breaks the rule the whole
product is built on -- no gym owner ever opens Frappe Desk -- and it means onboarding
gym number two needs a developer. It also produced a class of bug all of its own: the
July invoice file names customers by generated ID (``CUST-2026-00135``), those IDs are
an artifact of the order members were loaded in, and a reload silently repoints every
invoice at the wrong person. Loading server-side removes that by construction: nothing
in a file ever names a generated ID, because the server resolves the links itself.

**What it is.** A thin wrapper around Frappe's own ``Data Import``. Traced live
2026-08-15 (TL-0) before writing a line of this: Data Import already commits per row,
rolls back only the failing row, records what landed, and on a retry skips the rows
that already succeeded. It is the resumable, idempotent loader the plan asked for. So
this module does not parse, insert or post anything itself.

**The one dangerous edge, and the reason for the Data Load Step doctype.** That
idempotency belongs to a *Data Import record*, not to a file. Point a NEW Data Import
at the same file and it re-attempts every row. ``Program`` survives that only because
its name IS its natural key, so the database refuses the duplicates -- ``Sales
Invoice`` and ``Payment Entry`` are named from a series and have no such protection, so
a second import would mint duplicate money. Every step therefore owns exactly one Data
Import record, stored on :class:`Data Load Step`, and a re-upload retries *that* one.

**Order is not a preference.** The member file carries ``membership_plan`` and
``gym_program``, so those masters must exist first or every row fails on a broken link.
Rather than document that and hope, :func:`validate` reads the file, resolves every
link against the database, and names exactly what is missing before anything is
written.

Phase 1 covers masters and members -- programs, plans, people. Nothing here submits a
document or touches the ledger, which is why it can be trusted with a plain upload
button. Memberships, invoices and payments are phase 2 and need their own guards.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

import frappe
from frappe import _
from frappe.utils import now

from netgainz.net_gainz import permissions
from netgainz.net_gainz.accounting import provisioning
from netgainz.net_gainz.accounting.billing import _as_engine

STEP_DOCTYPE = "Data Load Step"

NOT_STARTED = "Not started"
IMPORTING = "Importing"
PARTIAL = "Partial"
COMPLETE = "Complete"
FAILED = "Failed"

# Data Import's own vocabulary -> ours.
_STATUS_MAP = {
	"Pending": IMPORTING,
	"Success": COMPLETE,
	"Partial Success": PARTIAL,
	"Error": FAILED,
	"Timed Out": FAILED,
}


@dataclass(frozen=True)
class Step:
	key: str
	label: str
	doctype: str
	#: Column whose value identifies a row to a human ("KE1003"), used for
	#: duplicate detection and for naming rows in error messages.
	key_column: str
	#: Columns that must carry a value on every row.
	required: tuple[str, ...]
	#: Column -> the doctype it points at. Resolved against the database, which is
	#: what turns "load the masters first" from advice into a refusal.
	links: dict[str, str] = field(default_factory=dict)
	blurb: str = ""


STEPS: tuple[Step, ...] = (
	Step(
		key="programs",
		label="Programs",
		doctype="Program",
		key_column="program_name",
		required=("program_name",),
		blurb="What the gym coaches -- the training programmes members are enrolled on.",
	),
	Step(
		key="plans",
		label="Membership Plans",
		doctype="Membership Plan",
		key_column="plan_name",
		required=(
			"plan_name",
			"duration_in_days",
			"amount",
			"plan_type",
			"billing_mode",
			"payment_due_rule",
		),
		blurb="How the gym charges. A plan with no price still loads -- members can carry their own.",
	),
	Step(
		key="members",
		label="Members",
		doctype="Member",
		key_column="member_code",
		required=("full_name",),
		links={
			"membership_plan": "Membership Plan",
			"gym_program": "Program",
			"coach": "Instructor",
			"branch": "Business Branch",
		},
		blurb="The register. Needs its programs and plans to exist first.",
	),
)

_BY_KEY = {s.key: s for s in STEPS}


def _step(step_key: str) -> Step:
	step = _BY_KEY.get(step_key)
	if not step:
		frappe.throw(_("Unknown load step {0}").format(step_key))
	return step


def _require_owner():
	"""Loading a register is an owner's act, not a front-desk one.

	The whitelisted method is the real permission boundary (WP-8): everything below
	runs as the engine, so this check is what stands between a Gym Staff session and
	the entire member table.
	"""
	# has_role already lets Administrator and System Manager through.
	if not permissions.has_role(permissions.GYM_OWNER):
		frappe.throw(_("Only the gym owner can load data."), frappe.PermissionError)


# ---------------------------------------------------------------- reading a file


def _parse(content: str) -> tuple[list[str], list[dict]]:
	"""CSV text -> (header, rows). Tolerates a UTF-8 BOM, which Excel adds and which
	otherwise turns the first column name into something no mapping matches."""
	if content.startswith("﻿"):
		content = content[1:]
	reader = csv.DictReader(io.StringIO(content))
	header = [h.strip() for h in (reader.fieldnames or [])]
	rows = []
	for raw in reader:
		rows.append({(k or "").strip(): (v or "").strip() for k, v in raw.items()})
	return header, rows


def _problem(rows: list[int], message: str, kind: str = "error") -> dict:
	return {"rows": rows, "message": message, "kind": kind}


def _step_order(doctype: str) -> int:
	"""Where this doctype sits in the load order shown on screen.

	Anything not loaded by a step of its own (Instructor, Business Branch) sorts
	after the ones that are, so the advice always reads in the order the owner is
	being asked to work.
	"""
	for i, s in enumerate(STEPS):
		if s.doctype == doctype:
			return i
	return len(STEPS)


def _already_there(step: Step, row: dict) -> bool:
	"""Is this row already in the register? Cached per request -- 267 rows would
	otherwise mean 267 round trips."""
	key = row.get(step.key_column)
	if not key:
		return False
	cache = frappe.local.netgainz_load_seen = getattr(frappe.local, "netgainz_load_seen", {})
	bucket = cache.setdefault(step.doctype, {})
	if key not in bucket:
		bucket[key] = bool(frappe.db.exists(step.doctype, key))
	return bucket[key]


def _describe(step: Step, row: dict, index: int) -> str:
	"""Name a row the way the owner would: by its code, else its name, else its line."""
	return row.get(step.key_column) or row.get("full_name") or f"row {index}"


# ------------------------------------------------------------------- validation


@frappe.whitelist()
def validate(step_key: str, content: str) -> dict:
	"""Owner/BFF: read a file and report what would go wrong. Writes nothing.

	Data Import has no dry-run of its own -- it either imports or it does not -- so
	this is the safety net, and it deliberately speaks in the gym's language rather
	than Frappe's.
	"""
	_require_owner()
	step = _step(step_key)
	frappe.local.netgainz_load_seen = {}
	header, rows = _parse(content)

	problems: list[dict] = []

	if not header:
		return {
			"ok": False,
			"step": step.key,
			"total_rows": 0,
			"problems": [_problem([], _("That file has no column headings in it."))],
		}

	missing_columns = [c for c in step.required if c not in header]
	if missing_columns:
		problems.append(
			_problem(
				[],
				_("The file is missing {0}: {1}").format(
					_("a required column") if len(missing_columns) == 1 else _("required columns"),
					", ".join(missing_columns),
				),
			)
		)

	if not rows:
		problems.append(_problem([], _("The file has headings but no rows.")))

	# --- per-row required values ------------------------------------------------
	for column in step.required:
		if column in missing_columns:
			continue  # already reported; do not repeat it 267 times
		blank = [i for i, r in enumerate(rows, start=2) if not r.get(column)]
		if blank:
			problems.append(
				_problem(
					blank,
					_("{0} {1} no {2}.").format(
						len(blank),
						_("row has") if len(blank) == 1 else _("rows have"),
						column.replace("_", " "),
					),
				)
			)

	# --- duplicates inside the file ---------------------------------------------
	if step.key_column in header:
		seen: dict[str, int] = {}
		dupes: dict[str, list[int]] = {}
		for i, r in enumerate(rows, start=2):
			key = r.get(step.key_column)
			if not key:
				continue
			if key in seen:
				dupes.setdefault(key, [seen[key]]).append(i)
			else:
				seen[key] = i
		if dupes:
			problems.append(
				_problem(
					sorted({i for v in dupes.values() for i in v}),
					_("The file lists the same {0} more than once: {1}").format(
						step.key_column.replace("_", " "),
						", ".join(sorted(dupes)[:10]) + ("…" if len(dupes) > 10 else ""),
					),
				)
			)

	# --- links: this is the "load the masters first" guard -----------------------
	# Reported in the SAME order as the numbered steps on screen. Dict order put
	# plans before programmes while the screen numbered programmes first, which read
	# as the tool contradicting itself about what to do next.
	link_problems: list[tuple[int, dict]] = []
	for column, target in step.links.items():
		if column not in header:
			continue
		wanted = {r[column] for r in rows if r.get(column)}
		if not wanted:
			continue
		existing = set(frappe.get_all(target, filters={"name": ["in", list(wanted)]}, pluck="name"))
		missing = sorted(wanted - existing)
		if missing:
			rows_hit = [i for i, r in enumerate(rows, start=2) if r.get(column) in missing]
			link_problems.append(
				(
					_step_order(target),
					_problem(
						rows_hit,
						_("{0} {1} named in this file {2} not been created yet: {3}. Load {4} first.").format(
							len(missing),
							_(target.lower()) if len(missing) == 1 else _(target.lower() + "s"),
							_("has") if len(missing) == 1 else _("have"),
							", ".join(missing[:10]) + ("…" if len(missing) > 10 else ""),
							_(target.lower() + "s"),
						),
					),
				)
			)
	problems.extend(p for _rank, p in sorted(link_problems, key=lambda x: x[0]))

	# --- customer naming: the trap that silently drops members -------------------
	# A Member auto-provisions a Customer. If ERPNext is naming Customers by NAME,
	# the customer's ID *is* the person's name, so two members called the same thing
	# collide -- and the collision fails the whole member row, not just the customer.
	# The real 267-row register has five repeated names, so this is not theoretical.
	# The runbook has always said "set this to Naming Series"; relying on a human to
	# remember is exactly what this loader exists to stop.
	if step.doctype == "Member" and "full_name" in header:
		# Read the GLOBAL DEFAULT, which is what ERPNext's Customer.autoname actually
		# consults -- not Selling Settings. The two diverge: the single only reaches
		# the global default when Selling Settings is SAVED, so the screen can read
		# "Naming Series" while customers are still being named after people.
		# Verified live 2026-08-15: global default "Customer Name", single
		# "Naming Series", customers created as "Paul Johnson".
		naming = frappe.defaults.get_global_default("cust_master_name")
		if naming != provisioning.CUSTOMER_NAMING:
			# Only rows that will actually be attempted can collide. A member already
			# in the register is skipped by Data Import, and its customer is its own --
			# counting those turned "5 repeated names" into "134 rows" on a site that
			# was already half-loaded.
			pending = [r for r in rows if not _already_there(step, r)]
			names = [r["full_name"] for r in pending if r.get("full_name")]
			repeated = sorted({n for n in names if names.count(n) > 1})
			clashing = set(frappe.get_all("Customer", filters={"name": ["in", names]}, pluck="name"))
			if repeated or clashing:
				offenders = sorted(set(repeated) | clashing)
				# Information, not an error, and no instruction to go anywhere: `run`
				# corrects the setting itself before importing. The owner is told only
				# because it explains why these names were worth mentioning.
				problems.append(
					_problem(
						[
							i
							for i, r in enumerate(rows, start=2)
							if r.get("full_name") in offenders and not _already_there(step, r)
						],
						_(
							"{0} of these names appear more than once ({1}). That is fine — "
							"the numbering is corrected automatically when you load."
						).format(
							len(offenders),
							", ".join(offenders[:5]) + ("…" if len(offenders) > 5 else ""),
						),
						kind="info",
					)
				)

	# --- rows already in the database -------------------------------------------
	# Not an error. Data Import skips what it already loaded, so a re-upload after a
	# partial load is the normal way to finish the job.
	already = 0
	if step.key_column in header:
		keys = [r[step.key_column] for r in rows if r.get(step.key_column)]
		if keys:
			already = len(frappe.get_all(step.doctype, filters={"name": ["in", keys]}, pluck="name"))
	if already:
		problems.append(
			_problem(
				[],
				_("{0} of these {1} are already loaded and will be left alone.").format(
					already, _(step.label.lower())
				),
				kind="info",
			)
		)

	blocking = [p for p in problems if p["kind"] == "error"]
	return {
		"ok": not blocking,
		"step": step.key,
		"label": step.label,
		"total_rows": len(rows),
		"already_loaded": already,
		"problems": problems,
	}


# ---------------------------------------------------------------------- running


def _get_or_create_step(step: Step):
	if frappe.db.exists(STEP_DOCTYPE, step.key):
		return frappe.get_doc(STEP_DOCTYPE, step.key)
	doc = frappe.new_doc(STEP_DOCTYPE)
	doc.step_key = step.key
	doc.label = step.label
	doc.target_doctype = step.doctype
	doc.status = NOT_STARTED
	doc.insert(ignore_permissions=True)
	return doc


def _attach(step: Step, content: str, filename: str) -> str:
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename or f"{step.key}.csv",
			"is_private": 1,
			"content": content,
		}
	).insert(ignore_permissions=True)
	return file_doc.file_url


@frappe.whitelist()
def run(step_key: str, content: str, filename: str = "") -> dict:
	"""Owner/BFF: load a file. Validates first, then hands it to Data Import.

	Re-uploading is safe and is the intended way to finish a partial load: the step
	keeps its Data Import record, and Data Import skips the rows that already landed.
	"""
	_require_owner()
	step = _step(step_key)

	report = validate(step_key, content)
	if not report["ok"]:
		return {"started": False, "validation": report}

	# Everything in the file is already in the register, so there is nothing to do.
	# Short-circuit rather than start an import: if this step's Data Import record has
	# been lost, a new one re-attempts every row, every row is refused as a duplicate,
	# and the owner is shown a red "Failed" for a file that was in fact complete.
	if report["total_rows"] and report.get("already_loaded") == report["total_rows"]:
		return {
			"started": False,
			"nothing_to_do": True,
			"validation": report,
			"message": _("Every one of these {0} is already loaded. Nothing to do.").format(
				_(step.label.lower())
			),
		}

	# Correct the customer numbering before importing anyone. This is the step that
	# used to be a line in a runbook -- and a line in a runbook gets missed exactly
	# once, silently, at the cost of real members. Only new customers are affected.
	if step.doctype == "Member" and not provisioning.ensure_customer_naming():
		return {
			"started": False,
			"validation": report,
			"error": _(
				"Could not set ERPNext to number customers, so members sharing a name "
				"would be lost. Nothing has been loaded."
			),
		}

	doc = _get_or_create_step(step)
	file_url = _attach(step, content, filename)

	with _as_engine():
		if doc.data_import and frappe.db.exists("Data Import", doc.data_import):
			# Reuse. A fresh Data Import would re-attempt every row -- see the module
			# docstring. Retrying THIS one skips whatever already succeeded.
			di = frappe.get_doc("Data Import", doc.data_import)
			di.import_file = file_url
			di.save(ignore_permissions=True)
		else:
			di = frappe.get_doc(
				{
					"doctype": "Data Import",
					"reference_doctype": step.doctype,
					"import_type": "Insert New Records",
					"import_file": file_url,
					"mute_emails": 1,
				}
			).insert(ignore_permissions=True)

		doc.data_import = di.name
		doc.file_url = file_url
		doc.status = IMPORTING
		doc.total_rows = report["total_rows"]
		doc.last_run = now()
		doc.message = ""
		doc.save(ignore_permissions=True)

		# Commit before starting. Data Import's failure handler calls
		# frappe.db.rollback(), which would otherwise discard the bookkeeping above
		# along with the failed rows -- traced 2026-08-15, it deleted its own record.
		frappe.db.commit()

		try:
			di.start_import()
		except Exception as exc:
			doc.db_set("status", FAILED, update_modified=False)
			doc.db_set("message", str(exc), update_modified=False)
			frappe.db.commit()
			return {"started": False, "validation": report, "error": str(exc)}

	return {"started": True, "validation": report, "status": status(step_key)}


@frappe.whitelist()
def status(step_key: str) -> dict:
	"""Owner/BFF: where a step has got to. Data Import runs as a background job, so
	the screen polls this rather than waiting on :func:`run`."""
	_require_owner()
	step = _step(step_key)

	if not frappe.db.exists(STEP_DOCTYPE, step.key):
		return {
			"step": step.key,
			"label": step.label,
			"status": NOT_STARTED,
			"loaded": frappe.db.count(step.doctype),
		}

	doc = frappe.get_doc(STEP_DOCTYPE, step.key)
	failures: list[dict] = []

	if doc.data_import and frappe.db.exists("Data Import", doc.data_import):
		di_status = frappe.db.get_value("Data Import", doc.data_import, "status")
		logs = frappe.get_all(
			"Data Import Log",
			filters={"data_import": doc.data_import},
			fields=["success", "exception", "row_indexes"],
		)
		imported = sum(1 for log in logs if log.success)
		failed = [log for log in logs if not log.success]
		for log in failed[:20]:
			failures.append({"rows": log.row_indexes, "message": _first_line(log.exception)})
		doc.db_set("imported_rows", imported, update_modified=False)
		doc.db_set("failed_rows", len(failed), update_modified=False)
		doc.db_set("status", _STATUS_MAP.get(di_status, IMPORTING), update_modified=False)

	return {
		"step": step.key,
		"label": step.label,
		"status": doc.status,
		"total_rows": doc.total_rows,
		"imported_rows": doc.imported_rows,
		"failed_rows": doc.failed_rows,
		"last_run": doc.last_run,
		"message": doc.message,
		"failures": failures,
		"loaded": frappe.db.count(step.doctype),
	}


def _first_line(exception: str | None) -> str:
	"""A Frappe traceback is not a message to a gym owner. Take the last line, which
	is where the actual reason lives."""
	if not exception:
		return _("The row was refused.")
	lines = [ln.strip() for ln in exception.strip().splitlines() if ln.strip()]
	return lines[-1] if lines else _("The row was refused.")


@frappe.whitelist()
def get_steps() -> list[dict]:
	"""Owner/BFF: the whole load, in order, with where each step has got to."""
	_require_owner()
	return [
		{
			"key": s.key,
			"label": s.label,
			"blurb": s.blurb,
			"doctype": s.doctype,
			"required_columns": list(s.required),
			**status(s.key),
		}
		for s in STEPS
	]
