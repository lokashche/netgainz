[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

### Net Gainz

Gym Accounting Application

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app netgainz
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/netgainz
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later).
See [LICENSE](./LICENSE) for the full text.

NetGainz was originally released under the MIT License. It was relicensed
to AGPLv3 in 2026 to protect the project against hosted-fork competition
while keeping self-hosting fully free. The story of this change is
documented in [RELICENSING.md](./RELICENSING.md).
