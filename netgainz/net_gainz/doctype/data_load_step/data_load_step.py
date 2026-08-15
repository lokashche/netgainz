# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class DataLoadStep(Document):
	"""Bookkeeping for one step of the tenant data load.

	It holds no logic. Its only job is to remember which ``Data Import`` record
	belongs to which step, because that is what makes a retry safe -- see
	``net_gainz/loader/data_load.py`` for why a second Data Import is dangerous.
	"""

	pass
