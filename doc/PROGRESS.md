# Implementation progress — 2026-11-14

Branch: `codex/leadflow-crm`. Baseline: `4c4764f` on main. Authoritative specifications remain under `doc/`; no prior ZIP starter or archive was used. The architecture explicitly permits combining Django apps, so the small monolith uses one `crm` app with separate models/forms/access/services/views rather than six thin forwarding apps.

## Implemented phases and requirements

| Phase | Implemented | Evidence |
| --- | --- | --- |
| 0 | Python 3.13, Django 6.1.3; hash-pinned lock; env settings; SQLite and PostgreSQL; Compose/Gunicorn; auth routes; CI | Installed in `.venv`; system/migration checks; container build/start |
| 1 / FR-01 | Seven domain models and migrations; explicit Manager/Employee scopes; manager-only account admin; non-manager staff denied | Permission, direct URL, CSRF, password/login and role tests on both databases |
| 2 / FR-02/03 | Customer create/edit/search/archive; public intake; normalization; no identity overwrite; ambiguous review; atomic history; practical per-process limiter and honeypot | Valid/invalid/ambiguous/repeated email, rollback, queue rendering and spam tests |
| 3 / FR-04/05 | Inquiry create/search/filter/edit; assignment; status corrections; append-only automatic/manual history | Assignment/status/ownership-negative tests; browser manager → employee flow |
| 4 / FR-06/07/08 | Inspection create/edit/cancel; multi-item quotes; exact Decimal calculation; HTML print; tasks/edit/complete/reopen | Yen rounding, quote edits/tampering, invalid inputs, Tokyo overdue and appointment tests; browser workflow |
| 5 / FR-09/10 | Scoped metrics, inclusive Tokyo creation-date cohort, conversion and monthly chart; Japanese responsive UI; idempotent 60-customer seed | Counts/date boundaries/empty-state/seed tests; desktop and 375px browser checks |
| 6 | README/setup/reset, walkthrough, security review, functional Docker and browser validation | Commands and limitations below |

## Verification

- `DJANGO_DEBUG=1 .venv/bin/python manage.py check`: passed, no issues.
- `DJANGO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`: no changes detected.
- SQLite clean test database: **80 tests passed** (`DJANGO_DEBUG=1 .venv/bin/pytest -q`).
- PostgreSQL 17 container test database: **80 tests passed** (`docker compose -p leadflow-review exec -T web pytest -q`).
- SQLite migrations applied successfully. Compose initialized a clean PostgreSQL volume, waited for DB health, applied migrations and served Gunicorn on loopback; restart/recreation also succeeded.
- `seed_demo` ran twice on SQLite; automated seed test verifies 60 customers/inquiries, 5 employees, 54 tasks/appointments, 18 quotes/36 items, and unusable initial passwords. Container demo seeded for browser testing.
- Headless Chromium with installed Playwright **1.62.1**: `tests/browser-smoke.cjs` passed public intake → queue → assignment → employee note → inspection → two-item quote → sample print → overdue task → completion → won. It checked unrelated employee 404 without record leakage, a rendered Chart.js chart, all main navigation screens at 375px, no horizontal overflow and no JS errors. Screenshots are generated locally under ignored `test-results/`.
- Browser checks found and drove fixes for null-owner/system-actor template fallbacks and default task/appointment assignees. Regression tests cover both. The UI uses Japanese labels and disabled chart animation.
- Production-mode `check --deploy --tag security --fail-level WARNING`: passed with generated temporary secret and no silenced checks.
- Full `check --deploy --fail-level WARNING`: intentionally fails **only `mail.E001`** because Django considers the dummy/disabled mailer development-only. Real email is explicitly out of scope (NFR-08); the check is not silenced and SMTP is not enabled to hide this finding.
- `git diff --check` and targeted credential-pattern review: clean; private `.env`, databases, screenshots, caches and virtual environment are ignored. This is a targeted review, not a claim of a dedicated external secret scanner.

## Docker build trust detail

The standard Compose build in this cloud session initially failed with `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain` inside pip. Host package installation was unaffected. Following the [cloud runtime guidance](skill://plugin_connector_1p_c5b7d5df5d7081918f2c4be5a633ed5d/cloud-environment-runtime/references/docker.md), a temporary Dockerfile mounted the host combined CA bundle as a BuildKit secret and set `PIP_CERT` for the install step. The full build then passed with TLS and package hashes verified; the CA was not copied into an image layer. README includes the exact reproducible session-only workaround. The committed Dockerfile remains usable on standard trusted networks. No application feature or test was bypassed.

## Decisions and remaining work

- FR-07's explicit rounding rule takes priority over the architecture's ambiguous subtotal-rounding sentence: retain exact decimal line amounts/subtotal and round tax only. README documents this and the tests use fractional quantities/half-yen tax boundaries.
- Quote transitions to sent synchronize the inquiry explicitly by a documented automatic rule; reversal of a quote does not automatically rewind the inquiry. Task/appointment assignees must be the active inquiry owner; reassignment requires the manager to review existing related assignments.
- Public-facing deployment, TLS termination, static-file hosting in non-debug mode, shared abuse controls, backup/restore, monitoring and real-person privacy review remain outside this local portfolio task. No external deployment or real communications occurred.
- P1 CSV import/export, advanced reporting and native PDF remain intentionally deferred. Printable HTML supports browser PDF printing.
- Remote GitHub Actions execution is not verified by local checks. The workflow is committed. PR/push results will be reported in the task handoff; nothing is merged automatically.
