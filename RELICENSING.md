# Relicensing: MIT → AGPL-3.0-or-later

## Summary

NetGainz was originally published under the **MIT License**. As of **2026**, the
project is relicensed to the **GNU Affero General Public License, version 3.0 or
later (AGPL-3.0-or-later)**. The full license text lives in [LICENSE](./LICENSE).

## Why

NetGainz is a gym accounting and operations application intended to stay free for
the people who run it. MIT permits anyone to take the code, run it as a hosted
service, and offer no improvements back. AGPLv3 keeps the software free to
**use, self-host, modify, and redistribute**, while closing the "hosted fork"
gap: anyone who offers NetGainz to others over a network must make their modified
source available to those users under the same terms.

In short:

- **Self-hosting stays completely free.** Running NetGainz for your own gym (or
  gyms) imposes no new obligation.
- **Modifications remain yours** — until you distribute the software or offer it
  as a network service, at which point AGPLv3's copyleft applies.
- **Hosted forks must share back.** Offering a modified NetGainz as a service
  requires publishing the corresponding source under AGPLv3.

## What changed

- `LICENSE` — MIT text replaced with the AGPLv3 text (file also renamed from
  `license.txt` to the conventional `LICENSE`).
- `pyproject.toml` — `[project].license` set to `AGPL-3.0-or-later`.
- `netgainz/hooks.py` — `app_license` set to `agpl-3.0`.
- `README.md` — license section and badge updated.

## Scope and authority

All contributions to NetGainz to date were authored by, or assigned to,
**Quantslate Solutions**, the sole copyright holder, which authorizes this
relicensing. Versions previously released under MIT remain available under MIT;
this change applies from the relicensing commit forward.

Nothing in this document is legal advice. If you have questions about how the
AGPLv3 applies to your use of NetGainz, consult a qualified attorney.
