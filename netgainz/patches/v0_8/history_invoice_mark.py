# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 12.2: add Sales Invoice.membership, the mark on a loaded-history invoice.

Every cash and billed read now names this column, so it must exist on every site."""

from netgainz.net_gainz.loader.history_books import ensure_invoice_mark


def execute():
	ensure_invoice_mark()
