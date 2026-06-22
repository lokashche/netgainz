# Copyright (c) 2026, Quantslate Solutions and contributors
# For license information, please see license.txt


def before_tests():
	"""Set up a complete ERPNext company before NetGainz tests run.

	NetGainz' Profit First sweeps and coach-commission runs post to ERPNext
	(Company, Account, Cost Center, Journal Entry). `bench run-tests --app
	netgainz` only runs THIS app's before_tests hook, so ERPNext's own test
	setup — which runs the setup wizard to create the test Company plus standard
	records like the "Transit" Warehouse Type — never runs unless we invoke it
	here. Without it, creating any Company in the test site fails with
	"Could not find Warehouse Type: Transit".
	"""
	from erpnext.setup.utils import before_tests as erpnext_before_tests

	erpnext_before_tests()
