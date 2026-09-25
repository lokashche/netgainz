# Contributing to NetGainz

NetGainz is a gym accounting and operations application built on
[Frappe](https://frappeframework.com/) and [ERPNext](https://erpnext.com/), with a
Next.js owner app on top. Contributions are welcome — bug reports, documentation,
and code alike.

Please read the licensing section before you send your first patch.

---

## Licensing and the sign-off

NetGainz is licensed under the **GNU Affero General Public License v3.0 or later**
(see [LICENSE](./LICENSE) and [RELICENSING.md](./RELICENSING.md)). Contributions are
accepted under the same licence — you keep the copyright in your own work.

We use the **Developer Certificate of Origin** ([DCO](https://developercertificate.org/)).
It is a one-line assertion that you wrote the patch, or otherwise have the right to
submit it under AGPLv3. Sign each commit with `-s`:

```bash
git commit -s -m "fix: correct the tariff rounding on part-month invoices"
```

That appends a `Signed-off-by: Your Name <you@example.com>` trailer. Forgot it on the
last commit? `git commit --amend -s`. Across a branch? `git rebase --signoff develop`.

We do not ask for a CLA and do not ask you to assign copyright.

---

## Ways to contribute

- **Report a bug.** Open an issue with what you did, what you expected, and what
  happened. Include your Frappe/ERPNext versions and any traceback.
- **Pick up an issue.** Issues tagged `good first issue` are scoped to be
  self-contained and safe for a first patch. Comment on one to claim it.
- **Improve the docs.** The README and this file are fair game.
- **Translate.** The owner app speaks plain English today; gym owners across India do not
  all read English first.

### Your first contribution, step by step

1. Pick a `good first issue` and comment "I'd like to take this" so nobody doubles up.
2. Fork the repository and clone your fork into `frappe-bench/apps/netgainz`.
3. Create a branch off `develop`: `git switch -c fix/short-description develop`.
4. Make the change, add or update a test, and run that test module (see below).
5. Commit with a sign-off (`git commit -s`) and push to your fork.
6. Open a pull request against `develop`. The template will ask for the checklist below.

Stuck at any step? Ask on the issue. A half-finished question is better than a silent
hour.

If you are planning something large, open an issue to discuss it first. NetGainz has
opinionated architecture (see [House rules](#house-rules)) and it is kinder to find a
mismatch before you have written the code.

---

## Development setup

NetGainz needs a Frappe bench with ERPNext, India Compliance, and the payments app
installed alongside it. India Compliance is a hard dependency — the tax rails assume it.

```bash
# Inside an existing bench on Frappe v15.118.0 — the versions below match CI and production
bench get-app erpnext --branch v15.119.2
bench get-app https://github.com/frappe/payments --branch version-15
bench get-app https://github.com/resilient-tech/india-compliance --branch v15.31.3
bench get-app https://github.com/lokashche/netgainz --branch develop

bench new-site netgainz.localhost \
  --install-app erpnext \
  --install-app payments \
  --install-app india_compliance \
  --install-app netgainz
```

**Keep these versions together.** ERPNext and India Compliance move in step: newer ERPNext
releases pass India Compliance an extra argument that older India Compliance versions do not
accept, and every invoice save then fails. When CI's pins in `.github/workflows/ci.yml`
change, this section changes with them. The `payments` app supplies the Payment Gateway
doctype that Frappe's test-record sweep expects — without it, test runs fail with
`Payment Gateway not found`.

### Sample data

For something to click around in, seed the demo gym on a **separate** site — the steps are
in the [README](./README.md#try-it-locally). Never seed it into a site holding a real gym:
dashboards read the whole site, so the two would mix.

### Repository layout

| Path | What it is |
| --- | --- |
| `netgainz/net_gainz/` | The Frappe app — doctypes, business logic, tests |
| `netgainz/patches/` | Schema/data migrations, registered in `patches.txt` |
| `owner-app/` | Next.js gym-owner UI, with a BFF layer under `app/api/` |
| `.github/workflows/` | CI (`ci.yml` = tests, `lint.yml` = ruff) |

---

## Running the tests

**Run tests per module, never app-wide.**

```bash
# Correct
bench --site netgainz.localhost run-tests --module netgainz.net_gainz.accounting.test_billing

# Everything, one module at a time (this is what CI does)
modules=$(cd apps/netgainz && find netgainz -name 'test_*.py' | sed 's#/#.#g; s#\.py$##')
for m in $modules; do bench --site netgainz.localhost run-tests --module "$m"; done
```

Do **not** use `bench run-tests --app netgainz`. With India Compliance installed,
Frappe's app-wide `make_test_records` sweep tries to build ERPNext fixtures (Payment
Gateway Account, Item Tax Template, and friends) that India Compliance's GST validation
rejects. The failures are real, but they have nothing to do with your change. Per-module
runs build only that module's own dependencies and pass cleanly.

Two more things that bite people writing tests:

- **Never call `frappe.db.commit()` in `setUp`.** Frappe rolls each test back; a commit
  leaks state into every test that follows.
- Tests run as **Administrator**. If you are testing a permission rule, switch users
  explicitly — otherwise you are testing nothing.

New behaviour needs a test. Find the test module nearest your change and follow its shape.

---

## Linting and formatting

The repo uses `pre-commit`. Install it once and it runs on every commit:

```bash
cd apps/netgainz
pre-commit install
```

It runs ruff (import sort, lint, format), prettier, and eslint. CI enforces
`ruff check .` and `ruff format --check .`, so a clean pre-commit run means a green
lint job.

### Owner app

```bash
cd owner-app
npm install
npm run dev          # http://localhost:3005
npm run lint
npx tsc --noEmit     # type-check; not run by CI, but reviewers will ask
```

One recurring trap: Next.js route params arrive **URL-encoded**. On any detail page keyed
by a name rather than an ID, decode the param — in both the page and its BFF route — or
records whose names contain spaces will 404.

---

## Branches, commits, and pull requests

- `develop` is the default branch and the target for pull requests.
- `main` holds tagged releases. Do not open PRs against it.
- Work on a branch off `develop`, named `feature/...` or `fix/...`.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(op4): PT session packs and day passes
fix(owner-app): Start Billing now reports why the preview failed
test: tolerate per-row tax rounding in the go-live assertion
docs: document the per-module test runner
```

### Before you open the PR

- [ ] Commits are signed off (`git commit -s`)
- [ ] Tests pass for every module you touched
- [ ] `pre-commit run --all-files` is clean
- [ ] New behaviour has a test
- [ ] The PR description says what changed and why, and links the issue it closes

CI runs tests and lint on every pull request. A red build will not be merged.

---

## House rules

These are the architectural commitments a reviewer will hold your patch to. They are
not style preferences — breaking one means the change gets sent back.

**ERPNext is an engine, not a user interface.** No gym owner ever opens Frappe Desk.
Every ERPNext master — Customer, Item, Subscription Plan, Cost Center — is provisioned
silently in code. If your feature requires someone to go and configure something in Desk,
it is not finished. `provisioning.py` is the reference pattern.

**Every new doctype carries a branch from birth.** NetGainz is multi-branch and
multi-gym by design. Adding the branch dimension to financial records after the fact is
painful, so new doctypes get it on day one, defaulting to the gym's main branch. Nothing
is hardcoded to a single gym.

**Profit First is cash-basis, always.** The Profit First engine reads **Payment
Entries** — money that actually arrived. It must never read Sales Invoices. Accrual
accounting, deferred revenue, and discounts all sit on the invoice side and must leave
the cash reads untouched.

**Money is computed in minor units.** Use the helpers in `profit_first/calc.py`
(`to_paise` / `to_rupees` / `round_half_away`) rather than doing float arithmetic on
rupees.

---

## Code of Conduct

Everyone taking part in NetGainz is expected to follow the
[Code of Conduct](./CODE_OF_CONDUCT.md).

## Questions

Open an issue. For anything touching security or member data, please do not open a
public issue — follow [SECURITY.md](./SECURITY.md) instead.
