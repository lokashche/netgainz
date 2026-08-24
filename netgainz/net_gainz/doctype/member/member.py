# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class Member(Document):
	def autoname(self):
		# Preserve an explicitly supplied member code (e.g. the gym's existing
		# KE#### register imported from their spreadsheet) as the record ID.
		# Otherwise generate the next ID from the owner-configurable prefix and
		# mirror it back onto member_code so the two always match.
		if self.member_code:
			self.name = self.member_code
			return
		prefix = frappe.db.get_single_value("Business Settings", "member_id_prefix") or "MEM-"
		_continue_after_register(prefix)
		self.name = make_autoname(f"{prefix}.####")
		self.member_code = self.name


def _continue_after_register(prefix: str):
	"""Start the ID counter after the register's highest code, never at 0001.

	An imported member carries its own code (KE1267) straight into ``name``, which
	never touches the series counter -- so the first member added through the app
	would come out as KE0001 while the register already runs to KE1267. Raise the
	counter to the highest numeric code on file before drawing the next one.
	"""
	row = frappe.db.sql(
		"""select max(cast(substring(name, %s) as unsigned)) from `tabMember`
		where name like %s and substring(name, %s) regexp '^[0-9]+$'""",
		(len(prefix) + 1, prefix + "%", len(prefix) + 1),
	)
	highest = int(row[0][0] or 0) if row else 0
	if not highest:
		return
	# The series key for "<prefix>.####" is the prefix itself (parse_naming_series
	# passes the accumulated prefix to getseries). One atomic statement: create the
	# counter at `highest`, or raise it if it is behind -- never lower it, so an
	# already-advanced counter is left alone.
	frappe.db.sql(
		"""insert into `tabSeries` (name, current) values (%s, %s)
		on duplicate key update current = greatest(current, %s)""",
		(prefix, highest, highest),
	)
