# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 8 DS-5: the record of every discount given, changed or taken away.

Read-only and written only by :mod:`netgainz.net_gainz.accounting.discounts`. It exists
because the membership shows only the discount a member has *now* — the owner also needs
to see that a 10% rate quietly became 30% last month, who did it, why, and whether it was
approved. DS-6 reports from these rows.
"""

from frappe.model.document import Document


class DiscountLog(Document):
	pass
