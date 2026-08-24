# Copyright (c) 2026, Quantslate Solutions and Contributors
# See license.txt
"""Tests for the Stage 7 WP-2 master provisioner (Member->Customer,
Membership Plan->Item/Item Price/Subscription Plan).

Exercises both the doc_events path (insert a record -> masters appear) and the
provisioning functions directly (idempotency, best-effort skips). Runs on an
India company with india_compliance installed, where SAC 999723 exists as a
GST HSN Code (so a sellable Item can be created).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from netgainz.net_gainz.accounting import provisioning

SAC = "999723"


class TestProvisioning(FrappeTestCase):
	def _make_member(self, full_name):
		doc = frappe.get_doc({"doctype": "Member", "full_name": full_name})
		doc.insert(ignore_permissions=True)
		return doc

	def _make_plan(self, plan_name, *, amount=1000.0, duration=30, sac=None):
		doc = frappe.get_doc(
			{
				"doctype": "Membership Plan",
				"plan_name": plan_name,
				"duration_in_days": duration,
				"amount": amount,
				"gst_hsn_code": sac,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	# ---- Member -> Customer ---------------------------------------------- #
	def test_inserting_member_provisions_customer(self):
		member = self._make_member("WP2 Member Alpha")
		self.assertTrue(member.customer, "doc_events should have linked a Customer")
		self.assertTrue(frappe.db.exists("Customer", member.customer))
		customer = frappe.get_doc("Customer", member.customer)
		self.assertEqual(customer.customer_name, "WP2 Member Alpha")
		self.assertEqual(customer.customer_type, "Individual")
		self.assertTrue(customer.customer_group)
		self.assertTrue(customer.territory)

	def test_provision_customer_is_idempotent(self):
		member = self._make_member("WP2 Member Beta")
		first = member.customer
		self.assertTrue(first)
		before = frappe.db.count("Customer")
		again = provisioning.provision_customer(member.name)
		self.assertEqual(again, first)
		self.assertEqual(frappe.db.count("Customer"), before, "no duplicate Customer")

	# ---- Membership Plan -> Item + Item Price + Subscription Plan --------- #
	def test_plan_with_sac_provisions_item_price_and_subscription_plan(self):
		plan = self._make_plan("WP2 Plan Quarterly", amount=4500.0, duration=90, sac=SAC)
		plan.reload()
		self.assertTrue(plan.item, "Item should be provisioned")
		self.assertTrue(plan.subscription_plan, "Subscription Plan should be provisioned")

		item = frappe.get_doc("Item", plan.item)
		self.assertEqual(item.is_stock_item, 0)
		self.assertEqual(item.is_sales_item, 1)
		self.assertEqual(item.gst_hsn_code, SAC)

		price_list = provisioning._selling_price_list()
		rate = frappe.db.get_value(
			"Item Price", {"item_code": plan.item, "price_list": price_list}, "price_list_rate"
		)
		self.assertEqual(rate, 4500.0)

		sub = frappe.get_doc("Subscription Plan", plan.subscription_plan)
		self.assertEqual(sub.price_determination, "Based On Price List")
		self.assertEqual(sub.item, plan.item)
		self.assertEqual(sub.price_list, price_list)
		# 90 days -> Month x 3 (never a fraction of a Year).
		self.assertEqual(sub.billing_interval, "Month")
		self.assertEqual(sub.billing_interval_count, 3)

	def test_plan_without_sac_gets_the_tenant_default_and_provisions(self):
		"""WP-10 fix: a plan created WITHOUT a tax code (which is every plan the
		owner app creates — it never asks for one, and shouldn't) now inherits the
		tenant default, so it provisions and can bill. Previously it silently got
		no Item and no Subscription Plan, i.e. it could not be billed at all."""
		plan = self._make_plan("WP2 Plan No SAC", amount=1000.0, duration=30, sac=None)
		plan.reload()
		self.assertTrue(plan.gst_hsn_code, "the tenant default tax code is applied")
		self.assertTrue(plan.item, "so a sellable Item is provisioned")
		self.assertTrue(plan.subscription_plan, "and billing can happen")

	def test_provision_item_still_skips_when_no_code_can_be_resolved(self):
		"""The defensive skip in provision_item stays: if a plan somehow has no
		code (default cleared, or a legacy row), provisioning must skip rather than
		throw — india_compliance rejects a sellable Item without an HSN/SAC."""
		plan = self._make_plan("WP2 Plan Forced No SAC", amount=1000.0, duration=30, sac=None)
		# Bypass the controller default to reach the skip path.
		frappe.db.set_value("Membership Plan", plan.name, "gst_hsn_code", None, update_modified=False)
		frappe.db.set_value("Membership Plan", plan.name, "item", None, update_modified=False)
		plan.reload()
		self.assertIsNone(provisioning.provision_item(plan))

	def test_amount_change_resyncs_item_price(self):
		plan = self._make_plan("WP2 Plan Reprice", amount=1000.0, duration=30, sac=SAC)
		price_list = provisioning._selling_price_list()
		plan.amount = 1750.0
		plan.save(ignore_permissions=True)
		rate = frappe.db.get_value(
			"Item Price", {"item_code": plan.item, "price_list": price_list}, "price_list_rate"
		)
		self.assertEqual(rate, 1750.0)
		# Still a single canonical price row, not a stacked duplicate.
		self.assertEqual(frappe.db.count("Item Price", {"item_code": plan.item, "price_list": price_list}), 1)

	def test_provision_plan_is_idempotent(self):
		plan = self._make_plan("WP2 Plan Idem", amount=1200.0, duration=365, sac=SAC)
		plan.reload()
		item, sub = plan.item, plan.subscription_plan
		self.assertTrue(item and sub)
		before_items = frappe.db.count("Item", {"item_code": item})
		before_subs = frappe.db.count("Subscription Plan", {"name": sub})
		result = provisioning.provision_plan(plan.name)
		self.assertEqual(result["item"], item)
		self.assertEqual(result["subscription_plan"], sub)
		self.assertEqual(frappe.db.count("Item", {"item_code": item}), before_items)
		self.assertEqual(frappe.db.count("Subscription Plan", {"name": sub}), before_subs)
		# Annual plan maps to Year x 1.
		annual = frappe.get_doc("Subscription Plan", sub)
		self.assertEqual((annual.billing_interval, annual.billing_interval_count), ("Year", 1))

	# ---- renaming a plan -------------------------------------------------- #
	def test_rename_plan_moves_the_item_and_every_link(self):
		plan = self._make_plan("WP2 Rename Before", amount=900.0, duration=30, sac=SAC)
		plan.reload()
		self.assertTrue(plan.item)
		member = self._make_member("WP2 Rename Member")
		member.db_set("membership_plan", plan.name, update_modified=False)

		new_name = provisioning.rename_plan(plan.name, "WP2 Rename After")

		self.assertEqual(new_name, "WP2 Rename After")
		self.assertTrue(frappe.db.exists("Membership Plan", "WP2 Rename After"))
		self.assertFalse(frappe.db.exists("Membership Plan", "WP2 Rename Before"))
		# The autoname field follows the document ID.
		self.assertEqual(
			frappe.db.get_value("Membership Plan", "WP2 Rename After", "plan_name"),
			"WP2 Rename After",
		)
		# The invariant provision_item relies on: Item code == plan name.
		self.assertTrue(frappe.db.exists("Item", "WP2 Rename After"))
		self.assertFalse(frappe.db.exists("Item", "WP2 Rename Before"))
		self.assertEqual(
			frappe.db.get_value("Membership Plan", "WP2 Rename After", "item"),
			"WP2 Rename After",
		)
		# Links from other records follow.
		self.assertEqual(
			frappe.db.get_value("Member", member.name, "membership_plan"),
			"WP2 Rename After",
		)

	def test_rename_plan_refuses_a_name_already_taken(self):
		self._make_plan("WP2 Rename Taken", sac=SAC)
		plan = self._make_plan("WP2 Rename Clash", sac=SAC)
		with self.assertRaises(frappe.ValidationError):
			provisioning.rename_plan(plan.name, "WP2 Rename Taken")

	# ---- backfill patch -------------------------------------------------- #
	def test_backfill_patch_seeds_sac_and_provisions(self):
		from netgainz.patches.v0_7 import backfill_masters

		# A member whose customer link we clear, simulating a pre-WP-2 row.
		member = self._make_member("WP2 Backfill Member")
		frappe.db.set_value("Member", member.name, "customer", None, update_modified=False)
		# A legacy plan with no SAC and no Item (pre-WP-2 shape). The controller now
		# defaults the code, so strip both fields directly to recreate that state.
		plan = self._make_plan("WP2 Backfill Plan", amount=3000.0, duration=30, sac=None)
		frappe.db.set_value(
			"Membership Plan",
			plan.name,
			{"gst_hsn_code": None, "item": None, "subscription_plan": None},
			update_modified=False,
		)
		plan.reload()
		self.assertFalse(plan.item)

		backfill_masters.execute()

		self.assertTrue(frappe.db.get_value("Member", member.name, "customer"), "backfill links a Customer")
		plan.reload()
		self.assertEqual(
			plan.gst_hsn_code, backfill_masters.DEFAULT_PILOT_SAC, "backfill seeds the default SAC"
		)
		self.assertTrue(plan.item, "backfill provisions the Item once a SAC is seeded")
		self.assertTrue(plan.subscription_plan)
