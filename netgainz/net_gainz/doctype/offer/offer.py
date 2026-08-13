# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 8 DS-2: an Offer is a campaign the gym runs — in gym language.

The owner writes "New Year 20%, monthly plans, runs to 31 Jan, first 50 members".
Everything else (how it reaches an invoice, how it ends, how it is counted) is the
app's problem. See ``accounting/offers.py`` for how a live offer becomes a
membership's discount, and why it is not an ERPNext Pricing Rule.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate

from netgainz.net_gainz.accounting import discounts, offers


class Offer(Document):
	def validate(self):
		self.offer_name = (self.offer_name or "").strip()
		if not self.offer_name:
			frappe.throw("Give the offer a name — it is what the desk will look for.")

		value = flt(self.discount_value)
		if value <= 0:
			frappe.throw("An offer needs a discount above zero.")
		if self.discount_type == discounts.PERCENTAGE and value > discounts.MAX_PERCENTAGE:
			frappe.throw("An offer cannot be more than 100% off.")

		if self.valid_upto and getdate(self.valid_upto) < getdate(self.valid_from):
			frappe.throw("The offer cannot end before it starts.")
		if self.discount_duration == offers.UNTIL_OFFER_ENDS and not self.valid_upto:
			frappe.throw(
				"An offer that applies 'Until the offer ends' needs an end date — "
				"otherwise it never ends, which is 'Every invoice'."
			)
		# DS-3: the code is what a member quotes at the desk, so it is normalised once
		# here and matched exactly everywhere else.
		self.coupon_code = offers.normalise_code(self.coupon_code)
		if self.coupon_code:
			clash = frappe.db.get_value(
				"Offer", {"coupon_code": self.coupon_code, "name": ("!=", self.name)}, "name"
			)
			if clash:
				frappe.throw(f"The code '{self.coupon_code}' is already used by the offer '{clash}'.")
		if flt(self.max_uses_per_member) < 0:
			frappe.throw("A per-member limit cannot be negative. Use 0 for no limit.")

		if flt(self.max_total_uses) < 0:
			frappe.throw("A limit cannot be negative. Use 0 for no limit.")

		# The limit may be lowered, but never below what has already been given out —
		# that would make the count read as exhausted-and-overdrawn for ever.
		used = offers.times_used(self.name) if not self.is_new() else 0
		if self.max_total_uses and used > int(self.max_total_uses):
			frappe.throw(
				f"This offer has already been given to {used} members. "
				f"Set the limit to {used} or more, or end the offer instead."
			)
