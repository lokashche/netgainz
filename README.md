[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/lokashche/netgainz/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/lokashche/netgainz/actions/workflows/ci.yml)

# NetGainz

**Accounting and operations for small gyms, built on the Profit First method.**

Most small gyms, or "microgyms", run on a notebook, a spreadsheet and a WhatsApp group.
The owner knows how many members they have. They often don't know whether the gym makes
money. NetGainz handles the daily work (members, fees, check-ins, expenses) and keeps
proper books underneath. It also shows the owner, in plain language, how much of this
month's cash is really theirs to keep.

NetGainz is free and open source under the AGPL-3.0. It is in use at a real gym, and new
contributors are welcome.

---

## What it does

| Area | What the gym owner gets |
| --- | --- |
| **Members** | Registration, member codes, search, referrals, bulk import from a spreadsheet |
| **Plans & billing** | Monthly / quarterly / yearly plans, per-member pricing, part-payments and instalments, automatic invoices |
| **Money in** | Payments, collections list ("who owes what"), refunds, write-offs, advances |
| **Money out** | Expenses by category, repeating expenses |
| **Profit First** | Every rupee that arrives is split into Profit, Owner's Pay, Tax and Operating buckets, with a dashboard that shows whether the gym is healthy |
| **Discounts & offers** | Per-member discounts, campaigns, coupon codes, free trials, owner-PIN approval, and a preview of what a discount does to profit |
| **Gym operations** | Check-in desk, attendance, churn-risk alerts, enquiry → trial → member pipeline, freeze / upgrade / cancel, PT packs, day passes, fitness assessments |
| **Coaches & classes** | Instructors, programs, class timetable, commissions |

Behind the scenes, every invoice and payment is a real ERPNext accounting entry (GST-ready
through India Compliance). **The gym owner never sees ERPNext.** They use the NetGainz owner
app, a simple web app that works on a phone.

## How it is built

```
 ┌──────────────────────────┐
 │  Owner app (Next.js)     │  what the gym owner uses: phone, tablet, desktop
 │  owner-app/              │
 └────────────┬─────────────┘
              │ REST calls through a thin backend-for-frontend (owner-app/app/api/)
 ┌────────────▼─────────────┐
 │  NetGainz (Frappe app)   │  gym logic, Profit First engine, provisioning
 │  netgainz/net_gainz/     │
 └────────────┬─────────────┘
              │ creates Customers, Items, Invoices, Payments silently
 ┌────────────▼─────────────┐
 │  ERPNext + India         │  the accounting engine (never shown to the owner)
 │  Compliance (Frappe v15) │
 └──────────────────────────┘
```

- **Backend:** Python, [Frappe Framework](https://frappeframework.com/) v15, [ERPNext](https://erpnext.com/) v15, [India Compliance](https://github.com/resilient-tech/india-compliance)
- **Owner app:** Next.js, React, TypeScript
- **Multi-gym by design:** one site per gym, and branches built into every record from day one

## Try it locally

You need a working [Frappe bench](https://frappeframework.com/docs/user/en/installation)
(Python 3.10+, Node 18+, MariaDB, Redis). Then run the following. The versions match what
CI and production run.

```bash
cd frappe-bench
bench get-app erpnext --branch v15.119.2
bench get-app https://github.com/frappe/payments --branch version-15
bench get-app https://github.com/resilient-tech/india-compliance --branch v15.31.3
bench get-app https://github.com/lokashche/netgainz --branch develop

bench new-site demo.localhost \
  --install-app erpnext --install-app payments \
  --install-app india_compliance --install-app netgainz
bench --site demo.localhost set-config developer_mode 1
bench start
```

**Load the demo gym.** Open `http://demo.localhost:8000` and finish the ERPNext setup wizard
once. Use the company **Iron Forge Fitness**, country **India**, currency **INR**. Then:

```bash
bench --site demo.localhost execute netgainz.net_gainz.demo.gym.seed_demo_gym
```

This creates a believable gym with six months of history: members, plans, invoices,
payments, expenses, offers and a class timetable. It goes through the same code paths the
real product uses. Re-running it is safe.

**Run the owner app:**

```bash
cd apps/netgainz/owner-app
cp .env.local.example .env.local      # set FRAPPE_URL=http://demo.localhost:8000
npm install
npm run dev                           # http://localhost:3005
```

Sign in as `Administrator` with the admin password you chose for the site.

> Use a separate site for the demo. Dashboards read the whole site, so demo data mixed into
> a real gym's site would show up in its numbers.

## Where it is going

NetGainz is built in stages. Stages 1–8 are done: members, billing, expenses, Profit First,
coaches and classes, accounting on ERPNext, and discounts. Stage 9 (daily gym operations) is
nearly done. Next up:

- **Member messaging:** WhatsApp / SMS reminders
- **Branches:** run several branches from one owner app, with profit per branch
- **Reports:** retention, churn, lifetime value, coach performance
- **Multi-gym hosting:** self-service onboarding for new gyms
- **Member app:** members pay fees, book classes and check in from their phone

## Contributing

Contributions are welcome: code, bug reports, docs and translations.

- New here? Read **[CONTRIBUTING.md](./CONTRIBUTING.md)**. It walks you from setup to your
  first pull request.
- Looking for something to do? Try issues labelled
  [`good first issue`](https://github.com/lokashche/netgainz/labels/good%20first%20issue).
- Please follow our [Code of Conduct](./CODE_OF_CONDUCT.md).
- Found a security problem? Don't open a public issue. See [SECURITY.md](./SECURITY.md).

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See [LICENSE](./LICENSE).

In short: you can use, self-host, change and share NetGainz for free. If you offer a
changed version to others as a hosted service, you must share your changes under the same
license. NetGainz started under the MIT License and moved to AGPLv3 in 2026.
[RELICENSING.md](./RELICENSING.md) explains why.
