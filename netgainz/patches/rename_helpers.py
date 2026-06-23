# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Reusable helpers for DocType-rename migration patches (Stage 7 WP-1).

Stage 7 renames several NetGainz DocTypes to vertical-neutral names
(Subscription -> Membership, Coach -> Instructor, Gym Expense -> Expense,
Gym Settings -> Business Settings, Class Session -> Session, ...). Each rename is
two halves:

1. On-disk source moves (folder, JSON ``name``, controller class + imports,
   series prefixes, tests) — made by hand at authoring time.
2. The database rename — done at migrate time by a ``v0_7`` patch that calls
   :func:`rename_doctype` below.

Keep all the runtime rename mechanics here so the per-rename patch stays a thin,
idempotent list of calls.
"""

from __future__ import annotations

import frappe


def rename_doctype(old: str, new: str) -> bool:
	"""Idempotently rename DocType ``old`` to ``new`` at the database level.

	Returns ``True`` if the rename happened, ``False`` if it was a no-op (``old``
	already gone or ``new`` already present) — so the patch is safe to re-run.

	``force=True`` is required because these are app-owned (not Custom) DocTypes.
	``frappe.rename_doc`` renames ``tab<old>`` -> ``tab<new>`` and rewrites child
	rows, link / dynamic-link fields and the naming series. We then evict the
	cached column list for both table names so any later ``has_column`` check in
	the same ``bench migrate`` run doesn't read a stale Redis snapshot — the same
	hazard the v0_1 column-drop patches documented.
	"""
	if not frappe.db.exists("DocType", old):
		return False
	if frappe.db.exists("DocType", new):
		return False

	frappe.rename_doc("DocType", old, new, force=True)

	for table in (f"tab{old}", f"tab{new}"):
		frappe.cache.hdel("table_columns", table)

	return True
