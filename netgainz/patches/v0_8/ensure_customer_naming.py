# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt
"""Number Customers rather than naming them after the member.

New sites get this from ``after_install``. Existing sites -- including every tenant
already live -- need it applied once, because ERPNext ships with "Customer Name" and
a repeated member name is silently dropped during an import.

Only affects customers created from now on. Existing customers keep the names they
have; renaming them would rewrite history for no benefit.
"""

from netgainz.net_gainz.accounting.provisioning import ensure_customer_naming


def execute():
	ensure_customer_naming()
