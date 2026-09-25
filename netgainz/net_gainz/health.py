# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 12.7 — is this site healthy? Answered for the uptime check.

A scheduled GitHub workflow (``.github/workflows/uptime.yml``) calls this every 15
minutes and fails when it says "not ok"; GitHub then emails the repo owner. That is
the whole alerting path: no mail server, no monitoring account, nothing to set up
per site.

Two things are checked, because both fail SILENTLY today:

* **background errors** — best-effort paths (billing provisioning, reminders) log an
  Error Log and carry on, so a member can quietly stop being billed and nobody sees
  it. Any Error Log in the last ``minutes`` fails the check;
* **the scheduler** — every daily job (sweeps, renewals, dues, recurring expenses)
  stops if it is off or stuck, again with no symptom on any screen.

Open to guests on purpose: it reveals a yes/no and a count, never what the errors
were. The operator reads those in the Error Log.
"""

import frappe
from frappe.utils import add_to_date, cint, now_datetime

# The scheduler's own frequent jobs run every few minutes; an hour of silence means
# it has stopped even though it reads "enabled".
SCHEDULER_SILENT_MINUTES = 60


@frappe.whitelist(allow_guest=True)
def check(minutes=30) -> dict:
	minutes = min(max(cint(minutes) or 30, 5), 24 * 60)
	since = add_to_date(now_datetime(), minutes=-minutes)
	errors = frappe.db.count("Error Log", {"creation": [">=", since]})

	from frappe.utils.scheduler import is_scheduler_inactive

	last_run = frappe.db.get_value("Scheduled Job Log", {}, "max(creation)")
	scheduler_on = not is_scheduler_inactive(verbose=False)
	scheduler_running = bool(
		last_run and last_run >= add_to_date(now_datetime(), minutes=-SCHEDULER_SILENT_MINUTES)
	)
	problems = []
	if errors:
		problems.append(f"{errors} background error(s) in the last {minutes} minutes")
	if not scheduler_on:
		problems.append("scheduled jobs are switched off")
	elif not scheduler_running:
		problems.append(f"no scheduled job has run in {SCHEDULER_SILENT_MINUTES} minutes")
	return {"ok": not problems, "problems": problems}
