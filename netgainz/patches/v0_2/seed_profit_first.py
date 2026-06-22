from netgainz.net_gainz.profit_first.seed import seed_profit_first_defaults


def execute():
	"""Seed the Profit First accounts + tier bands on existing sites (fresh sites
	are seeded by the after_install hook). Idempotent — only fills empty tables."""
	seed_profit_first_defaults()
