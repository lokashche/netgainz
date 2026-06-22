# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Seed the per-gym Profit First defaults into the Profit First Settings Single.

A Single ships empty, so a freshly provisioned gym site has no PF accounts and
no tier bands and the Instant Assessment would show blank targets. This runs
from ``after_install`` (fresh sites) and from a post_model_sync patch (existing
sites). It is idempotent: it only fills child tables that are currently empty,
so it never clobbers a gym's localised configuration on re-run.
"""

import frappe

# The five canonical Profit First accounts. Income is the 100% reference; the
# other four are allocation buckets.
PF_ACCOUNTS = [
	("Income", "Income"),
	("Profit", "Profit"),
	("Owner's Pay", "Owner's Pay"),
	("Tax", "Tax"),
	("Operating Expenses", "Operating Expenses"),
]

# Canonical Michalowicz TAP tiers. The rupee bands are placeholder conversions
# of the book's USD bands and are meant to be localised per gym; the percentages
# are the methodology defaults. Each row's four TAPs sum to 100.
# (tier_code, rr_lower, tap_profit, tap_owners_pay, tap_tax, tap_opex)
PF_TIERS = [
	("A", 0, 5, 50, 15, 30),
	("B", 250000, 10, 35, 15, 40),
	("C", 500000, 15, 20, 15, 50),
	("D", 1000000, 10, 10, 15, 65),
	("E", 5000000, 15, 5, 15, 65),
	("F", 10000000, 20, 0, 15, 65),
]


def seed_profit_first_defaults():
	"""Idempotently seed the 5 accounts + 6 tier bands. Returns True if it wrote."""
	settings = frappe.get_single("Profit First Settings")
	changed = False

	if not settings.accounts:
		for role, label in PF_ACCOUNTS:
			settings.append("accounts", {"account_role": role, "account_label": label})
		changed = True

	if not settings.tiers:
		for code, lower, profit, owners_pay, tax, opex in PF_TIERS:
			settings.append(
				"tiers",
				{
					"tier_code": code,
					"rr_lower": lower,
					"tap_profit": profit,
					"tap_owners_pay": owners_pay,
					"tap_tax": tax,
					"tap_opex": opex,
				},
			)
		changed = True

	if changed:
		settings.save(ignore_permissions=True)
	return changed


def after_install():
	seed_profit_first_defaults()
