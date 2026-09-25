# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Stage 10.1: flag the existing "Main" branch as the default.

Before 10.1 the default branch was found by its name. It is now found by the
``is_default`` flag so the owner can rename it to the real location. Every site that
already has a "Main" branch gets the flag on it once; a site with no branch yet is
left alone (the default is seeded on first use).
"""

from netgainz.net_gainz.accounting import branch


def execute():
	company = branch._company()
	if company:
		branch.ensure_default_branch(company)
