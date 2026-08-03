app_name = "netgainz"
app_title = "Net Gainz"
app_publisher = "Quantslate Solutions"
app_description = "Gym Accounting Application"
app_email = "lokash@quantslate.com"
app_license = "agpl-3.0"

# Apps
# ------------------

required_apps = ["erpnext", "india_compliance"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "netgainz",
# 		"logo": "/assets/netgainz/logo.png",
# 		"title": "Net Gainz",
# 		"route": "/netgainz",
# 		"has_permission": "netgainz.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/netgainz/css/netgainz.css"
# app_include_js = "/assets/netgainz/js/netgainz.js"

# include js, css files in header of web template
# web_include_css = "/assets/netgainz/css/netgainz.css"
# web_include_js = "/assets/netgainz/js/netgainz.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "netgainz/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "netgainz/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "netgainz.utils.jinja_methods",
# 	"filters": "netgainz.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "netgainz.install.before_install"
after_install = "netgainz.net_gainz.profit_first.seed.after_install"

# Uninstallation
# ------------

# before_uninstall = "netgainz.uninstall.before_uninstall"
# after_uninstall = "netgainz.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "netgainz.utils.before_app_install"
# after_app_install = "netgainz.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "netgainz.utils.before_app_uninstall"
# after_app_uninstall = "netgainz.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "netgainz.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Stage 7 WP-2: provision ERPNext masters from NetGainz records. on_update fires
# on insert AND every edit; the handlers are idempotent and best-effort (they
# skip, never block the save, when a prerequisite is missing).
doc_events = {
	"Member": {
		"before_insert": "netgainz.net_gainz.accounting.branch.stamp_default_branch",
		"on_update": "netgainz.net_gainz.accounting.provisioning.on_member_update",
	},
	"Membership": {
		"before_insert": "netgainz.net_gainz.accounting.branch.stamp_default_branch",
		"after_insert": "netgainz.net_gainz.accounting.billing.on_membership_insert",
	},
	"Membership Plan": {
		"on_update": "netgainz.net_gainz.accounting.provisioning.on_plan_update",
	},
	"Expense": {
		"before_insert": "netgainz.net_gainz.accounting.branch.stamp_default_branch",
	},
	"Sales Invoice": {
		# WP-10.3: the native Subscription hardcodes a single 100% payment_schedule
		# row and cannot carry a payment_terms_template, so installments have to be
		# applied to the invoice it generates: attach the template before validate,
		# then restate the amounts as clean numbers (D6) after.
		"before_validate": "netgainz.net_gainz.accounting.billing.on_sales_invoice_before_validate",
		"validate": "netgainz.net_gainz.accounting.billing.on_sales_invoice_validate",
		# Keep a membership's current_sales_invoice pointed at the latest period the
		# native Process Subscription scheduler bills (so renewals collect correctly).
		"on_submit": "netgainz.net_gainz.accounting.billing.on_sales_invoice_submit",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		# Auto-create a draft Profit First sweep on configured allocation days
		# (idempotent; posting still requires manual approval).
		"netgainz.net_gainz.profit_first.schedule.create_scheduled_sweeps",
		# Raise an in-app reminder for memberships due for renewal
		# (idempotent; read-only/notify-only — no email or SMS).
		"netgainz.net_gainz.operations.renewals.notify_due_renewals",
		# Auto-create the upcoming sessions for each active recurring Class Schedule
		# (idempotent; opt-out via the class_auto_generate setting).
		"netgainz.net_gainz.doctype.session_schedule.session_schedule.generate_scheduled_classes",
	],
}

# Testing
# -------

# Run ERPNext's test setup (creates the test Company + standard records such as
# the "Transit" Warehouse Type) before NetGainz tests, since `run-tests --app
# netgainz` only fires this app's before_tests hook.
before_tests = "netgainz.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "netgainz.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "netgainz.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["netgainz.utils.before_request"]
# after_request = ["netgainz.utils.after_request"]

# Job Events
# ----------
# before_job = ["netgainz.utils.before_job"]
# after_job = ["netgainz.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"netgainz.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
