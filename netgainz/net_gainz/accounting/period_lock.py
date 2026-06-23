# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Period-lock guard for NetGainz financial postings.

A thin, reusable wrapper over ERPNext's native posting-date guards so every
NetGainz posting path fails the SAME way and as EARLY as possible — before any
voucher is built — instead of only deep inside ``submit()``.

Today the two GL posters (Profit First sweep, coach commission run) already hit
these guards when their Journal Entry is submitted. As Stage 7 adds Sales
Invoice / Payment Entry creators, they should call :func:`assert_postable` up
front so a frozen or closed period is reported clearly at the call site.

The lock itself is ERPNext-native config, not a NetGainz table:
- ``Accounts Settings.acc_frozen_upto`` freezes posting on/before a date for
  anyone without the ``frozen_accounts_modifier`` role.
- A submitted ``Period Closing Voucher`` hard-closes a company's books up to its
  period-end date.
"""

from __future__ import annotations

import frappe


def assert_postable(posting_date, company=None, *, is_opening=False) -> None:
	"""Raise ``frappe.ValidationError`` if a doc dated ``posting_date`` can't post.

	Wraps ERPNext's ``check_freezing_date`` (the ``acc_frozen_upto`` freeze) and,
	when ``company`` is given, ``validate_against_pcv`` (the Period Closing
	Voucher close). Behaviour is identical to the native GL guard — this only
	surfaces it up front, before any voucher is constructed.
	"""
	from erpnext.accounts.general_ledger import check_freezing_date, validate_against_pcv

	check_freezing_date(posting_date)
	if company:
		validate_against_pcv(is_opening, posting_date, company)


def is_period_locked(posting_date, company=None, *, is_opening=False) -> bool:
	"""Non-raising probe: ``True`` if :func:`assert_postable` would throw."""
	try:
		assert_postable(posting_date, company, is_opening=is_opening)
		return False
	except frappe.ValidationError:
		return True
