# Security Policy

NetGainz holds gym members' names, phone numbers and payment records. We take reports
about its security seriously and thank everyone who makes one.

## Reporting a vulnerability

**Please do not open a public issue, discussion or pull request for a security problem.**

Report it privately through GitHub instead:

1. Go to the [Security tab](https://github.com/lokashche/netgainz/security) of this repository.
2. Click **Report a vulnerability**.
3. Tell us what you found, how to reproduce it, and what an attacker could do with it.

Only the maintainers can see the report. We aim to reply within 7 days, keep you updated
while we fix it, and credit you in the release notes if you would like that.

## What counts

Examples we especially want to hear about:

- One gym, branch or user seeing or changing another's data
- A Gym Staff user doing something only the Gym Owner should (refunds, write-offs, discounts)
- Member personal data exposed through the owner app or its API routes
- Money records (invoices, payments, Profit First allocations) that can be altered or
  forged without the proper permission

Bugs in Frappe, ERPNext or India Compliance themselves should go to those projects,
though we are glad to hear if NetGainz makes one worse.

## Supported versions

Security fixes land on the `develop` branch and ship in the next release. Older releases
are not patched.
